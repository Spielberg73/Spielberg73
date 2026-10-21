"""El manual encuadernado: los Markdown del kit en un solo PDF.

Junta los documentos **en orden**, les pone portada e indice y saca un PDF. Hay
uno por idioma: el castellano sale de la carpeta `docs/` y el ingles de
`docs/en/`, que es la traduccion.

Por que un renderizador de Markdown propio y no pandoc: por lo mismo que el
codec de ADPCM y el generador de ISO son de la casa. El Markdown que se usa en
el manual es poco y conocido -se puede contar: cabeceras, parrafos, negrita,
codigo en linea, bloques de codigo, tablas, listas, citas, enlaces y <kbd>-, y
asi `make manual` no pide nada mas que lo que ya hay. El renderizador **para en
seco** si se encuentra algo que no sabe convertir en vez de tragarselo: un
manual con un trozo mal puesto no se nota hasta que alguien lo lee en papel.

Lo unico de fuera es el motor de PDF, y ahi no hay nada que hacer: hace falta
alguien que sepa partir el texto en paginas y escribir un PDF. Se usa
**WeasyPrint** (`pip3 install weasyprint`), que entiende las cajas de margen de
CSS y por eso sabe numerar las paginas y poner el numero en el indice.
"""

import html
import io
import os
import re
import shutil
import subprocess
import unicodedata
from typing import Dict, List, Optional, Tuple


class ManualError(Exception):
    """Algo que el manual no puede hacer, dicho de forma que se entienda."""

    def __init__(self, mensaje: str, pista: str = "") -> None:
        super().__init__(mensaje)
        self.pista = pista


# --- que documentos, y en que orden -------------------------------------
#
# El orden es el de leerlos, no el alfabetico: primero por que existe el kit,
# luego como se usa, luego la referencia y al final una maquina por capitulo.
# `docs/README.md` va primero a proposito: es el indice de la carpeta, y en el
# PDF se convierte en la pagina de "por donde empezar" con los enlaces ya
# apuntando a los capitulos de dentro.

DOCUMENTOS: Tuple[Tuple[str, str, str], ...] = (
    # el original (castellano), la clave del capitulo, y como se llama en
    # docs/en/. El README del kit se llama ahi `neoplat.md` porque el
    # `README.md` de esa carpeta ya es el indice del manual en ingles.
    ("docs/README.md", "indice", "README.md"),
    ("README.md", "kit", "neoplat.md"),
    ("docs/tutorial.md", "tutorial", "tutorial.md"),
    ("docs/editor.md", "editor", "editor.md"),
    ("docs/formato.md", "formato", "formato.md"),
    ("docs/sonido.md", "sonido", "sonido.md"),
    ("docs/neogeo.md", "neogeo", "neogeo.md"),
    ("docs/megadrive.md", "megadrive", "megadrive.md"),
    ("docs/amiga.md", "amiga", "amiga.md"),
    ("docs/atarist.md", "atarist", "atarist.md"),
    ("docs/jaguar.md", "jaguar", "jaguar.md"),
    ("docs/x68000.md", "x68000", "x68000.md"),
)


def ruta_del_documento(ruta: str, ingles: str, idioma: str) -> str:
    """Donde esta ese documento en ese idioma, desde la raiz del kit."""
    if idioma == "es":
        return ruta
    return os.path.join("docs", "en", ingles)

IDIOMAS: Dict[str, Dict[str, str]] = {
    "es": {
        "lang": "es",
        "titulo": "NeoPlat",
        "subtitulo": "Juegos 2D para siete máquinas de 68000, sin programar",
        "indice": "Índice",
        "version": "Versión",
        "pie": "El manual de NeoPlat",
        "nota": ("El original de este manual son los Markdown de `docs/`. "
                 "Esto es el mismo texto encuadernado: si los dos no dicen lo "
                 "mismo, manda el Markdown."),
    },
    "en": {
        "lang": "en",
        "titulo": "NeoPlat",
        "subtitulo": "2D games for seven 68000 machines, without programming",
        "indice": "Contents",
        "version": "Version",
        "pie": "The NeoPlat manual",
        "nota": ("The source of this manual is the Markdown in `docs/`, in "
                 "Spanish. This is a translation: where the two disagree, the "
                 "Spanish is the original."),
    },
}


