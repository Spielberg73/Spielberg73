#!/usr/bin/env python3
"""NeoPlat como programa: doble clic y sale el editor en su ventana.

Esto es lo que se empaqueta como **NeoPlat.exe**, y la diferencia con
`ngplat.exe` no es lo que hace sino lo que **no** se ve: no hay consola. El
`ngplat.exe` de siempre es una herramienta de terminal que ademas sabe
preguntar; este es un programa de escritorio, y detras de el no se queda una
ventana negra abierta.

Lo que hace al arrancar:

  1. busca juegos en su carpeta y en las de al lado;
  2. si hay uno, lo abre; si hay varios o ninguno, **pregunta con una ventana**
     (tkinter, que viene con Python) en vez de escribir en una consola que
     aqui no existe;
  3. levanta el servidor local de siempre y abre el editor en su ventana.

Sin consola no hay donde escribir un error, asi que lo que falle sale en un
cuadro de dialogo. Un programa que se cierra sin decir nada es lo peor que
puede pasarle a quien acaba de hacer doble clic.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback

RAIZ = os.path.dirname(os.path.abspath(__file__))
if os.path.isdir(os.path.join(RAIZ, "tools")):
    sys.path.insert(0, os.path.join(RAIZ, "tools"))


def _aviso(titulo: str, texto: str) -> None:
    """Un cuadro de dialogo, y si tampoco se puede, a la consola."""
    try:
        import tkinter
        from tkinter import messagebox

        raiz = tkinter.Tk()
        raiz.withdraw()
        messagebox.showerror(titulo, texto)
        raiz.destroy()
    except Exception:
        print("%s: %s" % (titulo, texto), file=sys.stderr)


def _elegir_carpeta(titulo: str) -> str:
    """Pide una carpeta con el dialogo del sistema. Cadena vacia si se cancela."""
    try:
        import tkinter
        from tkinter import filedialog

        raiz = tkinter.Tk()
        raiz.withdraw()
        elegida = filedialog.askdirectory(title=titulo)
        raiz.destroy()
        return elegida or ""
    except Exception:
        return ""


def _preguntar(titulo: str, texto: str, por_defecto: str) -> str:
    try:
        import tkinter
        from tkinter import simpledialog

        raiz = tkinter.Tk()
        raiz.withdraw()
        dicho = simpledialog.askstring(titulo, texto, initialvalue=por_defecto)
        raiz.destroy()
        return (dicho or "").strip()
    except Exception:
        return ""


def _elegir(titulo: str, texto: str, opciones):
    """Una lista para elegir. Devuelve la opcion, o None si se cierra."""
    import tkinter

    elegido = {"valor": None}
    raiz = tkinter.Tk()
    raiz.title(titulo)
    raiz.geometry("460x300")
    tkinter.Label(raiz, text=texto, pady=10).pack()
    lista = tkinter.Listbox(raiz)
    for texto_opcion, _ in opciones:
        lista.insert(tkinter.END, texto_opcion)
    lista.selection_set(0)
    lista.pack(fill=tkinter.BOTH, expand=True, padx=14)

    def aceptar(*_):
        cual = lista.curselection()
        if cual:
            elegido["valor"] = opciones[cual[0]][1]
        raiz.destroy()

    lista.bind("<Double-Button-1>", aceptar)
    tkinter.Button(raiz, text="Abrir", command=aceptar, width=14).pack(pady=12)
    raiz.mainloop()
    return elegido["valor"]


def _donde_buscar() -> str:
    """La carpeta desde la que se mira: la del .exe, no la de trabajo.

    Con doble clic la carpeta de trabajo puede ser cualquiera -el escritorio,
    C:\\Windows\\system32-, asi que lo que vale es donde esta el programa.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.getcwd()


def main(argv) -> int:
    from ngplat import cli
    from ngplat.errors import ProjectError

    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("proyecto", nargs="?", default="")
    args, _ = ap.parse_known_args(argv)

    proyecto = args.proyecto
    if not proyecto:
        cerca = cli._proyectos_cerca(_donde_buscar())
        if len(cerca) == 1:
            proyecto = cerca[0]
        elif cerca:
            opciones = [(cli._nombre_de(p), p) for p in cerca]
            opciones.append(("-- abrir otra carpeta --", "?"))
            opciones.append(("-- crear un juego nuevo --", "+"))
            proyecto = _elegir("NeoPlat", "Que juego quieres abrir?", opciones)
            if proyecto is None:
                return 0
        else:
            proyecto = "+"

    if proyecto == "?":
        proyecto = _elegir_carpeta("Elige la carpeta del juego")
        if not proyecto:
            return 0
    if proyecto == "+":
        nombre = _preguntar("NeoPlat", "Nombre de la carpeta del juego nuevo:",
                            "mijuego")
        if not nombre:
            return 0
        destino = os.path.join(_donde_buscar(), nombre)
        titulo = _preguntar("NeoPlat", "Titulo que saldra en pantalla:",
                            nombre.upper()) or nombre.upper()
        from ngplat.scaffold import crear_proyecto

        crear_proyecto(destino, titulo, "", genero="plataformas")
        proyecto = destino

    return cli.cmd_app(argparse.Namespace(proyecto=proyecto, salida=None,
                                          puerto=0, sistema=""))


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception:
        _aviso("NeoPlat", "No se ha podido abrir el editor:\n\n%s"
               % traceback.format_exc(limit=3))
        raise SystemExit(1)
