"""Generacion de la ROM M1: el driver de sonido que corre en el Z80.

En la Neo Geo el chip de sonido (YM2610) cuelga del Z80, no del 68000: el juego
manda ordenes ("suena el efecto 3", "pon la musica 1") por el puerto de sonido
y este driver las ejecuta.

El driver usa los tres canales de onda cuadrada (SSG) del YM2610:

    canal A -> primera pista de la musica
    canal B -> segunda pista de la musica
    canal C -> efectos (y ruido para los golpes)

Formato de las secuencias (4 bytes por paso):

    periodo_bajo, periodo_alto, duracion_en_frames, volumen

`duracion = 0` marca el final: si la secuencia es en bucle vuelve al principio,
y si no, calla el canal.

El compas lo marca el temporizador B del YM2610, programado a ~60 Hz, asi que
la musica avanza al mismo ritmo que el juego.

AVISO: este driver esta escrito siguiendo la documentacion del hardware y se
prueba con un emulador de Z80 en tests/test_sonido.py (se comprueba que escribe
los periodos y volumenes correctos), pero no se ha podido ejecutar en una
consola ni en un emulador de Neo Geo.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .errors import ProjectError
from .sonido import EVENTOS, Sonido, periodo_ssg
from .z80 import ensamblar

M1_SIZE = 0x20000              # 128 KB, el tamano habitual de una ROM M1

# --- protocolo con el 68000 ---------------------------------------------
# El comando es un byte:  bit 6 = alternancia (para repetir el mismo sonido),
# bits 0-5 = carga util.
CMD_SFX_BASE = 0x01            # 0x01..0x2F -> efecto 0..46
CMD_MUSIC_BASE = 0x30          # 0x30..0x3E -> musica 0..14
CMD_MUSIC_STOP = 0x3F

# --- memoria del Z80 ------------------------------------------------------
RAM = 0xF800
VAR_CMD = RAM + 0x00           # ultimo comando recibido (lo escribe la NMI)
VAR_LAST = RAM + 0x01          # ultimo comando ya procesado
CANAL = RAM + 0x10             # estado de los canales, 8 bytes cada uno


def _canal_vars(indice: int) -> Dict[str, int]:
    base = CANAL + indice * 8
    return {"ptr": base, "base": base + 2, "cont": base + 4,
            "act": base + 5, "loop": base + 6}


def _cabecera() -> str:
    return """
; ------------------------------------------------------------------
; Driver de sonido de NeoPlat para el Z80 de la Neo Geo (ROM M1).
; Generado por ngplat; no se edita a mano.
; ------------------------------------------------------------------
        org $0000
        di
        jp inicio

        ; La NMI salta a $0066 y salta cada vez que el 68000 manda un comando.
        ds $0066-$, 0
        push af
        in a,($00)              ; leer el comando (y confirmarlo al hardware)
        ld ($%04x),a            ; lo deja para el bucle principal
        pop af
        retn

inicio:
        ld sp,$fffe
        xor a
        ld ($%04x),a
        ld ($%04x),a
        call limpiar_canales
        call init_ym
bucle_principal:
        call procesar_comando
        call esperar_tick
        call actualizar
        jr bucle_principal

; --- escribir un registro del YM2610 (parte A: SSG y temporizadores) ------
; b = registro, c = valor
escribir_ym:
        ld a,b
        out ($04),a
        nop
        nop
        nop
        ld a,c
        out ($05),a
        nop
        nop
        nop
        nop
        ret

init_ym:
        ld b,$07                ; mezclador: tono en A, B y C; ruido apagado
        ld c,%%00111000
        call escribir_ym
        ld b,$08                ; volumenes a cero
        ld c,0
        call escribir_ym
        ld b,$09
        ld c,0
        call escribir_ym
        ld b,$0a
        ld c,0
        call escribir_ym
        ld b,$26                ; temporizador B: unos 60 Hz
        ld c,140
        call escribir_ym
        ld b,$27                ; arrancarlo y limpiar su aviso
        ld c,$2a
        call escribir_ym
        ret

; --- esperar al siguiente tick (aviso del temporizador B) -----------------
esperar_tick:
        in a,($04)              ; estado del YM2610
        bit 1,a
        jr z,esperar_tick
        ld b,$27
        ld c,$2a                ; limpiar el aviso y seguir contando
        call escribir_ym
        ret

limpiar_canales:
        ld hl,$%04x
        ld b,24
limpiar_bucle:
        ld (hl),0
        inc hl
        djnz limpiar_bucle
        ret
""" % (VAR_CMD, VAR_CMD, VAR_LAST, CANAL)


def _procesar_comando(num_sfx: int, num_musica: int) -> str:
    return """
