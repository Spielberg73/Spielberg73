"""Media Neo Geo hecha en casa: el 68000 de verdad y el chip de video a mano.

Por que existe esto
-------------------
Los emuladores de Neo Geo necesitan la BIOS de SNK, que no se puede
distribuir. Sin ella no habia forma de comprobar que `np_video.c` programa
bien el hardware: las otras dos maquinas se arrancan en un emulador de
verdad y la Neo Geo se quedaba sin probar.

Aqui se juntan dos piezas:

  * el 68000 lo ejecuta Musashi (el mismo nucleo que usa MAME), a traves de
    `machine68k`, que viene con amitools;
  * el chip de video (el LSPC) esta escrito en este fichero: se queda con lo
    que el juego escribe en la VRAM y luego reconstruye la imagen a partir de
    los tiles de las ROMs C1/C2 y S1 y de las paletas.

No es un emulador de Neo Geo. No hay Z80, ni YM2610, ni zoom de sprites, ni
BIOS: el juego entra directo en `main()`. Lo que si comprueba, y no comprobaba
nada hasta ahora, es que la lista de sprites y el plano fix que deja el motor
en la VRAM dibujan el juego que se espera.

Lo que aqui se da por supuesto y no se ha podido contrastar con hardware:
  * el sprite 0 es el que va delante (los siguientes quedan detras);
  * la fila 0 del plano fix cae en la linea 0 de la pantalla.
Son las dos mismas suposiciones que hace el motor, asi que este banco de
pruebas no puede desmentirlas: solo un MVS o MAME con BIOS puede.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))

from imagen import colores, distintos, franja, guardar_png  # noqa: E402,F401

ANCHO, ALTO = 320, 224

# --- mapa de memoria de la placa ---------------------------------------
P1CNT = 0x300000        # mando del jugador 1 (activo a nivel bajo)
STATUS_B = 0x380000     # start y select (tambien a nivel bajo)
VRAMADDR = 0x3C0000
VRAMRW = 0x3C0002
VRAMMOD = 0x3C0004
LSPCMODE = 0x3C0006     # bits 15..7: linea que se esta pintando
PALETA = 0x400000
BACKDROP = 0x401FFE
TOPE_RAM_KIB = 4352     # llega hasta 0x440000: cubre la RAM de color

# --- mapa de la VRAM (el mismo que usa np_video.h) ---------------------
SCB1 = 0x0000           # tilemap de cada sprite: 64 words
FIXMAP = 0x7000         # plano fix: 0x7000 + columna*32 + fila
SCB2 = 0x8000           # zoom
SCB3 = 0x8200           # posicion Y, encadenado y altura
SCB4 = 0x8400           # posicion X
SPRITES = 381

VBLANK = 0xF0 << 7      # valor de LSPCMODE mientras dura el retrazo
CICLOS_FRAME = 200000   # 12 MHz / 60 Hz, para medir cuanto cuesta un frame
TROZO = 2000            # ciclos por tanda al buscar cuando el juego espera

BOTON = {"UP": 0x01, "DOWN": 0x02, "LEFT": 0x04, "RIGHT": 0x08,
         "A": 0x10, "B": 0x20, "C": 0x40, "D": 0x80}
SISTEMA = {"START": 0x01, "SELECT": 0x02}


def _color(valor):
    """El color de 16 bits de la Neo Geo a (r, g, b)."""
    r5 = ((valor >> 8) & 0xF) * 2 + ((valor >> 14) & 1)
    g5 = ((valor >> 4) & 0xF) * 2 + ((valor >> 13) & 1)
    b5 = (valor & 0xF) * 2 + ((valor >> 12) & 1)
    return (r5 * 255 // 31, g5 * 255 // 31, b5 * 255 // 31)


class Maquina:
    """El 68000 con la ROM P1 cargada y el LSPC emulado por encima.

    Solo puede haber una viva a la vez: Musashi guarda el estado de la CPU en
    variables globales de C, asi que montar una segunda maquina deja muda a la
    primera. Para comparar dos versiones del juego, corre una, llama a
    `cerrar()` y monta la otra.
    """

    def __init__(self, p1, c1, c2, s1):
        import machine68k

        self.maquina = machine68k.Machine(machine68k.CPUType.M68000, TOPE_RAM_KIB)
        self.mem = self.maquina.mem
        self.cpu = self.maquina.cpu
        self.mem.w_block(0, p1)
        self.c1, self.c2, self.s1 = c1, c2, s1

        self.vram = [0] * 0x10000
        self.vram_addr = 0
        self.vram_mod = 0
        self.escrituras_vram = 0
        self.lecturas_lspc = 0
        self.rarezas = []           # accesos que este banco no sabe emular
        self.frames = 0
        self.ciclos = 0

        self.pulsar()               # nada pulsado
        self.mem.set_trace_func(self._traza)
        self.mem.set_trace_mode(1)
        self.cpu.pulse_reset()

    # --- el LSPC --------------------------------------------------------

    def _traza(self, op, ancho, direccion, valor):
        """Musashi avisa de cada acceso a memoria; aqui solo importan los
        registros del chip de video, que en una placa de verdad no son RAM."""
        if direccion < 0x3C0000 or direccion > 0x3C0007:
            return 0
        if op == "W":
            if ancho != 1:
                self.rarezas.append("escritura de %d bytes en %06X"
                                    % (1 << ancho, direccion))
                return 0
            if direccion == VRAMRW:
                self.vram[self.vram_addr] = valor & 0xFFFF
                self.vram_addr = (self.vram_addr + self.vram_mod) & 0xFFFF
                self.escrituras_vram += 1
            elif direccion == VRAMADDR:
                self.vram_addr = valor & 0xFFFF
            elif direccion == VRAMMOD:
                self.vram_mod = valor & 0xFFFF
        elif direccion == LSPCMODE:
            self.lecturas_lspc += 1
        return 0

    # --- el mando -------------------------------------------------------

    def pulsar(self, *nombres):
        """Deja pulsados esos botones (y solo esos) hasta la proxima llamada."""
        mando = sistema = 0
        for nombre in nombres:
            if nombre in BOTON:
                mando |= BOTON[nombre]
            elif nombre in SISTEMA:
                sistema |= SISTEMA[nombre]
            else:
                raise KeyError("no existe el boton %r" % nombre)
        self.mem.w8(P1CNT, ~mando & 0xFF)
        self.mem.w8(STATUS_B, ~sistema & 0xFF)

    # --- el reloj -------------------------------------------------------

    def _hasta_que_espere(self, tope):
        """Corre hasta que el juego se queda esperando al LSPC.

        Se nota porque en una tanda entera lee muchas veces el contador de
        linea y no escribe nada en la VRAM: eso es el bucle de np_wait_vblank
        y no el juego trabajando. Devuelve solo los ciclos de trabajo, sin la
        ultima tanda (la de dar vueltas), con un margen de +-TROZO ciclos.
        """
        trabajo = total = 0
        while total < tope:
            escrituras, lecturas = self.escrituras_vram, self.lecturas_lspc
            total += self.maquina.execute(TROZO).cycles
            if (self.escrituras_vram == escrituras
                    and self.lecturas_lspc > lecturas + 4):
                break
            trabajo = total
        return trabajo

    def frame(self, tope=4000000):
        """Avanza un frame y devuelve los ciclos de 68000 que ha costado.

        Es lo que hay que comparar con los 200.000 ciclos que da la consola
        (12 MHz entre 60 frames): cuenta una simulacion y un dibujado, que es
        justo el trabajo de un frame, y no las vueltas que da el juego
        esperando al retrazo.
        """
        self.mem.w16(LSPCMODE, 0x0000)      # se acabo el vblank anterior
        gastados = self._hasta_que_espere(tope)
        self.mem.w16(LSPCMODE, VBLANK)      # empieza el vblank: el juego dibuja
        gastados += self._hasta_que_espere(tope)
        self.frames += 1
        self.ciclos = gastados
        return gastados

    def avanzar(self, cuantos=1):
        for _ in range(cuantos):
            self.frame()

    def cerrar(self):
        self.maquina.cleanup()

    # --- reconstruir la imagen ------------------------------------------

    def paleta(self, indice):
        base = PALETA + indice * 32
        return [self.mem.r16(base + i * 2) for i in range(16)]

    def _tile_sprite(self, numero):
        base = (numero * 64) % max(len(self.c1), 1)
        from ngplat.gfx import decode_sprite_tile
        return decode_sprite_tile(self.c1[base:base + 64], self.c2[base:base + 64])

    def _tile_fix(self, numero):
        base = (numero * 32) % max(len(self.s1), 1)
        from ngplat.gfx import decode_fix_tile
        return decode_fix_tile(self.s1[base:base + 32])

    def dibujar(self):
        """Reconstruye lo que se veria en la tele: fondo, sprites y plano fix."""
        fondo = _color(self.mem.r16(BACKDROP))
        pantalla = [fondo] * (ANCHO * ALTO)
        cache_sprite, cache_fix, cache_paleta = {}, {}, {}

        def paleta(indice):
            if indice not in cache_paleta:
                cache_paleta[indice] = [_color(c) for c in self.paleta(indice)]
            return cache_paleta[indice]

        # Los sprites se pintan del ultimo al primero: en la Neo Geo gana el de
        # numero mas bajo, asi que el 0 acaba encima de todos.
        for sprite in range(SPRITES - 1, -1, -1):
            control = self.vram[SCB3 + sprite]
            alto = control & 0x3F
            if alto == 0:
                continue                        # sprite apagado
            y = (496 - ((control >> 7) & 0x1FF)) & 0x1FF
            if y >= 256:
                y -= 512
            x = (self.vram[SCB4 + sprite] >> 7) & 0x1FF
            if x >= ANCHO:
                x -= 512
            if x <= -16 or x >= ANCHO:
                continue
            for fila in range(min(alto, 32)):
                cima = y + fila * 16
                if cima <= -16 or cima >= ALTO:
                    continue
                numero = self.vram[SCB1 + sprite * 64 + fila * 2]
                atributos = self.vram[SCB1 + sprite * 64 + fila * 2 + 1]
                if numero not in cache_sprite:
                    cache_sprite[numero] = self._tile_sprite(numero)
                pixeles = cache_sprite[numero]
                colores_tile = paleta(atributos >> 8)
                voltea_x = atributos & 0x01
                voltea_y = atributos & 0x02
                self._pegar(pantalla, pixeles, 16, x, cima,
                            colores_tile, voltea_x, voltea_y)

        # El plano fix va encima de todo: es el marcador.
        for columna in range(40):
            for fila in range(28):
                palabra = self.vram[FIXMAP + columna * 32 + fila]
                numero = palabra & 0x0FFF
                if numero == 0:
                    continue
                if numero not in cache_fix:
                    cache_fix[numero] = self._tile_fix(numero)
                self._pegar(pantalla, cache_fix[numero], 8,
                            columna * 8, fila * 8, paleta(palabra >> 12), 0, 0)

        return (ANCHO, ALTO, pantalla)

    @staticmethod
    def _pegar(pantalla, pixeles, lado, x0, y0, colores_tile, voltea_x, voltea_y):
        """Vuelca un tile en la pantalla saltandose el color 0 (transparente)."""
        for fila in range(lado):
            y = y0 + fila
            if y < 0 or y >= ALTO:
                continue
            origen = (lado - 1 - fila) if voltea_y else fila
            base = origen * lado
            destino = y * ANCHO
            for columna in range(lado):
                x = x0 + columna
                if x < 0 or x >= ANCHO:
                    continue
                indice = pixeles[base + ((lado - 1 - columna) if voltea_x else columna)]
                if indice:
                    pantalla[destino + x] = colores_tile[indice]


# --- construir la ROM P1 del banco de pruebas ---------------------------

FUENTES = ("main.c", "np_video.c", "np_hud.c", "np_sound.c", "np_world.c",
           "gamedata.c")


def compilador():
    """El gcc de 68000 que haya en el PATH, o None."""
    import shutil
    for nombre in ("m68k-neogeo-elf-gcc", "m68k-linux-gnu-gcc", "m68k-elf-gcc"):
        if shutil.which(nombre):
            return nombre
    return None


def construir_p1(carpeta, destino):
    """Enlaza una ROM P1 arrancable a partir del `src/` que genera el kit.

    La Neo Geo de verdad arranca por la BIOS, que prepara la placa y llama al
    juego. Aqui no hay BIOS, asi que se enlaza con `neogeo/arranque.c`, que
    pone la pila, copia .data, borra .bss y entra en main(). El codigo del
    juego es exactamente el que genera `ngplat compilar`.
    """
    import subprocess

    gcc = compilador()
    if not gcc:
        return None
    aqui = os.path.dirname(os.path.abspath(__file__))
    raiz = os.path.dirname(aqui)
    fuentes = [os.path.join(carpeta, "src", f) for f in FUENTES]
    fuentes.append(os.path.join(aqui, "neogeo", "arranque.c"))
    fuentes.append(os.path.join(raiz, "engine", "core", "np_aritmetica.c"))
    elf = destino + ".elf"
    orden = [gcc, "-m68000", "-Os", "-fomit-frame-pointer", "-fno-store-merging",
             "-ffreestanding", "-fno-builtin", "-std=c99",
             "-nostdlib", "-nodefaultlibs",
             "-I" + os.path.join(carpeta, "src"),
             "-T", os.path.join(aqui, "neogeo", "neogeo.ld"),
             "-o", elf] + fuentes
    subprocess.run(orden, check=True, capture_output=True)
    objcopy = gcc.replace("-gcc", "-objcopy")
    subprocess.run([objcopy, "-O", "binary", elf, destino],
                   check=True, capture_output=True)
    return destino


def cargar(carpeta, rom_id="202", trabajo=None):
    """Compila y monta la maquina a partir de una carpeta build/neogeo."""
    trabajo = trabajo or os.path.join(carpeta, "banco")
    os.makedirs(trabajo, exist_ok=True)
    p1 = construir_p1(carpeta, os.path.join(trabajo, "p1.bin"))
    if not p1:
        return None

    def leer(ruta):
        with open(ruta, "rb") as fh:
            return fh.read()

    def rom(sufijo):
        return leer(os.path.join(carpeta, "rom",
                                 "%s-%s.%s" % (rom_id, sufijo, sufijo)))

    return Maquina(leer(p1), rom("c1"), rom("c2"), rom("s1"))
