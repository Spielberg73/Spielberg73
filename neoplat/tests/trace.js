/* trace.js - la misma traza que engine/host/np_trace.c, con el motor en JS.
 *
 *   node trace.js datos.json pulsaciones.txt
 */
"use strict";

var fs = require("fs");
var path = require("path");
var NPCore = require(path.join(__dirname, "..", "preview", "np_core.js"));

var data = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
/* Dos numeros por linea, uno por mando (igual que np_trace.c). */
var numeros = fs.readFileSync(process.argv[3], "utf8").trim().split(/\s+/)
  .filter(function (s) { return s.length; })
  .map(Number);
var inputs = [];
for (var n = 0; n + 1 < numeros.length; n += 2) inputs.push([numeros[n], numeros[n + 1]]);

var world = NPCore.create(data);

function entityHash(w) {
  var hash = 2166136261;
  for (var i = 0; i < w.entityCount; i++) {
    var e = w.entities[i];
    var values = [
      e.active >>> 0, e.x >>> 0, e.y >>> 0, e.vy >>> 0,
      ((e.anim << 8) | e.animFrame) >>> 0,
      ((e.facing << 8) | e.health) >>> 0
    ];
    for (var k = 0; k < 6; k++) {
      hash = (hash ^ values[k]) >>> 0;
      hash = Math.imul(hash, 16777619) >>> 0;
    }
  }
  return hash >>> 0;
}

function hex8(v) {
  var s = v.toString(16);
  while (s.length < 8) s = "0" + s;
  return s;
}

var out = [];
inputs.forEach(function (par) {
  var p0 = world.players[0], p1 = world.players[1];
  world.step(par[0], par[1]);
  out.push([
    world.frame, p0.x, p0.y, p0.vx, p0.vy,
    world.state, p0.health, p0.lives, world.score,
    world.camX, world.camY, world.levelIndex, world.sfx, world.bossHealth,
    hex8(entityHash(world)),
    p1.x, p1.y, p1.vx, p1.vy, p1.health, p1.lives,
    p0.playing, p0.dying, p1.playing, p1.dying,
    world.keys, world.hearts,
    world.checkOn, world.checkX, world.checkY, p0.power,
    /* el dibujo del latigo: 0 = no hay ninguno en la lista */
    p0.whip ? 1 : 0
  ].join(" "));
});
process.stdout.write(out.join("\n") + "\n");
