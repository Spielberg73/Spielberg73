#!/usr/bin/env python3
"""NeoPlat como programa: doble clic y sale el editor en su ventana.

Esto es lo que se empaqueta como **NeoPlat.exe**, y la diferencia con
`ngplat.exe` no es lo que hace sino lo que **no** se ve: no hay consola. El
`ngplat.exe` de siempre es una herramienta de terminal que ademas sabe
preguntar; este es un programa de escritorio, y detras de el no se queda una
ventana negra abierta.

Lo que hace al arrancar:

  1. busca juegos en su carpeta y en las de al lado;
  2. si hay uno, lo abre; si hay varios o ninguno, **pregunta con un dialogo
     del sistema** en vez de escribir en una consola que aqui no existe;
  3. levanta el servidor local de siempre y abre el editor en su ventana.

**Los dialogos son de Windows, no de tkinter**, y eso no es un capricho: la
distribucion de Python que cabe dentro de un .exe de ocho megas -la embebida-
**no trae tkinter**, asi que un programa que lo necesitara se construiria sin
el y se cerraria en silencio al primer dialogo. Que es justo lo peor que puede
pasarle a quien acaba de hacer doble clic. `MessageBoxW` y `SHBrowseForFolderW`
estan en cualquier Windows desde hace treinta anyos y se llaman con ctypes, que
viene con Python.

Fuera de Windows -donde esto se prueba- se usa tkinter si esta, y si no,
la consola. Ahi siempre hay una.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback

RAIZ = os.path.dirname(os.path.abspath(__file__))
if os.path.isdir(os.path.join(RAIZ, "tools")):
    sys.path.insert(0, os.path.join(RAIZ, "tools"))

ES_WINDOWS = sys.platform.startswith("win")

# Lo que dice MessageBoxW. Son los de toda la vida.
MB_OK = 0x00000000
MB_OKCANCEL = 0x00000001
MB_ICONERROR = 0x00000010
MB_ICONINFO = 0x00000040
IDOK = 1


def mensaje(titulo: str, texto: str, error: bool = False) -> None:
    """Un cuadro de dialogo. Si no hay con que, por la salida de errores."""
    if ES_WINDOWS:
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None, texto, titulo,
                MB_OK | (MB_ICONERROR if error else MB_ICONINFO))
            return
        except Exception:
            pass
    else:
        try:
            import tkinter
            from tkinter import messagebox

            raiz = tkinter.Tk()
            raiz.withdraw()
            (messagebox.showerror if error else messagebox.showinfo)(titulo, texto)
            raiz.destroy()
            return
        except Exception:
            pass
    print("%s: %s" % (titulo, texto), file=sys.stderr)


def preguntar(titulo: str, texto: str) -> bool:
    """Un si/no. Sin dialogos, se da por bueno: aqui nunca se borra nada."""
    if ES_WINDOWS:
        try:
            import ctypes

            return ctypes.windll.user32.MessageBoxW(
                None, texto, titulo, MB_OKCANCEL | MB_ICONINFO) == IDOK
        except Exception:
            return True
    try:
        import tkinter
        from tkinter import messagebox

        raiz = tkinter.Tk()
        raiz.withdraw()
        dicho = messagebox.askokcancel(titulo, texto)
        raiz.destroy()
        return bool(dicho)
    except Exception:
        return True


def _carpeta_windows(titulo: str, desde: str) -> str:
    """El dialogo de elegir carpeta de Windows, por ctypes.

    `SHBrowseForFolderW` y no el de archivos: lo que se elige aqui es una
    carpeta -la del juego-, y pedir un archivo cuando se quiere una carpeta es
    de las cosas que hacen que un programa parezca prestado.
    """
    import ctypes
    import ctypes.wintypes as w

    BIF_RETURNONLYFSDIRS = 0x0001
    BIF_NEWDIALOGSTYLE = 0x0040
    BFFM_INITIALIZED = 1
    BFFM_SETSELECTIONW = 0x0467

    shell32 = ctypes.windll.shell32
    ole32 = ctypes.windll.ole32
    ole32.CoInitialize(None)

    CALLBACK = ctypes.WINFUNCTYPE(ctypes.c_int, w.HWND, w.UINT,
                                  w.LPARAM, w.LPARAM)

    def empezar(hwnd, mensaje_, lparam, datos):
        # Al abrirse, colocarse donde esta el programa: casi siempre es ahi al
        # lado donde esta el juego.
        if mensaje_ == BFFM_INITIALIZED and desde:
            ctypes.windll.user32.SendMessageW(hwnd, BFFM_SETSELECTIONW, 1,
                                              ctypes.c_wchar_p(desde))
        return 0

    guardado = CALLBACK(empezar)

    class BROWSEINFOW(ctypes.Structure):
        _fields_ = [("hwndOwner", w.HWND),
                    ("pidlRoot", ctypes.c_void_p),
                    ("pszDisplayName", ctypes.c_wchar_p),
                    ("lpszTitle", ctypes.c_wchar_p),
                    ("ulFlags", w.UINT),
                    ("lpfn", CALLBACK),
                    ("lParam", w.LPARAM),
                    ("iImage", ctypes.c_int)]

    hueco = ctypes.create_unicode_buffer(260)
    datos = BROWSEINFOW()
    datos.hwndOwner = None
    datos.pidlRoot = None
    datos.pszDisplayName = ctypes.cast(hueco, ctypes.c_wchar_p)
    datos.lpszTitle = titulo
    datos.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE
    datos.lpfn = guardado
    datos.lParam = 0

    pidl = shell32.SHBrowseForFolderW(ctypes.byref(datos))
    if not pidl:
        return ""
    camino = ctypes.create_unicode_buffer(260)
    ok = shell32.SHGetPathFromIDListW(pidl, camino)
    ole32.CoTaskMemFree(pidl)
    return camino.value if ok else ""


def elegir_carpeta(titulo: str, desde: str = "") -> str:
    """Pide una carpeta. Cadena vacia si se cancela o no hay dialogos."""
    if ES_WINDOWS:
        try:
            return _carpeta_windows(titulo, desde)
        except Exception:
            return ""
    try:
        import tkinter
        from tkinter import filedialog

        raiz = tkinter.Tk()
        raiz.withdraw()
        elegida = filedialog.askdirectory(title=titulo, initialdir=desde or None)
        raiz.destroy()
        return elegida or ""
    except Exception:
        return ""


def donde_buscar() -> str:
    """La carpeta desde la que se mira: la del .exe, no la de trabajo.

    Con doble clic la carpeta de trabajo puede ser cualquiera -el escritorio,
    C:\\Windows\\system32-, asi que lo que vale es donde esta el programa.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.getcwd()


