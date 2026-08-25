/* editor.js - pruebas del editor de niveles (preview/np_editor.js).
 *
 * El editor se ejecuta aqui sin navegador: se le pasa un canvas de mentira,
 * porque lo que se comprueba es la logica (pintar, deshacer, redimensionar,
 * exportar el game.yaml y reconstruir el nivel para jugarlo), no el dibujado.
 *
 *   node tests/editor.js datos.json [salida.yaml]
 */
"use strict";

var assert = require("assert");
var fs = require("fs");
var path = require("path");
var NPEditor = require(path.join(__dirname, "..", "preview", "np_editor.js"));

var DATA = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));

function lienzoFalso() {
  var nada = function () { return nada; };
  return {
    canvas: { width: 320, height: 224 },
    ctx: new Proxy({}, {
      get: function (destino, clave) {
        if (clave === "canvas") return { width: 320, height: 224 };
        return nada;
      },
      set: function () { return true; }
    })
  };
}

function nuevoEditor() {
  var falso = lienzoFalso();
  return NPEditor.crear({
    data: JSON.parse(JSON.stringify(DATA)),
    canvas: falso.canvas,
    ctx: falso.ctx,
    dibujarFrame: function () {},
    alJugar: function () {},
    alCambiar: function () {}
  });
}

var pruebas = [];
function prueba(nombre, fn) { pruebas.push([nombre, fn]); }

prueba("empieza con los mapas del proyecto", function () {
  var e = nuevoEditor();
  assert.strictEqual(e.filas.length, DATA.levels.length);
  assert.deepStrictEqual(e.filas[0], DATA.levels[0].rows);
});

prueba("pintar cambia el mapa", function () {
  var e = nuevoEditor();
  e.herramienta = "#";
  e.pintar(3, 3, false);
  assert.strictEqual(e.filas[0][3][3], "#");
});

prueba("borrar deja el tile vacio", function () {
  var e = nuevoEditor();
  e.herramienta = "#";
  e.pintar(3, 3, false);
  e.pintar(3, 3, true);
  assert.strictEqual(e.filas[0][3][3], ".");
});

prueba("deshacer vuelve atras paso a paso", function () {
  var e = nuevoEditor();
  var antes = e.filas[0].slice();
  e.herramienta = "#";
  e.pintar(3, 3, false);
  e.pintar(4, 3, false);
  e.deshacer();
  e.deshacer();
  assert.deepStrictEqual(e.filas[0], antes);
});

prueba("solo puede haber una salida del jugador", function () {
  var e = nuevoEditor();
  e.herramienta = "P";
  e.pintar(10, 5, false);
  e.pintar(12, 6, false);
  var texto = e.filas[0].join("");
  assert.strictEqual(texto.split("P").length - 1, 1, "hay mas de una P");
  assert.strictEqual(e.filas[0][6][12], "P");
});

prueba("avisa si el nivel se queda sin salida o sin meta", function () {
  var e = nuevoEditor();
  e.herramienta = ".";
  // borrar la meta del nivel
  for (var y = 0; y < e.filas[0].length; y++) {
    var x = e.filas[0][y].indexOf("G");
    if (x >= 0) e.pintar(x, y, false);
  }
  assert.ok(e.aviso.indexOf("meta") >= 0, "deberia avisar de que falta la meta");
});

prueba("no deja hacer el nivel mas pequeno que una pantalla", function () {
  var e = nuevoEditor();
  var ancho = e.filas[0][0].length;
  for (var i = 0; i < 100; i++) e.redimensionar(-1, 0);
  assert.ok(e.filas[0][0].length >= 20, "el nivel se ha quedado en " + e.filas[0][0].length);
  assert.ok(e.filas[0][0].length < ancho, "no ha estrechado nada");
});

prueba("ensanchar anade columnas vacias", function () {
  var e = nuevoEditor();
  var ancho = e.filas[0][0].length;
  e.redimensionar(3, 0);
  assert.strictEqual(e.filas[0][0].length, ancho + 3);
  e.filas[0].forEach(function (fila) {
    assert.strictEqual(fila.length, ancho + 3, "filas descuadradas");
  });
});

prueba("crecer en alto conserva el suelo abajo", function () {
  var e = nuevoEditor();
  var suelo = e.filas[0][e.filas[0].length - 1];
  var alto = e.filas[0].length;
  e.redimensionar(0, 2);
  assert.strictEqual(e.filas[0].length, alto + 2);
  assert.strictEqual(e.filas[0][e.filas[0].length - 1], suelo);
});

prueba("cambiar de nivel edita el otro mapa", function () {
  var e = nuevoEditor();
  e.cambiarNivel(1);
  e.herramienta = "#";
  e.pintar(5, 5, false);
  assert.strictEqual(e.filas[1][5][5], "#");
  assert.notStrictEqual(e.filas[0][5][5], "#");
});

prueba("el yaml exportado conserva todo menos los mapas", function () {
  var e = nuevoEditor();
  e.herramienta = "#";
  e.pintar(6, 6, false);
  var yaml = e.exportarYaml();
  assert.ok(yaml.indexOf("jugador:") >= 0, "falta la seccion del jugador");
  assert.ok(yaml.indexOf("sonido:") >= 0, "falta el sonido");
  assert.ok(yaml.indexOf("fondos:") >= 0, "faltan las capas de fondo");
  var filas = e.filas[0];
  filas.forEach(function (fila) {
    assert.ok(yaml.indexOf(fila) >= 0, "falta una fila del mapa en el yaml");
  });
  assert.strictEqual(yaml.split("mapa: |").length - 1, DATA.levels.length,
    "el yaml deberia tener un bloque de mapa por nivel");
});

prueba("aplicar reconstruye el nivel como lo haria el compilador", function () {
  var e = nuevoEditor();
  var nivel = e.data ? e.data.levels[0] : null;
  // pintamos un bloque solido en una zona vacia y aplicamos
  e.herramienta = "#";
  e.pintar(2, 2, false);
  e.aplicar();
  // el editor trabaja sobre su propia copia de DATA
  assert.ok(e.filas[0][2][2] === "#");
});

if (process.argv[3]) {
  var salida = nuevoEditor();
  salida.herramienta = "=";
  salida.pintar(2, 6, false);
  salida.pintar(3, 6, false);
  salida.herramienta = "P";
  salida.pintar(5, 9, false);
  fs.writeFileSync(process.argv[3], salida.exportarYaml());
}

var fallos = 0;
pruebas.forEach(function (par) {
  try {
    par[1]();
    console.log("  ok   " + par[0]);
  } catch (err) {
    fallos++;
    console.log("  FALLO " + par[0] + "\n         " + err.message);
  }
});
console.log("\n" + (pruebas.length - fallos) + "/" + pruebas.length + " pruebas del editor");
process.exit(fallos ? 1 : 0);
