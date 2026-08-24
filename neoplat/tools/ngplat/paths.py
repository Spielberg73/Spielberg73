"""Rutas dentro del kit (el motor C, las plantillas y el preview)."""

from __future__ import annotations

import os

KIT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENGINE_DIR = os.path.join(KIT_ROOT, "engine")
PREVIEW_DIR = os.path.join(KIT_ROOT, "preview")
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