# --- el renderizador de Markdown ----------------------------------------

def _ancla(texto: str) -> str:
    """El identificador que GitHub le pone a una cabecera.

    Se copia su regla porque los enlaces del manual estan escritos para
    GitHub: minusculas, fuera lo que no sea letra, numero, guion o espacio, y
    los espacios a guiones. Las tildes **se quedan** (GitHub las deja), asi
    que `#amiga_ram-a-que-amiga` no vale y `#amiga_ram-a-qué-amiga` si.
    """
    t = re.sub(r"`|\*|\[|\]|\(.*?\)", "", texto).strip().lower()
    t = "".join(c for c in t if c.isalnum() or c in " -_"
                or unicodedata.category(c).startswith("L"))
    return re.sub(r"\s+", "-", t.strip())


def _en_linea(texto: str, enlace) -> str:
    """Lo que va dentro de una linea: negrita, cursiva, codigo y enlaces.

    El codigo en linea se aparta **antes** de tocar nada mas y se devuelve al
    final: dentro de un `` `...` `` un asterisco es un asterisco y un
    `<carpeta>` es texto, no una etiqueta.
    """
    trozos: List[str] = []

    def apartar(m):
        trozos.append(m.group(1))
        return "\x00%d\x00" % (len(trozos) - 1)

    texto = re.sub(r"`([^`]+)`", apartar, texto)
    texto = html.escape(texto, quote=False)
    # <kbd> es la unica etiqueta de verdad que hay en el manual
    texto = texto.replace("&lt;kbd&gt;", "<kbd>").replace("&lt;/kbd&gt;", "</kbd>")
    texto = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                   lambda m: enlace(m.group(1), m.group(2)), texto)
    texto = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", texto)
    return re.sub(r"\x00(\d+)\x00",
                  lambda m: "<code>%s</code>"
                            % html.escape(trozos[int(m.group(1))], quote=False),
                  texto)


def _tabla(filas: List[str], enlace) -> str:
    """Una tabla de GitHub: cabecera, la fila de guiones y el cuerpo.

    La fila de guiones puede llevar dos puntos para alinear (`|---:|`), y se
    respeta, que en una tabla de cifras es la diferencia entre poder leerla y
    no.
    """
    def celdas(linea: str) -> List[str]:
        linea = linea.strip()
        if linea.startswith("|"):
            linea = linea[1:]
        if linea.endswith("|"):
            linea = linea[:-1]
        return [c.strip() for c in linea.split("|")]

    cabecera, guiones, cuerpo = celdas(filas[0]), celdas(filas[1]), filas[2:]
    alineacion = []
    for g in guiones:
        if g.startswith(":") and g.endswith(":"):
            alineacion.append(" style=\"text-align:center\"")
        elif g.endswith(":"):
            alineacion.append(" style=\"text-align:right\"")
        else:
            alineacion.append("")
    partes = ["<table>", "<thead><tr>"]
    for i, c in enumerate(cabecera):
        partes.append("<th%s>%s</th>" % (alineacion[i] if i < len(alineacion)
                                         else "", _en_linea(c, enlace)))
    partes.append("</tr></thead><tbody>")
    for fila in cuerpo:
        partes.append("<tr>")
        for i, c in enumerate(celdas(fila)):
            partes.append("<td%s>%s</td>"
                          % (alineacion[i] if i < len(alineacion) else "",
                             _en_linea(c, enlace)))
        partes.append("</tr>")
    partes.append("</tbody></table>")
    return "".join(partes)


