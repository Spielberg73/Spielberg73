"""Analizador de un subconjunto de YAML, para no depender de PyYAML.

Cubre exactamente lo que usa un `game.yaml` de NeoPlat:

  - mapas y listas anidados por indentacion
  - colecciones en linea: ``[1, 2]`` y ``{a: 1, b: 2}``
  - cadenas con y sin comillas, numeros, booleanos (``true``/``false``/
    ``si``/``no``) y ``null``
  - escalares de bloque ``|`` y ``|-`` (imprescindibles para los mapas ASCII)
  - comentarios con ``#`` y documentos que empiezan por ``---``

Si PyYAML esta instalado, `ngplat` lo usa; este modulo es la alternativa
para que el kit funcione con Python "de fabrica".
"""

from __future__ import annotations

from typing import Any, List, Tuple


class YamlError(Exception):
    """Error de sintaxis con numero de linea."""


# Se usan las mismas palabras que YAML 1.1 (las que entiende PyYAML). El "si"
# del espanol se resuelve mas arriba, en project.Node.bool_, para que los dos
# analizadores devuelvan exactamente lo mismo.
TRUE_WORDS = {"true", "yes", "on"}
FALSE_WORDS = {"false", "no", "off"}
NULL_WORDS = {"", "null", "~"}


def _strip_comment(line: str) -> str:
    out: List[str] = []
    quote = ""
    for i, ch in enumerate(line):
        if quote:
            out.append(ch)
            if ch == quote and (i == 0 or line[i - 1] != "\\"):
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _split_top(text: str, sep: str) -> List[str]:
    """Parte por `sep` respetando comillas y colecciones anidadas."""
    parts: List[str] = []
    depth = 0
    quote = ""
    current: List[str] = []
    for ch in text:
        if quote:
            current.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            current.append(ch)
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    parts.append("".join(current))
    return parts


def _split_key(text: str) -> Tuple[str, str]:
    """Separa ``clave: valor`` en el primer ':' de nivel superior."""
    depth = 0
    quote = ""
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == ":" and depth == 0:
            if i + 1 < len(text) and text[i + 1] not in " \t":
                continue  # p.ej. una hora "12:30" sin comillas
            return text[:i].strip(), text[i + 1:].strip()
    raise YamlError("se esperaba 'clave: valor' en %r" % text)


def _scalar(text: str, line_no: int) -> Any:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        body = text[1:-1]
        if text[0] == '"':
            body = body.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
        return body
    if text.startswith("[") or text.startswith("{"):
        return _flow(text, line_no)
    low = text.lower()
    if low in NULL_WORDS:
        return None
    if low in TRUE_WORDS:
        return True
    if low in FALSE_WORDS:
        return False
    try:
        if low.startswith("0x"):
            return int(low, 16)
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def _flow(text: str, line_no: int) -> Any:
    text = text.strip()
    if text.startswith("["):
        if not text.endswith("]"):
            raise YamlError("linea %d: falta ']' en %r" % (line_no, text))
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_scalar(p, line_no) for p in _split_top(inner, ",")]
    if text.startswith("{"):
        if not text.endswith("}"):
            raise YamlError("linea %d: falta '}' en %r" % (line_no, text))
        inner = text[1:-1].strip()
        out: dict = {}
        if not inner:
            return out
        for part in _split_top(inner, ","):
            key, value = _split_key(part)
            out[str(_scalar(key, line_no))] = _scalar(value, line_no)
        return out
    raise YamlError("linea %d: coleccion en linea invalida: %r" % (line_no, text))


class _Line:
    __slots__ = ("indent", "text", "no")

    def __init__(self, indent: int, text: str, no: int):
        self.indent = indent
        self.text = text
        self.no = no


