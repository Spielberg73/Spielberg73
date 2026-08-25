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

import json
import os
import secrets
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Tuple
from urllib.parse import parse_qs, urlparse

from . import sistemas
from .build import build_project
from .codegen import generar_para_sistema
from .errors import ProjectError
from .preview import write_preview
from .project import load_project

MAX_YAML = 4 * 1024 * 1024      # un game.yaml de mas de 4 MB es un error, no un juego


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
    with open(ruta, "w", encoding="utf-8") as fh:
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
        if urlparse(self.path).path != "/compilar":
            return self._json(404, {"ok": False, "lineas": ["no hay nada aqui"]})
        largo = int(self.headers.get("Content-Length") or 0)
        if largo <= 0 or largo > MAX_YAML:
            return self._json(400, {"ok": False, "lineas": ["peticion vacia o enorme"]})
        try:
            peticion = json.loads(self.rfile.read(largo).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return self._json(400, {"ok": False, "lineas": ["no entiendo la peticion"]})

        texto = peticion.get("yaml") or ""
        nombre = str(peticion.get("sistema") or "")
        if nombre and nombre not in [s.nombre for s in sistemas.disponibles()]:
            return self._json(400, {"ok": False, "lineas": ["no conozco esa maquina"]})
        with self.server.candado:
            try:
                if texto:
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