; --- leer el comando que ha dejado la NMI ---------------------------------
procesar_comando:
        ld a,($%04x)
        ld hl,$%04x
        cp (hl)
        ret z                   ; nada nuevo
        ld (hl),a
        and $3f                 ; quitar el bit de alternancia
        ret z
        cp $%02x
        jr nc,comando_musica
; --- efecto de sonido -----------------------------------------------------
        dec a                   ; los efectos empiezan en 1
        cp %d
        ret nc                  ; indice fuera de rango: se ignora
        add a,a
        ld l,a
        ld h,0
        ld de,tabla_efectos
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)               ; de = secuencia del efecto
        ld a,d
        or e
        ret z
        xor a
        ld (%s),a               ; los efectos no van en bucle
        ld hl,%s
        jp arrancar_canal

comando_musica:
        cp $%02x
        jr z,parar_musica
        sub $%02x
        cp %d
        ret nc
        add a,a
        add a,a                 ; cada musica son dos punteros
        ld l,a
        ld h,0
        ld de,tabla_musica
        add hl,de
        push hl
        ld e,(hl)
        inc hl
        ld d,(hl)               ; primera pista
        ld a,1
        ld (%s),a
        ld hl,%s
        call arrancar_canal
        pop hl
        inc hl
        inc hl
        ld e,(hl)
        inc hl
        ld d,(hl)               ; segunda pista
        ld a,1
        ld (%s),a
        ld hl,%s
        call arrancar_canal
        ret

parar_musica:
        xor a
        ld (%s),a
        ld (%s),a
        ld b,$08
        ld c,0
        call escribir_ym
        ld b,$09
        ld c,0
        call escribir_ym
        ret

; --- arrancar un canal: hl = estado del canal, de = secuencia -------------
arrancar_canal:
        ld a,d
        or e
        jr z,arrancar_nada
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld (hl),e               ; se guarda el principio para el bucle
        inc hl
        ld (hl),d
        inc hl
        ld (hl),1               ; suena en el proximo tick
        inc hl
        ld (hl),1               ; activo
        ret
arrancar_nada:
        ld de,5
        add hl,de
        ld (hl),0               ; sin secuencia: canal parado
        ret
""" % (VAR_CMD, VAR_LAST, CMD_MUSIC_BASE, num_sfx,
       "$%04x" % _canal_vars(2)["loop"], "$%04x" % _canal_vars(2)["ptr"],
       CMD_MUSIC_STOP, CMD_MUSIC_BASE, num_musica,
       "$%04x" % _canal_vars(0)["loop"], "$%04x" % _canal_vars(0)["ptr"],
       "$%04x" % _canal_vars(1)["loop"], "$%04x" % _canal_vars(1)["ptr"],
       "$%04x" % _canal_vars(0)["act"], "$%04x" % _canal_vars(1)["act"])


def _canal_asm(indice: int) -> str:
    v = _canal_vars(indice)
    reg_lo = indice * 2
    reg_hi = indice * 2 + 1
    reg_vol = 8 + indice
    ruido = indice == 2       # solo el canal de efectos usa el ruido
    codigo = """
; --- canal %d --------------------------------------------------------------
actualizar_canal%d:
        ld a,($%04x)            ; activo?
        or a
        ret z
        ld hl,$%04x             ; contador de frames
        dec (hl)
        ret nz
siguiente%d:
        ld hl,($%04x)           ; puntero a la secuencia
        ld c,(hl)               ; periodo bajo
        inc hl
        ld b,(hl)               ; periodo alto
        inc hl
        ld a,(hl)               ; duracion
        inc hl
        ld e,(hl)               ; volumen (bit 7 = ruido)
        inc hl
        or a
        jr z,fin%d
        ld ($%04x),a            ; guardar la duracion
        ld ($%04x),hl           ; y el puntero a la siguiente
        push bc
        push de
        ld a,c
        ld b,$%02x              ; periodo, parte baja
        ld c,a
        call escribir_ym
        pop de
        pop bc
        push de
        ld a,b                  ; parte alta del periodo (antes de tocar b)
        and $0f
        ld c,a
        ld b,$%02x
        call escribir_ym
        pop de
""" % (indice, indice, v["act"], v["cont"], indice, v["ptr"], indice,
       v["cont"], v["ptr"], reg_lo, reg_hi)

    if ruido:
        codigo += """        ld a,e
        and $80                 ; bit de ruido
        jr z,solo_tono%d
        ld b,$06                ; periodo del ruido
        ld c,16
        call escribir_ym
        ld b,$07                ; mezclador: ruido en C, tono de C apagado
        ld c,%%00011100
        call escribir_ym
        jr volumen%d
