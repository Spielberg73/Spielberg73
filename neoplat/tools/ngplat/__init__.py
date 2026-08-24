"""NeoPlat: kit para crear juegos de plataformas 2D que compilan para Neo Geo.

Modulos principales:
  project  - lee y valida `game.yaml`
  levels   - convierte mapas ASCII en tilemaps + tabla de spawns
  gfx      - convierte PNG a paletas y tiles de Neo Geo (C ROM / S ROM)
  codegen  - genera el codigo C del juego para el motor
  preview  - genera un preview jugable en el navegador
  cli      - la orden `ngplat`
"""

__version__ = "0.1.0"
