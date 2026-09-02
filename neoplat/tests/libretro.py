"""Un frontend minimo de libretro para arrancar lo que compila el kit.

Los emuladores de libretro son bibliotecas con una interfaz muy pequena: se les
dan unos cuantos callbacks, se les pasa la ROM y se les pide un frame cada vez.
Eso permite ejecutarlos **sin pantalla** y mirar el mapa de pixeles tal cual lo
genera el chip de video, que es la unica forma de comprobar lo que ninguna otra
prueba puede: que la maquina entiende de verdad lo que escribe el kit.

Aqui esta la parte comun; cada maquina tiene su archivo (emulador_md.py,
emulador_amiga.py) con su core y lo que hay que mirar en la pantalla.
"""

from __future__ import annotations

import array
import ctypes
import os
import sys

DIRECTORIOS = [
    "/usr/lib/x86_64-linux-gnu/libretro",
    "/usr/lib/libretro",
    "/usr/local/lib/libretro",
    os.path.expanduser("~/.config/retroarch/cores"),
]

# Constantes de la interfaz libretro que hacen falta aqui.
ENV_GET_CAN_DUPE = 3
ENV_GET_SYSTEM_DIRECTORY = 9
ENV_SET_PIXEL_FORMAT = 10
ENV_GET_VARIABLE = 15
ENV_SET_VARIABLES = 16
ENV_GET_VARIABLE_UPDATE = 17
ENV_SET_SUPPORT_NO_GAME = 18
ENV_SET_FRAME_TIME_CALLBACK = 21
ENV_GET_LOG_INTERFACE = 27
ENV_GET_CORE_ASSETS_DIRECTORY = 30
ENV_GET_SAVE_DIRECTORY = 31
ENV_SET_GEOMETRY = 37
ENV_GET_AUDIO_VIDEO_ENABLE = 47
PIXEL_0RGB1555, PIXEL_XRGB8888, PIXEL_RGB565 = 0, 1, 2
DEVICE_JOYPAD = 1
BOTON = {"B": 0, "Y": 1, "SELECT": 2, "START": 3, "UP": 4, "DOWN": 5,
         "LEFT": 6, "RIGHT": 7, "A": 8, "X": 9}


_LIBC = ctypes.CDLL("libc.so.6", use_errno=True)
_LIBC.snprintf.restype = ctypes.c_int
_RE = __import__("re")
# un formato en el que todo lo que se sustituye son numeros
_SOLO_NUMEROS = _RE.compile(r"^(?:[^%]|%[-+ 0-9.]*[diuxXc])*$")
_ESPECIFICADOR = _RE.compile(r"%[-+ #0-9.*]*(?:hh|h|ll|l|z)?([diuxXcsfgep%])")


def _mapa_de_memoria():
    """Los trozos de memoria del proceso que se pueden leer."""
    regiones = []
    try:
        with open("/proc/self/maps", "r") as fh:
            for linea in fh:
                rango, permisos = linea.split()[0], linea.split()[1]
                if "r" not in permisos:
                    continue
                inicio, fin = rango.split("-")
                regiones.append((int(inicio, 16), int(fin, 16)))
    except OSError:
        pass
    return regiones


def _cadena_de(direccion):
    """Lee una cadena de C solo si su direccion esta en memoria mapeada: seguir
    un puntero invalido no lanza una excepcion, tumba el proceso entero."""
    if not direccion:
        return None
    for inicio, fin in _mapa_de_memoria():
        if inicio <= direccion < fin:
            try:
                return ctypes.string_at(direccion).decode("latin-1", "replace")
            except Exception:
                return None
    return None


class Variable(ctypes.Structure):
    _fields_ = [("key", ctypes.c_char_p), ("value", ctypes.c_char_p)]


class GameInfo(ctypes.Structure):
    _fields_ = [("path", ctypes.c_char_p), ("data", ctypes.c_void_p),
                ("size", ctypes.c_size_t), ("meta", ctypes.c_char_p)]


class Geometry(ctypes.Structure):
    _fields_ = [("base_width", ctypes.c_uint), ("base_height", ctypes.c_uint),
                ("max_width", ctypes.c_uint), ("max_height", ctypes.c_uint),
                ("aspect_ratio", ctypes.c_float)]


class Timing(ctypes.Structure):
    _fields_ = [("fps", ctypes.c_double), ("sample_rate", ctypes.c_double)]


