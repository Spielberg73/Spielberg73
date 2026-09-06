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
from camara import Vigia, comprobar_salto  # noqa: E402
from imagen import minimo_de_colores, minimo_del_marcador  # noqa: E402
from sonido import (banda_del_efecto, comprobar_melodia, comprobar_titulo,  # noqa: E402
                    nivel, pico_por_frame)
from libretro import (Emulador, buscar_core, colores, distintos,  # noqa: E402
                      franja, guardar_png)

CORE = "virtualjaguar"
# El boton START del mando de RetroPad es el OPTION de la Jaguar; el que usa el
# kit para empezar la partida es PAUSE, que el core pone en SELECT.
EMPEZAR = "SELECT"
SALTAR = "A"
FPS = 60


def comprobar(rom: str, capturas: str = "capturas",
              pantallas: bool = False, musica=None, salto=None,
              titulo_musica: str = "", iso: bool = False) -> int:
    core = buscar_core(CORE, "NEOPLAT_CORE_JAGUAR")
    if not core:
        print("el core de Virtual Jaguar no esta instalado: se salta la prueba")
        return 0
    os.makedirs(capturas, exist_ok=True)
    franja_del_salto = banda_del_efecto(musica, salto) if musica and salto else None
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
    exigir(len(tonos) > minimo_de_colores(iso),
           "la pantalla de titulo solo tiene %d colores: no esta dibujando"
           % len(tonos))
    print("titulo: %dx%d con %d colores" % (titulo[0], titulo[1], len(tonos)))
    exigir(len(set(franja(titulo, 32))) > minimo_del_marcador(iso),
           "no se ve el marcador arriba")
    if musica:
        comprobar_titulo(exigir, nivel(emu.escuchar(20)), titulo_musica)

    # --- 2) empieza la partida ------------------------------------------
    emu.pulsar(EMPEZAR)
    emu.avanzar(10)
    emu.pulsar()
    emu.avanzar(60)
    juego = emu.frame
    guardar_png(juego, os.path.join(capturas, "jag_juego.png"))
    exigir(distintos(titulo, juego) > 0.002, "la pantalla no cambia al empezar")

    # --- 2b) y suena: el DSP toca la melodia del game.yaml ---------------
    #
    # La Jaguar no tiene chip de sonido: las ondas las hace el programa que
    # corre en el DSP de Jerry (tools/ngplat/jerry.py), muestra a muestra. Aqui
    # se cierra el circuito entero, del game.yaml al DAC.
    if musica:
        exigir(nivel(emu.escuchar(10)) > 1.0, "la Jaguar no saca ningun sonido")
        oido = emu.escuchar(musica.velocidad * (len(musica.pistas[0]) + 1))
        aciertos, total, _, notas = comprobar_melodia(oido, emu.ritmo, musica, FPS)
        exigir(total and aciertos >= total * 0.8,
               "el DSP no toca la melodia del game.yaml: %d notas de %d "
               "(se ha oido %s)" % (aciertos, total, [int(n) for n in notas]))
        print("musica: %d de %d notas son las del game.yaml" % (aciertos, total))

    if franja_del_salto:
        quieto = pico_por_frame(emu.escuchar, 24, emu.ritmo, *franja_del_salto)
        emu.pulsar(SALTAR)
        emu.avanzar(2)
        emu.pulsar()
        saltando = pico_por_frame(emu.escuchar, 24, emu.ritmo, *franja_del_salto)
        exigir(saltando > quieto * 2.5,
               "al saltar no se oye el efecto: entre %.0f y %.0f Hz suena %.1f "
               "veces mas que estando quieto, y deberia notarse mucho mas"
               % (franja_del_salto[0], franja_del_salto[1],
                  saltando / max(1.0, quieto)))
        print("efecto de salto: %.1f veces mas fuerte que el fondo"
              % (saltando / max(1.0, quieto)))

    # --- 3) se juega: correr a la derecha y saltar -----------------------
    movimiento = 0.0
    antes = juego
    vigia = Vigia() if pantallas else None
    for tramo in range(5):
        for i in range(50):
            emu.pulsar("RIGHT", "A") if i % 25 == 0 else emu.pulsar("RIGHT")
            emu.avanzar(1)
            if vigia:
                vigia.mirar(emu.frame)
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
    if vigia:
        comprobar_salto(vigia, exigir, iso)

    # --- 4) el marcador se ve una vez, no dos ---------------------------
    #
    # El chip compone la lista de objetos mientras el haz recorre la pantalla:
    # si la lista se reescribe a medias, el objeto se vuelve a pintar desde
    # arriba a partir de ahi y el marcador sale dos veces.
    ancho, alto, pixeles = emu.frame
    claro = max(colores(emu.frame), key=lambda p: sum(p))     # el blanco del marcador
    # Se mira **donde** cae el texto, no cuanto hay: contar filas a secas
    # confundia "el marcador tiene otra linea" (llaves, municion) con "el
    # marcador sale dos veces", que es lo unico que se quiere detectar. El
    # sintoma de la carrera es texto **por debajo** de la franja del marcador.
    # La franja del marcador, en coordenadas de la **captura**: el objeto del
    # HUD va en la linea 0 de la pantalla y mide NP_HUD_ALTO (24, tres filas de
    # ocho), pero lo que devuelve el emulador trae ocho lineas de borde por
    # arriba -medido: el texto de la primera fila sale en la 9-, asi que la
    # franja cae entre la 8 y la 32. Con 24 a secas, un juego que use las tres
    # filas -puntuacion, llaves y vida, que es lo que ensena el de kung-fu-
    # daba por "marcador repetido" su propia tercera fila.
    HUD = 32 * alto // 240
    arriba = abajo = 0
    for y in range(alto):
        cuantos = sum(1 for x in range(ancho) if pixeles[y * ancho + x] == claro)
        if cuantos < 20:
            continue
        if y < HUD:
            arriba += 1
        else:
            abajo += 1
    exigir(arriba >= 3, "no se ve el texto del marcador")
    exigir(abajo == 0,
           "hay %d filas de texto por debajo del marcador: la lista de objetos "
           "se esta reescribiendo con el haz en mitad de la pantalla" % abajo)
    print("marcador: %d filas de texto en su franja, %d por debajo"
          % (arriba, abajo))

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
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools"))
    from ngplat.project import load_project
    from sonido import buscar_proyecto
    proyecto = buscar_proyecto(rom)
    p = load_project(proyecto) if proyecto else None
    from sonido import musica_al_empezar
    sys.exit(comprobar(rom, sys.argv[2] if len(sys.argv) > 2 else "capturas",
                       pantallas=bool(p and p.camera == "pantallas"),
                       iso=bool(p and p.view == "iso"),
                       musica=musica_al_empezar(p) if p else None,
                       salto=p.sound.efectos.get("salto") if p else None,
                       titulo_musica=p.sound.titulo if p else ""))
