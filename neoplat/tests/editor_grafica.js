/* editor_grafica.js - el editor con una aventura grafica.
 *
 * Lo que este genero trae y ningun otro tenia: casillas que **contestan**. Ahi
 * todas son 'vacio' -un cursor no choca con nada- asi que puestas en la paleta
 * por su tipo saldrian las veinte iguales y no habria forma de distinguir el
 * cuadro de la pared de al lado. Lo que las separa es a que verbo contestan, y
 * eso es lo que se comprueba aqui.
 *
 *   node tests/editor_grafica.js datos.json
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

/* Las casillas que contestan a algun verbo, con la lista de verbos de cada
   una. Es la misma cuenta que hace la paleta. */
function contestonas() {
  var fuera = [];
  DATA.tiles.chars.forEach(function (ch, i) {
    var dice = [];
    (DATA.verbos || []).forEach(function (nombre, v) {
      if (((DATA.tiles.verbo || [])[v] || [])[i]) dice.push(nombre.toLowerCase());
    });
    if (dice.length) fuera.push([ch, i, dice]);
  });
  return fuera;
}

prueba("el juego de prueba es de puntero y sus casillas contestan", function () {
  assert.strictEqual(DATA.view, "puntero", "estos datos no son de puntero");
  assert.ok(DATA.tiles.verbo, "los datos no traen los guiones por verbo");
  assert.ok(contestonas().length >= 5,
            "solo " + contestonas().length + " casillas contestan a algo: no "
            + "se comprueba nada");
});

prueba("cada casilla sale en la paleta por los verbos que contesta", function () {
  var e = nuevoEditor();
  var paleta = e.paleta();
  contestonas().forEach(function (fila) {
    var ch = fila[0], dice = fila[2];
    var entrada = paleta.filter(function (p) { return p.char === ch; })[0];
    assert.ok(entrada, "la casilla '" + ch + "' no sale en la paleta");
    assert.strictEqual(entrada.etiqueta, dice.join(", "),
                       "'" + ch + "' sale como '" + entrada.etiqueta + "'");
  });
});

prueba("lo que no contesta a nada sale como decorado", function () {
  var e = nuevoEditor();
  var mudas = e.paleta().filter(function (p) {
    return p.tipo === "tile" && p.etiqueta === "decorado";
  });
  assert.ok(mudas.length >= 2,
            "no hay casillas de decorado en la paleta: " + mudas.length);
  /* y ninguna se queda con el nombre del tipo, que aqui es 'vacio' para todas
     y no distinguiria una pared de un cuadro */
  var vacias = e.paleta().filter(function (p) {
    return p.tipo === "tile" && p.etiqueta === "vacio";
  });
  assert.strictEqual(vacias.length, 0,
                     "hay " + vacias.length + " casillas puestas como 'vacio': "
                     + "en esta vista lo son todas y no dice nada");
});

prueba("una casilla que contesta se pinta y llega al motor", function () {
  var e = nuevoEditor();
  var ch = contestonas()[0][0];
  e.simbolo = ch;
  e.empezarCambio();
  e.pintar(3, 4, false);
  e.terminarCambio();
  e.aplicarAlMotor();
  var nivel = e.data.levels[e.nivel];
  assert.strictEqual(nivel.rows[4][3], ch,
                     "en el mapa ha quedado '" + nivel.rows[4][3] + "'");
  assert.strictEqual(nivel.cells[4 * nivel.width + 3], e.data.tiles.index[ch],
                     "la casilla no ha llegado al motor");
});

prueba("guardar el yaml no se lleva por delante los verbos", function () {
  /* El editor no reescribe el archivo: lo retoca linea a linea. Aqui se
     comprueba en lo que mas duele -una aventura grafica vive en esas lineas-:
     despues de pintar y guardar, la leyenda tiene que seguir diciendo a que
     contesta cada casilla. */
  var e = nuevoEditor();
  e.simbolo = contestonas()[0][0];
  e.empezarCambio();
  e.pintar(5, 4, false);
  e.terminarCambio();
  var texto = e.exportarYaml();
  contestonas().forEach(function (fila) {
    var linea = texto.split("\n").filter(function (l) {
      return l.indexOf("'" + fila[0] + "':") >= 0;
    })[0];
    assert.ok(linea, "la leyenda ya no trae '" + fila[0] + "'");
    fila[2].forEach(function (verbo) {
      assert.ok(linea.indexOf(verbo + ":") >= 0,
                "'" + fila[0] + "' ha perdido el verbo '" + verbo + "': " + linea);
    });
  });
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
            + " pruebas del editor con verbos");
process.exit(fallos ? 1 : 0);
