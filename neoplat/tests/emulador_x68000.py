"""Arranca el juego del X68000 en un emulador de verdad (opcional).

Mete el ejecutable .X en un disco de sistema de Human68k, lo arranca en px68k y
mira lo que sale por pantalla. Es la unica prueba que ejercita la maquina
entera: el formato .X con su tabla de correcciones, el disquete FAT12 de
sectores de 1024 bytes, el CRTC, el chip de sprites con su capa de fondo, el
plano de texto del marcador y los mandos por el 8255.

Nada de esto viene en el repositorio, porque nada de esto es nuestro:

    core     https://buildbot.libretro.com/nightly/linux/x86_64/latest/px68k_libretro.so.zip
    ROMs     iplrom.dat y cgrom.dat del X68000, en <sistema>/keropi/
    sistema  un disquete de arranque de Human68k (.xdf o .d88 convertido)

Las ROMs van en la carpeta de sistema de RetroArch (o se apunta la carpeta con
NEOPLAT_X68000_ROMS) y el disco de Human68k en NEOPLAT_HUMAN68K. Si falta algo,
la prueba se salta, igual que la del Atari ST con el TOS.

**El disquete que genera el kit no arranca solo**, y no es un fallo: Human68k es
software de Sharp y no se puede repartir, asi que el .xdf del kit lleva el juego
para copiarlo a un disco de sistema. Aqui se hace eso mismo sobre la marcha: se
coge el disco de Human68k del usuario, se le mete el .X y se le cambia el
AUTOEXEC.BAT para que lo llame.

    python3 tests/emulador_x68000.py JUEGO.X [capturas] [--proyecto RUTA]
                                    [--pantallas]
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from camara import Vigia, comprobar_salto  # noqa: E402
from libretro import (Emulador, buscar_core, colores, distintos,  # noqa: E402
                      franja, guardar_png)
from sonido import (banda_del_efecto, comprobar_melodia,  # noqa: E402
                    nivel, pico_por_frame)

CORE = "px68k"
FPS = 60
FRAMES_DE_ARRANQUE = 2400      # tope: Human68k tarda lo suyo en llegar al disco
ANCHO, ALTO = 320, 224         # el modo que pide el juego; Human68k usa 768x512


def _buscar_roms() -> str:
    """La carpeta con iplrom.dat y cgrom.dat, que el core busca en keropi/."""
    for ruta in (os.environ.get("NEOPLAT_X68000_ROMS", ""),
                 "/usr/local/share/neoplat/keropi",
                 os.path.expanduser("~/.config/retroarch/system/keropi")):
        if ruta and os.path.isfile(os.path.join(ruta, "iplrom.dat")):
            return ruta
    return ""


def _buscar_human68k() -> str:
    """Un disquete de arranque de Human68k, que es de Sharp y no viene aqui."""
    for ruta in (os.environ.get("NEOPLAT_HUMAN68K", ""),
                 "/usr/local/share/neoplat/human68k.xdf"):
        if ruta and os.path.isfile(ruta):
            return ruta
    return ""


def _disco_de_arranque(ejecutable: str, carpeta: str) -> str:
    """El disco de sistema del usuario con nuestro .X dentro y llamado desde el
    AUTOEXEC.BAT."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools"))
    from ngplat.x68k_disk import insertar_archivo, reemplazar_archivo
    nombre = os.path.basename(ejecutable).upper()
    with open(_buscar_human68k(), "rb") as fh:
        disco = fh.read()
    with open(ejecutable, "rb") as fh:
        disco = insertar_archivo(disco, nombre, fh.read())
    disco = reemplazar_archivo(disco, "AUTOEXEC.BAT",
                               b"A:\\" + nombre.encode("ascii") + b"\r\n")
    destino = os.path.join(carpeta, "arranque.xdf")
    with open(destino, "wb") as fh:
        fh.write(disco)
    return destino


def _donde_empieza(frame, fila: int):
    """El primer pixel encendido de una fila de texto del marcador."""
    ancho, alto, pixeles = frame
    for x in range(ancho):
        for y in range(fila * 8, min((fila + 1) * 8, alto)):
            if pixeles[y * ancho + x] != (0, 0, 0):
                return x
    return None


