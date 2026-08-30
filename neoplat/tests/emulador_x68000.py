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

    python3 tests/emulador_x68000.py JUEGO.X [capturas] [--pantallas]
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from camara import Vigia, comprobar_salto  # noqa: E402
from libretro import (Emulador, buscar_core, colores, distintos,  # noqa: E402
                      franja, guardar_png)

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


def _esperar_al_juego(emu) -> bool:
    """Espera a que Human68k acabe de arrancar y ejecute el juego.

    No hay que contar segundos ni mirar colores: el juego pide al CRTC su
    propio modo de pantalla, asi que en cuanto el emulador entrega un frame de
    320x224 en vez del 768x512 de la consola de Human68k, es que ya manda el
    juego.
    """
    while emu.frames < FRAMES_DE_ARRANQUE:
        emu.avanzar(30)
        if emu.frame and emu.frame[:2] == (ANCHO, ALTO):
            emu.avanzar(30)                       # que acabe de pintarse
            return True
    return False


def comprobar(ejecutable: str, capturas: str = "capturas",
              pantallas: bool = False) -> int:
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
    fallos = []

    def exigir(condicion, mensaje):
        if not condicion:
            fallos.append(mensaje)

    # El core busca las ROMs en <sistema>/keropi/, asi que se le monta una
    # carpeta de sistema con lo que haga falta y nada mas.
    sistema = tempfile.mkdtemp(prefix="neoplat-x68k-")
    os.makedirs(os.path.join(sistema, "keropi"))
    for nombre in os.listdir(roms):
        origen = os.path.join(roms, nombre)
        if os.path.isfile(origen):
            with open(origen, "rb") as fh:
                datos = fh.read()
            with open(os.path.join(sistema, "keropi", nombre), "wb") as fh:
                fh.write(datos)
    disco = _disco_de_arranque(ejecutable, sistema)

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

    # --- 3) se juega: el escenario se mueve y los actores tambien --------
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

    # --- 4) sigue vivo ---------------------------------------------------
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
    sys.exit(comprobar(ejecutable,
                       argumentos[1] if len(argumentos) > 1 else "capturas",
                       pantallas="--pantallas" in sys.argv[1:]))
