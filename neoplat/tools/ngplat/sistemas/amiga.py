"""Commodore Amiga (OCS/ECS, un A500 basta): 68000 a 7 MHz, blitter y Paula.

Es la mas distinta de las tres maquinas. No tiene tiles ni un plano de fondo
con scroll por celdas: tiene un **mapa de bits** que se puede mover entero por
hardware y un **blitter** que copia trozos de memoria a toda velocidad. Asi que
aqui:

  - todos los dibujos del juego se guardan entrelazados en 5 bitplanes, con su
    mascara al lado para poder recortarlos sobre el fondo
  - las paletas del proyecto se funden en **una sola de 32 colores**, que es lo
    que muestra el Amiga de una vez (el ultimo se reserva para el marcador)
  - el sonido sale por Paula con una onda cuadrada de dos bytes a la que se le
    cambia el periodo: las mismas notas que en las otras dos maquinas
  - el resultado no es un cartucho sino un **disquete arrancable** (.adf): el
    ejecutable lo hace hunk.py a partir del ELF del enlazador y adf.py lo mete
    en un disco de 880 KB con su bootblock y su sistema de ficheros
"""

from __future__ import annotations

import os
from typing import Dict, List

from .. import gfx, gfx_amiga
from ..build import Build
from ..errors import ProjectError
from ..paths import fuente_del_kit
from ..sonido import PAULA_CLOCK, periodo_paula, tabla_de_muestras_c
from .base import Limites, Salida, Sistema, registrar

# El mapa de bits del escenario ocupa lo mismo pase lo que pase (22 KB por
# plano); lo que cambia es su forma, y con ella lo que se puede hacer:
#
#   ancha  704x256  44 casillas x 16. Es una ventana: cabe el doble de pantalla
#                   a lo ancho y se va dibujando la columna que entra por el
#                   borde, asi que el nivel puede ser todo lo largo que quieras.
#   alta   352x512  22 x 32. Aqui no hay ventana que valga -sobrarian dos
#                   casillas- asi que el nivel tiene que caber entero de ancho.
#                   A cambio se puede subir el doble.
#
# La eleccion no se pregunta: la decide el nivel mas alto del juego.
VENTANA_ANCHA = (704, 256)
VENTANA_ALTA = (352, 512)
ALTO_MAX_TILES = VENTANA_ANCHA[1] // gfx_amiga.TILE_PX      # 16 casillas
ALTO_MAX_TILES_ALTA = VENTANA_ALTA[1] // gfx_amiga.TILE_PX  # 32
ANCHO_MAX_TILES_ALTA = VENTANA_ALTA[0] // gfx_amiga.TILE_PX # 22
COLOR_HUD = 31                              # el ultimo color, reservado
MAX_COLORES_JUEGO = COLOR_HUD               # los otros 31 son del juego

# En doble plano (8 colores) los seis bitplanes se parten en dos planos de tres:
# el juego delante con los colores 0-7 y el parallax detras con los 8-15.
COLOR_HUD_DOBLE = 7
COLORES_POR_PLANO = 8
ANCHO_PARALLAX = VENTANA_ANCHA[0] - 320     # lo que el plano de atras puede correr
MAX_TILES = 1024                            # 160 KB de dibujos: de sobra en chip


