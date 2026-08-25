"""Arranca el disquete de Amiga en un emulador de verdad (opcional).

Mete el .adf en un A500 emulado (PUAE, con la ROM libre de AROS) y mira lo que
sale por pantalla: si el disquete no arranca, si el juego no se dibuja o si se
cuelga, aqui se ve. Es la unica prueba que ejercita el disco entero, del
bootblock al ultimo bitplane.

El core no viene en los repositorios; se saca del buildbot de libretro:

    https://buildbot.libretro.com/nightly/linux/x86_64/latest/puae_libretro.so.zip

y se deja en /usr/local/lib/libretro/ (o se apunta con NEOPLAT_CORE_AMIGA).
Si no esta, la prueba se salta.

    python3 tests/emulador_amiga.py ruta/al/juego.adf [carpeta_de_capturas]
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from libretro import (Emulador, buscar_core, colores, distintos,  # noqa: E402
                      franja, guardar_png)

CORE = "puae"
# arrancar un Amiga lleva su tiempo: AROS tarda unos 50 segundos emulados
SEGUNDOS_DE_ARRANQUE = 70
FPS = 50


def comprobar(adf: str, capturas: str = "capturas") -> int:
    core = buscar_core(CORE, "NEOPLAT_CORE_AMIGA")
    if not core:
        print("el core de PUAE no esta instalado: se salta la prueba")
        return 0
    os.makedirs(capturas, exist_ok=True)
    fallos = []

    def exigir(condicion, mensaje):
        if not condicion:
            fallos.append(mensaje)

    sistema = tempfile.mkdtemp(prefix="neoplat-amiga-")
    emu = Emulador(core, sistema=sistema, opciones={
        "puae_kickstart": "aros",       # la ROM libre que trae el propio core
        "puae_model": "A500",           # OCS, 68000, 512 KB de RAM chip
        "puae_video_standard": "PAL",
    })
    emu.cargar(adf)

    # --- 1) el disquete arranca solo y sale el juego ---------------------
    while emu.frames < SEGUNDOS_DE_ARRANQUE * FPS:
        emu.avanzar(100)
    titulo = emu.frame
    exigir(titulo is not None, "el emulador no ha dibujado ningun frame")
    guardar_png(titulo, os.path.join(capturas, "amiga_titulo.png"))
    cuantos = len(colores(titulo))
    # si el disquete no arrancase se veria el escritorio de AROS, que es gris;
    # el juego tiene su fondo de color y su marcador
    exigir(cuantos > 6,
           "a los %d segundos solo hay %d colores: el disquete no ha arrancado"
           % (SEGUNDOS_DE_ARRANQUE, cuantos))
    exigir(len(set(franja(titulo, 24))) > 2, "no se ve el marcador arriba")
    print("titulo: %dx%d con %d colores" % (titulo[0], titulo[1], cuantos))

    # --- 2) empieza la partida (start = segundo boton del joystick) ------
    emu.pulsar("A")
    emu.avanzar(20)
    emu.pulsar()
    emu.avanzar(60)
    juego = emu.frame
    guardar_png(juego, os.path.join(capturas, "amiga_juego.png"))
    exigir(distintos(titulo, juego) > 0.001, "la pantalla no cambia al pulsar start")

    # --- 3) se juega ----------------------------------------------------
    movimiento = 0.0
    antes = juego
    for tramo in range(6):
        for i in range(60):
            emu.pulsar("RIGHT", "B") if i % 30 == 0 else emu.pulsar("RIGHT")
            emu.avanzar(1)
        ahora = emu.frame
        movimiento = max(movimiento, distintos(antes, ahora))
        antes = ahora
        if tramo == 3:
            guardar_png(ahora, os.path.join(capturas, "amiga_jugando.png"))
    exigir(movimiento > 0.01,
           "la pantalla apenas cambia al jugar (%.2f%%): no se mueve nada"
           % (movimiento * 100))
    print("jugando: hasta un %.0f%% de la pantalla cambia entre tramos"
          % (movimiento * 100))

    # --- 4) sigue vivo --------------------------------------------------
    ultimo = emu.frame
    emu.pulsar("RIGHT")
    emu.avanzar(100)
    exigir(distintos(ultimo, emu.frame) > 0.0,
           "la imagen se ha quedado congelada: el juego se ha colgado")
    guardar_png(emu.frame, os.path.join(capturas, "amiga_final.png"))
    emu.cerrar()

    for fallo in fallos:
        print("FALLO:", fallo)
    if fallos:
        return 1
    print("el disquete arranca y se juega en el emulador; capturas en %s/" % capturas)
    return 0


if __name__ == "__main__":
    disco = (sys.argv[1] if len(sys.argv) > 1
             else "examples/bosque-magico/build/amiga/disco/BosqueMagico.adf")
    sys.exit(comprobar(disco, sys.argv[2] if len(sys.argv) > 2 else "capturas"))
