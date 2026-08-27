"""Comprueba en un emulador de verdad que el segundo mando mueve al segundo
jugador, y que no es el mismo mando leido dos veces.

Con `jugadores: 2` los dos empiezan casi en el mismo sitio y con el mismo
dibujo, asi que una captura sola no dice gran cosa: si el segundo mando no
estuviera conectado, o si las dos lecturas dieran en el mismo puerto, la
pantalla saldria muy parecida. Lo que se hace es jugar **tres veces la misma
partida** (dandole al reset entre una y otra) y comparar como acaban:

    A  corriendo a la derecha con el mando 1
    B  corriendo a la derecha con el mando 2
    C  corriendo a la derecha con los dos

Con uno solo el que corre se queda pegado al borde de la pantalla, porque el
otro no se mueve y la vista tiene que seguir ensenando a los dos; con los dos
la pantalla avanza de verdad. Asi que A y C **tienen que salir distintas**, y
lo mismo B y C. Si el segundo mando no llegara al juego, las tres partidas
serian la misma y las dos comparaciones fallarian; si los dos mandos leyeran
del mismo sitio, A y C saldrian iguales.

Sirve para las cinco maquinas:

    python3 tests/dos_jugadores.py atarist ruta/al/disco.st [carpeta_de_capturas]
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from libretro import distintos, guardar_png  # noqa: E402
from maquinas import montar  # noqa: E402

# lo poco que cambia entre partida y partida se cuela por el ruido de un par de
# pixeles (el marcador parpadeando, una animacion a destiempo)
MINIMO = 0.004


def _partida(emu, empezar, botones, frames, esperar):
    emu.reiniciar()
    esperar(emu)
    emu.pulsar(empezar)
    emu.avanzar(10)
    emu.pulsar()
    emu.avanzar(30)
    for puerto, teclas in botones.items():
        emu.pulsar(*teclas, puerto=puerto)
    emu.avanzar(frames)
    emu.pulsar()
    emu.pulsar(puerto=1)
    emu.avanzar(20)
    return emu.frame


def comprobar(emu, empezar, capturas=None, prefijo="2p",
              frames=90, arranque=200, esperar=None):
    """Devuelve la lista de fallos (vacia si todo bien).

    `esperar` es lo que hay que hacer para llegar a la pantalla de titulo desde
    la maquina recien encendida; por defecto, avanzar `arranque` frames, que es
    lo que basta en un cartucho. Los disquetes tardan lo que tarde el sistema
    en arrancar y traen el suyo."""
    if esperar is None:
        def esperar(emu):
            emu.avanzar(arranque)
    fallos = []
    partidas = {
        "mando1": {0: ("RIGHT",)},
        "mando2": {1: ("RIGHT",)},
        "los-dos": {0: ("RIGHT",), 1: ("RIGHT",)},
    }
    imagenes = {}
    for nombre, botones in partidas.items():
        imagenes[nombre] = _partida(emu, empezar, botones, frames, esperar)
        if capturas:
            os.makedirs(capturas, exist_ok=True)
            guardar_png(imagenes[nombre],
                        os.path.join(capturas, "%s_%s.png" % (prefijo, nombre)))

    for solo in ("mando1", "mando2"):
        cambio = distintos(imagenes[solo], imagenes["los-dos"])
        print("dos jugadores: con %s se ve un %.2f%% distinto que con los dos"
              % (solo, cambio * 100))
        if cambio <= MINIMO:
            fallos.append(
                "moviendo solo con %s la pantalla acaba igual que moviendo con "
                "los dos (%.3f%% de diferencia): ese mando no llega a su "
                "jugador" % (solo, cambio * 100))
    return fallos


def comprobar_maquina(sistema, ruta, capturas="capturas") -> int:
    """Monta el emulador de esa maquina y hace la prueba. 0 = todo bien."""
    emu, empezar, esperar = montar(sistema, ruta)
    if emu is None:
        print("falta el emulador de %s: se salta la prueba" % sistema)
        return 0
    fallos = comprobar(emu, empezar, capturas=capturas,
                       prefijo=sistema + "_2p", esperar=esperar)
    for fallo in fallos:
        print("  FALLO", fallo)
    return 1 if fallos else 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(1)
    raise SystemExit(comprobar_maquina(
        sys.argv[1], sys.argv[2],
        sys.argv[3] if len(sys.argv) > 3 else "capturas"))
