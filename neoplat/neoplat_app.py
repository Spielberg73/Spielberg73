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
import io
import os
import sys
import tempfile
import time
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


class _Cuaderno(io.TextIOBase):
    """Una salida de pega que se queda con las ultimas lineas.

    En Windows, un programa enlazado **sin consola** arranca sin flujos
    estandar: `sys.stdout` y `sys.stderr` valen **None**, no un sitio vacio
    donde escribir. Y entonces cualquier `sys.stdout.write(...)` o
    `sys.stdout.isatty()` -y los hay, aqui y en media biblioteca estandar- no
    es que no escriba: **revienta** con un AttributeError en medio de lo que
    estuviera haciendo.

    Es lo que se llevo por delante a 1.57. El editor abria su ventana, y justo
    despues, al ir a decir "servidor en 127.0.0.1:...", el programa se moria
    ahi mismo sin llegar a atender una sola peticion. Lo que veia quien hacia
    doble clic era una ventana con un enlace muerto.

    Asi que donde Windows no pone nada se pone esto. No escribe en ninguna
    parte -no hay donde-, pero se queda con las ultimas lineas, y si algo
    falla salen en el cuadro de dialogo. En un programa sin consola esa es
    toda la informacion que va a haber.
    """

    LIMITE = 40

    def __init__(self):
        self.lineas = []
        self._a_medias = ""

    def write(self, texto: str) -> int:
        self._a_medias += texto
        while "\n" in self._a_medias:
            linea, self._a_medias = self._a_medias.split("\n", 1)
            self.lineas.append(linea)
        # solo las ultimas: esto no es un registro, es lo que quepa en un
        # cuadro de dialogo
        del self.lineas[:-self.LIMITE]
        return len(texto)

    def flush(self) -> None:
        pass

    def writable(self) -> bool:
        return True

    def isatty(self) -> bool:
        return False      # sin consola no hay colores que poner

    def ultimas(self, cuantas: int = 12) -> str:
        sueltas = [l for l in self.lineas[-cuantas:] if l.strip()]
        return "\n".join(sueltas)


CUADERNO = _Cuaderno()


def apuntalar_salidas() -> None:
    """Pone algo donde Windows no ha puesto nada.

    Lo primero que hace el programa, antes de importar nada del kit: el kit
    escribe por la salida de siempre y da por hecho que existe, que es lo
    normal en cualquier sitio menos aqui.
    """
    if sys.stdout is None:
        sys.stdout = CUADERNO
    if sys.stderr is None:
        sys.stderr = CUADERNO
    if sys.stdin is None:
        # Nadie va a teclear nada en un programa sin consola, pero preguntarlo
        # tampoco puede reventar.
        sys.stdin = io.StringIO("")


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
    try:
        print("%s: %s" % (titulo, texto), file=sys.stderr)
    except Exception:
        # Ultimo recurso del ultimo recurso: en un programa sin consola
        # `sys.stderr` puede ser None o estar cerrado. Que no haya donde
        # escribir no puede ser lo que tire el programa.
        pass


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


REGISTRO = "NeoPlat-registro.txt"


def donde_apuntar() -> str:
    """El fichero donde queda constancia de lo que ha hecho el programa.

    Al lado del .exe, que es donde lo va a encontrar quien lo necesite sin que
    haya que explicarle nada. Si ahi no se puede escribir -un .exe dentro de
    Program Files, una carpeta de solo lectura-, en la carpeta temporal.

    Esto existe por una tarde entera de arreglar a ciegas. Sin consola, un
    fallo que solo le pasa a quien lo usa no deja ni rastro, y lo unico que
    llega de vuelta es "sigue fallando". Con el registro, llega el fichero.
    """
    base = donde_buscar()
    # Se pregunta, no se prueba escribiendo: una prueba de escritura dejaria
    # el fichero creado aunque no hubiera nada que apuntar, y un registro
    # vacio al lado del programa es basura que alguien tendra que barrer.
    if base and os.access(base, os.W_OK):
        return os.path.join(base, REGISTRO)
    return os.path.join(tempfile.gettempdir(), REGISTRO)


def con_registro(texto: str) -> str:
    """El texto, y debajo donde esta apuntado todo. Para poder mandarlo."""
    return "%s\n\nQueda todo apuntado en:\n%s" % (texto, donde_apuntar())


def apuntar(texto: str) -> None:
    """Una linea con su hora en el registro. No puede fallar nunca.

    Si donde toca no se puede escribir, se intenta en la carpeta temporal; y
    si tampoco, se pierde la linea y se sigue. Esto es el registro, no el
    trabajo: que no se pueda apuntar no puede ser lo que tire el programa.
    """
    linea = "%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), texto)
    sitios = []
    try:
        sitios.append(donde_apuntar())
    except Exception:
        pass
    sitios.append(os.path.join(tempfile.gettempdir(), REGISTRO))
    for ruta in sitios:
        try:
            with open(ruta, "a", encoding="utf-8") as fh:
                fh.write(linea)
            return
        except OSError:
            continue


def main(argv) -> int:
    apuntalar_salidas()
    from ngplat import cli

    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("proyecto", nargs="?", default="")
    args, _ = ap.parse_known_args(argv)

    base = donde_buscar()
    apuntar("--- NeoPlat %s arranca en %s" % (cli.__version__, base))
    proyecto = args.proyecto or elegir_proyecto(cli._proyectos_cerca(base), base)
    apuntar("juego: %s" % (proyecto or "ninguno: no hay nada que abrir"))
    if not proyecto:
        return 0
    if not os.path.exists(os.path.join(proyecto, "game.yaml")):
        mensaje("NeoPlat",
                "En esa carpeta no hay ningun game.yaml, asi que ahi no hay "
                "juego que abrir:\n\n%s" % proyecto, error=True)
        return 2
    # `avisar` es por donde el kit saca lo que aqui no se puede escribir en
    # ninguna parte. Sin esto, un aviso como "no encuentro Edge" se iba a una
    # consola que no existe y lo unico que se veia era un navegador normal
    # abriendose, sin ninguna explicacion.
    return cli.cmd_app(argparse.Namespace(proyecto=proyecto, salida=None,
                                          puerto=0, sistema=""),
                       avisar=lambda texto: mensaje("NeoPlat", con_registro(texto)),
                       apuntar=apuntar)


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception:
        # Sin consola, lo que no salga aqui no sale en ninguna parte: van el
        # fallo y las ultimas lineas que el kit alcanzo a escribir, que es lo
        # que dice **por donde** iba cuando se rompio.
        apuntar("ha fallado: %s" % traceback.format_exc(limit=3).strip())
        ultimas = CUADERNO.ultimas()
        mensaje("NeoPlat", con_registro(
            "No se ha podido abrir el editor:\n\n%s%s"
            % (traceback.format_exc(limit=3),
               ("\nLo ultimo que estaba haciendo:\n" + ultimas)
               if ultimas else "")), error=True)
        raise SystemExit(1)
