"""Monta el emulador de cada maquina con la misma cara, para las pruebas.

Las cinco maquinas se arrancan de forma distinta (un cartucho es inmediato, un
disquete tarda lo que tarde el sistema, la Neo Geo no usa libretro sino el banco
del propio kit), pero una vez arrancadas todas se manejan igual. Aqui esta esa
parte comun, que usan `dos_jugadores.py` y `muestras.py`.

    emu, empezar, esperar = montar("amiga", "juego.adf")
    esperar(emu)                 # llegar a la pantalla de titulo
    emu.pulsar(empezar)          # empezar la partida
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from libretro import Emulador, buscar_core  # noqa: E402

# la variable de entorno con la que se puede apuntar a cada core a mano
VARIABLE = {"megadrive": "NEOPLAT_CORE_MD", "amiga": "NEOPLAT_CORE_AMIGA",
            "jaguar": "NEOPLAT_CORE_JAGUAR", "atarist": "NEOPLAT_CORE_ST"}

MAQUINAS = ("neogeo", "megadrive", "amiga", "jaguar", "atarist")


class _BancoNeoGeo:
    """Le pone al banco de la Neo Geo la misma cara que un core de libretro.

    La placa no tiene boton de reset, asi que reiniciar es montarla otra vez
    desde las mismas ROMs."""

    def __init__(self, carpeta):
        import maquina_neogeo
        self._ng = maquina_neogeo
        self.carpeta = carpeta
        self.maquina = None
        self.reiniciar()

    def reiniciar(self):
        self.maquina = self._ng.cargar(self.carpeta, sonido=False)
        if self.maquina is None:
            raise RuntimeError("el banco no ha podido montar la ROM")

    def avanzar(self, cuantos=1):
        self.maquina.avanzar(cuantos)

    def pulsar(self, *nombres, **kwargs):
        self.maquina.pulsar(*nombres, **kwargs)

    @property
    def frame(self):
        return self.maquina.dibujar()


def montar(sistema, ruta):
    """Devuelve (emulador, boton de start, como esperar al titulo)."""
    if sistema == "neogeo":
        return _BancoNeoGeo(ruta), "START", lambda emu: emu.avanzar(15)

    if sistema == "megadrive":
        import emulador_md as maq
        opciones, empezar, esperar = {}, "START", None
    elif sistema == "amiga":
        import emulador_amiga as maq
        opciones = {"puae_kickstart": "aros", "puae_model": "A500",
                    "puae_video_standard": "PAL"}
        empezar, esperar = "A", None
    elif sistema == "jaguar":
        import emulador_jaguar as maq
        opciones, empezar, esperar = {}, maq.EMPEZAR, None
    elif sistema == "atarist":
        import emulador_st as maq
        opciones = dict(maq.OPCIONES)
        # el segundo joystick del ST no se conecta solo: hay que pedirlo
        opciones["hatari_twojoy"] = "true"
        opciones["hatari_tosimage"] = "tos.img"
        empezar = "B"
        def esperar(emu):
            if not maq._esperar_al_juego(emu):
                raise RuntimeError("el disquete no arranca")
    else:
        raise ValueError("no conozco la maquina %r" % sistema)

    core = buscar_core(maq.CORE, VARIABLE[sistema])
    if not core:
        return (None, "", None)
    sistema_dir = tempfile.mkdtemp(prefix="neoplat-emu-")
    if sistema == "atarist":
        tos = maq._buscar_tos()
        if not tos:
            return (None, "", None)
        os.makedirs(os.path.join(sistema_dir, "hatari", "tos"))
        shutil.copyfile(tos, os.path.join(sistema_dir, "tos.img"))
        shutil.copyfile(tos, os.path.join(sistema_dir, "hatari", "tos", "tos.img"))
    emu = Emulador(core, sistema=sistema_dir, opciones=opciones)
    emu.cargar(ruta)
    if sistema == "amiga":
        esperar = lambda emu: emu.avanzar(maq.SEGUNDOS_DE_ARRANQUE * maq.FPS)
    return emu, empezar, esperar
