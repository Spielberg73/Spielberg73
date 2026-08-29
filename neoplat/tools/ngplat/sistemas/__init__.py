"""Sistemas de destino de NeoPlat.

Importar este paquete registra todas las maquinas disponibles.
"""

from .base import Sistema, Salida, Limites, obtener, disponibles, registrar  # noqa: F401
from . import neogeo    # noqa: F401  (se registra al importarse)
from . import megadrive  # noqa: F401
from . import amiga      # noqa: F401
from . import jaguar     # noqa: F401
from . import atarist    # noqa: F401
from . import x68000     # noqa: F401
