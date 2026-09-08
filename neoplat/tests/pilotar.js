/* Pilota un juego de carretera sobre el motor del preview y dice si se llega.
 *
 * No lo hace el bot del kit: un bot que sabe saltar y pegar no sabe conducir.
 * Este mira la cinta de la carretera -la que calcula el propio motor- y pone
 * el volante hacia donde va la calzada, con el pie a fondo. Si el circuito
 * tuviera una curva imposible, se saldria y no llegaria.
 */
var fs = require("fs");
var path = require("path");
var KIT = path.join(__dirname, "..");
var NPCore = require(path.join(KIT, "preview", "np_core.js"));

var datos = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
var IN = NPCore.IN;
var world = NPCore.create(datos);
world.step(IN.START);

var punta = 0, controles = 0, cronoAntes = world.timeLeft, llega = false;
for (var f = 0; f < 6000; f++) {
  var p = world.players[0];
  var vel = -p.vy / 256;
  if (vel > punta) punta = vel;
  if (world.timeLeft > cronoAntes) controles++;
  cronoAntes = world.timeLeft;
  if (world.state !== 1) { llega = world.state === 3 || world.levelIndex > 0; break; }
  var fila = ((p.y >> 8) >> 4) - 4;
  if (fila < 0) fila = 0;
  var objetivo = world.viaCentro[fila];
  var centro = (p.x >> 8) + 6;
  var mando = IN.ACTION;                       /* pie a fondo */
  if (f === 60) mando |= IN.JUMP;              /* la marcha larga */
  if (centro < objetivo - 3) mando |= IN.RIGHT;
  else if (centro > objetivo + 3) mando |= IN.LEFT;
  world.step(mando, 0);
}
console.log(JSON.stringify({
  llega: llega, punta: punta, controles: controles,
  fila: (world.players[0].y >> 8) >> 4, filas: world.level.cells_h,
  estado: world.state
}));
