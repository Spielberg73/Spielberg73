"""Escucha el timbre con el que suena la musica en un Amiga de verdad.

El Amiga no tiene chip de FM, asi que el kit le da el timbre de otra manera:
el compilador dibuja **un ciclo** de la onda y Paula la toca en bucle en vez de
la cuadrada de dos bytes de siempre (ver tools/ngplat/fm.py). Lo que distingue
un timbre de otro son sus armonicos, asi que eso es lo que se mide.

Se saca la melodia del canal **izquierdo** -Paula manda el canal 0 y el 3 a la
izquierda por hardware, y el kit pone ahi la melodia- y de la nota que mas
suena se miran el segundo y el tercer armonico contra el primero.

    python3 tests/timbre_amiga.py juego.adf

Imprime una linea de JSON con la nota que ha oido y sus armonicos, que es lo
que compara test_sonido.py entre dos discos con timbres distintos.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from libretro import Emulador, buscar_core          # noqa: E402
from sonido import energia, izquierdo, nivel, ESCALA  # noqa: E402

CORE = "puae"
FPS = 50.0
# Cuanto se le da al disquete para arrancar. **Se espera a que suene**, no un
# numero fijo de segundos: AROS no tarda siempre lo mismo y el mismo disquete
# unas veces esta tocando a los 22 segundos y otras no (medido: a los 22 hay
# silencio y a los 30 suena, con el mismo .adf). Con un tope fijo, la prueba
# fallaba una de cada tantas veces sin que pasara nada.
SEGUNDOS_MINIMO = 15
SEGUNDOS_MAXIMO = 60
# Media nota: las canciones del kit van a ocho frames por nota.
FRAMES_POR_VENTANA = 4


def escuchar(adf: str, ventanas: int = 24):
    """Los armonicos de la melodia, medidos **nota a nota**.

    No vale mirar dos segundos de tiron: en dos segundos caben varias notas y
    la fundamental de una cae justo encima del armonico de otra -el segundo
    armonico de un do5 es un do6, que a lo mejor es la nota siguiente-. Asi que
    se trocea en ventanas cortas, media nota cada una, y de cada ventana se
    saca la nota que suena y sus armonicos. Lo que se devuelve es la **mediana**
    de todas: las ventanas que pillan un cambio de nota salen raras, y la
    mediana las ignora.
    """
    core = buscar_core(CORE, "NEOPLAT_CORE_AMIGA")
    if not core:
        return None
    sistema = tempfile.mkdtemp(prefix="neoplat-timbre-")
    emu = Emulador(core, sistema=sistema, opciones={
        "puae_kickstart": "aros",
        "puae_model": "A500",
        "puae_video_standard": "PAL",
        "puae_chipmem_size": "1",
    })
    emu.cargar(adf)
    while emu.frames < SEGUNDOS_MINIMO * FPS:
        emu.avanzar(100)
    # esperar a que suene: AROS no tarda siempre lo mismo
    while emu.frames < SEGUNDOS_MAXIMO * FPS:
        if nivel(izquierdo(emu.escuchar(25))) >= 1.0:
            break
    else:
        return {"error": "no suena nada despues de %d segundos" % SEGUNDOS_MAXIMO}

    medidas = []
    for _ in range(ventanas):
        canal = izquierdo(emu.escuchar(FRAMES_POR_VENTANA))
        if not canal or nivel(canal) < 1.0:
            continue
        ritmo = emu.ritmo
        nombre, hz = max(ESCALA, key=lambda par: energia(canal, ritmo, par[1]))
        uno = energia(canal, ritmo, hz)
        if uno <= 0:
            continue
        medidas.append((nombre, energia(canal, ritmo, hz * 2.0) / uno,
                        energia(canal, ritmo, hz * 3.0) / uno))
    if not medidas:
        return {"error": "no se ha podido medir ninguna nota"}

    def mediana(cuales):
        cuales = sorted(cuales)
        return cuales[len(cuales) // 2]

    return {
        "ventanas": len(medidas),
        "notas": sorted({m[0] for m in medidas}),
        "h2": round(mediana([m[1] for m in medidas]), 4),
        "h3": round(mediana([m[2] for m in medidas]), 4),
    }


if __name__ == "__main__":
    salida = escuchar(sys.argv[1])
    if salida is None:
        print("el core de PUAE no esta instalado: se salta")
        sys.exit(0)
    print(json.dumps(salida))
    sys.exit(0 if "error" not in salida else 1)