class TiempoDeFrame(ctypes.Structure):
    """Lo que pasa el core en SET_FRAME_TIME_CALLBACK: una funcion a la que hay
    que llamar antes de cada frame diciendole cuanto tiempo ha pasado."""
    _fields_ = [("callback", ctypes.c_void_p), ("reference", ctypes.c_int64)]


class AvInfo(ctypes.Structure):
    _fields_ = [("geometry", Geometry), ("timing", Timing)]


def buscar_core(nombre: str, variable: str = "") -> str:
    """Busca un core de libretro por nombre (sin el _libretro.so)."""
    candidatos = [os.environ.get(variable, "")] if variable else []
    candidatos.append(os.environ.get("NEOPLAT_CORES", ""))
    for carpeta in DIRECTORIOS:
        candidatos.append(os.path.join(carpeta, nombre + "_libretro.so"))
    for ruta in candidatos:
        if not ruta:
            continue
        if os.path.isdir(ruta):
            ruta = os.path.join(ruta, nombre + "_libretro.so")
        if os.path.isfile(ruta):
            return ruta
    return ""


class Emulador:
    """Lo justo de un frontend de libretro para ejecutar una ROM y mirarla."""

    def __init__(self, core: str, sistema: str = "/tmp", opciones=None,
                 traza: bool = False):
        self.lib = ctypes.CDLL(core)
        self.opciones = dict(opciones or {})   # variables del core
        self.traza = traza
        self.mensajes = []
        self.variables = {}          # las que ofrece el core
        self._crudo = None           # (bytes, ancho, alto, paso)
        self._descifrado = None
        self.formato = PIXEL_0RGB1555   # el que trae libretro por defecto
        self.frames = 0
        self.pulsado = {0: set(), 1: set()}
        self.sonido = array.array("h")   # muestras estereo entrelazadas
        self.ritmo = 0                   # muestras por segundo, lo dice el core
        self._directorio = ctypes.c_char_p(sistema.encode())
        self._reloj = None               # reloj de frame, si el core lo pide
        self._reloj_us = 0
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

        registro = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p,
                                    ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_void_p, ctypes.c_void_p)
        self._vivos = []
        self._cb = [entorno(self._entorno), video(self._video), audio(self._audio),
                    audio_lote(self._audio_lote), sondear(lambda: None),
                    estado(self._estado), registro(self._log)]
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
        if orden in (ENV_GET_SYSTEM_DIRECTORY, ENV_GET_SAVE_DIRECTORY,
                     ENV_GET_CORE_ASSETS_DIRECTORY):
            ctypes.cast(datos, ctypes.POINTER(ctypes.c_char_p))[0] = self._directorio
            return True
        if orden == ENV_GET_VARIABLE:
            variable = ctypes.cast(datos, ctypes.POINTER(Variable))[0]
            valor = self.opciones.get(variable.key.decode() if variable.key else "")
            if valor is None:
                return False
            self._vivos.append(ctypes.c_char_p(valor.encode()))
            variable.value = self._vivos[-1]
            return True
        if orden == ENV_GET_VARIABLE_UPDATE:
            ctypes.cast(datos, ctypes.POINTER(ctypes.c_bool))[0] = False
            return True
        if orden == ENV_GET_LOG_INTERFACE:
            ctypes.cast(datos, ctypes.POINTER(ctypes.c_void_p))[0] = \
                ctypes.cast(self._cb[6], ctypes.c_void_p)
            return True
        if orden == ENV_SET_VARIABLES:
            self._leer_variables(datos)
            return True
        if orden == ENV_SET_FRAME_TIME_CALLBACK:
            # Hay cores cuyo tiempo interno **no avanza** con retro_run: lo
            # llevan por aqui. px68k es uno, y sin esto el X68000 arrancaba la
            # ROM pero el disquete no giraba nunca: se veia el texto del IPL y
            # ahi se quedaba, sin llegar a cargar el sistema. Nada de lo otro
            # que se probo (las ROMs, el formato del disco, la interfaz de
            # discos, el VFS, las opciones del core) tenia que ver.
            c = ctypes.cast(datos, ctypes.POINTER(TiempoDeFrame))[0]
            if c.callback:
                self._reloj = ctypes.CFUNCTYPE(None, ctypes.c_int64)(c.callback)
                self._reloj_us = c.reference or 16667
            return True
        if orden in (ENV_SET_GEOMETRY, ENV_SET_SUPPORT_NO_GAME):
            return True
        return False

    def _leer_variables(self, datos):
        """Guarda que opciones ofrece el core y que valores admite cada una."""
        array = ctypes.cast(datos, ctypes.POINTER(Variable))
        i = 0
        while array[i].key:
            descripcion = (array[i].value or b"").decode("latin-1", "replace")
            titulo, _, valores = descripcion.partition(";")
            self.variables[array[i].key.decode()] = (titulo.strip(),
                                                     valores.strip().split("|"))
            i += 1

    def _log(self, nivel, formato, a1=None, a2=None, a3=None, a4=None):
        """El core registra con printf. Solo se rellenan los numeros: seguir un
        puntero de cadena que no sea el que espera el formato tumba el proceso,
        asi que los `%s` se dejan tal cual."""
        texto = (formato or b"").decode("latin-1", "replace").rstrip()
        argumentos = [a1, a2, a3, a4]
        def sustituir(encaje):
            tipo = encaje.group(1)
            if tipo == "%" or not argumentos:
                return encaje.group(0)
            valor = argumentos.pop(0)
            if tipo == "s":
                return _cadena_de(valor) or "?"
            if tipo in "diu":
                return str(ctypes.c_int(valor or 0).value)
            if tipo in "xX":
                return "%x" % (valor or 0)
            if tipo == "c":
                return chr((valor or 0) & 0x7F)
            return "?"
        texto = _ESPECIFICADOR.sub(sustituir, texto).rstrip()
        self.mensajes.append(texto)
        if self.traza:
            print("   [core] " + texto)

    def _video(self, datos, ancho, alto, paso):
        """Se guarda el frame tal cual y se descifra solo si alguien lo mira:
        convertir medio millon de pixeles por frame en Python no vale la pena."""
        self.frames += 1
        if not datos:
            return                                   # frame repetido
        self._crudo = (ctypes.string_at(datos, paso * alto), ancho, alto, paso)

    @property
    def frame(self):
        if self._crudo is None:
            return None
        if self._descifrado is None:
            self._descifrado = self._descifrar(*self._crudo)
        return self._descifrado

    def _descifrar(self, crudo, ancho, alto, paso):
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
        return (ancho, alto, pixeles)

    # --- el sonido que sale del chip -----------------------------------
    #
    # El core entrega muestras de 16 bits con signo, estereo entrelazado
    # (izquierda, derecha, izquierda...). Se guardan tal cual: lo que se oiria
    # por el altavoz, ya mezclado por el chip emulado.

    def _audio(self, izquierda, derecha):
        self.sonido.append(izquierda)
        self.sonido.append(derecha)

    def _audio_lote(self, datos, marcos):
        if datos and marcos:
            trozo = (ctypes.c_int16 * (marcos * 2)).from_address(datos)
            self.sonido.extend(trozo)
        return marcos

    def _estado(self, puerto, dispositivo, indice, boton):
        if dispositivo != DEVICE_JOYPAD:
            return 0
        return 1 if boton in self.pulsado.get(puerto, ()) else 0

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
        self.ritmo = int(round(av.timing.sample_rate))
        # sin esto, PUAE no conecta ningun mando al Amiga
        self.lib.retro_set_controller_port_device(0, DEVICE_JOYPAD)
        self.lib.retro_set_controller_port_device(1, DEVICE_JOYPAD)
        return av

    def pulsar(self, *nombres, **kwargs):
        """Deja pulsados esos botones y sueltos los demas. `puerto=1` es el
        mando del segundo jugador; sin decir nada se toca el del primero, y el
        otro se queda como estaba."""
        puerto = kwargs.pop("puerto", 0)
        if kwargs:
            raise TypeError("pulsar() no conoce %s" % ", ".join(kwargs))
        self.pulsado[puerto] = set(BOTON[n] for n in nombres)

    def reiniciar(self):
        """Como darle al boton de reset: la maquina arranca otra vez con la
        misma ROM cargada. Sirve para repetir la misma partida cambiando lo que
        se pulsa y comparar como acaba."""
        self.pulsado = {0: set(), 1: set()}
        self._descifrado = None
        self.frames = 0
        self.lib.retro_reset()

    def avanzar(self, cuantos=1):
        for _ in range(cuantos):
            self._descifrado = None
            if self._reloj is not None:
                self._reloj(self._reloj_us)
            self.lib.retro_run()

    def escuchar(self, cuantos=1):
        """Avanza `cuantos` frames y devuelve solo el sonido de esos frames."""
        del self.sonido[:]
        self.avanzar(cuantos)
        return self.sonido

    def cerrar(self):
        self.lib.retro_unload_game()
        self.lib.retro_deinit()


# --- lo que se mira en la imagen --------------------------------------

from imagen import (colores, distintos, filas_escritas, franja,  # noqa: E402,F401
                    guardar_png)
