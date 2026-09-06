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
  var TILE_LOCK = 9;            /* la puerta que pide algo para abrirse */
  var TILE_CLIMB = 10;          /* la liana: se trepa y se coge en el aire */
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
       bot tiene su propia cabeza. Y uno de tortas tampoco: ahi no se avanza
       hasta limpiar la pantalla, asi que hay que pelear. */
    if (data.view === "cinta") return jugarCinta(NPCore, data, nivel, opciones);
    if (data.view === "iso") return jugarIso(NPCore, data, nivel, opciones);
    if (data.view === "cenital") return jugarCenital(NPCore, data, nivel, opciones);
    /* Y un juego con lianas tampoco: lo que hay que coger esta arriba y la
       puerta no se abre hasta tenerlo, asi que no vale con ir a la derecha. */
    if (data.player.climb_speed > 0)
      return jugarLianas(NPCore, data, nivel, opciones);
    var w = NPCore.create(data);
    w.step(NPCore.IN.START);
    if (nivel) w.loadLevel(nivel);
    var pa = data.player.actor;
    var limite = opciones.frames || 6000;
    var maxMuertes = opciones.muertes === undefined ? 6 : opciones.muertes;
    /* Cuanto mira hacia delante antes de saltar. Con el salto de siempre basta
       con mirarse los pies: se corrige en el aire. Con el salto de las
       aventuras **no**, y ademas chocar de lado contra la pared te deja el
       impulso a cero, asi que hay que saltar bastante antes de llegar: mirando
       solo seis pixeles el bot se estampaba contra el primer escalon y volvia
       a caer en el mismo sitio, una y otra vez. */
    var vista = opciones.vista === undefined ? 6 : opciones.vista;
    /* Y lo que mira para las paredes, que es otra cosa: ver un escalon a seis
       pixeles con el salto de las aventuras es estamparse contra el, porque
       chocar de lado deja el impulso a cero y se cae en el mismo sitio. */
    var vistaPared = data.player.air_control ? vista : vista + 20;
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

      /* La pared se mira mas lejos que el suelo **a proposito**: para subir un
         escalon hay que despegar antes de llegar, pero para saltar un hueco o
         unos pinchos hay que despegar en el borde, no dos pasos antes, o se
         cae justo encima. Con el salto de siempre da igual -se corrige en el
         aire-; con el de las aventuras es la diferencia entre pasar y morir. */
      var delante = NPCore.F2I(p.x) + pa.box_w + vistaPared;
      var pared = w.tileKindAt(delante >> 4, medio >> 4) === TILE_SOLID ||
                  w.tileKindAt(delante >> 4, (pies - 2) >> 4) === TILE_SOLID;
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

  /* ------------------------------------------------------------------ *
   * El bot de la vista de cinta (yo contra el barrio).
   *
   * Aqui no vale andar hacia la derecha: la camara no pasa de pantalla
   * mientras quede alguien vivo, asi que el nivel **se pelea**. El bot hace lo
   * que haria cualquiera: si tiene a alguien delante, se cuadra en su misma
   * profundidad y le pega; si no queda nadie a la vista, tira hacia la salida.
   *
   * Cuadrarse antes de pegar no es un detalle: en esta vista dos que no estan
   * a la misma profundidad no se tocan, asi que un bot que solo anduviera
   * hacia la derecha se pasaria el nivel entero dando punetazos al aire.
   * ------------------------------------------------------------------ */
  function jugarCinta(NPCore, data, nivel, opciones) {
    var w = NPCore.create(data);
    w.step(NPCore.IN.START);
    if (nivel) w.loadLevel(nivel);
    var pa = data.player.actor;
    var limite = opciones.frames || 12000;
    var maxMuertes = opciones.muertes === undefined ? 6 : opciones.muertes;
    var ataque = data.player.attack && data.player.attack.kind ? data.player.attack : null;
    var alcance = ataque ? (ataque.range || 16) : 0;
    var muertes = 0, maxX = 0, sinAvanzar = 0, boton = 0;
    /* frames seguidos empujando contra algo sin avanzar: es lo que dice que
       hay que rodear en vez de seguir insistiendo */
    var rozando = 0, antesX = -1;

    for (var i = 0; i < limite; i++) {
      var p = w.players[0];
      var cx = NPCore.F2I(p.x), cy = NPCore.F2I(p.y);
      var input = 0;

      /* Con alguien agarrado no hay nada que decidir: se le lanza. Es el golpe
         mas fuerte del genero y ademas te lo quita de encima, que es de lo que
         va agarrar a alguien. */
      if (p.grab) {
        boton = !boton;
        w.step(boton ? NPCore.IN.JUMP : 0);
        continue;
      }

      /* A quien pegarle: el enemigo vivo mas cercano que este en pantalla. */
      var objetivo = null, cerca = 99999;
      for (var k = 0; k < w.entityCount; k++) {
        var e = w.entities[k];
        if (!e.active || e.kind !== KIND_ENEMY || e.knock) continue;
        var ex = NPCore.F2I(e.x) - w.camX;
        if (ex < -16 || ex > 320) continue;          /* fuera de la pantalla */
        var d = Math.abs(NPCore.F2I(e.x) - cx) + Math.abs(NPCore.F2I(e.y) - cy);
        if (d < cerca) { cerca = d; objetivo = e; }
      }

      if (objetivo) {
        var ex2 = NPCore.F2I(objetivo.x), ey2 = NPCore.F2I(objetivo.y);
        var hueco = ex2 - cx;
        /* Lo que hay que hacer para que el punetazo entre: el golpe sale de tu
           borde y mide `alcance`, asi que el otro tiene que estar dentro de esa
           franja. Ni pegado -ahi el puno le pasa por encima- ni a dos pasos. */
        var oa = (data.enemies[objetivo.def] || {}).actor || pa;
        var minimo = 4, maximo = pa.box_w + alcance - 4;
        var aTiro = Math.abs(hueco) >= minimo && Math.abs(hueco) <= maximo;
        /* Y lo que hay que hacer para no cobrar: si el que tienes delante
           **esta preparando** su golpe y estas dentro de su alcance, no se
           cambia el golpe, se sale. Esquivar el aviso es de lo que va este
           genero, y un bot que no lo hiciera diria que la calle es imposible
           cuando lo unico que pasa es que no sabe jugar. */
        var ed = data.enemies[objetivo.def] || {};
        var avisando = objetivo.fase === 2 &&
            Math.abs(hueco) <= oa.box_w + (ed.reach || 0) + 4;
        if (rozando > 20) {
          input |= (rozando & 64) ? NPCore.IN.UP : NPCore.IN.DOWN;
          input |= (ex2 > cx) ? NPCore.IN.RIGHT : NPCore.IN.LEFT;
        } else if (avisando) {
          /* Apartarse **en profundidad** y nada mas: su golpe no llega a otra
             linea, y quedandose al lado se le castiga en cuanto se le acabe.
             Retroceder ademas seria perder el turno: se pasaria la
             recuperacion volviendo a acercarse y no pegaria nunca nadie. */
          input |= (ey2 >= cy) ? NPCore.IN.UP : NPCore.IN.DOWN;
        }
        /* y si no, la profundidad: sin cuadrarse, el punetazo pasa de largo */
        else if (ey2 - cy > 2) input |= NPCore.IN.DOWN;
        else if (cy - ey2 > 2) input |= NPCore.IN.UP;
        else if (!aTiro) {
          input |= (hueco > 0) ? NPCore.IN.RIGHT : NPCore.IN.LEFT;
        } else if (ataque) {
          /* a tiro: se pega, soltando el boton entre golpe y golpe porque el
             ataque va por flanco */
          boton = !boton;
          if (boton) input |= NPCore.IN.ACTION;
        }
      } else {
        /* Pantalla limpia: a por la salida. Y si algo se pone por medio -una
           valla, un contenedor-, se prueba a rodearlo por arriba y por abajo,
           que es lo que haria cualquiera: en esta vista casi todo se rodea
           cambiando de profundidad. */
        input |= NPCore.IN.RIGHT;
        if (rozando > 20) input |= (rozando & 64) ? NPCore.IN.UP : NPCore.IN.DOWN;
      }

      w.step(input);

      if (w.state === NPCore.STATE.LEVEL_END || w.state === NPCore.STATE.FINISHED)
        return { ok: true, frames: i, muertes: muertes, avance: maxX };
      if (w.state === NPCore.STATE.DYING) {
        muertes++;
        if (muertes > maxMuertes) {
          return { ok: false, motivo: "el bot muere una y otra vez",
                   muertes: muertes, avance: maxX, x: maxX };
        }
        while (w.state !== NPCore.STATE.PLAY && w.state !== NPCore.STATE.GAME_OVER &&
               w.state !== NPCore.STATE.TITLE) w.step(0);
        if (w.state !== NPCore.STATE.PLAY) {
          return { ok: false, motivo: "se queda sin vidas", muertes: muertes,
                   avance: maxX, x: maxX };
        }
        w.players[0].lives = data.lives;
        sinAvanzar = 0;
        continue;
      }

      /* "Ir bien" es avanzar por la calle: si no se avanza en mucho rato, o el
         nivel no se puede limpiar o el bot no llega a la salida. */
      var ahora = NPCore.F2I(w.players[0].x);
      rozando = (ahora === antesX) ? rozando + 1 : 0;
      antesX = ahora;
      if (ahora > maxX) { maxX = ahora; sinAvanzar = 0; }
      else if (++sinAvanzar > 900) {
        return { ok: false, motivo: "se queda atascado en la calle",
                 muertes: muertes, avance: maxX, x: ahora };
      }
    }
    return { ok: false, motivo: "no llega a la meta a tiempo",
             muertes: muertes, avance: maxX, x: maxX };
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

  /* ------------------------------------------------------------------ *
   * El bot de la vista isometrica.
   *
   * Es el de cenital con dos cosas mas, que son justo las dos que anade el
   * genero: el suelo tiene **relieve** -asi que una casilla no es "libre" o
   * "pared" sino que esta a una altura, y de una a otra se anda o se salta- y
   * hay **puertas**, que estan cerradas hasta que apareces con lo suyo.
   *
   * Del resto no hay nada que inventar: el mando va a la planta igual que en
   * cenital, asi que ir a una casilla es lo mismo de siempre.
   * ------------------------------------------------------------------ */

  var ESCALON = 6;              /* lo que se sube andando (np_types.h) */
  var SALTABLE = 16;            /* y lo que se sube de un salto */

  /** Lo que levanta una casilla, contando las puertas ya abiertas. */
  function altoDe(w, cx, cy) {
    var lv = w.level;
    if (cx < 0 || cy < 0 || cx >= lv.cells_w || cy >= lv.cells_h) return 999;
    var tile = lv.cells[cy * lv.cells_w + cx];
    if (w.tileVisto(cx, cy) === 0 && w.data.tiles.kind[tile] === TILE_LOCK)
      return 0;
    return w.data.tiles.alto[tile];
  }

  /** Se puede pasar de una casilla a la de al lado? Y hace falta saltar? */
  function pasoIso(w, llevaAlgo, cx, cy, nx, ny) {
    var lv = w.level;
    if (nx < 0 || ny < 0 || nx >= lv.cells_w || ny >= lv.cells_h) return null;
    var tile = lv.cells[ny * lv.cells_w + nx];
    var kind = w.data.tiles.kind[tile];
    if (kind === TILE_HAZARD) return null;          /* los pinchos, ni de broma */
    /* Una puerta cerrada solo se cruza si llevas algo con que abrirla: el
       motor la abre al ponerte delante, asi que basta con contar con ella. */
    if (kind === TILE_LOCK && w.tileVisto(nx, ny) === TILE_LOCK && !llevaAlgo)
      return null;
    var aqui = altoDe(w, cx, cy), alla = altoDe(w, nx, ny);
    if (kind === TILE_LOCK && llevaAlgo) alla = 0;
    var sube = alla - aqui;
    if (sube <= ESCALON) return "anda";             /* bajar es gratis */
    if (sube <= SALTABLE) return "salta";
    return null;
  }

  /**
   * Camino de una casilla a lo que se busque, por los cuatro lados. Devuelve
   * una lista de [x, y, comoSeLlega] o null si no hay manera.
   */
  function caminoIso(w, llevaAlgo, desdeX, desdeY, quiere) {
    if (!quiere)
      quiere = function (x, y) { return w.tileKindAt(x, y) === TILE_GOAL; };
    var an = w.level.cells_w, al = w.level.cells_h;
    var previo = new Int32Array(an * al);
    var salto = new Uint8Array(an * al);
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
        var como = pasoIso(w, llevaAlgo, cx, cy, nx, ny);
        if (!como) continue;
        var nn = ny * an + nx;
        if (visto[nn]) continue;
        visto[nn] = 1;
        previo[nn] = c;
        salto[nn] = como === "salta" ? 1 : 0;
        cola.push(nn);
      }
    }
    if (meta < 0) return null;
    var ruta = [];
    for (var q = meta; q >= 0; q = previo[q])
      ruta.push([q % an, (q / an) | 0, salto[q]]);
    ruta.reverse();
    return ruta;
  }

  /** Que buscar: primero lo que abre la puerta, luego las llaves, luego la
      meta. Se prueba en ese orden y se coge el primero al que haya camino. */
  function objetivosIso(w, data, F2I) {
    var casillas = function (efecto) {
      var sitios = {}, cuantos = 0;
      for (var k = 0; k < w.entityCount; k++) {
        var e = w.entities[k];
        if (!e.active || e.kind !== KIND_ITEM) continue;
        var d = data.items[e.def];
        if (!d || d.effect !== efecto) continue;
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
    var piden = w.level.keys_needed || 0;
    if (piden && w.keys < piden) {
      var llaves = casillas(3);              /* efecto llave */
      if (llaves) lista.push(hacia("la llave", llaves));
    } else {
      lista.push({ nombre: "la meta", quiere: null });
    }
    /* Y lo que se lleva encima: si hay un objeto de esos suelto, se coge. Es
       lo que abre las puertas, y sin el la meta puede no tener camino. */
    var cosas = casillas(8);                 /* efecto llevar */
    if (cosas) lista.unshift(hacia("el talisman", cosas));
    return { lista: lista };
  }

  function jugarIso(NPCore, data, nivel, opciones) {
    var w = NPCore.create(data);
    w.step(NPCore.IN.START);
    if (nivel) w.loadLevel(nivel);
    var pa = data.player.actor;
    var limite = opciones.frames || 12000;
    var maxMuertes = opciones.muertes === undefined ? 6 : opciones.muertes;
    var muertes = 0, ruta = null, paso = 0, recalcular = 0;
    var voy = "", mejorFalta = 99999, sinAvanzar = 0;

    function llevaAlgo() {
      for (var i = 0; i < w.bolsa.length; i++) if (w.bolsa[i]) return 1;
      return 0;
    }

    for (var i = 0; i < limite; i++) {
      var p = w.players[0];
      var cx = NPCore.F2I(p.x) + (pa.box_w >> 1);
      var cy = NPCore.F2I(p.y) + (pa.box_h >> 1);
      var tx = cx >> 4, ty = cy >> 4;

      if (!ruta || recalcular <= 0) {
        var busca = objetivosIso(w, data, NPCore.F2I);
        ruta = null;
        for (var o = 0; o < busca.lista.length && !ruta; o++) {
          ruta = caminoIso(w, llevaAlgo(), tx, ty, busca.lista[o].quiere);
          if (ruta && voy !== busca.lista[o].nombre) {
            voy = busca.lista[o].nombre;
            mejorFalta = 99999;
          }
        }
        paso = 0;
        recalcular = 45;
        if (!ruta) {
          return { ok: false, muertes: muertes, avance: 0, y: cy,
                   motivo: "no hay camino hasta "
                           + busca.lista[busca.lista.length - 1].nombre };
        }
      }
      recalcular--;

      while (paso < ruta.length - 1 &&
             ruta[paso][0] === tx && ruta[paso][1] === ty) paso++;
      var destino = ruta[Math.min(paso, ruta.length - 1)];
      var dx = (destino[0] * 16 + 8) - cx;
      var dy = (destino[1] * 16 + 8) - cy;

      /* Un eje cada vez, como en cenital: la caja mide diez en casillas de
         dieciseis y en diagonal se engancha en las esquinas de los cubos. */
      var input = 0;
      if (destino[0] !== tx) {
        if (dy < -2) input |= NPCore.IN.UP;
        else if (dy > 2) input |= NPCore.IN.DOWN;
        else input |= dx < 0 ? NPCore.IN.LEFT : NPCore.IN.RIGHT;
      } else if (dx < -2) input |= NPCore.IN.LEFT;
      else if (dx > 2) input |= NPCore.IN.RIGHT;
      else if (dy < -2) input |= NPCore.IN.UP;
      else if (dy > 2) input |= NPCore.IN.DOWN;

      /* Y si la casilla a la que se va esta mas alta, se salta. Pero no vale
         con estar en el suelo y andar hacia ella: en esta vista **el salto no
         se corrige en el aire**, asi que se despega con la velocidad que se
         lleve encima y se cae donde sea. Un bot que salta en cuanto puede sale
         de lado, aterriza en la casilla de al lado, vuelve a intentarlo y se
         queda dando tumbos delante del mismo cubo.

         Asi que antes de saltar se endereza: se anda por el eje que toca hasta
         estar en la linea de la casilla y con el **otro eje parado del todo**.
         Como la friccion se come la velocidad en dos frames, esperar a que sea
         cero no cuesta casi nada y a cambio el salto sale recto. */
      if (destino[2] && p.onGround && input) {
        var porX = destino[0] !== tx;        /* el salto va por el eje x */
        var derecho = porX ? (dy > -3 && dy < 3 && p.vy === 0)
                           : (dx > -3 && dx < 3 && p.vx === 0);
        if (derecho) input |= NPCore.IN.JUMP;
      }

      w.step(input);

      if (w.state === NPCore.STATE.LEVEL_END || w.state === NPCore.STATE.FINISHED)
        return { ok: true, frames: i, muertes: muertes, avance: cy };
      if (w.state === NPCore.STATE.DYING) {
        muertes++;
        if (muertes > maxMuertes)
          return { ok: false, motivo: "el bot muere una y otra vez",
                   muertes: muertes, avance: cy, y: cy };
        while (w.state !== NPCore.STATE.PLAY && w.state !== NPCore.STATE.GAME_OVER &&
               w.state !== NPCore.STATE.TITLE) w.step(0);
        if (w.state !== NPCore.STATE.PLAY)
          return { ok: false, motivo: "se queda sin vidas", muertes: muertes,
                   avance: cy, y: cy };
        w.players[0].lives = data.lives;
        ruta = null; mejorFalta = 99999; sinAvanzar = 0;
        continue;
      }

      var falta = ruta.length - 1 - paso;
      if (falta < mejorFalta) { mejorFalta = falta; sinAvanzar = 0; }
      else if (++sinAvanzar > 700) {
        return { ok: false, motivo: "se queda atascado yendo a " + voy,
                 muertes: muertes, avance: cy, y: cy };
      }
    }
    return { ok: false, motivo: "no llega a la meta a tiempo",
             muertes: muertes, avance: 0, y: 0 };
  }


  /* ------------------------------------------------------------------ *
   * El bot de los juegos con lianas.
   *
   * El de lado normal anda hacia la derecha y salta lo que se le pone
   * delante, y con eso basta cuando el camino es el camino. En un juego de
   * kung-fu no lo es: lo que hay que coger esta **arriba**, en una viga o al
   * final de una liana, y la puerta no se abre hasta tenerlo todo. Un bot que
   * solo sabe ir hacia la derecha se planta delante de la salida cerrada sin
   * entender por que.
   *
   * Asi que este busca el camino de verdad, como el de la vista cenital, pero
   * por un mapa de lado: las casillas no se tocan por los cuatro lados sino
   * que se **anda**, se **salta** o se **trepa**, que son las tres maneras de
   * moverse que tiene el jugador. Lo demas es lo mismo: se busca lo que falta,
   * se va a por ello y, cuando ya no falta nada, a la meta.
   * ------------------------------------------------------------------ */

  var SUBE_SALTO = 2;           /* casillas que sube un salto */
  var BAJA_SALTO = 3;           /* y las que se puede caer de un salto */
  var LARGO_SALTO = 3;          /* y lo que se llega de largo */

  function piso(w, x, y) {
    var k = w.tileKindAt(x, y);
    return k === TILE_SOLID || k === TILE_PLATFORM;
  }

  function seguro(w, x, y) {
    var k = w.tileKindAt(x, y);
    return k !== TILE_SOLID && k !== TILE_HAZARD;
  }

  function esLiana(w, x, y) { return w.tileKindAt(x, y) === TILE_CLIMB; }

  /** Una casilla en la que se puede estar de pie: libre y con suelo debajo. */
  function dePie(w, x, y) { return seguro(w, x, y) && piso(w, x, y + 1); }

  /** El pasillo de un salto: se sube por la columna de salida, se cruza por
      arriba y se baja por la de llegada. Es una aproximacion del arco -sube,
      vuela, cae- y peca de prudente a proposito: un salto que este bot da por
      bueno lo da bien cualquiera. */
  function pasilloLibre(w, x0, y0, x1, y1) {
    var alto = Math.min(y0, y1), y, x;
    for (y = alto; y <= y0; y++) if (!seguro(w, x0, y)) return false;
    for (x = Math.min(x0, x1); x <= Math.max(x0, x1); x++)
      if (!seguro(w, x, alto)) return false;
    for (y = alto; y <= y1; y++) if (!seguro(w, x1, y)) return false;
    return true;
  }

  /** Donde se acaba de caer si uno se tira por la casilla (x, y). */
  function dondeCae(w, x, y) {
    var lv = w.level;
    for (var ny = y; ny < lv.cells_h; ny++) {
      if (!seguro(w, x, ny)) return -1;
      if (piso(w, x, ny + 1)) return ny;
    }
    return -1;
  }

  /**
   * Camino desde una casilla hasta lo que se busque, contando las tres formas
   * de moverse. Cada nodo es una casilla **y en que se esta**: de pie o
   * colgado, porque no es lo mismo estar en una casilla pisando el suelo que
   * estar en ella agarrado a una liana.
   *
   * Devuelve una lista de [x, y, colgado, comoSeLlega] o null si no hay
   * manera. `como` es 0 andando, 1 saltando y 2 agarrandose.
   */
  function caminoLateral(w, desdeX, desdeY, colgado, quiere) {
    var an = w.level.cells_w, al = w.level.cells_h;
    var n = an * al * 2;
    var previo = new Int32Array(n), como = new Uint8Array(n);
    var visto = new Uint8Array(n);
    var nodo = function (x, y, c) { return (y * an + x) * 2 + c; };
    var inicio = nodo(desdeX, desdeY, colgado ? 1 : 0);
    var cola = [inicio], cabeza = 0, meta = -1;
    visto[inicio] = 1;
    previo[inicio] = -1;

    function mete(desde, x, y, c, forma) {
      if (x < 0 || y < 0 || x >= an || y >= al) return;
      var nn = nodo(x, y, c);
      if (visto[nn]) return;
      visto[nn] = 1;
      previo[nn] = desde;
      como[nn] = forma;
      cola.push(nn);
    }

    while (cabeza < cola.length) {
      var c = cola[cabeza++];
      var cc = c & 1, celda = c >> 1;
      var cx = celda % an, cy = (celda / an) | 0;
      if (quiere(cx, cy)) { meta = c; break; }

      if (cc) {
        /* Colgado de una liana: se sube, se baja y se salta a un lado. */
        if (esLiana(w, cx, cy - 1)) mete(c, cx, cy - 1, 1, 2);
        if (esLiana(w, cx, cy + 1)) mete(c, cx, cy + 1, 1, 2);
        if (dePie(w, cx, cy)) mete(c, cx, cy, 0, 0);
        for (var s = -1; s <= 1; s += 2) {
          for (var dx = 1; dx <= LARGO_SALTO; dx++) {
            /* Desde una liana solo se cuenta con subir **una** casilla, y no
               dos como desde el suelo. Colgado uno no esta pisando nada: la
               altura de la que despega es la que tenga en ese momento, no la
               del borde de la casilla, y un salto que sube justo lo justo se
               queda a un pixel de la viga. Subir un poco mas por la liana es
               gratis, asi que el camino que se planea es el seguro. */
            for (var dy = -1; dy <= 4; dy++) {
              var nx = cx + s * dx, ny = cy + dy;
              if (!dePie(w, nx, ny)) continue;
              if (!pasilloLibre(w, cx, cy, nx, ny)) continue;
              mete(c, nx, ny, 0, 1);
            }
          }
        }
        continue;
      }

      /* De pie: andar al lado, dejarse caer, saltar y agarrarse. */
      for (var s2 = -1; s2 <= 1; s2 += 2) {
        var lx = cx + s2;
        if (dePie(w, lx, cy)) mete(c, lx, cy, 0, 0);
        else if (seguro(w, lx, cy)) {
          var caida = dondeCae(w, lx, cy);
          if (caida >= 0) mete(c, lx, caida, 0, 0);
        }
        /* Los saltos. `jx = 0` es saltar en el sitio, que sirve para subirse
           a una plataforma de las de atravesar que este justo encima; y
           `jy = 0` es cruzar un foso de frente, que es lo que mas se hace. Los
           de `jy` negativo son los que caen mas abajo de donde se despega:
           tambien son saltos, y sin ellos un escalon hacia abajo con un hueco
           delante no tiene manera de bajarse. */
        for (var jx = 0; jx <= LARGO_SALTO; jx++) {
          for (var jy = -BAJA_SALTO; jy <= SUBE_SALTO; jy++) {
            if (!jx && jy <= 0) continue;
            var sx = cx + s2 * jx, sy = cy - jy;
            if (!dePie(w, sx, sy)) continue;
            if (!pasilloLibre(w, cx, cy, sx, sy)) continue;
            mete(c, sx, sy, 0, 1);
          }
        }
      }
      /* Agarrarse a una liana: la de la propia casilla, la de al lado o una
         que pase por encima al alcance del salto. Esto es lo que una escalera
         no deja hacer y lo que hace que las lianas sean otra cosa. */
      for (var ax = -2; ax <= 2; ax++) {
        for (var ay = -SUBE_SALTO; ay <= 0; ay++) {
          var ex = cx + ax, ey = cy + ay;
          if (!esLiana(w, ex, ey)) continue;
          if (!pasilloLibre(w, cx, cy, ex, ey)) continue;
          mete(c, ex, ey, 1, ax === 0 && ay === 0 ? 2 : 1);
        }
      }
    }

    if (meta < 0) return null;
    var ruta = [];
    for (var q = meta; q >= 0; q = previo[q])
      ruta.push([(q >> 1) % an, ((q >> 1) / an) | 0, q & 1, como[q]]);
    ruta.reverse();
    return ruta;
  }

  /** Que buscar: mientras falten llaves, la llave mas cercana; luego la meta.
      Es el orden de un juego de faroles: primero apagarlos y luego salir. */
  function objetivoLateral(w, data, F2I) {
    var piden = w.level.keys_needed || 0;
    if (piden && w.keys < piden) {
      var sitios = {}, hay = 0;
      for (var k = 0; k < w.entityCount; k++) {
        var e = w.entities[k];
        if (!e.active || e.kind !== KIND_ITEM) continue;
        var d = data.items[e.def];
        if (!d || d.effect !== 3) continue;         /* efecto llave */
        sitios[(F2I(e.y) >> 4) * 1024 + (F2I(e.x) >> 4)] = 1;
        hay++;
      }
      if (hay) {
        return { nombre: "el farol",
                 quiere: function (x, y) { return sitios[y * 1024 + x] === 1; } };
      }
    }
    return { nombre: "la meta",
             quiere: function (x, y) { return w.tileKindAt(x, y) === TILE_GOAL; } };
  }

  function jugarLianas(NPCore, data, nivel, opciones) {
    var w = NPCore.create(data);
    w.step(NPCore.IN.START);
    if (nivel) w.loadLevel(nivel);
    var pa = data.player.actor;
    var limite = opciones.frames || 20000;
    var maxMuertes = opciones.muertes === undefined ? 8 : opciones.muertes;
    var ataque = data.player.attack && data.player.attack.kind ? data.player.attack : null;
    var esperaGolpe = ataque ? (ataque.cooldown || 20) + 2 : 0;
    var alcance = ataque ? (ataque.range || 24) + 12 : 0;
    var golpeCd = 0, muertes = 0;
    var ruta = null, paso = 0, recalcular = 0, saltando = 0;
    var voy = "", mejorFalta = 99999, sinAvanzar = 0, llavesVistas = -1;

    for (var i = 0; i < limite; i++) {
      var p = w.players[0];
      var cx = NPCore.F2I(p.x) + (pa.box_w >> 1);
      var cy = NPCore.F2I(p.y) + (pa.box_h >> 1);
      var tx = cx >> 4, ty = cy >> 4;

      /* El camino se vuelve a pensar con los pies en el suelo o colgado de
         una liana, no en mitad de un salto: en el aire la casilla en la que
         se esta no es una casilla en la que se pueda estar, y el camino que
         sale de ahi manda hacia un lado mientras uno cae. Asi es como el bot
         se tiraba a los pinchos: iba bien a su casilla y a mitad de caida le
         cambiaban el destino. */
      if (!ruta || (recalcular <= 0 && (p.onGround || p.trepa))) {
        var busca = objetivoLateral(w, data, NPCore.F2I);
        var desdeY = ty;
        if (!p.onGround && !p.trepa) {
          var caida = dondeCae(w, tx, ty);
          if (caida >= 0) desdeY = caida;
        }
        ruta = caminoLateral(w, tx, desdeY, p.trepa, busca.quiere);
        paso = 0;
        recalcular = 40;
        if (voy !== busca.nombre) { voy = busca.nombre; mejorFalta = 99999; }
        if (!ruta) {
          return { ok: false, muertes: muertes, avance: cx, x: cx,
                   motivo: "no hay camino hasta " + busca.nombre };
        }
      }
      recalcular--;

      /* Por donde va la ruta. Se busca **la casilla mas avanzada** que sea la
         de ahora, no la siguiente sin mas: un salto se come dos o tres
         casillas de golpe, y un bot que solo mira el paso siguiente se queda
         apuntando a una casilla que ya dejo atras y va y vuelve sin parar. */
      for (var q = ruta.length - 1; q >= 0; q--) {
        if (ruta[q][0] === tx && ruta[q][1] === ty &&
            ruta[q][2] === (p.trepa ? 1 : 0)) {
          paso = Math.min(q + 1, ruta.length - 1);
          break;
        }
      }
      var destino = ruta[Math.min(paso, ruta.length - 1)];
      var dx2 = (destino[0] * 16 + 8) - cx;
      var dy2 = (destino[1] * 16 + 8) - cy;
      var input = 0;

      if (p.trepa) {
        /* Colgado. Si el siguiente paso sigue en la liana se sube o se baja;
           si no, se salta hacia el, que es la unica manera de soltarse con
           impulso. */
        if (destino[2]) {
          if (dy2 < -3) input |= NPCore.IN.UP;
          else if (dy2 > 3) input |= NPCore.IN.DOWN;
          else {
            input |= NPCore.IN.JUMP | (dx2 < 0 ? NPCore.IN.LEFT : NPCore.IN.RIGHT);
            saltando = 1;
          }
        } else {
          input |= NPCore.IN.JUMP;
          saltando = 1;         /* y se mantiene: soltarlo corta el salto */
          if (dx2 < -4) input |= NPCore.IN.LEFT;
          else if (dx2 > 4) input |= NPCore.IN.RIGHT;
        }
      } else if (destino[2]) {
        /* Yendo a por una liana: se anda hasta su columna con arriba pulsado,
           que es lo que hace que se agarre en cuanto la toca -en el suelo o en
           el aire, que da igual-. */
        input |= NPCore.IN.UP;
        if (dx2 < -3) input |= NPCore.IN.LEFT;
        else if (dx2 > 3) input |= NPCore.IN.RIGHT;
        /* Si la liana esta por encima, se salta hacia ella: se agarra en el
           aire, que es lo que la separa de una escalera. No hace falta estar
           debajo, porque en el aire todavia se manda. */
        if (dy2 < -8 && p.onGround) { input |= NPCore.IN.JUMP; saltando = 1; }
        else if (saltando && !p.onGround && p.vy < 0) input |= NPCore.IN.JUMP;
      } else {
        if (dx2 < -3) input |= NPCore.IN.LEFT;
        else if (dx2 > 3) input |= NPCore.IN.RIGHT;
        if (destino[3] === 1 && p.onGround) { input |= NPCore.IN.JUMP; saltando = 1; }
        else if (saltando && !p.onGround && p.vy < 0) input |= NPCore.IN.JUMP;
        else if (p.onGround) saltando = 0;
      }

      /* Y pegar a lo que se ponga al lado. Aqui no se pisa a nadie, asi que
         quitarse de en medio a golpes no es opcional: es como se anda. */
      if (golpeCd) golpeCd--;
      if (ataque && !p.trepa) {
        for (var k2 = 0; k2 < w.entityCount; k2++) {
          var en = w.entities[k2];
          if (!en.active || en.kind !== KIND_ENEMY) continue;
          var ex2 = NPCore.F2I(en.x) - NPCore.F2I(p.x);
          var ey2 = Math.abs(NPCore.F2I(en.y) - NPCore.F2I(p.y));
          if (ey2 >= 24 || Math.abs(ex2) > alcance) continue;
          if (!golpeCd) { input |= NPCore.IN.ACTION; golpeCd = esperaGolpe; }
          break;
        }
      }

      w.step(input);

      if (w.state === NPCore.STATE.LEVEL_END || w.state === NPCore.STATE.FINISHED)
        return { ok: true, frames: i, muertes: muertes, avance: cx };
      if (w.state === NPCore.STATE.DYING) {
        muertes++;
        if (muertes > maxMuertes)
          return { ok: false, motivo: "el bot muere una y otra vez",
                   muertes: muertes, avance: cx, x: cx };
        while (w.state !== NPCore.STATE.PLAY && w.state !== NPCore.STATE.GAME_OVER &&
               w.state !== NPCore.STATE.TITLE) w.step(0);
        if (w.state !== NPCore.STATE.PLAY)
          return { ok: false, motivo: "se queda sin vidas", muertes: muertes,
                   avance: cx, x: cx };
        w.players[0].lives = data.lives;
        ruta = null; mejorFalta = 99999; sinAvanzar = 0;
        continue;
      }

      /* Ir bien es que mengue lo que falta de camino, pero al apagar un farol
         el objetivo cambia y el camino nuevo puede ser mas largo que el que
         acaba de terminarse. Sin esto el bot se daba por atascado justo
         despues de conseguir algo, que es lo contrario de estar atascado. */
      if (w.keys !== llavesVistas) {
        llavesVistas = w.keys;
        mejorFalta = 99999;
        sinAvanzar = 0;
      }
      var falta = ruta.length - 1 - paso;
      if (falta < mejorFalta) { mejorFalta = falta; sinAvanzar = 0; }
      else if (++sinAvanzar > 900) {
        var piden = w.level.keys_needed || 0;
        return { ok: false, muertes: muertes, avance: cx, x: cx,
                 motivo: "se queda atascado yendo a " + voy
                         + (piden ? " (lleva " + w.keys + " de " + piden + ")" : "") };
      }
    }
    return { ok: false, motivo: "no llega a la meta a tiempo",
             muertes: muertes, avance: cx, x: cx };
  }

  /* El buscacaminos de lado se exporta aparte: lo usan las pruebas del kit
     para saber si un mapa con lianas tiene camino sin tener que jugarlo. */
  var api = { jugar: jugar, caminoLateral: caminoLateral };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.NPBot = api;
})(typeof window !== "undefined" ? window : this);
