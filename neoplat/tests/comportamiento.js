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

/* El simbolo del mapa -> su hueco en la leyenda; y la leyenda -> el tipo de
   tile que entiende el motor (0 vacio, 1 solido, 2 plataforma, 3 peligro,
   4 meta, 6 escalera que sube a la derecha, 7 la que sube a la izquierda). */
var LEYENDA = { ".": 0, "#": 1, "=": 2, "^": 3, "G": 4, "/": 5, "\\": 6 };
var TIPOS = [0, 1, 2, 3, 4, 6, 7];

function anim(frames, speed) {
  return { frames: frames, count: frames.length, speed: speed || 8, loop: 1 };
}

function actor(boxW, boxH) {
  return {
    first_tile: 0, palette: 0, cols: 1, rows: 1,
    box_x: 0, box_y: 0, box_w: boxW, box_h: boxH,
    frames: 1, frame_w: 16, frame_h: 16, sheet: "x",
    anims: [anim([0]), anim([0]), anim([0]), anim([0]), anim([0]), anim([0]),
            anim([0])]
  };
}

function datos(filas, opciones) {
  opciones = opciones || {};
  var alto = filas.length, ancho = filas[0].length;
  var celdas = [], spawns = [], start = [16, 16];
  var jugador = actor(opciones.boxW || 12, opciones.boxH || 14);
  var enemigo = actor(12, 12), objeto = actor(10, 10);
  var tablon = actor(opciones.tablonAncho || 32, 6);
  var candelabro = actor(12, 14);
  for (var y = 0; y < alto; y++) {
    for (var x = 0; x < ancho; x++) {
      var ch = filas[y][x];
      if (ch === "P") { start = [x * 16 + 2, y * 16 + 16 - jugador.box_h]; ch = "."; }
      else if (ch === "e") { spawns.push([x * 16 + 2, y * 16 + 16 - enemigo.box_h, 0, 0]); ch = "."; }
      else if (ch === "v") { spawns.push([x * 16 + 2, y * 16 + 16 - enemigo.box_h, 0, 1]); ch = "."; }
      else if (ch === "o") { spawns.push([x * 16 + 3, y * 16 + 16 - objeto.box_h, 1, 0]); ch = "."; }
      else if (ch === "k") { spawns.push([x * 16 + 3, y * 16 + 16 - objeto.box_h, 1, 1]); ch = "."; }
      else if (ch === "T") { spawns.push([x * 16, y * 16 + 16 - tablon.box_h, 3, 0]); ch = "."; }
      else if (ch === "C") { spawns.push([x * 16 + 2, y * 16 + 16 - candelabro.box_h, 4, 0]); ch = "."; }
      else if (ch === "V") { spawns.push([x * 16 + 2, y * 16 + 16 - candelabro.box_h, 4, 1]); ch = "."; }
      else if (ch === "J") { spawns.push([x * 16 + 2, y * 16 + 16 - enemigo.box_h, 0, 2]); ch = "."; }
      assert.ok(ch in LEYENDA, "simbolo desconocido: " + ch);
      celdas.push(LEYENDA[ch]);
    }
  }
  var sin = [];
  for (var i = 0; i < 64; i++) sin.push(Math.round(Math.sin(2 * Math.PI * i / 64) * F));
  return {
    title: "TEST", author: "", lives: opciones.lives || 3, time_limit: opciones.time || 0,
    players: opciones.jugadores || 1,
    hud: true, camara_pantallas: opciones.pantallas ? 1 : 0,
    player: {
      actor: jugador,
      speed: fx(opciones.speed || 1.6), accel: fx(0.3), friction: fx(0.35),
      air_accel: fx(0.16), jump: fx(opciones.jump || 4.3), jump_cut: fx(1.6),
      gravity: fx(0.28), max_fall: fx(6), bounce: fx(3.6), invuln: 90,
      /* el empujon al recibir un golpe y los frames sin control de despues */
      knockback: fx(opciones.retroceso === undefined ? (opciones.speed || 1.6)
                                                     : opciones.retroceso),
      stun: opciones.aturdido || 0,
      /* lo que se avanza por frame en una escalera; 0 = no se pueden subir */
      stair_speed: fx(opciones.escalera === undefined ? 0.8 : opciones.escalera),
      coyote: opciones.coyote === undefined ? 6 : opciones.coyote,
      jump_buffer: opciones.buffer === undefined ? 6 : opciones.buffer,
      double_jump: opciones.doubleJump ? 1 : 0,
      stomp: opciones.stomp === false ? 0 : 1,
      health: opciones.health || 1,
      /* el ataque: por defecto ninguno, como un proyecto sin `ataque:` */
      attack: {
        kind: opciones.ataque === "golpe" ? 2 : (opciones.ataque ? 1 : 0),
        speed: fx(opciones.balaVelocidad || 3),
        range: opciones.alcance || 64,
        cooldown: opciones.espera === undefined ? 10 : opciones.espera,
        duration: opciones.duracion || 6,
        windup: opciones.preparacion || 0,
        locks: opciones.clavado ? 1 : 0,
        damage: opciones.dano || 1,
        actor: actor(6, 6)
      },
      /* el arma secundaria: por defecto ninguna, como un juego sin
         `secundaria:` en el game.yaml */
      sub: {
        kind: opciones.secundaria === "arco" ? 2 : (opciones.secundaria ? 1 : 0),
        speed: fx(opciones.subVelocidad || 3),
        gravity: fx(opciones.subGravedad === undefined ? 0.25 : opciones.subGravedad),
        jump: fx(opciones.subSalto === undefined ? 3 : opciones.subSalto),
        range: opciones.subAlcance || 160,
        cooldown: opciones.subEspera === undefined ? 24 : opciones.subEspera,
        cost: opciones.subCoste === undefined ? 1 : opciones.subCoste,
        damage: opciones.subDano || 1,
        actor: actor(8, 8)
      }
    },
    enemies: [
      { actor: enemigo, speed: fx(0.5), gravity: fx(0.28), jump: fx(3.5), range: fx(96),
        amplitude: fx(24), period: 120, interval: 90, score: 100, behavior: 0,
        health: 1, damage: 1, stompable: 1, edge_turn: 1, name: "patrulla" },
      { actor: enemigo, speed: fx(0.5), gravity: 0, jump: 0, range: fx(96),
        amplitude: fx(24), period: 64, interval: 90, score: 200, behavior: 1,
        health: 1, damage: 1, stompable: 1, edge_turn: 0, name: "volador" },
      { actor: enemigo, speed: 0, gravity: fx(0.28), jump: 0, range: fx(96),
        amplitude: fx(24), period: 120, interval: 90, score: 1000, behavior: 4,
        health: opciones.bossHealth || 3, damage: 1, stompable: 1, edge_turn: 1,
        boss: 1, name: "jefe" }
    ],
    items: [
      { actor: objeto, score: 10, effect: 0, amount: 1, name: "moneda" },
      /* efecto 3 = llave: no da puntos de vida, suma al contador de la partida */
      { actor: objeto, score: 50, effect: 3, amount: opciones.valorLlave || 1,
        name: "llave" },
      /* efecto 4 = municion del arma secundaria */
      { actor: objeto, score: 0, effect: 4, amount: opciones.valorMunicion || 5,
        name: "corazon" }
    ],
    breakables: [
      /* "C": suelta la moneda; "V": no suelta nada */
      { actor: candelabro, score: 100, drop: opciones.suelta === undefined ? 1
                                             : opciones.suelta,
        health: opciones.candelabroVida || 1, name: "candelabro" },
      { actor: candelabro, score: 0, drop: 0, health: 1, name: "vacio" }
    ],
    platforms: [{
      actor: tablon,
      speed: fx(opciones.tablonVelocidad === undefined ? 0.5 : opciones.tablonVelocidad),
      distance: opciones.tablonDistancia === undefined ? 48 : opciones.tablonDistancia,
      axis: opciones.tablonEje === "vertical" ? 1 : 0,
      name: "tablon"
    }],
    tiles: { kind: TIPOS, gfx: [0, 1, 2, 3, 4, 5, 6] },
    levels: [{
      name: "TEST", width: ancho, height: alto, cells: celdas,
      spawns: spawns, start: start, background: "#000000",
      keys_needed: opciones.llaves || 0
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
  assert.strictEqual(w.players[0].onGround, 1);
  assert.strictEqual(w.players[0].vy, 0);
  assert.strictEqual(NP.F2I(w.players[0].y) + w.data.player.actor.box_h, 14 * 16);
});

prueba("andar acelera hasta la velocidad maxima y no la pasa", function () {
  var w = mundo(suelo([[13, 2, "P"]]));
  correr(w, 120, NP.IN.RIGHT);
  assert.strictEqual(w.players[0].vx, w.data.player.speed);
  assert.strictEqual(w.players[0].facing, 1);
});

prueba("soltar el mando frena al jugador", function () {
  var w = mundo(suelo([[13, 2, "P"]]));
  correr(w, 60, NP.IN.RIGHT);
  correr(w, 30);
  assert.strictEqual(w.players[0].vx, 0);
});

prueba("el salto mantenido llega mas alto que el toque corto", function () {
  function altura(mantener) {
    var w = mundo(suelo([[13, 2, "P"]]));
    correr(w, 30);
    var y0 = NP.F2I(w.players[0].y), min = y0;
    for (var i = 0; i < 90; i++) {
      w.step(mantener || i < 2 ? NP.IN.JUMP : 0);
      min = Math.min(min, NP.F2I(w.players[0].y));
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
  assert.ok(NP.F2I(w.players[0].x) + w.data.player.actor.box_w <= 10 * 16,
    "se ha colado en la pared: x=" + NP.F2I(w.players[0].x));
});

prueba("el techo corta el salto", function () {
  var filas = suelo([[13, 2, "P"]]);
  filas[11] = "#".repeat(24);
  var w = mundo(filas);
  correr(w, 30);
  correr(w, 20, NP.IN.JUMP);
  assert.ok(w.players[0].vy >= 0, "deberia estar cayendo tras chocar con el techo");
});

/* -------------------------------------------------------- ayudas de salto */

prueba("coyote time: se puede saltar justo despues del borde", function () {
  var filas = suelo([[13, 2, "P"]]);
  filas[14] = "###" + ".".repeat(21);          // el suelo se acaba en x=3
  var w = mundo(filas);
  correr(w, 20);
  correr(w, 30, NP.IN.RIGHT);                  // se cae por el borde
  assert.strictEqual(w.players[0].onGround, 0);
  var yAntes = NP.F2I(w.players[0].y);
  w.players[0].coyote = 3;                         // dentro del margen
  w.step(NP.IN.RIGHT | NP.IN.JUMP);
  assert.ok(w.players[0].vy < 0, "no ha saltado en el margen de coyote");
  assert.ok(NP.F2I(w.players[0].y) <= yAntes);
});

prueba("buffer de salto: pulsar antes de aterrizar cuenta", function () {
  var w = mundo(suelo([[8, 3, "P"]]));
  while (!w.players[0].onGround) w.step(0);
  var w2 = mundo(suelo([[8, 3, "P"]]));
  var saltoRegistrado = false;
  for (var i = 0; i < 200 && !saltoRegistrado; i++) {
    var cerca = !w2.players[0].onGround && w2.players[0].vy > 0 &&
      (13 * 16 - (NP.F2I(w2.players[0].y) + w2.data.player.actor.box_h)) < 8;
    w2.step(cerca ? NP.IN.JUMP : 0);           // se pulsa en el aire, antes de tocar
    if (w2.players[0].vy < 0) saltoRegistrado = true;
  }
  assert.ok(saltoRegistrado, "el buffer de salto no ha funcionado");
});

prueba("doble salto solo cuando esta activado", function () {
  function alturaDoble(activado) {
    var w = mundo(suelo([[13, 2, "P"]]), { doubleJump: activado });
    correr(w, 20);
    var y0 = NP.F2I(w.players[0].y), min = y0;
    w.step(NP.IN.JUMP);
    correr(w, 12, NP.IN.JUMP);
    w.step(0);
    w.step(NP.IN.JUMP);                        // segundo salto
    for (var i = 0; i < 60; i++) { w.step(NP.IN.JUMP); min = Math.min(min, NP.F2I(w.players[0].y)); }
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
  assert.strictEqual(w.players[0].onGround, 1);
  assert.strictEqual(NP.F2I(w.players[0].y) + w.data.player.actor.box_h, 9 * 16);
});

prueba("las plataformas se atraviesan desde abajo", function () {
  var filas = suelo([[13, 3, "P"]]);
  filas[11] = "..====" + ".".repeat(18);
  var w = mundo(filas, { jump: 5.5 });
  correr(w, 20);
  var subio = false;
  for (var i = 0; i < 60; i++) {
    w.step(NP.IN.JUMP);
    if (NP.F2I(w.players[0].y) + w.data.player.actor.box_h < 11 * 16) subio = true;
  }
  assert.ok(subio, "no ha podido atravesar la plataforma saltando");
});

prueba("pulsar abajo deja caer desde la plataforma", function () {
  var filas = suelo([[6, 3, "P"]]);
  filas[9] = "..====" + ".".repeat(18);
  var w = mundo(filas);
  correr(w, 60);
  assert.strictEqual(w.players[0].onGround, 1);
  correr(w, 20, NP.IN.DOWN);
  assert.ok(NP.F2I(w.players[0].y) + w.data.player.actor.box_h > 9 * 16,
    "sigue encima de la plataforma");
});

/* --------------------------------------------------------------- enemigos */

prueba("pisar a un enemigo lo elimina, da puntos y rebota", function () {
  var w = mundo(suelo([[13, 5, "e"], [8, 5, "P"]]));
  var enemigo = w.entities[0];
  var puntos = w.score;
  var reboto = false;
  for (var i = 0; i < 120 && enemigo.active; i++) w.step(0);
  for (var j = 0; j < 5; j++) { if (w.players[0].vy < 0) reboto = true; w.step(0); }
  assert.strictEqual(enemigo.active, 0, "el enemigo sigue vivo");
  assert.strictEqual(w.score, puntos + 100);
  assert.ok(reboto, "el jugador no ha rebotado");
});

prueba("al jefe hay que pisarlo varias veces y el marcador lo cuenta", function () {
  /* El jefe es un enemigo con 'jefe: si': aguanta varios pisotones y matarlo
     termina el nivel, como llegar a la meta. */
  /* el jugador aguanta varios golpes: al rebotar del pisoton cae al lado del
     jefe y se choca con el, que es justo lo que pasa en un juego */
  var w = mundo(suelo([[13, 5, "J"], [8, 5, "P"]]), { bossHealth: 3, health: 9 });
  var jefe = w.entities[0];
  var i;
  for (i = 0; i < 120 && w.bossHealth !== 3; i++) w.step(0);
  assert.strictEqual(w.bossHealth, 3, "el marcador no ve al jefe");
  assert.strictEqual(w.bossMax, 3);

  /* con el salto pulsado el jugador rebota sobre el y lo pisa una y otra vez */
  var golpes = 0;
  for (i = 0; i < 900 && jefe.active; i++) {
    var antes = jefe.health;
    w.step(NP.IN.JUMP);
    if (jefe.health < antes) golpes++;
  }
  assert.strictEqual(golpes, 2, "no se le han quitado dos golpes antes de morir");
  assert.strictEqual(jefe.active, 0, "el jefe sigue vivo");
  assert.strictEqual(w.state, NP.STATE.LEVEL_END,
                     "matar al jefe no ha terminado el nivel");
  assert.strictEqual(w.bossHealth, 0, "el marcador sigue ensenando al jefe muerto");
});

prueba("sin jefe en pantalla el marcador no ensena nada", function () {
  var w = mundo(suelo([[13, 5, "e"], [8, 5, "P"]]));
  for (var i = 0; i < 60; i++) w.step(0);
  assert.strictEqual(w.bossHealth, 0);
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
  for (var i = 0; i < 200 && w.players[0].health === 3; i++) w.step(NP.IN.RIGHT);
  assert.strictEqual(w.players[0].health, 2, "un solo golpe deberia quitar una vida");
  assert.ok(w.players[0].invuln > 0, "no hay invulnerabilidad tras el golpe");
});

/* ------------------------------------------------------------- ataque */

prueba("sin ataque, el boton de accion no hace nada", function () {
  var w = mundo(suelo([[13, 8, "e"]]));
  for (var i = 0; i < 30; i++) w.step(NP.IN.ACTION);
  var balas = w.entities.filter(function (e) { return e.active && e.kind === 2; });
  assert.strictEqual(balas.length, 0, "ha salido un disparo sin haber ataque");
});

prueba("disparar saca un proyectil que vuela hacia donde miras", function () {
  var w = mundo(suelo([[13, 2, "P"]]), { ataque: "disparo" });
  w.step(NP.IN.RIGHT);                       // mirando a la derecha
  w.step(NP.IN.ACTION);
  var bala = w.entities.filter(function (e) { return e.active && e.kind === 2; })[0];
  assert.ok(bala, "no ha salido ningun proyectil");
  var x0 = NP.F2I(bala.x);
  w.step(0);
  assert.ok(NP.F2I(bala.x) > x0, "el proyectil no avanza hacia la derecha");
});

prueba("el proyectil mata al enemigo y da puntos", function () {
  var w = mundo(suelo([[13, 2, "P"], [13, 10, "e"]]),
                { ataque: "disparo", alcance: 200 });
  w.step(NP.IN.RIGHT);
  w.step(NP.IN.ACTION);
  for (var i = 0; i < 120 && w.score === 0; i++) w.step(0);
  assert.ok(w.score > 0, "el disparo no ha matado al enemigo");
  var vivos = w.entities.filter(function (e) { return e.active && e.kind === 0; });
  assert.strictEqual(vivos.length, 0, "el enemigo sigue vivo");
});

prueba("el proyectil se apaga contra una pared", function () {
  var filas = suelo([[13, 2, "P"]]);
  filas[13] = filas[13].slice(0, 6) + "#" + filas[13].slice(7);   // pared delante
  var w = mundo(filas, { ataque: "disparo", alcance: 200 });
  w.step(NP.IN.RIGHT);
  w.step(NP.IN.ACTION);
  for (var i = 0; i < 120; i++) w.step(0);
  var balas = w.entities.filter(function (e) { return e.active && e.kind === 2; });
  assert.strictEqual(balas.length, 0, "el proyectil ha atravesado la pared");
});

prueba("el proyectil se apaga al agotar su alcance", function () {
  var w = mundo(suelo([[13, 2, "P"]]),
                { ataque: "disparo", alcance: 24, balaVelocidad: 3 });
  w.step(NP.IN.RIGHT);
  w.step(NP.IN.ACTION);
  var vivo = 0;
  for (var i = 0; i < 60; i++) {
    w.step(0);
    if (w.entities.some(function (e) { return e.active && e.kind === 2; })) vivo++;
  }
  assert.ok(vivo > 2 && vivo < 40,
    "el proyectil ha durado " + vivo + " frames: el alcance no se respeta");
});

prueba("la espera entre disparos se respeta", function () {
  var w = mundo(suelo([[13, 2, "P"]]), { ataque: "disparo", espera: 30 });
  w.step(NP.IN.RIGHT);
  w.step(NP.IN.ACTION);
  w.step(0);                                  // soltar, para que sea otro flanco
  w.step(NP.IN.ACTION);
  var balas = w.entities.filter(function (e) { return e.active && e.kind === 2; });
  assert.strictEqual(balas.length, 1, "ha disparado dos veces seguidas");
});

prueba("mantener el boton no dispara sin parar", function () {
  var w = mundo(suelo([[13, 2, "P"]]), { ataque: "disparo", espera: 1 });
  for (var i = 0; i < 20; i++) w.step(NP.IN.ACTION);   // sin soltarlo nunca
  var balas = w.entities.filter(function (e) { return e.active && e.kind === 2; });
  assert.strictEqual(balas.length, 1, "el boton dispara solo con mantenerlo");
});

prueba("el golpe mata de cerca y no saca proyectil", function () {
  var w = mundo(suelo([[13, 2, "P"], [13, 4, "e"]]),
                { ataque: "golpe", alcance: 40, duracion: 10 });
  w.step(NP.IN.RIGHT);
  w.step(NP.IN.ACTION);
  for (var i = 0; i < 10 && w.score === 0; i++) w.step(0);
  assert.ok(w.score > 0, "el golpe no ha matado al enemigo de al lado");
  var balas = w.entities.filter(function (e) { return e.active && e.kind === 2; });
  assert.strictEqual(balas.length, 0, "un golpe no deberia sacar proyectil");
});

prueba("el golpe no llega mas alla de su alcance", function () {
  var w = mundo(suelo([[13, 2, "P"], [13, 14, "e"]]),
                { ataque: "golpe", alcance: 8, duracion: 10 });
  w.step(NP.IN.ACTION);
  for (var i = 0; i < 10; i++) w.step(0);
  assert.strictEqual(w.score, 0, "el golpe ha llegado a un enemigo lejano");
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

prueba("sin las llaves que pide el nivel la meta no se abre", function () {
  var w = mundo(suelo([[13, 6, "G"], [13, 2, "P"]]), { llaves: 1 });
  correr(w, 200, NP.IN.RIGHT);
  assert.strictEqual(w.keys, 0, "no habia ninguna llave que coger");
  assert.strictEqual(w.state, NP.STATE.PLAY,
    "la meta se ha abierto sin la llave");
});

prueba("con la llave en la mano la meta se abre", function () {
  var w = mundo(suelo([[13, 4, "k"], [13, 8, "G"], [13, 2, "P"]]), { llaves: 1 });
  correr(w, 200, NP.IN.RIGHT);
  assert.strictEqual(w.keys, 1, "no se ha cogido la llave");
  assert.ok(w.state === NP.STATE.LEVEL_END || w.state === NP.STATE.FINISHED,
    "con la llave cogida la meta sigue cerrada");
});

prueba("una llave que vale por varias abre la meta ella sola", function () {
  var w = mundo(suelo([[13, 4, "k"], [13, 8, "G"], [13, 2, "P"]]),
                { llaves: 3, valorLlave: 3 });
  correr(w, 200, NP.IN.RIGHT);
  assert.strictEqual(w.keys, 3, "la llave no ha sumado su cantidad");
  assert.ok(w.state === NP.STATE.LEVEL_END || w.state === NP.STATE.FINISHED,
    "tres llaves de tres y la meta sigue cerrada");
});

prueba("las llaves son de la partida: las coge uno y le valen al otro", function () {
  /* el segundo jugador sale en el mismo sitio que el primero: se le manda a el
     a por la llave y es el primero el que sale por la meta */
  var w = mundo(suelo([[13, 5, "k"], [13, 2, "G"], [13, 8, "P"]]),
                { llaves: 1, jugadores: 2 });
  var i;
  for (i = 0; i < 120; i++) w.step(0, NP.IN.LEFT);       /* el 2 va a la llave */
  assert.strictEqual(w.keys, 1, "el segundo jugador no ha cogido la llave");
  for (i = 0; i < 200 && w.state === NP.STATE.PLAY; i++) w.step(NP.IN.LEFT, 0);
  assert.ok(w.state === NP.STATE.LEVEL_END || w.state === NP.STATE.FINISHED,
    "la llave del segundo jugador no le vale al primero");
});

prueba("las llaves no se guardan de un nivel para otro", function () {
  var w = mundo(suelo([[13, 4, "k"], [13, 2, "P"]]));
  correr(w, 120, NP.IN.RIGHT);
  assert.strictEqual(w.keys, 1);
  w.loadLevel(0);
  assert.strictEqual(w.keys, 0, "las llaves han sobrevivido al cambio de nivel");
});

/* --------------------------------------- el golpe recibido: empujon y susto */

prueba("recibir un golpe te empuja hacia atras", function () {
  var w = mundo(suelo([[13, 8, "e"], [13, 2, "P"]]), { health: 3, retroceso: 3 });
  var p = w.players[0], i;
  /* se mira en el frame del golpe: un par de frames despues el propio mando
     ya le esta acelerando otra vez hacia delante */
  for (i = 0; i < 400 && p.health === 3; i++) w.step(NP.IN.RIGHT);
  assert.ok(p.health < 3, "el enemigo no ha hecho dano");
  assert.ok(p.vx < 0, "el golpe no le ha empujado hacia atras: vx=" + p.vx);
  assert.strictEqual(p.vx, -w.data.player.knockback, "el empujon no es el pedido");
});

prueba("con retroceso grande sales mas lejos", function () {
  function donde(retroceso) {
    var w = mundo(suelo([[13, 8, "e"], [13, 2, "P"]]),
                  { health: 3, retroceso: retroceso, aturdido: 30 });
    var i;
    for (i = 0; i < 400 && w.players[0].health === 3; i++) w.step(NP.IN.RIGHT);
    var x = w.players[0].x;
    correr(w, 30);                    /* que le lleve el empujon */
    return x - w.players[0].x;        /* cuanto ha retrocedido */
  }
  var poco = donde(1), mucho = donde(4);
  assert.ok(mucho > poco, "el retroceso no cambia nada: " + mucho + " vs " + poco);
});

prueba("aturdido no se puede andar ni saltar", function () {
  var w = mundo(suelo([[13, 8, "e"], [13, 2, "P"]]),
                { health: 3, aturdido: 40, retroceso: 2 });
  var i;
  for (i = 0; i < 400 && w.players[0].health === 3; i++) w.step(NP.IN.RIGHT);
  assert.strictEqual(w.players[0].stun, 40, "no se ha quedado aturdido");
  var p = w.players[0];
  var vxAntes = p.vx;
  w.step(NP.IN.RIGHT | NP.IN.JUMP);
  assert.strictEqual(p.vx, vxAntes, "aturdido sigue acelerando con el mando");
  assert.ok(p.vy >= 0 || p.onGround === 0, "aturdido ha saltado");
  correr(w, 60);
  assert.strictEqual(p.stun, 0, "el aturdimiento no se acaba nunca");
  correr(w, 30, NP.IN.RIGHT);
  assert.ok(p.vx > 0, "no recupera el control al pasarsele el aturdimiento");
});

prueba("sin aturdimiento se recupera el control al momento", function () {
  var w = mundo(suelo([[13, 8, "e"], [13, 2, "P"]]), { health: 3, aturdido: 0 });
  var i;
  for (i = 0; i < 400 && w.players[0].health === 3; i++) w.step(NP.IN.RIGHT);
  assert.strictEqual(w.players[0].stun, 0);
  correr(w, 20, NP.IN.RIGHT);
  assert.ok(w.players[0].vx > 0, "no puede moverse justo despues del golpe");
});

/* ------------------------------------------- el ataque: preparacion y clavarse */

prueba("con preparacion el golpe no toca en los primeros frames", function () {
  function vivoTras(preparacion, frames) {
    /* el enemigo, pegado: patrulla y se va alejando, y con preparacion el
       golpe tarda seis frames en tocar */
    var w = mundo(suelo([[13, 3, "e"], [13, 2, "P"]]),
                  { ataque: "golpe", alcance: 24, duracion: 10,
                    preparacion: preparacion, espera: 60 });
    correr(w, 4);                     /* que caiga al suelo, y poco mas: el
                                         enemigo patrulla y se aleja */
    w.step(NP.IN.ACTION);
    correr(w, frames);
    return w.entities[0].active;
  }
  /* sin preparacion el enemigo cae en cuanto empieza el golpe */
  assert.strictEqual(vivoTras(0, 1), 0, "sin preparacion no ha matado");
  /* con preparacion de 6, al segundo frame todavia esta vivo */
  assert.strictEqual(vivoTras(6, 1), 1, "la preparacion no retrasa el golpe");
  /* pero acaba cayendo cuando el brazo llega */
  assert.strictEqual(vivoTras(6, 9), 0, "el golpe no llega nunca a tocar");
});

function avanzaPegando(clavado) {
  var w = mundo(suelo([[13, 2, "P"]]),
                { ataque: "golpe", duracion: 20, espera: 60, clavado: clavado });
  correr(w, 30, NP.IN.RIGHT);         /* llega a velocidad de crucero */
  var x = w.players[0].x;
  w.step(NP.IN.ACTION | NP.IN.RIGHT);
  correr(w, 15, NP.IN.RIGHT);
  return { avance: w.players[0].x - x, mundo: w, desde: x };
}

prueba("con 'clavado' el golpe te planta en el sitio", function () {
  var con = avanzaPegando(true);
  var sin = avanzaPegando(false);
  assert.ok(con.avance < sin.avance / 3,
    "clavado avanza casi lo mismo que sin clavar: " + con.avance + " vs " + sin.avance);
  /* y al acabar el golpe vuelve a andar */
  correr(con.mundo, 40, NP.IN.RIGHT);
  assert.ok(con.mundo.players[0].x > con.desde + con.avance,
    "no vuelve a andar al acabar el golpe");
});

prueba("sin 'clavado' se puede andar pegando", function () {
  var sin = avanzaPegando(false);
  assert.ok(sin.avance > 0, "clavado sin pedirlo");
});

prueba("clavado en el aire no te frena: saltas y pegas de camino", function () {
  var w = mundo(suelo([[13, 2, "P"]]),
                { ataque: "golpe", duracion: 20, espera: 60, clavado: true });
  correr(w, 30, NP.IN.RIGHT);
  w.step(NP.IN.JUMP | NP.IN.RIGHT);
  correr(w, 4, NP.IN.RIGHT);
  var x = w.players[0].x;
  assert.strictEqual(w.players[0].onGround, 0, "no esta en el aire");
  w.step(NP.IN.ACTION | NP.IN.RIGHT);
  correr(w, 8, NP.IN.RIGHT);
  assert.ok(w.players[0].x > x + NP.I2F(4),
    "el golpe le ha frenado en el aire");
});

prueba("el golpe recibido corta el ataque a medias", function () {
  var w = mundo(suelo([[13, 5, "e"], [13, 2, "P"]]),
                { ataque: "golpe", duracion: 40, espera: 90, health: 3,
                  alcance: 4, aturdido: 20 });
  correr(w, 30);
  w.step(NP.IN.ACTION);
  assert.ok(w.players[0].attackTimer > 0, "no ha empezado a pegar");
  var i;
  for (i = 0; i < 300 && w.players[0].health === 3; i++) w.step(NP.IN.RIGHT);
  assert.strictEqual(w.players[0].attackTimer, 0,
    "sigue pegando despues de que le hayan dado");
});

/* --------------------------------------------------------- escaleras */

/* Una escalera de tres escalones que sube a la derecha, entre dos suelos:
 *
 *   fila  9   ......####      suelo de arriba
 *   fila 10   ...../....
 *   fila 11   ..../.....
 *   fila 12   .../......
 *   fila 13   ##########      suelo de abajo (el de suelo())
 */
function conEscalera(subeDerecha) {
  var filas = [];
  for (var y = 0; y < 13; y++) filas.push(".".repeat(24));
  filas.push("#".repeat(24));       /* fila 13: el suelo de abajo */
  function pon(fila, col, ch) {
    var f = filas[fila].split("");
    f[col] = ch;
    filas[fila] = f.join("");
  }
  if (subeDerecha) {
    pon(12, 3, "/"); pon(11, 4, "/"); pon(10, 5, "/");
    for (var c = 6; c < 10; c++) pon(9, c, "#");     /* suelo de arriba */
  } else {
    pon(12, 8, "\\"); pon(11, 7, "\\"); pon(10, 6, "\\");
    for (var d = 1; d < 6; d++) pon(9, d, "#");
  }
  return filas;
}

function ponerP(filas, fila, col) {
  var f = filas[fila].split("");
  f[col] = "P";
  filas[fila] = f.join("");
  return filas;
}

/* Planta al jugador de pie encima de `filaSuelo`, centrado en `col`.
 *
 * Hace falta porque para subirse a una escalera hay que estar **dentro** de su
 * casilla, y el simbolo 'P' del mapa la borraria: la salida y el primer
 * escalon quieren la misma celda. */
function plantar(w, col, filaSuelo) {
  var p = w.players[0], a = w.data.player.actor;
  p.x = NP.I2F(col * 16 + 8 - Math.floor(a.box_w / 2));
  p.y = NP.I2F(filaSuelo * 16 - a.box_h);
  p.vx = 0;
  p.vy = 0;
  w.step(0);                      /* un frame para que se apoye */
  return p;
}

prueba("pulsando arriba en la base te subes a la escalera", function () {
  var w = mundo(ponerP(conEscalera(true), 12, 1));
  plantar(w, 3, 13);                 /* al pie de la escalera */
  assert.strictEqual(w.players[0].stairs, 0, "se ha subido sin pedirlo");
  w.step(NP.IN.UP);
  assert.strictEqual(w.players[0].stairs, 1, "no se ha subido a la escalera");
  assert.strictEqual(w.players[0].stairDir, 1, "no ha cogido el sentido");
});

prueba("subiendo se llega al suelo de arriba y se sale de la escalera", function () {
  var w = mundo(ponerP(conEscalera(true), 12, 1));
  plantar(w, 3, 13);
  var i;
  for (i = 0; i < 200 && w.players[0].stairs === 0; i++) w.step(NP.IN.UP);
  assert.strictEqual(w.players[0].stairs, 1, "no ha llegado a subirse");
  for (i = 0; i < 300 && w.players[0].stairs; i++) w.step(NP.IN.UP);
  assert.strictEqual(w.players[0].stairs, 0, "no sale nunca de la escalera");
  var p = w.players[0];
  assert.strictEqual(p.onGround, 1, "no ha quedado de pie al salir");
  /* de pie encima de la fila 9, que es el suelo de arriba */
  assert.strictEqual(NP.F2I(p.y) + w.data.player.actor.box_h, 9 * 16,
    "no ha quedado plantado en el suelo de arriba");
  correr(w, 40);
  assert.strictEqual(p.onGround, 1, "se ha caido despues de salir");
});

prueba("bajando desde arriba se llega al suelo de abajo", function () {
  var w = mundo(ponerP(conEscalera(true), 8, 1));
  plantar(w, 6, 9);                  /* de pie en el suelo de arriba */
  assert.strictEqual(w.players[0].onGround, 1);
  w.step(NP.IN.DOWN);
  assert.strictEqual(w.players[0].stairs, 1, "no se ha bajado a la escalera");
  var i;
  for (i = 0; i < 300 && w.players[0].stairs; i++) w.step(NP.IN.DOWN);
  var p = w.players[0];
  assert.strictEqual(p.stairs, 0, "no sale de la escalera");
  assert.strictEqual(NP.F2I(p.y) + w.data.player.actor.box_h, 13 * 16,
    "no ha quedado plantado en el suelo de abajo");
});

prueba("la escalera que sube a la izquierda va al otro lado", function () {
  var w = mundo(ponerP(conEscalera(false), 12, 1));
  plantar(w, 8, 13);
  var x0 = w.players[0].x;
  w.step(NP.IN.UP);
  assert.strictEqual(w.players[0].stairs, 1, "no se ha subido");
  assert.strictEqual(w.players[0].stairDir, -1, "el sentido esta al reves");
  correr(w, 20, NP.IN.UP);
  assert.ok(w.players[0].x < x0, "sube hacia la derecha en vez de a la izquierda");
});

prueba("en la escalera no hay gravedad ni saltos", function () {
  var w = mundo(ponerP(conEscalera(true), 12, 1));
  plantar(w, 3, 13);
  w.step(NP.IN.UP);
  correr(w, 6, NP.IN.UP);
  var y = w.players[0].y;
  correr(w, 30);                     /* sin tocar nada: no se cae */
  assert.strictEqual(w.players[0].y, y, "se ha caido estando en la escalera");
  correr(w, 20, NP.IN.JUMP);
  assert.strictEqual(w.players[0].stairs, 1, "el salto le ha sacado");
  assert.strictEqual(w.players[0].y, y, "ha saltado desde la escalera");
});

prueba("izquierda y derecha no hacen nada en la escalera", function () {
  var w = mundo(ponerP(conEscalera(true), 12, 1));
  plantar(w, 3, 13);
  w.step(NP.IN.UP);
  correr(w, 4, NP.IN.UP);
  var x = w.players[0].x;
  correr(w, 30, NP.IN.RIGHT);
  assert.strictEqual(w.players[0].x, x, "se mueve de lado en la escalera");
});

prueba("un golpe te tira de la escalera", function () {
  var filas = conEscalera(true);
  filas = ponerP(filas, 12, 1);
  var f = filas[12].split(""); f[6] = "v"; filas[12] = f.join("");  /* volador */
  var w = mundo(filas, { health: 3, aturdido: 20 });
  plantar(w, 3, 13);
  w.step(NP.IN.UP);
  assert.strictEqual(w.players[0].stairs, 1);
  var i;
  for (i = 0; i < 400 && w.players[0].health === 3; i++) w.step(NP.IN.UP);
  assert.ok(w.players[0].health < 3, "el volador no le ha tocado");
  assert.strictEqual(w.players[0].stairs, 0, "sigue en la escalera tras el golpe");
});

prueba("desde la escalera se puede pegar", function () {
  var w = mundo(ponerP(conEscalera(true), 12, 1),
                { ataque: "golpe", espera: 60, duracion: 12 });
  plantar(w, 3, 13);
  w.step(NP.IN.UP);
  assert.strictEqual(w.players[0].stairs, 1);
  w.step(NP.IN.ACTION);
  assert.ok(w.players[0].attackTimer > 0, "no se puede pegar en la escalera");
  assert.strictEqual(w.players[0].stairs, 1, "pegar le ha sacado de la escalera");
});

prueba("con velocidad_escalera a cero no hay escaleras", function () {
  var w = mundo(ponerP(conEscalera(true), 12, 1), { escalera: 0 });
  plantar(w, 3, 13);
  correr(w, 20, NP.IN.UP);
  assert.strictEqual(w.players[0].stairs, 0,
    "se sube a una escalera en un juego que no las lleva");
});

prueba("la escalera no frena a nadie: se pasa por delante andando", function () {
  var w = mundo(ponerP(conEscalera(true), 12, 1));
  correr(w, 10);
  var x = w.players[0].x;
  correr(w, 90, NP.IN.RIGHT);        /* pasa por delante de la escalera */
  assert.ok(w.players[0].x > x + NP.I2F(40), "la escalera le ha frenado");
  assert.strictEqual(w.players[0].stairs, 0, "se ha subido solo al pasar");
});

/* ------------------------------------ candelabros: pegarles y que suelten */

function entidadDe(w, kind) {
  for (var i = 0; i < w.entityCount; i++)
    if (w.entities[i].active && w.entities[i].kind === kind) return w.entities[i];
  return null;
}

prueba("un enemigo con vida aguanta un golpe por ataque, no uno por frame", function () {
  /* la caja del golpe dura varios frames y acertaba en todos: un solo ataque
     se llevaba por delante a un enemigo de cinco de vida */
  var w = mundo(suelo([[13, 3, "J"], [13, 2, "P"]]),
                { ataque: "golpe", alcance: 24, espera: 90, duracion: 8,
                  bossHealth: 5, health: 9 });
  correr(w, 4);
  w.step(NP.IN.ACTION);
  correr(w, 8);
  assert.strictEqual(w.entities[0].health, 4,
    "un solo ataque le ha quitado mas de un golpe de vida");
  assert.strictEqual(w.entities[0].active, 1, "lo ha matado de un ataque");
});

prueba("el candelabro no hace nada hasta que le pegas", function () {
  var w = mundo(suelo([[13, 4, "C"], [13, 2, "P"]]), { health: 3 });
  correr(w, 120, NP.IN.RIGHT);        /* se le pasa por encima */
  assert.strictEqual(w.players[0].health, 3, "el candelabro hace dano");
  assert.ok(entidadDe(w, 4), "el candelabro ha desaparecido solo");
});

prueba("el golpe rompe el candelabro y suelta lo que lleva", function () {
  var w = mundo(suelo([[13, 3, "C"], [13, 2, "P"]]),
                { ataque: "golpe", alcance: 24, espera: 60 });
  correr(w, 4);
  var puntos = w.score;
  w.step(NP.IN.ACTION);
  correr(w, 4);
  assert.strictEqual(entidadDe(w, 4), null, "el candelabro sigue entero");
  var objeto = entidadDe(w, 1);
  assert.ok(objeto, "no ha soltado nada");
  assert.strictEqual(objeto.def, 0, "ha soltado un objeto que no era");
  assert.ok(w.score > puntos, "romperlo no ha dado puntos");
});

prueba("lo que suelta se puede recoger", function () {
  var w = mundo(suelo([[13, 3, "C"], [13, 2, "P"]]),
                { ataque: "golpe", alcance: 24, espera: 60 });
  correr(w, 4);
  w.step(NP.IN.ACTION);
  correr(w, 4);
  var antes = w.score;
  correr(w, 60, NP.IN.RIGHT);        /* se va a por ello */
  assert.strictEqual(entidadDe(w, 1), null, "no ha recogido lo que ha soltado");
  assert.ok(w.score > antes, "recogerlo no ha dado puntos");
});

prueba("un candelabro vacio se rompe y no suelta nada", function () {
  var w = mundo(suelo([[13, 3, "V"], [13, 2, "P"]]),
                { ataque: "golpe", alcance: 24, espera: 60 });
  correr(w, 4);
  w.step(NP.IN.ACTION);
  correr(w, 4);
  assert.strictEqual(entidadDe(w, 4), null, "sigue entero");
  assert.strictEqual(entidadDe(w, 1), null, "ha soltado algo sin llevar nada");
});

prueba("un candelabro duro aguanta varios golpes", function () {
  var w = mundo(suelo([[13, 3, "C"], [13, 2, "P"]]),
                { ataque: "golpe", alcance: 24, espera: 8, candelabroVida: 3 });
  correr(w, 4);
  w.step(NP.IN.ACTION);
  correr(w, 4);
  assert.ok(entidadDe(w, 4), "ha caido al primer golpe llevando tres de vida");
  /* el boton va por flanco: hay que soltarlo entre golpe y golpe */
  var i;
  for (i = 0; i < 120 && entidadDe(w, 4); i++)
    w.step(i % 12 === 0 ? NP.IN.ACTION : 0);
  assert.strictEqual(entidadDe(w, 4), null, "no cae ni a golpes");
});

prueba("el disparo tambien rompe candelabros", function () {
  var w = mundo(suelo([[13, 8, "C"], [13, 2, "P"]]),
                { ataque: "disparo", alcance: 128, espera: 60 });
  correr(w, 4);
  w.step(NP.IN.ACTION);
  correr(w, 60);
  assert.strictEqual(entidadDe(w, 4), null, "el disparo no lo ha roto");
  assert.ok(entidadDe(w, 1), "no ha soltado nada");
});

/* --------------------------------------- corazones y arma secundaria */

prueba("los corazones se cuentan aparte de la vida", function () {
  var filas = suelo([[13, 2, "P"]]);
  /* la municion se coloca a mano: el simbolo 'o' es el objeto 0 */
  var w = mundo(filas, { secundaria: "recta" });
  w.entities.push({
    active: 1, kind: 1, def: 2, x: NP.I2F(60), y: NP.I2F(210),
    homeX: 0, homeY: 0, vx: 0, vy: 0, facing: 0, anim: 0, animFrame: 0,
    animTimer: 0, hurt: 0, timer: 0, health: 1, vida: 0
  });
  w.entityCount = w.entities.length;
  var vida = w.players[0].health;
  correr(w, 90, NP.IN.RIGHT);
  assert.strictEqual(w.hearts, 5, "no ha cogido la municion: " + w.hearts);
  assert.strictEqual(w.players[0].health, vida, "la municion ha dado vida");
});

prueba("arriba + accion tira el arma secundaria y gasta municion", function () {
  var w = mundo(suelo([[13, 2, "P"]]), { secundaria: "recta", subCoste: 2 });
  w.hearts = 5;
  correr(w, 4);
  w.step(NP.IN.UP | NP.IN.ACTION);
  correr(w, 2);
  assert.ok(entidadDe(w, 5), "no ha salido nada");
  assert.strictEqual(w.hearts, 3, "no ha gastado la municion que cuesta");
});

prueba("sin municion no sale el arma secundaria: se pega", function () {
  var w = mundo(suelo([[13, 2, "P"]]),
                { secundaria: "recta", subCoste: 2, ataque: "golpe", espera: 60 });
  w.hearts = 1;
  correr(w, 4);
  w.step(NP.IN.UP | NP.IN.ACTION);
  correr(w, 2);
  assert.strictEqual(entidadDe(w, 5), null, "ha tirado sin municion");
  assert.strictEqual(w.hearts, 1, "ha gastado municion igualmente");
  assert.ok(w.players[0].attackTimer > 0, "no ha pegado en su lugar");
});

prueba("el boton a secas no gasta municion", function () {
  var w = mundo(suelo([[13, 2, "P"]]),
                { secundaria: "recta", ataque: "golpe", espera: 60 });
  w.hearts = 4;
  correr(w, 4);
  w.step(NP.IN.ACTION);
  correr(w, 2);
  assert.strictEqual(w.hearts, 4, "el ataque normal gasta municion");
  assert.strictEqual(entidadDe(w, 5), null, "el boton a secas tira el arma");
});

prueba("el arma en arco cae, la recta no", function () {
  function altura(tipo) {
    var w = mundo(suelo([[13, 2, "P"]]),
                  { secundaria: tipo, subAlcance: 300, subSalto: 2, subGravedad: 0.3 });
    w.hearts = 9;
    correr(w, 4);
    w.step(NP.IN.UP | NP.IN.ACTION);
    var e = entidadDe(w, 5);
    var y0 = e.y, mas = y0;
    var i;
    for (i = 0; i < 40 && e.active; i++) {
      w.step(0);
      if (e.y > mas) mas = e.y;
    }
    return mas - y0;
  }
  assert.strictEqual(altura("recta"), 0, "la recta se ha caido");
  assert.ok(altura("arco") > 0, "el arco no cae");
});

prueba("el arma secundaria mata enemigos y rompe candelabros", function () {
  var w = mundo(suelo([[13, 8, "e"], [13, 12, "C"], [13, 2, "P"]]),
                { secundaria: "recta", subAlcance: 300, subEspera: 4 });
  w.hearts = 20;
  correr(w, 4);
  /* el boton va por flanco: mantenerlo pulsado tira una sola vez */
  var i;
  for (i = 0; i < 400; i++)
    w.step(i % 8 === 0 ? (NP.IN.UP | NP.IN.ACTION) : 0);
  assert.strictEqual(entidadDe(w, 0), null, "no ha matado al enemigo");
  assert.strictEqual(entidadDe(w, 4), null, "no ha roto el candelabro");
});

/* ------------------------------------------------- plataformas moviles */

function tablonDe(w) {
  for (var i = 0; i < w.entityCount; i++)
    if (w.entities[i].active && w.entities[i].kind === 3) return w.entities[i];
  return null;
}

prueba("la plataforma va y viene entre sus dos extremos", function () {
  var w = mundo(suelo([[11, 5, "T"], [13, 2, "P"]]), { tablonDistancia: 48 });
  var t = tablonDe(w);
  assert.ok(t, "no ha salido la plataforma");
  var casa = t.homeX, minimo = t.x, maximo = t.x, i;
  for (i = 0; i < 400; i++) {
    w.step(0);
    if (t.x < minimo) minimo = t.x;
    if (t.x > maximo) maximo = t.x;
  }
  assert.strictEqual(minimo, casa, "se ha ido por detras de donde salio");
  assert.strictEqual(maximo, casa + NP.I2F(48), "no llega al final del recorrido");
});

prueba("el jugador cae encima de la plataforma y se queda", function () {
  var w = mundo(suelo([[11, 5, "T"], [9, 5, "P"]]), { tablonVelocidad: 0 });
  correr(w, 60);
  var t = tablonDe(w), p = w.players[0];
  assert.strictEqual(p.onGround, 1, "no se ha plantado encima");
  assert.strictEqual(p.riding, 1, "no se ha subido a la plataforma");
  assert.strictEqual(p.y + NP.I2F(w.data.player.actor.box_h), t.y,
    "no se queda a ras de la plataforma");
});

prueba("la plataforma se lleva al jugador consigo", function () {
  var w = mundo(suelo([[11, 5, "T"], [9, 5, "P"]]), { tablonVelocidad: 0.5 });
  correr(w, 60);                       /* que aterrice */
  var t = tablonDe(w), p = w.players[0];
  assert.strictEqual(p.riding, 1, "no se ha subido");
  var antesP = p.x, antesT = t.x;
  correr(w, 30);
  assert.notStrictEqual(t.x, antesT, "la plataforma no se mueve");
  assert.strictEqual(p.x - antesP, t.x - antesT,
    "el jugador no se ha movido lo mismo que la plataforma");
});

prueba("una plataforma vertical sube y baja con el jugador encima", function () {
  var w = mundo(suelo([[11, 5, "T"], [9, 5, "P"]]),
                { tablonEje: "vertical", tablonVelocidad: 0.5, tablonDistancia: 32 });
  correr(w, 60);
  var t = tablonDe(w), p = w.players[0];
  assert.strictEqual(p.riding, 1, "no se ha subido");
  var alturas = {}, i;
  for (i = 0; i < 300; i++) {
    w.step(0);
    alturas[t.y] = 1;
    assert.strictEqual(p.y + NP.I2F(w.data.player.actor.box_h), t.y,
      "el jugador se ha despegado de la plataforma en el frame " + i);
  }
  assert.ok(Object.keys(alturas).length > 10, "la plataforma no se mueve");
});

prueba("desde la plataforma se puede saltar", function () {
  var w = mundo(suelo([[11, 5, "T"], [9, 5, "P"]]), { tablonVelocidad: 0 });
  correr(w, 60);
  var t = tablonDe(w), p = w.players[0];
  assert.strictEqual(p.riding, 1);
  w.step(NP.IN.JUMP);
  assert.ok(p.vy < 0, "no salta desde encima de la plataforma");
  correr(w, 8, NP.IN.JUMP);
  assert.ok(p.y + NP.I2F(w.data.player.actor.box_h) < t.y,
    "el salto no le despega de la plataforma");
  assert.strictEqual(p.riding, 0, "sigue apuntado a la plataforma en el aire");
});

prueba("por debajo se pasa a traves, como un tile de plataforma", function () {
  /* el jugador esta justo debajo y salta: tiene que atravesarla */
  var w = mundo(suelo([[11, 5, "T"], [13, 5, "P"]]),
                { tablonVelocidad: 0, jump: 6.5 });
  correr(w, 30);
  var t = tablonDe(w), p = w.players[0];
  var arriba = 0, i;
  for (i = 0; i < 40; i++) {
    w.step(NP.IN.JUMP);
    if (p.y + NP.I2F(w.data.player.actor.box_h) < t.y - NP.I2F(2)) arriba = 1;
  }
  assert.ok(arriba, "la plataforma le ha frenado por debajo");
});

prueba("pulsando abajo se deja caer de la plataforma", function () {
  var w = mundo(suelo([[11, 5, "T"], [9, 5, "P"]]), { tablonVelocidad: 0 });
  correr(w, 60);
  assert.strictEqual(w.players[0].riding, 1, "no se ha subido");
  correr(w, 40, NP.IN.DOWN);
  assert.strictEqual(w.players[0].riding, 0, "sigue encima de la plataforma");
  assert.ok(w.players[0].y > tablonDe(w).y, "no se ha dejado caer");
});

prueba("la plataforma no hace dano ni se puede pisar como a un enemigo", function () {
  var w = mundo(suelo([[11, 5, "T"], [9, 5, "P"]]), { tablonVelocidad: 0, health: 3 });
  var vida = w.players[0].health, puntos = w.score;
  correr(w, 120);
  assert.strictEqual(w.players[0].health, vida, "la plataforma hace dano");
  assert.strictEqual(w.score, puntos, "pisar la plataforma da puntos");
  assert.ok(tablonDe(w), "la plataforma ha desaparecido");
});

prueba("perder todas las vidas lleva a game over y luego al titulo", function () {
  var w = mundo(suelo([[13, 4, "^"], [13, 2, "P"]]), { lives: 1 });
  for (var i = 0; i < 400 && w.state !== NP.STATE.GAME_OVER; i++) w.step(NP.IN.RIGHT);
  assert.strictEqual(w.state, NP.STATE.GAME_OVER);
  correr(w, 300);
  assert.strictEqual(w.state, NP.STATE.TITLE);
  assert.strictEqual(w.players[0].lives, 0);
});

prueba("morir con vidas de sobra reinicia el nivel", function () {
  var w = mundo(suelo([[13, 4, "^"], [13, 2, "P"]]), { lives: 3 });
  var inicio = w.level.start[0];
  for (var i = 0; i < 400 && w.players[0].lives === 3; i++) w.step(NP.IN.RIGHT);
  assert.strictEqual(w.players[0].lives, 2);
  assert.strictEqual(NP.F2I(w.players[0].x), inicio);
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

/* --- camara ---------------------------------------------------------- */

/* Un nivel ancho para que la camara tenga sitio donde moverse. */
function nivelAncho() {
  var filas = [];
  for (var y = 0; y < 14; y++) filas.push(".".repeat(60));
  filas.push("#".repeat(60));
  var f = filas[13].split(""); f[2] = "P"; filas[13] = f.join("");
  return filas;
}

prueba("con scroll, la camara sigue al jugador poco a poco", function () {
  var w = mundo(nivelAncho());
  var vistas = {};
  for (var i = 0; i < 300; i++) { w.step(NP.IN.RIGHT); vistas[w.camX] = 1; }
  assert.ok(Object.keys(vistas).length > 20,
            "la camara deberia tomar muchos valores distintos, no " +
            Object.keys(vistas).length);
});

prueba("con pantallas, la camara solo salta de pantalla en pantalla", function () {
  var w = mundo(nivelAncho(), { pantallas: true });
  var vistas = {};
  for (var i = 0; i < 300; i++) { w.step(NP.IN.RIGHT); vistas[w.camX] = 1; }
  Object.keys(vistas).forEach(function (x) {
    var v = Number(x);
    assert.ok(v % 320 === 0 || v === 60 * 16 - 320,
              "la camara se ha parado en " + v + ", que no es el borde de una pantalla");
  });
  assert.ok(Object.keys(vistas).length > 1, "la camara no ha llegado a saltar");
});

prueba("con pantallas, la camara no se sale del nivel", function () {
  var w = mundo(nivelAncho(), { pantallas: true });
  for (var i = 0; i < 900; i++) {
    w.step(NP.IN.RIGHT);
    assert.ok(w.camX >= 0 && w.camX <= 60 * 16 - 320, "camara fuera: " + w.camX);
  }
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
console.log("\n" + (pruebas.length - fallos) + "/" + pruebas.length + " pruebas de jugabilidad");
process.exit(fallos ? 1 : 0);