def elegir_proyecto(cerca, base: str) -> str:
    """Que juego abrir. Cadena vacia para no abrir ninguno.

    Con uno solo no se pregunta nada, que es el caso de siempre: el .exe al
    lado de la carpeta del juego. Con varios o con ninguno se abre el dialogo
    de carpetas, que es lo que un programa de Windows hace aqui.
    """
    if len(cerca) == 1:
        return cerca[0]
    if cerca:
        nombres = ", ".join(os.path.basename(p.rstrip("\\/")) for p in cerca[:6])
        mensaje("NeoPlat",
                "Aqui hay varios juegos (%s).\n\n"
                "Elige en la ventana siguiente cual quieres abrir." % nombres)
        return elegir_carpeta("Elige la carpeta del juego", base)
    if not preguntar("NeoPlat",
                     "Aqui no hay ningun juego todavia.\n\n"
                     "Aceptar para elegir una carpeta vacia y crear uno."):
        return ""
    destino = elegir_carpeta("Carpeta para el juego nuevo", base)
    if not destino:
        return ""
    if os.path.isdir(destino) and os.listdir(destino):
        # Ahi ya hay cosas: o es un juego, o no se toca.
        if os.path.exists(os.path.join(destino, "game.yaml")):
            return destino
        mensaje("NeoPlat",
                "Esa carpeta no esta vacia y no tiene ningun game.yaml.\n\n"
                "Elige una vacia, o la carpeta de un juego que ya exista.",
                error=True)
        return ""
    from ngplat.scaffold import crear_proyecto

    nombre = os.path.basename(destino.rstrip("\\/")) or "mijuego"
    crear_proyecto(destino, nombre.upper(), "", genero="plataformas")
    return destino


def main(argv) -> int:
    from ngplat import cli

    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("proyecto", nargs="?", default="")
    args, _ = ap.parse_known_args(argv)

    base = donde_buscar()
    proyecto = args.proyecto or elegir_proyecto(cli._proyectos_cerca(base), base)
    if not proyecto:
        return 0
    if not os.path.exists(os.path.join(proyecto, "game.yaml")):
        mensaje("NeoPlat",
                "En esa carpeta no hay ningun game.yaml, asi que ahi no hay "
                "juego que abrir:\n\n%s" % proyecto, error=True)
        return 2
    return cli.cmd_app(argparse.Namespace(proyecto=proyecto, salida=None,
                                          puerto=0, sistema=""))


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception:
        # Sin consola, lo que no salga aqui no sale en ninguna parte.
        mensaje("NeoPlat", "No se ha podido abrir el editor:\n\n%s"
                % traceback.format_exc(limit=3), error=True)
        raise SystemExit(1)
