/* np_bot.js - un jugador automatico que intenta terminarse un nivel.
 *
 * Hay dos, uno por vista. De lado hace lo que haria alguien la primera vez:
 * andar hacia la derecha y saltar cuando ve una pared, un hueco, pinchos o un
 * enemigo. Desde arriba no hay saltos que medir sino un camino que tuerce, asi
 * que ese busca el paso hasta la meta, sube y dispara a lo que se le acerca.
 * En los dos casos vale lo mismo: si el bot llega a la meta, una persona
 * tambien puede.
 *
 * Lo usan dos sitios: las pruebas del kit (tests/nivel_jugable.js) y el boton
 * "¿se puede terminar?" del editor.
 */
(function (root) {
  "use strict";

  var TILE_SOLID = 1, TILE_PLATFORM = 2, TILE_HAZARD = 3, TILE_GOAL = 4;
  var KIND_ENEMY = 0, KIND_ITEM = 1, KIND_PRISONER = 8;

  /**
   * @param NPCore  el motor (preview/np_core.js)
   * @param data    los datos del juego
   * @param nivel   indice del nivel
   * @param opciones {frames, muertes, vista}
   */
  function jugar(NPCore, data, nivel, opciones) {
    opciones = opciones || {};
    /* Un juego de comando no se juega andando hacia la derecha: se sube. Ese
       bot tiene su propia cabeza. */
    if (data.view === "cenital") return jugarCenital(NPCore, data, nivel, opciones);
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
        if (!e.active || e.kind !== KIND_ENEMY) continue;
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

  /* ------------------------------------------------------------------ *
   * El bot de vista cenital.
   *
   * Aqui no hay saltos que medir: hay un camino que tuerce. Asi que este bot
   * hace lo que hace una persona que ve la pantalla entera: mira por donde se
   * puede pasar, se va hacia la meta y dispara a lo que se le acerca. Si no
   * llega, es que el nivel no tiene camino o que mata demasiado.
   * ------------------------------------------------------------------ */

  /** Casillas por las que se puede andar: ni solido ni peligro. */
  function libre(w, tx, ty) {
    var k = w.tileKindAt(tx, ty);
    return k !== TILE_SOLID && k !== TILE_HAZARD;
  }

  /**
   * Camino mas corto de una casilla a **lo que se busque**, en anchura y por
   * los cuatro lados (nada de diagonales: rozarian las esquinas). Devuelve la
   * lista de casillas o null si no hay camino, que es justo lo que interesa
   * saber de un nivel dibujado a mano.
   *
   * `quiere(x, y)` dice si esa casilla vale. Por defecto es la meta, pero en
   * una mazmorra tambien se va a por una llave o a por comida.
   */
  function camino(w, desdeX, desdeY, quiere) {
    if (!quiere) quiere = function (x, y) { return w.tileKindAt(x, y) === TILE_GOAL; };
    var an = w.level.width, al = w.level.height;
    var previo = new Int32Array(an * al);
    var visto = new Uint8Array(an * al);
    var cola = [desdeY * an + desdeX];
    var meta = -1, cabeza = 0;
    visto[cola[0]] = 1;
    previo[cola[0]] = -1;
    while (cabeza < cola.length) {
      var c = cola[cabeza++];
      var cx = c % an, cy = (c / an) | 0;
      if (quiere(cx, cy)) { meta = c; break; }
      var lados = [[cx - 1, cy], [cx + 1, cy], [cx, cy - 1], [cx, cy + 1]];
      for (var i = 0; i < 4; i++) {
        var nx = lados[i][0], ny = lados[i][1];
        if (nx < 0 || ny < 0 || nx >= an || ny >= al) continue;
        var n = ny * an + nx;
        if (visto[n] || !libre(w, nx, ny)) continue;
        visto[n] = 1; previo[n] = c; cola.push(n);
      }
    }
    if (meta < 0) return null;
    var ruta = [];
    for (var q = meta; q >= 0; q = previo[q]) ruta.push([q % an, (q / an) | 0]);
    ruta.reverse();
    return ruta;
  }

  /**
   * Que buscar, por orden de preferencia. En un juego de comando siempre es la
   * meta; en una mazmorra hay que decidir, que es de lo que va el genero:
   *
   *   1. si la vida se gasta sola y queda poca, **comida** antes que nada
   *   2. si la meta pide llaves y no se tienen, la **llave** (y aqui la meta
   *      ya no vale de recambio: cerrada no se abre)
   *   3. y si no, la meta
   *
   * Va una lista y no un objetivo suelto porque lo de arriba puede estar
   * encerrado: quien llama se queda con el primero al que haya camino. Si lo
   * que falta no esta en el nivel, devuelve {falta: "..."} y no hay mas que
   * hablar.
   */
  function objetivos(w, data, F2I) {
    var p = w.players[0];
    var casillas = function (efecto) {
      var sitios = {}, cuantos = 0;
      for (var k = 0; k < w.entityCount; k++) {
        var e = w.entities[k];
        if (!e.active || e.kind !== KIND_ITEM) continue;
        var d = data.items[e.def];
        if (!d || d.effect !== efecto) continue;
        /* la casilla, en una sola clave: los niveles llegan a 512 de ancho,
           asi que el hueco para la x tiene que ser de 1024 y no de 256 */
        sitios[(F2I(e.y) >> 4) * 1024 + (F2I(e.x) >> 4)] = 1;
        cuantos++;
      }
      return cuantos ? sitios : null;
    };
    var hacia = function (nombre, sitios) {
      return { nombre: nombre,
               quiere: function (x, y) { return sitios[y * 1024 + x] === 1; } };
    };
    var lista = [];
    if (data.player.wear && p.health * 5 < data.player.health * 2) {
      var comida = casillas(2);              /* efecto salud */
      if (comida) lista.push(hacia("la comida", comida));
    }
    var piden = w.level.keys_needed || 0;
    if (piden && w.keys < piden) {
      var llaves = casillas(3);              /* efecto llave */
      if (!llaves)
        return { falta: "le faltan llaves para abrir la meta y no queda "
                        + "ninguna a mano: tiene " + w.keys + " de " + piden };
      lista.push(hacia("la llave", llaves));
    } else {
      lista.push({ nombre: "la meta", quiere: null });
    }
    return { lista: lista };
  }

  function jugarCenital(NPCore, data, nivel, opciones) {
    var w = NPCore.create(data);
    w.step(NPCore.IN.START);
    if (nivel) w.loadLevel(nivel);
    var pa = data.player.actor;
    var limite = opciones.frames || 9000;
    var maxMuertes = opciones.muertes === undefined ? 6 : opciones.muertes;
    var ataque = data.player.attack && data.player.attack.kind ? data.player.attack : null;
    var esperaGolpe = ataque ? (ataque.cooldown || 10) + 1 : 0;
    var alcance = ataque ? Math.max(96, ataque.range || 160) : 0;
    var golpeCd = 0, muertes = 0, mejorY = 99999, sinAvanzar = 0;
    var ruta = null, paso = 0, recalcular = 0;
    var voy = "", mejorFalta = 99999;

    function centroX(p) { return NPCore.F2I(p.x) + (pa.box_w >> 1); }
    function centroY(p) { return NPCore.F2I(p.y) + (pa.box_h >> 1); }

    for (var i = 0; i < limite; i++) {
      var p = w.players[0];
      var cx = centroX(p), cy = centroY(p);
      var tx = cx >> 4, ty = cy >> 4;

      /* El camino se recalcula de vez en cuando: al empezar, al morir y al
         perder el hilo. El mapa no cambia, pero el jugador si se mueve, y en
         una mazmorra lo que se busca tampoco es siempre lo mismo: primero la
         comida o la llave, y la meta al final. */
      if (!ruta || recalcular <= 0) {
        var busca = objetivos(w, data, NPCore.F2I);
        if (busca.falta) {
          return { ok: false, motivo: busca.falta, muertes: muertes,
                   avance: mejorY === 99999 ? 0 : mejorY, y: cy };
        }
        ruta = null;
        for (var o = 0; o < busca.lista.length && !ruta; o++) {
          ruta = camino(w, tx, ty, busca.lista[o].quiere);
          if (ruta && voy !== busca.lista[o].nombre) {
            voy = busca.lista[o].nombre;
            mejorFalta = 99999;
          }
        }
        paso = 0;
        recalcular = 60;
        if (!ruta) {
          return { ok: false, muertes: muertes, avance: 0, y: cy,
                   motivo: "no hay camino andando hasta "
                           + busca.lista[busca.lista.length - 1].nombre };
        }
      }
      recalcular--;

      /* Avanzar por la ruta: la casilla objetivo es la siguiente que aun no
         se ha pisado. */
      while (paso < ruta.length - 1 &&
             ruta[paso][0] === tx && ruta[paso][1] === ty) paso++;
      var destino = ruta[Math.min(paso, ruta.length - 1)];
      var dx = (destino[0] * 16 + 8) - cx;
      var dy = (destino[1] * 16 + 8) - cy;

      /* Se anda por un eje cada vez, y antes de cruzar se cuadra en el otro.
         La caja del heroe mide doce de alto en casillas de dieciseis: dos
         pixeles descuadrado y una esquina de sacos le muerde el paso. En
         diagonal el bot se quedaba clavado contra un muro que en la pantalla
         se ve libre. */
      var input = 0;
      if (destino[0] !== tx) {
        if (dy < -1) input |= NPCore.IN.UP;
        else if (dy > 1) input |= NPCore.IN.DOWN;
        else input |= dx < 0 ? NPCore.IN.LEFT : NPCore.IN.RIGHT;
      } else {
        if (dx < -1) input |= NPCore.IN.LEFT;
        else if (dx > 1) input |= NPCore.IN.RIGHT;
        else if (dy < -1) input |= NPCore.IN.UP;
        else if (dy > 1) input |= NPCore.IN.DOWN;
        else input |= NPCore.IN.UP;        /* ya esta encima: seguir subiendo */
      }

      /* Disparar a lo que se acerca, respetando la cadencia. Se dispara hacia
         donde se anda, asi que lo que importa de un rehen atado no es que este
         cerca, sino que este **en la linea de tiro**: mirar solo la distancia
         dejaba al bot sin disparar con un preso a dos casillas al lado,
         clavado y acribillado. */
      if (golpeCd) golpeCd--;
      var ix = (input & NPCore.IN.RIGHT ? 1 : 0) - (input & NPCore.IN.LEFT ? 1 : 0);
      var iy = (input & NPCore.IN.DOWN ? 1 : 0) - (input & NPCore.IN.UP ? 1 : 0);
      var largoMira = Math.sqrt(ix * ix + iy * iy) || 1;
      var cerca = 99999, enLaLinea = 0;
      for (var k = 0; k < w.entityCount; k++) {
        var e = w.entities[k];
        if (!e.active) continue;
        var ex = NPCore.F2I(e.x) - cx, ey = NPCore.F2I(e.y) - cy;
        if (e.kind === KIND_ENEMY) {
          var d = Math.abs(ex) + Math.abs(ey);
          if (d < cerca) cerca = d;
        } else if (e.kind === KIND_PRISONER && !e.timer) {
          var largo = Math.sqrt(ex * ex + ey * ey);
          if (largo < 72 && (ex * ix + ey * iy) > 0.85 * largo * largoMira)
            enLaLinea = 1;
        }
      }
      if (ataque && !golpeCd && cerca < alcance && !enLaLinea) {
        input |= NPCore.IN.ACTION;
        golpeCd = esperaGolpe;
      }

      w.step(input);

      if (w.state === NPCore.STATE.LEVEL_END || w.state === NPCore.STATE.FINISHED) {
        return { ok: true, frames: i, muertes: muertes,
                 avance: mejorY === 99999 ? 0 : mejorY };
      }
      if (w.state === NPCore.STATE.DYING) {
        muertes++;
        if (muertes > maxMuertes) {
          return { ok: false, motivo: "el bot muere una y otra vez",
                   muertes: muertes, avance: mejorY, y: cy };
        }
        while (w.state !== NPCore.STATE.PLAY && w.state !== NPCore.STATE.GAME_OVER &&
               w.state !== NPCore.STATE.TITLE) w.step(0);
        if (w.state !== NPCore.STATE.PLAY) {
          return { ok: false, motivo: "se queda sin vidas", muertes: muertes,
                   avance: mejorY, y: cy };
        }
        w.players[0].lives = data.lives;
        ruta = null; mejorY = 99999; sinAvanzar = 0; mejorFalta = 99999;
        continue;
      }

      /* "Ir bien" no es subir: en una mazmorra se baja a por la llave y se
         vuelve. Lo que tiene que menguar es **lo que falta de camino hasta lo
         que se busca ahora**, y eso se reinicia al cambiar de objetivo. */
      var ahora = centroY(w.players[0]);
      if (ahora < mejorY) mejorY = ahora;
      var falta = ruta.length - 1 - paso;
      if (falta < mejorFalta) { mejorFalta = falta; sinAvanzar = 0; }
      else if (++sinAvanzar > 600) {
        return { ok: false, motivo: "se queda atascado yendo a " + voy,
                 muertes: muertes, avance: mejorY, y: ahora };
      }
    }
    return { ok: false, motivo: "no llega a la meta a tiempo",
             muertes: muertes, avance: mejorY, y: mejorY };
  }

  var api = { jugar: jugar };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.NPBot = api;
})(typeof window !== "undefined" ? window : this);