def md_a_html(texto: str, enlace=None, nivel_base: int = 0,
              prefijo: str = "") -> Tuple[str, List[Tuple[int, str, str]]]:
    """Convierte un documento del manual en HTML, y devuelve sus cabeceras.

    `nivel_base` baja todas las cabeceras ese numero de niveles: en el PDF el
    `#` de cada documento es un capitulo, asi que sus `##` tienen que ser `h3`
    y no `h2`, o el indice sale plano.

    Para en seco con lo que no sabe hacer. La lista que devuelve es
    (nivel, ancla, titulo) de cada cabecera, que es de lo que sale el indice.
    """
    if enlace is None:
        def enlace(txt, destino):
            return "<a href=\"%s\">%s</a>" % (html.escape(destino, quote=True), txt)
    salida: List[str] = []
    cabeceras: List[Tuple[int, str, str]] = []
    lineas = texto.split("\n")
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        # --- bloque de codigo ---
        if linea.startswith("```"):
            j = i + 1
            while j < len(lineas) and not lineas[j].startswith("```"):
                j += 1
            if j >= len(lineas):
                raise ManualError(
                    "un bloque de codigo que se abre en la linea %d y no se "
                    "cierra" % (i + 1),
                    pista="falta una linea con ``` al final del bloque")
            dentro = "\n".join(lineas[i + 1:j])
            salida.append("<pre><code>%s</code></pre>"
                          % html.escape(dentro, quote=False))
            i = j + 1
            continue
        # --- cabecera ---
        m = re.match(r"^(#{1,6}) (.+)$", linea)
        if m:
            nivel = len(m.group(1)) + nivel_base
            if nivel > 6:
                nivel = 6
            ancla = prefijo + _ancla(m.group(2))
            cabeceras.append((nivel, ancla, re.sub(r"`|\*\*|\*", "", m.group(2))))
            salida.append("<h%d id=\"%s\">%s</h%d>"
                          % (nivel, html.escape(ancla, quote=True),
                             _en_linea(m.group(2), enlace), nivel))
            i += 1
            continue
        # --- regla ---
        if re.match(r"^-{3,}$", linea.strip()):
            salida.append("<hr>")
            i += 1
            continue
        # --- tabla ---
        if (linea.lstrip().startswith("|") and i + 1 < len(lineas)
                and re.match(r"^\s*\|[\s:|-]+\|?\s*$", lineas[i + 1])):
            j = i
            while j < len(lineas) and lineas[j].lstrip().startswith("|"):
                j += 1
            salida.append(_tabla(lineas[i:j], enlace))
            i = j
            continue
        # --- cita ---
        if linea.startswith(">"):
            j = i
            dentro = []
            while j < len(lineas) and (lineas[j].startswith(">")
                                       or (dentro and lineas[j].strip()
                                           and not lineas[j].startswith(("#", "|", "```")))):
                dentro.append(re.sub(r"^> ?", "", lineas[j]))
                j += 1
            cuerpo, _ = md_a_html("\n".join(dentro), enlace, nivel_base, prefijo)
            salida.append("<blockquote>%s</blockquote>" % cuerpo)
            i = j
            continue
        # --- listas ---
        m = re.match(r"^(\s*)([-*]|\d+[.)]) (.*)$", linea)
        if m:
            i, trozo = _lista(lineas, i, enlace, nivel_base, prefijo)
            salida.append(trozo)
            continue
        # --- blanco ---
        if not linea.strip():
            i += 1
            continue
        # --- parrafo: hasta el siguiente blanco o bloque ---
        j = i
        dentro = []
        while (j < len(lineas) and lineas[j].strip()
               and not lineas[j].startswith(("#", ">", "```"))
               and not lineas[j].lstrip().startswith("|")
               and not re.match(r"^(\s*)([-*]|\d+[.)]) ", lineas[j])
               and not re.match(r"^-{3,}$", lineas[j].strip())):
            dentro.append(lineas[j])
            j += 1
        salida.append("<p>%s</p>" % _en_linea(" ".join(
            l.strip() for l in dentro), enlace))
        i = j
    return "\n".join(salida), cabeceras


