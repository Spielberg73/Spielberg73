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
    /* Si el juego lleva ataque, el bot pega a lo que se le pone delante. Sin
       esto, en un juego de latigo -donde no se pisa a los enemigos- se metia
       de cabeza en el primero y moria una y otra vez: el nivel era perfecto y
       el que no sabia jugar era el bot. */
    var ataque = data.player.attack && data.player.attack.kind ? data.player.attack : null;
    var esperaGolpe = ataque ? (ataque.cooldown || 20) + 2 : 0;
    /* A que distancia merece la pena atacar. Con un cuerpo a cuerpo es el
       alcance del golpe y poco mas: pararse antes es pegarle al aire mientras
       el enemigo te alcanza, que es justo como moria el bot. Con un disparo da
       igual, porque el proyectil hace el viaje. */
    var alcance = !ataque ? 0
                : (ataque.kind === 2 ? (ataque.range || 24) + 10
                                     : Math.max(48, ataque.range || 96));
    var golpeCd = 0;

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

      /* Lo que hay delante y lo que hay detras. Lo de detras importa porque un
         perseguidor se te cruza: cuando te adelanta deja de estar delante, y
         un bot que solo mira hacia delante lo deja vivo y se va. */
      var distancia = 9999, detras = 9999;
      for (var k = 0; k < w.entityCount; k++) {
        var e = w.entities[k];
        if (!e.active || e.kind !== 0) continue;
        var dx = NPCore.F2I(e.x) - NPCore.F2I(p.x);
        var dy = Math.abs(NPCore.F2I(e.y) - NPCore.F2I(p.y));
        if (dy >= 40) continue;
        if (dx > 0) { if (dx < distancia) distancia = dx; }
        else if (-dx < detras) detras = -dx;
      }

      /* Pegar a lo que viene de frente, respetando la cadencia. Y **pararse
         mientras**: si sigue andando se cruza con el enemigo, se lo deja
         detras y ya no le puede pegar -que es como se le escapaba vivo el jefe
         del segundo nivel-. Es ademas lo que hace un jugador. */
      if (golpeCd) golpeCd--;
      if (ataque && distancia < alcance) {
        /* Plantarse solo tiene sentido si no se puede pisar: en un juego de
           saltar, pararse delante de un enemigo es peor que saltarlo. */
        if (!data.player.stomp) input = 0;
        if (!golpeCd) {
          input |= NPCore.IN.ACTION;
          golpeCd = esperaGolpe;
        }
      } else if (ataque && !data.player.stomp && detras < alcance) {
        /* se le ha cruzado por detras: darse la vuelta y pegarle ahi */
        input = NPCore.IN.LEFT;
        if (!golpeCd) {
          input |= NPCore.IN.ACTION;
          golpeCd = esperaGolpe;
        }
      }

      /* Saltar por encima de un enemigo solo tiene sentido si se le puede
         pisar; si no, saltarle encima es tirarse a sus brazos. */
      var estorba = data.player.stomp ? distancia < 34
                                      : (!ataque && distancia < 34);
      if (p.onGround && (pared || hueco || peligro || estorba)) {
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
