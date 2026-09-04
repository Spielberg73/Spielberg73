"""Arranca la ROM de Mega Drive en un emulador de verdad (opcional).

Ejecuta el cartucho en Genesis Plus GX sin pantalla y mira el mapa de pixeles
que sale del VDP: si la consola no entiende lo que escribe el kit, aqui se ve.
Si el core no esta instalado, se salta:

    apt-get install libretro-genesisplusgx
    python3 tests/emulador_md.py ruta/al/juego.bin [carpeta_de_capturas]
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from libretro import (Emulador, buscar_core, colores, distintos,  # noqa: E402
                      franja, guardar_png)
from imagen import minimo_de_colores, minimo_del_marcador  # noqa: E402
from camara import Vigia, comprobar_salto  # noqa: E402
from sonido import (banda_del_efecto, comprobar_melodia, comprobar_titulo,  # noqa: E402
                    nivel, pico_por_frame)

CORE = "genesis_plus_gx"
FPS = 60


def comprobar(rom: str, capturas: str = "capturas", musica=None,
              salto=None, pantallas: bool = False, titulo_musica: str = "",
              iso: bool = False) -> int:
    core = buscar_core(CORE, "NEOPLAT_CORE_MD")
    if not core:
        print("el core de Genesis Plus GX no esta instalado: se salta la prueba")
        return 0
    os.makedirs(capturas, exist_ok=True)
    franja_del_salto = banda_del_efecto(musica, salto) if musica and salto else None
    fallos = []

    def exigir(condicion, mensaje):
        if not condicion:
            fallos.append(mensaje)

    emu = Emulador(core)
    emu.cargar(rom)

    # --- 1) arranca y pinta la pantalla de titulo ------------------------
    emu.avanzar(120)
    exigir(emu.frame is not None, "el emulador no ha dibujado ningun frame")
    titulo = emu.frame
    guardar_png(titulo, os.path.join(capturas, "md_titulo.png"))
    exigir(titulo[0] == 320 and titulo[1] == 224,
           "la pantalla mide %dx%d y deberia ser 320x224" % (titulo[0], titulo[1]))
    distintos_titulo = colores(titulo)
    exigir(len(distintos_titulo) > minimo_de_colores(iso),
           "la pantalla de titulo solo tiene %d colores: no esta dibujando"
           % len(distintos_titulo))
    print("titulo: %dx%d con %d colores" % (titulo[0], titulo[1], len(distintos_titulo)))
    # el marcador vive en las tres primeras filas (plano ventana)
    exigir(len(set(franja(titulo, 24))) > minimo_del_marcador(iso),
           "no se ve el marcador arriba")
    comprobar_titulo(exigir, nivel(emu.escuchar(30)), titulo_musica)

    # --- 2) empieza la partida ------------------------------------------
    emu.pulsar("START")
    emu.avanzar(10)
    emu.pulsar()
    emu.avanzar(40)
    juego = emu.frame
    guardar_png(juego, os.path.join(capturas, "md_juego.png"))
    exigir(distintos(titulo, juego) > 0.002, "la pantalla no cambia al pulsar start")
    exigir(distintos((titulo[0], 24, franja(titulo, 24)),
                     (juego[0], 24, franja(juego, 24))) > 0.005,
           "el marcador no cambia al empezar: el titulo deberia desaparecer")

    # --- 3) y ademas suena: el PSG toca la melodia del game.yaml ---------
    #
    # Se escucha nada mas empezar el nivel y sin tocar el mando: los efectos
    # comparten canal con la musica y taparian las notas.
    if musica:
        exigir(nivel(emu.escuchar(max(10, musica.velocidad))) > 1.0,
               "la consola no saca ningun sonido")
        oido = emu.escuchar(musica.velocidad * (len(musica.pistas[0]) + 1))
        aciertos, total, _, notas = comprobar_melodia(oido, emu.ritmo, musica, FPS)
        exigir(total and aciertos >= total * 0.8,
               "el PSG no toca la melodia del game.yaml: %d notas de %d "
               "(se ha oido %s)" % (aciertos, total, [int(n) for n in notas]))
        print("musica: %d de %d notas son las del game.yaml" % (aciertos, total))

    # los efectos van por su canal y suenan mas agudos que la musica: al
    # saltar tiene que aparecer algo en esa franja que antes no estaba
    if franja_del_salto:
        quieto = pico_por_frame(emu.escuchar, 24, emu.ritmo, *franja_del_salto)
        emu.pulsar("B")
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

    # --- 4) se juega: correr a la derecha y saltar -----------------------
    movimiento = 0.0
    antes = juego
    vigia = Vigia() if pantallas else None
    for tramo in range(6):
        for i in range(50):
            emu.pulsar("RIGHT", "B") if i % 25 == 0 else emu.pulsar("RIGHT")
            emu.avanzar(1)
            if vigia:
                vigia.mirar(emu.frame)
        ahora = emu.frame
        movimiento = max(movimiento, distintos(antes, ahora))
        antes = ahora
        if tramo == 2:
            guardar_png(ahora, os.path.join(capturas, "md_jugando.png"))
    exigir(movimiento > 0.05,
           "la pantalla apenas cambia al jugar (%.1f%%): el scroll no se mueve"
           % (movimiento * 100))
    print("jugando: hasta un %.0f%% de la pantalla cambia entre tramos"
          % (movimiento * 100))
    if vigia:
        comprobar_salto(vigia, exigir, iso)

    # --- 5) sigue vivo al final -----------------------------------------
    ultimo = emu.frame
    emu.pulsar("RIGHT")
    emu.avanzar(60)
    exigir(distintos(ultimo, emu.frame) > 0.0,
           "la imagen se ha quedado congelada: el juego se ha colgado")
    guardar_png(emu.frame, os.path.join(capturas, "md_final.png"))

    print("frames dibujados: %d" % emu.frames)
    emu.cerrar()

    for fallo in fallos:
        print("FALLO:", fallo)
    if fallos:
        return 1
    print("la ROM arranca, dibuja y se juega en el emulador; capturas en %s/" % capturas)
    return 0


if __name__ == "__main__":
    rom = (sys.argv[1] if len(sys.argv) > 1
           else "examples/bosque-magico/build/megadrive/rom/juego.bin")
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools"))
    from ngplat.project import load_project
    from sonido import buscar_proyecto, musica_al_empezar
    proyecto = buscar_proyecto(rom)
    p = load_project(proyecto) if proyecto else None
    sys.exit(comprobar(rom, sys.argv[2] if len(sys.argv) > 2 else "capturas",
                       musica_al_empezar(p) if p else None,
                       p.sound.efectos.get("salto") if p else None,
                       pantallas=bool(p and p.camera == "pantallas"),
                       iso=bool(p and p.view == "iso"),
                       titulo_musica=p.sound.titulo if p else ""))
