"""Arranca la ROM de Neo Geo en el banco de pruebas y mira lo que sale.

La Neo Geo no se puede probar en un emulador normal sin la BIOS de SNK, que es
de SNK y no se distribuye. Asi que el banco lo pone el kit: el 68000 de verdad
(Musashi, via `machine68k`) y el chip de video escrito a mano en
`tests/maquina_neogeo.py`. El juego que se ejecuta es el que genera
`ngplat compilar`, sin tocar una linea.

    pip3 install amitools        # trae machine68k
    apt-get install gcc-m68k-linux-gnu
    python3 tests/emulador_neogeo.py examples/bosque-magico/build/neogeo [capturas]
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import maquina_neogeo as ng  # noqa: E402
from imagen import colores, distintos, franja, guardar_png  # noqa: E402


def comprobar(carpeta, capturas="capturas"):
    try:
        import machine68k  # noqa: F401
    except ImportError:
        print("falta machine68k (pip3 install amitools): se salta la prueba")
        return 0
    if not ng.compilador():
        print("no hay compilador de 68000 en el PATH: se salta la prueba")
        return 0

    os.makedirs(capturas, exist_ok=True)
    fallos = []

    def exigir(condicion, mensaje):
        if not condicion:
            fallos.append(mensaje)

    maquina = ng.cargar(carpeta)

    # --- 1) arranca y pinta la pantalla de titulo ------------------------
    maquina.avanzar(10)
    titulo = maquina.dibujar()
    guardar_png(titulo, os.path.join(capturas, "ng_titulo.png"))
    tonos = colores(titulo)
    exigir(len(tonos) > 8,
           "la pantalla de titulo solo tiene %d colores: no esta dibujando"
           % len(tonos))
    print("titulo: %dx%d con %d colores" % (titulo[0], titulo[1], len(tonos)))
    exigir(len(set(franja(titulo, 24))) > 2, "no se ve el marcador arriba")

    # --- 2) empieza la partida ------------------------------------------
    maquina.pulsar("START")
    maquina.avanzar(5)
    maquina.pulsar()
    maquina.avanzar(40)
    juego = maquina.dibujar()
    guardar_png(juego, os.path.join(capturas, "ng_juego.png"))
    exigir(distintos(titulo, juego) > 0.002, "la pantalla no cambia al pulsar start")
    # el texto del titulo vive en el plano fix, en las filas 12 a 16
    medio = [maquina.vram[ng.FIXMAP + c * 32 + f]
             for c in range(40) for f in range(12, 17)]
    exigir(not any(medio),
           "el texto del titulo sigue escrito en el plano fix al empezar la partida")

    # --- 3) se juega: correr a la derecha y saltar -----------------------
    movimiento = 0.0
    peor = 0
    antes = juego
    for tramo in range(6):
        for i in range(50):
            maquina.pulsar("RIGHT", "A") if i % 25 == 0 else maquina.pulsar("RIGHT")
            peor = max(peor, maquina.frame())
        ahora = maquina.dibujar()
        movimiento = max(movimiento, distintos(antes, ahora))
        antes = ahora
        if tramo == 2:
            guardar_png(ahora, os.path.join(capturas, "ng_jugando.png"))
    exigir(movimiento > 0.05,
           "la pantalla apenas cambia al jugar (%.1f%%): el scroll no se mueve"
           % (movimiento * 100))
    print("jugando: hasta un %.0f%% de la pantalla cambia entre tramos"
          % (movimiento * 100))

    # --- 4) el frame mas caro cabe en los 200.000 ciclos de la maquina ---
    print("frame mas caro: %d ciclos de los %d que da la consola (%.0f fps)"
          % (peor, ng.CICLOS_FRAME, 60.0 * min(1.0, float(ng.CICLOS_FRAME) / peor)))
    exigir(peor <= ng.CICLOS_FRAME,
           "el frame mas caro gasta %d ciclos y la Neo Geo solo da %d por frame"
           % (peor, ng.CICLOS_FRAME))

    # --- 5) sigue vivo al final -----------------------------------------
    ultimo = maquina.dibujar()
    maquina.pulsar("RIGHT")
    maquina.avanzar(60)
    exigir(distintos(ultimo, maquina.dibujar()) > 0.0,
           "la imagen se ha quedado congelada: el juego se ha colgado")
    guardar_png(maquina.dibujar(), os.path.join(capturas, "ng_final.png"))
    exigir(not maquina.rarezas,
           "el juego hace accesos que el banco no sabe emular: %s"
           % "; ".join(maquina.rarezas[:3]))

    print("frames dibujados: %d" % maquina.frames)
    maquina.cerrar()

    for fallo in fallos:
        print("FALLO:", fallo)
    if fallos:
        return 1
    print("la ROM arranca, dibuja y se juega en el banco; capturas en %s/" % capturas)
    return 0


if __name__ == "__main__":
    carpeta = (sys.argv[1] if len(sys.argv) > 1
               else "examples/bosque-magico/build/neogeo")
    sys.exit(comprobar(carpeta, sys.argv[2] if len(sys.argv) > 2 else "capturas"))
