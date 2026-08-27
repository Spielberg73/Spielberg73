"""Comprueba en un emulador de verdad que las muestras digitales suenan.

Cuatro de las cinco maquinas saben tocar sonido grabado (todas menos el Atari
ST, que solo tiene ondas cuadradas), cada una con un chip distinto. Que el
compilador meta los bytes en la ROM no quiere decir que se oigan: puede fallar
el puntero, la frecuencia, el DMA o el canal. Asi que aqui se **escucha**.

El proyecto de prueba (comun.proyecto_con_muestra) pone como efecto de salto un
tono puro a 3000 Hz **sin notas de recambio**. Entonces:

  1. se juega un rato sin saltar y se mide cuanta energia hay en 3000 Hz
     (la que meta la musica, que no llega ahi);
  2. se salta y se vuelve a medir.

Si la muestra suena, el segundo numero es mucho mayor. Si la maquina se saltara
las muestras, al no haber notas de recambio no sonaria nada y los dos numeros
serian el mismo.

    python3 tests/muestras.py amiga ruta/al/juego.adf
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import MUESTRA_HZ  # noqa: E402
from maquinas import montar  # noqa: E402
from sonido import pico_por_frame  # noqa: E402

ANCHO = 120           # +-120 Hz alrededor del tono: la muestra no es perfecta
FRAMES = 30           # un efecto dura unos pocos frames; se mira el mayor
VECES = 4.0           # cuanto tiene que destacar sobre el fondo


def comprobar(emu, empezar, saltar, esperar=None, arranque=200, fps=60):
    """Devuelve la lista de fallos (vacia si todo bien)."""
    if esperar is None:
        def esperar(emu):
            emu.avanzar(arranque)
    fallos = []
    esperar(emu)
    emu.pulsar(empezar)
    emu.avanzar(10)
    emu.pulsar()
    emu.avanzar(60)

    banda = (MUESTRA_HZ - ANCHO, MUESTRA_HZ + ANCHO)
    quieto = pico_por_frame(emu.escuchar, FRAMES, emu.ritmo, *banda)
    emu.pulsar(saltar)
    emu.avanzar(2)
    emu.pulsar()
    saltando = pico_por_frame(emu.escuchar, FRAMES, emu.ritmo, *banda)

    veces = saltando / max(1e-6, quieto)
    print("muestra: al saltar, %d Hz suena %.1f veces mas que estando quieto"
          % (MUESTRA_HZ, veces))
    if veces < VECES:
        fallos.append(
            "al saltar no se oye la muestra: en %d Hz suena %.1f veces mas que "
            "estando quieto y deberia notarse mucho mas (%.0f y %.0f)"
            % (MUESTRA_HZ, veces, quieto, saltando))
    return fallos


# El boton de saltar de cada mando, tal y como lo mapea su emulador (el mismo
# que usan las pruebas de sonido de cada maquina).
SALTAR = {"neogeo": "A", "megadrive": "B", "amiga": "B", "jaguar": "A"}


def comprobar_maquina(sistema, ruta) -> int:
    """Monta el emulador de esa maquina y escucha. 0 = todo bien."""
    if sistema not in SALTAR:
        print("%s no toca muestras digitales: no hay nada que escuchar" % sistema)
        return 0
    emu, empezar, esperar = montar(sistema, ruta)
    if emu is None:
        print("falta el emulador de %s: se salta la prueba" % sistema)
        return 0
    fallos = comprobar(emu, empezar, SALTAR[sistema], esperar=esperar)
    for fallo in fallos:
        print("  FALLO", fallo)
    return 1 if fallos else 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(1)
    raise SystemExit(comprobar_maquina(sys.argv[1], sys.argv[2]))
