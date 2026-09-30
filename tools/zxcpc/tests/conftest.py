import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DATA = os.path.join(ROOT, "tests", "data")

# ROMs opcionales (no se distribuyen): solo para las pruebas que las necesitan
ZX_ROM = os.environ.get("ZXCPC_ZX_ROM", "/usr/share/spectrum-roms/48.rom")
CPC_ROM = os.environ.get("ZXCPC_CPC_ROM", "")


def data(name):
    return os.path.join(DATA, name)


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    """Ensambla los juegos de prueba una vez y devuelve {nombre: (ruta .bin, símbolos)}."""
    from zxcpc.z80.asm import assemble_file
    out = tmp_path_factory.mktemp("bin")
    res = {}
    for name in ("zxgame", "zxgame2", "cpcgame", "cpcgame_hw"):
        r = assemble_file(data(name + ".asm"))
        path = out / (name + ".bin")
        path.write_bytes(r.image())
        res[name] = (str(path), r.symbols, r.start)
    return res
