#!/usr/bin/env python3
"""Empaqueta NeoPlat para repartirlo: los ZIP y el ejecutable de Windows.

    python3 empaquetar.py            los tres ZIP
    python3 empaquetar.py --exe      ademas, el ngplat.exe (necesita PyInstaller)
    python3 empaquetar.py --dist X   los deja en X en vez de en dist/

Sale todo en `dist/`, con la version en el nombre (ngplat/__init__.py):

    neoplat-docs-1.2.zip      solo la documentacion (para llevarsela a otro sitio)
    neoplat-kit-1.2.zip       el kit entero: motor, herramientas, ejemplo y pruebas
    neoplat-windows-1.5.zip   el ngplat.exe con su LEEME, si se ha construido

Los ZIP se arman a mano con `zipfile` y no llamando a `zip`, para que esto
funcione igual en Windows, en Linux y en un mac sin instalar nada. Y las fechas
van fijas: asi dos ZIP del mismo codigo salen byte a byte iguales y se pueden
comparar.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile

RAIZ = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(RAIZ, "dist")
FECHA = (2025, 1, 1, 0, 0, 0)          # para que el ZIP sea repetible

# Lo que nunca va en un paquete: lo generado, lo temporal y el historial.
FUERA = {".git", "__pycache__", "build", "dist", "capturas", ".pytest_cache",
         ".neoplat"}          # las copias locales del historial no se reparten
FUERA_EXT = {".pyc", ".pyo", ".adf", ".st", ".j64", ".bin", ".elf", ".o"}

DOCS = ["README.md", "CAMBIOS.md", "docs", "LICENSE"]
KIT = ["README.md", "CAMBIOS.md", "docs", "engine", "preview", "tools", "tests",
       "examples", "ngplat", "Makefile", "empaquetar.py", "LICENSE"]

sys.path.insert(0, os.path.join(RAIZ, "tools"))
from ngplat import __version__ as VERSION  # noqa: E402


def _interesa(ruta: str) -> bool:
    partes = ruta.replace("\\", "/").split("/")
    if any(p in FUERA for p in partes):
        return False
    return os.path.splitext(ruta)[1] not in FUERA_EXT


def _recorrer(relativo: str):
    """Todos los archivos de un archivo o carpeta del kit, ya filtrados."""
    entero = os.path.join(RAIZ, relativo)
    if os.path.isfile(entero):
        if _interesa(relativo):
            yield relativo
        return
    for carpeta, subcarpetas, archivos in os.walk(entero):
        subcarpetas[:] = sorted(s for s in subcarpetas if s not in FUERA)
        for nombre in sorted(archivos):
            ruta = os.path.relpath(os.path.join(carpeta, nombre), RAIZ)
            if _interesa(ruta):
                yield ruta


def hacer_zip(destino: str, entradas, prefijo: str) -> str:
    """Mete en un ZIP esas carpetas del kit, bajo una carpeta con nombre."""
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    cuantos = 0
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for entrada in entradas:
            if not os.path.exists(os.path.join(RAIZ, entrada)):
                continue
            for ruta in _recorrer(entrada):
                info = zipfile.ZipInfo(prefijo + "/" + ruta.replace("\\", "/"), FECHA)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                if ruta == "ngplat" or ruta.endswith(".py"):
                    info.external_attr = 0o755 << 16
                with open(os.path.join(RAIZ, ruta), "rb") as fh:
                    zf.writestr(info, fh.read())
                cuantos += 1
    print("%s  (%d archivos, %d KB)"
          % (os.path.relpath(destino, RAIZ), cuantos,
             os.path.getsize(destino) // 1024))
    return destino


# --- el ejecutable de Windows -------------------------------------------
#
# PyInstaller mete el interprete, el codigo y los datos en un solo .exe. Los
# datos son el motor en C, el preview y las plantillas: sin ellos `ngplat
# compilar` no tendria que copiar. Dentro del .exe quedan donde los busca
# tools/ngplat/paths.py cuando esta congelado.

DATOS = [
    ("engine", "engine"),
    ("preview", "preview"),
    ("tools/ngplat/templates", "ngplat/templates"),
]

# Y los modulos que el proyecto generado se lleva dentro (el Amiga y el Atari
# ST arman su ejecutable y su disquete con ellos): de un modulo congelado no se
# puede leer el fuente, asi que van como datos.
from ngplat.paths import FUENTES_COPIADAS  # noqa: E402

DATOS += [("tools/ngplat/" + nombre, "ngplat") for nombre in FUENTES_COPIADAS]


def opciones_pyinstaller(para_windows: bool):
    """Todo en rutas **relativas** a la raiz del kit.

    Es a proposito: asi la misma orden vale ejecutando PyInstaller en Windows
    y ejecutandolo bajo Wine desde Linux, donde una ruta absoluta de Unix no
    significaria nada para el Python de Windows."""
    separador = ";" if para_windows else ":"
    orden = [
        "--onefile", "--console", "--name", "ngplat",
        "--distpath", "dist/windows" if para_windows else "dist/linux",
        "--workpath", "dist/trabajo",
        # el .spec se queda en la raiz porque PyInstaller resuelve los
        # `--add-data` **desde donde este el .spec**, no desde el directorio de
        # trabajo; se borra al acabar
        "--specpath", ".",
        "--paths", "tools",
        "--noconfirm", "--clean", "--log-level", "WARN",
    ]
    for origen, dentro in DATOS:
        orden += ["--add-data", origen + separador + dentro]
    orden.append("ngplat")
    return orden


def hacer_exe(python=None) -> str:
    """Llama a PyInstaller.

    `python` puede ser una orden entera, con espacios, para usar otro
    interprete: `--python "wine /ruta/python.exe"` construye el .exe de
    Windows desde Linux. Sin eso sale el binario de la maquina en la que se
    ejecute esto."""
    lanzador = python.split() if python else [sys.executable]
    para_windows = os.name == "nt" or bool(python)
    orden = lanzador + ["-m", "PyInstaller"] + opciones_pyinstaller(para_windows)
    print("$ " + " ".join(orden))
    hecho = subprocess.run(orden, cwd=RAIZ)
    spec = os.path.join(RAIZ, "ngplat.spec")
    if os.path.exists(spec):
        os.remove(spec)
    if hecho.returncode != 0:
        raise SystemExit("PyInstaller ha fallado")
    salida = os.path.join(DIST, "windows" if para_windows else "linux")
    for nombre in ("ngplat.exe", "ngplat"):
        ruta = os.path.join(salida, nombre)
        if os.path.exists(ruta):
            print("%s  (%d KB)" % (os.path.relpath(ruta, RAIZ),
                                   os.path.getsize(ruta) // 1024))
            return ruta
    raise SystemExit("PyInstaller no ha dejado el ejecutable donde se esperaba")


LEEME = """NeoPlat para Windows
====================

