"""Rutas dentro del kit (el motor C, las plantillas y el preview).

El kit se usa de dos maneras y las rutas no son las mismas:

  - **desde el repositorio**, con `./ngplat`: todo cuelga de la carpeta del
    proyecto, tres niveles por encima de este archivo;
  - **desde el ejecutable de Windows** (`ngplat.exe`, que arma
    `empaquetar.py`): PyInstaller mete el motor, el preview y las plantillas
    dentro del propio .exe y al arrancar los deja en una carpeta temporal cuyo
    nombre esta en `sys._MEIPASS`.

Todo lo que abre archivos del kit pasa por aqui, asi que con distinguir los dos
casos en este sitio basta.
"""

from __future__ import annotations

import os
import sys

CONGELADO = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")

if CONGELADO:
    KIT_ROOT = sys._MEIPASS
    TEMPLATES_DIR = os.path.join(KIT_ROOT, "ngplat", "templates")
else:
    KIT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

ENGINE_DIR = os.path.join(KIT_ROOT, "engine")
PREVIEW_DIR = os.path.join(KIT_ROOT, "preview")


# Modulos del kit que se copian **tal cual** dentro del proyecto generado, para
# que su `make` se valga solo sin tener NeoPlat instalado (el Amiga y el Atari
# ST arman su ejecutable y su disquete con ellos). En el .exe van dentro como
# datos, porque de un modulo congelado ya no se puede leer el fuente.
FUENTES_COPIADAS = ("hunk.py", "adf.py", "prg.py", "st_disk.py")


def fuente_del_kit(modulo: str) -> str:
    """El texto de uno de esos modulos."""
    if modulo not in FUENTES_COPIADAS:
        raise ValueError("%r no esta en FUENTES_COPIADAS" % modulo)
    if CONGELADO:
        ruta = os.path.join(KIT_ROOT, "ngplat", modulo)
    else:
        ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), modulo)
    with open(ruta, "r", encoding="utf-8") as fh:
        return fh.read()