def _lista(lineas: List[str], i: int, enlace, nivel_base: int,
           prefijo: str) -> Tuple[int, str]:
    """Una lista, con las de dentro y los parrafos que cuelgan de un punto.

    Lo que decide si algo esta dentro de otra cosa es la sangria, como en el
    propio Markdown: un punto sangrado mas que el anterior abre una lista
    dentro, y una linea sangrada que no empieza por guion es la continuacion
    del punto de arriba.
    """
    m = re.match(r"^(\s*)([-*]|\d+[.)]) (.*)$", lineas[i])
    sangria = len(m.group(1))
    numerada = not m.group(2) in ("-", "*")
    puntos: List[List[str]] = []
    while i < len(lineas):
        linea = lineas[i]
        m = re.match(r"^(\s*)([-*]|\d+[.)]) (.*)$", linea)
        if m and len(m.group(1)) == sangria:
            puntos.append([m.group(3)])
            i += 1
            continue
        if not linea.strip():
            # un blanco solo corta la lista si lo que viene no esta sangrado
            if (i + 1 < len(lineas) and lineas[i + 1].strip()
                    and len(lineas[i + 1]) - len(lineas[i + 1].lstrip()) > sangria):
                puntos[-1].append("")
                i += 1
                continue
            break
        if puntos and len(linea) - len(linea.lstrip()) > sangria:
            puntos[-1].append(linea[sangria + 2:] if linea[sangria:sangria + 2]
                              .strip() == "" else linea.strip())
            i += 1
            continue
        if puntos and linea.strip() and not m:
            puntos[-1].append(linea.strip())   # continuacion sin sangrar
            i += 1
            continue
        break
    etiqueta = "ol" if numerada else "ul"
    partes = ["<%s>" % etiqueta]
    for punto in puntos:
        cuerpo, _ = md_a_html("\n".join(punto), enlace, nivel_base, prefijo)
        # un punto de una sola linea no necesita el <p>: aprieta la lista
        if cuerpo.count("<p>") == 1 and cuerpo.startswith("<p>") \
                and cuerpo.endswith("</p>"):
            cuerpo = cuerpo[3:-4]
        partes.append("<li>%s</li>" % cuerpo)
    partes.append("</%s>" % etiqueta)
    return i, "".join(partes)


# --- juntar los documentos ----------------------------------------------

def _resolver(destino: str, documento: str, anclas: Dict[str, str],
              documentos: Dict[str, str]) -> Optional[str]:
    """Donde apunta dentro del PDF un enlace que estaba escrito para GitHub.

    Un `[algo](formato.md#coche)` del tutorial tiene que acabar en el `#coche`
    del capitulo de formato, que en el PDF es otro trozo del mismo archivo. Lo
    que no se puede resolver -una carpeta, un archivo que no es del manual-
    devuelve None y el enlace se queda en texto: mejor sin enlace que con uno
    que no lleva a ninguna parte.
    """
    if destino.startswith(("http://", "https://", "mailto:")):
        return destino
    archivo, _, ancla = destino.partition("#")
    if not archivo:
        clave = "%s|%s" % (documento, ancla)
        return "#" + anclas[clave] if clave in anclas else None
    base = os.path.dirname(documento)
    ruta = os.path.normpath(os.path.join(base, archivo))
    if ruta not in documentos:
        return None
    if not ancla:
        return "#" + documentos[ruta]
    clave = "%s|%s" % (ruta, ancla)
    return "#" + anclas[clave] if clave in anclas else "#" + documentos[ruta]


def construir_html(raiz: str, idioma: str, version: str) -> str:
    """El manual entero en un HTML, listo para que lo pagine WeasyPrint."""
    if idioma not in IDIOMAS:
        raise ManualError("no se conoce el idioma '%s'" % idioma,
                          pista="hay %s" % ", ".join(sorted(IDIOMAS)))
    txt = IDIOMAS[idioma]

    # 1) leerlos, y de paso apuntar las anclas de todas las cabeceras: los
    #    enlaces de un capitulo a otro no se pueden resolver hasta tenerlas
    #    todas, porque el tutorial enlaza a formato y formato al tutorial.
    crudos: List[Tuple[str, str, str, str]] = []   # ruta, clave, prefijo, texto
    documentos: Dict[str, str] = {}
    anclas: Dict[str, str] = {}
    for ruta, clave, ingles in DOCUMENTOS:
        real = ruta_del_documento(ruta, ingles, idioma)
        entero = os.path.join(raiz, real)
        if not os.path.exists(entero):
            raise ManualError(
                "falta %s" % real,
                pista=("el manual en %s no esta completo; el castellano esta en "
                       "docs/ y el ingles en docs/en/" % idioma))
        with io.open(entero, encoding="utf-8") as fh:
            texto = fh.read()
        prefijo = clave + "--"
        for linea in texto.split("\n"):
            m = re.match(r"^#{1,6} (.+)$", linea)
            if m:
                anclas["%s|%s" % (ruta, _ancla(m.group(1)))] = prefijo + _ancla(m.group(1))
                # un enlace al documento entero cae en su primera cabecera, que
                # es el titulo del capitulo
                documentos.setdefault(ruta, prefijo + _ancla(m.group(1)))
        if ruta not in documentos:
            raise ManualError("%s no tiene ni una cabecera" % real,
                              pista="el capitulo necesita un titulo con #")
        crudos.append((ruta, clave, prefijo, texto))

    # 2) convertirlos, ya con las anclas de todos
    capitulos: List[str] = []
    indice: List[Tuple[int, str, str]] = []
    for ruta, clave, prefijo, texto in crudos:
        def enlace(etiqueta, destino, _ruta=ruta):
            resuelto = _resolver(destino, _ruta, anclas, documentos)
            if resuelto is None:
                return etiqueta
            return "<a href=\"%s\">%s</a>" % (html.escape(resuelto, quote=True),
                                              etiqueta)
        cuerpo, cabeceras = md_a_html(texto, enlace, nivel_base=0, prefijo=prefijo)
        # la primera cabecera del documento es el titulo del capitulo
        cuerpo = cuerpo.replace("<h1 id=\"%s\"" % cabeceras[0][1],
                                "<h1 class=\"capitulo\" id=\"%s\"" % cabeceras[0][1], 1)
        capitulos.append("<section class=\"doc\">%s</section>" % cuerpo)
        for nivel, ancla, titulo in cabeceras:
            if nivel <= 2:
                indice.append((nivel, ancla, titulo))

    partes = [_cabeza(txt, version), _portada(txt, version),
              _indice(txt, indice)]
    partes.extend(capitulos)
    partes.append("</body></html>")
    return "\n".join(partes)


