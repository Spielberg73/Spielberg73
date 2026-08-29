"""Servidor local del preview: deja que el editor genere la ROM.

El preview es una pagina web, y una pagina no puede compilar nada. Cuando
`ngplat probar` levanta este servidor, el boton "generar ROM" del editor manda
el `game.yaml` que se esta editando y el servidor hace lo mismo que
`ngplat compilar`: lo guarda en el proyecto, genera el codigo y las ROMs de
graficos y, si hay un compilador de 68000, llama a `make`.

Solo escucha en 127.0.0.1 y exige una clave que se genera al arrancar y que va
en la direccion que se abre en el navegador. Sin eso, cualquier otra pagina que
tuvieras abierta podria escribir en tu `game.yaml` y lanzar un `make`: los
navegadores dejan que cualquier sitio mande peticiones a localhost.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import secrets
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Tuple
from urllib.parse import parse_qs, urlparse

from . import historial, miniyaml, sistemas
from .build import build_project
from .codegen import generar_para_sistema
from .errors import ProjectError
from .preview import write_preview
from .project import load_project

MAX_YAML = 4 * 1024 * 1024      # un game.yaml de mas de 4 MB es un error, no un juego
MAX_DIBUJO = 2 * 1024 * 1024    # y un PNG de mas de 2 MB tampoco es un sprite
MAX_GUARDADO = 32 * 1024 * 1024  # el yaml mas todos los dibujos de una tacada
MAX_DIBUJOS_POR_GUARDADO = 64


def compilador_de(sistema) -> str:
    """El compilador de 68000 que haya en el PATH para esa maquina, o ''."""
    candidatos = {
        "neogeo": ["m68k-neogeo-elf-gcc", "m68k-elf-gcc"],
        "megadrive": ["m68k-elf-gcc", "m68k-linux-gnu-gcc"],
        "amiga": ["m68k-amigaos-gcc", "vc", "m68k-elf-gcc", "m68k-linux-gnu-gcc"],
    }
    for nombre in candidatos.get(sistema.nombre, ["m68k-elf-gcc"]):
        if shutil.which(nombre):
            return nombre
    return ""


def ruta_del_yaml(raiz: str) -> str:
    for nombre in ("game.yaml", "juego.yaml", "game.yml", "juego.yml"):
        ruta = os.path.join(raiz, nombre)
        if os.path.isfile(ruta):
            return ruta
    return os.path.join(raiz, "game.yaml")


def guardar_yaml(raiz: str, texto: str) -> str:
    """Escribe el game.yaml dejando antes una copia .bak del anterior."""
    ruta = ruta_del_yaml(raiz)
    if os.path.isfile(ruta):
        shutil.copyfile(ruta, ruta + ".bak")
    with open(ruta, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(texto)
    return ruta


def deshacer_guardado(raiz: str) -> bool:
    """Devuelve el game.yaml a como estaba antes del ultimo guardado.

    Si lo que manda el editor no se puede ni leer, dejarlo escrito seria
    cambiar un proyecto que funcionaba por uno que no arranca."""
    ruta = ruta_del_yaml(raiz)
    if not os.path.isfile(ruta + ".bak"):
        return False
    shutil.copyfile(ruta + ".bak", ruta)
    return True


def guardar_proyecto(raiz: str, texto: str, dibujos: List[Dict]) -> Tuple[bool, List[str]]:
    """Escribe el game.yaml y los dibujos **sin compilar nada**.

    Esta es la diferencia que hace que un juego grande no pierda trabajo: antes
    la unica forma de escribir en disco desde el editor era el boton de
    compilar, que ademas deshacia el guardado si el proyecto no compilaba. Un
    juego a medias -un nivel empezado, un enemigo sin colocar- no compila, y era
    justo lo que no se podia guardar.

    Aqui se guarda igual. Lo unico que se rechaza es un yaml que no se pueda ni
    leer como yaml: eso no seria trabajo a medias sino un archivo roto, y el
    editor no deberia generarlo nunca. Lo que si se avisa, sin dejar de
    guardar, es de los problemas del proyecto: que le falta la meta, que un
    nivel pide mas llaves de las que hay, lo que sea.

    Antes de escribir nada se deja una copia de como estaba todo, asi que
    tambien se puede volver atras (ver historial.py).
    """
    lineas: List[str] = []
    if texto:
        try:
            miniyaml.loads(texto)
        except miniyaml.YamlError as error:
            return (False, ["el game.yaml no se puede leer: %s" % error,
                            "no se ha escrito nada"])

    try:
        copia = historial.copiar(raiz, "editor")
    except historial.ErrorHistorial as error:
        copia = None
        lineas.append("aviso: no se ha podido guardar copia (%s)" % error)
    if copia is not None:
        lineas.append("copia %04d guardada por si acaso (ngplat historial)"
                      % copia["numero"])

    escritos: List[str] = []
    try:
        if texto:
            guardar_yaml(raiz, texto)
            escritos.append(os.path.basename(ruta_del_yaml(raiz)))
        for dibujo in dibujos:
            destino = ruta_de_dibujo(raiz, str(dibujo.get("ruta") or ""))
            crudo = png_de_data_uri(str(dibujo.get("datos") or ""))
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, "wb") as fh:
                fh.write(crudo)
            escritos.append(str(dibujo.get("ruta")))
    except ValueError as error:
        lineas.append("un dibujo no se ha podido guardar: %s" % error)
        return (False, lineas)
    except OSError as error:
        lineas.append("no se ha podido escribir: %s" % error)
        return (False, lineas)

    lineas.append("guardado: " + ", ".join(escritos) if escritos
                  else "no habia nada nuevo que guardar")

    # Se guarda igual, pero se dice si el proyecto esta entero o no.
    try:
        proyecto = load_project(raiz)
        lineas.extend("aviso: " + a for a in proyecto.warnings)
    except ProjectError as error:
        lineas.append("guardado, pero todavia no compila: %s" % error)
        if getattr(error, "hint", ""):
            lineas.append(error.hint)
    return (True, lineas)


def compilar(raiz: str, nombre_sistema: str, hacer_make: bool = True
             ) -> Tuple[bool, List[str]]:
    """Genera el proyecto para esa maquina. Devuelve (ha ido bien, lineas)."""
    lineas: List[str] = []
    try:
        project = load_project(raiz)
        lineas.extend("aviso: " + a for a in project.warnings)
        sistema = sistemas.obtener(nombre_sistema or project.system)
        build = build_project(project)
        sistema.preparar(build)
        lineas.extend("aviso: " + a for a in sistema.comprobar(build))
        salida = os.path.join(raiz, "build", sistema.nombre)
        os.makedirs(salida, exist_ok=True)
        _binarios, resultado = generar_para_sistema(build, salida, sistema, "202")
        lineas.append("proyecto para %s generado en build/%s"
                      % (sistema.titulo, sistema.nombre))
        lineas.extend(resultado.resumen)
    except ProjectError as error:
        lineas.append(str(error))
        if getattr(error, "hint", ""):
            lineas.append(error.hint)
        return (False, lineas)

    if not hacer_make:
        return (True, lineas)
    if not compilador_de(sistema):
        lineas.append("no hay compilador de 68000 en el PATH: falta el binario")
        lineas.append("cuando lo tengas:  cd build/%s && make" % sistema.nombre)
        return (True, lineas)

    hecho = subprocess.run(["make"], cwd=salida, capture_output=True, text=True)
    salida_make = (hecho.stdout + hecho.stderr).strip().splitlines()
    if hecho.returncode != 0:
        # cuando falla si interesa verlo todo: ahi esta el error del compilador
        lineas.extend(salida_make[-30:])
        lineas.append("make ha fallado (codigo %d)" % hecho.returncode)
        return (False, lineas)
    # cuando va bien, las ordenes de gcc no le dicen nada a nadie: solo se
    # dejan los avisos y las lineas que el propio Makefile imprime
    lineas.extend(l for l in salida_make if _interesa(l))
    lineas.append("binario construido en build/%s/%s"
                  % (sistema.nombre, sistema.carpeta_salida))
    return (True, lineas)


def ruta_de_dibujo(raiz: str, ruta: str) -> str:
    """Comprueba que la ruta que manda el editor es un PNG dentro del proyecto.

    El servidor solo escucha en localhost y pide una clave, pero aun asi no se
    fia de la ruta: se resuelve contra la raiz del proyecto y tiene que caer
    dentro. Asi un '../../.ssh/algo' no sale de la carpeta.
    """
    if not ruta or not ruta.lower().endswith(".png"):
        raise ValueError("solo se guardan archivos .png")
    if os.path.isabs(ruta) or "\\" in ruta:
        raise ValueError("la ruta tiene que ser relativa al proyecto")
    base = os.path.realpath(raiz)
    destino = os.path.realpath(os.path.join(base, ruta))
    if destino != base and not destino.startswith(base + os.sep):
        raise ValueError("la ruta se sale del proyecto")
    return destino


def png_de_data_uri(datos: str) -> bytes:
    """Saca los bytes de un data: URI y comprueba que es un PNG de verdad."""
    marca = "base64,"
    if not datos.startswith("data:image/png;") or marca not in datos:
        raise ValueError("se esperaba un PNG en base64")
    try:
        crudo = base64.b64decode(datos.split(marca, 1)[1], validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("el base64 no vale")
    if len(crudo) > MAX_DIBUJO:
        raise ValueError("el dibujo es demasiado grande")
    if crudo[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("eso no es un PNG")
    return crudo


def _interesa(linea: str) -> bool:
    """Si esa linea de make merece salir en el registro del editor."""
    if "warning:" in linea or "error:" in linea:
        return True
    primera = linea.split(" ", 1)[0]
    return not (primera.endswith("gcc") or primera.endswith("objcopy")
                or primera.endswith("ld") or primera in ("make", "python3", "dd")
                or primera.startswith("/") or primera.startswith("make["))


class _Manejador(BaseHTTPRequestHandler):
    server_version = "NeoPlat"
    sys_version = ""

    # --- lo minimo para no dejar la puerta abierta ----------------------

    def _clave_ok(self) -> bool:
        partes = urlparse(self.path)
        query = parse_qs(partes.query)
        dada = (self.headers.get("X-NeoPlat")
                or (query.get("t") or [""])[0])
        return secrets.compare_digest(dada, self.server.clave)

    def _origen_ok(self) -> bool:
        """Que la peticion venga de esta misma pagina, no de otra pestana."""
        origen = self.headers.get("Origin")
        if origen is None:
            return True                       # no es una peticion de otra web
        return origen in self.server.origenes

    def _anfitrion_ok(self) -> bool:
        """Corta el 'DNS rebinding': solo se responde a localhost."""
        anfitrion = (self.headers.get("Host") or "").split(":")[0]
        return anfitrion in ("127.0.0.1", "localhost", "[::1]", "::1")

    def _responder(self, codigo: int, cuerpo: bytes, tipo: str) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, codigo: int, datos: Dict) -> None:
        self._responder(codigo, json.dumps(datos).encode("utf-8"),
                        "application/json; charset=utf-8")

    # --- rutas ----------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 (lo llama http.server)
        if not self._anfitrion_ok():
            return self._responder(403, b"solo localhost", "text/plain")
        camino = urlparse(self.path).path
        if camino not in ("/", "/preview.html"):
            return self._responder(404, b"no hay nada aqui", "text/plain")
        if not self._clave_ok():
            return self._responder(
                403, "Falta la clave. Abre la direccion que imprimio "
                     "'ngplat probar'.".encode("utf-8"), "text/plain; charset=utf-8")
        with open(self.server.preview, "rb") as fh:
            self._responder(200, fh.read(), "text/html; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        if not self._anfitrion_ok():
            return self._responder(403, b"solo localhost", "text/plain")
        if not self._clave_ok() or not self._origen_ok():
            return self._json(403, {"ok": False, "lineas": ["clave incorrecta"]})
        camino = urlparse(self.path).path
        if camino not in ("/compilar", "/dibujo", "/guardar", "/historial",
                          "/recuperar"):
            return self._json(404, {"ok": False, "lineas": ["no hay nada aqui"]})
        largo = int(self.headers.get("Content-Length") or 0)
        topes = {"/dibujo": MAX_DIBUJO, "/guardar": MAX_GUARDADO}
        tope = topes.get(camino, MAX_YAML)
        if camino in ("/historial", "/recuperar") and largo == 0:
            largo = 0                      # estas dos pueden venir sin cuerpo
        if largo > tope or (largo <= 0 and camino not in ("/historial", "/recuperar")):
            return self._json(400, {"ok": False, "lineas": ["peticion vacia o enorme"]})
        try:
            crudo = self.rfile.read(largo) if largo > 0 else b"{}"
            peticion = json.loads(crudo.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return self._json(400, {"ok": False, "lineas": ["no entiendo la peticion"]})
        if not isinstance(peticion, dict):
            return self._json(400, {"ok": False, "lineas": ["no entiendo la peticion"]})
        if camino == "/dibujo":
            return self._guardar_dibujo(peticion)
        if camino == "/guardar":
            return self._guardar(peticion)
        if camino == "/historial":
            return self._historial()
        if camino == "/recuperar":
            return self._recuperar(peticion)

        texto = peticion.get("yaml") or ""
        nombre = str(peticion.get("sistema") or "")
        if nombre and nombre not in [s.nombre for s in sistemas.disponibles()]:
            return self._json(400, {"ok": False, "lineas": ["no conozco esa maquina"]})
        with self.server.candado:
            try:
                if texto:
                    # copia antes de pisar nada, igual que en /guardar
                    try:
                        historial.copiar(self.server.raiz, "compilar")
                    except historial.ErrorHistorial:
                        pass
                    guardar_yaml(self.server.raiz, texto)
                ok, lineas = compilar(self.server.raiz, nombre,
                                      bool(peticion.get("make", True)))
                if not ok and texto and deshacer_guardado(self.server.raiz):
                    lineas.append("el game.yaml se ha dejado como estaba")
                if ok:
                    # el preview se regenera para que refleje lo recien guardado
                    project = load_project(self.server.raiz)
                    build = build_project(project)
                    sistema = sistemas.obtener(nombre or project.system)
                    sistema.preparar(build)
                    write_preview(build, self.server.preview)
                    lineas.append("game.yaml guardado (la copia anterior queda "
                                  "en game.yaml.bak)")
            except Exception as error:                    # noqa: BLE001
                ok, lineas = False, ["error inesperado: %s" % error]
        self._json(200, {"ok": ok, "lineas": lineas})

    def _guardar(self, peticion) -> None:
        """Guardar de verdad: el yaml y los dibujos, y sin compilar."""
        texto = peticion.get("yaml") or ""
        dibujos = peticion.get("dibujos") or []
        if not isinstance(dibujos, list) or len(dibujos) > MAX_DIBUJOS_POR_GUARDADO:
            return self._json(400, {"ok": False,
                                    "lineas": ["demasiados dibujos de una vez"]})
        dibujos = [d for d in dibujos if isinstance(d, dict)]
        with self.server.candado:
            try:
                ok, lineas = guardar_proyecto(self.server.raiz, texto, dibujos)
            except Exception as error:                    # noqa: BLE001
                ok, lineas = False, ["error inesperado: %s" % error]
        self._json(200, {"ok": ok, "lineas": lineas})

    def _historial(self) -> None:
        """Las copias que hay, para que el editor las pueda ensenar."""
        with self.server.candado:
            try:
                copias = historial.listar(self.server.raiz)
            except Exception as error:                    # noqa: BLE001
                return self._json(200, {"ok": False, "lineas": [str(error)],
                                        "copias": []})
        self._json(200, {"ok": True, "copias": copias})

    def _recuperar(self, peticion) -> None:
        """Devuelve el proyecto a una copia y regenera el preview."""
        try:
            numero = int(peticion.get("copia"))
        except (TypeError, ValueError):
            return self._json(400, {"ok": False, "lineas": ["falta el numero de copia"]})
        with self.server.candado:
            try:
                escritos, sobrantes = historial.recuperar(self.server.raiz, numero)
            except historial.ErrorHistorial as error:
                return self._json(200, {"ok": False, "lineas": [str(error)]})
            except Exception as error:                    # noqa: BLE001
                return self._json(200, {"ok": False,
                                        "lineas": ["error inesperado: %s" % error]})
            lineas = ["proyecto devuelto a la copia %04d (%d archivos)"
                      % (numero, len(escritos))]
            for relativo in sobrantes:
                lineas.append("quitado: %s" % relativo)
            # el preview se rehace con lo recuperado; si esa version no
            # compilaba, se dice y ya, que para eso se ha recuperado
            try:
                project = load_project(self.server.raiz)
                build = build_project(project)
                sistema = sistemas.obtener(project.system)
                sistema.preparar(build)
                write_preview(build, self.server.preview)
                lineas.append("recarga la pagina para verlo")
            except ProjectError as error:
                lineas.append("ojo: esa copia todavia no compila: %s" % error)
        self._json(200, {"ok": True, "lineas": lineas})

    def _guardar_dibujo(self, peticion) -> None:
        """Guarda un PNG del editor de dibujos dentro del proyecto."""
        ruta = str(peticion.get("ruta") or "")
        datos = str(peticion.get("datos") or "")
        try:
            destino = ruta_de_dibujo(self.server.raiz, ruta)
            crudo = png_de_data_uri(datos)
        except ValueError as error:
            return self._json(400, {"ok": False, "error": str(error)})
        with self.server.candado:
            try:
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                with open(destino, "wb") as fh:
                    fh.write(crudo)
            except OSError as error:
                return self._json(500, {"ok": False, "error": str(error)})
        self._json(200, {"ok": True, "ruta": ruta, "bytes": len(crudo)})

    def log_message(self, formato, *args):   # noqa: A003 (firma de http.server)
        pass                                  # sin ruido en la terminal


def crear(raiz: str, preview: str, puerto: int = 0) -> Tuple[ThreadingHTTPServer, str]:
    """Levanta el servidor y devuelve (servidor, direccion con la clave)."""
    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), _Manejador)
    servidor.raiz = os.path.abspath(raiz)
    servidor.preview = os.path.abspath(preview)
    servidor.clave = secrets.token_urlsafe(24)
    servidor.candado = threading.Lock()
    puerto_real = servidor.server_address[1]
    servidor.origenes = ("http://127.0.0.1:%d" % puerto_real,
                         "http://localhost:%d" % puerto_real)
    return servidor, "http://127.0.0.1:%d/?t=%s" % (puerto_real, servidor.clave)
