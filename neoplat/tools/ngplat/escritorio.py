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

**Donde se busca Edge, y por que ahi.** Mirar en `%ProgramFiles%` no basta:
una instalacion puede estar en otra unidad, la variable puede no estar puesta
en el entorno que hereda un programa lanzado con doble clic, y Edge no es el
unico que cuenta. Asi que primero se le pregunta a **Windows**: la lista
`App Paths` del registro es la que usa el propio sistema para resolver
"msedge" cuando se escribe en Ejecutar, y es la respuesta buena sea donde sea
que este instalado. Las rutas de `Program Files` se quedan detras, de
respaldo, y `NEOPLAT_NAVEGADOR` manda sobre todo lo demas.

Y si al final no sale ninguno, **eso se cuenta**: con `ngplat navegador` sale
la lista entera de sitios mirados y lo que hay en cada uno. Un programa que se
calla lo que ha intentado no se puede arreglar desde la otra punta del mundo.
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
    # Con %ProgramFiles% sin poner -pasa en entornos heredados de un doble
    # clic- estas dos siguen valiendo, y la ultima pareja vale aunque no haya
    # ni una variable de entorno en pie.
    r"%ProgramW6432%\Microsoft\Edge\Application\msedge.exe",
    r"%SystemDrive%\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"%SystemDrive%\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)

ORDENES: Tuple[str, ...] = (
    "microsoft-edge-stable", "msedge",
    "google-chrome-stable", "google-chrome", "chrome",
    "chromium-browser", "chromium",
    "brave-browser", "brave",
)

ANCHO, ALTO = 1280, 860


# Las entradas del registro de Windows que dicen donde esta cada navegador.
APP_PATHS = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
EJECUTABLES = ("msedge.exe", "chrome.exe", "brave.exe")


def _del_registro() -> List[str]:
    """Donde dice **Windows** que esta cada navegador.

    `App Paths` es la lista con la que el propio sistema resuelve "msedge"
    cuando se escribe en Ejecutar. Es la respuesta buena: no depende de que el
    navegador este en Program Files, ni de que las variables de entorno hayan
    llegado hasta aqui, ni del idioma en que se instalo Windows.

    Se mira en las dos ramas -la del usuario primero, que es donde aparece una
    instalacion que no pidio permisos de administrador- y pidiendo la vista de
    64 bits, para que un programa de 32 no acabe leyendo Wow6432Node y viendo
    media verdad.
    """
    if not sys.platform.startswith("win"):
        return []
    try:
        import winreg
    except ImportError:          # pragma: no cover - solo falta fuera de Windows
        return []
    encontrados = []
    for raiz in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for nombre in EJECUTABLES:
            for vista in (getattr(winreg, "KEY_WOW64_64KEY", 0), 0):
                try:
                    with winreg.OpenKey(raiz, APP_PATHS + "\\" + nombre, 0,
                                        winreg.KEY_READ | vista) as clave:
                        valor = winreg.QueryValueEx(clave, None)[0]
                except OSError:
                    continue
                ruta = str(valor).strip().strip('"')
                if ruta and ruta not in encontrados:
                    encontrados.append(ruta)
                break        # leida esta entrada, la otra vista dice lo mismo
    return encontrados


def explicacion(motivo: str) -> str:
    """Lo que se le cuenta a quien esperaba una ventana y no la ha tenido.

    Esta aqui y no en quien llama porque lo lee **gente**, no un programa: va
    tal cual al cuadro de dialogo de NeoPlat.exe, y lleva lo unico que hay que
    saber para arreglarlo -la variable y la orden que lista los sitios-.
    """
    return ("No he podido abrir el editor en su ventana, asi que lo abro en "
            "tu navegador de siempre.\n\n%s\n\n"
            "Si tienes Edge o Chrome en otro sitio, dilo con la variable "
            "NEOPLAT_NAVEGADOR. Para ver donde he buscado:\n"
            "    ngplat navegador" % motivo)


