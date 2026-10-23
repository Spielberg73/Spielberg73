"""El editor en su propia ventana, sin navegador alrededor.

`ngplat probar` abre el preview en el navegador: con su barra de direcciones,
sus pestanas, sus marcadores y, en Windows, una ventana negra de consola
detras. Funciona, pero no se parece a un programa de hacer juegos: se parece a
una pagina web.

Esto lo abre como lo que es. El editor sigue siendo el mismo -son quince mil
lineas de JavaScript y reescribirlas en un armario de botones nativo seria
rehacer el kit entero y quedarse con un editor peor-, pero la ventana es suya:
sin barra de direcciones, sin pestanas, con su icono en la barra de tareas y
cerrandose como se cierra un programa. Por dentro sigue siendo `ngplat probar`
sirviendo en 127.0.0.1, asi que guardar y compilar funcionan igual.

**Como se hace, y por que asi.** Los navegadores de hoy traen un *modo
aplicacion* (`--app=URL`) pensado justo para esto, y es lo unico que hace falta:

    msedge.exe --app=http://127.0.0.1:8777/?clave=...

Edge viene con Windows 10 y 11, asi que en la maquina donde esto importa ya
esta puesto y no hay nada que instalar. Las alternativas que se miraron:

  * **empaquetar un navegador entero** (Electron, Tauri y companyia): entre
    150 y 200 MB de descarga, una cadena de herramientas de node o de rust que
    el kit no tiene, y un segundo motor de navegador que mantener. El kit
    entero -motor, compilador, editor y pruebas- ocupa menos que eso;
  * **empotrar WebView2 a mano**: es la via "nativa" de verdad, pero hay que
    escribir un anfitrion en C y llevarlo por separado para 32 y 64 bits. Lo
    que ve el usuario es exactamente la misma ventana que con `--app`;
  * **reescribir el editor en Tk**: tkinter viene con Python, si. Pero el
    editor dibuja sprites a mano alzada, reproduce animaciones a 60 imagenes
    por segundo y juega el propio juego dentro: en un canvas de Tk eso no se
    sostiene, y serian meses para acabar con menos de lo que ya hay.

Asi que se usa el modo aplicacion, y si no hay con que, se dice y se abre el
navegador de siempre en vez de dejar al usuario mirando una ventana vacia.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from typing import List, Optional, Tuple

# Donde mirar, en orden. Primero los que trae Windows y despues los que trae
# todo el mundo; el ultimo es el Chromium que dejan instalado las pruebas.
NAVEGADORES_WINDOWS: Tuple[str, ...] = (
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe",
)

ORDENES: Tuple[str, ...] = (
    "microsoft-edge-stable", "msedge",
    "google-chrome-stable", "google-chrome", "chrome",
    "chromium-browser", "chromium",
    "brave-browser", "brave",
)

ANCHO, ALTO = 1280, 860


def _de_windows() -> Optional[str]:
    for plantilla in NAVEGADORES_WINDOWS:
        ruta = os.path.expandvars(plantilla)
        if "%" not in ruta and os.path.isfile(ruta):
            return ruta
    return None


def buscar_navegador() -> Optional[str]:
    """El navegador con el que abrir la ventana, o None si no hay ninguno.

    Se mira tambien `NEOPLAT_NAVEGADOR`, que es por donde se le dice a esto
    cual usar cuando hay varios o cuando esta en un sitio raro.
    """
    puesto = os.environ.get("NEOPLAT_NAVEGADOR", "").strip()
    if puesto:
        return puesto if os.path.isfile(puesto) else shutil.which(puesto)
    if sys.platform.startswith("win"):
        encontrado = _de_windows()
        if encontrado:
            return encontrado
    for orden in ORDENES:
        ruta = shutil.which(orden)
        if ruta:
            return ruta
    return None


def carpeta_de_perfil() -> str:
    """Donde guarda la ventana sus cosas.

    Un perfil propio y no el del usuario: asi la ventana del editor no hereda
    las extensiones ni las pestanas del navegador de todos los dias, sale con
    su icono en la barra de tareas y cerrarla no cierra nada mas. Y asi no se
    le toca al usuario su perfil, que es suyo.
    """
    if sys.platform.startswith("win"):
        base = os.environ.get("LocalAppData") or tempfile.gettempdir()
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = (os.environ.get("XDG_DATA_HOME")
                or os.path.expanduser("~/.local/share"))
    return os.path.join(base, "NeoPlat", "ventana")


def argumentos(navegador: str, direccion: str) -> List[str]:
    """La orden entera con la que se abre la ventana."""
    perfil = carpeta_de_perfil()
    os.makedirs(perfil, exist_ok=True)
    return [
        navegador,
        "--app=%s" % direccion,
        "--user-data-dir=%s" % perfil,
        "--window-size=%d,%d" % (ANCHO, ALTO),
        # Sin esto, la ventana saca la primera vez el cuento de "elige tu
        # navegador por defecto", que en un programa de hacer juegos no pinta
        # nada.
        "--no-first-run",
        "--no-default-browser-check",
        # Y que no se quede un proceso suelto si la ventana se cierra mal.
        "--disable-background-networking",
    ]


def abrir(direccion: str) -> Optional[subprocess.Popen]:
    """Abre el editor en su ventana. Devuelve el proceso, o None si no se pudo.

    None no es un error: quiere decir "aqui no hay con que", y quien llama abre
    el navegador de siempre y lo dice. Es lo que pasa en una maquina sin Edge
    ni Chrome.
    """
    navegador = buscar_navegador()
    if not navegador:
        return None
    try:
        return subprocess.Popen(argumentos(navegador, direccion),
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    except OSError:
        return None
