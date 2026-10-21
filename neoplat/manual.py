#!/usr/bin/env python3
"""Encuaderna el manual: los Markdown del kit en un PDF, uno por idioma.

    python3 manual.py                 los dos: castellano e ingles
    python3 manual.py --idioma es     solo el castellano
    python3 manual.py --dist X        los deja en X en vez de en dist/

Sale en `dist/`, con el idioma en el nombre:

    neoplat-manual-es.pdf     el original, de docs/
    neoplat-manual-en.pdf     la traduccion, de docs/en/

Hace falta **WeasyPrint** (`pip3 install weasyprint`), que es quien pagina y
escribe el PDF; lo demas -juntar los documentos, convertir el Markdown, el
indice con los numeros de pagina- es del kit, en tools/ngplat/manual.py.
"""

from __future__ import annotations

import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(RAIZ, "tools"))

from ngplat import __version__ as VERSION          # noqa: E402
from ngplat.manual import IDIOMAS, ManualError, generar, motor   # noqa: E402


def main(argv: list) -> int:
    destino = os.path.join(RAIZ, "dist")
    idiomas = list(IDIOMAS)
    for i, arg in enumerate(argv):
        if arg == "--dist" and i + 1 < len(argv):
            destino = argv[i + 1]
        elif arg == "--idioma" and i + 1 < len(argv):
            idiomas = [argv[i + 1]]
    if not motor():
        print("falta WeasyPrint, que es quien pagina el PDF:\n"
              "    pip3 install weasyprint", file=sys.stderr)
        return 1
    for idioma in idiomas:
        salida = os.path.join(destino, "neoplat-manual-%s.pdf" % idioma)
        try:
            generar(RAIZ, idioma, VERSION, salida)
        except ManualError as error:
            print("manual (%s): %s" % (idioma, error), file=sys.stderr)
            if error.pista:
                print("  %s" % error.pista, file=sys.stderr)
            return 1
        print("%s  (%d KB)" % (os.path.relpath(salida, RAIZ),
                               os.path.getsize(salida) // 1024))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