def preparar(ejecutable: str):
    """Deja lista una carpeta de sistema con las ROMs y un disco de arranque.

    Lo usan esta prueba y la de muestras digitales (tests/maquinas.py), que
    necesitan lo mismo: el core busca las ROMs en <sistema>/keropi/ y el juego
    tiene que ir dentro de un disco de Human68k.
    """
    sistema = tempfile.mkdtemp(prefix="neoplat-x68k-")
    os.makedirs(os.path.join(sistema, "keropi"))
    roms = _buscar_roms()
    for nombre in os.listdir(roms):
        origen = os.path.join(roms, nombre)
        if os.path.isfile(origen):
            with open(origen, "rb") as fh:
                datos = fh.read()
            with open(os.path.join(sistema, "keropi", nombre), "wb") as fh:
                fh.write(datos)
    return sistema, _disco_de_arranque(ejecutable, sistema)


def _esperar_al_juego(emu) -> bool:
    """Espera a que Human68k acabe de arrancar y ejecute el juego.

    Se mira el modo de pantalla y no los colores: el juego pide al CRTC el
    suyo, asi que en cuanto el emulador entrega un frame de 320x224 en vez del
    768x512 de la consola de Human68k, es que ya manda el juego.

    Y despues hay que esperar a que dibuje. Entre que cambia el modo y que hay
    algo en pantalla pasa un rato -sube la PCG entera y pinta la primera
    pantalla de escenario-, y cuanto tarda depende del juego: con treinta
    frames fijos el ejemplo grande llegaba a tiempo y el de `ngplat nuevo` no,
    y la captura del titulo salia en negro.
    """
    # El tope se cuenta desde aqui y no desde el frame cero: esta funcion se
    # llama otra vez despues de un reset (la prueba de los dos mandos juega tres
    # partidas seguidas), y con un tope absoluto la segunda vez se rendiria sin
    # esperar nada.
    limite = emu.frames + FRAMES_DE_ARRANQUE
    while emu.frames < limite:
        emu.avanzar(30)
        if emu.frame and emu.frame[:2] == (ANCHO, ALTO):
            break
    else:
        return False
    while emu.frames < limite:
        emu.avanzar(15)
        if emu.frame and len(colores(emu.frame)) > 2:
            emu.avanzar(15)                       # que acabe de pintarse
            return True
    return False


