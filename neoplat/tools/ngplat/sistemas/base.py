"""Lo que tiene que saber hacer un sistema de destino.

NeoPlat separa el juego en dos mitades:

  - la simulacion (engine/core/np_world.c), que es aritmetica entera y no sabe
    nada de hardware: vale igual para cualquier maquina;
  - la capa de sistema, que dibuja, suena y lee el mando.

Un "sistema" de este modulo es la segunda mitad: como se convierten los
graficos, que archivos del motor se usan, que datos se generan y como se
construye el ejecutable o el cartucho.

Los tres sistemas que hay ahora (Neo Geo, Mega Drive y Amiga) llevan el mismo
procesador, un 68000, asi que comparten el motor tal cual; lo que cambia es
todo lo demas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..build import Build
from ..errors import ProjectError


@dataclass
class Limites:
    """Lo que aguanta la maquina. Se usa para avisar antes de compilar."""
    colores_por_paleta: int = 16        # incluyendo el transparente
    paletas: int = 256
    sprites: int = 96
    tiles: int = 65536
    colores_en_pantalla: int = 4096


@dataclass
class Salida:
    """Lo que produce un sistema al compilar."""
    archivos: Dict[str, str] = field(default_factory=dict)      # texto (codigo)
    binarios: Dict[str, bytes] = field(default_factory=dict)    # datos y ROMs
    resumen: List[str] = field(default_factory=list)            # que contar al usuario
    avisos: List[str] = field(default_factory=list)


class Sistema:
    """Interfaz que implementa cada maquina."""

    nombre = "generico"
    # Si esta maquina ya sabe dibujar la carretera en perspectiva de un juego
    # de conducir. Las que no, compilan el juego igual y se juega igual, pero
    # en pantalla sale el mapa -el trazado- en vez de la carretera, y el
    # compilador lo dice al compilar en vez de dejar que se descubra al
    # arrancar la ROM.
    dibuja_carreteras = False
    titulo = "sistema generico"
    cpu = "68000"
    pantalla: Tuple[int, int] = (320, 224)
    limites = Limites()
    # archivos del motor que se copian al proyecto generado
    archivos_motor: List[Tuple[str, str]] = []
    extension_ejecutable = "bin"
    # donde deja `make` el cartucho o el ejecutable, dentro del proyecto generado
    carpeta_salida = "rom"
    # como se llama lo que sale, con su articulo, para poder decirselo al
    # usuario: no todas las maquinas hacen una ROM (el Amiga hace un disquete)
    nombre_binario = "la ROM"
    # como dibuja los actores, para el listado: las que no tienen sprites no
    # los dibujan todas igual (el Amiga tiene blitter y el Atari ST no tiene
    # nada). Solo se usa cuando `limites.sprites` es cero.
    dibujo_actores = "actores dibujados con el blitter"
    # lo que hay que saber de esta maquina y no cabe en los limites: que hace
    # con el parallax, con que chip suena y si tiene modos que elegir. Lo
    # imprime `ngplat sistemas`.
    notas: List[str] = []

    # si esta maquina toca sonido grabado. Las que no, avisan de los efectos
    # que se quedarian mudos por no llevar notas al lado.
    toca_muestras = False

    def comprobar(self, build: Build) -> List[str]:
        """Avisos propios del sistema (o ProjectError si algo no cabe)."""
        return []

    @staticmethod
    def dibuja_el_mapa(build: Build) -> bool:
        """Si esta maquina va a pintar el mapa del nivel en el fondo.

        En nueve generos de diez, si: el mapa **es** el escenario. En un juego
        de conducir, no: ahi el mapa es el trazado de la carretera -por donde
        pasa y donde esta la hierba- y lo que se ve es la carretera en
        perspectiva, que es otra imagen. El mapa se sigue pisando casilla a
        casilla, pero no se dibuja ni una.

        Sirve para no aplicar a un circuito los limites del plano de fondo:
        un trazado de ciento setenta filas no cabe en el plano de la Mega
        Drive, y no hace ninguna falta que quepa."""
        return build.project.view != "carretera"

    def aviso_de_muestras(self, build: Build, porque: str) -> List[str]:
        """El aviso de los efectos que en esta maquina no van a sonar.

        Solo los que son **solo** muestra: si el efecto trae tambien notas,
        esas notas son el recambio y se oye eso."""
        if self.toca_muestras:
            return []
        mudos = [n for n, e in build.project.sound.efectos.items()
                 if e.digital and not e.pasos]
        if not mudos:
            return []
        return ["%s no toca muestras digitales (%s), asi que %s no sonara. "
                "Ponle notas al lado de la muestra ('notas:', 'tipo: barrido' o "
                "'tipo: ruido') y sonaran esas"
                % (self.titulo, porque, ", ".join("'%s'" % n for n in mudos))]

    def generar(self, build: Build, rom_id: str) -> Salida:
        raise NotImplementedError

    # --- utilidades comunes -------------------------------------------

    @staticmethod
    def error(mensaje: str, pista: Optional[str] = None) -> None:
        raise ProjectError(mensaje, hint=pista)


_SISTEMAS: Dict[str, Sistema] = {}


def registrar(sistema: Sistema) -> Sistema:
    _SISTEMAS[sistema.nombre] = sistema
    return sistema


def obtener(nombre: str) -> Sistema:
    clave = (nombre or "neogeo").strip().lower().replace(" ", "").replace("-", "")
    alias = {
        "neogeo": "neogeo", "neo": "neogeo", "aes": "neogeo", "mvs": "neogeo",
        "megadrive": "megadrive", "genesis": "megadrive", "md": "megadrive",
        "segamegadrive": "megadrive", "segagenesis": "megadrive",
        "amiga": "amiga", "a500": "amiga", "commodoreamiga": "amiga",
        "jaguar": "jaguar", "atarijaguar": "jaguar", "jag": "jaguar", "j64": "jaguar",
        "atarist": "atarist", "st": "atarist", "520st": "atarist",
        "1040st": "atarist", "stf": "atarist", "ste": "atarist",
        "x68000": "x68000", "x68k": "x68000", "sharpx68000": "x68000",
        "x68030": "x68000",
    }
    clave = alias.get(clave, clave)
    if clave not in _SISTEMAS:
        raise ProjectError(
            "no conozco el sistema '%s'" % nombre,
            hint="sistemas disponibles: %s" % ", ".join(sorted(_SISTEMAS)),
        )
    return _SISTEMAS[clave]


def disponibles() -> List[Sistema]:
    return [_SISTEMAS[nombre] for nombre in sorted(_SISTEMAS)]