class Amiga(Sistema):
    nombre = "amiga"
    toca_muestras = True          # Paula las lee de la RAM chip por DMA
    titulo = "Commodore Amiga (OCS/ECS)"
    cpu = "68000 a 7 MHz"
    pantalla = (320, 224)
    limites = Limites(colores_por_paleta=16, paletas=1, sprites=0,
                      tiles=MAX_TILES, colores_en_pantalla=gfx_amiga.COLORES)

    # Lo que cambia entre el OCS y el AGA del A1200 son numeros, no codigo: el
    # A1200 hereda de esta clase y solo pisa esto (ver amiga1200.py).
    aga = False
    planos_llenos = gfx_amiga.PLANOS       # bitplanes en el modo de un plano
    planos_doble = 3                       # y en doble plano, por cada uno
    colores_totales = gfx_amiga.COLORES    # 1 << planos_llenos
    hud_lleno = COLOR_HUD                  # el color reservado al marcador
    hud_doble = COLOR_HUD_DOBLE
    por_plano = COLORES_POR_PLANO          # colores de cada plano en doble
    cpu_gcc = "-m68000"
    archivos_motor = [
        ("include/np_types.h", "src/np_types.h"),
        ("include/np_game.h", "src/np_game.h"),
        ("include/np_world.h", "src/np_world.h"),
        ("include/np_sonido.h", "src/np_sonido.h"),
        ("core/np_world.c", "src/np_world.c"),
        ("core/np_aritmetica.c", "src/np_aritmetica.c"),
        ("amiga/np_amiga.h", "src/np_amiga.h"),
        ("amiga/np_video.c", "src/np_video.c"),
        ("amiga/np_hud.c", "src/np_hud.c"),
        ("amiga/np_sound.c", "src/np_sound.c"),
        ("amiga/main.c", "src/main.c"),
        ("amiga/arranque.c", "src/arranque.c"),
        ("amiga/amiga.ld", "amiga.ld"),
    ]
    extension_ejecutable = ""
    carpeta_salida = "disco"       # una carpeta que se copia tal cual al disquete
    nombre_binario = "el disquete"
    notas = [
        "colores:  'amiga: 32colores' da 31 colores y ningun parallax;",
        "          'amiga: 8colores' parte los bitplanes en dos planos de 7 y 7",
        "          colores, y ahi si hay una capa de parallax por hardware",
        "sonido:   Paula, cuatro canales; toca muestras digitales",
    ]

    # --- colores -------------------------------------------------------

    def color(self, rgb):
        return gfx_amiga.amiga_color(rgb)

    def color_visible(self, rgb):
        return gfx_amiga.amiga_color_a_rgb(gfx_amiga.amiga_color(rgb))

    # --- empaquetado ---------------------------------------------------

    def preparar(self, build: Build) -> None:
        build.sistema = self
        doble = build.project.amiga_modo == "8colores"
        planos = self.planos_doble if doble else self.planos_llenos
        color_hud = self.hud_doble if doble else self.hud_lleno
        banco = gfx_amiga.BancoAmiga(planos=planos)

        # 1) las paletas. Con 32 colores caben todas juntas; en doble plano el
        #    juego se queda con siete y el parallax con otros siete, porque cada
        #    plano solo tiene tres bitplanes. Ahi no hay dibujo que quepa tal
        #    cual, asi que los colores que sobran se acercan al mas parecido.
        paletas = [build.tileset.palette]
        paletas += [a.sheet.palette for a in build.actor_builds()]
        pesos = _pesos([(build.tileset.palette, build.tileset.tiles)]
                       + [(a.sheet.palette, a.sheet.tiles) for a in build.actor_builds()])
        unica = gfx_amiga.fusionar_paletas(paletas, tope=color_hud, pesos=pesos,
                                           aproximar=doble)

        def remapear(tile, nombre, mapa=None):
            mapa = mapa if mapa is not None else unica.asignacion[nombre]
            return [mapa.get(v, 0) for v in tile]

        # 2) los dibujos, ya entrelazados y con su mascara
        #    (sin compartir: el motor cuenta con que van seguidos)
        build.tileset.first_tile = banco.cuantos
        for tile in build.tileset.tiles:
            banco.anadir(remapear(tile, build.tileset.palette.name), compartir=False)
        build.tileset.palette_index = 0

        for actor in build.actor_builds():
            actor.sheet.first_tile = banco.cuantos
            for tile in actor.sheet.tiles:
                banco.anadir(remapear(tile, actor.sheet.palette.name), compartir=False)
            actor.sheet.palette_index = 0

        # 3) las capas de parallax: solo se dibujan en doble plano, y con su
        #    propia paleta de siete colores (los registros 9 a 15).
        colores_fondo = []
        perdidos_fondo = 0
        if doble and build.layers:
            pesos_fondo = _pesos([(c.palette, [c.dibujos[i] for i in c.tiles])
                                  for c in build.layers])
            fondo = gfx_amiga.fusionar_paletas(
                [c.palette for c in build.layers], tope=self.por_plano,
                pesos=pesos_fondo, aproximar=True)
            perdidos_fondo = fondo.perdidos
            colores_fondo = fondo.palabras_de(self.color, self.por_plano)
            for capa in build.layers:
                mapa = fondo.asignacion[capa.palette.name]
                nuevos = [banco.anadir(remapear(d, capa.palette.name, mapa))
                          for d in capa.dibujos]
                capa.tiles = [nuevos[i] for i in capa.tiles]
                capa.palette_index = 0
                capa.dibujos = []
        else:
            for capa in build.layers:
                capa.tiles = [0] * len(capa.tiles)
                capa.palette_index = 0
                capa.dibujos = []

        if banco.cuantos > MAX_TILES:
            raise ProjectError(
                "los graficos ocupan %d dibujos de 16x16 y el limite del Amiga "
                "en NeoPlat son %d" % (banco.cuantos, MAX_TILES),
                hint="usa menos dibujos distintos o capas de fondo mas pequenas",
            )

        # 4) la fuente del marcador: 8x8 en un solo bit por pixel
        fuente: Dict[str, int] = {}
        glifos = [[0] * 8]                       # el 0 es el hueco en blanco
        for i, char in enumerate(gfx.FONT_CHARS):
            glifos.append(_glifo_1bpp(gfx.font_glyph_pixels(char)))
            fuente[char] = i + 1

        colores = unica.palabras_de(self.color, self.colores_totales)
        colores[color_hud] = self.color((255, 255, 255))
        if doble:
            # la mitad de arriba de la paleta es el plano de atras
            for i in range(self.por_plano):
                colores[self.por_plano + i] = (colores_fondo[i]
                                               if i < len(colores_fondo) else 0)

        # el color de fondo de cada nivel, en el formato de esta maquina
        for nivel in build.levels:
            nivel.background = self.color(nivel.background_rgb)

        build.font = fuente
        build.hud_palette = 0
        # np_palettes no lo usa esta maquina -sus colores van en graficos.c- pero
        # gamedata.c lo emite igual y es de 16 bits, asi que aqui va la paleta
        # redondeada al formato del OCS. En AGA el bueno es el de graficos.c.
        ocs = unica.palabras_de(gfx_amiga.amiga_color, self.colores_totales)
        build.paletas = [ocs[i:i + 16] for i in range(0, self.colores_totales, 16)]
        build.tile_gfx = [build.tileset.first_tile + t.index for t in build.tiles]
        # La forma del mapa de bits: la decide el nivel mas alto del juego. Un
        # juego de los de siempre no se entera; uno que se sube se lleva el
        # mapa estrecho y alto sin tener que pedirlo.
        alto_max = max([n.height for n in build.levels] or [0])
        ventana = VENTANA_ALTA if alto_max > ALTO_MAX_TILES else VENTANA_ANCHA

        build.info = {
            "banco": banco,
            "glifos": glifos,
            "colores": colores,
            "ventana": ventana,
            "stats": {
                "dibujos_16x16": banco.cuantos,
                "bytes_dibujos": len(banco.tiles),
                "bytes_mascaras": len(banco.mascaras),
                "colores": len(unica.colores),
                "aproximados": unica.perdidos + perdidos_fondo,
            },
            "doble": doble,
            "cabecera": [
                "#define NP_TILE_COUNT %d" % banco.cuantos,
                "#define NP_FONT_COUNT %d" % len(glifos),
                "#define NP_PLANOS %d" % planos,
                "#define NP_AGA %d" % (1 if self.aga else 0),
                "#define NP_MAPA_ANCHO %d" % ventana[0],
                "#define NP_MAPA_ALTO %d" % ventana[1],
            ],
        }

    def comprobar(self, build: Build) -> List[str]:
        avisos: List[str] = []
        if build.info.get("stats", {}).get("aproximados"):
            avisos.append(
                "con 'amiga: 8colores' solo hay siete colores por plano: %d colores "
                "de tus dibujos se han cambiado por el mas parecido de los que "
                "caben. Si quieres mandar tu en los colores, dibuja con siete"
                % build.info["stats"]["aproximados"])
        ancho_px, alto_px = build.info.get("ventana", VENTANA_ANCHA)
        alto_tiles = alto_px // gfx_amiga.TILE_PX
        ancho_tiles = ancho_px // gfx_amiga.TILE_PX
        alta = (ancho_px, alto_px) == VENTANA_ALTA
        for nivel in build.levels:
            if nivel.height > alto_tiles:
                self.error(
                    "el nivel '%s' tiene %d casillas de alto y en el Amiga el mapa "
                    "de bits llega a %d" % (nivel.name, nivel.height, alto_tiles),
                    "haz los niveles mas bajos y mas largos",
                )
            # Con el mapa de bits alto no hay ventana: el nivel entero tiene
            # que caber de ancho. Es el precio de poder subir 32 casillas, y
            # merece la pena decirlo con esas palabras.
            if alta and nivel.width > ancho_tiles:
                self.error(
                    "el nivel '%s' mide %d x %d casillas: en el Amiga, un juego con "
                    "niveles de mas de %d casillas de alto se lleva el mapa de bits "
                    "estrecho, y ahi el nivel no puede pasar de %d de ancho"
                    % (nivel.name, nivel.width, nivel.height, ALTO_MAX_TILES,
                       ancho_tiles),
                    "o estrechas el nivel, o lo bajas a %d casillas de alto y "
                    "vuelve a haber ancho de sobra" % ALTO_MAX_TILES,
                )
        for nivel in build.levels:
            if nivel.layers and not build.info.get("doble"):
                avisos.append(
                    "con 'amiga: %dcolores' no se dibujan las capas de parallax: el "
                    "fondo de '%s' se vera del color de fondo. Con 'amiga: %dcolores' "
                    "si se dibujan, a cambio de bajar a %d colores por plano"
                    % (self.colores_totales, nivel.name, self.por_plano,
                       self.por_plano - 1))
                break
            if len(nivel.layers) > 1 and build.info.get("doble"):
                avisos.append(
                    "el Amiga solo tiene sitio para una capa de parallax: en '%s' se "
                    "usara la primera" % nivel.name)
                break
        if build.info.get("doble"):
            for capa in build.layers:
                margen = ancho_px - 320
                if capa.cols * gfx_amiga.TILE_PX > margen:
                    avisos.append(
                        "la capa '%s' mide %d pixeles de ancho y el plano de atras "
                        "solo puede correr %d antes de tener que volver al "
                        "principio: se parara en el borde"
                        % (capa.name, capa.cols * gfx_amiga.TILE_PX, margen))
                    break
        return avisos

    # --- generacion ----------------------------------------------------

    def generar(self, build: Build, rom_id: str) -> Salida:
        salida = Salida()
        banco: gfx_amiga.BancoAmiga = build.info["banco"]

        salida.archivos["src/graficos.c"] = _graficos_c(build, banco)
        salida.archivos["src/sonido.c"] = _sonido_c(build)
        nombre = _nombre_ejecutable(build)
        salida.archivos["Makefile"] = _makefile(build, nombre,
                                                _etiqueta_disco(build.project.title),
                                                self.cpu_gcc)
        salida.archivos["hacer_ejecutable.py"] = fuente_del_kit("hunk.py")
        salida.archivos["hacer_adf.py"] = fuente_del_kit("adf.py")
        salida.resumen.append(
            "graficos: %d dibujos de 16x16 (%d KB de dibujos y %d KB de mascaras)"
            % (banco.cuantos, len(banco.tiles) // 1024, len(banco.mascaras) // 1024))
        if build.info["doble"]:
            plantilla = ("colores:  %%d por plano de los %d del doble plano "
                         "(el %d es el del marcador)"
                         % (self.por_plano, self.hud_doble))
        else:
            plantilla = ("colores:  %%d de los %d de esta maquina "
                         "(el %d es el del marcador)"
                         % (self.colores_totales, self.hud_lleno))
        salida.resumen.append(plantilla % build.info["stats"]["colores"])
        if build.pcm_bytes:
            salida.resumen.append(
                "muestras: %d efectos digitales a %d Hz (%d KB en RAM chip)"
                % (sum(1 for e in build.project.sound.efectos.values() if e.digital),
                   PCM_RITMO, (build.pcm_bytes + 1023) // 1024))
        salida.resumen.append(
            "disquete: disco/%s.adf (880 KB, arranca solo en %s)"
            % (nombre, "un Amiga con AGA: A1200, A4000 o CD32" if self.aga
               else "cualquier Amiga"))
        return salida


def _nombre_ejecutable(build: Build) -> str:
    """El titulo del juego, hecho un nombre de archivo de AmigaDOS."""
    trozos = [t for t in "".join(
        c if c.isalnum() else " " for c in build.project.title).split() if t]
    nombre = "".join(t[:1].upper() + t[1:].lower() for t in trozos)
    return nombre or "Juego"


def _pesos(partes) -> Dict[tuple, int]:
    """Cuenta cuantos pixeles usa cada color, para saber cuales merece la pena
    conservar cuando hay que bajar de colores."""
    pesos: Dict[tuple, int] = {}
    for paleta, dibujos in partes:
        for dibujo in dibujos:
            for v in dibujo:
                if v:
                    color = paleta.colors[v - 1]
                    pesos[color] = pesos.get(color, 0) + 1
    return pesos


def _glifo_1bpp(pixeles) -> List[int]:
    """8x8 indices de paleta -> ocho bytes, un bit por pixel."""
    filas = []
    for y in range(8):
        bits = 0
        for x in range(8):
            if pixeles[y * 8 + x]:
                bits |= 1 << (7 - x)
        filas.append(bits)
    return filas


def _c_bytes(datos, por_linea=16) -> str:
    lineas = []
    for i in range(0, len(datos), por_linea):
        trozo = datos[i:i + por_linea]
        lineas.append("    " + ", ".join("0x%02x" % b for b in trozo) + ",")
    return "\n".join(lineas)


def _graficos_c(build: Build, banco: gfx_amiga.BancoAmiga) -> str:
    colores = build.info["colores"]
    glifos = []
    for filas in build.info["glifos"]:
        glifos.extend(filas)
    partes = [
        "/* Archivo generado por ngplat: los dibujos, ya en bitplanes del Amiga. */",
        '#include "np_amiga.h"',
        "",
        "/* El mapa de bits y la franja del marcador. Estan sin inicializar a",
        " * proposito: asi van al hunk de BSS, que AmigaDOS reserva en RAM chip",
        " * y entrega puesto a cero.",
        " * Alineados a cuatro: el blitter y los punteros de bitplane no saben",
        " * leer de una direccion impar. */",
        "uint8_t np_bitmap[NP_MAPA_ALTO * NP_PASO_FILA] __attribute__((aligned(4)));",
        "uint8_t np_hud_bitmap[NP_HUD_ALTO * NP_HUD_PASO] __attribute__((aligned(4)));",
        "#if NP_DOBLE_PLANO",
        "/* El plano de atras, donde va el parallax: mismo tamano que el del",
        " * juego, con su propio scroll por hardware. */",
        "uint8_t np_fondo_bitmap[NP_MAPA_ALTO * NP_PASO_FILA]",
        "    __attribute__((aligned(4)));",
        "#endif",
        "",
        "/* Cada dibujo son 16 filas x %d bitplanes x 2 bytes = %d bytes."
        % (banco.planos, banco.bytes_por_tile),
        " * Las dos palabras de mas del final son para el blitter: al desplazar un",
        " * dibujo lee una palabra por detras de la ultima fila.",
        " * Y el `aligned(4)`: el blitter no sabe leer de una direccion impar, y",
        " * el enlazador coloca los arrays de bytes donde le cabe. */",
        "const uint8_t np_tile_data[NP_TILE_COUNT * %d + 4] __attribute__((aligned(4))) = {"
        % banco.bytes_por_tile,
        _c_bytes(bytes(banco.tiles)),
        "};",
        "",
        "/* Y su mascara: un bit por pixel, 1 donde el dibujo tapa el fondo,",
        " * repetida para cada bitplane. */",
        "const uint8_t np_tile_mask[NP_TILE_COUNT * %d + 4] __attribute__((aligned(4))) = {"
        % banco.bytes_por_tile,
        _c_bytes(bytes(banco.mascaras)),
        "};",
        "",
    ] + _colores_c(build, colores) + [
        "",
        "/* Fuente del marcador: ocho bytes por caracter. */",
        "const uint8_t np_font_data[NP_FONT_COUNT * 8] = {",
        _c_bytes(glifos, por_linea=8),
        "};",
        "",
    ]
    return "\n".join(partes)


def _colores_c(build: Build, colores: List[int]) -> List[str]:
    """La paleta, en el formato que lee el copper de cada chipset.

    El OCS guarda cada color en una palabra de 4+4+4 bits. El AGA los guarda de
    24 bits y los escribe en dos veces (los cuatro bits altos de cada canal y
    luego los bajos), asi que aqui van tal cual y es np_video.c quien los parte.
    """
    if not build.sistema.aga:
        return [
            "/* Los 32 colores de la pantalla, en formato del Amiga (4 bits por canal). */",
            "const uint16_t np_colores[32] = {",
            "    " + ", ".join("0x%04x" % c for c in colores[:16]) + ",",
            "    " + ", ".join("0x%04x" % c for c in colores[16:32]) + ",",
            "};",
        ]
    lineas = [
        "/* Los 256 colores del AGA, de 24 bits: 0x00RRGGBB. Aqui no hay",
        " * redondeo ninguno, el color que dibujaste es el que sale. */",
        "const uint32_t np_colores[NP_COLORES] = {",
    ]
    for i in range(0, len(colores), 8):
        lineas.append("    " + ", ".join("0x%06x" % c for c in colores[i:i + 8]) + ",")
    lineas.append("};")
    return lineas


def _secuencia_c(nombre: str, pasos) -> List[str]:
    lineas = ["static const NpSndPaso %s[] = {" % nombre]
    for paso in pasos:
        duracion = max(1, int(paso.duracion))
        volumen = (paso.volumen & 0x0F) | (0x80 if paso.ruido else 0)
        # una onda cuadrada de dos bytes: periodo = reloj / (2 * hercios)
        periodo = periodo_paula(paso.frecuencia, muestras=2)
        while duracion > 0:
            trozo = min(255, duracion)
            lineas.append("    { %d, %d, 0x%02x }," % (periodo, trozo, volumen))
            duracion -= trozo
    lineas.append("    { 0, 0, 0 }")
    lineas.append("};")
    return lineas


# Las muestras digitales van en RAM chip (que es donde se carga el ejecutable
# entero) y Paula las lee por DMA. 11025 Hz es el punto medio razonable: se
# oyen bien y no se comen el disquete.
PCM_RITMO = 11025
PCM_MAXIMO = 48 * 1024        # por efecto; el aviso salta mucho antes


def _sonido_c(build: Build) -> str:
    from ..sonido import EVENTOS
    sonido = build.project.sound
    efectos = [n for n in EVENTOS if n in sonido.efectos]
    partes = [
        "/* Archivo generado por ngplat: la musica y los efectos, ya en periodos",
        " * de Paula (Amiga). */",
        '#include "np_sonido.h"',
        "",
    ]
    for i, nombre in enumerate(efectos):
        partes.extend(_secuencia_c("np_sfx%d" % i, sonido.efectos[nombre].pasos))
        partes.append("")
    for i, nombre in enumerate(build.music_order):
        tema = sonido.musica[nombre]
        for p in range(2):
            pista = tema.pistas[p] if p < len(tema.pistas) else []
            partes.extend(_secuencia_c("np_mus%d_%d" % (i, p), pista))
        partes.append("")

    partes.append("const NpSndPaso *const np_snd_efectos[] = {")
    partes.append("    " + (", ".join("np_sfx%d" % i for i in range(len(efectos)))
                            if efectos else "0"))
    partes.append("};")
    partes.append("const NpSndPaso *const np_snd_musica[] = {")
    if build.music_order:
        entradas = []
        for i in range(len(build.music_order)):
            entradas.append("np_mus%d_0" % i)
            entradas.append("np_mus%d_1" % i)
        partes.append("    " + ", ".join(entradas))
    else:
        partes.append("    0, 0")
    partes.append("};")
    partes.append("const uint16_t np_snd_efecto_count = %d;" % len(efectos))
    partes.append("const uint16_t np_snd_musica_count = %d;" % len(build.music_order))
    partes.append("")
    lineas, bytes_pcm = tabla_de_muestras_c(
        [sonido.efectos[n] for n in efectos], PCM_RITMO, 50,
        lambda ritmo: int(round(PAULA_CLOCK / float(ritmo))),
        maximo=PCM_MAXIMO, par=True)
    partes.extend(lineas)
    build.pcm_bytes = bytes_pcm
    partes.append("")
    return "\n".join(partes)


def _makefile(build: Build, nombre: str, etiqueta: str, cpu: str = "-m68000") -> str:
    return """# Makefile generado por ngplat para "%s" (Amiga).
# Se reescribe en cada `ngplat compilar`: pon tus cambios en game.yaml.
#
# Necesita un compilador de 68000. Vale cualquiera de estos:
#   m68k-amigaos-gcc      (el del bebbo/amiga-gcc, si lo tienes)
#   m68k-elf-gcc
#   m68k-linux-gnu-gcc    (el paquete gcc-m68k-linux-gnu de Debian/Ubuntu)
#
# El enlazador saca un ELF; hacer_ejecutable.py lo convierte en un ejecutable de
# AmigaDOS de verdad (hunks + tabla de relocalizacion, todo en RAM chip) y
# hacer_adf.py monta con el un disquete de 880 KB que arranca solo.

# make trae su propio CC por defecto, asi que solo se cambia si nadie lo ha puesto
ifeq ($(origin CC), default)
CC := $(shell which m68k-elf-gcc 2>/dev/null || which m68k-linux-gnu-gcc 2>/dev/null)
endif
ifeq ($(CC),)
$(error no encuentro un compilador de 68000: instala gcc-m68k-linux-gnu o m68k-elf-gcc)
endif
PYTHON ?= python3

# -fno-store-merging: sin el, gcc junta dos escrituras de un byte seguidas en
# una sola de dos bytes, y si cae en una direccion impar el 68000 se para con
# un "address error". Las pruebas del kit comprueban que no quede ninguna.
CFLAGS  := %s -Os -fomit-frame-pointer -fno-builtin -ffreestanding \\
           -fno-store-merging -std=c99 -Wall -Wextra -Isrc
# -nodefaultlibs: la libgcc de un compilador de 68k para Linux esta hecha para
# 68020 y lleva instrucciones que el 68000 no tiene; las rutinas de multiplicar
# y dividir las pone src/np_aritmetica.c.
LDFLAGS := -nostdlib -nodefaultlibs -T amiga.ld -Wl,--emit-relocs -Wl,--build-id=none

SRC := src/arranque.c src/main.c src/np_video.c src/np_hud.c src/np_sound.c \\
       src/np_world.c src/np_aritmetica.c src/gamedata.c src/graficos.c \\
       src/sonido.c
OBJ := $(SRC:.c=.o)
JUEGO := disco/%s
ADF   := disco/%s.adf
DISCO := "%s"

all: $(ADF)
	@echo "disquete listo: $(ADF)"

%%.o: %%.c
	$(CC) $(CFLAGS) -c $< -o $@

juego.elf: $(OBJ)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(OBJ)

$(JUEGO): juego.elf
	@mkdir -p disco
	$(PYTHON) hacer_ejecutable.py $< $@

# El .adf es la copia de un disquete: se mete en el emulador (o en un Gotek, o
# en un Amiga de verdad con ADF Blitz) y arranca solo, sin Workbench.
$(ADF): $(JUEGO) hacer_adf.py
	$(PYTHON) hacer_adf.py $@ $(DISCO) %s $(JUEGO)

# Con un emulador instalado, `make run` mete el disquete y enciende el Amiga.
EMU ?= fs-uae
run: all
	$(EMU) --floppy_drive_0=$(ADF)

clean:
	rm -f $(OBJ) juego.elf $(JUEGO) $(ADF)

.PHONY: all run clean
""" % (build.project.title, cpu, nombre, nombre, etiqueta, nombre)


def _etiqueta_disco(titulo: str) -> str:
    """Nombre del volumen: AmigaDOS no admite ':' ni '/' y se queda en 30 letras."""
    limpio = "".join(c if (c.isalnum() or c in " -_") else " " for c in titulo)
    return " ".join(limpio.split())[:30].upper() or "NEOPLAT"


registrar(Amiga())
