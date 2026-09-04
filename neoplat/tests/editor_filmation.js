/* editor_filmation.js - el editor con un juego isometrico.
 *
 * Lo que este genero trae y ningun otro tenia: el mapa **no es lo que se ve**.
 * Cada casilla lleva una altura, el escenario se dibuja con cubos y las salas
 * se pintan en isometrica, asi que el editor tiene que hacer dos cosas que en
 * los demas generos no hacen falta:
 *
 *   1. traducir el raton al reves -de donde pinchas a que casilla de la planta
 *      es-, que es lo unico que separa un editor de salas de un editor de
 *      cuadriculas;
 *   2. ensenar en la paleta el **cubo** de cada tile y su altura, porque
 *      puestos por su `tile:` -que en esta vista es siempre el vacio- saldrian
 *      todos en blanco y no habria manera de saber cual es la pared y cual el
 *      escalon.
 *
 *   node tests/editor_filmation.js datos.json
 */
"use strict";

var assert = require("assert");
var fs = require("fs");
var path = require("path");
var NPEditor = require(path.join(__dirname, "..", "preview", "np_editor.js"));

var DATA = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));

/* Los mismos numeros que np_types.h y que el propio editor. */
var SALA = 8, ISO_OX = 160, ISO_OY = 80, SALA_W = 320, SALA_H = 224, TILE = 16;

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

/* Donde cae en la pantalla el centro del rombo de una casilla. Es la cuenta
   del motor (np_pantalla), escrita aqui aparte a proposito: si la prueba usara
   la del editor, comprobaria que el editor es igual a si mismo. */
function puntoDe(cx, cy) {
  var rx = Math.floor(cx / SALA), ry = Math.floor(cy / SALA);
  var lx = (cx - rx * SALA) * TILE + 8, ly = (cy - ry * SALA) * TILE + 8;
  return { x: rx * SALA_W + ISO_OX + (lx - ly),
           y: ry * SALA_H + ISO_OY + ((lx + ly) >> 1) };
}

function tilesConCubo() {
  var fuera = [];
  DATA.tiles.chars.forEach(function (ch, i) {
    if (DATA.tiles.bloque && DATA.tiles.bloque[i]) fuera.push([ch, i]);
  });
  return fuera;
}

prueba("el juego de prueba es isometrico y trae relieve", function () {
  assert.strictEqual(DATA.view, "iso", "estos datos no son de un juego isometrico");
  assert.ok(DATA.tiles.alto, "los datos no dicen lo que levanta cada casilla");
  assert.ok(DATA.bloques && DATA.bloques.length >= 3,
            "estos datos traen " + ((DATA.bloques || []).length) + " cubos: no "
            + "se comprueba nada");
  assert.ok(tilesConCubo().length >= 3,
            "no hay tiles con cubo: no se comprueba nada");
  assert.ok(DATA.tiles.sala && DATA.tiles.sala.tile >= 0,
            "los datos no dicen donde esta el dibujo del suelo de la sala");
});

prueba("cada tile con relieve sale en la paleta con su cubo y su altura",
       function () {
  var e = nuevoEditor();
  var paleta = e.paleta();
  tilesConCubo().forEach(function (par) {
    var ch = par[0], i = par[1];
    var entrada = paleta.filter(function (p) { return p.char === ch; })[0];
    assert.ok(entrada, "el tile '" + ch + "' no sale en la paleta");
    var cubo = DATA.bloques[DATA.tiles.bloque[i] - 1];
    assert.strictEqual(entrada.hoja, cubo.actor.sheet,
                       "el tile '" + ch + "' sale con la hoja '" + entrada.hoja
                       + "' y su cubo es '" + cubo.name + "'");
    if (DATA.tiles.alto[i])
      assert.ok(entrada.etiqueta.indexOf("alto " + DATA.tiles.alto[i]) >= 0,
                "el tile '" + ch + "' levanta " + DATA.tiles.alto[i]
                + " y en la paleta pone '" + entrada.etiqueta + "'");
  });
});

prueba("dos tiles de distinta altura no se ven iguales en la paleta",
       function () {
  var e = nuevoEditor();
  var etiquetas = {};
  e.paleta().forEach(function (p) {
    if (p.tipo !== "tile") return;
    assert.ok(!etiquetas[p.etiqueta],
              "dos tiles con la misma etiqueta: '" + p.etiqueta + "'");
    etiquetas[p.etiqueta] = 1;
  });
});

prueba("pinchar en un rombo da su casilla", function () {
  var e = nuevoEditor();
  e.zoom = 1;
  e.camX = 0;
  e.camY = 0;
  e.herramienta = "mano";           // que pinchar no pinte nada
  /* Se prueban las cuatro esquinas de la primera sala y el centro: son los
     sitios donde una proyeccion mal despejada se nota mas. */
  [[0, 0], [7, 0], [0, 7], [7, 7], [3, 4]].forEach(function (celda) {
    var p = puntoDe(celda[0], celda[1]);
    e.mover_raton(p.x, p.y);
    assert.strictEqual(e.raton.x + "," + e.raton.y, celda[0] + "," + celda[1],
                       "pinchando en el rombo de " + celda + " sale la casilla "
                       + e.raton.x + "," + e.raton.y);
  });
});

prueba("pinchar en la sala de al lado da la casilla de la sala de al lado",
       function () {
  var e = nuevoEditor();
  e.zoom = 1;
  e.camX = 0;
  e.camY = 0;
  e.herramienta = "mano";
  var celda = [SALA + 3, SALA + 4];      // sala 1,1, casilla 3,4
  var p = puntoDe(celda[0], celda[1]);
  e.mover_raton(p.x - e.camX, p.y - e.camY);
  assert.strictEqual(e.raton.x + "," + e.raton.y, celda[0] + "," + celda[1],
                     "sale la casilla " + e.raton.x + "," + e.raton.y);
});

prueba("lo que se pinta llega al mapa y al motor", function () {
  var e = nuevoEditor();
  var ch = tilesConCubo()[0][0];
  e.simbolo = ch;
  e.empezarCambio();
  e.pintar(3, 5, false);
  e.terminarCambio();
  e.aplicarAlMotor();
  var nivel = e.data.levels[e.nivel];
  assert.strictEqual(nivel.rows[5][3], ch,
                     "en el mapa ha quedado '" + nivel.rows[5][3] + "'");
  assert.strictEqual(nivel.cells[5 * nivel.cells_w + 3], e.data.tiles.index[ch],
                     "la casilla no ha llegado al motor");
});

prueba("el mapa que se pisa y el que se dibuja son cosas distintas",
       function () {
  var e = nuevoEditor();
  var nivel = e.data.levels[e.nivel];
  assert.strictEqual(nivel.cells_w, nivel.rows[0].length,
                     "la planta no mide lo que el mapa de texto");
  assert.strictEqual(nivel.width, 20,
                     "lo que se dibuja mide " + nivel.width + " tiles de ancho "
                     + "y una sala es una pantalla de 20");
  assert.strictEqual(nivel.height, 14,
                     "lo que se dibuja mide " + nivel.height + " tiles de alto "
                     + "y una sala es una pantalla de 14");
  assert.ok(nivel.cells_w % SALA === 0 && nivel.cells_h % SALA === 0,
            "la planta no se reparte en salas enteras");
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
process.exit(fallos ? 1 : 0);
