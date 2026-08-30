"""NeoPlat: kit para crear juegos de plataformas 2D que compilan para Neo Geo.

Modulos principales:
  project  - lee y valida `game.yaml`
  levels   - convierte mapas ASCII en tilemaps + tabla de spawns
  gfx      - convierte PNG a paletas y tiles de Neo Geo (C ROM / S ROM)
  codegen  - genera el codigo C del juego para el motor
  preview  - genera un preview jugable en el navegador
  cli      - la orden `ngplat`
"""

# La version del kit. Sube cada vez que se cambia algo que se reparte, y va en
# el nombre de los paquetes (neoplat-kit-1.7.zip) y en `ngplat --version`, para
# saber sin abrir nada que version se esta probando. El historial de cada una
# esta en CAMBIOS.md.
__version__ = "1.7"
