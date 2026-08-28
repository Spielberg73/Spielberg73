/* np_bot.js - un jugador automatico que intenta terminarse un nivel.
 *
 * Solo sabe hacer lo que haria alguien la primera vez: andar hacia la derecha
 * y saltar cuando ve una pared, un hueco, pinchos o un enemigo. Si el bot llega
 * a la meta, una persona tambien puede.
 *
 * Lo usan dos sitios: las pruebas del kit (tests/nivel_jugable.js) y el boton
 * "¿se puede terminar?" del editor.
 */
(function (root) {
  "use strict";

  var TILE_SOLID = 1, TILE_PLATFORM = 2, TILE_HAZARD = 3;

  /**
   * @param NPCore  el motor (preview/np_core.js)
   * @param data    los datos del juego
   * @param nivel   indice del nivel
   * @param opciones {frames, muertes, vista}
   */
  function jugar(NPCore, data, nivel, opciones) {
    opciones = opciones || {};
    var w = NPCore.create(data);
    w.step(NPCore.IN.START);
    if (nivel) w.loadLevel(nivel);
    var pa = data.player.actor;
    var limite = opciones.frames || 6000;
    var maxMuertes = opciones.muertes === undefined ? 6 : opciones.muertes;
    var vista = opciones.vista === undefined ? 6 : opciones.vista;
    var maxX = 0, sinAvanzar = 0, muertes = 0, saltando = 0;

    /* El bot solo sabe andar hacia la derecha: si la llave que pide la meta
       esta escondida arriba, se queda dando vueltas delante de la meta sin
       saber por que. Este aviso lo dice con todas las letras. */
    function motivo(texto) {
      var piden = w.level.keys_needed || 0;
      if (piden && w.keys < piden)
        return texto + " (le faltan llaves para abrir la meta: tiene "
               + w.keys + " de " + piden + ")";
      return texto;
    }

    for (var i = 0; i < limite; i++) {
      var p = w.players[0];
      var pies = NPCore.F2I(p.y) + pa.box_h;
      var frente = NPCore.F2I(p.x) + pa.box_w + vista;
      var medio = NPCore.F2I(p.y) + Math.floor(pa.box_h / 2);
      var input = NPCore.IN.RIGHT;

      var pared = w.tileKindAt(frente >> 4, medio >> 4) === TILE_SOLID ||
                  w.tileKindAt(frente >> 4, (pies - 2) >> 4) === TILE_SOLID;
      var sueloDelante = w.tileKindAt(frente >> 4, (pies + 2) >> 4);
      var hueco = sueloDelante !== TILE_SOLID && sueloDelante !== TILE_PLATFORM;
      var peligro = w.tileKindAt(frente >> 4, medio >> 4) === TILE_HAZARD ||
                    w.tileKindAt(frente >> 4, (pies + 2) >> 4) === TILE_HAZARD;

      var distancia = 9999;
      for (var k = 0; k < w.entityCount; k++) {
        var e = w.entities[k];
        if (!e.active || e.kind !== 0) continue;
        var dx = NPCore.F2I(e.x) - NPCore.F2I(p.x);
        var dy = Math.abs(NPCore.F2I(e.y) - NPCore.F2I(p.y));
        if (dx > 0 && dx < distancia && dy < 40) distancia = dx;
      }

      if (p.onGround && (pared || hueco || peligro || distancia < 34)) {
        input |= NPCore.IN.JUMP;
        saltando = 1;
      } else if (saltando && !p.onGround && p.vy < 0) {
        input |= NPCore.IN.JUMP;
      } else if (p.onGround) {
        saltando = 0;
      }

      w.step(input);

      if (w.state === NPCore.STATE.LEVEL_END || w.state === NPCore.STATE.FINISHED) {
        return { ok: true, frames: i, muertes: muertes, avance: NPCore.F2I(w.players[0].x) };
      }
      if (w.state === NPCore.STATE.DYING) {
        muertes++;
        var donde = NPCore.F2I(w.players[0].x);
        if (muertes > maxMuertes) {
          return { ok: false, motivo: "el bot muere una y otra vez", muertes: muertes,
                   avance: maxX, x: donde };
        }
        while (w.state !== NPCore.STATE.PLAY && w.state !== NPCore.STATE.GAME_OVER &&
               w.state !== NPCore.STATE.TITLE) w.step(0);
        if (w.state !== NPCore.STATE.PLAY) {
          return { ok: false, motivo: "se queda sin vidas", muertes: muertes,
                   avance: maxX, x: donde };
        }
        w.players[0].lives = data.lives;
        maxX = 0;
        continue;
      }
      if (NPCore.F2I(w.players[0].x) > maxX) { maxX = NPCore.F2I(w.players[0].x); sinAvanzar = 0; }
      else if (++sinAvanzar > 600) {
        return { ok: false, motivo: motivo("se queda atascado"), muertes: muertes,
                 avance: maxX, x: maxX };
      }
    }
    return { ok: false, motivo: motivo("no llega a la meta a tiempo"),
             muertes: muertes, avance: maxX, x: maxX };
  }

  var api = { jugar: jugar };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.NPBot = api;
})(typeof window !== "undefined" ? window : this);
