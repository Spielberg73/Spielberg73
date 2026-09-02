"""Commodore Amiga 1200: el mismo Amiga, con el chipset AGA sacando pecho.

Es la misma maquina que `amiga` en todo lo que importa -bitplanes, blitter,
copper y Paula-, asi que hereda de ella y comparte el motor entero
(engine/amiga/). Lo que cambia son numeros, y con ellos lo que se ve:

  bitplanes   8 en vez de 5, o sea **256 colores** a la vez en vez de 32
  paleta      **8 bits por canal** en vez de 4: 16,7 millones en vez de 4096.
              Ahi no hay redondeo: el color que dibujas es el que sale
  parallax    el doble plano parte los ocho bitplanes en 4+4, o sea **16
              colores por plano** en vez de los 7+7 del OCS
  CPU         68EC020 a 14 MHz: el doble de reloj y multiplicaciones de 32
              bits de verdad, asi que se compila con -m68020
  RAM chip    2 MB de serie, que es lo que permite los dibujos al doble de
              tamano (8 bitplanes por dibujo en vez de 5)

Ocho bitplanes en baja resolucion no caben en la DMA de siempre: hacen falta
las lecturas de 32 bits del AGA (el registro FMODE). Eso, y como se escriben
256 colores en un registro de 12 bits, esta en engine/amiga/np_video.c.

El disquete es el mismo formato de siempre y arranca solo, pero **solo en una
maquina AGA** (A1200, A4000, CD32): en un A500 los ocho bitplanes no existen.
Por eso es un sistema aparte y no una opcion de `amiga`.
"""

from __future__ import annotations

from .. import gfx_amiga
from .amiga import Amiga, MAX_TILES
from .base import Limites, registrar


class Amiga1200(Amiga):
    nombre = "amiga1200"
    titulo = "Commodore Amiga 1200 (AGA)"
    cpu = "68EC020 a 14 MHz"
    limites = Limites(colores_por_paleta=16, paletas=1, sprites=0,
                      tiles=MAX_TILES,
                      colores_en_pantalla=gfx_amiga.COLORES_AGA)

    aga = True
    planos_llenos = gfx_amiga.PLANOS_AGA       # 8 bitplanes
    planos_doble = 4                           # 4 + 4 en doble plano
    colores_totales = gfx_amiga.COLORES_AGA    # 256
    hud_lleno = gfx_amiga.COLORES_AGA - 1      # 255
    hud_doble = 15                             # el ultimo del plano de delante
    por_plano = 16                             # colores de cada plano en doble
    cpu_gcc = "-m68020"

    notas = [
        "colores:  'amiga: 256colores' da 255 colores y ningun parallax;",
        "          'amiga: 16colores' parte los bitplanes en dos planos de 16",
        "          y 16 colores, y ahi si hay una capa de parallax por hardware",
        "paleta:   8 bits por canal: los colores salen exactos, sin redondear",
        "sonido:   Paula, cuatro canales; toca muestras digitales",
        "ojo:      el disquete pide una maquina AGA (A1200, A4000 o CD32)",
    ]

    # --- colores -------------------------------------------------------
    #
    # Aqui no hay conversion que valga: el AGA guarda ocho bits por canal, que
    # es exactamente lo que trae un PNG. `color_visible` -lo que el preview
    # ensena- es la identidad, y por eso el editor no avisa nunca de colores
    # aproximados en esta maquina.

    def color(self, rgb):
        return gfx_amiga.aga_color(rgb)

    def color_visible(self, rgb):
        return tuple(rgb)


registrar(Amiga1200())
