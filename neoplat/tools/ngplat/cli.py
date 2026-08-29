"""La orden `ngplat`: crear, comprobar, probar y compilar juegos NeoPlat."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from typing import List, Optional

from . import __version__
from . import sistemas
from .build import build_project
from .codegen import generar_para_sistema
from .errors import ProjectError
from . import historial as hist
from .preview import write_preview
from .project import load_project
from .scaffold import (ESTILOS, GENEROS, crear_proyecto, genero_de,
                       menu_de_generos)

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


def _cargar(ruta: str, sistema_nombre: str = ""):
    """Carga el proyecto y lo prepara para la maquina de destino."""
    project = load_project(ruta)
    for warning in project.warnings:
        _aviso(warning)
    sistema = sistemas.obtener(sistema_nombre or project.system)
    build = build_project(project)
    sistema.preparar(build)
    for aviso in sistema.comprobar(build):
        _aviso(aviso)
    return project, build, sistema


# ------------------------------------------------------------------ ordenes

def cmd_nuevo(args: argparse.Namespace) -> int:
    # Sin `--genero` y con alguien delante, se pregunta. En un guion o en las
    # pruebas no hay a quien preguntar, asi que sale el de por defecto y nada
    # se queda esperando en una tuberia.
    genero = getattr(args, "genero", None)
    if not genero:
        genero = menu_de_generos() if sys.stdin.isatty() else GENEROS[0]
    creados = crear_proyecto(args.carpeta,
                             args.titulo or os.path.basename(args.carpeta.rstrip("/")),
                             args.autor or "", args.estilo, genero)
    _ok("proyecto creado en '%s'" % args.carpeta)
    _info("genero: %s -- %s" % (genero, genero_de(genero, args.estilo).resumen))
    for nombre in creados:
        _info(nombre)
    print()
    print("Siguiente paso:")
    print("  cd %s" % args.carpeta)
    print("  ngplat probar        # abre el preview jugable en el navegador")
    print("  ngplat compilar      # genera el proyecto en C y las ROMs graficas")
    return 0


def cmd_comprobar(args: argparse.Namespace) -> int:
    project, build, sistema = _cargar(args.proyecto, args.sistema)
    stats = build.stats()
    _ok("'%s' es valido para %s" % (project.title, sistema.titulo))
    print()
    print("  sistema         %s (%s)" % (sistema.titulo, sistema.cpu))
    print("  pantalla        %d x %d" % sistema.pantalla)
    print("  niveles         %d" % stats["niveles"])
    for level in build.levels:
        print("    %-20s %3d x %-3d tiles, %2d entidades"
              % (level.name, level.width, level.height, len(level.spawns)))
    print("  enemigos        %d" % stats["enemigos"])
    print("  objetos         %d" % stats["objetos"])
    if stats.get("plataformas"):
        print("  plataformas     %d" % stats["plataformas"])
    if stats.get("rompibles"):
        print("  rompibles       %d" % stats["rompibles"])
    if "tiles_sprite" in stats:
        print("  tiles de sprite %d  (%d KB de ROM C)"
              % (stats["tiles_sprite"], (stats["bytes_c1"] + stats["bytes_c2"]) // 1024))
        print("  tiles de fix    %d" % stats["tiles_fix"])
    if "tiles_8x8" in stats:
        print("  tiles de 8x8    %d  (%d KB en la ROM)"
              % (stats["tiles_8x8"], stats["bytes_tiles"] // 1024))
    if "dibujos_16x16" in stats:
        print("  dibujos 16x16   %d  (%d KB de dibujos + %d KB de mascaras)"
              % (stats["dibujos_16x16"], stats["bytes_dibujos"] // 1024,
                 stats["bytes_mascaras"] // 1024))
    if sistema.limites.paletas > 1:
        print("  paletas         %d de %d" % (stats["paletas"], sistema.limites.paletas))
    else:
        # el Amiga no reparte paletas: tiene una sola de 32 colores
        print("  colores         %d de %d"
              % (stats.get("colores", 0), sistema.limites.colores_en_pantalla))
    print("  capas de fondo  %d" % stats["capas"])
    print("  efectos         %d" % stats["efectos"])
    print("  musicas         %d" % stats["musicas"])
    print("  mapas           %d bytes" % stats["bytes_mapas"])
    return 0


def cmd_probar(args: argparse.Namespace) -> int:
    project, build, sistema = _cargar(args.proyecto, args.sistema)
    destino = args.salida or os.path.join(project.root, "preview.html")
    write_preview(build, destino)
    _ok("preview generado: %s" % destino)

    if args.no_abrir or args.no_servidor:
        if not args.no_abrir:
            _abrir("file://" + os.path.abspath(destino))
        return 0
    return _servir(project.root, destino, args.puerto)


def _abrir(direccion: str) -> None:
    try:
        import webbrowser

        webbrowser.open(direccion)
        _info("abriendo en el navegador...")
    except Exception:
        _info("abrelo a mano en tu navegador")


def _servir(raiz: str, preview: str, puerto: int) -> int:
    """Sirve el preview desde localhost para que el editor pueda guardar y compilar.

    Abierto como file://, el editor solo puede exportar el game.yaml: una
    pagina no escribe en tu disco ni compila nada. Servido desde aqui, el boton
    "guardar" (o Ctrl+S) escribe en el proyecto y el de compilar genera las
    ROMs; este proceso hace el trabajo.
    """
    from .servidor import crear

    servidor, direccion = crear(raiz, preview, puerto)
    _ok("servidor en %s" % direccion)
    _info("en el editor: 'guardar' (o Ctrl+S) escribe en el proyecto y deja copia")
    _info("y la pestana 'compilar' genera las ROMs")
    _info("Ctrl+C para parar")
    _abrir(direccion)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print()
        _info("servidor parado")
    finally:
        servidor.server_close()
    return 0


def cmd_compilar(args: argparse.Namespace) -> int:
    project, build, sistema = _cargar(args.proyecto, args.sistema)
    out_dir = args.salida or os.path.join(project.root, "build", sistema.nombre)
    os.makedirs(out_dir, exist_ok=True)

    binarios, salida = generar_para_sistema(build, out_dir, sistema, args.rom_id)

    stats = build.stats()
    _ok("proyecto para %s generado en '%s'" % (sistema.titulo, out_dir))
    _info("codigo:   src/ (motor + tu juego)")
    for linea in salida.resumen:
        _info(linea)
    # se monta como lista y no encadenando condicionales: encadenados, el
    # 'else' se comia el trozo siguiente y los rompibles no salian nunca
    partes = ["%d niveles" % stats["niveles"],
              "%d enemigos" % stats["enemigos"],
              "%d objetos" % stats["objetos"]]
    for clave, singular, plural in (("plataformas", "plataforma", "plataformas"),
                                    ("rompibles", "rompible", "rompibles")):
        cuantos = stats.get(clave, 0)
        if cuantos:
            partes.append("%d %s" % (cuantos, singular if cuantos == 1 else plural))
    partes.append("%d efectos" % stats["efectos"])
    partes.append("%d musicas" % stats["musicas"])
    if build.project.players > 1:
        partes.append("a dos jugadores")
    _info(", ".join(partes))

    if args.make:
        return _ejecutar_make(out_dir, sistema)

    print()
    compilador = _compilador_de(sistema)
    if compilador:
        print("Compila con:")
        print("  cd %s && make" % out_dir)
    else:
        print("Para construir el binario necesitas un compilador de 68000:")
        print("  " + _como_instalar(sistema))
        print("Cuando lo tengas:  cd %s && make" % out_dir)
    return 0


def _compilador_de(sistema) -> str:
    candidatos = {
        "neogeo": ["m68k-neogeo-elf-gcc", "m68k-elf-gcc"],
        "megadrive": ["m68k-elf-gcc", "m68k-linux-gnu-gcc"],
        "amiga": ["m68k-amigaos-gcc", "vc", "m68k-elf-gcc", "m68k-linux-gnu-gcc"],
        "jaguar": ["m68k-linux-gnu-gcc", "m68k-elf-gcc"],
        "atarist": ["m68k-atari-mint-gcc", "m68k-elf-gcc", "m68k-linux-gnu-gcc"],
    }
    for nombre in candidatos.get(sistema.nombre, ["m68k-elf-gcc"]):
        if shutil.which(nombre):
            return nombre
    return ""


def _como_instalar(sistema) -> str:
    return {
        "neogeo": "ngdevkit: https://github.com/dciabrin/ngdevkit",
        "megadrive": "apt install gcc-m68k-linux-gnu   (o el m68k-elf-gcc que uses)",
        "amiga": "apt install gcc-m68k-linux-gnu   (o vbcc / m68k-amigaos-gcc)",
        "jaguar": "apt install gcc-m68k-linux-gnu   (el GPU y el DSP no se usan)",
        "atarist": "apt install gcc-m68k-linux-gnu   (o m68k-atari-mint-gcc)",
    }.get(sistema.nombre, "un gcc para 68000")


def _ejecutar_make(out_dir: str, sistema) -> int:
    if not _compilador_de(sistema):
        raise ProjectError(
            "no encuentro un compilador de 68000 para %s" % sistema.titulo,
            hint=_como_instalar(sistema),
        )
    _info("ejecutando make en %s" % out_dir)
    result = subprocess.run(["make"], cwd=out_dir)
    if result.returncode != 0:
        raise ProjectError("make ha fallado (codigo %d)" % result.returncode)
    _ok("binario construido en %s" % os.path.join(out_dir, sistema.carpeta_salida))
    return 0


# ------------------------------------------------------------------- parser

def _ayuda_sistemas() -> str:
    return "maquina de destino: %s" % ", ".join(s.nombre for s in sistemas.disponibles())


def _cuando_legible(cuando: str) -> str:
    """'20260829-174501' -> '2026-08-29 17:45'."""
    if len(cuando) != 15:
        return cuando
    return "%s-%s-%s %s:%s" % (cuando[0:4], cuando[4:6], cuando[6:8],
                               cuando[9:11], cuando[11:13])


def cmd_copia(args: argparse.Namespace) -> int:
    """Guarda una copia del proyecto tal y como esta ahora."""
    ficha = hist.copiar(args.proyecto, args.motivo)
    if ficha is None:
        _info("no ha cambiado nada desde la ultima copia: no hace falta otra")
        return 0
    _ok("copia %04d guardada (%d archivos, %d KB)"
        % (ficha["numero"], ficha["archivos"], int(ficha["bytes"]) // 1024))
    _info("en %s" % os.path.join(args.proyecto, hist.HISTORIAL, str(ficha["archivo"])))
    return 0


def cmd_historial(args: argparse.Namespace) -> int:
    """Lista las copias que hay guardadas."""
    copias = hist.listar(args.proyecto)
    if not copias:
        _info("todavia no hay ninguna copia de este proyecto")
        _info("se hacen solas al guardar desde el editor, o con 'ngplat copia'")
        return 0
    print()
    print("  %-6s %-17s %-18s %8s  %s"
          % ("copia", "cuando", "motivo", "tamano", "archivos"))
    for copia in copias:
        roto = "  (rota)" if copia.get("roto") else ""
        print("  %04d   %-17s %-18s %6d KB  %d%s"
              % (copia["numero"], _cuando_legible(str(copia["cuando"])),
                 copia["motivo"], int(copia["bytes"]) // 1024,
                 copia["archivos"], roto))
    print()
    _info("para volver a una: ngplat recuperar %04d" % copias[0]["numero"])
    return 0


def cmd_recuperar(args: argparse.Namespace) -> int:
    """Devuelve el proyecto a como estaba en una copia."""
    escritos, sobrantes = hist.recuperar(args.proyecto, args.copia)
    _ok("proyecto devuelto a la copia %04d" % args.copia)
    _info("%d archivos restaurados" % len(escritos))
    for relativo in sobrantes:
        _info("quitado (no estaba en esa copia): %s" % relativo)
    _info("como estaba antes ha quedado guardado: ngplat historial")
    return 0


def cmd_sistemas(args: argparse.Namespace) -> int:
    print("Sistemas que puede compilar NeoPlat:")
    print()
    for sistema in sistemas.disponibles():
        limites = sistema.limites
        if limites.paletas > 1:
            colores = "%d colores a la vez (%d paletas de %d)" % (
                limites.colores_en_pantalla, limites.paletas,
                limites.colores_por_paleta)
        else:
            colores = "%d colores a la vez, en una sola paleta" % (
                limites.colores_en_pantalla)
        actores = ("%d sprites" % limites.sprites) if limites.sprites else \
            sistema.dibujo_actores
        print("  %-11s %s" % (sistema.nombre, sistema.titulo))
        print("  %-11s %s, pantalla %dx%d" % ("", sistema.cpu, *sistema.pantalla))
        print("  %-11s %s, %s" % ("", colores, actores))
        print("  %-11s sale:     %s, en build/%s/%s/"
              % ("", sistema.nombre_binario, sistema.nombre, sistema.carpeta_salida))
        for nota in sistema.notas:
            print("  %-11s %s" % ("", nota))
        print()
    print("Se elige con 'sistema:' en el game.yaml o con --sistema al compilar.")
    return 0


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
    p_nuevo.add_argument("--estilo", choices=ESTILOS, default="bosque",
                         help="dibujos de partida: 'bosque' (colores libres) o "
                              "'hierro' (seis colores, listo para el doble plano "
                              "del Amiga)")
    p_nuevo.add_argument("--genero", choices=GENEROS, default=None,
                         help="como se juega: 'plataformas' (saltar, pisar y "
                              "disparar) o 'castlevania' (latigo, escaleras y "
                              "municion). Sin esto, se pregunta")
    p_nuevo.set_defaults(func=cmd_nuevo)

    p_check = sub.add_parser("comprobar", aliases=["check"],
                             help="valida game.yaml y muestra el tamano del juego")
    p_check.add_argument("proyecto", nargs="?", default=".")
    p_check.add_argument("--sistema", default="", help=_ayuda_sistemas())
    p_check.set_defaults(func=cmd_comprobar)

    p_probar = sub.add_parser("probar", aliases=["preview", "play"],
                              help="genera y abre el preview jugable")
    p_probar.add_argument("proyecto", nargs="?", default=".")
    p_probar.add_argument("--salida", help="ruta del HTML de salida")
    p_probar.add_argument("--no-abrir", action="store_true",
                          help="solo generar el HTML, sin abrir ni servir")
    p_probar.add_argument("--no-servidor", action="store_true",
                          help="abrir el HTML como file:// (sin generar ROM desde el editor)")
    p_probar.add_argument("--puerto", type=int, default=0,
                          help="puerto del servidor local (0 = el que haya libre)")
    p_probar.add_argument("--sistema", default="", help=_ayuda_sistemas())
    p_probar.set_defaults(func=cmd_probar)

    p_build = sub.add_parser("compilar", aliases=["build"],
                             help="genera el proyecto en C y las ROMs graficas")
    p_build.add_argument("proyecto", nargs="?", default=".")
    p_build.add_argument("--salida", help="carpeta de salida (por defecto build/)")
    p_build.add_argument("--rom-id", default="202",
                         help="identificador del romset (por defecto 202)")
    p_build.add_argument("--sistema", default="", help=_ayuda_sistemas())
    p_build.add_argument("--make", action="store_true",
                         help="ejecuta make para construir el binario")
    p_build.set_defaults(func=cmd_compilar)

    p_copia = sub.add_parser("copia", aliases=["save", "guardar"],
                             help="guarda una copia del proyecto en su historial")
    p_copia.add_argument("proyecto", nargs="?", default=".")
    p_copia.add_argument("--motivo", default="manual",
                         help="una palabra para reconocerla en la lista")
    p_copia.set_defaults(func=cmd_copia)

    p_hist = sub.add_parser("historial", aliases=["history", "copias"],
                            help="lista las copias guardadas del proyecto")
    p_hist.add_argument("proyecto", nargs="?", default=".")
    p_hist.set_defaults(func=cmd_historial)

    p_rec = sub.add_parser("recuperar", aliases=["restore"],
                           help="devuelve el proyecto a una copia anterior")
    p_rec.add_argument("copia", type=int, help="numero que sale en 'ngplat historial'")
    p_rec.add_argument("proyecto", nargs="?", default=".")
    p_rec.set_defaults(func=cmd_recuperar)

    p_sistemas = sub.add_parser("sistemas", aliases=["systems"],
                                help="lista las maquinas de destino")
    p_sistemas.set_defaults(func=cmd_sistemas)

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
    except hist.ErrorHistorial as exc:
        print(_color("  error " + str(exc), ROJO), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
