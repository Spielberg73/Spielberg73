"""Nombres que acepta cada opcion del `game.yaml`.

El lector (project.py) admite las claves en castellano y en ingles. El editor
necesita saber esos mismos nombres para dos cosas: encontrar la opcion dentro
del archivo del usuario (aunque la haya escrito con otro nombre) y, si no
existe, escribirla con el nombre principal.

tests/test_claves.py comprueba que **todos** estos alias los entiende de verdad
el lector, para que la tabla no se quede desfasada.
"""

from __future__ import annotations

from typing import Dict, List

# {seccion: {campo: [nombres aceptados, el primero es el que se escribe]}}
CAMPOS: Dict[str, Dict[str, List[str]]] = {
    "juego": {
        "titulo": ["titulo", "title"],
        "autor": ["autor", "author"],
        "vidas": ["vidas", "lives"],
        "tiempo": ["tiempo", "time"],
        "hud": ["hud", "marcador"],
        "sistema": ["sistema", "system"],
        "fondo": ["fondo", "background"],
        "camara": ["camara", "camera"],
    },
    "jugador": {
        "velocidad": ["velocidad", "speed"],
        "aceleracion": ["aceleracion", "accel"],
        "friccion": ["friccion", "friction"],
        "control_aire": ["control_aire", "air_accel"],
        "salto": ["salto", "jump"],
        "corte_salto": ["corte_salto", "jump_cut"],
        "gravedad": ["gravedad", "gravity"],
        "max_caida": ["max_caida", "max_fall"],
        "doble_salto": ["doble_salto", "double_jump"],
        "coyote": ["coyote", "margen_salto"],
        "buffer_salto": ["buffer_salto", "jump_buffer"],
        "pisar_enemigos": ["pisar_enemigos", "pisar", "stomp"],
        "rebote": ["rebote", "bounce"],
        "vida": ["vida", "salud", "health"],
        "invulnerable": ["invulnerable", "invuln"],
    },
    "enemigo": {
        "comportamiento": ["comportamiento", "behavior"],
        "velocidad": ["velocidad", "speed"],
        "gravedad": ["gravedad", "gravity"],
        "vida": ["vida", "salud", "health"],
        "dano": ["dano", "damage"],
        "puntos": ["puntos", "score"],
        "pisable": ["pisable", "stompable"],
        "girar_en_borde": ["girar_en_borde", "edge_turn"],
        "rango": ["rango", "range"],
        "amplitud": ["amplitud", "amplitude"],
        "periodo": ["periodo", "period"],
        "salto": ["salto", "jump"],
        "intervalo": ["intervalo", "interval"],
    },
    "objeto": {
        "puntos": ["puntos", "score"],
        "efecto": ["efecto", "effect"],
        "cantidad": ["cantidad", "amount"],
    },
    "nivel": {
        "nombre": ["nombre", "name"],
        "fondo": ["fondo", "background"],
        "camara": ["camara", "camera"],
        "musica": ["musica", "music"],
        "fondos": ["fondos", "layers"],
    },
}

# Valores que admiten las opciones de tipo lista cerrada.
OPCIONES: Dict[str, List[str]] = {
    "comportamiento": ["patrulla", "volador", "perseguidor", "saltarin", "fijo"],
    "efecto": ["puntos", "vida", "salud", "llave"],
    "camara": ["scroll", "pantallas"],
}

# Rangos y paso de cada numero, para poder ofrecer controles con sentido.
RANGOS: Dict[str, Dict[str, float]] = {
    "velocidad": {"min": 0.05, "max": 8, "paso": 0.05},
    "aceleracion": {"min": 0.01, "max": 4, "paso": 0.01},
    "friccion": {"min": 0.0, "max": 4, "paso": 0.01},
    "control_aire": {"min": 0.0, "max": 4, "paso": 0.01},
    "salto": {"min": 0.5, "max": 12, "paso": 0.1},
    "corte_salto": {"min": 0.0, "max": 12, "paso": 0.1},
    "gravedad": {"min": 0.01, "max": 4, "paso": 0.01},
    "max_caida": {"min": 0.5, "max": 16, "paso": 0.5},
    "rebote": {"min": 0.0, "max": 12, "paso": 0.1},
    "coyote": {"min": 0, "max": 30, "paso": 1},
    "buffer_salto": {"min": 0, "max": 30, "paso": 1},
    "invulnerable": {"min": 0, "max": 600, "paso": 10},
    "vida": {"min": 1, "max": 9, "paso": 1},
    "vidas": {"min": 1, "max": 9, "paso": 1},
    "tiempo": {"min": 0, "max": 999, "paso": 10},
    "dano": {"min": 0, "max": 9, "paso": 1},
    "puntos": {"min": 0, "max": 9999, "paso": 10},
    "rango": {"min": 0, "max": 512, "paso": 8},
    "amplitud": {"min": 0, "max": 200, "paso": 4},
    "periodo": {"min": 8, "max": 1200, "paso": 10},
    "intervalo": {"min": 8, "max": 1200, "paso": 10},
    "cantidad": {"min": 1, "max": 9, "paso": 1},
    "gravedad_enemigo": {"min": 0, "max": 4, "paso": 0.01},
}


def tabla_para_el_editor() -> Dict[str, object]:
    """Lo que se manda al preview para que el editor pueda tocar el yaml."""
    return {"campos": CAMPOS, "opciones": OPCIONES, "rangos": RANGOS}