def _cabeza(txt: Dict[str, str], version: str) -> str:
    return (
        "<!doctype html>\n<html lang=\"%s\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<title>%s %s</title>\n<style>\n%s</style>\n</head>\n<body>"
        % (txt["lang"], txt["titulo"], version, HOJA))


def _portada(txt: Dict[str, str], version: str) -> str:
    nota, _ = md_a_html(txt["nota"])
    return ("<section class=\"portada\">"
            "<h1>%s</h1><p class=\"lema\">%s</p>"
            "<p class=\"version\">%s %s</p>"
            "<div class=\"nota\">%s</div></section>"
            % (html.escape(txt["titulo"]), html.escape(txt["subtitulo"]),
               html.escape(txt["version"]), html.escape(version), nota))


def _indice(txt: Dict[str, str], indice: List[Tuple[int, str, str]]) -> str:
    partes = ["<section class=\"indice\"><h1>%s</h1><ul>"
              % html.escape(txt["indice"])]
    for nivel, ancla, titulo in indice:
        partes.append("<li class=\"n%d\"><a href=\"#%s\">%s</a></li>"
                      % (nivel, html.escape(ancla, quote=True),
                         html.escape(titulo)))
    partes.append("</ul></section>")
    return "".join(partes)


# --- la hoja de estilo --------------------------------------------------
#
# Lo que se pide a un manual en papel: que el texto se lea de un tiron, que los
# bloques de codigo no se partan por la mitad si caben enteros, que las tablas
# repitan la cabecera al cambiar de pagina y que el indice lleve el numero de
# pagina. Lo ultimo es `target-counter`, que es justo lo que WeasyPrint sabe
# hacer y un navegador no.

