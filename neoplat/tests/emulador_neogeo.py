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
from camara import Vigia, comprobar_salto  # noqa: E402
import maquina_neogeo as ng  # noqa: E402
from imagen import colores, distintos, franja, guardar_png  # noqa: E402
from sonido import (banda_del_efecto, comprobar_melodia,  # noqa: E402
                    nivel, pico_por_frame)

FPS = 60


def comprobar(carpeta, capturas="capturas", musica=None, salto=None,
              sonido=True, pantallas=False):
    try:
        import machine68k  # noqa: F401
    except ImportError:
        print("falta machine68k (pip3 install amitools): se salta la prueba")
        return 0
    if not ng.compilador():
        print("no hay compilador de 68000 en el PATH: se salta la prueba")
        return 0

    os.makedirs(capturas, exist_ok=True)
    franja_del_salto = banda_del_efecto(musica, salto) if musica and salto else None
    fallos = []

    def exigir(condicion, mensaje):
        if not condicion:
            fallos.append(mensaje)

    maquina = ng.cargar(carpeta, sonido=sonido)

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
    if maquina.sonido:
        exigir(nivel(maquina.escuchar(30)) < 1.0,
               "la pantalla de titulo hace ruido: la musica es solo de la partida")

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

    # --- 3) y ademas suena ----------------------------------------------
    #
    # Aqui se cierra el circuito entero: el 68000 escribe una orden en $320000,
    # eso dispara una NMI en el Z80, el Z80 ejecuta la ROM M1 y escribe en el
    # YM2610, y de esos registros sale la onda que se analiza. Es lo unico que
    # comprueba de verdad que la Neo Geo toca lo que pone el game.yaml.
    if musica and maquina.sonido:
        exigir(nivel(maquina.escuchar(10)) > 1.0, "la placa no saca ningun sonido")
        oido = maquina.escuchar(musica.velocidad * (len(musica.pistas[0]) + 1))
        aciertos, total, _, notas = comprobar_melodia(oido, maquina.ritmo, musica, FPS)
        exigir(total and aciertos >= total * 0.8,
               "el YM2610 no toca la melodia del game.yaml: %d notas de %d "
               "(se ha oido %s)" % (aciertos, total, [int(n) for n in notas]))
        print("musica: %d de %d notas son las del game.yaml" % (aciertos, total))
        exigir(not maquina.sonido.colgado,
               "el driver del Z80 se ha quedado colgado en %d frames"
               % maquina.sonido.colgado)

    if franja_del_salto and maquina.sonido:
        quieto = pico_por_frame(maquina.escuchar, 24, maquina.ritmo,
                                *franja_del_salto)
        maquina.pulsar("A")
        maquina.avanzar(2)
        maquina.pulsar()
        saltando = pico_por_frame(maquina.escuchar, 24, maquina.ritmo,
                                  *franja_del_salto)
        exigir(saltando > quieto * 2.5,
               "al saltar no se oye el efecto: entre %.0f y %.0f Hz suena %.1f "
               "veces mas que estando quieto, y deberia notarse mucho mas"
               % (franja_del_salto[0], franja_del_salto[1],
                  saltando / max(1.0, quieto)))
        print("efecto de salto: %.1f veces mas fuerte que el fondo"
              % (saltando / max(1.0, quieto)))

    # --- 4) se juega: correr a la derecha y saltar -----------------------
    movimiento = 0.0
    peor = 0
    antes = juego
    vigia = Vigia() if pantallas else None
    for tramo in range(6):
        for i in range(50):
            maquina.pulsar("RIGHT", "A") if i % 25 == 0 else maquina.pulsar("RIGHT")
            peor = max(peor, maquina.frame())
            if vigia:
                vigia.mirar(maquina.dibujar())
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
    if vigia:
        comprobar_salto(vigia, exigir)

    # --- 5) el frame mas caro cabe en los 200.000 ciclos de la maquina ---
    print("frame mas caro: %d ciclos de los %d que da la consola (%.0f fps)"
          % (peor, ng.CICLOS_FRAME, 60.0 * min(1.0, float(ng.CICLOS_FRAME) / peor)))
    exigir(peor <= ng.CICLOS_FRAME,
           "el frame mas caro gasta %d ciclos y la Neo Geo solo da %d por frame"
           % (peor, ng.CICLOS_FRAME))

    # --- 6) sigue vivo al final -----------------------------------------
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
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools"))
    from ngplat.project import load_project
    from sonido import musica_al_empezar
    raiz = ng.buscar_proyecto(carpeta)
    p = load_project(raiz) if raiz else None
    sys.exit(comprobar(carpeta, sys.argv[2] if len(sys.argv) > 2 else "capturas",
                       musica_al_empezar(p) if p else None,
                       p.sound.efectos.get("salto") if p else None,
                       pantallas=bool(p and p.camera == "pantallas")))
