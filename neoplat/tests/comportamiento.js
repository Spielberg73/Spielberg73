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
   4 meta, 6 escalera que sube a la derecha, 7 la que sube a la izquierda,
   8 punto de control). */
var LEYENDA = { ".": 0, "#": 1, "=": 2, "^": 3, "G": 4, "/": 5, "\\": 6, "!": 7,
                /* las dos puertas de las aventuras: "L" la abre la llave y
                   "Y" el tablon (los objetos 5 y 6 de la lista) */
                "L": 8, "Y": 9,
                /* Y el relieve de la vista isometrica: un escalon que se sube
                   andando, un cubo al que hay que saltar y una pared. Son
                   `solido` de toda la vida; lo que cambia es lo que levantan */
                "b": 10, "c": 11, "W": 12,
                /* y la pared que **no se dibuja**, porque ya viene en el
                   dibujo de la sala: levanta lo mismo que "W" y no trae cubo */
                "p": 13 };
var TIPOS = [0, 1, 2, 3, 4, 6, 7, 8, 9, 9, 1, 1, 1, 1];
/* que objeto abre cada tile: el objeto mas uno, 0 = no es cerrojo */
var NECESITA = [0, 0, 0, 0, 0, 0, 0, 0, 6, 7, 0, 0, 0, 0];
/* lo que levanta cada tile (solo lo mira la vista isometrica) y con que cubo
   se dibuja: el indice en `bloques` mas uno, 0 = no se dibuja */
var ALTOS =   [0, 0, 0, 0, 0, 0, 0, 0, 48, 48, 4, 16, 48, 48];
var BLOQUES = [0, 0, 0, 0, 0, 0, 0, 0,  1,  1, 1,  1,  1,  0];

function anim(frames, speed) {
  return { frames: frames, count: frames.length, speed: speed || 8, loop: 1 };
}

