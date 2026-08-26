"""Arranca el disquete de Atari ST en un emulador de verdad (opcional).

Mete el .st en un 520 ST emulado (Hatari, con EmuTOS: el TOS libre) y mira lo
que sale por pantalla y por el YM2149. Es la unica prueba que ejercita el disco
entero: la FAT12, la carpeta AUTO, el ejecutable de GEMDOS con su tabla de
relocalizacion, el Shifter, el teclado por interrupcion y el chip de sonido.

Ni el core ni el TOS vienen en los repositorios:

    https://buildbot.libretro.com/nightly/linux/x86_64/latest/hatari_libretro.so.zip
    https://sourceforge.net/projects/emutos/files/emutos/1.4/

El core va en /usr/local/lib/libretro/ (o se apunta con NEOPLAT_CORE_ST) y la
imagen de EmuTOS en la carpeta de sistema como `tos.img`. Si falta alguno, la
prueba se salta.

**El mando del emulador.** Hatari no conecta el mando al joystick del ST si no
se le dice; hay que pedirlo opcion a opcion (`hatari_mapper_*`). Esta
comprobado byte a byte contra el IKBD: sin esas opciones no llega **nada**, ni
teclas ni joystick, y el juego parece colgado cuando lo que pasa es que nadie
le esta hablando.

    python3 tests/emulador_st.py ruta/al/juego.st [carpeta_de_capturas]
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from camara import Vigia, comprobar_salto  # noqa: E402
from libretro import (Emulador, buscar_core, colores, distintos,  # noqa: E402
                      franja, guardar_png)
from sonido import (banda_del_efecto, comprobar_melodia,  # noqa: E402
                    nivel, pico_por_frame)

CORE = "hatari"
FPS = 50                       # el hardware; el juego dibuja uno de cada dos
SEGUNDOS_DE_ARRANQUE = 8       # lo que tarda EmuTOS en llegar a la carpeta AUTO
BORDE_ARRIBA = 24              # lineas de borde que ensena Hatari antes del ST

# Lo que hay que decirle a Hatari. Los `mapper` no son un capricho: son lo que
# conecta el mando de libretro al joystick y al teclado del ST.
OPCIONES = {
    "hatari_machinetype": "st",          # un 520 ST de los de siempre
    "hatari_ramsize": "1",
    "hatari_fastboot": "true",           # sin la cuenta de memoria del arranque
    "hatari_fastfdc": "true",
    "hatari_frameskips": "0",
    "hatari_writeprotect_floppy": "off",
    "hatari_writeprotect_hd": "off",
    "hatari_autoloadb": "false",
    "hatari_floppy_sound": "false",
    "hatari_led_status_display": "false",
    "hatari_nomouse": "true",
    "hatari_nokeys": "false",
    "hatari_twojoy": "false",
    "hatari_start_in_mouse_mode": "false",
    "hatari_mapper_b": "JOYSTICK_FIRE",
    "hatari_mapper_left": "JOYSTICK_LEFT",
    "hatari_mapper_right": "JOYSTICK_RIGHT",
    "hatari_mapper_up": "JOYSTICK_UP",
    "hatari_mapper_down": "JOYSTICK_DOWN",
    "hatari_mapper_a": "RETROK_SPACE",    # las teclas tambien valen
    "hatari_mapper_x": "RETROK_RETURN",
}


def _buscar_tos():
    """La imagen de EmuTOS, que el core busca en la carpeta de sistema."""
    for ruta in (os.environ.get("NEOPLAT_TOS", ""),
                 "/usr/local/share/neoplat/tos.img",
                 os.path.expanduser("~/.config/retroarch/system/tos.img")):
        if ruta and os.path.isfile(ruta):
            return ruta
    return ""


def comprobar(disco: str, capturas: str = "capturas", musica=None,
              salto=None, pantallas: bool = False) -> int:
    core = buscar_core(CORE, "NEOPLAT_CORE_ST")
    if not core:
        print("el core de Hatari no esta instalado: se salta la prueba")
        return 0
    tos = _buscar_tos()
    if not tos:
        print("no encuentro una imagen de TOS (tos.img): se salta la prueba")
        return 0
    os.makedirs(capturas, exist_ok=True)
    franja_del_salto = banda_del_efecto(musica, salto) if musica and salto else None
    fallos = []

    def exigir(condicion, mensaje):
        if not condicion:
            fallos.append(mensaje)

    # El core se monta su carpeta de trabajo en <sistema>/hatari y busca el TOS
    # ahi dentro; sin ella no llega ni a cargar el disquete.
    sistema = tempfile.mkdtemp(prefix="neoplat-st-")
    os.makedirs(os.path.join(sistema, "hatari", "tos"))
    shutil.copyfile(tos, os.path.join(sistema, "tos.img"))
    shutil.copyfile(tos, os.path.join(sistema, "hatari", "tos", "tos.img"))
    opciones = dict(OPCIONES)
    opciones["hatari_tosimage"] = "tos.img"
    emu = Emulador(core, sistema=sistema, opciones=opciones)
    emu.cargar(disco)

    # --- 1) el disquete arranca solo y sale el juego ---------------------
    while emu.frames < SEGUNDOS_DE_ARRANQUE * FPS:
        emu.avanzar(50)
    titulo = emu.frame
    exigir(titulo is not None, "el emulador no ha dibujado ningun frame")
    guardar_png(titulo, os.path.join(capturas, "st_titulo.png"))
    cuantos = len(colores(titulo))
    # si el juego no arrancase se veria el escritorio de EmuTOS, que es liso
    exigir(cuantos > 5,
           "a los %d segundos solo hay %d colores: el juego de la carpeta AUTO "
           "no ha arrancado" % (SEGUNDOS_DE_ARRANQUE, cuantos))
    # el marcador del ST es texto blanco sobre el fondo del nivel: con que la
    # franja de arriba tenga dos colores ya esta escrito algo
    exigir(len(set(franja(titulo, BORDE_ARRIBA + 16))) > 1,
           "no se ve el marcador arriba")
    print("titulo: %dx%d con %d colores" % (titulo[0], titulo[1], cuantos))

    # --- 2) empieza la partida (el joystick del ST solo tiene un boton) --
    for _ in range(4):
        emu.pulsar("B")
        emu.avanzar(20)
        emu.pulsar()
        emu.avanzar(20)
    juego = emu.frame
    guardar_png(juego, os.path.join(capturas, "st_juego.png"))
    exigir(distintos(titulo, juego) > 0.001, "la pantalla no cambia al pulsar start")

    # --- 3) y ademas suena: el YM2149 toca la melodia del game.yaml ------
    if musica:
        exigir(nivel(emu.escuchar(10)) > 1.0, "el ST no saca ningun sonido")
        oido = emu.escuchar(musica.velocidad * (len(musica.pistas[0]) + 1))
        aciertos, total, _, notas = comprobar_melodia(oido, emu.ritmo, musica, FPS)
        exigir(total and aciertos >= total * 0.8,
               "el YM2149 no toca la melodia del game.yaml: %d notas de %d "
               "(se ha oido %s)" % (aciertos, total, [int(n) for n in notas]))
        print("musica: %d de %d notas son las del game.yaml" % (aciertos, total))

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

    # --- 4) se juega ----------------------------------------------------
    movimiento = 0.0
    antes = juego
    vigia = Vigia() if pantallas else None
    for tramo in range(6):
        for i in range(60):
            emu.pulsar("RIGHT", "B") if i % 30 == 0 else emu.pulsar("RIGHT")
            emu.avanzar(1)
            if vigia:
                vigia.mirar(emu.frame)
        ahora = emu.frame
        movimiento = max(movimiento, distintos(antes, ahora))
        antes = ahora
        if tramo == 3:
            guardar_png(ahora, os.path.join(capturas, "st_jugando.png"))
    exigir(movimiento > 0.01,
           "la pantalla apenas cambia al jugar (%.2f%%): no se mueve nada"
           % (movimiento * 100))
    print("jugando: hasta un %.0f%% de la pantalla cambia entre tramos"
          % (movimiento * 100))
    if vigia:
        comprobar_salto(vigia, exigir)

    # --- 5) sigue vivo --------------------------------------------------
    ultimo = emu.frame
    emu.pulsar("RIGHT")
    emu.avanzar(100)
    exigir(distintos(ultimo, emu.frame) > 0.0,
           "la imagen se ha quedado congelada: el juego se ha colgado")
    guardar_png(emu.frame, os.path.join(capturas, "st_final.png"))
    emu.cerrar()

    for fallo in fallos:
        print("FALLO:", fallo)
    if fallos:
        return 1
    print("el disquete arranca y se juega en el emulador; capturas en %s/" % capturas)
    return 0


if __name__ == "__main__":
    disco = (sys.argv[1] if len(sys.argv) > 1
             else "examples/bosque-magico/build/atarist/disco/bosquema.st")
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools"))
    from ngplat.project import load_project
    from sonido import buscar_proyecto, musica_al_empezar
    proyecto = buscar_proyecto(disco)
    p = load_project(proyecto) if proyecto else None
    sys.exit(comprobar(disco, sys.argv[2] if len(sys.argv) > 2 else "capturas",
                       musica_al_empezar(p) if p else None,
                       p.sound.efectos.get("salto") if p else None,
                       pantallas=bool(p and p.camera == "pantallas")))
