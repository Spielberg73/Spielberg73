/* editor_mazmorra.js - el editor con un juego que trae generadores.
 *
 * El editor conoce los bichos por su `kind`, y hasta ahora la tabla se paraba
 * en el rompible: un nido (kind 9) o un prisionero (kind 8) caian en la lista
 * de objetos, que es otra, y salian en la paleta con el nombre y el dibujo de
 * lo que hubiera en esa posicion. Aqui se comprueba con el proyecto de
 * mazmorra, que trae las dos cosas.
 *
 *   node tests/editor_mazmorra.js datos.json
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
    canvas: { width: 480, height: 312 },
    ctx: new Proxy({}, {
      get: function (destino, clave) {
        if (clave === "canvas") return { width: 480, height: 312 };
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
    alCambiar: function () {},
    almacenamiento: {
      setItem: function () {}, getItem: function () { return null; },
      removeItem: function () {}
    }
  });
}

var pruebas = [];
function prueba(nombre, fn) { pruebas.push([nombre, fn]); }

prueba("el juego de prueba trae generadores", function () {
  assert.ok(DATA.generators && DATA.generators.length,
            "estos datos no traen generadores: no se comprueba nada");
  assert.ok(DATA.nombres.generadores.length === DATA.generators.length,
            "los nombres de los generadores no llegan al editor");
});

prueba("los nidos salen en la paleta con su nombre y su dibujo", function () {
  var e = nuevoEditor();
  var paleta = e.paleta();
  DATA.nombres.generadores.forEach(function (nombre, i) {
    var entradas = paleta.filter(function (p) { return p.etiqueta === nombre; });
    assert.strictEqual(entradas.length, 1, "el nido '" + nombre + "' no sale");
    assert.strictEqual(entradas[0].tipo, "generador",
                       "sale como '" + entradas[0].tipo + "'");
    assert.strictEqual(entradas[0].hoja, DATA.generators[i].actor.sheet,
                       "sale con el dibujo de otro");
  });
});

prueba("y no se cuelan en la lista de objetos", function () {
  var e = nuevoEditor();
  var objetos = e.paleta().filter(function (p) { return p.tipo === "objeto"; });
  assert.strictEqual(objetos.length, DATA.nombres.objetos.length,
                     "hay " + objetos.length + " objetos en la paleta y el "
                     + "juego tiene " + DATA.nombres.objetos.length);
});

prueba("un nido pintado llega al motor como kind 9", function () {
  var e = nuevoEditor();
  var nido = e.paleta().filter(function (p) { return p.tipo === "generador"; })[0];
  e.simbolo = nido.char;
  e.empezarCambio();
  e.pintar(9, 10, false);
  e.terminarCambio();
  e.aplicarAlMotor();
  /* los spawns van en pixeles, no en casillas */
  var puestos = e.data.levels[e.nivel].spawns.filter(function (s) {
    return (s[0] >> 4) === 9 && (s[1] >> 4) === 10;
  });
  assert.strictEqual(puestos.length, 1, "el nido no ha llegado al motor");
  assert.strictEqual(puestos[0][2], 9,
                     "ha llegado como kind " + puestos[0][2] + " y no como 9");
});

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
console.log("\n" + (pruebas.length - fallos) + "/" + pruebas.length
            + " pruebas del editor con generadores");
process.exit(fallos ? 1 : 0);
