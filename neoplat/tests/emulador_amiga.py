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
from camara import (Vigia, comprobar_salto,  # noqa: E402
                    desplazamiento, perfiles)
from libretro import (Emulador, buscar_core, colores, distintos,  # noqa: E402
                      filas_escritas, franja, guardar_png)
from sonido import (banda_del_efecto, comprobar_melodia, comprobar_titulo,  # noqa: E402
                    nivel, pico_por_frame)

CORE = "puae"
# arrancar un Amiga lleva su tiempo: AROS tarda unos 50 segundos emulados
SEGUNDOS_DE_ARRANQUE = 70
FPS = 50
FRANJA_FONDO = (78, 112)     # el cielo: ahi solo se ve la capa de parallax
FRANJA_SUELO = (225, 250)    # el suelo del escenario, con sus bordes
FRAMES_ANTES_DE_MEDIR = 110  # lo que tarda la camara en despegarse del borde


def comprobar(adf: str, capturas: str = "capturas", musica=None,
              salto=None, disparo=None, parallax: bool = False,
              pantallas: bool = False, titulo_musica: str = "",
              modelo: str = "A500") -> int:
    """`modelo` es la maquina que se emula: 'A500' (OCS, lo de siempre) o
    'A1200' (AGA). El disquete del A1200 lleva ocho bitplanes y en un A500 no
    se veria nada, asi que cada uno se prueba en el suyo."""
    core = buscar_core(CORE, "NEOPLAT_CORE_AMIGA")
    if not core:
        print("el core de PUAE no esta instalado: se salta la prueba")
        return 0
    os.makedirs(capturas, exist_ok=True)
    franja_del_salto = banda_del_efecto(musica, salto) if musica and salto else None
    franja_del_disparo = (banda_del_efecto(musica, disparo)
                          if musica and disparo else None)
    fallos = []

    def exigir(condicion, mensaje):
        if not condicion:
            fallos.append(mensaje)

    sistema = tempfile.mkdtemp(prefix="neoplat-amiga-")
    emu = Emulador(core, sistema=sistema, opciones={
        "puae_kickstart": "aros",       # la ROM libre que trae el propio core
        "puae_model": modelo,           # A500: OCS, 68000, 512 KB de RAM chip
        "puae_video_standard": "PAL",
        # el A1200 lleva 2 MB de RAM chip de serie, y los ocho bitplanes los
        # necesitan: el mapa de bits solo son ya 176 KB
        "puae_chipmem_size": "2" if modelo != "A500" else "1",
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
    escritas = filas_escritas(titulo, 48)
    exigir(escritas >= 6,
           "no se ve el marcador arriba: solo %d filas de las 48 de arriba "
           "llevan algo dibujado" % escritas)
    comprobar_titulo(exigir, nivel(emu.escuchar(25)), titulo_musica)
    print("titulo: %dx%d con %d colores" % (titulo[0], titulo[1], cuantos))

    # --- 2) empieza la partida ------------------------------------------
    #
    # El start se lo lleva el **disparo** (que ademas salta): el segundo boton
    # es el de accion, para poder atacar. Un joystick de un solo boton empieza
    # la partida igual.
    emu.pulsar("B")
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

    # --- el boton de accion: el segundo del joystick ---------------------
    #
    # Es lo que hacia falta para atacar y para tirar el arma secundaria, y en
    # el Amiga no estaba leido: el segundo boton valia de start y no habia
    # ningun boton de accion. Se comprueba por el sonido, que es lo unico que
    # dice si la pulsacion ha llegado al motor: al disparar suena su efecto.
    if franja_del_disparo:
        # El efecto del disparo solo asoma por encima de la musica en su primer
        # frame (es un barrido que baja), asi que la senal es mas floja que la
        # del salto. Para que no dependa del volumen de la cancion se compara
        # con **otro boton que no hace nada**: si el de accion suena mas que
        # ese, la pulsacion ha llegado al motor.
        def pico(boton=None):
            emu.pulsar()
            emu.avanzar(40)              # que se apague lo de antes
            mejor = 0.0
            for i in range(60):
                emu.pulsar(boton) if (boton and i % 20 == 0) else emu.pulsar()
                mejor = max(mejor, pico_por_frame(emu.escuchar, 1, emu.ritmo,
                                                  *franja_del_disparo))
            return mejor

        quieto = pico()
        otro = pico("X")
        atacando = pico("A")
        referencia = max(quieto, otro)
        exigir(atacando > referencia * 1.6,
               "el segundo boton no ataca: entre %.0f y %.0f Hz suena %.1f veces mas "
               "que sin tocar nada y %.1f veces mas que con otro boton, y "
               "deberia notarse mucho mas"
               % (franja_del_disparo[0], franja_del_disparo[1],
                  atacando / max(1.0, quieto), atacando / max(1.0, otro)))
        print("boton de accion: %.1f veces mas fuerte que el fondo (otro boton, %.1f)"
              % (atacando / max(1.0, referencia), otro / max(1.0, quieto)))


    # --- 3b) el parallax va mas despacio que el suelo --------------------
    #
    # Solo en doble plano (amiga: 8colores). Se corre a la derecha tomando
    # fotos cada pocos frames y se mide cuanto se ha desplazado la franja del
    # cielo y cuanto la del suelo. Se para en cuanto el suelo deja de irse a la
    # izquierda: eso es que el jugador ha muerto y la camara ha vuelto al
    # principio, y desde ahi las medidas ya no valen.
    if parallax:
        for _ in range(FRAMES_ANTES_DE_MEDIR):
            emu.pulsar("RIGHT")
            emu.avanzar(1)
        fotos = [emu.frame]
        for _ in range(8):
            for _ in range(6):
                emu.pulsar("RIGHT")
                emu.avanzar(1)
            fotos.append(emu.frame)
        emu.pulsar()
        guardar_png(fotos[0], os.path.join(capturas, "amiga_parallax_antes.png"))
        cielos = perfiles(fotos, *FRANJA_FONDO)
        suelos = perfiles(fotos, *FRANJA_SUELO)
        fondo = suelo = 0
        fiable_f = fiable_s = 0.0
        for i in range(1, len(fotos)):
            paso, fiable = desplazamiento(suelos[0], suelos[i])
            if paso >= suelo or fiable < 0.5:
                break                      # la camara ha dejado de avanzar
            suelo, fiable_s = paso, fiable
            fondo, fiable_f = desplazamiento(cielos[0], cielos[i])
            guardar_png(fotos[i], os.path.join(capturas, "amiga_parallax.png"))
        exigir(suelo < 0, "el escenario no se ha movido al correr a la derecha")
        exigir(fiable_f > 0.5,
               "no se puede medir el fondo: solo casa el %.0f%% de las columnas"
               % (fiable_f * 100))
        exigir(fondo < 0, "la capa de fondo no se mueve: no hay parallax")
        exigir(abs(fondo) < abs(suelo) / 2,
               "la capa de fondo se mueve %d pixeles y el suelo %d: no van a "
               "velocidades distintas" % (abs(fondo), abs(suelo)))
        print("parallax: el suelo se mueve %d pixeles y el fondo %d (%.2f del scroll)"
              % (abs(suelo), abs(fondo), abs(fondo) / max(1, abs(suelo))))


    # --- 4) se juega ----------------------------------------------------
    movimiento = 0.0
    antes = juego
    vigia = Vigia() if pantallas else None
    for tramo in range(6):
        for i in range(60):
            emu.pulsar("RIGHT", "B") if i % 30 == 0 else emu.pulsar("RIGHT")
            emu.avanzar(1)
            if vigia:
                vigia.mirar(emu.frame)
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
    if vigia:
        comprobar_salto(vigia, exigir)

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
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    opciones = [a for a in sys.argv[1:] if a.startswith("--")]
    disco = (argumentos[0] if argumentos
             else "examples/bosque-magico/build/amiga/disco/BosqueMagico.adf")
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools"))
    from ngplat.project import load_project
    from sonido import buscar_proyecto, musica_al_empezar
    # el game.yaml no siempre esta encima del disquete (las pruebas del kit lo
    # dejan en otra carpeta), asi que se puede decir donde esta
    proyecto = ""
    modelo = "A500"
    for opcion in opciones:
        if opcion.startswith("--proyecto="):
            proyecto = opcion.split("=", 1)[1]
        elif opcion.startswith("--modelo="):
            modelo = opcion.split("=", 1)[1]
    proyecto = proyecto or buscar_proyecto(disco)
    p = load_project(proyecto) if proyecto else None
    sys.exit(comprobar(disco, argumentos[1] if len(argumentos) > 1 else "capturas",
                       musica_al_empezar(p) if p else None,
                       p.sound.efectos.get("salto") if p else None,
                       p.sound.efectos.get("disparo") if p else None,
                       parallax=bool(p and p.amiga_modo == "8colores" and p.layers),
                       pantallas="--pantallas" in opciones
                                 or bool(p and p.camera == "pantallas"),
                       titulo_musica=p.sound.titulo if p else "",
                       modelo=modelo))