Este es el kit entero dentro de un solo archivo: no hace falta instalar Python
ni nada mas.

Con doble clic en ngplat.exe se abre una ventana que pregunta que quieres
hacer: crear un juego nuevo, abrir el editor de uno que ya exista o compilarlo
para su maquina. La ventana no se cierra hasta que pulses Enter.

Si prefieres escribir las ordenes tu, abre una ventana de simbolo del sistema
en esta carpeta y prueba:

    ngplat.exe nuevo mijuego
    ngplat.exe probar mijuego
    ngplat.exe compilar mijuego --sistema megadrive

`nuevo` crea un juego jugable con sus graficos y sus sonidos; `probar` lo abre
en el navegador con el editor incluido; `compilar` genera el proyecto en C y
las ROMs graficas.

Para construir de verdad el cartucho o el disquete hace falta ademas un
compilador de 68000 (m68k-elf-gcc). Sin el, `compilar` deja el proyecto en C
listo y te dice que orden ejecutar.

La documentacion completa va en el ZIP de docs, y el codigo fuente en el del
kit.
"""


def main(argv):
    # A donde van los paquetes. Se puede cambiar (--dist) para no pisar dist/:
    # lo usan las pruebas, que si no borrarian los paquetes ya construidos.
    destino = DIST
    for i, arg in enumerate(argv):
        if arg == "--dist" and i + 1 < len(argv):
            destino = os.path.abspath(argv[i + 1])
    if os.path.isdir(destino):
        shutil.rmtree(destino)
    hacer_zip(os.path.join(destino, "neoplat-docs-%s.zip" % VERSION), DOCS,
              "neoplat-docs-%s" % VERSION)
    hacer_zip(os.path.join(destino, "neoplat-kit-%s.zip" % VERSION), KIT,
              "neoplat-%s" % VERSION)

    if "--exe" in argv:
        python = None
        for i, arg in enumerate(argv):
            if arg == "--python" and i + 1 < len(argv):
                python = argv[i + 1]
        exe = hacer_exe(python)
        carpeta = os.path.dirname(exe)
        with open(os.path.join(carpeta, "LEEME.txt"), "w", encoding="utf-8") as fh:
            fh.write(LEEME)
        paquete = os.path.join(destino, "neoplat-windows-%s.zip" % VERSION)
        with zipfile.ZipFile(paquete, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for nombre in sorted(os.listdir(carpeta)):
                info = zipfile.ZipInfo(nombre, FECHA)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o755 if nombre.endswith(".exe") else 0o644) << 16
                with open(os.path.join(carpeta, nombre), "rb") as fh:
                    zf.writestr(info, fh.read())
        print("%s  (%d KB)" % (os.path.relpath(paquete, RAIZ),
                               os.path.getsize(paquete) // 1024))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
