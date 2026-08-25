"""El servidor local que deja al editor generar la ROM.

Se levanta de verdad y se le hacen peticiones como las que hace el navegador:
las buenas tienen que compilar y las malas tienen que rebotar. Que reboten
importa tanto como lo otro: es un proceso que escribe en tu proyecto y lanza
`make`, y los navegadores dejan que cualquier pagina hable con localhost.
"""

import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import comun
from ngplat import servidor
from ngplat.scaffold import crear_proyecto


class TestServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-servidor-")
        cls.raiz = os.path.join(cls.tmp, "juego")
        crear_proyecto(cls.raiz, "PRUEBA", "TEST")
        cls.preview = os.path.join(cls.tmp, "preview.html")
        with open(cls.preview, "w", encoding="utf-8") as fh:
            fh.write("<!doctype html><title>preview</title>")
        cls.servidor, cls.direccion = servidor.crear(cls.raiz, cls.preview)
        cls.hilo = threading.Thread(target=cls.servidor.serve_forever, daemon=True)
        cls.hilo.start()
        cls.puerto = cls.servidor.server_address[1]
        cls.clave = cls.servidor.clave

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # --- utilidades -----------------------------------------------------

    def _url(self, camino, clave=None):
        return "http://127.0.0.1:%d%s?t=%s" % (
            self.puerto, camino, self.clave if clave is None else clave)

    def _pedir(self, camino, clave=None, cabeceras=None):
        peticion = urllib.request.Request(self._url(camino, clave))
        for nombre, valor in (cabeceras or {}).items():
            peticion.add_header(nombre, valor)
        return urllib.request.urlopen(peticion, timeout=30)

    def _compilar(self, cuerpo, clave=None, cabeceras=None):
        datos = json.dumps(cuerpo).encode("utf-8")
        peticion = urllib.request.Request(
            self._url("/compilar", clave), data=datos,
            headers={"Content-Type": "application/json"})
        for nombre, valor in (cabeceras or {}).items():
            peticion.add_header(nombre, valor)
        with urllib.request.urlopen(peticion, timeout=300) as respuesta:
            return json.load(respuesta)

    def _codigo(self, hacer):
        try:
            hacer()
        except urllib.error.HTTPError as error:
            return error.code
        return 200

    # --- lo que tiene que funcionar -------------------------------------

    def test_la_direccion_lleva_la_clave(self):
        self.assertIn("127.0.0.1", self.direccion)
        self.assertIn("?t=" + self.clave, self.direccion)
        self.assertGreaterEqual(len(self.clave), 24)

    def test_sirve_el_preview(self):
        with self._pedir("/") as respuesta:
            self.assertIn(b"preview", respuesta.read())

    def test_genera_el_proyecto(self):
        datos = self._compilar({"sistema": "neogeo", "make": False})
        self.assertTrue(datos["ok"], datos["lineas"])
        self.assertTrue(os.path.isfile(
            os.path.join(self.raiz, "build", "neogeo", "src", "gamedata.c")))

    def test_guarda_el_yaml_que_manda_el_editor(self):
        ruta = servidor.ruta_del_yaml(self.raiz)
        with open(ruta, "r", encoding="utf-8") as fh:
            original = fh.read()
        cambiado = original.replace("vidas:", "vidas:", 1) + "\n# escrito por el editor\n"
        datos = self._compilar({"yaml": cambiado, "sistema": "neogeo", "make": False})
        self.assertTrue(datos["ok"], datos["lineas"])
        with open(ruta, "r", encoding="utf-8") as fh:
            self.assertIn("escrito por el editor", fh.read())
        with open(ruta + ".bak", "r", encoding="utf-8") as fh:
            self.assertEqual(fh.read(), original, "no ha dejado copia del anterior")

    def test_un_yaml_roto_no_pisa_el_bueno(self):
        ruta = servidor.ruta_del_yaml(self.raiz)
        with open(ruta, "r", encoding="utf-8") as fh:
            bueno = fh.read()
        datos = self._compilar({"yaml": "esto: [no cierra\n", "sistema": "neogeo",
                                "make": False})
        self.assertFalse(datos["ok"])
        with open(ruta, "r", encoding="utf-8") as fh:
            self.assertEqual(fh.read(), bueno,
                             "ha dejado escrito un game.yaml que no se puede leer")

    # --- lo que tiene que rebotar ---------------------------------------

    def test_sin_clave_no_se_entra(self):
        self.assertEqual(self._codigo(lambda: self._pedir("/", clave="")), 403)
        self.assertEqual(self._codigo(lambda: self._pedir("/", clave="otra")), 403)

    def test_sin_clave_no_se_compila(self):
        try:
            self._compilar({"sistema": "neogeo"}, clave="otra")
        except urllib.error.HTTPError as error:
            self.assertEqual(error.code, 403)
        else:
            self.fail("ha compilado sin la clave")

    def test_otra_pagina_no_puede_compilar(self):
        """Con la clave pero desde otro sitio: eso es una peticion de otra web."""
        try:
            self._compilar({"sistema": "neogeo"},
                           cabeceras={"Origin": "https://otro.example"})
        except urllib.error.HTTPError as error:
            self.assertEqual(error.code, 403)
        else:
            self.fail("ha aceptado una peticion de otro origen")

    def test_solo_responde_a_localhost(self):
        """Corta el 'DNS rebinding': un nombre que apunte aqui no vale."""
        try:
            self._pedir("/", cabeceras={"Host": "cualquiera.example"})
        except urllib.error.HTTPError as error:
            self.assertEqual(error.code, 403)
        else:
            self.fail("ha respondido a un Host que no es localhost")

    def test_no_compila_para_una_maquina_inventada(self):
        try:
            self._compilar({"sistema": "spectrum"})
        except urllib.error.HTTPError as error:
            self.assertEqual(error.code, 400)
        else:
            self.fail("ha aceptado una maquina que no existe")

    def test_no_hay_mas_rutas(self):
        self.assertEqual(self._codigo(lambda: self._pedir("/etc/passwd")), 404)
        self.assertEqual(self._codigo(lambda: self._pedir("/../servidor.py")), 404)


if __name__ == "__main__":
    unittest.main()