class _Parser:
    def __init__(self, source: str):
        self.raw = source.split("\n")
        self.lines: List[_Line] = []
        for i, raw_line in enumerate(self.raw):
            if "\t" in raw_line[: len(raw_line) - len(raw_line.lstrip())]:
                raise YamlError(
                    "linea %d: usa espacios, no tabuladores, para la indentacion" % (i + 1)
                )
            text = _strip_comment(raw_line)
            if not text.strip() or text.strip() == "---":
                continue
            self.lines.append(_Line(len(text) - len(text.lstrip()), text.strip(), i + 1))
        self.pos = 0

    def parse(self) -> Any:
        if not self.lines:
            return None
        value = self.parse_block(self.lines[0].indent)
        if self.pos < len(self.lines):
            raise YamlError(
                "linea %d: indentacion inesperada" % self.lines[self.pos].no
            )
        return value

    def parse_block(self, indent: int) -> Any:
        line = self.lines[self.pos]
        if line.text.startswith("- "):
            return self.parse_list(indent)
        return self.parse_map(indent)

    def parse_list(self, indent: int) -> List[Any]:
        out: List[Any] = []
        while self.pos < len(self.lines):
            line = self.lines[self.pos]
            if line.indent < indent:
                break
            if line.indent > indent:
                raise YamlError("linea %d: indentacion inesperada en la lista" % line.no)
            if not (line.text.startswith("- ") or line.text == "-"):
                break
            item_text = line.text[1:].strip()
            self.pos += 1
            if not item_text:
                out.append(self.parse_child(indent))
            elif ":" in item_text and not item_text.startswith(("[", "{", '"', "'")):
                # "- clave: valor" abre un mapa alineado tras el guion
                child_indent = line.indent + 2
                self.lines.insert(self.pos, _Line(child_indent, item_text, line.no))
                out.append(self.parse_map(child_indent))
            else:
                out.append(self.parse_inline(item_text, line))
        return out

    def parse_map(self, indent: int) -> dict:
        out: dict = {}
        while self.pos < len(self.lines):
            line = self.lines[self.pos]
            if line.indent < indent:
                break
            if line.indent > indent:
                raise YamlError("linea %d: indentacion inesperada" % line.no)
            if line.text.startswith("- "):
                break
            key_text, value_text = _split_key(line.text)
            key = str(_scalar(key_text, line.no))
            self.pos += 1
            if value_text == "" or value_text is None:
                out[key] = self.parse_child(indent)
            elif value_text in ("|", "|-", "|+", ">", ">-"):
                out[key] = self.parse_block_scalar(indent, value_text, line.no)
            else:
                out[key] = self.parse_inline(value_text, line)
        return out

    def parse_child(self, indent: int) -> Any:
        if self.pos >= len(self.lines) or self.lines[self.pos].indent <= indent:
            return None
        return self.parse_block(self.lines[self.pos].indent)

    def parse_inline(self, text: str, line: _Line) -> Any:
        if text in ("|", "|-", "|+", ">", ">-"):
            return self.parse_block_scalar(line.indent, text, line.no)
        return _scalar(text, line.no)

    def parse_block_scalar(self, indent: int, style: str, line_no: int) -> str:
        """Lee un escalar de bloque desde el texto original (conserva espacios)."""
        body: List[str] = []
        idx = line_no  # las lineas originales van 1..n; la siguiente es raw[line_no]
        block_indent = None
        while idx < len(self.raw):
            raw_line = self.raw[idx]
            stripped = raw_line.strip()
            current_indent = len(raw_line) - len(raw_line.lstrip())
            if stripped and current_indent <= indent:
                break
            if stripped and block_indent is None:
                block_indent = current_indent
            body.append(raw_line[block_indent:] if block_indent else raw_line.strip())
            idx += 1
        # Consume las lineas del bloque tambien en la lista filtrada.
        while self.pos < len(self.lines) and self.lines[self.pos].no <= idx:
            self.pos += 1
        while body and not body[-1].strip():
            body.pop()
        text = "\n".join(body)
        if style.startswith(">"):
            text = " ".join(line.strip() for line in text.split("\n"))
        if style in ("|", ">") and text:
            text += "\n"
        return text


def loads(source: str) -> Any:
    """Analiza un documento YAML (subconjunto) y devuelve datos de Python."""
    return _Parser(source).parse()


def load_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return loads(fh.read())