HOJA = """
@page {
  size: A4;
  margin: 22mm 20mm 20mm 20mm;
  @bottom-center { content: counter(page); font: 8.5pt "DejaVu Sans", sans-serif;
                   color: #8a8a94; }
}
@page :first { @bottom-center { content: none; } }

html { font-size: 10.5pt; }
body { font-family: "DejaVu Serif", Georgia, serif; line-height: 1.5;
       color: #1a1a1f; hyphens: auto; text-align: justify; }

h1, h2, h3, h4, h5, h6 { font-family: "DejaVu Sans", Helvetica, sans-serif;
  line-height: 1.25; text-align: left; hyphens: none; break-after: avoid; }
h1.capitulo { break-before: right; font-size: 22pt; margin: 0 0 1.2em 0;
  padding-bottom: .35em; border-bottom: 2.5pt solid #1a1a1f; }
h2 { font-size: 14pt; margin: 1.8em 0 .5em; }
h3 { font-size: 11.5pt; margin: 1.5em 0 .4em; }
h4 { font-size: 10.5pt; margin: 1.3em 0 .3em; color: #3a3a46; }

p { margin: 0 0 .7em; orphans: 2; widows: 2; }

code { font-family: "DejaVu Sans Mono", monospace; font-size: .86em;
       background: #f1f1f4; padding: .5pt 2pt; border-radius: 2pt;
       hyphens: none; }
pre { background: #f6f6f8; border-left: 2.5pt solid #c8c8d2;
      padding: 6pt 8pt; margin: .8em 0; break-inside: avoid;
      font-size: 8.2pt; line-height: 1.35; overflow-wrap: break-word; }
pre code { background: none; padding: 0; font-size: 1em; }

table { border-collapse: collapse; width: 100%; margin: .9em 0;
        font-size: 9pt; text-align: left; }
thead { background: #ececf1; }
th, td { border: .5pt solid #c8c8d2; padding: 3pt 5pt; vertical-align: top;
         text-align: left; hyphens: none; }
th { font-family: "DejaVu Sans", sans-serif; font-size: 8.5pt; }

blockquote { margin: .9em 0; padding: 5pt 10pt; background: #f4f4f8;
             border-left: 2.5pt solid #9a9aa8; break-inside: avoid; }
blockquote p:last-child { margin-bottom: 0; }

ul, ol { margin: 0 0 .8em; padding-left: 1.3em; }
li { margin-bottom: .3em; }

hr { border: none; border-top: .5pt solid #c8c8d2; margin: 1.4em 0; }
kbd { font-family: "DejaVu Sans Mono", monospace; font-size: .82em;
      border: .5pt solid #9a9aa8; border-bottom-width: 1.5pt;
      border-radius: 2.5pt; padding: .5pt 3pt; background: #fafafc; }
a { color: #1a1a1f; text-decoration: none; }

/* --- la portada --- */
.portada { break-after: right; padding-top: 55mm; text-align: center; }
.portada h1 { font-size: 46pt; margin: 0; letter-spacing: -1pt;
              text-align: center; border: none; }
.portada .lema { font-size: 12pt; color: #4a4a58; margin: .5em 0 0;
                 text-align: center; }
.portada .version { font-family: "DejaVu Sans", sans-serif; font-size: 10pt;
                    color: #8a8a94; margin-top: 2.5em; text-align: center; }
.portada .nota { margin: 45mm auto 0; max-width: 105mm; font-size: 8.5pt;
                 color: #6a6a78; text-align: left; }
.portada .nota p { margin: 0; }

/* --- el indice, con el numero de pagina --- */
.indice { break-after: right; }
.indice h1 { font-size: 20pt; margin: 0 0 1em; }
.indice ul { list-style: none; padding: 0; margin: 0;
             font-family: "DejaVu Sans", sans-serif; }
.indice li { margin: 0; break-inside: avoid; }
.indice li a::after { content: " " leader('.') " " target-counter(attr(href), page);
                      color: #8a8a94; }
.indice li.n1 { font-size: 11pt; font-weight: bold; margin-top: 1.1em; }
.indice li.n2 { font-size: 9pt; padding-left: 7mm; color: #3a3a46; }
"""


# --- sacar el PDF -------------------------------------------------------

def motor() -> Optional[str]:
    """Donde esta WeasyPrint, o None si no esta instalado."""
    return shutil.which("weasyprint")


def generar(raiz: str, idioma: str, version: str, salida: str) -> str:
    """Escribe el PDF y devuelve por donde ha quedado."""
    quien = motor()
    if not quien:
        raise ManualError(
            "no esta instalado WeasyPrint, que es quien pagina el PDF",
            pista="pip3 install weasyprint")
    pagina = construir_html(raiz, idioma, version)
    carpeta = os.path.dirname(os.path.abspath(salida))
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    fuente = os.path.splitext(salida)[0] + ".html"
    with io.open(fuente, "w", encoding="utf-8") as fh:
        fh.write(pagina)
    hecho = subprocess.run([quien, "--quiet", "-u", raiz + os.sep, fuente, salida],
                           capture_output=True, text=True)
    if hecho.returncode != 0:
        raise ManualError("WeasyPrint no ha podido con el manual",
                          pista=(hecho.stderr or hecho.stdout).strip()[:400])
    os.remove(fuente)
    return salida
