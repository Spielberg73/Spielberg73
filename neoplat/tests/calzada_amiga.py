"""Arranca un disquete de carretera del Amiga y dice por donde pasa la calzada.

Va en un programa aparte, y no es mania: **PUAE no se deja arrancar dos veces
en el mismo proceso** (esta contado en _comprobar_amiga, en test_sistemas.py), y
la prueba que lo usa necesita arrancar dos, un A500 y un A1200, para comparar.

    python3 tests/calzada_amiga.py juego.adf A500 1 "#4a4a52,#42424a"

Saca por la salida estandar un JSON con, para unas cuantas lineas de pantalla,
donde empieza y donde acaba el asfalto. Se arranca y **no se acelera**: asi las
dos maquinas se quedan en el mismo sitio del circuito y son comparables.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from libretro import Emulador, buscar_core  # noqa: E402

SEGUNDOS_DE_ARRANQUE = 45
FPS = 50
LINEAS = (120, 150, 180, 200, 240)
# Cada maquina redondea el color a lo suyo -el OCS guarda cuatro bits por canal
# y el AGA ocho-, asi que se compara con holgura.
HOLGURA = 24


def donde_esta_la_calzada(pantalla, tonos):
    ancho, alto, pixeles = pantalla
    salida = {}
    for y in LINEAS:
        if y >= alto:
            continue
        base = y * ancho
        xs = []
        for x in range(ancho):
            r, g, b = pixeles[base + x][:3]
            for cr, cg, cb in tonos:
                if (abs(r - cr) <= HOLGURA and abs(g - cg) <= HOLGURA
                        and abs(b - cb) <= HOLGURA):
                    xs.append(x)
                    break
        salida[str(y)] = [min(xs), max(xs)] if xs else None
    return salida


def main():
    adf, modelo, chip, tonos_txt = sys.argv[1:5]
    tonos = []
    for trozo in tonos_txt.split(","):
        t = trozo.strip().lstrip("#")
        tonos.append((int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16)))
    core = buscar_core("puae", "NEOPLAT_CORE_AMIGA")
    if not core:
        print(json.dumps({"saltar": "no esta el core de PUAE"}))
        return 0
    emu = Emulador(core, sistema=tempfile.mkdtemp(prefix="neoplat-calzada-"),
                   opciones={"puae_kickstart": "aros", "puae_model": modelo,
                             "puae_video_standard": "PAL",
                             "puae_chipmem_size": chip})
    emu.cargar(adf)
    while emu.frames < SEGUNDOS_DE_ARRANQUE * FPS:
        emu.avanzar(100)
    emu.pulsar("A")                   # empezar la partida
    emu.avanzar(6)
    emu.pulsar()                      # y soltar: sin acelerar, quieto en la salida
    emu.avanzar(120)
    print(json.dumps(donde_esta_la_calzada(emu.frame, tonos)))
    emu.cerrar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
