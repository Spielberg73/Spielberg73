"""Arranca el cartucho de Atari Jaguar en un emulador de verdad (opcional).

Mete la .j64 en Virtual Jaguar y mira lo que sale por pantalla. El core no
necesita la BIOS de Atari para los cartuchos (viene desactivada por defecto),
asi que esta maquina se puede comprobar igual que la Mega Drive y el Amiga.

El core no viene en los repositorios; se saca del buildbot de libretro:

    https://buildbot.libretro.com/nightly/linux/x86_64/latest/virtualjaguar_libretro.so.zip

y se deja en /usr/local/lib/libretro/ (o se apunta con NEOPLAT_CORE_JAGUAR).
Si no esta, la prueba se salta.

    python3 tests/emulador_jaguar.py ruta/al/juego.j64 [carpeta_de_capturas]
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from libretro import (Emulador, buscar_core, colores, distintos,  # noqa: E402
                      franja, guardar_png)

CORE = "virtualjaguar"
# El boton START del mando de RetroPad es el OPTION de la Jaguar; el que usa el
# kit para empezar la partida es PAUSE, que el core pone en SELECT.
EMPEZAR = "SELECT"


def comprobar(rom: str, capturas: str = "capturas") -> int:
    core = buscar_core(CORE, "NEOPLAT_CORE_JAGUAR")
    if not core:
        print("el core de Virtual Jaguar no esta instalado: se salta la prueba")
        return 0
    os.makedirs(capturas, exist_ok=True)
    fallos = []

    def exigir(condicion, mensaje):
        if not condicion:
            fallos.append(mensaje)

    emu = Emulador(core, sistema=tempfile.mkdtemp(prefix="neoplat-jaguar-"))
    emu.cargar(rom)

    # --- 1) arranca y pinta la pantalla de titulo ------------------------
    emu.avanzar(200)
    titulo = emu.frame
    exigir(titulo is not None, "el emulador no ha dibujado ningun frame")
    guardar_png(titulo, os.path.join(capturas, "jag_titulo.png"))
    tonos = colores(titulo)
    exigir(len(tonos) > 6,
           "la pantalla de titulo solo tiene %d colores: no esta dibujando"
           % len(tonos))
    print("titulo: %dx%d con %d colores" % (titulo[0], titulo[1], len(tonos)))
    exigir(len(set(franja(titulo, 32))) > 2, "no se ve el marcador arriba")

    # --- 2) empieza la partida ------------------------------------------
    emu.pulsar(EMPEZAR)
    emu.avanzar(10)
    emu.pulsar()
    emu.avanzar(60)
    juego = emu.frame
    guardar_png(juego, os.path.join(capturas, "jag_juego.png"))
    exigir(distintos(titulo, juego) > 0.002, "la pantalla no cambia al empezar")

    # --- 3) se juega: correr a la derecha y saltar -----------------------
    movimiento = 0.0
    antes = juego
    for tramo in range(5):
        for i in range(50):
            emu.pulsar("RIGHT", "A") if i % 25 == 0 else emu.pulsar("RIGHT")
            emu.avanzar(1)
        ahora = emu.frame
        movimiento = max(movimiento, distintos(antes, ahora))
        antes = ahora
        if tramo == 2:
            guardar_png(ahora, os.path.join(capturas, "jag_jugando.png"))
    exigir(movimiento > 0.02,
           "la pantalla apenas cambia al jugar (%.1f%%): el scroll no se mueve"
           % (movimiento * 100))
    print("jugando: hasta un %.0f%% de la pantalla cambia entre tramos"
          % (movimiento * 100))

    # --- 4) el marcador se ve una vez, no dos ---------------------------
    #
    # El chip compone la lista de objetos mientras el haz recorre la pantalla:
    # si la lista se reescribe a medias, el objeto se vuelve a pintar desde
    # arriba a partir de ahi y el marcador sale dos veces.
    ancho, alto, pixeles = emu.frame
    claro = max(colores(emu.frame), key=lambda p: sum(p))     # el blanco del marcador
    filas_texto = 0
    for y in range(alto):
        cuantos = sum(1 for x in range(ancho) if pixeles[y * ancho + x] == claro)
        if cuantos >= 20:
            filas_texto += 1
    exigir(filas_texto >= 3, "no se ve el texto del marcador")
    exigir(filas_texto <= 8,
           "el marcador sale repetido (%d filas de texto, deberian ser unas 5): "
           "la lista de objetos se esta reescribiendo con el haz en mitad de la "
           "pantalla" % filas_texto)
    print("marcador: %d filas de texto" % filas_texto)

    # --- 5) sigue vivo al final -----------------------------------------
    ultimo = emu.frame
    emu.pulsar("RIGHT")
    emu.avanzar(60)
    exigir(distintos(ultimo, emu.frame) > 0.0,
           "la imagen se ha quedado congelada: el juego se ha colgado")
    guardar_png(emu.frame, os.path.join(capturas, "jag_final.png"))

    print("frames dibujados: %d" % emu.frames)
    emu.cerrar()

    for fallo in fallos:
        print("FALLO:", fallo)
    if fallos:
        return 1
    print("el cartucho arranca, dibuja y se juega en el emulador; capturas en %s/"
          % capturas)
    return 0


if __name__ == "__main__":
    rom = (sys.argv[1] if len(sys.argv) > 1
           else "examples/bosque-magico/build/jaguar/rom/BosqueMagico.j64")
    sys.exit(comprobar(rom, sys.argv[2] if len(sys.argv) > 2 else "capturas"))