def _de_windows() -> List[str]:
    """Las rutas de Program Files que se dejan de respaldo."""
    rutas = []
    for plantilla in NAVEGADORES_WINDOWS:
        ruta = os.path.expandvars(plantilla)
        if "%" in ruta:
            # La variable no esta puesta en este entorno: la plantilla se
            # queda tal cual y no hay nada que mirar.
            continue
        if ruta not in rutas:
            rutas.append(ruta)
    return rutas


def candidatos() -> List[Tuple[str, str]]:
    """Todo lo que se va a mirar, en orden, con de donde ha salido cada cosa.

    Lo devuelve entero -mire o no mire luego cada sitio- porque esta misma
    lista es la que sale en `ngplat navegador`: lo que hay que poder contar no
    es solo que no se encontro, sino **donde se busco**.
    """
    lista: List[Tuple[str, str]] = []

    def anotar(ruta: str, de_donde: str) -> None:
        if ruta and not any(ruta == r for r, _ in lista):
            lista.append((ruta, de_donde))

    puesto = os.environ.get("NEOPLAT_NAVEGADOR", "").strip()
    if puesto:
        anotar(puesto, "NEOPLAT_NAVEGADOR")
        suelto = shutil.which(puesto)
        if suelto:
            anotar(suelto, "NEOPLAT_NAVEGADOR (por el PATH)")
        # Con NEOPLAT_NAVEGADOR puesto no se mira nada mas: si quien lo puso
        # se equivoco, mas vale que se note que arrancar otro por detras.
        return lista

    for ruta in _del_registro():
        anotar(ruta, "registro de Windows (App Paths)")
    for ruta in _de_windows():
        anotar(ruta, "Program Files")
    for orden in ORDENES:
        ruta = shutil.which(orden)
        if ruta:
            anotar(ruta, "PATH (%s)" % orden)
        else:
            anotar(orden, "PATH (no esta)")
    return lista


def donde_se_busca() -> List[Tuple[str, str, bool]]:
    """La lista de candidatos con un si o un no al lado. Para el diagnostico."""
    return [(ruta, de_donde, os.path.isfile(ruta))
            for ruta, de_donde in candidatos()]


def buscar_navegador() -> Optional[str]:
    """El navegador con el que abrir la ventana, o None si no hay ninguno.

    `NEOPLAT_NAVEGADOR` manda: es por donde se le dice a esto cual usar cuando
    hay varios o cuando esta en un sitio que no se le ocurriria mirar.
    """
    for ruta, _ in candidatos():
        if os.path.isfile(ruta):
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


def abrir_con_motivo(direccion: str):
    """Abre el editor en su ventana. Devuelve (proceso, motivo).

    El motivo es lo que hacia falta y no habia: **no es lo mismo** que aqui no
    haya Edge ni Chrome que encontrarlo y que no arranque, y las dos cosas se
    veian igual desde fuera -un navegador normal abriendose- porque la unica
    explicacion iba a una consola que en NeoPlat.exe no existe. Con el motivo
    en la mano, quien llama lo puede poner en un cuadro de dialogo.

    Con proceso, el motivo va vacio: no hay nada que contar.
    """
    navegador = buscar_navegador()
    if not navegador:
        mirados = sum(1 for _, _, hay in donde_se_busca() if not hay)
        return None, ("no encuentro Edge ni Chrome (%d sitios mirados; "
                      "'ngplat navegador' los lista)" % mirados)
    try:
        proceso = subprocess.Popen(argumentos(navegador, direccion),
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
    except OSError as error:
        return None, "no he podido arrancar %s: %s" % (navegador, error)
    return proceso, ""


def abrir(direccion: str) -> Optional[subprocess.Popen]:
    """Lo mismo sin el motivo, para quien no lo necesita."""
    return abrir_con_motivo(direccion)[0]
