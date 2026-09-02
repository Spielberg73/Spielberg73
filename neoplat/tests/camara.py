"""Comprobar que la camara por pantallas salta de verdad, en la maquina.

Con `camara: scroll` el escenario se desliza: entre dos frames seguidos casi
ningun pixel esta donde estaba. Con `camara: pantallas` pasa lo contrario: el
escenario se queda **clavado** durante muchos frames y de vez en cuando cambia
entero de golpe. Eso se ve mirando cuantas columnas de la pantalla son
identicas de un frame al siguiente, sin comparar nada mas.

Se mira casi toda la pantalla menos el marcador, que no se mueve nunca. Hace
falta que entre el suelo: es la parte con dibujo en todas las columnas, y por
tanto la que delata un scroll de un solo pixel. Los actores se mueven siempre y
ensucian un poco la cuenta, pero ocupan poco: por eso "quieto" no exige el 100%.
"""

from __future__ import annotations

from typing import List, Tuple

QUIETO = 0.85          # a partir de aqui la franja se considera la misma
SALTO = 0.55           # por debajo de aqui ha cambiado media pantalla o mas
DESDE, HASTA = 0.15, 0.98      # de debajo del marcador al borde de abajo


class Vigia:
    """Va mirando frames y cuenta cuantos dejan el escenario donde estaba."""

    def __init__(self, desde: float = DESDE, hasta: float = HASTA):
        self.desde, self.hasta = desde, hasta
        self.anterior: List[Tuple[int, ...]] = []
        self.iguales: List[float] = []

    def _perfil(self, frame) -> List[Tuple[int, ...]]:
        ancho, alto, pixeles = frame
        y0, y1 = int(alto * self.desde), int(alto * self.hasta)
        return [tuple(pixeles[y * ancho + x] for y in range(y0, y1))
                for x in range(ancho)]

    def mirar(self, frame) -> None:
        perfil = self._perfil(frame)
        if self.anterior:
            iguales = sum(1 for a, b in zip(self.anterior, perfil) if a == b)
            self.iguales.append(iguales / len(perfil))
        self.anterior = perfil

    def veredicto(self) -> Tuple[float, float]:
        """(fraccion de frames con el escenario quieto, el cambio mas grande)."""
        if not self.iguales:
            return (0.0, 1.0)
        quietos = sum(1 for v in self.iguales if v >= QUIETO) / len(self.iguales)
        return (quietos, min(self.iguales))


def comprobar_salto(vigia: Vigia, exigir) -> None:
    """Las dos condiciones que separan 'pantallas' de 'scroll'."""
    quietos, mayor = vigia.veredicto()
    exigir(quietos >= 0.8,
           "la camara no esta quieta: solo el %.0f%% de los frames dejan el "
           "escenario donde estaba, y por pantallas deberian ser casi todos"
           % (quietos * 100))
    exigir(mayor <= SALTO,
           "la camara no llega a saltar: el frame que mas cambia solo mueve el "
           "%.0f%% de la pantalla" % ((1 - mayor) * 100))
    print("camara por pantallas: quieta el %.0f%% de los frames y el salto "
          "cambia el %.0f%% de la pantalla" % (quietos * 100, (1 - mayor) * 100))


# --- medir el parallax ---------------------------------------------------
#
# Lo usan las maquinas que dibujan capas de fondo con scroll propio (el
# Amiga en doble plano y el X68000 en la pantalla grafica): se corre a la
# derecha y se mide cuanto se desplaza cada franja de la pantalla.

def perfiles(frames, y0, y1):
    """Firma de cada columna de una franja, en varios frames a la vez.

    Comparar columnas enteras y no filas sueltas evita que un suelo liso, que
    es igual desplazado o sin desplazar, de una medida cualquiera. Las firmas
    se numeran para poder compararlas de un tiron.
    """
    numeros, salida = {}, []
    for ancho, _alto, pixeles in frames:
        fila = []
        for x in range(ancho):
            firma = tuple(pixeles[y * ancho + x] for y in range(y0, y1))
            if firma not in numeros:
                numeros[firma] = len(numeros)
            fila.append(numeros[firma])
        salida.append(fila)
    return salida


def recorrido(fotos, y0, y1, maximo=12):
    """Cuanto se ha desplazado una franja en total, sumando paso a paso.

    Medir del primer frame al ultimo no vale cuando el dibujo se repite: un
    suelo de tiles de 16 pixeles desplazado 64 se ve igual que sin mover, y la
    medida sale cero. Sumando desplazamientos pequenos -menos de lo que dura el
    motivo- cada paso es inequivoco y el total sale bien.

    Devuelve (pixeles en total, la peor fiabilidad de los pasos).
    """
    perfil = perfiles(fotos, y0, y1)
    total, peor = 0, 1.0
    for i in range(1, len(perfil)):
        paso, fiable = desplazamiento(perfil[i - 1], perfil[i], maximo=maximo)
        total += paso
        peor = min(peor, fiable)
    return total, peor


def desplazamiento(antes, ahora, maximo=70):
    """Cuantos pixeles se ha movido una franja entre dos frames, y si la medida
    es de fiar (cuantas columnas casan con ese desplazamiento)."""
    mejor, acierto = 0, 0.0
    ancho = len(antes)
    for d in range(-maximo, maximo + 1):
        iguales = sum(1 for x in range(maximo, ancho - maximo)
                      if antes[x + d] == ahora[x])
        razon = iguales / (ancho - 2 * maximo)
        if razon > acierto:
            mejor, acierto = d, razon
    return mejor, acierto