function actor(boxW, boxH) {
  return {
    first_tile: 0, palette: 0, cols: 1, rows: 1,
    box_x: 0, box_y: 0, box_w: boxW, box_h: boxH,
    frames: 1, frame_w: 16, frame_h: 16, sheet: "x",
    /* once ranuras: las ocho de siempre, las dos de la vista cenital (de
       espaldas y de frente) y la del remate */
    anims: [anim([0]), anim([0]), anim([0]), anim([0]), anim([0]), anim([0]),
            anim([0]), anim([0]), anim([0]), anim([0]), anim([0])]
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
  /* En la isometrica la caja es la **planta** de lo que se ocupa, no un cuerpo
     apoyado en una linea de suelo: va centrada en la casilla por los dos ejes,
     igual que hace el compilador. */
  function abajo(y, caja) {
    return opciones.iso ? y * 16 + ((16 - caja) >> 1) : y * 16 + 16 - caja;
  }
  for (var y = 0; y < alto; y++) {
    for (var x = 0; x < ancho; x++) {
      var ch = filas[y][x];
      if (ch === "P") { start = [x * 16 + 2, abajo(y, jugador.box_h)]; ch = "."; }
      else if (ch === "e") { spawns.push([x * 16 + 2, abajo(y, enemigo.box_h), 0, 0]); ch = "."; }
      else if (ch === "v") { spawns.push([x * 16 + 2, abajo(y, enemigo.box_h), 0, 1]); ch = "."; }
      else if (ch === "o") { spawns.push([x * 16 + 3, abajo(y, objeto.box_h), 1, 0]); ch = "."; }
      else if (ch === "k") { spawns.push([x * 16 + 3, y * 16 + 16 - objeto.box_h, 1, 1]); ch = "."; }
      else if (ch === "M") { spawns.push([x * 16 + 3, y * 16 + 16 - objeto.box_h, 1, 3]); ch = "."; }
      else if (ch === "H") { spawns.push([x * 16 + 3, y * 16 + 16 - objeto.box_h, 1, 4]); ch = "."; }
      else if (ch === "T") { spawns.push([x * 16, y * 16 + 16 - tablon.box_h, 3, 0]); ch = "."; }
      else if (ch === "C") { spawns.push([x * 16 + 2, y * 16 + 16 - candelabro.box_h, 4, 0]); ch = "."; }
      else if (ch === "V") { spawns.push([x * 16 + 2, y * 16 + 16 - candelabro.box_h, 4, 1]); ch = "."; }
      else if (ch === "J") { spawns.push([x * 16 + 2, y * 16 + 16 - enemigo.box_h, 0, 2]); ch = "."; }
      else if (ch === "R") { spawns.push([x * 16 + 2, y * 16 + 16 - enemigo.box_h, 8, 0]); ch = "."; }
      else if (ch === "N") { spawns.push([x * 16 + 1, y * 16 + 2, 9, 0]); ch = "."; }
      /* los tres objetos que se llevan: llave, tablon y cubo */
      else if (ch === "1") { spawns.push([x * 16 + 3, y * 16 + 6, 1, 5]); ch = "."; }
      else if (ch === "2") { spawns.push([x * 16 + 3, y * 16 + 6, 1, 6]); ch = "."; }
      else if (ch === "3") { spawns.push([x * 16 + 3, y * 16 + 6, 1, 7]); ch = "."; }
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
    /* cuantos enemigos pegan a la vez en un juego de tortas */
    agresivos: opciones.agresivos === undefined ? 2 : opciones.agresivos,
    /* 1 = el juego lleva bolsa (objetos de `efecto: llevar`) */
    bolsa_activa: opciones.bolsa ? 1 : 0,
    /* desde donde se mira: con "cenital" no hay gravedad y se anda en
       ocho direcciones */
    view: opciones.iso ? "iso"
        : (opciones.cinta ? "cinta"
        : (opciones.cenital ? "cenital" : "lateral")),
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
      /* 0 = el salto de las aventuras: al despegar se decide y ya no se cambia */
      air_control: opciones.saltoFijo ? 0 : 1,
      stomp: opciones.stomp === false ? 0 : 1,
      health: opciones.health || 1,
      /* `desgaste:` frames por punto de vida; 0 = la vida solo se pierde a golpes */
      wear: opciones.desgaste || 0,
      /* el agarre de los juegos de tortas; 0 = el juego no lleva agarre */
      grab_time: opciones.agarre || 0,
      grab_damage: opciones.rodillazo === undefined ? 1 : opciones.rodillazo,
      throw_damage: opciones.danoLanzar === undefined ? 2 : opciones.danoLanzar,
      throw_speed: fx(opciones.fuerzaLanzar === undefined
                      ? 3.5 : opciones.fuerzaLanzar),
      /* cuanto baja el techo de la caja al agacharse; 0 = no se puede */
      crouch_drop: opciones.agachado || 0,
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
        /* las mejoras del arma: cada una suma `range_step` al alcance */
        levels: opciones.mejoras || 0,
        range_step: opciones.alcanceMejora === undefined ? 12
                                                         : opciones.alcanceMejora,
        /* 1 = el ataque trae dibujo propio (el latigo) y se ve al pegar */
        fx: opciones.latigo ? 1 : 0,
        /* la serie de golpes de los juegos de tortas: 1 = no hay serie */
        combo: opciones.combo || 1,
        combo_window: opciones.ventana === undefined ? 30 : opciones.ventana,
        finish_damage: opciones.danoRemate || 0,
        finish_stun: opciones.derribo || 0,
        finish_push: fx(opciones.empujonRemate === undefined
                        ? 3 : opciones.empujonRemate),
        actor: actor(6, 6)
      },
      /* las armas secundarias: por defecto ninguna, como un juego sin
         `secundaria:` en el game.yaml. Con `secundaria` sale una, y con
         `secundarias` (una lista de tipos) salen varias, que es lo que hace
         falta para probar el objeto que las cambia. */
      subs: (opciones.secundarias || (opciones.secundaria ? [opciones.secundaria] : []))
        .map(function (tipo, i) {
          return {
            kind: tipo === "arco" ? 2 : 1,
            speed: fx(opciones.subVelocidad || 3),
            gravity: fx(opciones.subGravedad === undefined ? 0.25 : opciones.subGravedad),
            jump: fx(opciones.subSalto === undefined ? 3 : opciones.subSalto),
            range: opciones.subAlcance || 160,
            cooldown: opciones.subEspera === undefined ? 24 : opciones.subEspera,
            cost: opciones.subCoste === undefined ? 1 : opciones.subCoste,
            damage: opciones.subDano || 1,
            at_once: (opciones.subALaVez || [])[i] || 0,
            actor: actor(8, 8),
            name: "arma" + i
          };
        })
    },
    enemies: [
      { actor: enemigo,
        /* con `velocidadEnemigo: 0` se queda quieto, que es lo que hace falta
           para medir golpes sin que se vaya andando */
        speed: fx(opciones.velocidadEnemigo === undefined
                  ? 0.5 : opciones.velocidadEnemigo),
        gravity: fx(0.28), jump: fx(3.5), range: fx(96),
        amplitude: fx(24), period: 120, interval: 90, score: 100, behavior: 0,
        health: opciones.vidaEnemigo || 1,
        damage: 1, stompable: 1, edge_turn: 1, name: "patrulla",
        reach: 0, windup: 16, active: 6, recover: 20, wait: 40, punch: 0,
        /* con `dispara:` este mismo enemigo te tirotea */
        shot: opciones.dispara ? 1 : 0 },
      { actor: enemigo, speed: fx(0.5), gravity: 0, jump: 0, range: fx(96),
        amplitude: fx(24), period: 64, interval: 90, score: 200, behavior: 1,
        health: 1, damage: 1, stompable: 1, edge_turn: 0, name: "volador",
        reach: 0, windup: 16, active: 6, recover: 20, wait: 40, punch: 0 },
      /* el jefe esta quieto salvo que la prueba lo mande perseguir: es la
         forma de probar al perseguidor sin montar otro enemigo */
      { actor: enemigo, speed: opciones.jefePersigue ? fx(0.5) : 0,
        gravity: fx(0.28), jump: 0, range: fx(opciones.jefeRango || 96),
        amplitude: fx(24), period: 120, interval: 90, score: 1000,
        behavior: opciones.jefePersigue ? 2 : 4,
        health: opciones.bossHealth || 3, damage: 1, stompable: 1,
        edge_turn: opciones.jefeBorde === undefined ? 1 : opciones.jefeBorde,
        boss: 1, name: "jefe",
        /* El golpe cuerpo a cuerpo del genero de tortas. Con `alcanceEnemigo`
           a cero -lo normal- no pega: hace dano al tocarte, como siempre. */
        reach: opciones.alcanceEnemigo || 0,
        windup: opciones.avisoEnemigo === undefined ? 16 : opciones.avisoEnemigo,
        active: opciones.duracionEnemigo || 6,
        recover: opciones.recuperaEnemigo === undefined ? 20 : opciones.recuperaEnemigo,
        wait: opciones.esperaEnemigo === undefined ? 40 : opciones.esperaEnemigo,
        punch: opciones.punoEnemigo || 0 }
    ],
    /* los prisioneros: tocarlos los suelta, dispararles los pierde */
    prisoners: [
      { actor: actor(12, 14), score: opciones.rehenPuntos === undefined ? 500
                                     : opciones.rehenPuntos,
        speed: fx(opciones.rehenVelocidad || 1.2),
        escape: opciones.rehenEscape === undefined ? 90 : opciones.rehenEscape,
        name: "prisionero" }
    ],
    /* lo que tiran los enemigos con `dispara:`; el enemigo guarda su numero */
    enemy_shots: [
      { actor: actor(6, 6), speed: fx(opciones.tiroVelocidad || 2),
        range: opciones.tiroAlcance || 200,
        cooldown: opciones.tiroEspera || 30,
        damage: opciones.tiroDano === undefined ? 1 : opciones.tiroDano,
        name: "tiro" }
    ],
    /* Los nidos de Gauntlet: sacan el enemigo 0 (el de patrulla) */
    generators: [
      { actor: actor(14, 14), score: 1000,
        cooldown: opciones.nidoCada === undefined ? 30 : opciones.nidoCada,
        health: opciones.nidoVida === undefined ? 3 : opciones.nidoVida,
        enemy: 0, cap: opciones.nidoTope === undefined ? 3 : opciones.nidoTope,
        name: "nido" }
    ],
    items: [
      { actor: objeto, score: 10,
        effect: opciones.objetoEfecto === undefined ? 0 : opciones.objetoEfecto,
        amount: opciones.objetoCantidad === undefined ? 1 : opciones.objetoCantidad,
        name: "moneda" },
      /* efecto 3 = llave: no da puntos de vida, suma al contador de la partida */
      { actor: objeto, score: 50, effect: 3, amount: opciones.valorLlave || 1,
        name: "llave" },
      /* efecto 4 = municion del arma secundaria */
      { actor: objeto, score: 0, effect: 4, amount: opciones.valorMunicion || 5,
        name: "corazon" },
      /* efecto 5 = mejora del arma: la alarga un paso y se pierde al morir */
      { actor: objeto, score: 200, effect: 5, amount: 1, name: "mejora" },
      /* efecto 6 = cambia el arma secundaria; `amount` es su numero */
      { actor: objeto, score: 0, effect: 6,
        amount: opciones.armaDelObjeto === undefined ? 1 : opciones.armaDelObjeto,
        name: "hacha" },
      /* efecto 8 = se lleva encima (la bolsa de las aventuras). Van tres para
         poder llenarla, que es donde esta la gracia del genero. */
      { actor: objeto, score: 0, effect: 8, amount: 1, name: "llave",
        label: "LLAVE" },
      { actor: objeto, score: 0, effect: 8, amount: 1, name: "tablon",
        label: "TABLO" },
      { actor: objeto, score: 0, effect: 8, amount: 1, name: "cubo",
        label: "CUBO" }
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
    tiles: { kind: TIPOS, gfx: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 0, 0],
             need: NECESITA, alto: ALTOS, bloque: BLOQUES,
             sala: { tile: 0, ancho: 1, alto: 1, x: 0, y: 0 } },
    /* el cubo con el que se dibuja una casilla levantada: aqui solo hace
       falta que exista, porque las pruebas no dibujan nada */
    bloques: [{ actor: actor(16, 16), name: "cubo" }],
    levels: [{
      name: "TEST",
      /* Lo que se dibuja y lo que se pisa. Fuera de la isometrica son lo
         mismo; alli lo que se ve es una sala y lo que se pisa es la planta. */
      width: opciones.iso ? 20 : ancho, height: opciones.iso ? 14 : alto,
      cells_w: ancho, cells_h: alto,
      fondo: opciones.iso ? new Array(20 * 14).fill(0) : [],
      cells: celdas,
      spawns: spawns, start: start, background: "#000000",
      keys_needed: opciones.llaves || 0,
      music: opciones.musicaNivel || 0
    }],
    /* solo los numeros de cancion: para saber cual toca no hace falta ninguna
       nota, y asi la prueba no depende de como suene */
    sonido: { titulo: opciones.musicaTitulo || 0, jefe: opciones.musicaJefe || 0,
              musica: [], efectos: {}, eventos: {} },
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

/* ------------------------------------- el salto fijo (aventuras tipo Dizzy) */
/*
 * Con `salto_fijo: si` el jugador no manda en el aire: al despegar se decide
 * hacia donde va y con cuanto impulso, y hasta que aterriza no se cambia. Ni
 * soltar el boton acorta el salto. Es lo que hace que en una aventura cada
 * salto sea una decision y no un tramite.
 */

prueba("con salto fijo, en el aire el mando no mueve", function () {
  var w = mundo(suelo([[13, 6, "P"]]), { saltoFijo: true });
  correr(w, 20);
  w.step(NP.IN.JUMP);                     // salta parado
  var x0 = NP.F2I(w.players[0].x);
  correr(w, 20, NP.IN.RIGHT);             // y ahora empuja a la derecha
  assert.strictEqual(NP.F2I(w.players[0].x), x0,
                     "se ha movido en el aire con el salto fijo");
});

prueba("sin salto fijo, en el aire si se manda", function () {
  /* El control: el salto de siempre sigue dejando corregir en el aire. */
  var w = mundo(suelo([[13, 6, "P"]]));
  correr(w, 20);
  w.step(NP.IN.JUMP);
  var x0 = NP.F2I(w.players[0].x);
  correr(w, 20, NP.IN.RIGHT);
  assert.ok(NP.F2I(w.players[0].x) > x0 + 8,
            "el salto de siempre deberia dejar mover en el aire");
});

prueba("el salto fijo sale con el impulso que llevabas", function () {
  var w = mundo(suelo([[13, 2, "P"]]), { saltoFijo: true });
  correr(w, 40, NP.IN.RIGHT);             // corriendo
  var x0 = NP.F2I(w.players[0].x);
  w.step(NP.IN.RIGHT | NP.IN.JUMP);
  correr(w, 20, 0);                       // se suelta todo al despegar
  assert.ok(NP.F2I(w.players[0].x) > x0 + 20,
            "el salto no ha conservado el impulso: x=" + NP.F2I(w.players[0].x));
});

prueba("el salto fijo hace siempre el mismo arco", function () {
  function altura(mantener) {
    var w = mundo(suelo([[13, 2, "P"]]), { saltoFijo: true });
    correr(w, 30);
    var y0 = NP.F2I(w.players[0].y), min = y0;
    for (var i = 0; i < 90; i++) {
      w.step(mantener || i < 2 ? NP.IN.JUMP : 0);
      min = Math.min(min, NP.F2I(w.players[0].y));
    }
    return y0 - min;
  }
  assert.strictEqual(altura(true), altura(false),
                     "soltar el boton ha cambiado el salto fijo");
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

/* --------------------------------------------------------------- agacharse */

prueba("agachado no se anda", function () {
  var w = mundo(suelo([[13, 3, "P"]]), { agachado: 5 });
  correr(w, 30);
  var x = w.players[0].x;
  correr(w, 30, NP.IN.DOWN | NP.IN.RIGHT);
  assert.strictEqual(w.players[0].crouch, 1, "no se ha agachado");
  assert.strictEqual(w.players[0].x, x, "agachado se ha movido");
  /* y al soltar abajo, vuelve a andar */
  correr(w, 30, NP.IN.RIGHT);
  assert.strictEqual(w.players[0].crouch, 0, "sigue agachado");
  assert.ok(w.players[0].x > x, "levantado no anda");
});

prueba("agachado no se salta", function () {
  var w = mundo(suelo([[13, 3, "P"]]), { agachado: 5 });
  correr(w, 30);
  var y = w.players[0].y;
  correr(w, 20, NP.IN.DOWN | NP.IN.JUMP);
  assert.strictEqual(w.players[0].y, y, "agachado ha saltado");
  /* el salto va por flanco: se suelta todo y se vuelve a pulsar */
  correr(w, 2, 0);
  correr(w, 6, NP.IN.JUMP);
  assert.ok(w.players[0].y < y, "de pie no salta");
});

prueba("agachado, lo que pasa por encima ya no toca", function () {
  /* Un volador que llega a la altura de la cabeza: de pie te da y agachado
     -seis pixeles mas bajo- te pasa por encima. Es para lo que sirve
     agacharse, y sin la caja mas baja las dos partidas saldrian iguales. */
  function partida(input) {
    var w = mundo(suelo([[13, 3, "P"], [12, 14, "v"]]),
                  { boxH: 20, agachado: 6, health: 3 });
    w.data.enemies[1].amplitude = 0;    /* que venga recto, sin ondular */
    correr(w, 4);                       /* que aterrice: agachado es de suelo */
    w.entities[0].facing = 0;           /* y que venga hacia el jugador */
    correr(w, 400, input);
    return w.players[0].health;
  }
  assert.ok(partida(0) < 3, "de pie el volador no le da");
  assert.strictEqual(partida(NP.IN.DOWN), 3, "agachado le sigue dando");
});

prueba("agachado, el golpe sale por abajo", function () {
  var w = mundo(suelo([[13, 3, "P"]]),
                { ataque: "golpe", latigo: 1, duracion: 10, alcance: 20 });
  correr(w, 20);
  var arriba = w.players[0].y;
  correr(w, 2, NP.IN.ACTION);
  var latigo = w.entities.filter(function (e) { return e.active && e.kind === 6; });
  assert.strictEqual(latigo.length, 1, "no sale el latigo");
  assert.strictEqual(latigo[0].y, arriba, "de pie el latigo no sale a su altura");

  var v = mundo(suelo([[13, 3, "P"]]),
                { ataque: "golpe", latigo: 1, duracion: 10, alcance: 20,
                  agachado: 5 });
  correr(v, 20, NP.IN.DOWN);
  correr(v, 2, NP.IN.DOWN | NP.IN.ACTION);
  var bajo = v.entities.filter(function (e) { return e.active && e.kind === 6; });
  assert.strictEqual(bajo.length, 1, "agachado no sale el latigo");
  assert.strictEqual(bajo[0].y, v.players[0].y + 5 * F,
    "agachado el latigo no baja los cinco pixeles de la caja");
});

prueba("sin 'agachado' el boton de abajo no agacha a nadie", function () {
  var w = mundo(suelo([[13, 3, "P"]]));
  correr(w, 30);
  var x = w.players[0].x;
  correr(w, 30, NP.IN.DOWN | NP.IN.RIGHT);
  assert.strictEqual(w.players[0].crouch, 0, "se agacha sin poder");
  assert.ok(w.players[0].x > x, "no anda con abajo pulsado");
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

/* Un perseguidor va detras del jugador mire donde mire, asi que con un agujero
   por medio se tiraba por el y se perdia. Si el que se cae es el jefe, el nivel
   no se puede terminar y no hay nada en pantalla que lo explique. */
prueba("el perseguidor se planta en el borde en vez de tirarse", function () {
  var filas = suelo([[13, 14, "J"], [13, 3, "P"]]);
  filas[14] = "#".repeat(8) + "....." + "#".repeat(11);   // agujero de x=8 a x=12
  var w = mundo(filas, { jefePersigue: true, jefeRango: 300 });
  var jefe = w.entities[0];
  var x0 = NP.F2I(jefe.x);
  for (var i = 0; i < 600; i++) {
    w.step(0);
    assert.ok(jefe.active, "el jefe se ha caido por el agujero en el frame " + i);
  }
  var x1 = NP.F2I(jefe.x);
  assert.ok(x1 < x0, "el jefe no se ha movido hacia el jugador: " + x0 + " -> " + x1);
  assert.ok(x1 >= 13 * 16 - 8 && x1 <= 13 * 16 + 2,
            "el jefe no se ha parado en el borde del agujero: x=" + x1);
});

prueba("con 'borde: no' el perseguidor si se tira", function () {
  var filas = suelo([[13, 14, "J"], [13, 3, "P"]]);
  filas[14] = "#".repeat(8) + "....." + "#".repeat(11);
  var w = mundo(filas, { jefePersigue: true, jefeRango: 300, jefeBorde: 0 });
  var jefe = w.entities[0], caido = false;
  for (var i = 0; i < 600 && !caido; i++) { w.step(0); caido = !jefe.active; }
  assert.ok(caido, "'borde: no' ya no deja que el enemigo se tire");
});

/* Que cancion toca en cada momento lo decide el motor (musicaAhora, y
   np_music_now en C), no cada maquina: las seis tenian la misma linea copiada
   y una cancion nueva habia que anadirla seis veces. */
prueba("en el titulo suena la del titulo y jugando la del nivel", function () {
  var datos_ = datos(suelo([[13, 3, "P"]]), { musicaNivel: 2, musicaTitulo: 5 });
  var w = NP.create(datos_);
  assert.strictEqual(w.musicaAhora(), 5, "en el titulo no suena la del titulo");
  w.step(NP.IN.START);
  assert.strictEqual(w.musicaAhora(), 2, "jugando no suena la del nivel");
});

prueba("sin musica de titulo, el titulo es mudo", function () {
  var w = NP.create(datos(suelo([[13, 3, "P"]]), { musicaNivel: 2 }));
  assert.strictEqual(w.musicaAhora(), 0);
});

prueba("con el jefe en pantalla manda la del jefe", function () {
  var filas = suelo([[13, 3, "P"], [13, 8, "J"]]);
  var w = mundo(filas, { musicaNivel: 2, musicaJefe: 7, bossHealth: 1 });
  correr(w, 2);
  assert.strictEqual(w.musicaAhora(), 7, "con jefe no suena la suya");
  /* al matarlo vuelve la del nivel; el nivel se acaba, asi que se mira antes */
  w.bossMax = 0;
  assert.strictEqual(w.musicaAhora(), 2, "muerto el jefe no vuelve la del nivel");
});

prueba("sin musica de jefe sigue la del nivel", function () {
  var filas = suelo([[13, 3, "P"], [13, 8, "J"]]);
  var w = mundo(filas, { musicaNivel: 2, bossHealth: 1 });
  correr(w, 2);
  assert.ok(w.bossMax > 0, "el jefe no esta en pantalla");
  assert.strictEqual(w.musicaAhora(), 2);
});

prueba("fuera de la partida no suena nada", function () {
  var w = mundo(suelo([[13, 3, "P"]]), { musicaNivel: 2, musicaTitulo: 5 });
  w.state = NP.STATE.GAME_OVER;
  assert.strictEqual(w.musicaAhora(), 0, "en el game over sigue sonando algo");
});

/* --------------------------------------------------- los prisioneros */
/*
 * El rehen atado de Guerrilla War: si lo tocas se suelta y suma; si le pegas
 * un tiro, se acabo. Es el unico actor del kit al que no hay que dispararle, y
 * eso es lo que obliga a mirar antes de disparar.
 */

function primerRehen(w) {
  for (var i = 0; i < w.entityCount; i++)
    if (w.entities[i].active && w.entities[i].kind === 8) return w.entities[i];
  return null;
}

prueba("tocar a un prisionero lo suelta y suma puntos", function () {
  var w = mundo(suelo([[13, 3, "P"], [13, 6, "R"]]));
  var rehen = primerRehen(w);
  assert.ok(rehen, "no ha salido el prisionero");
  assert.strictEqual(rehen.timer, 0, "no empieza atado");
  assert.strictEqual(w.score, 0);
  correr(w, 60, NP.IN.RIGHT);
  assert.ok(w.score >= 500, "soltarlo no ha sumado: " + w.score);
  assert.ok(rehen.timer > 0, "sigue atado despues de tocarlo");
});

prueba("el prisionero suelto echa a correr y se pierde de vista", function () {
  var w = mundo(suelo([[13, 3, "P"], [13, 6, "R"]]), { rehenEscape: 40 });
  var rehen = primerRehen(w);
  correr(w, 60, NP.IN.RIGHT);
  assert.ok(rehen.vx !== 0, "no ha echado a correr");
  correr(w, 60);
  assert.ok(!rehen.active, "no se ha ido");
});

prueba("solo suma una vez, por mucho que lo toques", function () {
  var w = mundo(suelo([[13, 3, "P"], [13, 6, "R"]]), { rehenEscape: 600 });
  correr(w, 90, NP.IN.RIGHT);
  var puntos = w.score;
  correr(w, 120, NP.IN.RIGHT);
  assert.strictEqual(w.score, puntos, "ha vuelto a sumar al tocarlo otra vez");
});

prueba("dispararle a un prisionero lo pierde y no suma", function () {
  var w = mundo(suelo([[13, 3, "P"], [13, 8, "R"]]), { ataque: "disparo" });
  var rehen = primerRehen(w);
  w.step(NP.IN.ACTION);
  correr(w, 90);
  assert.ok(!rehen.active, "el tiro no se lo ha llevado por delante");
  assert.strictEqual(w.score, 0, "dispararle ha sumado puntos");
});

prueba("un prisionero ya suelto no lo mata tu propio tiro", function () {
  /* Ya corre: el tiro que sale detras no tiene que castigarte otra vez. */
  var w = mundo(suelo([[13, 3, "P"], [13, 5, "R"]]),
                { ataque: "disparo", rehenEscape: 600 });
  correr(w, 40, NP.IN.RIGHT);
  var rehen = primerRehen(w);
  assert.ok(rehen && rehen.timer > 0, "no se ha soltado");
  w.step(NP.IN.ACTION);
  correr(w, 20);
  assert.ok(rehen.active, "el tiro se ha llevado a un prisionero ya suelto");
});

/* ------------------------------------------ enemigos que te disparan */
/*
 * Con `dispara:` un enemigo deja de ser un obstaculo que esquivar y pasa a ser
 * una amenaza a distancia. Es lo que separa un plataformas de un juego de
 * comando, asi que se comprueba que sale el tiro, que vuela hacia el jugador,
 * que hace dano y que respeta su cadencia y su alcance.
 */

function primerTiro(w) {
  for (var i = 0; i < w.entityCount; i++)
    if (w.entities[i].active && w.entities[i].kind === 7) return w.entities[i];
  return null;
}

prueba("un enemigo con 'dispara:' saca un tiro", function () {
  var w = mundo(suelo([[13, 3, "P"], [13, 10, "e"]]), { dispara: true });
  assert.ok(!primerTiro(w), "ya habia un tiro antes de tiempo");
  correr(w, 40);
  var tiro = primerTiro(w);
  assert.ok(tiro, "el enemigo no ha disparado");
  assert.ok(tiro.vx < 0, "el tiro no va hacia el jugador: vx=" + tiro.vx);
});

prueba("sin 'dispara:' el enemigo no tira nada", function () {
  var w = mundo(suelo([[13, 3, "P"], [13, 10, "e"]]));
  correr(w, 200);
  assert.ok(!primerTiro(w), "ha salido un tiro de un enemigo que no dispara");
});

prueba("el tiro del enemigo hace dano al jugador", function () {
  var w = mundo(suelo([[13, 3, "P"], [13, 10, "e"]]),
                { dispara: true, vida: 3, tiroVelocidad: 3 });
  var salud = w.players[0].health;
  for (var i = 0; i < 300 && w.players[0].health === salud; i++) w.step(0);
  assert.ok(w.players[0].health < salud,
            "el tiro no ha hecho dano en 300 frames");
});

prueba("el tiro se para en las paredes", function () {
  var filas = suelo([[13, 3, "P"], [13, 10, "e"]]);
  filas[13] = filas[13].substring(0, 7) + "#" + filas[13].substring(8);
  var w = mundo(filas, { dispara: true, vida: 3 });
  var salud = w.players[0].health;
  correr(w, 300);
  assert.strictEqual(w.players[0].health, salud,
                     "el tiro ha atravesado la pared");
});

prueba("el enemigo respeta su cadencia", function () {
  var w = mundo(suelo([[13, 3, "P"], [13, 10, "e"]]),
                { dispara: true, tiroEspera: 120, tiroVelocidad: 1 });
  correr(w, 60);
  var cuantos = 0;
  for (var i = 0; i < w.entityCount; i++)
    if (w.entities[i].active && w.entities[i].kind === 7) cuantos++;
  assert.strictEqual(cuantos, 1,
                     "con espera de 120 frames ha sacado " + cuantos + " tiros");
});

prueba("desde lejos no dispara", function () {
  var w = mundo(suelo([[13, 1, "P"], [13, 22, "e"]]),
                { dispara: true, tiroAlcance: 40 });
  correr(w, 200);
  assert.ok(!primerTiro(w), "ha disparado desde fuera de su alcance");
});

prueba("mirando desde arriba el enemigo te apunta a ti", function () {
  /* Un soldado de un juego de comando te tira **a ti**: si solo tirase de
     lado, bastaria con ponerse encima o debajo y ya no dan. */
  var w = mundo(suelo([[4, 10, "P"], [12, 10, "e"]]),
                { dispara: true, cenital: true, tiroAlcance: 300 });
  correr(w, 40);
  var tiro = primerTiro(w);
  assert.ok(tiro, "no ha disparado");
  assert.ok(tiro.vy < 0, "el tiro no sube hacia el jugador: vy=" + tiro.vy);
});

/* ------------------------------------------------------- vista cenital */
/*
 * Con `vista: cenital` el juego se mira desde arriba: no hay gravedad ni
 * suelo, se anda en ocho direcciones y se dispara hacia donde se mira. Es lo
 * que hace falta para un juego de comando (Ikari Warriors, Guerrilla War).
 */

prueba("desde arriba no hay gravedad: quieto se queda quieto", function () {
  var w = mundo(suelo([[6, 5, "P"]]), { cenital: true });
  var y = w.players[0].y;
  correr(w, 60);
  assert.strictEqual(w.players[0].y, y, "el jugador se ha caido");
  assert.strictEqual(w.players[0].vy, 0);
});

prueba("desde arriba se anda en las cuatro direcciones", function () {
  var casos = [[NP.IN.RIGHT, 1, 0], [NP.IN.LEFT, -1, 0],
               [NP.IN.DOWN, 0, 1], [NP.IN.UP, 0, -1]];
  casos.forEach(function (caso) {
    var w = mundo(suelo([[6, 8, "P"]]), { cenital: true });
    var x0 = NP.F2I(w.players[0].x), y0 = NP.F2I(w.players[0].y);
    correr(w, 30, caso[0]);
    var dx = NP.F2I(w.players[0].x) - x0, dy = NP.F2I(w.players[0].y) - y0;
    assert.strictEqual(Math.sign(dx), caso[1], "en x: " + dx);
    assert.strictEqual(Math.sign(dy), caso[2], "en y: " + dy);
  });
});

prueba("en diagonal no se va mas rapido que en recto", function () {
  /* Sin corregir la diagonal se iria un 41% mas rapido en diagonal que en
     recto, y entonces todo el mundo juega en diagonal. */
  var recto = mundo(suelo([[6, 8, "P"]]), { cenital: true });
  var x0 = NP.F2I(recto.players[0].x), y0 = NP.F2I(recto.players[0].y);
  correr(recto, 30, NP.IN.RIGHT);
  var solo = NP.F2I(recto.players[0].x) - x0;

  var diagonal = mundo(suelo([[6, 8, "P"]]), { cenital: true });
  correr(diagonal, 30, NP.IN.RIGHT | NP.IN.UP);
  var dx = NP.F2I(diagonal.players[0].x) - x0;
  var dy = NP.F2I(diagonal.players[0].y) - y0;
  var recorrido = Math.sqrt(dx * dx + dy * dy);
  assert.ok(dx < solo, "en diagonal avanza en x lo mismo que en recto");
  assert.ok(Math.abs(recorrido - solo) <= solo * 0.12,
            "en diagonal recorre " + recorrido.toFixed(1) + " y en recto " + solo);
});

prueba("desde arriba las paredes frenan tambien por arriba y por abajo",
       function () {
  var filas = suelo([[6, 8, "P"]]);
  filas[4] = "#".repeat(24);          // una pared entera por encima
  var w = mundo(filas, { cenital: true });
  correr(w, 60, NP.IN.UP);
  var arriba = NP.F2I(w.players[0].y);
  assert.ok(arriba >= 5 * 16,
            "se ha metido en la pared de arriba: y=" + arriba);
  correr(w, 120, NP.IN.DOWN);         // y por abajo, el borde del mapa
  var abajo = NP.F2I(w.players[0].y) + 14;
  assert.ok(abajo <= 15 * 16,
            "se ha salido del mapa por abajo: y=" + abajo);
});

prueba("desde arriba no se sale del mapa por abajo", function () {
  var w = mundo(suelo([[13, 8, "P"]]), { cenital: true });
  correr(w, 200, NP.IN.DOWN);
  assert.strictEqual(w.state, NP.STATE.PLAY,
                     "el jugador se ha caido del mapa y se ha muerto");
});

prueba("el disparo sale hacia donde se mira", function () {
  var casos = [[NP.IN.UP, 0, -1], [NP.IN.DOWN, 0, 1],
               [NP.IN.LEFT, -1, 0], [NP.IN.RIGHT, 1, 0]];
  casos.forEach(function (caso) {
    var w = mundo(suelo([[6, 8, "P"]]), { cenital: true, ataque: "disparo" });
    correr(w, 4, caso[0]);
    w.step(caso[0] | NP.IN.ACTION);
    var bala = null, i;
    for (i = 0; i < w.entityCount; i++)
      if (w.entities[i].active && w.entities[i].kind === 2) bala = w.entities[i];
    assert.ok(bala, "no ha salido ningun disparo");
    assert.strictEqual(Math.sign(bala.vx), caso[1], "vx: " + bala.vx);
    assert.strictEqual(Math.sign(bala.vy), caso[2], "vy: " + bala.vy);
  });
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

prueba("el objeto cambia el arma secundaria que se lleva", function () {
  /* dos armas: la 0 va recta y la 1 en arco. Se empieza con la 0 y el objeto
     'H' cambia a la 1, que es lo que hace un hacha en los clasicos */
  var w = mundo(suelo([[13, 4, "H"], [13, 2, "P"]]),
                { secundarias: ["recta", "arco"], subEspera: 4 });
  w.hearts = 20;
  assert.strictEqual(w.sub, 0, "no se empieza con la primera arma");
  correr(w, 60, NP.IN.RIGHT);
  assert.strictEqual(w.sub, 1, "coger el objeto no ha cambiado el arma");

  /* y lo que se tira ahora es la otra: en arco, o sea que baja */
  w.step(NP.IN.UP | NP.IN.ACTION);
  var tirada = null, i;
  for (i = 0; i < w.entityCount; i++)
    if (w.entities[i].active && w.entities[i].kind === 5) tirada = w.entities[i];
  assert.ok(tirada, "no sale nada al tirar");
  assert.strictEqual(tirada.def, 1, "sale con el arma de antes");
  var alto = tirada.y;
  correr(w, 40);
  assert.ok(tirada.y > alto, "la segunda arma no cae: no va en arco");
});

prueba("lo ya lanzado se queda con el arma con la que salio", function () {
  var w = mundo(suelo([[13, 4, "H"], [13, 2, "P"]]),
                { secundarias: ["recta", "arco"], subEspera: 4, subAlcance: 300 });
  w.hearts = 20;
  w.step(NP.IN.UP | NP.IN.ACTION);       /* una recta, antes de cambiar */
  var recta = null, i;
  for (i = 0; i < w.entityCount; i++)
    if (w.entities[i].active && w.entities[i].kind === 5) recta = w.entities[i];
  var alto = recta.y;
  correr(w, 50, NP.IN.RIGHT);            /* se coge el hacha por el camino */
  assert.strictEqual(w.sub, 1, "no se ha cambiado de arma");
  assert.strictEqual(recta.def, 0, "la tirada ha cambiado de arma en el aire");
  assert.strictEqual(recta.y, alto, "la que iba recta ha empezado a caer");
});

prueba("'a_la_vez' limita cuantas van por el aire", function () {
  function cuantas(tope) {
    var w = mundo(suelo([[13, 2, "P"]]),
                  { secundarias: ["recta"], subEspera: 1, subAlcance: 400,
                    subALaVez: [tope] });
    w.hearts = 90;
    for (var i = 0; i < 40; i++) w.step(i % 2 ? 0 : (NP.IN.UP | NP.IN.ACTION));
    var n = 0;
    for (i = 0; i < w.entityCount; i++)
      if (w.entities[i].active && w.entities[i].kind === 5) n++;
    return n;
  }
  assert.strictEqual(cuantas(1), 1, "con tope de una hay mas de una en el aire");
  assert.strictEqual(cuantas(3), 3, "con tope de tres no salen las tres");
  assert.ok(cuantas(0) > 3, "sin tope tendria que haber mas de tres");
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

/* ------------------------------------------- puntos de control */

/* El suelo de siempre con la antorcha en la columna 8 y unos pinchos en la 14:
   se sale de la 2, se pasa por la antorcha y se muere en los pinchos. */
function conAntorcha(extra) {
  return suelo([[13, 2, "P"], [13, 8, "!"], [13, 14, "^"]].concat(extra || []));
}

/* Corre hacia la derecha hasta que se pierde una vida (o se acaban los frames)
   y devuelve el jugador ya reaparecido. */
function morirYVolver(w) {
  var vidas = w.players[0].lives;
  for (var i = 0; i < 600 && w.players[0].lives === vidas; i++) w.step(NP.IN.RIGHT);
  for (var j = 0; j < 200 && w.state !== NP.STATE.PLAY; j++) w.step(0);
  return w.players[0];
}

prueba("la antorcha no estorba: se pasa por delante", function () {
  /* sin pinchos: aqui lo unico que se mira es que la casilla no frene ni haga
     dano, y unos pinchos mas adelante lo taparian */
  var w = mundo(suelo([[13, 2, "P"], [13, 8, "!"]]));
  var antes = NP.F2I(w.players[0].x);
  correr(w, 120, NP.IN.RIGHT);
  assert.ok(NP.F2I(w.players[0].x) > antes + 100,
            "la antorcha frena al jugador");
  assert.strictEqual(w.players[0].health, 1, "la antorcha hace dano");
});

prueba("pasar por la antorcha apunta su casilla", function () {
  var w = mundo(conAntorcha());
  assert.strictEqual(w.checkOn, 0, "empieza con un punto de control puesto");
  correr(w, 120, NP.IN.RIGHT);
  assert.strictEqual(w.checkOn, 1, "no se ha marcado el punto de control");
  assert.strictEqual(w.checkX, 8, "la columna marcada no es la de la antorcha");
  assert.strictEqual(w.checkY, 13, "la fila marcada no es la de la antorcha");
});

prueba("al morir se reaparece en la antorcha y no en la salida", function () {
  var w = mundo(conAntorcha(), { lives: 3 });
  var salida = w.level.start[0];
  var p = morirYVolver(w);
  assert.strictEqual(w.players[0].lives, 2, "no se ha perdido una vida");
  assert.strictEqual(w.state, NP.STATE.PLAY, "el nivel no ha vuelto a empezar");
  assert.ok(NP.F2I(p.x) > salida + 32, "se reaparece en la salida");
  assert.ok(Math.abs(NP.F2I(p.x) - 8 * 16) < 16,
            "se reaparece lejos de la antorcha: " + NP.F2I(p.x));
  assert.strictEqual(w.checkOn, 1, "reiniciar el nivel ha borrado la antorcha");
});

prueba("sin pasar por la antorcha se reaparece en la salida", function () {
  /* la misma prueba con la antorcha detras: si el motor la marcase sin
     tocarla, la de arriba pasaria sin comprobar nada */
  var w = mundo(suelo([[13, 2, "P"], [13, 0, "!"], [13, 14, "^"]]), { lives: 3 });
  var salida = w.level.start[0];
  var p = morirYVolver(w);
  assert.strictEqual(w.checkOn, 0, "se ha marcado una antorcha que no se toca");
  assert.strictEqual(NP.F2I(p.x), salida, "no se reaparece en la salida");
});

prueba("volver a pasar por la misma antorcha no vuelve a sonar", function () {
  var w = mundo(conAntorcha());
  var suena = 0, i;
  for (i = 0; i < 120; i++) { w.step(NP.IN.RIGHT); if (w.sfx & NP.SFX.CHECK) suena++; }
  assert.strictEqual(suena, 1, "la antorcha ha sonado " + suena + " veces");
  for (i = 0; i < 90; i++) { w.step(NP.IN.LEFT); if (w.sfx & NP.SFX.CHECK) suena++; }
  for (i = 0; i < 120; i++) { w.step(NP.IN.RIGHT); if (w.sfx & NP.SFX.CHECK) suena++; }
  assert.strictEqual(suena, 1, "la antorcha vuelve a sonar al repasarla");
});

prueba("manda la ultima antorcha por la que se pasa", function () {
  var w = mundo(suelo([[13, 2, "P"], [13, 6, "!"], [13, 12, "!"], [13, 18, "^"]]),
                { lives: 3 });
  correr(w, 50, NP.IN.RIGHT);
  assert.strictEqual(w.checkX, 6, "no se ha marcado la primera");
  correr(w, 90, NP.IN.RIGHT);
  assert.strictEqual(w.checkX, 12, "la segunda antorcha no releva a la primera");
  var p = morirYVolver(w);
  assert.ok(Math.abs(NP.F2I(p.x) - 12 * 16) < 16,
            "se reaparece en la primera antorcha, no en la ultima");
});

prueba("cargar el nivel a mano borra la antorcha", function () {
  var w = mundo(conAntorcha());
  correr(w, 120, NP.IN.RIGHT);
  assert.strictEqual(w.checkOn, 1);
  w.loadLevel(0);                 /* empezar un nivel es empezarlo de cero */
  assert.strictEqual(w.checkOn, 0, "el nivel nuevo hereda la antorcha");
  assert.strictEqual(NP.F2I(w.players[0].x), w.level.start[0],
                     "no se empieza en la salida del nivel");
});

/* ------------------------------------------- mejoras del arma */

/* El jugador en la columna 2 y un candelabro en la 4: con el alcance de serie
   (12 px) el latigo se queda corto y con una mejora (+12) llega. */
function conMejora(opciones) {
  var o = { ataque: "golpe", alcance: 12, mejoras: 2, alcanceMejora: 12,
            espera: 1, duracion: 6 };
  Object.keys(opciones || {}).forEach(function (k) { o[k] = opciones[k]; });
  return { filas: suelo([[13, 2, "P"], [13, 4, "V"]]), opciones: o };
}

function candelabroVivo(w) {
  for (var i = 0; i < w.entityCount; i++)
    if (w.entities[i].kind === 4 && w.entities[i].active) return true;
  return false;
}

prueba("el latigo de serie no llega al candelabro", function () {
  var c = conMejora();
  var w = mundo(c.filas, c.opciones);
  correr(w, 60, NP.IN.ACTION);
  assert.ok(candelabroVivo(w), "el latigo de serie ya llegaba: la prueba no vale");
});

prueba("con una mejora el latigo llega mas lejos", function () {
  var c = conMejora();
  var w = mundo(c.filas, c.opciones);
  w.players[0].power = 1;
  correr(w, 60, NP.IN.ACTION);
  assert.ok(!candelabroVivo(w), "la mejora no alarga el latigo");
});

prueba("una mejora de mas no alarga nada si el arma no las admite", function () {
  var c = conMejora({ mejoras: 0 });
  var w = mundo(c.filas, c.opciones);
  w.players[0].power = 5;
  correr(w, 60, NP.IN.ACTION);
  assert.ok(candelabroVivo(w), "el arma se alarga sin admitir mejoras");
});

prueba("recoger la mejora sube el nivel del arma", function () {
  var c = conMejora();
  var w = mundo(suelo([[13, 2, "P"], [13, 3, "M"], [13, 4, "V"]]), c.opciones);
  assert.strictEqual(w.players[0].power, 0);
  correr(w, 30, NP.IN.RIGHT);
  assert.strictEqual(w.players[0].power, 1, "recoger la mejora no ha subido nada");
});

prueba("las mejoras no pasan del tope del arma", function () {
  var c = conMejora({ mejoras: 1 });
  var w = mundo(suelo([[13, 2, "P"], [13, 3, "M"], [13, 5, "M"]]), c.opciones);
  correr(w, 90, NP.IN.RIGHT);
  assert.strictEqual(w.players[0].power, 1, "el arma se ha mejorado de mas");
});

prueba("morir devuelve el arma a como estaba", function () {
  var c = conMejora();
  var w = mundo(suelo([[13, 2, "P"], [13, 3, "M"], [13, 14, "^"]]),
                Object.assign({ lives: 3 }, c.opciones));
  correr(w, 30, NP.IN.RIGHT);
  assert.strictEqual(w.players[0].power, 1, "no se ha cogido la mejora");
  morirYVolver(w);
  assert.strictEqual(w.players[0].power, 0, "la mejora sobrevive a la muerte");
});

/* --------------------------------------- generadores de bichos (Gauntlet) */

/* El boton de accion dispara al **pulsarlo**, no mientras se aguanta: para
   soltar varios tiros hay que soltarlo entre uno y otro. */
function disparar(w, frames) {
  for (var i = 0; i < frames; i++) w.step(i % 2 ? NP.IN.ACTION : 0);
  return w;
}

function bichos(w) {
  var cuantos = 0;
  for (var i = 0; i < w.entityCount; i++) {
    var e = w.entities[i];
    if (e.active && e.kind === 0) cuantos++;
  }
  return cuantos;
}

function primerNido(w) {
  for (var i = 0; i < w.entityCount; i++) {
    if (w.entities[i].active && w.entities[i].kind === 9) return w.entities[i];
  }
  return null;
}

prueba("un generador saca bichos cada tantos frames", function () {
  var w = mundo(["......", "..N...", "P.....", "######"],
                { cenital: true, nidoCada: 30, nidoTope: 5 });
  assert.strictEqual(bichos(w), 0, "ha salido alguno antes de tiempo");
  correr(w, 29);
  assert.strictEqual(bichos(w), 0, "el primero ha salido antes de los 30 frames");
  correr(w, 1);
  assert.strictEqual(bichos(w), 1, "no ha salido el primero");
  correr(w, 30);
  assert.strictEqual(bichos(w), 2, "no ha salido el segundo");
});

prueba("el generador no pasa de su tope", function () {
  var w = mundo(["......", "..N...", "P.....", "######"],
                { cenital: true, nidoCada: 5, nidoTope: 2 });
  correr(w, 300);
  assert.strictEqual(bichos(w), 2, "se ha pasado del tope de dos");
});

prueba("a tiros el generador se acaba, y deja de sacar bichos", function () {
  var w = mundo(["......", "P.N...", "......", "######"],
                { cenital: true, ataque: "disparo", alcance: 96, espera: 4,
                  nidoCada: 40, nidoTope: 5, nidoVida: 2 });
  assert.ok(primerNido(w), "no hay generador");
  disparar(w, 80);
  assert.ok(!primerNido(w), "el generador aguanta mas de lo que dice su vida");
  var antes = bichos(w);
  correr(w, 200);
  assert.strictEqual(bichos(w), antes, "sigue sacando bichos despues de roto");
});

prueba("destruir un generador suma sus puntos", function () {
  var w = mundo(["......", "P.N...", "......", "######"],
                { cenital: true, ataque: "disparo", alcance: 96, espera: 4,
                  nidoCada: 400, nidoVida: 1 });
  disparar(w, 40);
  assert.strictEqual(w.score, 1000, "no ha sumado los puntos del generador");
});

prueba("el generador no hace dano al tocarlo", function () {
  /* En Gauntlet lo que mata son los bichos, no el nido: hay que poder
     pegarse a el para reventarlo de cerca. */
  var w = mundo(["......", "PN....", "......", "######"],
                { cenital: true, health: 5, nidoCada: 400 });
  correr(w, 60, NP.IN.RIGHT);
  assert.strictEqual(w.players[0].health, 5, "el nido le ha quitado vida");
});

/* ------------------------------------------ la pocima (Gauntlet) */

prueba("la pocima se lleva por delante lo que se ve", function () {
  var w = mundo(["..........", "P.o.e.e.e.", "..........", "##########"],
                { cenital: true, objetoEfecto: 7, objetoCantidad: 3 });
  assert.strictEqual(bichos(w), 3, "no hay tres bichos para empezar");
  correr(w, 60, NP.IN.RIGHT);
  assert.strictEqual(bichos(w), 0, "la pocima no se los ha llevado");
});

prueba("la pocima tambien revienta generadores", function () {
  var w = mundo(["..........", "P.o.N.....", "..........", "##########"],
                { cenital: true, objetoEfecto: 7, objetoCantidad: 5,
                  nidoVida: 3, nidoCada: 400 });
  assert.ok(primerNido(w), "no hay generador");
  correr(w, 60, NP.IN.RIGHT);
  assert.ok(!primerNido(w), "la pocima no se ha llevado el nido");
});

prueba("la pocima no llega a lo que esta fuera de pantalla", function () {
  /* Una pocima que limpiara el nivel entero se cargaria el juego: en
     Gauntlet se lleva lo que ves, y por eso hay que elegir cuando usarla. */
  var filas = ["", "", "", ""];
  for (var x = 0; x < 40; x++) {
    filas[0] += ".";
    filas[1] += (x === 0 ? "P" : (x === 2 ? "o" : (x === 38 ? "e" : ".")));
    filas[2] += ".";
    filas[3] += "#";
  }
  var w = mundo(filas, { cenital: true, objetoEfecto: 7, objetoCantidad: 3 });
  assert.strictEqual(bichos(w), 1, "no hay un bicho lejos");
  correr(w, 60, NP.IN.RIGHT);
  assert.strictEqual(bichos(w), 1, "se ha llevado uno que no se veia");
});

/* ------------------------------------------- el desgaste (Gauntlet) */

prueba("con desgaste, la vida se va sola", function () {
  var w = mundo(["....", "....", "P...", "####"], { health: 20, desgaste: 10 });
  correr(w, 9);
  assert.strictEqual(w.players[0].health, 20, "se ha ido antes de tiempo");
  correr(w, 1);
  assert.strictEqual(w.players[0].health, 19, "no se ha ido el primer punto");
  correr(w, 50);
  assert.strictEqual(w.players[0].health, 14, "no baja uno cada diez frames");
});

prueba("sin desgaste la vida no se mueve sola", function () {
  var w = mundo(["....", "....", "P...", "####"], { health: 5 });
  correr(w, 600);
  assert.strictEqual(w.players[0].health, 5, "ha bajado sin que nadie la toque");
});

prueba("el desgaste mata, y cuesta una vida", function () {
  var w = mundo(["....", "....", "P...", "####"],
                { health: 3, desgaste: 5, lives: 3 });
  correr(w, 15);
  assert.strictEqual(w.players[0].health, 0, "no ha llegado a cero");
  assert.strictEqual(w.state, NP.STATE.DYING, "no se esta muriendo");
  /* hasta que reaparece: el nivel vuelve a empezar */
  for (var i = 0; i < 400 && w.state !== NP.STATE.PLAY; i++) w.step(0);
  assert.strictEqual(w.state, NP.STATE.PLAY, "no ha vuelto a la partida");
  assert.strictEqual(w.players[0].lives, 2, "no ha costado una vida");
  assert.strictEqual(w.players[0].health, 3, "no ha vuelto con la vida entera");
});

prueba("la invulnerabilidad no para el desgaste", function () {
  /* Si el desgaste pasara por donde pasa un golpe, cada roce con un bicho
     dejaria la cuenta atras parada noventa frames. */
  var w = mundo(["....", "....", "P...", "####"], { health: 20, desgaste: 10 });
  w.players[0].invuln = 600;
  correr(w, 100);
  assert.strictEqual(w.players[0].health, 10,
                     "la invulnerabilidad ha parado la cuenta");
});

prueba("la comida devuelve vida contra el desgaste", function () {
  var w = mundo(["....", "....", "P.o.", "####"],
                { health: 60, desgaste: 4, objetoEfecto: 2, objetoCantidad: 20 });
  correr(w, 60);
  var antes = w.players[0].health;
  assert.ok(antes < 60, "no se ha gastado nada");
  correr(w, 40, NP.IN.RIGHT);
  assert.ok(w.players[0].health > antes,
            "coger la comida no ha devuelto vida (" + antes + " -> "
            + w.players[0].health + ")");
});

/* ------------------------------------ la vista de cinta (yo contra el barrio) */
/*
 * Con `vista: cinta` se anda por una franja de suelo en ocho direcciones, como
 * desde arriba, pero **se salta**: hay una tercera coordenada, la altura sobre
 * el suelo. Es lo que hace un Double Dragon, y lo que hay que comprobar es que
 * las tres se llevan bien: que se salta, que la altura no mueve el suelo por el
 * que se anda y que dos cosas a distinta profundidad no se tocan.
 */

prueba("en la cinta se anda en las cuatro direcciones", function () {
  var casos = [[NP.IN.RIGHT, 1, 0], [NP.IN.LEFT, -1, 0],
               [NP.IN.DOWN, 0, 1], [NP.IN.UP, 0, -1]];
  casos.forEach(function (caso) {
    var w = mundo(suelo([[6, 8, "P"]]), { cinta: true });
    var x0 = NP.F2I(w.players[0].x), y0 = NP.F2I(w.players[0].y);
    correr(w, 30, caso[0]);
    var dx = NP.F2I(w.players[0].x) - x0, dy = NP.F2I(w.players[0].y) - y0;
    assert.strictEqual(Math.sign(dx), caso[1], "en x: " + dx);
    assert.strictEqual(Math.sign(dy), caso[2], "en y: " + dy);
  });
});

prueba("en la cinta no hay gravedad en el suelo: quieto se queda quieto",
       function () {
  var w = mundo(suelo([[6, 5, "P"]]), { cinta: true });
  var y = w.players[0].y;
  correr(w, 60);
  assert.strictEqual(w.players[0].y, y, "el jugador se ha caido");
  assert.strictEqual(w.players[0].altura, 0);
});

prueba("en la cinta se salta y se vuelve al mismo sitio", function () {
  var w = mundo(suelo([[6, 8, "P"]]), { cinta: true });
  var y0 = w.players[0].y;
  w.step(NP.IN.JUMP);
  assert.ok(w.players[0].altura > 0, "no ha despegado");
  assert.strictEqual(w.players[0].onGround, 0);
  var maximo = 0;
  for (var i = 0; i < 60; i++) {
    w.step(0);
    if (w.players[0].altura > maximo) maximo = w.players[0].altura;
  }
  assert.ok(NP.F2I(maximo) > 16, "el salto sube " + NP.F2I(maximo) + " pixeles");
  assert.strictEqual(w.players[0].altura, 0, "no ha vuelto al suelo");
  assert.strictEqual(w.players[0].onGround, 1);
  assert.strictEqual(w.players[0].y, y0, "ha acabado en otra fila del suelo");
});

prueba("saltando se sube el dibujo, no la fila por la que se anda", function () {
  /* Es la regla de la vista: `y` es donde se dibuja y la linea del suelo es
     y + altura. Si el salto moviera el suelo, saltar seria andar hacia
     arriba y se colaria uno por encima de las paredes. */
  var w = mundo(suelo([[6, 8, "P"]]), { cinta: true });
  var suelo0 = w.players[0].y + w.players[0].altura;
  w.step(NP.IN.JUMP);
  correr(w, 10);
  var p = w.players[0];
  assert.ok(p.altura > 0, "no esta en el aire");
  assert.ok(p.y < suelo0, "el dibujo no ha subido");
  assert.strictEqual(p.y + p.altura, suelo0, "el suelo se ha movido con el salto");
});

prueba("saltando no se atraviesan las paredes", function () {
  var filas = suelo([[6, 8, "P"]]);
  filas[4] = "#".repeat(24);          // una pared entera por encima
  var w = mundo(filas, { cinta: true });
  w.step(NP.IN.JUMP);
  correr(w, 40, NP.IN.UP);            // saltando y empujando contra la pared
  var p = w.players[0];
  assert.ok(NP.F2I(p.y + p.altura) >= 5 * 16,
            "se ha colado en la pared: suelo=" + NP.F2I(p.y + p.altura));
});

prueba("en la cinta el mando no manda en el aire", function () {
  /* En estos juegos no se cambia de idea a medio salto: el impulso con el que
     saltas es el que te lleva hasta caer. */
  var w = mundo(suelo([[6, 8, "P"]]), { cinta: true });
  w.step(NP.IN.JUMP);                 // salto sin correr: sale recto
  var x0 = NP.F2I(w.players[0].x);
  for (var i = 0; i < 40 && !w.players[0].onGround; i++) w.step(NP.IN.RIGHT);
  assert.strictEqual(NP.F2I(w.players[0].x), x0,
                     "se ha movido en el aire");
});

prueba("el dano se recibe con los pies en el suelo, no por el aire", function () {
  /* La prueba de que las cajas hacen de profundidad **y** de altura a la vez:
     saltando por encima del enemigo no te toca, y el golpe llega justo cuando
     aterrizas al otro lado. Si la altura no contara, el toque seria el mismo
     que andando y llegaria a mitad del salto. */
  var w = mundo(suelo([[8, 6, "P"], [8, 9, "e"]]),
                { cinta: true, health: 99, aturdido: 0 });
  var p = w.players[0];
  var previa = p.health, golpes = [], porElAire = 0;
  w.step(NP.IN.RIGHT | NP.IN.JUMP);        // se salta hacia el
  for (var i = 0; i < 60; i++) {
    w.step(NP.IN.RIGHT);
    /* la altura se mira **despues** del paso: los toques se comprueban al
       final del frame, con la altura que haya quedado */
    if (p.health < previa) {
      golpes.push(NP.F2I(p.altura));
      if (p.altura > 0) porElAire++;
    }
    previa = p.health;
  }
  assert.ok(golpes.length > 0, "no le toca nunca: la prueba no vale");
  assert.strictEqual(porElAire, 0,
                     "le ha dado por el aire, a alturas " + golpes.join(", "));
});

/* --------------------------------- la serie de golpes (Double Dragon) */
/*
 * Un juego de tortas no va de apretar el boton, va de encadenar: puno, puno y
 * remate. El ultimo pega mas fuerte y **tumba**, y mientras el matón esta en el
 * suelo ni decide ni hace dano. Sin eso, pegar es machacar el boton.
 */

/** Pega `cuantos` golpes seguidos, soltando el boton entre uno y otro (el
    ataque va por flanco) y esperando la cadencia. */
function pegar(w, cuantos, espera) {
  var quedan = espera === undefined ? 10 : espera;
  for (var i = 0; i < cuantos; i++) {
    w.step(NP.IN.ACTION);
    /* Los frames de la **parada del impacto** no cuentan: lo que se mide aqui
       es el ritmo del juego, y durante la parada el juego no corre. Sin esto,
       cada golpe que acierta se comeria cuatro frames de la espera y la serie
       se cortaria sola aunque el mando fuera perfecto. */
    for (var f = 0; f < quedan; f++) {
      w.step(0);
      if (w.congelado) f--;
    }
  }
  return w;
}

prueba("los golpes se encadenan mientras dura la ventana", function () {
  var w = mundo(suelo([[8, 6, "P"]]),
                { cinta: true, ataque: "golpe", combo: 3, ventana: 40,
                  espera: 6, alcance: 20 });
  var p = w.players[0];
  assert.strictEqual(p.comboLink, 0);
  w.step(NP.IN.ACTION);
  assert.strictEqual(p.comboLink, 0, "el primero es el primero");
  correr(w, 8); w.step(NP.IN.ACTION);
  assert.strictEqual(p.comboLink, 1, "el segundo no encadena");
  correr(w, 8); w.step(NP.IN.ACTION);
  assert.strictEqual(p.comboLink, 2, "el tercero no encadena");
  /* y el cuarto vuelve a empezar la serie */
  correr(w, 8); w.step(NP.IN.ACTION);
  assert.strictEqual(p.comboLink, 0, "la serie no vuelve a empezar");
});

prueba("si te duermes, la serie se corta", function () {
  var w = mundo(suelo([[8, 6, "P"]]),
                { cinta: true, ataque: "golpe", combo: 3, ventana: 12,
                  espera: 6, alcance: 20 });
  var p = w.players[0];
  w.step(NP.IN.ACTION);
  correr(w, 8); w.step(NP.IN.ACTION);
  assert.strictEqual(p.comboLink, 1, "no ha encadenado el segundo");
  correr(w, 30);                      // se pasa la ventana entera
  w.step(NP.IN.ACTION);
  assert.strictEqual(p.comboLink, 0, "ha encadenado fuera de la ventana");
});

prueba("el remate hace mas dano que los demas golpes", function () {
  function golpes(hasta) {
    var w = mundo(suelo([[8, 6, "P"], [8, 8, "e"]]),
                  { cinta: true, ataque: "golpe", combo: 3, ventana: 40,
                    espera: 6, alcance: 24, dano: 1, danoRemate: 5,
                    vidaEnemigo: 20, velocidadEnemigo: 0 });
    pegar(w, hasta, 8);
    return w.entities[0].health;
  }
  var trasUno = golpes(1), trasTres = golpes(3);
  assert.strictEqual(20 - trasUno, 1, "el primero no hace 1 de dano");
  assert.strictEqual(20 - trasTres, 1 + 1 + 5,
                     "los tres golpes hacen " + (20 - trasTres) + " y no 7");
});

prueba("el remate tumba al que lo cobra", function () {
  var w = mundo(suelo([[8, 6, "P"], [8, 8, "e"]]),
                { cinta: true, ataque: "golpe", combo: 3, ventana: 40,
                  espera: 6, alcance: 24, dano: 1, danoRemate: 2,
                  derribo: 40, empujonRemate: 3, vidaEnemigo: 20,
                  velocidadEnemigo: 0 });
  var e = w.entities[0];
  var x0 = NP.F2I(e.x);
  pegar(w, 2, 8);
  assert.strictEqual(e.knock, 0, "un golpe normal ya tumba");
  pegar(w, 1, 8);
  assert.ok(e.knock > 0, "el remate no ha tumbado a nadie");
  var mirando = w.players[0].facing;
  correr(w, 10);
  assert.ok(mirando ? NP.F2I(e.x) > x0 : NP.F2I(e.x) < x0,
            "no ha salido despedido: x=" + NP.F2I(e.x) + " y salio de " + x0);
});

prueba("uno tumbado no hace dano al tocarlo", function () {
  var w = mundo(suelo([[8, 6, "P"], [8, 8, "e"]]),
                { cinta: true, ataque: "golpe", combo: 3, ventana: 40,
                  espera: 6, alcance: 24, dano: 1, danoRemate: 2,
                  derribo: 120, empujonRemate: 0, vidaEnemigo: 20,
                  velocidadEnemigo: 0, health: 9, aturdido: 0 });
  var e = w.entities[0], p = w.players[0];
  pegar(w, 3, 8);
  assert.ok(e.knock > 0, "el remate no ha tumbado a nadie");
  var salud = p.health;
  correr(w, 60, NP.IN.RIGHT);         // se le anda por encima
  assert.strictEqual(p.health, salud,
                     "el que esta en el suelo sigue haciendo dano");
});

/* ------------------------------------------- el agarre (Double Dragon) */
/*
 * Pegar, coger y rematar: la escalera entera de un juego de tortas. Al que se
 * tambalea de un golpe se le agarra tocandolo, y ahi se decide entre
 * zarandearlo a rodillazos o lanzarlo por encima del hombro.
 */

/** Un mundo de tortas con un matón quieto al lado, ya agarrado. */
function conAgarre(opciones) {
  var base = { cinta: true, ataque: "golpe", espera: 6, alcance: 24, dano: 1,
               vidaEnemigo: 20, velocidadEnemigo: 0, agarre: 90,
               health: 9, aturdido: 0 };
  for (var k in (opciones || {})) base[k] = opciones[k];
  var w = mundo(suelo([[8, 6, "P"], [8, 8, "e"]]), base);
  w.step(NP.IN.ACTION);          // un golpe: se queda tambaleando
  /* y se le va a tocar: son dos casillas, o sea unos catorce frames andando,
     y el tambaleo dura veinte */
  for (var i = 0; i < 20 && !w.players[0].grab; i++) w.step(NP.IN.RIGHT);
  return w;
}

prueba("al que se tambalea se le agarra tocandolo", function () {
  var w = conAgarre();
  assert.ok(w.players[0].grab > 0, "no lo ha agarrado");
  assert.strictEqual(w.players[0].grab - 1, 0, "ha agarrado a otro");
});

prueba("agarrado no se anda ni se va solo", function () {
  var w = conAgarre();
  var e = w.entities[0], p = w.players[0];
  var x0 = NP.F2I(p.x);
  correr(w, 20, NP.IN.RIGHT);
  assert.ok(w.players[0].grab > 0, "se ha soltado antes de tiempo");
  assert.strictEqual(NP.F2I(p.x), x0, "el jugador anda con uno agarrado");
  /* y lo lleva pegado al costado por el que mira */
  assert.ok(NP.F2I(e.x) > NP.F2I(p.x), "no lo lleva por delante");
  assert.ok(NP.F2I(e.x) - NP.F2I(p.x) < 20, "lo lleva demasiado lejos");
});

prueba("el rodillazo hace dano sin soltarlo", function () {
  var w = conAgarre({ rodillazo: 3 });
  var e = w.entities[0];
  var antes = e.health;
  w.step(NP.IN.ACTION);
  correr(w, 8);
  assert.strictEqual(antes - e.health, 3, "el rodillazo no hace 3 de dano");
  assert.ok(w.players[0].grab > 0, "el rodillazo lo suelta");
});

prueba("agarrado se le acaba soltando", function () {
  var w = conAgarre({ agarre: 20 });
  assert.ok(w.players[0].grab > 0, "no lo ha agarrado");
  correr(w, 40);
  assert.strictEqual(w.players[0].grab, 0, "no se suelta nunca");
});

prueba("lanzarlo lo manda por el aire y cae derribado", function () {
  var w = conAgarre({ danoLanzar: 4, fuerzaLanzar: 4 });
  var e = w.entities[0], p = w.players[0];
  var antes = e.health, x0 = NP.F2I(e.x), mirando = p.facing;
  w.step(NP.IN.JUMP);
  assert.strictEqual(p.grab, 0, "sigue agarrado despues de lanzarlo");
  assert.strictEqual(antes - e.health, 4, "el estrellon no hace 4 de dano");
  assert.ok(e.knock > 0, "no cae derribado");
  /* vuela: sube y vuelve a bajar */
  var arriba = 0;
  for (var i = 0; i < 60; i++) {
    correr(w, 1);
    if (e.altura > arriba) arriba = e.altura;
  }
  assert.ok(NP.F2I(arriba) > 8, "no ha volado: subio " + NP.F2I(arriba));
  assert.strictEqual(e.altura, 0, "no ha vuelto al suelo");
  assert.ok(mirando ? NP.F2I(e.x) > x0 + 16 : NP.F2I(e.x) < x0 - 16,
            "no ha salido despedido: de " + x0 + " a " + NP.F2I(e.x));
});

prueba("sin `agarre:` se cobra al tocarlo, como en cualquier otro juego",
       function () {
  /* El control de todo lo de arriba: el mismo acercamiento sin el bloque de
     agarre no agarra a nadie y cuesta un golpe, que es lo de siempre. */
  var con = conAgarre();
  var sin = conAgarre({ agarre: 0 });
  assert.ok(con.players[0].grab > 0, "con agarre no ha agarrado");
  assert.strictEqual(sin.players[0].grab, 0, "agarra sin llevar agarre");
  assert.strictEqual(con.players[0].health, 9,
                     "agarrando tambien se cobra el golpe");
  assert.ok(sin.players[0].health < 9,
            "sin agarre el enemigo no hace dano al tocarlo");
});

/* ------------------------------------ el orden de dibujo por profundidad */

prueba("en la cinta se dibuja de mas lejos a mas cerca", function () {
  /* En un juego donde todo el mundo se pisa, el que esta detras tiene que
     pintarse antes. El motor da el orden y las siete maquinas lo siguen. */
  var w = mundo(suelo([[7, 6, "e"], [10, 8, "e"], [8, 12, "e"], [9, 4, "P"]]),
                { cinta: true, velocidadEnemigo: 0 });
  var orden = w.ordenDibujo();
  var suelos = orden.map(function (i) {
    var e = w.entities[i];
    return e.y + e.altura;
  });
  for (var i = 1; i < suelos.length; i++)
    assert.ok(suelos[i] >= suelos[i - 1],
              "el de la fila " + suelos[i] + " se pinta despues del "
              + suelos[i - 1]);
  assert.strictEqual(orden.length, 3, "no salen las tres entidades");
});

prueba("fuera de la cinta el orden es el de la lista", function () {
  /* Ordenar en los demas generos costaria ciclos en la consola sin arreglar
     nada: alli no hay un "detras". */
  var w = mundo(suelo([[7, 6, "e"], [10, 8, "e"], [8, 12, "e"], [12, 4, "P"]]));
  assert.deepStrictEqual(w.ordenDibujo(), [0, 1, 2]);
});

/* --------------------------- el cerrojo de la camara (Final Fight) */
/*
 * Lo que convierte un pasillo en una pelea: mientras quede alguien vivo en la
 * pantalla, la camara no pasa de ahi. Sin esto, un juego de tortas se termina
 * andando hacia la derecha sin pegar a nadie.
 */

prueba("con alguien en pantalla la camara no avanza", function () {
  var filas = [];
  for (var y = 0; y < 14; y++) filas.push(".".repeat(60));
  filas.push("#".repeat(60));
  filas[8] = filas[8].substring(0, 2) + "P" + filas[8].substring(3);
  filas[8] = filas[8].substring(0, 12) + "e" + filas[8].substring(13);
  var w = mundo(filas, { cinta: true, velocidadEnemigo: 0, health: 99,
                         aturdido: 0 });
  correr(w, 200, NP.IN.RIGHT);
  var conBicho = w.camX;
  assert.strictEqual(conBicho, 0, "la camara ha avanzado con el bicho vivo");
  /* se lo quita de en medio y entonces si */
  w.entities[0].active = 0;
  correr(w, 200, NP.IN.RIGHT);
  assert.ok(w.camX > conBicho,
            "sin nadie en pantalla la camara sigue clavada");
});

prueba("el cerrojo es solo de la vista de cinta", function () {
  /* En los otros generos la camara sigue al jugador pase lo que pase: si el
     cerrojo se colara ahi, un enemigo cualquiera pararia el scroll. */
  var filas = [];
  for (var y = 0; y < 14; y++) filas.push(".".repeat(60));
  filas.push("#".repeat(60));
  filas[8] = filas[8].substring(0, 2) + "P" + filas[8].substring(3);
  filas[8] = filas[8].substring(0, 12) + "e" + filas[8].substring(13);
  var w = mundo(filas, { cenital: true, velocidadEnemigo: 0, health: 99,
                         aturdido: 0 });
  correr(w, 200, NP.IN.RIGHT);
  assert.ok(w.camX > 0, "la camara no avanza en un juego cenital");
});

/* ----------------------------------------- la bolsa (aventuras tipo Dizzy) */
/*
 * En una aventura lo que te para no es un bicho: es una puerta cerrada y la
 * llave esta tres pantallas atras. Se llevan tres cosas a la vez, se cogen
 * tocandolas y se sueltan con el boton, y elegir **que** llevas encima es
 * medio juego.
 */

prueba("los objetos de llevar se guardan en la bolsa", function () {
  var w = mundo(suelo([[13, 6, "P"], [13, 8, "1"]]), { bolsa: true });
  correr(w, 60, NP.IN.RIGHT);
  assert.deepStrictEqual(w.bolsa, [6, 0, 0], "no lo lleva encima");
  assert.strictEqual(w.bolsaCuantos(), 1);
});

prueba("la bolsa se llena y el cuarto objeto se queda en el suelo", function () {
  var w = mundo(suelo([[13, 4, "P"], [13, 6, "1"], [13, 8, "2"], [13, 10, "3"]]),
                { bolsa: true });
  correr(w, 120, NP.IN.RIGHT);
  assert.strictEqual(w.bolsaCuantos(), 3, "no ha cogido las tres");
  /* y ahora una cuarta cosa: no cabe */
  var libres = 0;
  for (var i = 0; i < w.entityCount; i++) if (w.entities[i].active) libres++;
  assert.strictEqual(libres, 0, "queda algo por el suelo y cabia");

  var lleno = mundo(suelo([[13, 4, "P"], [13, 6, "1"], [13, 8, "2"],
                           [13, 10, "3"], [13, 12, "1"]]), { bolsa: true });
  correr(lleno, 160, NP.IN.RIGHT);
  assert.strictEqual(lleno.bolsaCuantos(), 3, "lleva mas de tres cosas");
  var enElSuelo = 0;
  for (var k = 0; k < lleno.entityCount; k++)
    if (lleno.entities[k].active) enElSuelo++;
  assert.strictEqual(enElSuelo, 1,
                     "el que no cabia no se ha quedado en el suelo");
});

prueba("el boton suelta lo primero de la bolsa", function () {
  var w = mundo(suelo([[13, 4, "P"], [13, 6, "1"], [13, 8, "2"]]),
                { bolsa: true });
  correr(w, 90, NP.IN.RIGHT);
  assert.deepStrictEqual(w.bolsa, [6, 7, 0]);
  w.step(NP.IN.ACTION);
  assert.deepStrictEqual(w.bolsa, [7, 0, 0], "no ha soltado el primero");
  /* y esta en el suelo, a los pies */
  var sueltos = [];
  for (var i = 0; i < w.entityCount; i++)
    if (w.entities[i].active && w.entities[i].kind === 1) sueltos.push(w.entities[i]);
  assert.strictEqual(sueltos.length, 1, "no ha caido nada al suelo");
  assert.ok(Math.abs(NP.F2I(sueltos[0].x) - NP.F2I(w.players[0].x)) < 8,
            "no ha caido a sus pies");
});

prueba("lo que acabas de soltar no se recoge solo", function () {
  var w = mundo(suelo([[13, 4, "P"], [13, 6, "1"]]), { bolsa: true });
  correr(w, 60, NP.IN.RIGHT);
  assert.strictEqual(w.bolsaCuantos(), 1);
  w.step(NP.IN.ACTION);
  correr(w, 20);                    // quieto encima de el
  assert.strictEqual(w.bolsaCuantos(), 0,
                     "lo ha vuelto a coger sin moverse");
  /* pasada la gracia, si se recoge otra vez */
  correr(w, 40);
  assert.strictEqual(w.bolsaCuantos(), 1,
                     "pasada la gracia sigue sin poder cogerse");
});

prueba("sin bolsa el boton hace lo de siempre", function () {
  /* El control: en cualquier otro juego, accion es atacar y los objetos se
     cogen y se gastan al tocarlos, sin bolsa que valga. */
  var w = mundo(suelo([[13, 4, "P"]]), { ataque: "disparo", alcance: 40 });
  correr(w, 30, NP.IN.RIGHT);
  assert.strictEqual(w.bolsaCuantos(), 0, "guarda cosas sin llevar bolsa");
  w.step(NP.IN.ACTION);
  var disparos = 0;
  for (var i = 0; i < w.entityCount; i++)
    if (w.entities[i].active && w.entities[i].kind === 2) disparos++;
  assert.strictEqual(disparos, 1, "el boton no dispara");
});

/* ------------------------------------- los cerrojos (aventuras tipo Dizzy) */
/*
 * La otra mitad del genero: una casilla que no se pasa hasta que llegas con el
 * objeto que pide. Al abrirla se gasta el objeto y el paso se queda abierto
 * para siempre, que es lo que convierte un mapa pequeno en una aventura.
 */

prueba("un cerrojo frena como una pared", function () {
  var filas = suelo([[13, 4, "P"]]);
  var f = filas[13].split("");
  f[8] = "L";                       // una puerta a la derecha
  filas[13] = f.join("");
  var w = mundo(filas, { bolsa: true });
  correr(w, 120, NP.IN.RIGHT);
  var x = NP.F2I(w.players[0].x);
  assert.ok(x < 8 * 16, "ha pasado por la puerta: x=" + x);
});

prueba("con el objeto que pide, la puerta se abre y se queda abierta",
       function () {
  var filas = suelo([[13, 4, "P"], [13, 6, "1"]]);   // la llave por el camino
  var f = filas[13].split("");
  f[9] = "L";
  filas[13] = f.join("");
  var w = mundo(filas, { bolsa: true });
  correr(w, 200, NP.IN.RIGHT);
  var x = NP.F2I(w.players[0].x);
  assert.ok(x > 10 * 16, "no ha pasado por la puerta: x=" + x);
  assert.strictEqual(w.bolsaCuantos(), 0, "no ha gastado la llave");
  assert.strictEqual(w.abiertos.length, 1, "no ha apuntado la puerta abierta");
  /* y sigue abierta: se vuelve y se pasa otra vez */
  correr(w, 200, NP.IN.LEFT);
  correr(w, 200, NP.IN.RIGHT);
  assert.ok(NP.F2I(w.players[0].x) > 10 * 16, "la puerta se ha vuelto a cerrar");
});

prueba("cada puerta quiere lo suyo", function () {
  /* La llave no abre la puerta del tablon: si abriera cualquiera, no habria
     puzle que valga. */
  var filas = suelo([[13, 4, "P"], [13, 6, "1"]]);
  var f = filas[13].split("");
  f[9] = "Y";                       // esta pide el tablon
  filas[13] = f.join("");
  var w = mundo(filas, { bolsa: true });
  correr(w, 200, NP.IN.RIGHT);
  assert.ok(NP.F2I(w.players[0].x) < 9 * 16, "la llave ha abierto la del tablon");
  assert.strictEqual(w.bolsaCuantos(), 1, "se ha gastado la llave igualmente");
});

prueba("una puerta alta se abre entera y cuesta un solo objeto", function () {
  /* Dos casillas de puerta, una encima de otra, son **una** puerta: se abren
     las dos y se gasta una sola llave. Si costara una por casilla, dibujar una
     puerta de la altura de una persona saldria al doble de precio. */
  var filas = suelo([[13, 4, "P"], [13, 6, "1"], [13, 7, "1"]]);
  var f = filas[13].split(""); f[10] = "L"; filas[13] = f.join("");
  var g = filas[12].split(""); g[10] = "L"; filas[12] = g.join("");
  var w = mundo(filas, { bolsa: true });
  correr(w, 260, NP.IN.RIGHT);
  assert.strictEqual(w.abiertos.length, 2, "no ha abierto la puerta entera");
  assert.strictEqual(w.bolsaCuantos(), 1, "se ha gastado mas de una llave");
  assert.ok(NP.F2I(w.players[0].x) > 11 * 16, "no ha pasado por la puerta");
});

prueba("dos puertas separadas cuestan dos objetos", function () {
  /* El control: se abren juntas porque estan **pegadas**, no por ser del mismo
     tipo. Con un hueco en medio, cada una pide lo suyo. */
  var filas = suelo([[13, 4, "P"], [13, 6, "1"], [13, 7, "1"]]);
  var f = filas[13].split(""); f[10] = "L"; f[13] = "L"; filas[13] = f.join("");
  var w = mundo(filas, { bolsa: true });
  correr(w, 320, NP.IN.RIGHT);
  assert.strictEqual(w.abiertos.length, 2, "no ha abierto las dos");
  assert.strictEqual(w.bolsaCuantos(), 0, "deberia haber gastado las dos llaves");
});

prueba("al cambiar de nivel la bolsa se vacia y las puertas se cierran",
       function () {
  var filas = suelo([[13, 4, "P"], [13, 6, "1"]]);
  var f = filas[13].split("");
  f[9] = "L";
  filas[13] = f.join("");
  var w = mundo(filas, { bolsa: true, niveles: 2 });
  correr(w, 200, NP.IN.RIGHT);
  assert.strictEqual(w.abiertos.length, 1);
  w.loadLevel(0);                   // volver a empezar el nivel
  assert.strictEqual(w.abiertos.length, 0, "la puerta sigue abierta");
  assert.strictEqual(w.bolsaCuantos(), 0, "la bolsa no se ha vaciado");
});

/* ------------------------------------ la pelea (yo contra el barrio) */
/*
 * Lo que separa una pelea de un enjambre. Un enemigo con `golpe:` no anda
 * hacia ti para rozarte: se coloca a su distancia, espera turno, avisa y
 * suelta. Cada una de esas cuatro cosas se mide aqui por separado, porque
 * cada una se puede romper sola y el juego se queda en lo de antes.
 */

/* Un enemigo perseguidor con golpe, plantado a la derecha del jugador. */
function calle(opciones) {
  var o = { cinta: true, jefePersigue: true, jefeRango: 400,
            ataque: "golpe", alcance: 20, dano: 1, health: 9,
            velocidad: 1.5, alcanceEnemigo: 14, avisoEnemigo: 20,
            duracionEnemigo: 6, recuperaEnemigo: 24, esperaEnemigo: 40,
            bossHealth: 40, vidaEnemigo: 40 };
  for (var k in opciones) if (opciones.hasOwnProperty(k)) o[k] = opciones[k];
  /* "J" es el jefe, que es el enemigo perseguidor de estas pruebas */
  return mundo(suelo([[8, 4, "P"], [8, 10, "J"]]), o);
}

function jefeDe(w) {
  for (var i = 0; i < w.entityCount; i++)
    if (w.entities[i].active && w.entities[i].kind === 0) return w.entities[i];
  return null;
}

prueba("el que pelea no se te mete dentro", function () {
  var w = calle({});
  var p = w.players[0], e = jefeDe(w);
  var minimo = 9999;
  for (var i = 0; i < 300; i++) {
    w.step(0);
    var hueco = Math.abs(NP.F2I(e.x) - NP.F2I(p.x));
    if (hueco < minimo) minimo = hueco;
  }
  assert.ok(minimo >= 8, "se ha puesto a " + minimo + " px: eso es encima");
});

prueba("sin golpe si se te mete dentro", function () {
  /* El control: el mismo enemigo sin `golpe:` vuelve a ser un bicho que anda
     hacia ti hasta tocarte, que es lo que hace en el resto de generos. */
  var w = calle({ alcanceEnemigo: 0 });
  var p = w.players[0], e = jefeDe(w);
  var minimo = 9999;
  for (var i = 0; i < 300; i++) {
    w.step(0);
    var hueco = Math.abs(NP.F2I(e.x) - NP.F2I(p.x));
    if (hueco < minimo) minimo = hueco;
  }
  assert.ok(minimo < 8, "se ha quedado a " + minimo + " px sin tener golpe");
});

prueba("el golpe se ve venir antes de hacer dano", function () {
  /* La preparacion es el aviso: durante esos frames el enemigo ya esta en la
     pose de atacar pero **todavia no toca**. Sin ese hueco no hay forma de
     esquivar y el juego seria injusto. */
  var w = calle({ avisoEnemigo: 30 });
  var p = w.players[0];
  var avisando = 0, vidaAlEmpezar = p.health, cobradoEn = -1;
  for (var i = 0; i < 400 && cobradoEn < 0; i++) {
    w.step(0);
    var e = jefeDe(w);
    if (e && e.fase === 2) avisando++;
    if (p.health < vidaAlEmpezar) cobradoEn = i;
  }
  assert.ok(avisando >= 30,
            "solo ha avisado " + avisando + " frames de los 30 que pide");
  assert.ok(cobradoEn > 0, "no ha llegado a pegar en 400 frames");
});

prueba("despues de pegar se queda vendido", function () {
  /* La recuperacion es tu turno: durante esos frames no decide nada. Si no
     existiera, la pelea no tendria ritmo -no habria hueco para responder- y
     seria otra vez cuestion de machacar el boton. */
  var w = calle({ recuperaEnemigo: 40 });
  var recuperando = 0;
  for (var i = 0; i < 400; i++) {
    w.step(0);
    var e = jefeDe(w);
    if (e && e.fase === 4) recuperando++;
  }
  assert.ok(recuperando >= 30,
            "solo se ha quedado vendido " + recuperando + " frames");
});

prueba("solo pegan los que dice `agresivos:`", function () {
  /* La ficha de ataque: con `agresivos: 1` no puede haber dos preparando o
     pegando a la vez, por muchos que haya alrededor. Es la regla que hace que
     una pelea se juegue en vez de sufrirse. */
  function aLaVez(cuantos) {
    var filas = suelo([[8, 4, "P"], [8, 10, "J"], [7, 10, "J"], [9, 10, "J"]]);
    var w = mundo(filas, { cinta: true, jefePersigue: true, jefeRango: 400,
                           ataque: "golpe", alcance: 20, health: 20,
                           alcanceEnemigo: 14, avisoEnemigo: 20,
                           bossHealth: 40, agresivos: cuantos });
    var maximo = 0;
    for (var i = 0; i < 400; i++) {
      w.step(0);
      var n = 0;
      for (var k = 0; k < w.entityCount; k++) {
        var e = w.entities[k];
        if (e.active && e.kind === 0 && e.fase >= 2 && e.fase <= 4) n++;
      }
      if (n > maximo) maximo = n;
    }
    return maximo;
  }
  assert.strictEqual(aLaVez(1), 1, "con `agresivos: 1` pega mas de uno");
  assert.ok(aLaVez(3) > 1, "con `agresivos: 3` sigue pegando uno solo");
});

prueba("al acertar, el mundo se para unos frames", function () {
  /* La parada del impacto: sin ella el puno atraviesa al otro y no se siente
     nada. Se mide en que, mientras dura, el mundo **no corre**: el reloj del
     golpe se queda quieto aunque se sigan pidiendo frames. */
  var w = calle({ velocidad: 0.1 });
  var p = w.players[0];
  var parados = 0;
  for (var i = 0; i < 200; i++) {
    var antesX = p.x, antesAt = p.attackTimer;
    w.step(i % 12 < 2 ? NP.IN.ACTION : 0);
    if (w.congelado && p.x === antesX && p.attackTimer === antesAt) parados++;
  }
  /* Cada acierto para cuatro frames, y en doscientos frames caben un par de
     aciertos: con que haya una parada entera ya esta demostrado que existe. */
  assert.ok(parados >= 4, "solo " + parados + " frames parados: no congela");
});

prueba("el que cobra se tambalea y por ahi entra el siguiente", function () {
  /* El tambaleo es lo que hace que una serie sea una serie: mientras dura, el
     que la cobra no decide nada y el golpe siguiente le alcanza. */
  var w = calle({ velocidad: 0.1 });
  var e = jefeDe(w);
  var tambaleando = 0;
  for (var i = 0; i < 200; i++) {
    w.step(i % 12 < 2 ? NP.IN.ACTION : 0);
    if (e.aturdido) tambaleando++;
  }
  assert.ok(tambaleando > 20,
            "solo " + tambaleando + " frames tambaleandose: no hay hueco para "
            + "encadenar");
});

prueba("el que ya esta soltando el golpe no se para con un puno", function () {
  /* La armadura del aviso: quien ya se ha comprometido llega a soltarlo. Es
     lo que hace que prepararse sea una amenaza y no un adorno; si un puno
     cualquiera lo cortara, bastaria con pegar sin parar. */
  var w = calle({ avisoEnemigo: 40 });
  var e = jefeDe(w);
  /* esperar a que empiece a preparar */
  for (var i = 0; i < 400 && e.fase !== 2; i++) w.step(0);
  assert.strictEqual(e.fase, 2, "no ha llegado a preparar el golpe");
  /* pegarle mientras prepara: tiene que seguir preparando */
  w.step(NP.IN.ACTION);
  correr(w, 6);
  assert.ok(e.fase === 2 || e.fase === 3,
            "un puno normal le ha cortado el golpe (fase " + e.fase + ")");
});

prueba("la patada en salto pega mas que un punetazo", function () {
  /* Saltar y pegar es el golpe que rompe un grupo, y cuesta algo: en el aire
     no se corrige. Por eso vale por un remate. */
  function dano(saltando) {
    var w = calle({ velocidad: 0.1, danoRemate: 4, combo: 3, ventana: 30 });
    var e = jefeDe(w);
    /* clavar al enemigo delante para medir solo el golpe */
    var p = w.players[0];
    var antes = e.health;
    if (saltando) { w.step(NP.IN.JUMP); correr(w, 4); }
    e.x = p.x + NP.I2F(16); e.y = p.y + p.altura;
    w.step(NP.IN.ACTION);
    for (var i = 0; i < 10; i++) {
      w.step(0);
      e.x = p.x + NP.I2F(16); e.y = p.y + p.altura;
    }
    return antes - e.health;
  }
  var suelo_ = dano(false), aire = dano(true);
  assert.ok(aire > suelo_,
            "la patada hace " + aire + " y el puno " + suelo_);
});

prueba("el codazo le da al que se te cuela por detras", function () {
  /* Te rodean: la mitad viene por el otro lado. Girarse a mano con tres
     encima es imposible, asi que el golpe se va solo hacia atras cuando ahi
     hay alguien y delante no. */
  var w = calle({ velocidad: 0.1 });
  var p = w.players[0], e = jefeDe(w);
  p.facing = 1;                       /* mirando a la derecha */
  e.x = p.x - NP.I2F(16);             /* y el otro, a la izquierda */
  e.y = p.y;
  var antes = e.health;
  w.step(NP.IN.ACTION);
  for (var i = 0; i < 10; i++) {
    w.step(0);
    e.x = p.x - NP.I2F(16); e.y = p.y;
  }
  assert.ok(e.health < antes, "el de atras no ha cobrado nada");
  assert.strictEqual(p.facing, 0, "no se ha girado hacia el");
});

prueba("con doble toque se corre", function () {
  /* Correr es la respuesta a que te rodeen, y se enciende con el mando: en un
     recreativo no habia botones de sobra. */
  function avance(dobleToque) {
    var w = calle({ velocidad: 1.5, alcanceEnemigo: 0 });
    var p = w.players[0];
    /* el enemigo no pinta nada aqui */
    var e = jefeDe(w); e.active = 0;
    var x0 = NP.F2I(p.x);
    if (dobleToque) { w.step(NP.IN.RIGHT); w.step(0); }
    for (var i = 0; i < 40; i++) w.step(NP.IN.RIGHT);
    return NP.F2I(p.x) - x0;
  }
  var corriendo = avance(true), andando = avance(false);
  assert.ok(corriendo > andando + 10,
            "corriendo avanza " + corriendo + " y andando " + andando);
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

/* ------------------------------------------- la vista isometrica
 *
 * Aqui la tercera coordenada es de verdad: el suelo tiene relieve y lo que te
 * frena no es el tipo de la casilla de al lado sino lo alto que esta. Estas
 * pruebas son las de esa regla, que es la que sostiene el genero entero.
 *
 * El mapa de estas pruebas es una sala de 8x8 con el jugador en el centro, y
 * los simbolos del relieve son: "b" un escalon de 4 (se sube andando), "c" un
 * cubo de 16 (hay que saltarlo) y "W" una pared de 48.
 */

function sala(extra) {
  var filas = [];
  for (var y = 0; y < 8; y++) filas.push("........");
  (extra || []).forEach(function (par) {   // [fila, columna, simbolo]
    var f = filas[par[0]].split("");
    f[par[1]] = par[2];
    filas[par[0]] = f.join("");
  });
  return filas;
}

function isoMundo(extra, opciones) {
  opciones = opciones || {};
  opciones.iso = true;
  opciones.pantallas = true;
  if (opciones.jump === undefined) opciones.jump = 3.6;
  if (opciones.gravity === undefined) opciones.gravity = 0.28;
  if (opciones.speed === undefined) opciones.speed = 1.0;
  return mundo(sala(extra), opciones);
}

/* Lo mas alto a lo que llego el jugador en toda la tirada. Se mide asi -y no
   al final- porque andando se pasa por encima de un cubo y se sale por el otro
   lado: preguntar al final contaria donde acabo, no si se subio. */
function isoCorrer(w, frames, input) {
  var maximo = 0;
  for (var i = 0; i < frames; i++) {
    w.step(input || 0);
    maximo = Math.max(maximo, NP.F2I(w.players[0].altura));
  }
  return maximo;
}

/* la casilla en la que esta el jugador, por el centro de su caja */
function celda(w) {
  var p = w.players[0], a = w.data.player.actor;
  return [(NP.F2I(p.x) + (a.box_w >> 1)) >> 4,
          (NP.F2I(p.y) + (a.box_h >> 1)) >> 4];
}

prueba("en isometrica se anda por la planta y el mando va a los ejes del mapa",
       function () {
  /* Derecha es el eje x del mapa y abajo el eje y: en pantalla salen en
     diagonal, pero lo que se mueve es la planta. */
  var w = isoMundo([[4, 3, "P"]]);
  correr(w, 30, NP.IN.RIGHT);
  assert.strictEqual(celda(w)[1], 4, "andando a la derecha ha cambiado de fila");
  assert.ok(celda(w)[0] > 3, "andando a la derecha no ha avanzado en x");
  var w2 = isoMundo([[4, 3, "P"]]);
  correr(w2, 30, NP.IN.DOWN);
  assert.strictEqual(celda(w2)[0], 3, "andando hacia abajo ha cambiado de columna");
  assert.ok(celda(w2)[1] > 4, "andando hacia abajo no ha avanzado en y");
});

prueba("un escalon pequeno se sube andando", function () {
  var w = isoMundo([[4, 3, "P"], [4, 5, "b"]]);
  var arriba = isoCorrer(w, 60, NP.IN.RIGHT);
  assert.ok(celda(w)[0] >= 5,
            "se ha quedado en la casilla " + celda(w) + ": el escalon de 4 "
            + "pixeles no se sube andando");
  assert.strictEqual(arriba, 4,
                     "lo mas alto que ha estado es " + arriba
                     + " y el escalon levanta 4");
});

prueba("un cubo de una altura no se sube andando: hay que saltar", function () {
  var w = isoMundo([[4, 3, "P"], [4, 5, "c"]]);
  var arriba = isoCorrer(w, 60, NP.IN.RIGHT);
  assert.ok(celda(w)[0] < 5,
            "ha llegado a la casilla " + celda(w) + " andando: un cubo de 16 "
            + "tiene que frenar");
  assert.strictEqual(arriba, 0, "andando ya se ha subido: " + arriba);
  /* y saltando si */
  w.step(NP.IN.RIGHT | NP.IN.JUMP);
  arriba = isoCorrer(w, 40, NP.IN.RIGHT);
  assert.ok(arriba >= 16,
            "saltando lo mas alto que ha estado es " + arriba);
});

prueba("una pared de tres alturas no se salta", function () {
  var w = isoMundo([[4, 3, "P"], [4, 5, "W"]]);
  for (var i = 0; i < 6; i++) {
    w.step(NP.IN.RIGHT | NP.IN.JUMP);
    correr(w, 40, NP.IN.RIGHT);
  }
  assert.ok(celda(w)[0] < 5,
            "ha llegado a la casilla " + celda(w) + ": una pared de 48 no se "
            + "salta con un salto de 23");
});

prueba("una pared ya pintada en la sala para igual y no cuesta un cubo",
       function () {
  /* Las dos paredes del fondo de una habitacion vienen dibujadas en el propio
     dibujo de la sala, asi que en el mapa son casillas que levantan y **no
     traen cubo**. Tienen que frenar exactamente igual que un muro -si no, el
     jugador se sale de la habitacion- y no deben entrar en la fila del
     dibujado, que es de lo que vive el que la Mega Drive vaya a 60. */
  var w = isoMundo([[4, 3, "P"], [4, 5, "p"]]);
  for (var i = 0; i < 6; i++) {
    w.step(NP.IN.RIGHT | NP.IN.JUMP);
    correr(w, 40, NP.IN.RIGHT);
  }
  assert.ok(celda(w)[0] < 5,
            "ha llegado a la casilla " + celda(w) + ": una pared pintada de 48 "
            + "tiene que parar igual que un muro");
  assert.strictEqual(w.bloquesN, 0,
                     "la sala ha montado " + w.bloquesN + " cubos y la unica "
                     + "casilla que levanta es la que ya viene pintada");
});

prueba("en la fila del dibujado no entra lo que esta en otra habitacion",
       function () {
  /* Todas las salas se dibujan en el mismo cuadro de pantalla, asi que lo que
     esta en otra habitacion no se pinta. Tampoco tiene que entrar en la fila:
     ordenar treinta puestos cuando se van a dibujar cinco es lo que le costaba
     a la Mega Drive el frame. */
  var w = isoMundo([[4, 3, "P"], [4, 5, "c"]], { extraFilas: null });
  var fuera = w.entities[0];
  fuera.active = 1;
  fuera.kind = 1;                       // un objeto cualquiera
  fuera.def = 0;
  fuera.x = NP.I2F(8 * 16);             // la sala de al lado
  fuera.y = NP.I2F(4 * 16);
  if (w.entityCount < 1) w.entityCount = 1;
  var orden = w.ordenDibujo();
  assert.ok(orden.indexOf(0) < 0,
            "el puesto 0 esta en otra sala y ha entrado en la fila");
  fuera.x = NP.I2F(2 * 16);             // y ahora si, en esta
  orden = w.ordenDibujo();
  assert.ok(orden.indexOf(0) >= 0,
            "el puesto 0 esta en esta sala y no ha entrado en la fila");
});

prueba("al abrir un cerrojo su cubo deja de dibujarse en el acto", function () {
  /* La puerta de un cerrojo es un cubo de la sala. Al abrirla la casilla pasa
     a ser un hueco por el que se pasa, y el cubo tiene que desaparecer en ese
     mismo frame: los cubos de la sala se montan una vez y no se vuelven a
     mirar, asi que sin rehacerlos la puerta se quedaba pintada -y atravesable-
     hasta salir de la habitacion. */
  var w = isoMundo([[4, 3, "P"], [4, 5, "L"], [4, 2, "1"]], { bolsa: true });
  correr(w, 40, NP.IN.LEFT);            // recoger lo que abre la puerta
  assert.strictEqual(w.bolsaCuantos(), 1, "no ha cogido el objeto");
  var antes = w.bloquesN;
  assert.ok(antes >= 1, "la sala no ha montado el cubo de la puerta");
  correr(w, 90, NP.IN.RIGHT);           // ir a la puerta y abrirla
  assert.strictEqual(w.abiertos.length, 1,
                     "la puerta no se ha abierto llevando lo que pide");
  assert.strictEqual(w.bloquesN, antes - 1,
                     "la sala sigue con " + w.bloquesN + " cubos de los "
                     + antes + " de antes: la puerta abierta sigue dibujada");
});

prueba("al salirse de un cubo se cae hasta el suelo", function () {
  var w = isoMundo([[4, 3, "P"], [4, 4, "c"]]);
  /* Subirse al cubo. Despues del despegue se suelta el mando: por el aire da
     igual, y al aterrizar se queda quieto encima en vez de seguir andando. */
  w.step(NP.IN.RIGHT | NP.IN.JUMP);
  correr(w, 30, 0);
  assert.strictEqual(NP.F2I(w.players[0].altura), 16,
                     "no se ha quedado encima del cubo: altura "
                     + NP.F2I(w.players[0].altura));
  assert.strictEqual(w.players[0].onGround, 1, "no ha aterrizado");
  /* y seguir andando: al pasarse, se cae */
  correr(w, 60, NP.IN.RIGHT);
  assert.strictEqual(NP.F2I(w.players[0].altura), 0,
                     "sigue a altura " + NP.F2I(w.players[0].altura)
                     + " fuera del cubo");
  assert.strictEqual(w.players[0].onGround, 1, "se ha quedado por el aire");
});

prueba("en el aire el impulso no se manda pero se guarda", function () {
  /* Saltar pegado a un cubo tiene que subirte encima: el impulso con el que
     despegaste se guarda aunque de momento no quepas. Es lo unico que hace
     que se pueda subir a algo estando al lado, sin carrerilla. */
  var w = isoMundo([[4, 3, "P"], [4, 4, "c"]]);
  correr(w, 40, NP.IN.RIGHT);          // pegarse al cubo
  assert.strictEqual(NP.F2I(w.players[0].altura), 0, "se ha subido andando");
  w.step(NP.IN.RIGHT | NP.IN.JUMP);
  correr(w, 25, NP.IN.RIGHT);
  assert.strictEqual(NP.F2I(w.players[0].altura), 16,
                     "saltando desde al lado se ha quedado a altura "
                     + NP.F2I(w.players[0].altura));
});

prueba("saltar por encima de un pincho no mata", function () {
  /* Con el paso largo el salto cruza una casilla entera: es lo que hace que
     un pincho suelto sea un obstaculo y no una pared. */
  var rapido = { speed: 1.6 };
  var w = isoMundo([[4, 3, "P"], [4, 5, "^"]], { speed: 1.6 });
  correr(w, 40, NP.IN.RIGHT);
  assert.strictEqual(w.state, NP.STATE.DYING, "andando sobre el pincho no muere");
  var w2 = isoMundo([[4, 3, "P"], [4, 5, "^"]], { speed: 1.6 });
  /* Saltar antes de pisarlo y mirar **mientras se pasa por encima**: en pleno
     vuelo el jugador esta sobre la casilla del pincho y sigue vivo. */
  correr(w2, 2, NP.IN.RIGHT);
  w2.step(NP.IN.RIGHT | NP.IN.JUMP);
  correr(w2, 18, NP.IN.RIGHT);
  assert.strictEqual(celda(w2)[0], 5,
                     "no esta sobre el pincho: esta en " + celda(w2));
  assert.ok(NP.F2I(w2.players[0].altura) > 6,
            "no esta por el aire: altura " + NP.F2I(w2.players[0].altura));
  assert.strictEqual(w2.state, NP.STATE.PLAY,
                     "pasando por encima tambien muere");
  void rapido;
});

prueba("saltar por encima de un bicho es esquivarlo", function () {
  /* En esta vista no basta con pisar la misma casilla: hay que cruzarse
     tambien en altura. Es lo que convierte el salto en una forma de esquivar. */
  var w = isoMundo([[4, 3, "P"], [4, 4, "e"]]);
  var vida0 = w.players[0].health;
  correr(w, 30, NP.IN.RIGHT);
  assert.ok(w.players[0].health < vida0 || w.state === NP.STATE.DYING,
            "andando contra el bicho no ha cobrado");
  var w2 = isoMundo([[4, 3, "P"], [4, 4, "e"]]);
  w2.step(NP.IN.RIGHT | NP.IN.JUMP);
  correr(w2, 8, NP.IN.RIGHT);
  assert.ok(NP.F2I(w2.players[0].altura) > 12,
            "no ha despegado: " + NP.F2I(w2.players[0].altura));
  assert.strictEqual(w2.state, NP.STATE.PLAY,
                     "por encima del bicho tambien cobra");
});

prueba("la sala se monta con sus cubos y se rehace al cambiar de sala",
       function () {
  /* Los cubos viven al final de la lista de entidades y solo existen los de la
     habitacion que se ve: es lo que permite que un castillo entero quepa en
     sesenta y cuatro huecos. */
  var filas = [];
  for (var y = 0; y < 8; y++) filas.push("........" + "........");
  filas[4] = "...P...." + "..cc....";
  filas[2] = "..cc...." + "........";
  var w = mundo(filas, { iso: true, pantallas: true, speed: 1.0,
                         jump: 3.6, gravity: 0.28 });
  assert.strictEqual(w.salaX, 0, "no empieza en la primera sala");
  assert.strictEqual(w.bloquesN, 2,
                     "la primera sala ha montado " + w.bloquesN + " cubos y "
                     + "tiene 2");
  correr(w, 200, NP.IN.RIGHT);
  assert.strictEqual(w.salaX, 1, "no ha cambiado de sala");
  assert.strictEqual(w.bloquesN, 2,
                     "la segunda sala tiene " + w.bloquesN + " cubos y "
                     + "tambien tiene 2");
});

prueba("lo que pasa en la sala de al lado no corre", function () {
  /* Un bicho de otra habitacion se queda en pausa: ni anda, ni te toca, ni
     ocupa sitio en la pantalla. */
  var filas = [];
  for (var y = 0; y < 8; y++) filas.push("................");
  filas[4] = "...P...........e";
  var w = mundo(filas, { iso: true, pantallas: true, speed: 1.0,
                         jump: 3.6, gravity: 0.28 });
  var bicho = w.entities[0];
  var x0 = bicho.x;
  correr(w, 120, 0);
  assert.strictEqual(bicho.x, x0,
                     "el bicho de la sala de al lado se ha movido");
  assert.strictEqual(w.dibujo(0), null,
                     "el bicho de la sala de al lado se dibuja encima de esta");
});

prueba("los cubos se dibujan por profundidad y el jugador entra en la fila",
       function () {
  /* En esta vista hay un detras de verdad: uno se mete tras un cubo cada dos
     pasos, asi que los jugadores tienen que entrar en la fila de dibujado y
     no pintarse al final, encima de todo. */
  var w = isoMundo([[4, 3, "P"], [2, 2, "c"], [6, 6, "c"]]);
  var orden = w.ordenDibujo();
  var honduras = orden.map(function (p) { return w.hondura(p); });
  for (var i = 1; i < honduras.length; i++)
    assert.ok(honduras[i] >= honduras[i - 1],
              "la fila no va de mas lejos a mas cerca");
  assert.ok(orden.indexOf(64) >= 0,
            "el jugador no entra en la fila de dibujado");
  assert.ok(orden.indexOf(64) > 0 && orden.indexOf(64) < orden.length - 1,
            "el jugador sale el primero o el ultimo de la fila: no esta "
            + "colocado por profundidad");
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
