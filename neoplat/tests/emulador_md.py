"""Arranca la ROM de Mega Drive en un emulador de verdad (opcional).

Carga el core de Genesis Plus GX (libretro) y ejecuta la ROM sin pantalla,
sacando el mapa de pixeles de cada frame tal cual lo genera el VDP. Sirve para
comprobar lo unico que las demas pruebas no pueden: que la consola entiende de
verdad lo que escribe el kit.

Si el core no esta instalado, se salta:

    apt-get install libretro-genesisplusgx
    python3 tests/emulador_md.py ruta/al/juego.bin [carpeta_de_capturas]
"""

from __future__ import annotations

import ctypes
import os
import sys

CORES = [
    os.environ.get("NEOPLAT_CORE_MD", ""),
    "/usr/lib/x86_64-linux-gnu/libretro/genesis_plus_gx_libretro.so",
    "/usr/lib/libretro/genesis_plus_gx_libretro.so",
]

# Constantes de la interfaz libretro que hacen falta aqui.
ENV_GET_CAN_DUPE = 3
ENV_SET_PIXEL_FORMAT = 10
ENV_GET_SYSTEM_DIRECTORY = 9
ENV_GET_SAVE_DIRECTORY = 31
PIXEL_0RGB1555, PIXEL_XRGB8888, PIXEL_RGB565 = 0, 1, 2
DEVICE_JOYPAD = 1
BOTON = {"B": 0, "Y": 1, "SELECT": 2, "START": 3, "UP": 4, "DOWN": 5,
         "LEFT": 6, "RIGHT": 7, "A": 8, "X": 9}


class GameInfo(ctypes.Structure):
    _fields_ = [("path", ctypes.c_char_p), ("data", ctypes.c_void_p),
                ("size", ctypes.c_size_t), ("meta", ctypes.c_char_p)]


class Geometry(ctypes.Structure):
    _fields_ = [("base_width", ctypes.c_uint), ("base_height", ctypes.c_uint),
                ("max_width", ctypes.c_uint), ("max_height", ctypes.c_uint),
                ("aspect_ratio", ctypes.c_float)]


class Timing(ctypes.Structure):
    _fields_ = [("fps", ctypes.c_double), ("sample_rate", ctypes.c_double)]


class AvInfo(ctypes.Structure):
    _fields_ = [("geometry", Geometry), ("timing", Timing)]


def buscar_core() -> str:
    for ruta in CORES:
        if ruta and os.path.isfile(ruta):
            return ruta
    return ""


