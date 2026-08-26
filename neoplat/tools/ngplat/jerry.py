"""El driver de sonido de la Jaguar: un programa para el DSP de Jerry.

La Jaguar no tiene chip de sonido. Tiene **dos DAC de 16 bits** y alguien que
les de una muestra cada vez que el reloj de audio hace tic; ese alguien es el
DSP de Jerry, que es quien recibe la interrupcion I2S. Asi que aqui hay un
programa para el DSP, y el 68000 se queda con lo de siempre: leer las
secuencias del `game.yaml` y decir, cada frame, que nota toca cada canal.

El reparto es el mismo que en las otras tres maquinas:

    canal 0 -> primera pista de la musica
    canal 1 -> segunda pista
    canal 2 -> efectos
    ruido   -> percusion y golpes

**Como suena cada canal.** Un acumulador de fase de 32 bits al que se le suma
un `paso` por muestra; el bit de arriba de la fase dice si la onda cuadrada
esta arriba o abajo, y se suma `+amplitud` o `-amplitud`. Es la forma mas
barata de hacer una cuadrada exacta, y da la misma nota que el SSG de la Neo
Geo o el PSG de la Mega Drive:

    paso = frecuencia * 2^32 / muestras_por_segundo

El ruido sale de un registro de desplazamiento realimentado (el mismo truco que
el PSG), sin saltos: la realimentacion se aplica con una mascara.

**Como hablan el 68000 y el DSP.** Un bloque de siete palabras en la RAM del
DSP, que el 68000 escribe cada frame y el manejador lee en cada muestra:

    paso0, paso1, paso2, amplitud0, amplitud1, amplitud2, amplitud_ruido

**Lo que hay que saber del hardware** (todo comprobado contra el emulador, que
es lo mismo que dice la documentacion de Atari):

  - la RAM del DSP esta en $F1B000 y son 8 KB; los vectores de interrupcion van
    al principio, 16 bytes cada uno, y el de I2S es el segundo ($F1B010);
  - al entrar en la interrupcion el DSP fuerza el banco 0 de registros, mete la
    direccion de vuelta en la pila (r31) y pone IMASK; para volver hay que
    sacarla, sumarle 2 y escribir D_FLAGS con IMASK a cero;
  - la frecuencia de muestreo la da SCLK: muestras = reloj / (64 * (SCLK + 1)).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .dsp import RAM_DSP, ensamblar

RELOJ = 26590906                 # el reloj del sistema (NTSC), en hercios
SCLK = 19                        # 26590906 / (64 * 20) = 20774 muestras/segundo
MUESTRAS = RELOJ // (64 * (SCLK + 1))
DESPLAZAMIENTO = 14              # el paso se guarda en 16 bits: paso32 = campo << 14
CANALES = 3
AMPLITUD = 400                   # por cada punto de volumen (0-15)

# --- registros de Jerry ---------------------------------------------------
LTXD = 0xF1A148
RTXD = 0xF1A14C
D_FLAGS = 0xF1A100
D_I2SENA = 0x20
D_I2SCLR = 0x400
VOLVER = D_I2SENA | D_I2SCLR     # I2S sigue habilitada, se limpia el aviso,
                                 # IMASK a cero para poder atender la siguiente

# El polinomio del ruido: los mismos bits que usa el PSG de la Mega Drive.
RUIDO_SEMILLA = 0x00012345
RUIDO_POLINOMIO = 0x00012000


def _canal(fase: int, amplitud: int) -> List[str]:
    """La onda cuadrada de un canal, sin un solo salto.

    `fase >> 31` da 0 o 1; restandole 1 sale 0 o -1, que es justo la mascara
    para negar: `(a xor m) - m` vale `a` si m es 0 y `-a` si m es -1.
    """
    return [
        "        move   r%d,r18" % fase,
        "        shrq   #31,r18",
        "        subq   #1,r18",
        "        move   r%d,r19" % amplitud,
        "        xor    r18,r19",
        "        sub    r18,r19",
        "        add    r19,r17",
    ]


def fuente() -> str:
    """El programa del DSP, en el ensamblador de tools/ngplat/dsp.py."""
    lineas = [
        "; Driver de sonido de la Jaguar. Lo genera tools/ngplat/jerry.py.",
        "        org    $%06X" % RAM_DSP,
        "        ds     16                  ; vector 0 (68000): no se usa",
        "",
        "manejador                          ; vector de la interrupcion I2S",
        "        move   r10,r16             ; el bloque que escribe el 68000",
        "        load   (r16),r4            ; paso de cada canal",
        "        addq   #4,r16",
        "        load   (r16),r5",
        "        addq   #4,r16",
        "        load   (r16),r6",
        "        addq   #4,r16",
        "        load   (r16),r7            ; y su amplitud",
        "        addq   #4,r16",
        "        load   (r16),r8",
        "        addq   #4,r16",
        "        load   (r16),r9",
        "        addq   #4,r16",
        "        load   (r16),r23           ; amplitud del ruido",
        "",
        "        add    r4,r1               ; una muestra: la fase avanza un paso",
        "        add    r5,r2",
        "        add    r6,r3",
        "        moveq  #0,r17              ; aqui se suman los cuatro",
    ]
    for i in range(CANALES):
        lineas.append("")
        lineas.extend(_canal(1 + i, 7 + i))

    lineas.extend([
        "",
        "        move   r20,r21             ; ruido: el bit que sale del registro",
        "        moveq  #1,r22",
        "        and    r22,r21",
        "        neg    r21                 ; 0 o -1",
        "        and    r25,r21             ; 0 o el polinomio",
        "        shrq   #1,r20",
        "        xor    r21,r20             ; realimentado",
        "        move   r20,r18",
        "        moveq  #1,r22",
        "        and    r22,r18",
        "        subq   #1,r18              ; 0 o -1, como en los canales",
        "        move   r23,r19",
        "        xor    r18,r19",
        "        sub    r18,r19",
        "        add    r19,r17",
        "",
        "        store  r17,(r11)           ; los dos DAC, el mismo sonido",
        "        store  r17,(r12)",
        "",
        "        load   (r31),r18           ; la direccion de vuelta, de la pila",
        "        addq   #4,r31",
        "        addq   #2,r18              ; apunta a la ya ejecutada",
        "        jump   t,(r18)",
        "        store  r14,(r13)           ; ranura de retardo: D_FLAGS",
        "",
        "inicio                             ; aqui arranca el DSP (D_PC)",
        "        movei  #pila,r31",
        "        moveq  #0,r1",
        "        moveq  #0,r2",
        "        moveq  #0,r3",
        "        movei  #$%08X,r20          ; semilla del ruido" % RUIDO_SEMILLA,
        "        movei  #$%08X,r25          ; su polinomio" % RUIDO_POLINOMIO,
        "        movei  #parametros,r10",
        "        movei  #$%06X,r11" % LTXD,
        "        movei  #$%06X,r12" % RTXD,
        "        movei  #$%06X,r13" % D_FLAGS,
        "        movei  #$%X,r14" % VOLVER,
        "        store  r14,(r13)           ; y a esperar la interrupcion",
        "espera",
        "        jr     t,espera",
        "        nop",
        "",
        "        alinea 4",
        "parametros",
        "        dc.l   0,0,0,0,0,0,0",
        "        ds     64                  ; la pila crece hacia abajo",
        "pila",
    ])
    return "\n".join(lineas)


def generar() -> Tuple[bytes, Dict[str, int]]:
    """El driver ya ensamblado y donde ha quedado cada cosa."""
    return ensamblar(fuente(), RAM_DSP)


def paso_de_frecuencia(hz: float) -> int:
    """Frecuencia -> el numero de 16 bits que lee el 68000.

    El DSP trabaja con un paso de 32 bits, pero en la tabla de notas caben 16:
    se guarda `paso >> 14` y el 68000 lo devuelve a su sitio.
    """
    paso = int(round(hz * (1 << 32) / MUESTRAS))
    campo = paso >> DESPLAZAMIENTO
    return max(1, min(0xFFFF, campo))


def frecuencia_de_paso(campo: int) -> float:
    """La inversa, para las pruebas."""
    return (campo << DESPLAZAMIENTO) * float(MUESTRAS) / (1 << 32)
