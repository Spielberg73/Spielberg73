"""La orden `ngplat`: crear, comprobar, probar y compilar juegos NeoPlat."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from typing import List, Optional

from . import __version__
from .build import build_project
from .codegen import copy_engine, generate_gamedata, generate_makefile, write_rom_data
from .errors import ProjectError
from .preview import write_preview
from .project import load_project
from .scaffold import crear_proyecto

VERDE = "\033[32m"
AMARILLO = "\033[33m"
ROJO = "\033[31m"
GRIS = "\033[90m"
FIN = "\033[0m"


def _color(text: str, code: str) -> str:
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return text
    return code + text + FIN


def _ok(text: str) -> None:
    print(_color("  ok  ", VERDE) + text)


def _info(text: str) -> None:
    print(_color("  ..  ", GRIS) + text)


def _aviso(text: str) -> None:
    print(_color(" aviso", AMARILLO) + " " + text)


def _cargar(ruta: str):
    project = load_project(ruta)
    for warning in project.warnings:
        _aviso(warning)
    return project


# ------------------------------------------------------------------ ordenes

def cmd_nuevo(args: argparse.Namespace) -> int:
    creados = crear_proyecto(args.carpeta, args.titulo or os.path.basename(args.carpeta.rstrip("/")),
                             args.autor or "")
    _ok("proyecto creado en '%s'" % args.carpeta)
    for nombre in creados:
        _info(nombre)
    print()
    print("Siguiente paso:")
    print("  cd %s" % args.carpeta)
    print("  ngplat probar        # abre el preview jugable en el navegador")
    print("  ngplat compilar      # genera el proyecto en C y las ROMs graficas")
    return 0


def cmd_comprobar(args: argparse.Namespace) -> int:
    project = _cargar(args.proyecto)
    build = build_project(project)
    stats = build.stats()
    _ok("'%s' es valido" % project.title)
    print()
    print("  niveles         %d" % stats["niveles"])
    for level in build.levels:
        print("    %-20s %3d x %-3d tiles, %2d entidades"
              % (level.name, level.width, level.height, len(level.spawns)))
    print("  enemigos        %d" % stats["enemigos"])
    print("  objetos         %d" % stats["objetos"])
    print("  tiles de sprite %d  (%d KB de ROM C)"
          % (stats["tiles_sprite"], (stats["bytes_c1"] + stats["bytes_c2"]) // 1024))
    print("  tiles de fix    %d" % stats["tiles_fix"])
    print("  paletas         %d de 256" % stats["paletas"])
    print("  mapas           %d bytes" % stats["bytes_mapas"])
    return 0


def cmd_probar(args: argparse.Namespace) -> int:
    project = _cargar(args.proyecto)
    build = build_project(project)
    destino = args.salida or os.path.join(project.root, "preview.html")
    write_preview(build, destino)
    _ok("preview generado: %s" % destino)
    if not args.no_abrir:
        try:
            import webbrowser

            webbrowser.open("file://" + os.path.abspath(destino))
            _info("abriendo en el navegador...")
        except Exception:
            _info("abrelo a mano en tu navegador")
    return 0


def cmd_compilar(args: argparse.Namespace) -> int:
    project = _cargar(args.proyecto)
    build = build_project(project)
    out_dir = args.salida or os.path.join(project.root, "build")
    os.makedirs(out_dir, exist_ok=True)

    for relativo, contenido in generate_gamedata(build).items():
        ruta = os.path.join(out_dir, relativo)
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(contenido)
    copy_engine(out_dir)
    roms = write_rom_data(build, out_dir, args.rom_id)
    with open(os.path.join(out_dir, "Makefile"), "w", encoding="utf-8") as fh:
        fh.write(generate_makefile(build, args.rom_id))

    stats = build.stats()
    _ok("proyecto en C generado en '%s'" % out_dir)
    _info("codigo:   src/ (motor + gamedata.c con tu juego)")
    for nombre, tamano in sorted(roms.items()):
        _info("grafico:  rom/%s (%d KB)" % (nombre, tamano // 1024))
    _info("%d tiles de sprite, %d paletas, %d niveles"
          % (stats["tiles_sprite"], stats["paletas"], stats["niveles"]))

    if args.make:
        return _ejecutar_make(out_dir)

    if shutil.which("m68k-neogeo-elf-gcc"):
        print()
        print("Compila la ROM con:")
        print("  cd %s && make" % out_dir)
        print("  make run          # arranca ngdevkit-gngeo")
    else:
        print()
        print("Para generar la ROM final necesitas ngdevkit (compilador de 68000):")
        print("  https://github.com/dciabrin/ngdevkit")
        print("Cuando lo tengas:  cd %s && make" % out_dir)
    return 0


def _ejecutar_make(out_dir: str) -> int:
    if not shutil.which("m68k-neogeo-elf-gcc"):
        raise ProjectError(
            "no encuentro m68k-neogeo-elf-gcc (el compilador de 68000 de ngdevkit)",
            hint="instala ngdevkit o quita la opcion --make",
        )
    _info("ejecutando make en %s" % out_dir)
    result = subprocess.run(["make"], cwd=out_dir)
    if result.returncode != 0:
        raise ProjectError("make ha fallado (codigo %d)" % result.returncode)
    _ok("ROM construida en %s/rom" % out_dir)
    return 0


# ------------------------------------------------------------------- parser

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ngplat",
        description="NeoPlat: juegos de plataformas 2D para Neo Geo desde un game.yaml",
    )
    parser.add_argument("--version", action="version", version="ngplat %s" % __version__)
    sub = parser.add_subparsers(dest="orden")

    p_nuevo = sub.add_parser("nuevo", aliases=["new"], help="crea un proyecto de ejemplo")
    p_nuevo.add_argument("carpeta")
    p_nuevo.add_argument("--titulo", help="titulo del juego")
    p_nuevo.add_argument("--autor", help="tu nombre")
    p_nuevo.set_defaults(func=cmd_nuevo)

    p_check = sub.add_parser("comprobar", aliases=["check"],
                             help="valida game.yaml y muestra el tamano del juego")
    p_check.add_argument("proyecto", nargs="?", default=".")
    p_check.set_defaults(func=cmd_comprobar)

    p_probar = sub.add_parser("probar", aliases=["preview", "play"],
                              help="genera y abre el preview jugable")
    p_probar.add_argument("proyecto", nargs="?", default=".")
    p_probar.add_argument("--salida", help="ruta del HTML de salida")
    p_probar.add_argument("--no-abrir", action="store_true", help="no abrir el navegador")
    p_probar.set_defaults(func=cmd_probar)

    p_build = sub.add_parser("compilar", aliases=["build"],
                             help="genera el proyecto en C y las ROMs graficas")
    p_build.add_argument("proyecto", nargs="?", default=".")
    p_build.add_argument("--salida", help="carpeta de salida (por defecto build/)")
    p_build.add_argument("--rom-id", default="202",
                         help="identificador del romset (por defecto 202)")
    p_build.add_argument("--make", action="store_true",
                         help="ejecuta make para construir la ROM (necesita ngdevkit)")
    p_build.set_defaults(func=cmd_compilar)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    try:
        return args.func(args)
    except ProjectError as exc:
        print(_color(exc.render(), ROJO), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
