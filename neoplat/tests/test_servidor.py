"""El servidor local que deja al editor generar la ROM.

Se levanta de verdad y se le hacen peticiones como las que hace el navegador:
las buenas tienen que compilar y las malas tienen que rebotar. Que reboten
importa tanto como lo otro: es un proceso que escribe en tu proyecto y lanza
`make`, y los navegadores dejan que cualquier pagina hable con localhost.
"""

import base64
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


def _png_de_prueba() -> str:
    """Un PNG de 2x2 de verdad, hecho con el codificador del kit."""
    from ngplat.png import Image, encode_png
    imagen = Image(2, 2, [(255, 0, 0, 255), (0, 255, 0, 255),
                          (0, 0, 255, 255), (0, 0, 0, 0)])
    return "data:image/png;base64," + base64.b64encode(encode_png(imagen)).decode("ascii")


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

    def _dibujo(self, cuerpo, clave=None):
        datos = json.dumps(cuerpo).encode("utf-8")
        peticion = urllib.request.Request(
            self._url("/dibujo", clave), data=datos,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(peticion, timeout=60) as respuesta:
                return respuesta.status, json.load(respuesta)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def _post(self, camino, cuerpo, clave=None):
        datos = json.dumps(cuerpo).encode("utf-8")
        peticion = urllib.request.Request(
            self._url(camino, clave), data=datos,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(peticion, timeout=120) as respuesta:
                return respuesta.status, json.load(respuesta)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

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

    # --- guardar sin compilar -------------------------------------------

    def test_guardar_escribe_el_yaml_sin_compilar(self):
        """Guardar y compilar son dos cosas distintas: esta escribe y ya."""
        ruta = servidor.ruta_del_yaml(self.raiz)
        with open(ruta, encoding="utf-8") as fh:
            original = fh.read()
        codigo, datos = self._post("/guardar",
                                   {"yaml": original + "\n# guardado a secas\n"})
        self.assertEqual(codigo, 200)
        self.assertTrue(datos["ok"], datos["lineas"])
        with open(ruta, encoding="utf-8") as fh:
            self.assertIn("guardado a secas", fh.read())

    def test_guardar_deja_copia_en_el_historial(self):
        from ngplat import historial
        antes = len(historial.listar(self.raiz))
        ruta = servidor.ruta_del_yaml(self.raiz)
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        # marcadores raros a proposito: "# uno" o "# dos" aparecen en los
        # comentarios del andamiaje y la prueba pasaria (o fallaria) sola
        self._post("/guardar", {"yaml": texto + "\n#MARCA-PRIMERA\n"})
        self._post("/guardar", {"yaml": texto + "\n#MARCA-SEGUNDA\n"})
        copias = historial.listar(self.raiz)
        self.assertGreater(len(copias), antes, "guardar no ha dejado copia")
        # y de esa copia se puede volver al texto anterior
        numero = int(copias[0]["numero"])
        _codigo, datos = self._post("/recuperar", {"copia": numero})
        self.assertTrue(datos["ok"], datos["lineas"])
        with open(ruta, encoding="utf-8") as fh:
            recuperado = fh.read()
        self.assertIn("#MARCA-PRIMERA", recuperado)
        self.assertNotIn("#MARCA-SEGUNDA", recuperado)

    def test_se_guarda_un_juego_a_medias_que_todavia_no_compila(self):
        """Esta es la razon de ser de /guardar: un nivel empezado no compila, y
        antes era justo lo que no se podia dejar escrito."""
        ruta = servidor.ruta_del_yaml(self.raiz)
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        # una meta que pide mas llaves de las que hay: el proyecto no carga
        roto = texto.replace("    llaves: 1", "    llaves: 9", 1)
        self.assertNotEqual(roto, texto, "el andamiaje ya no trae 'llaves: 1'")
        codigo, datos = self._post("/guardar", {"yaml": roto})
        self.assertEqual(codigo, 200)
        self.assertTrue(datos["ok"], datos["lineas"])
        with open(ruta, encoding="utf-8") as fh:
            self.assertIn("llaves: 9", fh.read(),
                          "no ha guardado un proyecto a medias")
        self.assertTrue(any("todavia no compila" in l for l in datos["lineas"]),
                        datos["lineas"])
        # y se puede volver a dejar como estaba
        self._post("/guardar", {"yaml": texto})

    def test_guardar_tambien_escribe_los_dibujos(self):
        codigo, datos = self._post("/guardar", {
            "yaml": "",
            "dibujos": [{"ruta": "graficos/desde-guardar.png",
                         "datos": _png_de_prueba()}]})
        self.assertEqual(codigo, 200)
        self.assertTrue(datos["ok"], datos["lineas"])
        self.assertTrue(os.path.isfile(
            os.path.join(self.raiz, "graficos", "desde-guardar.png")))

    def test_un_yaml_que_no_es_yaml_no_se_guarda(self):
        """Trabajo a medias si; un archivo roto no: eso seria un fallo del
        editor, no algo que el usuario haya escrito."""
        ruta = servidor.ruta_del_yaml(self.raiz)
        with open(ruta, encoding="utf-8") as fh:
            bueno = fh.read()
        codigo, datos = self._post("/guardar", {"yaml": "juego:\n\tmal: [1,\n"})
        self.assertEqual(codigo, 200)
        self.assertFalse(datos["ok"], datos["lineas"])
        with open(ruta, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), bueno)

    def test_el_historial_se_puede_pedir(self):
        _codigo, datos = self._post("/historial", {})
        self.assertTrue(datos["ok"])
        self.assertIsInstance(datos["copias"], list)
        for copia in datos["copias"]:
            self.assertIn("numero", copia)
            self.assertIn("motivo", copia)

    def test_no_se_recupera_una_copia_inventada(self):
        _codigo, datos = self._post("/recuperar", {"copia": 4321})
        self.assertFalse(datos["ok"])

    def test_sin_clave_no_se_guarda(self):
        codigo, _datos = self._post("/guardar", {"yaml": "# no"}, clave="mentira")
        self.assertEqual(codigo, 403)

    def test_sin_clave_no_se_recupera(self):
        codigo, _datos = self._post("/recuperar", {"copia": 1}, clave="mentira")
        self.assertEqual(codigo, 403)

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

    # --- el editor de dibujos -------------------------------------------

    def test_guarda_un_dibujo_en_el_proyecto(self):
        """Lo que dibujas en el navegador acaba en graficos/ sin tocar nada."""
        codigo, respuesta = self._dibujo({"ruta": "graficos/heroe.png",
                                          "datos": _png_de_prueba()})
        self.assertEqual(codigo, 200)
        self.assertTrue(respuesta["ok"], respuesta)
        destino = os.path.join(self.raiz, "graficos", "heroe.png")
        with open(destino, "rb") as fh:
            guardado = fh.read()
        self.assertEqual(guardado[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(len(guardado), respuesta["bytes"])

    def test_un_dibujo_no_puede_salirse_del_proyecto(self):
        """La ruta la manda el navegador, asi que no se da por buena."""
        for ruta in ("../fuera.png", "/tmp/fuera.png", "graficos/../../fuera.png",
                     "graficos/algo.txt", ""):
            codigo, respuesta = self._dibujo({"ruta": ruta, "datos": _png_de_prueba()})
            self.assertEqual(codigo, 400, "ha aceptado la ruta '%s'" % ruta)
            self.assertFalse(respuesta["ok"])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "fuera.png")))

    def test_solo_se_guardan_pngs_de_verdad(self):
        for datos in ("data:image/png;base64,bm8gc295IHVuIHBuZw==",
                      "data:text/plain;base64,aG9sYQ==",
                      "no soy un data uri"):
            codigo, respuesta = self._dibujo({"ruta": "graficos/x.png", "datos": datos})
            self.assertEqual(codigo, 400, datos[:40])
            self.assertFalse(respuesta["ok"])

    def test_sin_clave_no_se_guardan_dibujos(self):
        codigo, _ = self._dibujo({"ruta": "graficos/x.png",
                                  "datos": _png_de_prueba()}, clave="mentira")
        self.assertEqual(codigo, 403)

    def test_no_hay_mas_rutas(self):
        self.assertEqual(self._codigo(lambda: self._pedir("/etc/passwd")), 404)
        self.assertEqual(self._codigo(lambda: self._pedir("/../servidor.py")), 404)


if __name__ == "__main__":
    unittest.main()
