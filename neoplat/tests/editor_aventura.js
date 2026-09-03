/* editor_aventura.js - el editor con un juego de aventura.
 *
 * Lo que este genero trae y ningun otro tenia: **cerrojos**, que son tiles con
 * un tipo nuevo (9) y con un objeto asociado. En la paleta salian como "tile" a
 * secas -el nombre del tipo se paraba en el punto de control- y las tres
 * puertas del juego se veian iguales, que en una aventura es justo lo que no
 * puede pasar: la gracia esta en saber cual pide que.
 *
 *   node tests/editor_aventura.js datos.json
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

function cerrojos() {
  var fuera = [];
  DATA.tiles.chars.forEach(function (ch, i) {
    if (DATA.tiles.kind[i] === 9) fuera.push([ch, i]);
  });
  return fuera;
}

prueba("el juego de prueba trae cerrojos", function () {
  assert.ok(cerrojos().length >= 2,
            "estos datos traen " + cerrojos().length + " cerrojos: no se "
            + "comprueba nada");
  assert.ok(DATA.tiles.need, "los datos no dicen que pide cada tile");
});

prueba("cada cerrojo sale en la paleta por lo que pide", function () {
  var e = nuevoEditor();
  var paleta = e.paleta();
  var vistos = {};
  cerrojos().forEach(function (par) {
    var ch = par[0], i = par[1];
    var pide = DATA.tiles.need[i];
    assert.ok(pide, "el cerrojo '" + ch + "' no pide nada");
    var objeto = DATA.nombres.objetos[pide - 1];
    var entrada = paleta.filter(function (p) { return p.char === ch; })[0];
    assert.ok(entrada, "el cerrojo '" + ch + "' no sale en la paleta");
    assert.strictEqual(entrada.etiqueta, "cerrojo: " + objeto,
                       "sale como '" + entrada.etiqueta + "'");
    assert.ok(!vistos[entrada.etiqueta],
              "dos cerrojos con la misma etiqueta: " + entrada.etiqueta);
    vistos[entrada.etiqueta] = 1;
  });
});

prueba("los cerrojos no se cuelan como tiles sin nombre", function () {
  var e = nuevoEditor();
  var sinNombre = e.paleta().filter(function (p) {
    return p.tipo === "tile" && p.etiqueta === "tile";
  });
  assert.strictEqual(sinNombre.length, 0,
                     "hay " + sinNombre.length + " tiles sin nombre en la paleta");
});

prueba("un cerrojo pintado llega al mapa", function () {
  var e = nuevoEditor();
  var ch = cerrojos()[0][0];
  e.simbolo = ch;
  e.empezarCambio();
  e.pintar(3, 5, false);
  e.terminarCambio();
  e.aplicarAlMotor();
  var fila = e.data.levels[e.nivel].rows[5];
  assert.strictEqual(fila[3], ch,
                     "en el mapa ha quedado '" + fila[3] + "' y no '" + ch + "'");
  var i = e.data.tiles.index[ch];
  assert.strictEqual(e.data.levels[e.nivel].cells[5 * e.data.levels[e.nivel].width + 3],
                     i, "la casilla no ha llegado al motor");
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
            + " pruebas del editor con cerrojos");
process.exit(fallos ? 1 : 0);
