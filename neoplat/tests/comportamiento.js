/* comportamiento.js - pruebas de jugabilidad del motor.
 *
 * Usan el motor en JavaScript (preview/np_core.js), que test_paridad.py
 * verifica que se comporta exactamente igual que el motor en C. Los escenarios
 * se construyen a mano para poder probar cada mecanica por separado.
 *
 *   node tests/comportamiento.js
 */
"use strict";

var assert = require("assert");
var path = require("path");
var NP = require(path.join(__dirname, "..", "preview", "np_core.js"));

var F = NP.FIX_ONE;
function fx(v) { return Math.round(v * F); }

/* tipos de tile: 0 vacio, 1 solido, 2 plataforma, 3 peligro, 4 meta */
var LEYENDA = { ".": 0, "#": 1, "=": 2, "^": 3, "G": 4 };

function anim(frames, speed) {
  return { frames: frames, count: frames.length, speed: speed || 8, loop: 1 };
}

function actor(boxW, boxH) {
  return {
    first_tile: 0, palette: 0, cols: 1, rows: 1,
    box_x: 0, box_y: 0, box_w: boxW, box_h: boxH,
    frames: 1, frame_w: 16, frame_h: 16, sheet: "x",
    anims: [anim([0]), anim([0]), anim([0]), anim([0]), anim([0])]
  };
}

function datos(filas, opciones) {
  opciones = opciones || {};
  var alto = filas.length, ancho = filas[0].length;
  var celdas = [], spawns = [], start = [16, 16];
  var jugador = actor(opciones.boxW || 12, opciones.boxH || 14);
  var enemigo = actor(12, 12), objeto = actor(10, 10);
  for (var y = 0; y < alto; y++) {
    for (var x = 0; x < ancho; x++) {
      var ch = filas[y][x];
      if (ch === "P") { start = [x * 16 + 2, y * 16 + 16 - jugador.box_h]; ch = "."; }
      else if (ch === "e") { spawns.push([x * 16 + 2, y * 16 + 16 - enemigo.box_h, 0, 0]); ch = "."; }
      else if (ch === "v") { spawns.push([x * 16 + 2, y * 16 + 16 - enemigo.box_h, 0, 1]); ch = "."; }
      else if (ch === "o") { spawns.push([x * 16 + 3, y * 16 + 16 - objeto.box_h, 1, 0]); ch = "."; }
      assert.ok(ch in LEYENDA, "simbolo desconocido: " + ch);
      celdas.push(".#=^G".indexOf(ch));
    }
  }
  var sin = [];
  for (var i = 0; i < 64; i++) sin.push(Math.round(Math.sin(2 * Math.PI * i / 64) * F));
  return {
    title: "TEST", author: "", lives: opciones.lives || 3, time_limit: opciones.time || 0,
    hud: true,
    player: {
      actor: jugador,
      speed: fx(opciones.speed || 1.6), accel: fx(0.3), friction: fx(0.35),
      air_accel: fx(0.16), jump: fx(opciones.jump || 4.3), jump_cut: fx(1.6),
      gravity: fx(0.28), max_fall: fx(6), bounce: fx(3.6), invuln: 90,
      coyote: opciones.coyote === undefined ? 6 : opciones.coyote,
      jump_buffer: opciones.buffer === undefined ? 6 : opciones.buffer,
      double_jump: opciones.doubleJump ? 1 : 0,
      stomp: opciones.stomp === false ? 0 : 1,
      health: opciones.health || 1
    },
    enemies: [
      { actor: enemigo, speed: fx(0.5), gravity: fx(0.28), jump: fx(3.5), range: fx(96),
        amplitude: fx(24), period: 120, interval: 90, score: 100, behavior: 0,
        health: 1, damage: 1, stompable: 1, edge_turn: 1, name: "patrulla" },
      { actor: enemigo, speed: fx(0.5), gravity: 0, jump: 0, range: fx(96),
        amplitude: fx(24), period: 64, interval: 90, score: 200, behavior: 1,
        health: 1, damage: 1, stompable: 1, edge_turn: 0, name: "volador" }
    ],
    items: [{ actor: objeto, score: 10, effect: 0, amount: 1, name: "moneda" }],
    tiles: { kind: [0, 1, 2, 3, 4], gfx: [0, 1, 2, 3, 4] },
    levels: [{
      name: "TEST", width: ancho, height: alto, cells: celdas,
      spawns: spawns, start: start, background: "#000000"
    }],
    sin: sin, sheets: { x: { url: "", frame_w: 16, frame_h: 16, per_row: 1 } },
    font: {}
  };
}

