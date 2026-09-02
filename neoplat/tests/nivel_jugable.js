/* nivel_jugable.js - comprueba con un bot que los niveles se pueden terminar.
 *
 * El bot vive en preview/np_bot.js, que es el mismo que usa el boton
 * "¿se puede terminar?" del editor: asi la comprobacion es identica.
 *
 *   node tests/nivel_jugable.js datos.json
 */
"use strict";

var fs = require("fs");
var path = require("path");
var NP = require(path.join(__dirname, "..", "preview", "np_core.js"));
var NPBot = require(path.join(__dirname, "..", "preview", "np_bot.js"));

function jugar(data, nivel, opciones) {
  return NPBot.jugar(NP, data, nivel, opciones);
}

if (require.main === module) {
  var data = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  var fallos = 0;
  data.levels.forEach(function (nivel, i) {
    var r = jugar(data, i);
    if (r.ok) {
      console.log("  ok   nivel %d (%s): terminado en %d frames, %d muertes",
                  i + 1, nivel.name, r.frames, r.muertes);
    } else {
      fallos++;
      /* En vista cenital se sube, asi que lo que se cuenta es hasta donde
         subio: decir "x=" ahi seria mentir sobre lo que hizo el bot. */
      if (data.view === "cenital") {
        console.log("  FALLO nivel %d (%s): %s (subio hasta y=%d de %d)",
                    i + 1, nivel.name, r.motivo, r.avance, nivel.height * 16);
      } else {
        console.log("  FALLO nivel %d (%s): %s (llego a x=%d de %d)",
                    i + 1, nivel.name, r.motivo, r.avance, nivel.width * 16);
      }
    }
  });
  process.exit(fallos ? 1 : 0);
}

module.exports = { jugar: jugar };