class Emulador:
    """Lo justo de un frontend de libretro para ejecutar una ROM y mirarla."""

    def __init__(self, core: str):
        self.lib = ctypes.CDLL(core)
        self.frame = None            # (ancho, alto, [(r,g,b), ...])
        self.formato = PIXEL_0RGB1555   # el que trae libretro por defecto
        self.frames = 0
        self.pulsado = set()
        self._directorio = ctypes.c_char_p(b"/tmp")
        self._guardar_callbacks()
        self.lib.retro_init()

    # --- callbacks que pide el core ------------------------------------

    def _guardar_callbacks(self):
        entorno = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_uint, ctypes.c_void_p)
        video = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint,
                                 ctypes.c_uint, ctypes.c_size_t)
        audio = ctypes.CFUNCTYPE(None, ctypes.c_int16, ctypes.c_int16)
        audio_lote = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t)
        sondear = ctypes.CFUNCTYPE(None)
        estado = ctypes.CFUNCTYPE(ctypes.c_int16, ctypes.c_uint, ctypes.c_uint,
                                  ctypes.c_uint, ctypes.c_uint)

        self._cb = [entorno(self._entorno), video(self._video), audio(self._audio),
                    audio_lote(self._audio_lote), sondear(lambda: None),
                    estado(self._estado)]
        self.lib.retro_set_environment(self._cb[0])
        self.lib.retro_set_video_refresh(self._cb[1])
        self.lib.retro_set_audio_sample(self._cb[2])
        self.lib.retro_set_audio_sample_batch(self._cb[3])
        self.lib.retro_set_input_poll(self._cb[4])
        self.lib.retro_set_input_state(self._cb[5])

    def _entorno(self, orden, datos):
        if orden == ENV_SET_PIXEL_FORMAT:
            # el core elige: Genesis Plus GX pide RGB565 (dos bytes por pixel)
            self.formato = ctypes.cast(datos, ctypes.POINTER(ctypes.c_int))[0]
            return self.formato in (PIXEL_0RGB1555, PIXEL_XRGB8888, PIXEL_RGB565)
        if orden == ENV_GET_CAN_DUPE:
            ctypes.cast(datos, ctypes.POINTER(ctypes.c_bool))[0] = True
            return True
        if orden in (ENV_GET_SYSTEM_DIRECTORY, ENV_GET_SAVE_DIRECTORY):
            ctypes.cast(datos, ctypes.POINTER(ctypes.c_char_p))[0] = self._directorio
            return True
        return False

    def _video(self, datos, ancho, alto, paso):
        self.frames += 1
        if not datos:
            return                                   # frame repetido
        crudo = ctypes.string_at(datos, paso * alto)
        pixeles = []
        if self.formato == PIXEL_XRGB8888:
            for y in range(alto):
                fila = y * paso
                for x in range(ancho):
                    p = fila + x * 4
                    pixeles.append((crudo[p + 2], crudo[p + 1], crudo[p]))
        else:
            de565 = self.formato == PIXEL_RGB565
            for y in range(alto):
                fila = y * paso
                for x in range(ancho):
                    p = fila + x * 2
                    v = crudo[p] << 8 | crudo[p + 1]       # el core escribe en el orden de la maquina
                    v = crudo[p + 1] << 8 | crudo[p]
                    if de565:
                        r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
                        pixeles.append((r * 255 // 31, g * 255 // 63, b * 255 // 31))
                    else:
                        r, g, b = (v >> 10) & 31, (v >> 5) & 31, v & 31
                        pixeles.append((r * 255 // 31, g * 255 // 31, b * 255 // 31))
        self.frame = (ancho, alto, pixeles)

    def _audio(self, izquierda, derecha):
        pass

    def _audio_lote(self, datos, marcos):
        return marcos

    def _estado(self, puerto, dispositivo, indice, boton):
        if puerto != 0 or dispositivo != DEVICE_JOYPAD:
            return 0
        return 1 if boton in self.pulsado else 0

    # --- manejo ---------------------------------------------------------

    def cargar(self, rom: str):
        with open(rom, "rb") as fh:
            datos = fh.read()
        self._rom = ctypes.create_string_buffer(datos, len(datos))
        info = GameInfo(rom.encode(), ctypes.cast(self._rom, ctypes.c_void_p),
                        len(datos), None)
        self.lib.retro_load_game.restype = ctypes.c_bool
        if not self.lib.retro_load_game(ctypes.byref(info)):
            raise RuntimeError("el emulador no ha podido cargar la ROM")
        av = AvInfo()
        self.lib.retro_get_system_av_info(ctypes.byref(av))
        return av

    def pulsar(self, *nombres):
        self.pulsado = set(BOTON[n] for n in nombres)

    def avanzar(self, cuantos=1):
        for _ in range(cuantos):
            self.lib.retro_run()

    def cerrar(self):
        self.lib.retro_unload_game()
        self.lib.retro_deinit()


# --- lo que se mira en la imagen ---------------------------------------

def colores(frame):
    """Cuantas veces sale cada color en el frame."""
    cuenta = {}
    for pixel in frame[2]:
        cuenta[pixel] = cuenta.get(pixel, 0) + 1
    return cuenta


def guardar_png(frame, ruta):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools"))
    from ngplat.png import Image, encode_png
    ancho, alto, pixeles = frame
    imagen = Image(ancho, alto, [(r, g, b, 255) for (r, g, b) in pixeles])
    with open(ruta, "wb") as fh:
        fh.write(encode_png(imagen))


def _distintos(a, b):
    """Que parte de la pantalla ha cambiado entre dos frames (0 a 1)."""
    return sum(1 for x, y in zip(a[2], b[2]) if x != y) / float(len(a[2]))


def _franja(frame, alto):
    return frame[2][:frame[0] * alto]


def comprobar(rom: str, capturas: str = "capturas") -> int:
    core = buscar_core()
    if not core:
        print("el core de Genesis Plus GX no esta instalado: se salta la prueba")
        return 0
    os.makedirs(capturas, exist_ok=True)
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
    distintos = colores(titulo)
    exigir(len(distintos) > 8,
           "la pantalla de titulo solo tiene %d colores: no esta dibujando"
           % len(distintos))
    print("titulo: %dx%d con %d colores" % (titulo[0], titulo[1], len(distintos)))

    # el marcador vive en las tres primeras filas (plano ventana)
    exigir(len(set(_franja(titulo, 24))) > 2, "no se ve el marcador arriba")

    # --- 2) empieza la partida ------------------------------------------
    emu.pulsar("START")
    emu.avanzar(10)
    emu.pulsar()
    emu.avanzar(40)
    juego = emu.frame
    guardar_png(juego, os.path.join(capturas, "md_juego.png"))
    # al empezar desaparece el titulo del marcador y sale el jugador: cambia
    # poca pantalla, pero la franja de arriba tiene que cambiar seguro
    exigir(_distintos(titulo, juego) > 0.002, "la pantalla no cambia al pulsar start")
    marcador = ((titulo[0], 24, _franja(titulo, 24)), (juego[0], 24, _franja(juego, 24)))
    exigir(_distintos(*marcador) > 0.005,
           "el marcador no cambia al empezar: el titulo deberia desaparecer")

    # --- 3) se juega: correr a la derecha y saltar -----------------------
    movimiento = 0.0
    antes = juego
    for tramo in range(6):
        for i in range(50):
            emu.pulsar("RIGHT", "B") if i % 25 == 0 else emu.pulsar("RIGHT")
            emu.avanzar(1)
        ahora = emu.frame
        movimiento = max(movimiento, _distintos(antes, ahora))
        antes = ahora
        if tramo == 2:
            guardar_png(ahora, os.path.join(capturas, "md_jugando.png"))
    exigir(movimiento > 0.05,
           "la pantalla apenas cambia al jugar (%.1f%%): el scroll no se mueve"
           % (movimiento * 100))
    print("jugando: hasta un %.0f%% de la pantalla cambia entre tramos"
          % (movimiento * 100))

    # --- 4) sigue vivo al final -----------------------------------------
    ultimo = emu.frame
    emu.pulsar("RIGHT")
    emu.avanzar(60)
    exigir(_distintos(ultimo, emu.frame) > 0.0,
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
    rom = sys.argv[1] if len(sys.argv) > 1 else "examples/bosque-magico/build/megadrive/rom/juego.bin"
    salida = sys.argv[2] if len(sys.argv) > 2 else "capturas"
    sys.exit(comprobar(rom, salida))