function suelo(extra) {
  var filas = [];
  for (var y = 0; y < 14; y++) filas.push(".".repeat(24));
  filas.push("#".repeat(24));
  (extra || []).forEach(function (par) { // [fila, columna, simbolo]
    var f = filas[par[0]].split("");
    f[par[1]] = par[2];
    filas[par[0]] = f.join("");
  });
  return filas;
}

function mundo(filas, opciones) {
  var w = NP.create(datos(filas, opciones));
  w.step(NP.IN.START);          // salir del titulo
  return w;
}

function correr(w, frames, input) {
  for (var i = 0; i < frames; i++) w.step(input || 0);
  return w;
}

var pruebas = [];
function prueba(nombre, fn) { pruebas.push([nombre, fn]); }

/* ------------------------------------------------------------ movimiento */

prueba("el jugador cae y aterriza en el suelo", function () {
  var w = mundo(suelo([[10, 3, "P"]]));
  correr(w, 60);
  assert.strictEqual(w.player.onGround, 1);
  assert.strictEqual(w.player.vy, 0);
  assert.strictEqual(NP.F2I(w.player.y) + w.data.player.actor.box_h, 14 * 16);
});

prueba("andar acelera hasta la velocidad maxima y no la pasa", function () {
  var w = mundo(suelo([[13, 2, "P"]]));
  correr(w, 120, NP.IN.RIGHT);
  assert.strictEqual(w.player.vx, w.data.player.speed);
  assert.strictEqual(w.player.facing, 1);
});

prueba("soltar el mando frena al jugador", function () {
  var w = mundo(suelo([[13, 2, "P"]]));
  correr(w, 60, NP.IN.RIGHT);
  correr(w, 30);
  assert.strictEqual(w.player.vx, 0);
});

prueba("el salto mantenido llega mas alto que el toque corto", function () {
  function altura(mantener) {
    var w = mundo(suelo([[13, 2, "P"]]));
    correr(w, 30);
    var y0 = NP.F2I(w.player.y), min = y0;
    for (var i = 0; i < 90; i++) {
      w.step(mantener || i < 2 ? NP.IN.JUMP : 0);
      min = Math.min(min, NP.F2I(w.player.y));
    }
    return y0 - min;
  }
  var largo = altura(true), corto = altura(false);
  assert.ok(largo > corto + 8, "salto largo " + largo + " vs corto " + corto);
  assert.ok(largo >= 24 && largo <= 40, "altura de salto rara: " + largo);
});

prueba("no atraviesa paredes ni a la maxima velocidad", function () {
  var filas = suelo([[13, 2, "P"]]);
  filas[13] = filas[13].substring(0, 10) + "#" + filas[13].substring(11);
  var w = mundo(filas, { speed: 7.9 });
  correr(w, 200, NP.IN.RIGHT);
  assert.ok(NP.F2I(w.player.x) + w.data.player.actor.box_w <= 10 * 16,
    "se ha colado en la pared: x=" + NP.F2I(w.player.x));
});

prueba("el techo corta el salto", function () {
  var filas = suelo([[13, 2, "P"]]);
  filas[11] = "#".repeat(24);
  var w = mundo(filas);
  correr(w, 30);
  correr(w, 20, NP.IN.JUMP);
  assert.ok(w.player.vy >= 0, "deberia estar cayendo tras chocar con el techo");
});

/* -------------------------------------------------------- ayudas de salto */

prueba("coyote time: se puede saltar justo despues del borde", function () {
  var filas = suelo([[13, 2, "P"]]);
  filas[14] = "###" + ".".repeat(21);          // el suelo se acaba en x=3
  var w = mundo(filas);
  correr(w, 20);
  correr(w, 30, NP.IN.RIGHT);                  // se cae por el borde
  assert.strictEqual(w.player.onGround, 0);
  var yAntes = NP.F2I(w.player.y);
  w.player.coyote = 3;                         // dentro del margen
  w.step(NP.IN.RIGHT | NP.IN.JUMP);
  assert.ok(w.player.vy < 0, "no ha saltado en el margen de coyote");
  assert.ok(NP.F2I(w.player.y) <= yAntes);
});

