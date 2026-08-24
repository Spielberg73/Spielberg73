"""Errores de usuario con mensajes claros (nunca trazas de Python)."""

from __future__ import annotations

from typing import List, Optional


class ProjectError(Exception):
    """Fallo en el proyecto del usuario: se muestra bonito y sin traza."""

    def __init__(self, message: str, hint: Optional[str] = None, where: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.where = where

    def render(self) -> str:
        lines: List[str] = []
        head = "error: %s" % self.message
        if self.where:
            head = "error en %s: %s" % (self.where, self.message)
        lines.append(head)
        if self.hint:
            lines.append("  pista: %s" % self.hint)
        return "\n".join(lines)
