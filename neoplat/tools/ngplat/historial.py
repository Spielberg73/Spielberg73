"""Copias del proyecto: guardar sin miedo y poder volver atras.

El proyecto de NeoPlat **ya es** su propio formato de guardado: una carpeta con
un `game.yaml` de texto, los PNG y los WAV. Eso esta bien para leerlo y para
meterlo en git, pero no protege de lo de siempre: guardas encima de algo que
funcionaba, o el editor escribe una version a medias y no hay a donde volver.

Aqui vive la otra mitad: **el historial**. Cada vez que algo escribe en el
proyecto (el editor del navegador, `ngplat copia`, un `ngplat compilar` que
guarda el yaml) se deja antes una instantanea de como estaba todo, en:

    <proyecto>/.neoplat/historial/0007-20260829-174501-editor.zip

Dentro va el proyecto entero **menos lo que se puede volver a generar**
(`build/`, `preview.html` y el propio `.neoplat/`), asi que una instantanea de
un juego grande son unos pocos cientos de KB. Se guardan las ultimas
`MAX_COPIAS` y las mas viejas se van cayendo.

Dos detalles que importan:

  - **No se repite lo que no ha cambiado.** Cada instantanea lleva la huella
    del contenido; si guardas dos veces sin tocar nada, la segunda no ocupa
    nada porque no se escribe.
  - **Recuperar tambien deja copia.** Antes de devolver el proyecto a una
    version anterior se guarda como esta ahora, asi que equivocarse al
    recuperar tampoco pierde nada.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import zipfile
from typing import Dict, List, Optional, Tuple

CARPETA = ".neoplat"
HISTORIAL = os.path.join(CARPETA, "historial")
MAX_COPIAS = 40
MAX_BYTES = 64 * 1024 * 1024      # un proyecto de mas de 64 MB no es un juego

# Lo que no entra en la copia: se genera solo a partir de lo que si entra.
EXCLUIDOS = (CARPETA, "build", "dist", "__pycache__", ".git")
ARCHIVOS_FUERA = ("preview.html",)
# Y lo que no tiene sentido guardar aunque este suelto en la carpeta.
SUFIJOS_FUERA = (".pyc", ".zip", ".adf", ".st", ".j64", ".bin", ".rom")

NOMBRE = re.compile(r"^(\d{4})-(\d{8}-\d{6})-([a-z0-9_-]{1,24})\.zip$")


class ErrorHistorial(Exception):
    pass


def _carpeta(raiz: str) -> str:
    return os.path.join(raiz, HISTORIAL)


def _entra(relativo: str) -> bool:
    """Si ese archivo del proyecto va dentro de la copia."""
    partes = relativo.replace("\\", "/").split("/")
    if any(parte in EXCLUIDOS for parte in partes):
        return False
    if partes[0] in ARCHIVOS_FUERA:
        return False
    if relativo.lower().endswith(SUFIJOS_FUERA):
        return False
    return True


def archivos_del_proyecto(raiz: str) -> List[str]:
    """Las rutas relativas que forman el proyecto, ordenadas.

    Ordenadas a proposito: asi la huella de dos carpetas con lo mismo dentro
    sale igual aunque el sistema de archivos las liste en otro orden.
    """
    salida: List[str] = []
    for base, carpetas, nombres in os.walk(raiz):
        carpetas[:] = sorted(c for c in carpetas if c not in EXCLUIDOS)
        for nombre in sorted(nombres):
            completo = os.path.join(base, nombre)
            relativo = os.path.relpath(completo, raiz).replace(os.sep, "/")
            if _entra(relativo):
                salida.append(relativo)
    return sorted(salida)


def huella(raiz: str) -> str:
    """Un resumen del contenido del proyecto: si no cambia, no hay que copiar."""
    h = hashlib.sha256()
    for relativo in archivos_del_proyecto(raiz):
        h.update(relativo.encode("utf-8"))
        h.update(b"\0")
        with open(os.path.join(raiz, relativo), "rb") as fh:
            while True:
                trozo = fh.read(65536)
                if not trozo:
                    break
                h.update(trozo)
        h.update(b"\0")
    return h.hexdigest()


def _peso(raiz: str, rutas: List[str]) -> int:
    return sum(os.path.getsize(os.path.join(raiz, r)) for r in rutas)


def listar(raiz: str) -> List[Dict[str, object]]:
    """Las copias que hay, de la mas nueva a la mas vieja."""
    carpeta = _carpeta(raiz)
    if not os.path.isdir(carpeta):
        return []
    copias: List[Dict[str, object]] = []
    for nombre in os.listdir(carpeta):
        casa = NOMBRE.match(nombre)
        if not casa:
            continue
        ruta = os.path.join(carpeta, nombre)
        datos: Dict[str, object] = {
            "numero": int(casa.group(1)),
            "cuando": casa.group(2),
            "motivo": casa.group(3),
            "archivo": nombre,
            "bytes": os.path.getsize(ruta),
            "huella": "",
            "archivos": 0,
        }
        # la ficha que va dentro; si el zip esta roto se ensena igual, con lo
        # que se sepa por el nombre, para poder borrarlo
        try:
            with zipfile.ZipFile(ruta) as z:
                ficha = json.loads(z.read("neoplat.json").decode("utf-8"))
            datos["huella"] = str(ficha.get("huella", ""))
            datos["archivos"] = int(ficha.get("archivos", 0))
            datos["titulo"] = str(ficha.get("titulo", ""))
        except (OSError, KeyError, ValueError, zipfile.BadZipFile):
            datos["roto"] = True
        copias.append(datos)
    copias.sort(key=lambda c: c["numero"], reverse=True)
    return copias


def _siguiente_numero(copias: List[Dict[str, object]]) -> int:
    return (max((int(c["numero"]) for c in copias), default=0) + 1) % 10000


def _titulo_del_yaml(raiz: str) -> str:
    """El titulo del juego, leido a ojo del yaml: la ficha es informativa y no
    merece cargar el proyecto entero (que ademas puede no ser valido)."""
    for nombre in ("game.yaml", "juego.yaml", "game.yml", "juego.yml"):
        ruta = os.path.join(raiz, nombre)
        if not os.path.isfile(ruta):
            continue
        try:
            with open(ruta, encoding="utf-8") as fh:
                for linea in fh:
                    casa = re.match(r"\s*(?:titulo|title):\s*\"?([^\"\n#]*)", linea)
                    if casa:
                        return casa.group(1).strip()[:40]
        except OSError:
            return ""
        return ""
    return ""


def _podar(raiz: str, maximo: int) -> List[str]:
    """Deja solo las `maximo` copias mas nuevas. Devuelve las que ha borrado."""
    borradas = []
    for copia in listar(raiz)[maximo:]:
        ruta = os.path.join(_carpeta(raiz), str(copia["archivo"]))
        try:
            os.remove(ruta)
            borradas.append(str(copia["archivo"]))
        except OSError:
            pass
    return borradas


def copiar(raiz: str, motivo: str = "manual", maximo: int = MAX_COPIAS
           ) -> Optional[Dict[str, object]]:
    """Guarda una instantanea del proyecto. `None` si no habia nada que copiar.

    Devuelve `None` cuando el proyecto esta exactamente igual que en la ultima
    copia: repetirla solo gastaria disco y llenaria la lista de versiones
    identicas entre las que no se puede elegir.
    """
    raiz = os.path.abspath(raiz)
    if not os.path.isdir(raiz):
        raise ErrorHistorial("no existe la carpeta '%s'" % raiz)
    motivo = re.sub(r"[^a-z0-9_-]", "", motivo.lower())[:24] or "manual"

    rutas = archivos_del_proyecto(raiz)
    if not rutas:
        raise ErrorHistorial("la carpeta '%s' no tiene nada que guardar" % raiz)
    peso = _peso(raiz, rutas)
    if peso > MAX_BYTES:
        raise ErrorHistorial(
            "el proyecto ocupa %d MB y el limite de una copia son %d MB"
            % (peso // (1024 * 1024), MAX_BYTES // (1024 * 1024)))

    actual = huella(raiz)
    copias = listar(raiz)
    if copias and copias[0].get("huella") == actual:
        return None

    carpeta = _carpeta(raiz)
    os.makedirs(carpeta, exist_ok=True)
    numero = _siguiente_numero(copias)
    nombre = "%04d-%s-%s.zip" % (numero, time.strftime("%Y%m%d-%H%M%S"), motivo)
    destino = os.path.join(carpeta, nombre)
    ficha = {
        "version": 1,
        "huella": actual,
        "archivos": len(rutas),
        "bytes": peso,
        "cuando": time.strftime("%Y-%m-%d %H:%M:%S"),
        "motivo": motivo,
        "titulo": _titulo_del_yaml(raiz),
    }
    # se escribe a un temporal y se mueve al final: si algo se tuerce a medias
    # no queda un zip roto en el historial
    temporal = destino + ".parcial"
    try:
        with zipfile.ZipFile(temporal, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("neoplat.json", json.dumps(ficha, indent=2, sort_keys=True))
            for relativo in rutas:
                z.write(os.path.join(raiz, relativo), "proyecto/" + relativo)
        os.replace(temporal, destino)
    except OSError:
        if os.path.exists(temporal):
            try:
                os.remove(temporal)
            except OSError:
                pass
        raise
    _podar(raiz, maximo)
    ficha["archivo"] = nombre
    ficha["numero"] = numero
    return ficha


def _copia_por_numero(raiz: str, numero: int) -> Dict[str, object]:
    for copia in listar(raiz):
        if int(copia["numero"]) == numero:
            return copia
    raise ErrorHistorial("no hay ninguna copia con el numero %d" % numero)


def contenido(raiz: str, numero: int) -> Dict[str, bytes]:
    """Lo que hay dentro de una copia, sin tocar el proyecto."""
    copia = _copia_por_numero(raiz, numero)
    ruta = os.path.join(_carpeta(raiz), str(copia["archivo"]))
    salida: Dict[str, bytes] = {}
    with zipfile.ZipFile(ruta) as z:
        for miembro in z.namelist():
            if not miembro.startswith("proyecto/") or miembro.endswith("/"):
                continue
            relativo = miembro[len("proyecto/"):]
            if not _entra(relativo) or os.path.isabs(relativo) or ".." in relativo.split("/"):
                continue
            salida[relativo] = z.read(miembro)
    if not salida:
        raise ErrorHistorial("la copia %04d esta vacia o rota" % numero)
    return salida


def recuperar(raiz: str, numero: int) -> Tuple[List[str], List[str]]:
    """Devuelve el proyecto a como estaba en esa copia.

    Antes guarda como esta ahora, para que equivocarse de version tampoco
    pierda nada. Devuelve (archivos escritos, archivos que sobraban y se han
    quitado).
    """
    raiz = os.path.abspath(raiz)
    dentro = contenido(raiz, numero)          # antes de tocar nada: si falla, falla aqui
    copiar(raiz, "antes-de-recuperar")

    escritos: List[str] = []
    for relativo, crudo in sorted(dentro.items()):
        destino = os.path.join(raiz, relativo.replace("/", os.sep))
        carpeta = os.path.dirname(destino)
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)
        with open(destino, "wb") as fh:
            fh.write(crudo)
        escritos.append(relativo)

    # lo que hay ahora y no estaba en la copia: se quita, o el proyecto seria
    # una mezcla de las dos versiones
    sobrantes: List[str] = []
    for relativo in archivos_del_proyecto(raiz):
        if relativo in dentro:
            continue
        try:
            os.remove(os.path.join(raiz, relativo.replace("/", os.sep)))
            sobrantes.append(relativo)
        except OSError:
            pass
    return escritos, sobrantes


def borrar_todo(raiz: str) -> int:
    """Se lleva el historial entero. Devuelve cuantas copias habia."""
    copias = listar(raiz)
    carpeta = _carpeta(raiz)
    if os.path.isdir(carpeta):
        shutil.rmtree(carpeta, ignore_errors=True)
    return len(copias)