prueba("buffer de salto: pulsar antes de aterrizar cuenta", function () {
  var w = mundo(suelo([[8, 3, "P"]]));
  while (!w.player.onGround) w.step(0);
  var w2 = mundo(suelo([[8, 3, "P"]]));
  var saltoRegistrado = false;
  for (var i = 0; i < 200 && !saltoRegistrado; i++) {
    var cerca = !w2.player.onGround && w2.player.vy > 0 &&
      (13 * 16 - (NP.F2I(w2.player.y) + w2.data.player.actor.box_h)) < 8;
    w2.step(cerca ? NP.IN.JUMP : 0);           // se pulsa en el aire, antes de tocar
    if (w2.player.vy < 0) saltoRegistrado = true;
  }
  assert.ok(saltoRegistrado, "el buffer de salto no ha funcionado");
});

prueba("doble salto solo cuando esta activado", function () {
  function alturaDoble(activado) {
    var w = mundo(suelo([[13, 2, "P"]]), { doubleJump: activado });
    correr(w, 20);
    var y0 = NP.F2I(w.player.y), min = y0;
    w.step(NP.IN.JUMP);
    correr(w, 12, NP.IN.JUMP);
    w.step(0);
    w.step(NP.IN.JUMP);                        // segundo salto
    for (var i = 0; i < 60; i++) { w.step(NP.IN.JUMP); min = Math.min(min, NP.F2I(w.player.y)); }
    return y0 - min;
  }
  assert.ok(alturaDoble(true) > alturaDoble(false) + 10, "el doble salto no sube mas");
});

/* ------------------------------------------------------------ plataformas */

prueba("las plataformas frenan desde arriba", function () {
  var filas = suelo([[6, 3, "P"]]);
  filas[9] = "..====" + ".".repeat(18);
  var w = mundo(filas);
  correr(w, 60);
  assert.strictEqual(w.player.onGround, 1);
  assert.strictEqual(NP.F2I(w.player.y) + w.data.player.actor.box_h, 9 * 16);
});

prueba("las plataformas se atraviesan desde abajo", function () {
  var filas = suelo([[13, 3, "P"]]);
  filas[11] = "..====" + ".".repeat(18);
  var w = mundo(filas, { jump: 5.5 });
  correr(w, 20);
  var subio = false;
  for (var i = 0; i < 60; i++) {
    w.step(NP.IN.JUMP);
    if (NP.F2I(w.player.y) + w.data.player.actor.box_h < 11 * 16) subio = true;
  }
  assert.ok(subio, "no ha podido atravesar la plataforma saltando");
});

prueba("pulsar abajo deja caer desde la plataforma", function () {
  var filas = suelo([[6, 3, "P"]]);
  filas[9] = "..====" + ".".repeat(18);
  var w = mundo(filas);
  correr(w, 60);
  assert.strictEqual(w.player.onGround, 1);
  correr(w, 20, NP.IN.DOWN);
  assert.ok(NP.F2I(w.player.y) + w.data.player.actor.box_h > 9 * 16,
    "sigue encima de la plataforma");
});

/* --------------------------------------------------------------- enemigos */

prueba("pisar a un enemigo lo elimina, da puntos y rebota", function () {
  var w = mundo(suelo([[13, 5, "e"], [8, 5, "P"]]));
  var enemigo = w.entities[0];
  var puntos = w.score;
  var reboto = false;
  for (var i = 0; i < 120 && enemigo.active; i++) w.step(0);
  for (var j = 0; j < 5; j++) { if (w.player.vy < 0) reboto = true; w.step(0); }
  assert.strictEqual(enemigo.active, 0, "el enemigo sigue vivo");
  assert.strictEqual(w.score, puntos + 100);
  assert.ok(reboto, "el jugador no ha rebotado");
});

prueba("chocar de lado con un enemigo hace dano", function () {
  var w = mundo(suelo([[13, 8, "e"], [13, 2, "P"]]));
  var golpeado = false;
  for (var i = 0; i < 200 && !golpeado; i++) {
    w.step(NP.IN.RIGHT);
    if (w.state === NP.STATE.DYING) golpeado = true;
  }
  assert.ok(golpeado, "el enemigo no ha hecho dano");
});

prueba("con varias vidas de salud solo se pierde una por golpe", function () {
  var w = mundo(suelo([[13, 8, "e"], [13, 2, "P"]]), { health: 3, stomp: false });
  for (var i = 0; i < 200 && w.player.health === 3; i++) w.step(NP.IN.RIGHT);
  assert.strictEqual(w.player.health, 2, "un solo golpe deberia quitar una vida");
  assert.ok(w.player.invuln > 0, "no hay invulnerabilidad tras el golpe");
});

