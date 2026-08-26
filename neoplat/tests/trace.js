/* trace.js - la misma traza que engine/host/np_trace.c, con el motor en JS.
 *
 *   node trace.js datos.json pulsaciones.txt
 */
"use strict";

var fs = require("fs");
var path = require("path");
var NPCore = require(path.join(__dirname, "..", "preview", "np_core.js"));

var data = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
var inputs = fs.readFileSync(process.argv[3], "utf8").trim().split(/\s+/)
  .filter(function (s) { return s.length; })
  .map(Number);

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
inputs.forEach(function (input) {
  world.step(input);
  out.push([
    world.frame, world.player.x, world.player.y, world.player.vx, world.player.vy,
    world.state, world.player.health, world.lives, world.score,
    world.camX, world.camY, world.levelIndex, world.sfx, world.bossHealth,
    hex8(entityHash(world))
  ].join(" "));
});
process.stdout.write(out.join("\n") + "\n");
