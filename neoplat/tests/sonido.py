"""Mirar por dentro el sonido que sale de un emulador.

Las pruebas de video comparan pixeles; estas comparan notas. Lo que entra es un
trozo de sonido tal y como lo entrega el core de libretro (muestras de 16 bits
con signo, estereo entrelazado) y lo que sale es que nota se esta oyendo.

Para saberlo se usa el algoritmo de Goertzel, que es una DFT de una sola
frecuencia: mide cuanta energia hay exactamente en un hercio concreto sin
calcular el espectro entero. Se prueba una a una toda la escala cromatica y
gana la que mas energia tiene.
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))

from ngplat.sonido import frecuencia_de_nota  # noqa: E402

NOMBRES = ["do", "do#", "re", "re#", "mi", "fa",
           "fa#", "sol", "sol#", "la", "la#", "si"]

# La escala que se busca: de do2 a si6, que es donde cabe todo lo que toca el
# kit sin irse a los armonicos de las ondas cuadradas.
ESCALA = [("%s%d" % (NOMBRES[s], o), frecuencia_de_nota(s, o))
          for o in range(2, 7) for s in range(12)]


def mono(muestras):
    """De estereo entrelazado a una sola lista, sin la componente continua."""
    izq = muestras[0::2]
    der = muestras[1::2]
    suma = [(a + b) * 0.5 for a, b in zip(izq, der)]
    if not suma:
        return suma
    medio = sum(suma) / len(suma)
    return [x - medio for x in suma]


def nivel(muestras):
    """Cuanto suena (valor eficaz, 0 = silencio)."""
    canal = mono(muestras) if muestras and len(muestras) % 2 == 0 else list(muestras)
    if not canal:
        return 0.0
    return math.sqrt(sum(x * x for x in canal) / len(canal))


def energia(canal, ritmo, hz):
    """Cuanta energia hay en esa frecuencia exacta (Goertzel)."""
    if hz <= 0 or hz >= ritmo / 2.0:
        return 0.0
    coeficiente = 2.0 * math.cos(2.0 * math.pi * hz / ritmo)
    s1 = s2 = 0.0
    for x in canal:
        s1, s2 = x + coeficiente * s1 - s2, s1
    return math.sqrt(abs(s1 * s1 + s2 * s2 - coeficiente * s1 * s2))


def nota_dominante(muestras, ritmo, escala=None):
    """(nombre, hercios, energia) de la nota que mas suena, o None si es silencio.

    Una onda cuadrada trae armonicos impares muy fuertes (el tercero suena una
    quinta y media por encima), asi que a cada candidata se le suma un poco de
    lo que tienen sus armonicos: si no, a veces gana el tercero en vez de la
    nota de verdad.
    """
    canal = mono(muestras)
    if not canal or nivel(canal) < 1.0:
        return None
    escala = escala or ESCALA
    mejor = None
    for nombre, hz in escala:
        peso = (energia(canal, ritmo, hz)
                + energia(canal, ritmo, hz * 3.0) / 3.0
                + energia(canal, ritmo, hz * 5.0) / 5.0)
        if mejor is None or peso > mejor[2]:
            mejor = (nombre, hz, peso)
    return mejor


def notas_por_tramo(muestras, ritmo, frames, fps=60.0):
    """Trocea el sonido en bloques de `frames` frames y dice que nota hay en cada
    uno. Es como leer la partitura de lo que ha sonado."""
    por_bloque = int(round(ritmo * frames / fps)) * 2
    salida = []
    for i in range(0, len(muestras) - por_bloque + 1, por_bloque):
        trozo = muestras[i:i + por_bloque]
        # se mira solo el centro del bloque: los bordes pillan la nota vecina
        margen = por_bloque // 6
        margen -= margen % 2
        gana = nota_dominante(trozo[margen:por_bloque - margen], ritmo)
        salida.append(gana[0] if gana else "-")
    return salida


# --- comparar lo que suena con lo que pide el game.yaml -----------------

def escala_de(musica):
    """Las frecuencias distintas que usa una musica, ordenadas.

    Buscar solo entre estas es lo que hace que la comprobacion sea rapida: no
    hace falta recorrer la escala cromatica entera para saber si esta sonando
    la nota que toca."""
    vistas = set()
    for pista in musica.pistas:
        for paso in pista:
            if paso.frecuencia > 0:
                vistas.add(paso.frecuencia)
    return sorted(vistas)


def melodia_de(musica):
    """La primera pista como lista de frecuencias, una por hueco de nota
    (0 = silencio). Es la partitura que se espera oir."""
    salida = []
    for paso in musica.pistas[0]:
        huecos = max(1, paso.duracion // max(1, musica.velocidad))
        salida.extend([paso.frecuencia] * huecos)
    return salida


def _bloques(muestras, ritmo, frames, fps, cuantos, desde=0):
    """Trocea la captura en huecos de nota y devuelve el centro de cada uno.

    Se tira la cuarta parte de cada extremo: en los bordes se solapan la nota
    que acaba y la que empieza, y eso emborrona la medida."""
    por_bloque = int(round(ritmo * frames / fps)) * 2
    margen = por_bloque // 4
    margen -= margen % 2
    salida = []
    for b in range(cuantos):
        principio = desde + b * por_bloque
        trozo = muestras[principio:principio + por_bloque]
        if len(trozo) < por_bloque:
            break
        salida.append(mono(trozo[margen:por_bloque - margen]))
    return salida


def _puntuar(canales, ritmo, escala, melodia, entre_las):
    """Cuantos huecos de nota coinciden con la partitura, probando todos los
    desfases: la captura empieza donde empieza, no en el primer compas."""
    niveles = [nivel(c) for c in canales]
    ordenados = sorted(niveles)
    tope_silencio = ordenados[len(ordenados) // 2] * 0.2

    pesos = []
    for canal, cuanto in zip(canales, niveles):
        if cuanto <= tope_silencio:
            pesos.append(None)
        else:
            pesos.append([energia(canal, ritmo, hz) for hz in escala])

    def acierta(peso, hz):
        if hz <= 0:
            return peso is None                  # un silencio no debe sonar
        if peso is None:
            return False
        orden = sorted(range(len(escala)), key=lambda i: peso[i], reverse=True)
        return escala.index(hz) in orden[:entre_las]

    mejor = (0, 0)
    for desfase in range(len(melodia)):
        aciertos = sum(1 for i, peso in enumerate(pesos)
                       if acierta(peso, melodia[(i + desfase) % len(melodia)]))
        if aciertos > mejor[0]:
            mejor = (aciertos, desfase)
    oido = [0.0 if peso is None else escala[peso.index(max(peso))] for peso in pesos]
    return mejor[0], mejor[1], oido


def comprobar_melodia(muestras, ritmo, musica, fps=60.0, entre_las=2):
    """Comprueba que lo capturado es la melodia que pide el `game.yaml`.

    El acompanamiento suena a la vez que la melodia, asi que no se exige que la
    nota de la melodia sea la mas fuerte: basta con que este entre las
    `entre_las` que mas energia tienen de todas las que usa la cancion.

    Los silencios se miden en relativo, comparando con lo que suena el resto de
    la cancion: un silencio de verdad se queda muy por debajo, pero no llega a
    cero (el chip sigue soltando algo).

    La musica lleva sonando desde que empezo el nivel, asi que la captura no
    empieza ni en una nota concreta ni justo en su primer instante: se prueban
    todos los desfases, de compas y de frame, y se devuelve el mejor. Una
    melodia equivocada no acierta con ninguno.

    Devuelve (aciertos, total, desfase, lo que se ha oido en Hz).
    """
    escala = escala_de(musica)
    melodia = melodia_de(musica)
    por_frame = int(round(ritmo / fps)) * 2
    mejor = (0, 0, [], 0)
    for salto in range(musica.velocidad):
        canales = _bloques(muestras, ritmo, musica.velocidad, fps,
                           len(melodia), salto * por_frame)
        if len(canales) < len(melodia):
            continue
        aciertos, desfase, oido = _puntuar(canales, ritmo, escala, melodia,
                                          entre_las)
        if aciertos > mejor[0]:
            mejor = (aciertos, desfase, oido, len(canales))
    if not mejor[2]:
        return (0, 0, 0, [])
    return (mejor[0], mejor[3], mejor[1], mejor[2])


def musica_al_empezar(proyecto):
    """La musica que se oye nada mas empezar la partida (la del primer nivel
    que tenga), o None si el juego no lleva musica."""
    for nivel in proyecto.levels:
        if nivel.music and nivel.music in proyecto.sound.musica:
            return proyecto.sound.musica[nivel.music]
    return None


def comprobar_titulo(exigir, medido, titulo):
    """La pantalla de titulo: muda o con su cancion, segun lo que diga el
    proyecto.

    Con `sonido: titulo:` la pantalla de titulo tiene musica propia y tiene que
    sonar; sin ella se queda callada, que es como estaba el kit. Las cuatro
    maquinas que escuchan el titulo hacen la misma comprobacion, asi que vive
    aqui: `medido` es el nivel que se ha oido y `titulo` el nombre de la
    cancion del titulo (vacio si el juego no lleva).
    """
    if titulo:
        exigir(medido >= 1.0,
               "la pantalla de titulo esta muda y el juego trae "
               "'titulo: %s'" % titulo)
        print("titulo: suena '%s' (nivel %.1f)" % (titulo, medido))
    else:
        exigir(medido < 1.0,
               "la pantalla de titulo hace ruido y el juego no trae "
               "'sonido: titulo:'")


def buscar_proyecto(ruta):
    """Sube por las carpetas desde un binario hasta encontrar el game.yaml que
    lo genero. Sirve para que las pruebas sueltas sepan que musica esperar."""
    carpeta = os.path.dirname(os.path.abspath(ruta))
    while carpeta and carpeta != os.path.dirname(carpeta):
        if os.path.isfile(os.path.join(carpeta, "game.yaml")):
            return carpeta
        carpeta = os.path.dirname(carpeta)
    return ""


def banda(muestras, ritmo, desde_hz, hasta_hz, puntos=10):
    """Cuanta energia hay en una banda de frecuencias, medida en unos cuantos
    puntos repartidos por ella.

    Sirve para los efectos: son barridos y ruidos, no notas, asi que no tiene
    sentido buscarles una frecuencia exacta. Lo que si se puede es mirar si hay
    algo sonando por encima de donde llega la musica."""
    canal = mono(muestras)
    if not canal:
        return 0.0
    paso = (hasta_hz - desde_hz) / float(max(1, puntos - 1))
    return sum(energia(canal, ritmo, desde_hz + paso * i) for i in range(puntos))


def tope_de_la_musica(musica):
    """La nota mas aguda de la cancion. Por encima de ella, lo que suene es un
    efecto."""
    escala = escala_de(musica)
    return escala[-1] if escala else 0.0


def banda_del_efecto(musica, efecto, margen=1.15):
    """La franja de frecuencias donde se oye un efecto y la musica no llega.

    Devuelve None si el efecto entero cae dentro del registro de la cancion:
    entonces no hay forma de distinguirlo por la frecuencia."""
    tope = tope_de_la_musica(musica) * margen
    agudos = [p.frecuencia for p in efecto.pasos if p.frecuencia > tope]
    if not agudos:
        return None
    return (min(agudos), max(agudos))


def pico_por_frame(escuchar, frames, ritmo, desde_hz, hasta_hz):
    """El frame que mas suena en esa banda, de los `frames` siguientes.

    Un efecto dura unos pocos frames; midiendo el trozo entero de una vez, la
    musica de alrededor lo diluye. Frame a frame, el efecto destaca."""
    return max(banda(escuchar(1), ritmo, desde_hz, hasta_hz, 8)
               for _ in range(frames))
