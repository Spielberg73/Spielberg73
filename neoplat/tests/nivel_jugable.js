/* nivel_jugable.js - un bot recorre los niveles para comprobar que se pueden
 * terminar sin trucos.
 *
 * El bot solo sabe hacer lo que haria alguien la primera vez: andar a la
 * derecha, saltar cuando ve una pared, un hueco, pinchos o un enemigo, y
 * mantener el salto mientras sube. Si el bot llega a la meta, una persona
 * tambien puede. Si no llega, el nivel esta mal diseñado.
 *
 *   node tests/nivel_jugable.js datos.json [--detalle]
 */
"use strict";

var fs = require("fs");
var path = require("path");
var NP = require(path.join(__dirname, "..", "preview", "np_core.js"));

var TILE_SOLID = 1, TILE_PLATFORM = 2, TILE_HAZARD = 3;

function jugar(data, nivel, opciones) {
  opciones = opciones || {};
  var w = NP.create(data);
  w.step(NP.IN.START);
  while (w.levelIndex < nivel) {           // saltar a los niveles siguientes
    w.loadLevel(nivel);
  }
  var pa = data.player.actor;
  var maxX = 0, sinAvanzar = 0, muertes = 0, saltando = 0;
  var limite = opciones.frames || 6000;

  for (var i = 0; i < limite; i++) {
    var p = w.player;
    var pies = NP.F2I(p.y) + pa.box_h;
    var frente = NP.F2I(p.x) + pa.box_w + 6;    // mira un poco por delante
    var medio = NP.F2I(p.y) + Math.floor(pa.box_h / 2);
    var input = NP.IN.RIGHT;

    var pared = w.tileKindAt(frente >> 4, medio >> 4) === TILE_SOLID ||
                w.tileKindAt(frente >> 4, (pies - 2) >> 4) === TILE_SOLID;
    var sueloDelante = w.tileKindAt(frente >> 4, (pies + 2) >> 4);
    var hueco = sueloDelante !== TILE_SOLID && sueloDelante !== TILE_PLATFORM;
    var peligro = w.tileKindAt(frente >> 4, medio >> 4) === TILE_HAZARD ||
                  w.tileKindAt(frente >> 4, (pies + 2) >> 4) === TILE_HAZARD;

    var enemigo = null, distancia = 9999;
    for (var k = 0; k < w.entityCount; k++) {
      var e = w.entities[k];
      if (!e.active || e.kind !== 0) continue;
      var dx = NP.F2I(e.x) - NP.F2I(p.x);
      var dy = Math.abs(NP.F2I(e.y) - NP.F2I(p.y));
      if (dx > 0 && dx < distancia && dy < 40) { distancia = dx; enemigo = e; }
    }

    if (p.onGround && (pared || hueco || peligro || (enemigo && distancia < 34))) {
      input |= NP.IN.JUMP;
      saltando = 1;
    } else if (saltando && !p.onGround && p.vy < 0) {
      input |= NP.IN.JUMP;                 // mantener para llegar mas alto
    } else if (p.onGround) {
      saltando = 0;
    }

    w.step(input);

    if (w.state === NP.STATE.LEVEL_END || w.state === NP.STATE.FINISHED) {
      return { ok: true, frames: i, muertes: muertes, avance: NP.F2I(w.player.x) };
    }
    if (w.state === NP.STATE.DYING) {
      muertes++;
      if (muertes > (opciones.muertes || 6)) {
        return { ok: false, motivo: "muere demasiadas veces", muertes: muertes,
                 avance: maxX, frames: i };
      }
      while (w.state !== NP.STATE.PLAY && w.state !== NP.STATE.GAME_OVER &&
             w.state !== NP.STATE.TITLE) w.step(0);
      if (w.state !== NP.STATE.PLAY) {
        return { ok: false, motivo: "game over", muertes: muertes, avance: maxX, frames: i };
      }
      w.lives = data.lives;               // al bot le interesa seguir probando
      maxX = 0;
      continue;
    }
    if (NP.F2I(w.player.x) > maxX) { maxX = NP.F2I(w.player.x); sinAvanzar = 0; }
    else if (++sinAvanzar > 600) {
      return { ok: false, motivo: "atascado en x=" + maxX, muertes: muertes,
               avance: maxX, frames: i };
    }
  }
  return { ok: false, motivo: "no termina a tiempo", muertes: muertes, avance: maxX };
}

if (require.main === module) {
  var data = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  var fallos = 0;
  data.levels.forEach(function (nivel, i) {
    var r = jugar(data, i);
    var ancho = nivel.width * 16;
    if (r.ok) {
      console.log("  ok   nivel %d (%s): terminado en %d frames, %d muertes",
                  i + 1, nivel.name, r.frames, r.muertes);
    } else {
      fallos++;
      console.log("  FALLO nivel %d (%s): %s (llego a x=%d de %d)",
                  i + 1, nivel.name, r.motivo, r.avance, ancho);
    }
  });
  process.exit(fallos ? 1 : 0);
}

module.exports = { jugar: jugar };