prueba("el enemigo que patrulla gira en el borde", function () {
  var filas = suelo([[13, 5, "e"]]);
  filas[14] = "#".repeat(8) + ".".repeat(16);   // el suelo se acaba en x=8
  var w = mundo(filas);
  var enemigo = w.entities[0];
  var giro = false;
  for (var i = 0; i < 600; i++) {
    w.step(0);
    if (enemigo.facing === 0) giro = true;
    assert.ok(enemigo.active, "el enemigo se ha caido del mapa");
  }
  assert.ok(giro, "el enemigo no ha girado en el borde");
});

prueba("el enemigo volador oscila alrededor de su altura", function () {
  var w = mundo(suelo([[6, 5, "v"]]));
  var enemigo = w.entities[0];
  var min = enemigo.y, max = enemigo.y;
  for (var i = 0; i < 200; i++) {
    w.step(0);
    min = Math.min(min, enemigo.y);
    max = Math.max(max, enemigo.y);
  }
  var amplitud = NP.F2I(max - min);
  assert.ok(amplitud >= 40 && amplitud <= 60, "amplitud inesperada: " + amplitud);
});

/* ------------------------------------------------------ objetos y niveles */

prueba("recoger un objeto suma puntos y lo quita del nivel", function () {
  var w = mundo(suelo([[13, 4, "o"], [13, 2, "P"]]));
  var objeto = w.entities[0];
  correr(w, 120, NP.IN.RIGHT);
  assert.strictEqual(objeto.active, 0);
  assert.strictEqual(w.score, 10);
});

prueba("los pinchos matan", function () {
  var w = mundo(suelo([[13, 4, "^"], [13, 2, "P"]]));
  correr(w, 120, NP.IN.RIGHT);
  assert.ok(w.state === NP.STATE.DYING || w.state === NP.STATE.GAME_OVER,
    "los pinchos no han matado");
});

prueba("caerse del mapa mata", function () {
  var filas = suelo([[13, 2, "P"]]);
  filas[14] = "##" + ".".repeat(22);
  var w = mundo(filas);
  correr(w, 300, NP.IN.RIGHT);
  assert.ok(w.state !== NP.STATE.PLAY, "caerse al vacio no ha matado");
});

prueba("la meta termina el nivel", function () {
  var w = mundo(suelo([[13, 6, "G"], [13, 2, "P"]]));
  correr(w, 200, NP.IN.RIGHT);
  assert.ok(w.state === NP.STATE.LEVEL_END || w.state === NP.STATE.FINISHED,
    "no se ha completado el nivel");
  assert.ok(w.score >= 100, "no se han sumado los puntos del nivel");
});

prueba("perder todas las vidas lleva a game over y luego al titulo", function () {
  var w = mundo(suelo([[13, 4, "^"], [13, 2, "P"]]), { lives: 1 });
  for (var i = 0; i < 400 && w.state !== NP.STATE.GAME_OVER; i++) w.step(NP.IN.RIGHT);
  assert.strictEqual(w.state, NP.STATE.GAME_OVER);
  correr(w, 300);
  assert.strictEqual(w.state, NP.STATE.TITLE);
  assert.strictEqual(w.lives, 0);
});

prueba("morir con vidas de sobra reinicia el nivel", function () {
  var w = mundo(suelo([[13, 4, "^"], [13, 2, "P"]]), { lives: 3 });
  var inicio = w.level.start[0];
  for (var i = 0; i < 400 && w.lives === 3; i++) w.step(NP.IN.RIGHT);
  assert.strictEqual(w.lives, 2);
  assert.strictEqual(NP.F2I(w.player.x), inicio);
  assert.strictEqual(w.state, NP.STATE.PLAY);
});

/* ----------------------------------------------------------------- camara */

prueba("la camara sigue al jugador sin salirse del nivel", function () {
  var w = mundo(suelo([[13, 2, "P"]]));
  assert.strictEqual(w.camX, 0);
  correr(w, 400, NP.IN.RIGHT);
  var maxX = w.level.width * 16 - NP.SCREEN_W;
  var maxY = w.level.height * 16 - NP.SCREEN_H;
  assert.ok(w.camX >= 0 && w.camX <= Math.max(0, maxX), "camara fuera del nivel: " + w.camX);
  assert.ok(w.camY >= 0 && w.camY <= Math.max(0, maxY), "camara fuera del nivel: " + w.camY);
  assert.ok(w.camX > 0, "la camara no ha seguido al jugador");
});

/* ------------------------------------------------------------ ejecucion */

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
console.log("\n" + (pruebas.length - fallos) + "/" + pruebas.length + " pruebas de jugabilidad");
process.exit(fallos ? 1 : 0);