solo_tono%d:
        ld b,$07                ; mezclador normal
        ld c,%%00111000
        call escribir_ym
volumen%d:
""" % (indice, indice, indice, indice)

    codigo += """        ld a,e
        and $0f
        ld c,a
        ld b,$%02x              ; volumen del canal
        call escribir_ym
        ret

fin%d:
        ld a,($%04x)            ; en bucle?
        or a
        jr z,parar%d
        ld hl,($%04x)           ; volver al principio
        ld ($%04x),hl
        jr siguiente%d
parar%d:
        xor a
        ld ($%04x),a
        ld b,$%02x
        ld c,0
        call escribir_ym
        ret
""" % (reg_vol, indice, v["loop"], indice, v["base"], v["ptr"], indice,
       indice, v["act"], reg_vol)
    return codigo


def _actualizar() -> str:
    return """
actualizar:
        call actualizar_canal0
        call actualizar_canal1
        call actualizar_canal2
        ret
"""


def _secuencia_bytes(pasos, nombre: str) -> List[str]:
    """Convierte los pasos en lineas 'db' de 4 bytes."""
    lineas = ["%s:" % nombre]
    for paso in pasos:
        duracion = max(1, int(paso.duracion))
        volumen = (paso.volumen & 0x0F) | (0x80 if paso.ruido else 0)
        periodo = periodo_ssg(paso.frecuencia)
        while duracion > 0:
            trozo = min(255, duracion)
            lineas.append("        db $%02x,$%02x,%d,$%02x"
                          % (periodo & 0xFF, (periodo >> 8) & 0x0F, trozo, volumen))
            duracion -= trozo
    lineas.append("        db 0,0,0,0        ; fin")
    return lineas


def generar_asm(sonido: Sonido, orden_musica: List[str]) -> Tuple[str, List[str]]:
    """Devuelve el fuente completo del driver y el orden de los efectos."""
    orden_efectos = [nombre for nombre in EVENTOS if nombre in sonido.efectos]
    if len(orden_efectos) > 46:
        raise ProjectError("hay demasiados efectos de sonido (maximo 46)")
    if len(orden_musica) > 14:
        raise ProjectError("hay demasiadas musicas (maximo 14)")

    partes = [_cabecera(), _procesar_comando(len(orden_efectos), len(orden_musica)),
              _actualizar()]
    for i in range(3):
        partes.append(_canal_asm(i))

    datos = ["", "; ---------------------------------------------------- datos"]
    datos.append("tabla_efectos:")
    if orden_efectos:
        datos.append("        dw " + ", ".join("efecto_%s" % n for n in orden_efectos))
    else:
        datos.append("        dw 0")
    datos.append("tabla_musica:")
    if orden_musica:
        for nombre in orden_musica:
            tema = sonido.musica[nombre]
            pistas = ["musica_%s_%d" % (nombre, i) for i in range(len(tema.pistas))]
            while len(pistas) < 2:
                pistas.append("0")
            datos.append("        dw " + ", ".join(pistas))
    else:
        datos.append("        dw 0, 0")

    for nombre in orden_efectos:
        datos.extend(_secuencia_bytes(sonido.efectos[nombre].pasos, "efecto_%s" % nombre))
    for nombre in orden_musica:
        tema = sonido.musica[nombre]
        for i, pista in enumerate(tema.pistas):
            datos.extend(_secuencia_bytes(pista, "musica_%s_%d" % (nombre, i)))

    fuente = "\n".join(partes) + "\n" + "\n".join(datos) + "\n"
    return fuente, orden_efectos


def generar_m1(sonido: Sonido, orden_musica: List[str]) -> Tuple[bytes, Dict[str, object]]:
    """Ensambla el driver y devuelve la ROM M1 lista para grabar."""
    fuente, orden_efectos = generar_asm(sonido, orden_musica)
    codigo, etiquetas = ensamblar(fuente)
    if len(codigo) > M1_SIZE:
        raise ProjectError(
            "el sonido ocupa %d bytes y la ROM M1 son %d" % (len(codigo), M1_SIZE),
            hint="acorta la musica o usa menos efectos",
        )
    rom = bytearray(codigo)
    rom.extend(b"\x00" * (M1_SIZE - len(rom)))
    info = {
        "bytes": len(codigo),
        "efectos": orden_efectos,
        "musica": list(orden_musica),
        "etiquetas": etiquetas,
        "fuente": fuente,
    }
    return bytes(rom), info


def comando_efecto(indice: int) -> int:
    return CMD_SFX_BASE + indice


def comando_musica(indice: int) -> int:
    return CMD_MUSIC_BASE + indice
