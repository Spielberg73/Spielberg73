"""Arranca el disquete de Amiga en un emulador de verdad (opcional).

Mete el .adf en un A500 emulado (PUAE, con la ROM libre de AROS) y mira lo que
sale por pantalla: si el disquete no arranca, si el juego no se dibuja o si se
cuelga, aqui se ve. Es la unica prueba que ejercita el disco entero, del
bootblock al ultimo bitplane.

El core no viene en los repositorios; se saca del buildbot de libretro:

    https://buildbot.libretro.com/nightly/linux/x86_64/latest/puae_libretro.so.zip

y se deja en /usr/local/lib/libretro/ (o se apunta con NEOPLAT_CORE_AMIGA).
Si no esta, la prueba se salta.

    python3 tests/emulador_amiga.py ruta/al/juego.adf [carpeta_de_capturas]
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from libretro import (Emulador, buscar_core, colores, distintos,  # noqa: E402
                      franja, guardar_png)
from sonido import (banda_del_efecto, comprobar_melodia,  # noqa: E402
                    nivel, pico_por_frame)

CORE = "puae"
# arrancar un Amiga lleva su tiempo: AROS tarda unos 50 segundos emulados
SEGUNDOS_DE_ARRANQUE = 70
FPS = 50


def comprobar(adf: str, capturas: str = "capturas", musica=None,
              salto=None) -> int:
    core = buscar_core(CORE, "NEOPLAT_CORE_AMIGA")
    if not core:
        print("el core de PUAE no esta instalado: se salta la prueba")
        return 0
    os.makedirs(capturas, exist_ok=True)
    franja_del_salto = banda_del_efecto(musica, salto) if musica and salto else None
    fallos = []

    def exigir(condicion, mensaje):
        if not condicion:
            fallos.append(mensaje)

    sistema = tempfile.mkdtemp(prefix="neoplat-amiga-")
    emu = Emulador(core, sistema=sistema, opciones={
        "puae_kickstart": "aros",       # la ROM libre que trae el propio core
        "puae_model": "A500",           # OCS, 68000, 512 KB de RAM chip
        "puae_video_standard": "PAL",
    })
    emu.cargar(adf)

    # --- 1) el disquete arranca solo y sale el juego ---------------------
    while emu.frames < SEGUNDOS_DE_ARRANQUE * FPS:
        emu.avanzar(100)
    titulo = emu.frame
    exigir(titulo is not None, "el emulador no ha dibujado ningun frame")
    guardar_png(titulo, os.path.join(capturas, "amiga_titulo.png"))
    cuantos = len(colores(titulo))
    # si el disquete no arrancase se veria el escritorio de AROS, que es gris;
    # el juego tiene su fondo de color y su marcador
    exigir(cuantos > 6,
           "a los %d segundos solo hay %d colores: el disquete no ha arrancado"
           % (SEGUNDOS_DE_ARRANQUE, cuantos))
    exigir(len(set(franja(titulo, 24))) > 2, "no se ve el marcador arriba")
    exigir(nivel(emu.escuchar(25)) < 1.0,
           "la pantalla de titulo hace ruido: la musica es solo de la partida")
    print("titulo: %dx%d con %d colores" % (titulo[0], titulo[1], cuantos))

    # --- 2) empieza la partida (start = segundo boton del joystick) ------
    emu.pulsar("A")
    emu.avanzar(20)
    emu.pulsar()
    emu.avanzar(60)
    juego = emu.frame
    guardar_png(juego, os.path.join(capturas, "amiga_juego.png"))
    exigir(distintos(titulo, juego) > 0.001, "la pantalla no cambia al pulsar start")

    # --- 3) y ademas suena: Paula toca la melodia del game.yaml ----------
    #
    # Se escucha nada mas empezar el nivel y sin tocar el mando: los efectos
    # van por su canal pero se mezclan con la musica y emborronan la medida.
    if musica:
        exigir(nivel(emu.escuchar(10)) > 1.0, "el Amiga no saca ningun sonido")
        oido = emu.escuchar(musica.velocidad * (len(musica.pistas[0]) + 1))
        aciertos, total, _, notas = comprobar_melodia(oido, emu.ritmo, musica, FPS)
        exigir(total and aciertos >= total * 0.8,
               "Paula no toca la melodia del game.yaml: %d notas de %d "
               "(se ha oido %s)" % (aciertos, total, [int(n) for n in notas]))
        print("musica: %d de %d notas son las del game.yaml" % (aciertos, total))

    # los efectos van por su canal de Paula y suenan mas agudos que la musica:
    # al saltar tiene que aparecer algo en esa franja que antes no estaba
    if franja_del_salto:
        quieto = pico_por_frame(emu.escuchar, 24, emu.ritmo, *franja_del_salto)
        emu.pulsar("B")
        emu.avanzar(2)
        emu.pulsar()
        saltando = pico_por_frame(emu.escuchar, 24, emu.ritmo, *franja_del_salto)
        exigir(saltando > quieto * 2.5,
               "al saltar no se oye el efecto: entre %.0f y %.0f Hz suena %.1f "
               "veces mas que estando quieto, y deberia notarse mucho mas"
               % (franja_del_salto[0], franja_del_salto[1],
                  saltando / max(1.0, quieto)))
        print("efecto de salto: %.1f veces mas fuerte que el fondo"
              % (saltando / max(1.0, quieto)))

    # --- 4) se juega ----------------------------------------------------
    movimiento = 0.0
    antes = juego
    for tramo in range(6):
        for i in range(60):
            emu.pulsar("RIGHT", "B") if i % 30 == 0 else emu.pulsar("RIGHT")
            emu.avanzar(1)
        ahora = emu.frame
        movimiento = max(movimiento, distintos(antes, ahora))
        antes = ahora
        if tramo == 3:
            guardar_png(ahora, os.path.join(capturas, "amiga_jugando.png"))
    exigir(movimiento > 0.01,
           "la pantalla apenas cambia al jugar (%.2f%%): no se mueve nada"
           % (movimiento * 100))
    print("jugando: hasta un %.0f%% de la pantalla cambia entre tramos"
          % (movimiento * 100))

    # --- 5) sigue vivo --------------------------------------------------
    ultimo = emu.frame
    emu.pulsar("RIGHT")
    emu.avanzar(100)
    exigir(distintos(ultimo, emu.frame) > 0.0,
           "la imagen se ha quedado congelada: el juego se ha colgado")
    guardar_png(emu.frame, os.path.join(capturas, "amiga_final.png"))
    emu.cerrar()

    for fallo in fallos:
        print("FALLO:", fallo)
    if fallos:
        return 1
    print("el disquete arranca y se juega en el emulador; capturas en %s/" % capturas)
    return 0


if __name__ == "__main__":
    disco = (sys.argv[1] if len(sys.argv) > 1
             else "examples/bosque-magico/build/amiga/disco/BosqueMagico.adf")
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools"))
    from ngplat.project import load_project
    from sonido import buscar_proyecto, musica_al_empezar
    proyecto = buscar_proyecto(disco)
    p = load_project(proyecto) if proyecto else None
    sys.exit(comprobar(disco, sys.argv[2] if len(sys.argv) > 2 else "capturas",
                       musica_al_empezar(p) if p else None,
                       p.sound.efectos.get("salto") if p else None))