def comprobar(ejecutable: str, capturas: str = "capturas", musica=None,
              salto=None, pantallas: bool = False) -> int:
    core = buscar_core(CORE, "NEOPLAT_CORE_X68000")
    if not core:
        print("el core de px68k no esta instalado: se salta la prueba")
        return 0
    roms = _buscar_roms()
    if not roms:
        print("no encuentro iplrom.dat: se salta la prueba")
        return 0
    if not _buscar_human68k():
        print("no hay un disco de Human68k (NEOPLAT_HUMAN68K): se salta la prueba")
        return 0
    os.makedirs(capturas, exist_ok=True)
    franja_del_salto = banda_del_efecto(musica, salto) if musica and salto else None
    fallos = []

    def exigir(condicion, mensaje):
        if not condicion:
            fallos.append(mensaje)

    # El core busca las ROMs en <sistema>/keropi/, y el juego tiene que ir
    # dentro de un disco de Human68k: de las dos cosas se encarga preparar().
    sistema, disco = preparar(ejecutable)

    emu = Emulador(core, sistema=sistema)
    emu.cargar(disco)

    # --- 1) arranca Human68k y se ejecuta el juego -----------------------
    arranco = _esperar_al_juego(emu)
    titulo = emu.frame
    exigir(arranco,
           "en %d frames el juego no ha llegado a pedir su modo de pantalla: "
           "Human68k no ha arrancado el .X" % FRAMES_DE_ARRANQUE)
    exigir(titulo is not None, "el emulador no ha dibujado ningun frame")
    if not arranco or titulo is None:
        for fallo in fallos:
            print("FALLO:", fallo)
        return 1
    guardar_png(titulo, os.path.join(capturas, "x68000_titulo.png"))
    cuantos = len(colores(titulo))
    exigir(cuantos > 3, "la pantalla de titulo solo tiene %d colores" % cuantos)
    # el marcador va en el plano de texto, en las tres primeras filas de 8
    exigir(len(set(franja(titulo, 8))) > 1, "no se ve el marcador arriba")
    # Y el nombre del juego, que se escribe en la fila 2 y empieza siempre en
    # la columna 12 (o sea el pixel 96). Se mira donde empieza lo que se ve:
    # si empezara mas a la derecha es que le falta el principio, que es lo que
    # pasaba cuando la barra de vida en blanco lo borraba.
    exigir(_donde_empieza(titulo, 2) is not None
           and _donde_empieza(titulo, 2) < 112,
           "el titulo no empieza donde tiene que empezar: la fila de mensajes "
           "arranca en el pixel %s y el nombre se escribe desde el 96"
           % _donde_empieza(titulo, 2))
    print("titulo: %dx%d con %d colores" % (titulo[0], titulo[1], cuantos))

    # --- 2) empieza la partida ------------------------------------------
    #
    # El mando de esta maquina tiene dos botones, asi que el de saltar hace
    # tambien de START (ver np_video.c). En libretro es el A.
    for _ in range(4):
        emu.pulsar("A")
        emu.avanzar(20)
        emu.pulsar()
        emu.avanzar(20)
    juego = emu.frame
    guardar_png(juego, os.path.join(capturas, "x68000_juego.png"))
    exigir(distintos(titulo, juego) > 0.001, "la pantalla no cambia al pulsar start")

    # --- 3) y ademas suena: el YM2151 toca la melodia del game.yaml ------
    if musica:
        exigir(nivel(emu.escuchar(10)) > 1.0, "el X68000 no saca ningun sonido")
        oido = emu.escuchar(musica.velocidad * (len(musica.pistas[0]) + 1))
        aciertos, total, _, notas = comprobar_melodia(oido, emu.ritmo, musica, FPS)
        exigir(total and aciertos >= total * 0.8,
               "el YM2151 no toca la melodia del game.yaml: %d notas de %d "
               "(se ha oido %s)" % (aciertos, total, [int(n) for n in notas]))
        print("musica: %d de %d notas son las del game.yaml" % (aciertos, total))

    if franja_del_salto:
        quieto = pico_por_frame(emu.escuchar, 24, emu.ritmo, *franja_del_salto)
        emu.pulsar("A")
        emu.avanzar(2)
        emu.pulsar()
        saltando = pico_por_frame(emu.escuchar, 24, emu.ritmo, *franja_del_salto)
        exigir(saltando > quieto * 2.5,
               "al saltar no se oye el efecto: entre %.0f y %.0f Hz suena %.1f "
               "veces mas que estando quieto"
               % (franja_del_salto[0], franja_del_salto[1],
                  saltando / max(1.0, quieto)))
        print("efecto de salto: %.1f veces mas fuerte que el fondo"
              % (saltando / max(1.0, quieto)))

    # --- 4) se juega: el escenario se mueve y los actores tambien --------
    movimiento = 0.0
    antes = juego
    vigia = Vigia() if pantallas else None
    for tramo in range(6):
        for i in range(60):
            emu.pulsar("RIGHT", "A") if i % 30 == 0 else emu.pulsar("RIGHT")
            emu.avanzar(1)
            if vigia:
                vigia.mirar(emu.frame)
        ahora = emu.frame
        movimiento = max(movimiento, distintos(antes, ahora))
        antes = ahora
        if tramo == 3:
            guardar_png(ahora, os.path.join(capturas, "x68000_jugando.png"))
    exigir(movimiento > 0.01,
           "la pantalla apenas cambia al jugar (%.2f%%): no se mueve nada"
           % (movimiento * 100))
    print("jugando: hasta un %.0f%% de la pantalla cambia entre tramos"
          % (movimiento * 100))
    if vigia:
        comprobar_salto(vigia, exigir)

    # --- 5) sigue vivo ---------------------------------------------------
    ultimo = emu.frame
    movida = 0.0
    for i in range(100):
        emu.pulsar("RIGHT", "A") if i % 20 == 0 else emu.pulsar(
            "LEFT" if (i // 25) % 2 else "RIGHT")
        emu.avanzar(1)
        movida = max(movida, distintos(ultimo, emu.frame))
        ultimo = emu.frame
    exigir(movida > 0.0, "la imagen se ha quedado congelada: el juego se ha colgado")
    guardar_png(emu.frame, os.path.join(capturas, "x68000_final.png"))
    emu.cerrar()

    for fallo in fallos:
        print("FALLO:", fallo)
    if fallos:
        return 1
    print("el juego arranca desde el disco de Human68k y se juega; capturas en "
          "%s/" % capturas)
    return 0


if __name__ == "__main__":
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    ejecutable = (argumentos[0] if argumentos
                  else "examples/bosque-magico/build/x68000/disco/BOSQUEMA.X")
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools"))
    from ngplat.project import load_project
    from sonido import buscar_proyecto, musica_al_empezar
    proyecto = ""
    for opcion in sys.argv[1:]:
        if opcion.startswith("--proyecto="):
            proyecto = opcion.split("=", 1)[1]
    proyecto = proyecto or buscar_proyecto(ejecutable)
    p = load_project(proyecto) if proyecto else None
    sys.exit(comprobar(ejecutable,
                       argumentos[1] if len(argumentos) > 1 else "capturas",
                       musica_al_empezar(p) if p else None,
                       p.sound.efectos.get("salto") if p else None,
                       pantallas="--pantallas" in sys.argv[1:]))
