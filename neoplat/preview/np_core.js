/* np_core.js - la misma simulacion que engine/core/np_world.c, en JavaScript.
 *
 * Es una traduccion literal, con enteros y coma fija 24.8, para que el preview
 * del navegador se comporte exactamente igual que la ROM de Neo Geo.
 * tests/test_paridad.py compara las dos implementaciones frame a frame: si
 * tocas una, toca la otra.
 */
(function (root) {
  "use strict";

  var FIX_SHIFT = 8;
  var FIX_ONE = 1 << FIX_SHIFT;
  var TILE = 16, TILE_SHIFT = 4;
  var SCREEN_W = 320, SCREEN_H = 224;
  var SUBSTEP = 8 * FIX_ONE;
  var ENTITY_FALL = 8 * FIX_ONE;
  var DYING_TIME = 60, LEVEL_END_TIME = 90, GAME_OVER_TIME = 240;
  var CULL_MARGIN = 64;
  /* Margen de perdon de los pinchos (ver NP_HAZARD_INSET_* en np_world.c). */
  var HAZARD_INSET_X = 2, HAZARD_INSET_Y = 4;
  var MAX_ENTITIES = 64;

  var IN = { LEFT: 1, RIGHT: 2, UP: 4, DOWN: 8, JUMP: 16, ACTION: 32, START: 64 };
  var TILE_EMPTY = 0, TILE_SOLID = 1, TILE_PLATFORM = 2, TILE_HAZARD = 3, TILE_GOAL = 4;
  /* escaleras: la que sube a la derecha y la que sube a la izquierda */
  var TILE_STAIR_R = 6, TILE_STAIR_L = 7;
  /* punto de control: se atraviesa y apunta donde reaparece el jugador */
  var TILE_CHECK = 8;
  /* cerrojo: frena como una pared hasta que llegas con el objeto que pide */
  var TILE_LOCK = 9;
  var TILE_CLIMB = 10;
  var AI_PATROL = 0, AI_FLYER = 1, AI_CHASER = 2, AI_JUMPER = 3;
  /* Las fases del luchador, igual que NP_LUCHA_* en C. */
  var LUCHA_IR = 0, LUCHA_RONDAR = 1, LUCHA_PREPARAR = 2, LUCHA_GOLPEAR = 3,
      LUCHA_RECUPERAR = 4, LUCHA_REPLEGAR = 5;
  /* Lo que se para el mundo al acertar, y lo que tiembla la camara al tumbar. */
  var CONGELADO = 4, CONGELADO_REMATE = 9, SACUDIDA = 10;
  /* Lo que se tambalea el que cobra un golpe. Igual que NP_ATURDE en C. */
  var ATURDE = 16;
  /* La carrera de doble toque. Igual que NP_TOQUE_* y NP_CARRERA_* en C. */
  var TOQUE_VENTANA = 12, CARRERA = 80, CARRERA_X2 = 12;
  var ANIM_IDLE = 0, ANIM_RUN = 1, ANIM_JUMP = 2, ANIM_FALL = 3, ANIM_HURT = 4,
      ANIM_ATTACK = 5, ANIM_STAIR = 6, ANIM_CROUCH = 7,
      /* solo en vista cenital: de espaldas y de frente */
      ANIM_UP = 8, ANIM_DOWN = 9,
      /* el ultimo golpe de una serie, el que tumba */
      ANIM_FINISH = 10, ANIM_KICK = 11;
  var KIND_ENEMY = 0, KIND_ITEM = 1, KIND_SHOT = 2, KIND_PLATFORM = 3;
  var KIND_BREAKABLE = 4, KIND_SUBSHOT = 5, KIND_MELEE = 6;
  var KIND_ENEMY_SHOT = 7;      /* lo que tira un enemigo con `dispara:` */
  var KIND_PRISONER = 8;        /* el rehen: se suelta tocandolo */
  var KIND_GENERATOR = 9;       /* el nido: saca bichos hasta que lo rompes */
  /* El cubo de la vista isometrica: escenario que se dibuja como entidad para
     que entre en su sitio en la fila de profundidad. */
  var KIND_BLOQUE = 10;
  /* La vista isometrica: una sala son 8x8 casillas (128x128 px de planta) y se
     proyecta en rombos de 32x16. Los mismos numeros que np_types.h. */
  var SALA = 8, SALA_PX = 128, SALA_SHIFT = 7;
  var ISO_OX = 160, ISO_OY = 64;
  var ESCALON = 6;              /* lo que se sube andando */
  var ISO_PISA = 6;             /* lo cerca del suelo que hay que estar */
  /* el arma secundaria: 0 ninguna, 1 recta, 2 en arco */
  var SUB_NONE = 0, SUB_LINE = 1, SUB_ARC = 2;
  /* lo que se aparta un maton despues de pegarte, en frames (np_world.c) */
  var RECULA = 26;
  /* La bolsa de las aventuras: tres cosas a la vez, como en los Dizzy. Y los
     frames que un objeto recien soltado no se deja coger (np_world.c). */
  var BOLSA = 3, GRACIA_SOLTAR = 40, MAX_ABIERTOS = 12;
  /* por donde va y viene una plataforma movil */
  var PLAT_X = 0, PLAT_Y = 1;
  var ATTACK_NONE = 0, ATTACK_SHOT = 1, ATTACK_MELEE = 2;
  var STATE = { TITLE: 0, PLAY: 1, DYING: 2, LEVEL_END: 3, GAME_OVER: 4, FINISHED: 5 };
  /* Eventos de sonido; mismos bits que NP_SFX_* en np_types.h. */
  var SFX = { START: 1, JUMP: 2, DJUMP: 4, COIN: 8, STOMP: 16, HURT: 32,
              DIE: 64, GOAL: 128, LIFE: 256, SHOOT: 512, BREAK: 1024,
              CHECK: 2048 };

  function I2F(v) { return v * FIX_ONE; }
  function F2I(v) { return v >> FIX_SHIFT; }
  function abs(v) { return v < 0 ? -v : v; }
  function clamp(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }
  function idiv(a, b) { return (a / b) | 0; }

  function approach(value, target, delta) {
    if (value < target) { value += delta; if (value > target) value = target; }
    else if (value > target) { value -= delta; if (value < target) value = target; }
    return value;
  }

  var MAX_PLAYERS = 2;
  var HUECO_2P = 20;             /* lo mismo que NP_HUECO_2P en C */

  function World(data) {
    var i;
    this.data = data;
    this.level = data.levels[0];
    /* Los jugadores. Con `jugadores: 1` el segundo existe igual, con `playing`
       a cero: asi el motor es el mismo que en C y no hay dos caminos. */
    this.players = [];
    for (i = 0; i < MAX_PLAYERS; i++) {
      this.players.push({
        x: 0, y: 0, vx: 0, vy: 0, animTimer: 0, invuln: 0, dying: 0,
        anim: 0, animFrame: 0, onGround: 0, facing: 1, jumpsLeft: 0,
        health: 1, coyote: 0, buffer: 0, lives: 0, playing: 0, wearTimer: 0,
        /* la tercera coordenada de la vista de cinta: lo alto que estas sobre
           el suelo y a que velocidad subes o bajas */
        altura: 0, valtura: 0,
        /* la serie de golpes: por cual va y cuanto queda de ventana */
        comboLink: 0, comboTimer: 0,
        /* a quien tienes agarrado: su sitio en la lista mas uno (0 = a nadie) */
        grab: 0, grabTimer: 0,
        attackTimer: 0, attackCd: 0, riding: 0, whip: 0, crouch: 0,
        stun: 0, power: 0,
        /* el repertorio de tortas: el golpe fuerte (patada o hombro), la
           carrera y el doble toque que la enciende */
        fuerte: 0, carrera: 0, toque: 0, toqueDir: 0,
        stairs: 0, trepa: 0, stairDir: 1
      });
    }
    this.playerCount = data.players || 1;
    this.entities = [];
    this.camX = 0; this.camY = 0;
    /* lo que se lleva encima: el objeto de cada hueco mas uno (0 = vacio) */
    this.bolsa = [0, 0, 0];
    /* las casillas de cerrojo ya abiertas en este nivel */
    this.abiertos = [];
    this.score = 0; this.frame = 0;
    this.levelIndex = 0;
    this.state = STATE.TITLE; this.stateTimer = 0;
    this.timeLeft = 0; this.prevInput = [0, 0];
    this.sfx = 0;                 /* eventos de sonido de este frame */
    this.keys = 0; this.hearts = 0; this.entityCount = 0;
    /* Cuantos enemigos pegan ahora mismo, los frames de parada al acertar y
       los que tiembla la camara. Igual que en NpWorld. */
    this.atacando = 0; this.congelado = 0; this.sacudida = 0;
    /* La sala que se esta viendo y cuantos cubos suyos hay montados (solo la
       vista isometrica). Igual que en NpWorld. */
    this.salaX = -1; this.salaY = -1; this.bloquesN = 0;
    this.pantallaX = 0; this.pantallaY = 0;
    this.bloquesAbiertos = 0;
    this.sub = 0;                 /* el arma secundaria que se lleva */
    this.bossHealth = 0; this.bossMax = 0;
    /* El punto de control tocado en este nivel, en casillas. `checkOn` a cero
       quiere decir que se reaparece en la salida. */
    this.checkX = 0; this.checkY = 0; this.checkOn = 0;
    /* Igual que np_world_init en C: en el titulo ya se ve el principio del
       nivel, con los jugadores colocados en su salida. */
    for (i = 0; i < MAX_PLAYERS; i++) {
      this.players[i].playing = i < this.playerCount ? 1 : 0;
      this.players[i].lives = data.lives;
      this.placePlayer(i);
    }
    this.cameraUpdate();
  }

  /* El primer jugador sale en la salida del nivel y el segundo un poco a la
     derecha, para que no empiecen uno dentro del otro. Si hay un punto de
     control tocado, se sale de pie encima de esa casilla y centrado en su
     columna, igual que np_player_place en C. */
  World.prototype.placePlayer = function (quien) {
    var a = this.data.player.actor, p = this.players[quien], x, y;
    if (this.checkOn) {
      x = this.checkX * TILE + ((TILE - a.box_w) / 2 | 0);
      y = this.checkY * TILE + TILE - a.box_h;
    } else {
      x = this.level.start[0];
      y = this.level.start[1];
    }
    p.x = I2F(x + (quien ? HUECO_2P : 0));
    p.y = I2F(y);
  };

  /* --- la vista cenital ---------------------------------------------
   *
   * Con `vista: cenital` no hay gravedad ni suelo: se anda en ocho
   * direcciones y se dispara hacia donde se mira. Traduccion literal del
   * bloque del mismo nombre de engine/core/np_world.c. */
  var AIM_X = [1, 1, 0, -1, -1, -1, 0, 1];
  var AIM_Y = [0, 1, 1, 1, 0, -1, -1, -1];
  var DIAGONAL = 181;             /* 0,707 en 8 bits */

  function aimDe(dx, dy) {
    if (dx > 0) return dy > 0 ? 1 : (dy < 0 ? 7 : 0);
    if (dx < 0) return dy > 0 ? 3 : (dy < 0 ? 5 : 4);
    return dy > 0 ? 2 : 6;
  }

  function pasoCenital(velocidad, eje, diagonal) {
    var v = diagonal ? (velocidad * DIAGONAL) >> 8 : velocidad;
    return eje * v;
  }

  World.prototype.cenital = function () {
    /* La cinta es una vista cenital que ademas salta: el movimiento, la
       punteria y el empujon de los golpes son los mismos. Igual que
       np_vista_cenital en C, que tambien vale 1 con `vista: cinta`. */
    return !!(this.data.view === "cenital" || this.data.view === "cinta"
              || this.data.view === "iso");
  };

  /* La isometrica: se anda por la planta de una sala y se salta de cubo en
     cubo. Igual que np_vista_iso. */
  World.prototype.iso = function () {
    return this.data.view === "iso";
  };

  World.prototype.cinta = function () {
    return !!(this.data.view === "cinta");
  };

  World.prototype.tileKindAt = function (tx, ty) {
    var lv = this.level;
    /* Ojo con las medidas: cells_w y cells_h son las del mapa que se pisa, que
       en la isometrica no es el que se ve. Igual que np_tile_kind_at. */
    if (tx < 0 || tx >= lv.cells_w) return TILE_SOLID;
    /* De lado, arriba hay cielo y abajo un abismo. Desde arriba el mapa es
       una caja cerrada y sus cuatro lados son pared. */
    if (ty < 0 || ty >= lv.cells_h)
      return this.cenital() ? TILE_SOLID : TILE_EMPTY;
    return this.data.tiles.kind[lv.cells[ty * lv.cells_w + tx]];
  };

  /* Lo mismo, pero contando los cerrojos ya abiertos: una puerta abierta es
     aire y hay que verla como aire desde todos los sitios que miran el
     escenario. Igual que np_tile_visto. */
  World.prototype.tileVisto = function (tx, ty) {
    var kind = this.tileKindAt(tx, ty);
    if (kind !== TILE_LOCK) return kind;
    var casilla = ty * this.level.cells_w + tx;
    for (var i = 0; i < this.abiertos.length; i++)
      if (this.abiertos[i] === casilla) return TILE_EMPTY;
    return kind;
  };

  World.prototype.tileGfxAt = function (tx, ty) {
    var lv = this.level;
    if (tx < 0 || tx >= lv.width || ty < 0 || ty >= lv.height) return -1;
    /* En la isometrica el escenario que se dibuja no es el mapa: es el suelo
       de las salas, que ya viene en numeros de tile. */
    if (this.iso()) return lv.fondo[ty * lv.width + tx];
    /* Una puerta abierta se ve por lo que hay detras: el aire. Igual que
       np_tile_gfx_at en C. */
    if (this.abiertos.length && this.tileKindAt(tx, ty) === TILE_LOCK
        && this.tileVisto(tx, ty) === TILE_EMPTY)
      return this.data.tiles.gfx_vacio || 0;
    return this.data.tiles.gfx[lv.cells[ty * lv.cells_w + tx]];
  };

  /* Un cerrojo frena como una pared hasta que se abre: en cuanto se abre,
     tileVisto ya lo devuelve como aire y aqui no llega. */
  function blocks(kind) { return kind === TILE_SOLID || kind === TILE_LOCK; }

  function overlap(ax, ay, aw, ah, bx, by, bw, bh) {
    if (ax + I2F(aw) <= bx) return false;
    if (bx + I2F(bw) <= ax) return false;
    if (ay + I2F(ah) <= by) return false;
    if (by + I2F(bh) <= ay) return false;
    return true;
  }

  /* --- la vista isometrica ------------------------------------------
   *
   * El mapa es la planta de la sala y cada casilla ademas levanta: lo que te
   * frena no es el tipo de la casilla de al lado sino lo alto que esta
   * comparada con tus pies. Traduccion literal del bloque del mismo nombre de
   * engine/core/np_world.c. */

  World.prototype.celdaAlto = function (cx, cy) {
    var lv = this.level;
    if (cx < 0 || cx >= lv.cells_w) return I2F(255);
    if (cy < 0 || cy >= lv.cells_h) return I2F(255);
    if (this.abiertos.length && this.tileVisto(cx, cy) === TILE_EMPTY
        && this.tileKindAt(cx, cy) === TILE_LOCK) return 0;
    return I2F(this.data.tiles.alto[lv.cells[cy * lv.cells_w + cx]]);
  };

  World.prototype.isoChoca = function (cx, cy, pies) {
    return this.celdaAlto(cx, cy) > pies + I2F(ESCALON);
  };

  /* El suelo que hay debajo de una caja: la casilla mas alta que pisa. */
  World.prototype.isoSuelo = function (x, y, bw, bh) {
    var cx0 = F2I(x) >> TILE_SHIFT, cx1 = F2I(x + I2F(bw) - 1) >> TILE_SHIFT;
    var cy0 = F2I(y) >> TILE_SHIFT, cy1 = F2I(y + I2F(bh) - 1) >> TILE_SHIFT;
    var alto = 0, cx, cy;
    for (cy = cy0; cy <= cy1; cy++)
      for (cx = cx0; cx <= cx1; cx++) {
        var h = this.celdaAlto(cx, cy);
        if (h > alto) alto = h;
      }
    return alto;
  };

  /* Andar por la planta con el relieve delante. Un solo bucle para los dos
     ejes, como np_iso_move: en la planta no hay un eje que sea el del suelo. */
  World.prototype.isoMove = function (x, y, bw, bh, paso, pies, eje, out) {
    var movil = eje ? y : x;
    var quieto = eje ? x : y;
    var tam = eje ? bh : bw;
    var otroTam = eje ? bw : bh;
    out.hit = 0;
    while (paso !== 0) {
      var trozo = clamp(paso, -SUBSTEP, SUBSTEP);
      var a0, a1, c, borde, choca = false;
      paso -= trozo;
      movil += trozo;
      a0 = F2I(quieto) >> TILE_SHIFT;
      a1 = F2I(quieto + I2F(otroTam) - 1) >> TILE_SHIFT;
      borde = (trozo > 0) ? (F2I(movil + I2F(tam) - 1) >> TILE_SHIFT)
                          : (F2I(movil) >> TILE_SHIFT);
      for (c = a0; c <= a1; c++) {
        var cx = eje ? c : borde, cy = eje ? borde : c;
        if (this.isoChoca(cx, cy, pies)) { choca = true; break; }
      }
      if (choca) {
        movil = (trozo > 0) ? I2F(borde * TILE - tam) : I2F((borde + 1) * TILE);
        out.hit = 1;
        paso = 0;
      }
    }
    return movil;
  };

  /* Donde cae en la pantalla un actor: la esquina de arriba a la izquierda de
     su dibujo, sin restar la camara. Gemelo de np_pantalla. */
  World.prototype.pantalla = function (x, y, altura, def) {
    if (!this.iso())
      return { sx: F2I(x) - def.box_x, sy: F2I(y) - def.box_y };
    /* Solo cuenta el sitio dentro de la sala: todas se dibujan en el mismo
       cuadro y la camara no se mueve. Igual que np_pantalla. */
    var px = F2I(x) + idiv(def.box_w, 2);
    var py = F2I(y) + idiv(def.box_h, 2);
    var lx = px & (SALA_PX - 1), ly = py & (SALA_PX - 1);
    return {
      sx: ISO_OX + (lx - ly) - (def.box_x + idiv(def.box_w, 2)),
      sy: ISO_OY + ((lx + ly) >> 1) - F2I(altura) - (def.box_y + def.box_h)
    };
  };

  World.prototype.moveX = function (x, y, bw, bh, dx, out) {
    out.hit = 0;
    while (dx !== 0) {
      var step = clamp(dx, -SUBSTEP, SUBSTEP);
      var nx = x + step;
      var ty0 = F2I(y) >> TILE_SHIFT;
      var ty1 = F2I(y + I2F(bh) - 1) >> TILE_SHIFT;
      var ty, tx;
      dx -= step;
      if (step > 0) {
        tx = F2I(nx + I2F(bw) - 1) >> TILE_SHIFT;
        for (ty = ty0; ty <= ty1; ty++) {
          if (blocks(this.tileVisto(tx, ty))) {
            nx = I2F(tx * TILE - bw); out.hit = 1; dx = 0; break;
          }
        }
      } else {
        tx = F2I(nx) >> TILE_SHIFT;
        for (ty = ty0; ty <= ty1; ty++) {
          if (blocks(this.tileVisto(tx, ty))) {
            nx = I2F((tx + 1) * TILE); out.hit = 1; dx = 0; break;
          }
        }
      }
      x = nx;
    }
    return x;
  };

  World.prototype.moveY = function (x, y, bw, bh, dy, dropThrough, out) {
    out.hitDown = 0; out.hitUp = 0;
    while (dy !== 0) {
      var step = clamp(dy, -SUBSTEP, SUBSTEP);
      var ny = y + step;
      var tx0 = F2I(x) >> TILE_SHIFT;
      var tx1 = F2I(x + I2F(bw) - 1) >> TILE_SHIFT;
      var tx, ty;
      dy -= step;
      if (step > 0) {
        ty = F2I(ny + I2F(bh) - 1) >> TILE_SHIFT;
        var oldBottom = F2I(y + I2F(bh) - 1);
        for (tx = tx0; tx <= tx1; tx++) {
          var kind = this.tileVisto(tx, ty);
          var stops = blocks(kind);
          if (!stops && kind === TILE_PLATFORM && !dropThrough)
            stops = oldBottom < ty * TILE;
          if (stops) { ny = I2F(ty * TILE - bh); out.hitDown = 1; dy = 0; break; }
        }
      } else {
        ty = F2I(ny) >> TILE_SHIFT;
        for (tx = tx0; tx <= tx1; tx++) {
          if (blocks(this.tileVisto(tx, ty))) {
            ny = I2F((ty + 1) * TILE); out.hitUp = 1; dy = 0; break;
          }
        }
      }
      y = ny;
    }
    return y;
  };

  World.prototype.boxTouches = function (x, y, bw, bh, kind) {
    var tx0 = F2I(x) >> TILE_SHIFT, tx1 = F2I(x + I2F(bw) - 1) >> TILE_SHIFT;
    var ty0 = F2I(y) >> TILE_SHIFT, ty1 = F2I(y + I2F(bh) - 1) >> TILE_SHIFT;
    for (var ty = ty0; ty <= ty1; ty++)
      for (var tx = tx0; tx <= tx1; tx++)
        if (this.tileVisto(tx, ty) === kind) return true;
    return false;
  };

  World.prototype.entityDef = function (e) {
    if (e.kind === KIND_ENEMY) return this.data.enemies[e.def];
    if (e.kind === KIND_SHOT) return this.data.player.attack;
    if (e.kind === KIND_PLATFORM) return this.data.platforms[e.def];
    if (e.kind === KIND_BREAKABLE) return this.data.breakables[e.def];
    if (e.kind === KIND_SUBSHOT) return this.data.player.subs[e.def];
    if (e.kind === KIND_MELEE) return this.data.player.attack;
    if (e.kind === KIND_ENEMY_SHOT) return this.data.enemy_shots[e.def];
    if (e.kind === KIND_PRISONER) return this.data.prisoners[e.def];
    if (e.kind === KIND_GENERATOR) return this.data.generators[e.def];
    if (e.kind === KIND_BLOQUE) return this.data.bloques[e.def];
    return this.data.items[e.def];
  };

  function actorFrame(def, anim, animFrame) {
    var a = def.anims[anim];
    if (a.count === 0) a = def.anims[ANIM_IDLE];
    if (a.count === 0) return 0;
    if (animFrame >= a.count) animFrame = a.count - 1;
    return a.frames[animFrame];
  }

  function animSet(obj, next) {
    if (obj.anim !== next) { obj.anim = next; obj.animFrame = 0; obj.animTimer = 0; }
  }

  function animTick(def, obj) {
    var a = def.anims[obj.anim];
    if (a.count === 0) a = def.anims[ANIM_IDLE];
    if (a.count <= 1) { obj.animFrame = 0; obj.animTimer = 0; return; }
    obj.animTimer++;
    if (obj.animTimer >= a.speed) {
      obj.animTimer = 0;
      if (obj.animFrame + 1 < a.count) obj.animFrame++;
      else if (a.loop) obj.animFrame = 0;
    }
  }

  World.prototype.spawnEntities = function () {
    var lv = this.level, i;
    /* La lista se vacia entera: los proyectiles buscan hueco recorriendola
       desde el principio, y una entidad viva de un nivel anterior les daria un
       sitio ocupado. En C es el mismo bucle sobre las 64 ranuras. */
    this.entities = [];
    this.entityCount = 0;
    /* y con ellas se van los cubos de la sala, que se vuelven a montar en
       cuanto la camara diga en cual estamos */
    this.bloquesN = 0;
    for (i = 0; i < lv.spawns.length && this.entityCount < MAX_ENTITIES; i++) {
      var s = lv.spawns[i];
      var e = {
        active: 1, kind: s[2], def: s[3], x: I2F(s[0]), y: I2F(s[1]),
        homeX: I2F(s[0]), homeY: I2F(s[1]), vx: 0, vy: 0, facing: 0,
        anim: ANIM_IDLE,
        animFrame: 0, animTimer: 0, hurt: 0, timer: 0, health: 1, vida: 0,
        knock: 0,    /* derribado: frames que se queda en el suelo */
        altura: 0, valtura: 0,   /* lo alto que va el que sale lanzado */
        golpeado: 0, /* a quien ya ha tocado este golpe: un bit por jugador */
        /* el luchador: en que fase va y a quien ha tocado **su** golpe */
        fase: LUCHA_IR, tocado: 0, aturdido: 0
      };
      /* En la isometrica todo se apoya en el relieve: una llave puesta encima
         de un cubo sale encima del cubo. Igual que np_spawn_entities. */
      if (this.iso()) {
        var da = this.entityDef(e).actor;
        e.altura = this.isoSuelo(e.x, e.y, da.box_w, da.box_h);
      }
      if (e.kind === KIND_ENEMY) {
        var ed = this.data.enemies[e.def];
        e.health = ed.health;
        e.timer = ed.interval;
        e.vx = ed.speed;
        e.facing = 1;
      } else if (e.kind === KIND_PLATFORM) {
        e.facing = 1;             /* sale hacia la derecha o hacia abajo */
      } else if (e.kind === KIND_BREAKABLE) {
        e.health = this.data.breakables[e.def].health;
      } else if (e.kind === KIND_PRISONER) {
        e.health = 1;
        e.timer = 0;              /* cero = sigue atado */
      } else if (e.kind === KIND_GENERATOR) {
        var gd = this.data.generators[e.def];
        e.health = gd.health;
        e.timer = 0;              /* el primer bicho tarda lo mismo que los demas */
      }
      this.entities.push(e);
      this.entityCount++;
    }
  };

  /* Deja a un jugador como recien salido. Se usa al empezar el nivel y cuando
     reaparece despues de morir. */
  World.prototype.resetPlayer = function (quien) {
    var d = this.data.player, p = this.players[quien];
    this.placePlayer(quien);
    p.vx = 0; p.vy = 0; p.onGround = 0; p.facing = 1; p.aim = 0;
    p.health = d.health; p.invuln = 0; p.coyote = 0; p.buffer = 0;
    p.wearTimer = 0;            /* la cuenta atras de `desgaste:` de cero */
    p.altura = 0; p.valtura = 0;   /* con los pies en el suelo */
    p.comboLink = 0; p.comboTimer = 0;   /* la serie, desde el primero */
    p.grab = 0; p.grabTimer = 0;         /* y sin nadie agarrado */
    /* y sin carrera ni golpe fuerte a medias */
    p.fuerte = 0; p.carrera = 0; p.toque = 0; p.toqueDir = 0;
    p.dying = 0; p.attackTimer = 0; p.attackCd = 0; p.riding = 0; p.stun = 0;
    p.power = 0;                /* el arma vuelve a la de serie */
    p.crouch = 0;
    this.whipOff(quien);
    p.stairs = 0; p.trepa = 0; p.stairDir = 1;
    p.jumpsLeft = d.double_jump ? 1 : 0;
    p.anim = ANIM_IDLE; p.animFrame = 0; p.animTimer = 0;
  };

  World.prototype.loadLevel = function (index) {
    var i;
    if (index >= this.data.levels.length) index = 0;
    this.levelIndex = index;
    this.level = this.data.levels[index];
    /* antes de colocar a nadie: cargar un nivel es empezarlo de cero */
    this.checkOn = 0; this.checkX = 0; this.checkY = 0;
    for (i = 0; i < MAX_PLAYERS; i++) this.resetPlayer(i);
    this.keys = 0;
    this.hearts = 0;
    /* La bolsa y las puertas abiertas son de este nivel. Igual que en C. */
    this.bolsa = [0, 0, 0];
    this.abiertos = [];
    this.sub = 0;                 /* se empieza con la primera arma */
    this.bossHealth = 0; this.bossMax = 0;
    this.timeLeft = this.data.time_limit * 60;
    this.state = STATE.PLAY;
    this.stateTimer = 0;
    this.spawnEntities();
    /* Nadie ha estado nunca en la sala -1: con eso la camara ve un cambio de
       sala en su primera vuelta y monta los cubos de la de verdad. */
    this.salaX = -1;
    this.salaY = -1;
    this.cameraUpdate();
    /* La pantalla de salida es en la que se empieza: nadie entra detras de ti
       en el primer frame de un nivel. */
    this.pantallaX = Math.floor(this.camX / SCREEN_W);
    this.pantallaY = Math.floor(this.camY / SCREEN_H);
  };

  /* Cuantos siguen en juego y no se estan muriendo. */
  World.prototype.playersUp = function () {
    var n = 0, i;
    for (i = 0; i < MAX_PLAYERS; i++)
      if (this.players[i].playing && !this.players[i].dying) n++;
    return n;
  };

  World.prototype.playerDie = function (quien) {
    var p = this.players[quien];
    this.sfx |= SFX.DIE;
    p.dying = DYING_TIME;
    p.vy = -this.data.player.jump;
    p.vx = 0;
    p.attackTimer = 0;
    this.whipOff(quien);        /* muriendo no se pega, y el latigo no se queda */
    p.anim = ANIM_HURT;
    p.animFrame = 0;
    if (!this.playersUp()) { this.state = STATE.DYING; this.stateTimer = DYING_TIME; }
  };

  /* La vida que se gasta sola: `desgaste:` frames por punto. Igual que
     np_player_wear en C. No pasa por playerHurt a proposito: ahi rebota la
     invulnerabilidad, y la cuenta atras se pararia cada vez que te rozan. */
  World.prototype.playerWear = function (quien) {
    var d = this.data.player, p = this.players[quien];
    if (!d.wear || !p.playing || p.dying) return;
    if (this.state !== STATE.PLAY) return;
    if (++p.wearTimer < d.wear) return;
    p.wearTimer = 0;
    if (p.health > 1) { p.health--; return; }
    p.health = 0;
    this.playerDie(quien);
  };

  World.prototype.playerHurt = function (quien, damage) {
    var d = this.data.player, p = this.players[quien];
    if (p.invuln || p.dying || !p.playing) return;
    if (this.state !== STATE.PLAY) return;
    if (damage >= p.health) { p.health = 0; this.playerDie(quien); return; }
    p.health -= damage;
    this.sfx |= SFX.HURT;
    p.invuln = d.invuln;
    if (this.cenital()) {
      /* desde arriba el empujon va al reves de donde miras */
      p.vx = -AIM_X[p.aim] * d.knockback;
      p.vy = -AIM_Y[p.aim] * d.knockback;
    } else {
      p.vy = -idiv(d.bounce, 2);
      p.vx = p.facing ? -d.knockback : d.knockback;
    }
    /* El aturdimiento: mientras dura no se frena ni se cambia de sentido, asi
       que el empujon te lleva donde te lleve. Igual que np_player_hurt. */
    p.stun = d.stun;
    p.attackTimer = 0;
    this.whipOff(quien);
    p.stairs = 0;               /* un golpe te tira de la escalera */
    p.trepa = 0;                /* y de la liana */
  };

  var moveOut = { hit: 0, hitDown: 0, hitUp: 0 };

  /* ------------------------------------------------------------- ataque
   *
   * Traduccion literal de np_player_attack / np_shot_update / np_melee_update
   * de engine/core/np_world.c. Los proyectiles van en la misma lista que
   * enemigos y objetos (kind = KIND_SHOT) para que las cinco maquinas los
   * dibujen sin tocar nada y para que la traza de las pruebas los cuente.
   */

  /* Un hueco libre en la lista, buscando desde el principio: el mismo orden
     que en C, o la paridad falla. */
  World.prototype.huecoLibre = function () {
    var i;
    /* Los cubos de la sala ocupan el final de la lista y no son huecos libres
       aunque lo parezcan. Igual que np_hueco_libre. */
    var tope = this.entities.length - this.bloquesN;
    for (i = 0; i < tope; i++) {
      if (!this.entities[i].active) {
        if (i >= this.entityCount) this.entityCount = i + 1;
        return i;
      }
    }
    if (this.entities.length >= MAX_ENTITIES) return -1;
    this.entities.push({
      active: 0, kind: KIND_SHOT, def: 0, x: 0, y: 0, homeX: 0, homeY: 0,
      vx: 0, vy: 0,
      facing: 0, anim: ANIM_IDLE, animFrame: 0, animTimer: 0, hurt: 0,
      timer: 0, health: 1, vida: 0, knock: 0, golpeado: 0,
      altura: 0, valtura: 0, fase: LUCHA_IR, tocado: 0, aturdido: 0
    });
    i = this.entities.length - 1;
    if (i >= this.entityCount) this.entityCount = i + 1;
    return i;
  };

  World.prototype.hitEnemy = function (e, damage) {
    var d = this.data.enemies[e.def];
    /* Le has pegado tu primero: se le corta el golpe y pierde el turno. Igual
       que np_hit_enemy en C. */
    e.fase = LUCHA_IR;
    if (e.health > damage) {
      e.health -= damage;
      e.hurt = 20;
      /* Y se tambalea: el hueco por el que entra el golpe siguiente. Igual
         que np_hit_enemy. */
      if (this.cinta()) e.aturdido = ATURDE;
      this.sfx |= SFX.STOMP;
      return;
    }
    e.active = 0;
    this.score += d.score;
    this.sfx |= SFX.STOMP;
    if (d.boss) this.finishLevel();
  };

  /* Romper un candelabro. Lo que suelte ocupa su propia ranura, asi que nunca
     se queda sin sitio. Igual que np_hit_breakable en C. */
  World.prototype.hitBreakable = function (e, damage) {
    var d = this.data.breakables[e.def];
    var suelta = d.drop;
    if (e.health > damage) {
      e.health -= damage;
      e.hurt = 10;
      this.sfx |= SFX.BREAK;
      return;
    }
    this.score += d.score;
    this.sfx |= SFX.BREAK;
    if (!suelta || suelta > this.data.items.length) { e.active = 0; return; }
    var ea = d.actor, ia = this.data.items[suelta - 1].actor;
    var cx = e.x + I2F(idiv(ea.box_w, 2));
    var suelo = e.y + I2F(ea.box_h);
    e.kind = KIND_ITEM;
    e.def = suelta - 1;
    e.x = cx - I2F(idiv(ia.box_w, 2));
    e.y = suelo - I2F(ia.box_h);
    e.homeX = e.x; e.homeY = e.y;
    e.vx = 0; e.vy = 0;
    e.health = 1; e.hurt = 0; e.timer = 0; e.vida = 0; e.knock = 0;
    e.golpeado = 0; e.altura = 0; e.valtura = 0;
    e.fase = LUCHA_IR; e.tocado = 0; e.aturdido = 0;
    e.anim = ANIM_IDLE; e.animFrame = 0; e.animTimer = 0;
  };

  /* Un generador aguanta unos tiros y se acabo. Igual que np_hit_generator. */
  World.prototype.hitGenerator = function (e, damage) {
    var d = this.data.generators[e.def];
    if (e.health > damage) {
      e.health -= damage;
      e.hurt = 10;
      this.sfx |= SFX.BREAK;
      return;
    }
    this.score += d.score;
    this.sfx |= SFX.BREAK;
    e.active = 0;
  };

  /* Lo que hace un ataque al tocar algo. Igual que np_hit_entity. */
  World.prototype.hitEntity = function (e, damage) {
    if (e.kind === KIND_ENEMY) this.hitEnemy(e, damage);
    else if (e.kind === KIND_BREAKABLE) this.hitBreakable(e, damage);
    else if (e.kind === KIND_GENERATOR) this.hitGenerator(e, damage);
  };

  /* El alcance del arma ahora mismo: el de siempre mas lo que suman las
     mejoras recogidas. Igual que np_attack_range en C. */
  /* La caja del jugador ahora mismo: agachado, el techo baja `crouch_drop`
     pixeles y los pies se quedan donde estan. Igual que np_player_top y
     np_player_height. */
  World.prototype.playerTop = function (quien) {
    var p = this.players[quien];
    return p.crouch ? p.y + I2F(this.data.player.crouch_drop) : p.y;
  };

  World.prototype.playerHeight = function (quien) {
    var d = this.data.player, p = this.players[quien];
    return p.crouch ? d.actor.box_h - d.crouch_drop : d.actor.box_h;
  };

  World.prototype.attackLevel = function (quien) {
    var at = this.data.player.attack, p = this.players[quien];
    return p.power < at.levels ? p.power : at.levels;
  };

  /* Esto es una patada voladora y no un puno? Con `patada:` puesto, pegar sin
     pisar suelo es otro golpe. Igual que np_es_patada. */
  World.prototype.esPatada = function (quien) {
    var p = this.players[quien];
    return !!this.data.player.attack.kick_range && !p.onGround
           && !p.stairs && !p.trepa;
  };

  World.prototype.attackRange = function (quien) {
    var at = this.data.player.attack;
    if (this.esPatada(quien)) return at.kick_range;
    return at.range + this.attackLevel(quien) * at.range_step;
  };

  /* Apaga el dibujo del latigo. Igual que np_whip_off. */
  World.prototype.whipOff = function (quien) {
    var p = this.players[quien];
    if (p.whip && p.whip <= this.entities.length)
      this.entities[p.whip - 1].active = 0;
    p.whip = 0;
  };

  /* El latigo que se ve: una entidad mas de la lista, para que la dibuje el
     preview igual que las seis maquinas. Igual que np_whip_on. */
  World.prototype.whipOn = function (quien) {
    var at = this.data.player.attack, p = this.players[quien];
    var pa = this.data.player.actor, e;
    if (!at.fx) return;                   /* el ataque no trae dibujo */
    if (!p.whip) {
      var hueco = this.huecoLibre();
      if (hueco < 0) return;              /* no cabe: se pega sin verse */
      p.whip = hueco + 1;
      e = this.entities[hueco];
      e.active = 1; e.kind = KIND_MELEE; e.def = 0;
      e.vx = 0; e.vy = 0; e.homeX = 0; e.homeY = 0;
      e.vida = 0; e.timer = 0; e.health = 1; e.hurt = 0;
      e.anim = ANIM_IDLE; e.animTimer = 0;
    }
    e = this.entities[p.whip - 1];
    e.facing = p.facing;
    /* mirando a la izquierda el dibujo sale espejado, asi que hay que restar
       el ancho entero: el latigo empieza por el borde derecho del fotograma */
    e.x = p.facing ? p.x + I2F(pa.box_w)
                   : p.x - I2F(at.actor.cols * TILE);
    e.y = this.playerTop(quien);      /* agachado, el latigo va por abajo */
    e.animFrame = this.attackLevel(quien);   /* cada mejora, su fotograma */
  };

  World.prototype.playerAttack = function (quien) {
    var at = this.data.player.attack, p = this.players[quien];
    var pa = this.data.player.actor;
    if (!at || at.kind === ATTACK_NONE || p.attackCd) return;
    p.attackCd = at.cooldown;
    this.sfx |= SFX.SHOOT;
    /* Golpe nuevo, cuenta nueva: lo que ya haya tocado el anterior vuelve a
       poder recibir. Igual que np_player_attack. */
    if (at.kind === ATTACK_MELEE) {
      for (var k = 0; k < this.entityCount; k++)
        this.entities[k].golpeado &= ~(1 << quien);
    }

    /* La serie: si queda ventana, este golpe es el siguiente de la tanda; si
       no, se empieza otra vez por el primero. Igual que np_player_attack. */
    if (at.kind === ATTACK_MELEE && at.combo > 1) {
      if (p.comboTimer && p.comboLink + 1 < at.combo) p.comboLink++;
      else p.comboLink = 0;
      p.comboTimer = at.combo_window;
    }
    /* La pose de atacar dura lo mismo se pegue o se dispare. */
    p.attackTimer = at.duration;
    if (at.kind === ATTACK_MELEE) return;

    var hueco = this.huecoLibre();
    if (hueco < 0) return;
    var e = this.entities[hueco];
    e.active = 1;
    e.kind = KIND_SHOT;
    e.def = 0;
    e.facing = p.facing;
    if (this.cenital()) {
      var ax = AIM_X[p.aim], ay = AIM_Y[p.aim], diag = (ax && ay);
      e.x = p.x + I2F(idiv(pa.box_w - at.actor.box_w, 2)
                      + ax * (idiv(pa.box_w, 2) + 1));
      e.y = p.y + I2F(idiv(pa.box_h - at.actor.box_h, 2)
                      + ay * (idiv(pa.box_h, 2) + 1));
      e.vx = pasoCenital(at.speed, ax, diag);
      e.vy = pasoCenital(at.speed, ay, diag);
    } else {
      e.x = p.x + I2F(p.facing ? pa.box_w : -at.actor.box_w);
      e.y = this.playerTop(quien)
          + I2F(idiv(this.playerHeight(quien) - at.actor.box_h, 2));
      e.vx = p.facing ? at.speed : -at.speed;
      e.vy = 0;
    }
    e.homeY = e.y;
    e.health = 1;
    e.hurt = 0;
    e.timer = 0;
    e.anim = ANIM_IDLE;
    e.animFrame = 0;
    e.animTimer = 0;
    e.vida = at.speed
      ? idiv(I2F(this.attackRange(quien)), at.speed) + 1 : 1;
  };

  World.prototype.shotUpdate = function (e) {
    var at = this.data.player.attack, a = at.actor, i;
    if (!e.vida) { e.active = 0; return; }
    e.vida--;
    e.x = this.moveX(e.x, e.y, a.box_w, a.box_h, e.vx, moveOut);
    if (moveOut.hit) { e.active = 0; return; }
    if (this.cenital() && e.vy) {
      /* desde arriba el disparo tambien vuela en vertical */
      e.y = this.moveY(e.x, e.y, a.box_w, a.box_h, e.vy, 1, moveOut);
      if (moveOut.hitDown || moveOut.hitUp) { e.active = 0; return; }
    }
    for (i = 0; i < this.entityCount; i++) {
      var otra = this.entities[i];
      if (!otra.active) continue;
      /* al prisionero no hay que dispararle: si le das, se acabo */
      if (otra.kind === KIND_PRISONER) {
        var pa2 = this.entityDef(otra).actor;
        if (!overlap(e.x, e.y, a.box_w, a.box_h,
                     otra.x, otra.y, pa2.box_w, pa2.box_h)) continue;
        if (!otra.timer) { otra.active = 0; this.sfx |= SFX.HURT; }
        e.active = 0;
        return;
      }
      if (otra.kind !== KIND_ENEMY && otra.kind !== KIND_BREAKABLE
          && otra.kind !== KIND_GENERATOR) continue;
      var ea = this.entityDef(otra).actor;
      if (!overlap(e.x, e.y, a.box_w, a.box_h,
                        otra.x, otra.y, ea.box_w, ea.box_h)) continue;
      this.hitEntity(otra, at.damage);
      e.active = 0;
      return;
    }
    animTick(a, e);
  };

  World.prototype.meleeUpdate = function (quien) {
    var at = this.data.player.attack, p = this.players[quien];
    var pa = this.data.player.actor, i;
    if (!p.attackTimer) { p.fuerte = 0; this.whipOff(quien); return; }
    p.attackTimer--;
    if (at.kind !== ATTACK_MELEE) return;     /* un disparo no pega de cerca */
    /* Los primeros `preparacion:` frames el golpe se ve pero no toca. El
       latigo aparece justo cuando empieza a hacer dano. */
    if (p.attackTimer + at.windup >= at.duration) { this.whipOff(quien); return; }
    this.whipOn(quien);
    var alcance = this.attackRange(quien);
    var gx = p.facing ? p.x + I2F(pa.box_w) : p.x - I2F(alcance);
    var gy = this.playerTop(quien);
    var alto = this.playerHeight(quien);
    /* La patada en salto llega al suelo: la caja se estira desde donde estas
       hasta la linea del suelo. Igual que np_melee_update. */
    if (this.cinta() && p.altura > 0) alto += F2I(p.altura);
    for (i = 0; i < this.entityCount; i++) {
      var e = this.entities[i];
      if (!e.active) continue;
      if (e.kind !== KIND_ENEMY && e.kind !== KIND_BREAKABLE
          && e.kind !== KIND_GENERATOR) continue;
      /* A quien ya ha tocado este golpe no se le toca otra vez: la caja dura
         varios frames y acertaria en todos. Se mira **este** golpe y no el
         parpadeo, para que el segundo de una serie acierte al que aun
         parpadea del primero. Igual que np_melee_update. */
      if (e.golpeado & (1 << quien)) continue;
      var ea = this.entityDef(e).actor;
      if (!overlap(gx, gy, alcance, alto,
                        e.x, e.y, ea.box_w, ea.box_h)) continue;
      e.golpeado |= (1 << quien);
      var faseAntes = e.fase;
      this.hitEntity(e, this.golpeDano(quien));
      /* El que ya ha empezado a soltar el golpe no se para con un puno
         normal. Igual que np_melee_update. */
      if (this.cinta() && e.active && faseAntes === LUCHA_PREPARAR
          && !this.esRemate(quien)) {
        e.fase = LUCHA_PREPARAR;
        e.aturdido = 0;
      }
      /* La parada del impacto, solo en la cinta. Igual que np_melee_update. */
      if (this.cinta()) {
        this.congelado = this.esRemate(quien) ? CONGELADO_REMATE : CONGELADO;
        /* y con el remate la pantalla tiembla, muera o no el que lo cobra.
           Igual que np_melee_update. */
        if (this.esRemate(quien) && e.kind === KIND_ENEMY)
          this.sacudida = SACUDIDA;
      }
      /* y el empujon del tambaleo, hacia donde miras. Igual que en C. */
      if (this.cinta() && e.active && e.aturdido) {
        e.vx = this.players[quien].facing ? I2F(1) : -I2F(1);
        e.vy = 0;
      }
      if (e.active) this.derribar(quien, e);
    }
  };

  /* ¿Hay alguien a tiro a ese lado? Es la pregunta del codazo. Igual que
     np_hay_a_ese_lado en C. */
  World.prototype.hayALado = function (quien, derecha) {
    var p = this.players[quien], pa = this.data.player.actor;
    var alcance = this.attackRange(quien);
    var gx = derecha ? p.x + I2F(pa.box_w) : p.x - I2F(alcance);
    for (var i = 0; i < this.entityCount; i++) {
      var e = this.entities[i];
      if (!e.active || e.kind !== KIND_ENEMY || e.knock) continue;
      var ea = this.entityDef(e).actor;
      if (overlap(gx, this.playerTop(quien), alcance, this.playerHeight(quien),
                  e.x, e.y, ea.box_w, ea.box_h))
        return true;
    }
    return false;
  };

  /* La patada en salto y el hombro en carrera valen por un remate. Igual que
     np_es_remate. */
  World.prototype.esRemate = function (quien) {
    var at = this.data.player.attack, p = this.players[quien];
    if (this.cinta() && p.fuerte) return true;
    return !!(at && at.combo > 1 && p.comboLink + 1 >= at.combo);
  };

  /* Lo que hace el golpe que se esta dando ahora. Igual que np_golpe_dano. */
  World.prototype.golpeDano = function (quien) {
    var at = this.data.player.attack;
    if (this.esPatada(quien) && at.kick_damage) return at.kick_damage;
    if (this.esRemate(quien) && at.finish_damage) return at.finish_damage;
    return at.damage;
  };

  /* Al que cobra el remate lo tumba. Igual que np_derribar. */
  World.prototype.derribar = function (quien, e) {
    var at = this.data.player.attack, p = this.players[quien];
    if (!this.esRemate(quien) || !at.finish_stun) return;
    if (e.kind !== KIND_ENEMY) return;
    e.knock = at.finish_stun;
    e.vx = p.facing ? at.finish_push : -at.finish_push;
    e.vy = 0;
  };

  /* ------------------------------------------------- arma secundaria
   *
   * Arriba + accion, y gasta municion. Traduccion literal de np_player_sub /
   * np_subshot_update / np_breakable_update. */

  /* Cuantas tiradas de esta arma van por el aire. Igual que np_subs_volando. */
  World.prototype.subsVolando = function (arma) {
    var cuantas = 0, i;
    for (i = 0; i < this.entityCount; i++) {
      var e = this.entities[i];
      if (e.active && e.kind === KIND_SUBSHOT && e.def === arma) cuantas++;
    }
    return cuantas;
  };

  World.prototype.playerSub = function (quien) {
    var armas = this.data.player.subs, p = this.players[quien];
    var sb = armas[this.sub], pa = this.data.player.actor;
    if (!sb || sb.kind === SUB_NONE || p.attackCd) return;
    if (this.hearts < sb.cost) return;
    /* `a_la_vez`: igual que np_player_sub */
    if (sb.at_once && this.subsVolando(this.sub) >= sb.at_once) return;
    var hueco = this.huecoLibre();
    if (hueco < 0) return;
    this.hearts -= sb.cost;
    p.attackCd = sb.cooldown;
    p.attackTimer = this.data.player.attack.duration;
    this.sfx |= SFX.SHOOT;
    var e = this.entities[hueco];
    e.active = 1;
    e.kind = KIND_SUBSHOT;
    e.def = this.sub;             /* se queda con el arma con la que salio */
    e.facing = p.facing;
    if (this.cenital()) {
      var gx = AIM_X[p.aim], gy = AIM_Y[p.aim], gdiag = (gx && gy);
      e.x = p.x + I2F(idiv(pa.box_w - sb.actor.box_w, 2)
                      + gx * (idiv(pa.box_w, 2) + 1));
      e.y = p.y + I2F(idiv(pa.box_h - sb.actor.box_h, 2)
                      + gy * (idiv(pa.box_h, 2) + 1));
      e.vx = pasoCenital(sb.speed, gx, gdiag);
      e.vy = pasoCenital(sb.speed, gy, gdiag);
    } else {
      e.x = p.x + I2F(p.facing ? pa.box_w : -sb.actor.box_w);
      e.y = this.playerTop(quien)
          + I2F(idiv(this.playerHeight(quien) - sb.actor.box_h, 2));
      e.vx = p.facing ? sb.speed : -sb.speed;
      e.vy = (sb.kind === SUB_ARC) ? -sb.jump : 0;
    }
    e.homeX = e.x; e.homeY = e.y;
    e.health = 1; e.hurt = 0; e.timer = 0;
    e.anim = ANIM_IDLE; e.animFrame = 0; e.animTimer = 0;
    e.vida = sb.speed ? idiv(I2F(sb.range), sb.speed) + 1 : 1;
  };

  World.prototype.subshotUpdate = function (e) {
    var sb = this.data.player.subs[e.def], a = sb.actor, i;
    if (!e.vida) { e.active = 0; return; }
    e.vida--;
    /* el arco es de la vista lateral: desde arriba la granada vuela recta */
    if (sb.kind === SUB_ARC && !this.cenital()) {
      e.vy += sb.gravity;
      if (e.vy > ENTITY_FALL) e.vy = ENTITY_FALL;
    }
    e.x = this.moveX(e.x, e.y, a.box_w, a.box_h, e.vx, moveOut);
    if (moveOut.hit) { e.active = 0; return; }
    if (e.vy) {
      e.y = this.moveY(e.x, e.y, a.box_w, a.box_h, e.vy, 1, moveOut);
      if (moveOut.hitDown || moveOut.hitUp) { e.active = 0; return; }
    }
    for (i = 0; i < this.entityCount; i++) {
      var otra = this.entities[i];
      if (!otra.active) continue;
      /* al prisionero no hay que dispararle: si le das, se acabo */
      if (otra.kind === KIND_PRISONER) {
        var pa2 = this.entityDef(otra).actor;
        if (!overlap(e.x, e.y, a.box_w, a.box_h,
                     otra.x, otra.y, pa2.box_w, pa2.box_h)) continue;
        if (!otra.timer) { otra.active = 0; this.sfx |= SFX.HURT; }
        e.active = 0;
        return;
      }
      if (otra.kind !== KIND_ENEMY && otra.kind !== KIND_BREAKABLE
          && otra.kind !== KIND_GENERATOR) continue;
      var ea = this.entityDef(otra).actor;
      if (!overlap(e.x, e.y, a.box_w, a.box_h,
                        otra.x, otra.y, ea.box_w, ea.box_h)) continue;
      this.hitEntity(otra, sb.damage);
      e.active = 0;
      return;
    }
    animTick(a, e);
  };

  /* Un candelabro no hace nada: se anima y espera a que le pegues. */
  World.prototype.breakableUpdate = function (e) {
    var d = this.data.breakables[e.def];
    animSet(e, ANIM_IDLE);
    animTick(d.actor, e);
  };

  /* --------------------------------------------- plataformas moviles */

  /* Va y viene entre donde salio y `distance` pixeles mas alla. Se mueve antes
     que los jugadores: el que va encima tiene que ir con ella, y para eso hay
     que saber cuanto se ha movido. Eso es lo que queda en vx/vy, que aqui no
     es una velocidad sino el desplazamiento de este frame. Igual que
     np_platform_update en C. */
  World.prototype.platformUpdate = function (e) {
    var d = this.data.platforms[e.def];
    var limite = I2F(d.distance);
    var paso = e.facing ? d.speed : -d.speed;
    e.vx = 0;
    e.vy = 0;
    if (d.speed && d.distance) {
      if (d.axis === PLAT_Y) {
        var ny = e.y + paso;
        if (ny >= e.homeY + limite) { ny = e.homeY + limite; e.facing = 0; }
        else if (ny <= e.homeY) { ny = e.homeY; e.facing = 1; }
        e.vy = ny - e.y;
        e.y = ny;
      } else {
        var nx = e.x + paso;
        if (nx >= e.homeX + limite) { nx = e.homeX + limite; e.facing = 0; }
        else if (nx <= e.homeX) { nx = e.homeX; e.facing = 1; }
        e.vx = nx - e.x;
        e.x = nx;
      }
    }
    animSet(e, ANIM_IDLE);
    animTick(d.actor, e);
  };

  /* Encima de que plataforma se queda el jugador. Funciona igual que un tile
     de `plataforma`: solo se aterriza cayendo y desde arriba, y pulsando abajo
     se deja caer. Igual que np_ride_update en C. */
  World.prototype.rideUpdate = function (quien, antesY, soltar) {
    var a = this.data.player.actor, p = this.players[quien];
    var piesAntes = antesY + I2F(a.box_h);
    var i;
    p.riding = 0;
    if (soltar || p.vy < 0) return;
    for (i = 0; i < this.entityCount; i++) {
      var e = this.entities[i];
      if (!e.active || e.kind !== KIND_PLATFORM) continue;
      var ea = this.data.platforms[e.def].actor;
      if (p.x + I2F(a.box_w) <= e.x) continue;
      if (e.x + I2F(ea.box_w) <= p.x) continue;
      if (piesAntes > e.y) continue;                 /* venia por debajo */
      if (p.y + I2F(a.box_h) < e.y) continue;        /* no llega a tocarla */
      p.y = e.y - I2F(a.box_h);
      p.vy = 0;
      p.onGround = 1;
      p.riding = i + 1;
      return;
    }
  };

  /* ------------------------------------------------------------ escaleras
   *
   * Traduccion literal de np_stair_at / np_stair_mount / np_stair_update. Una
   * escalera es un segundo modo de movimiento: sin gravedad, sin saltos y sin
   * choques, y todo se apoya en el pixel de abajo del centro de la caja. */

  World.prototype.stairAt = function (x, y) {
    var kind = this.tileVisto(F2I(x) >> TILE_SHIFT, F2I(y) >> TILE_SHIFT);
    return (kind === TILE_STAIR_R || kind === TILE_STAIR_L) ? kind : 0;
  };

  function refX(p, a) { return p.x + I2F(idiv(a.box_w, 2)); }
  function refY(p, a) { return p.y + I2F(a.box_h - 1); }

  function stairPlace(p, a, tx, ty) {
    p.x = I2F(tx * TILE + idiv(TILE, 2) - idiv(a.box_w, 2));
    p.y = I2F(ty * TILE + idiv(TILE, 2) - (a.box_h - 1));
    p.vx = 0;
    p.vy = 0;
  }

  World.prototype.stairMount = function (quien, input) {
    var a = this.data.player.actor, p = this.players[quien];
    var tx = F2I(refX(p, a)) >> TILE_SHIFT;
    var kind;
    if (!p.onGround || this.data.player.stair_speed <= 0) return 0;

    if (input & IN.UP) {
      var ty = F2I(refY(p, a)) >> TILE_SHIFT;
      kind = this.stairAt(refX(p, a), refY(p, a));
      if (kind) {
        p.stairs = 1;
        p.stairDir = (kind === TILE_STAIR_R) ? 1 : -1;
        stairPlace(p, a, tx, ty);
        return 1;
      }
    }
    if (input & IN.DOWN) {
      var tb = (F2I(p.y + I2F(a.box_h)) >> TILE_SHIFT) + 1;
      for (var bx = -1; bx <= 1; bx += 2) {
        var esperado = (bx < 0) ? TILE_STAIR_R : TILE_STAIR_L;
        kind = this.tileKindAt(tx + bx, tb);
        if (kind !== esperado) continue;
        p.stairs = 1;
        p.stairDir = (kind === TILE_STAIR_R) ? 1 : -1;
        stairPlace(p, a, tx + bx, tb);
        return 1;
      }
    }
    return 0;
  };

  World.prototype.stairUpdate = function (quien, input) {
    var d = this.data.player, a = d.actor, p = this.players[quien];
    var moviendo = 0;
    p.vx = 0;
    p.vy = 0;
    p.onGround = 0;
    if (input & IN.UP) {
      p.x += p.stairDir * d.stair_speed;
      p.y -= d.stair_speed;
      moviendo = 1;
    } else if (input & IN.DOWN) {
      p.x -= p.stairDir * d.stair_speed;
      p.y += d.stair_speed;
      moviendo = 1;
    }
    if (!this.stairAt(refX(p, a), refY(p, a))) {
      var ty = F2I(refY(p, a)) >> TILE_SHIFT;
      p.y = I2F(ty * TILE - a.box_h);
      p.stairs = 0;
      p.onGround = 1;
      return 0;
    }
    animSet(p, ANIM_STAIR);
    if (moviendo) animTick(a, p);
    return 1;
  };

  /* --- las lianas. Gemelas de np_climb_at, np_climb_mount y np_climb_update.
     Una liana no es una escalera: se coge en el aire y se sube recta. */
  World.prototype.climbAt = function (x, y) {
    return this.tileVisto(F2I(x) >> TILE_SHIFT, F2I(y) >> TILE_SHIFT) === TILE_CLIMB;
  };

  World.prototype.climbMount = function (quien, input) {
    var a = this.data.player.actor, p = this.players[quien];
    if (this.data.player.climb_speed <= 0) return 0;
    if (!(input & (IN.UP | IN.DOWN))) return 0;
    if (!this.climbAt(refX(p, a), refY(p, a))) return 0;
    var tx = F2I(refX(p, a)) >> TILE_SHIFT;
    p.x = I2F(tx * TILE + idiv(TILE, 2) - idiv(a.box_w, 2));
    p.vx = 0;
    p.vy = 0;
    p.trepa = 1;
    p.onGround = 0;
    return 1;
  };

  World.prototype.climbUpdate = function (quien, input) {
    var d = this.data.player, a = d.actor, p = this.players[quien];
    var moviendo = 0;
    p.vx = 0;
    p.vy = 0;
    p.onGround = 0;
    if ((input & IN.JUMP) && !(this.prevInput[quien] & IN.JUMP)) {
      p.trepa = 0;
      p.vy = -d.jump;
      if (input & IN.RIGHT) { p.vx = d.speed; p.facing = 1; }
      else if (input & IN.LEFT) { p.vx = -d.speed; p.facing = 0; }
      this.sfx |= SFX.JUMP;
      return 0;
    }
    if (input & (IN.UP | IN.DOWN)) {
      var paso = (input & IN.UP) ? -d.climb_speed : d.climb_speed;
      var out = {};
      p.y = this.moveY(p.x, p.y, a.box_w, a.box_h, paso, 1, out);
      moviendo = 1;
    }
    if (!this.climbAt(refX(p, a), refY(p, a))) {
      p.trepa = 0;
      if (input & IN.UP) {
        var ty = F2I(refY(p, a)) >> TILE_SHIFT;
        p.y = I2F(ty * TILE + TILE - a.box_h);
      }
      return 0;
    }
    animSet(p, ANIM_STAIR);
    if (moviendo) animTick(a, p);
    return 1;
  };

  /* El boton de accion, aparte porque vale igual andando que en la escalera. */
  World.prototype.playerAction = function (quien, input) {
    var p = this.players[quien];
    if (p.attackCd) p.attackCd--;
    /* En una aventura el boton no pega: suelta lo que llevas. Igual que
       np_player_action. */
    if (this.data.bolsa_activa) {
      if ((input & IN.ACTION) && !(this.prevInput[quien] & IN.ACTION))
        this.soltarObjeto(quien);
      return;
    }
    if ((input & IN.ACTION) && !(this.prevInput[quien] & IN.ACTION)) {
      var sb = this.data.player.subs[this.sub];
      if ((input & IN.UP) && sb && sb.kind !== SUB_NONE && this.hearts >= sb.cost)
        this.playerSub(quien);
      else
        this.playerAttack(quien);
    }
    this.meleeUpdate(quien);
  };

  /* El jugador mirando desde arriba: ocho direcciones, sin gravedad y sin
     suelo. Traduccion literal de np_player_update_cenital. */
  World.prototype.playerUpdateCenital = function (quien, input) {
    var d = this.data.player, a = d.actor, p = this.players[quien];
    var dx = 0, dy = 0, pose;

    if (p.stun) { p.stun--; input = 0; }
    else {
      if (input & IN.RIGHT) dx += 1;
      if (input & IN.LEFT) dx -= 1;
      if (input & IN.DOWN) dy += 1;
      if (input & IN.UP) dy -= 1;
    }

    if (dx || dy) {
      p.aim = aimDe(dx, dy);
      if (dx) p.facing = dx > 0 ? 1 : 0;
      p.vx = pasoCenital(d.speed, dx, dx && dy);
      p.vy = pasoCenital(d.speed, dy, dx && dy);
    } else if (p.stun) {
      p.vx = approach(p.vx, 0, d.friction);
      p.vy = approach(p.vy, 0, d.friction);
    } else {
      p.vx = 0;
      p.vy = 0;
    }

    p.x = this.moveX(p.x, p.y, a.box_w, a.box_h, p.vx, moveOut);
    if (moveOut.hit) p.vx = 0;
    p.y = this.moveY(p.x, p.y, a.box_w, a.box_h, p.vy, 1, moveOut);
    if (moveOut.hitDown || moveOut.hitUp) p.vy = 0;
    p.onGround = 1;
    p.jumpsLeft = 0;
    p.stairs = 0;
    p.trepa = 0;
    p.crouch = 0;

    /* saltar no tiene sentido desde arriba: ese boton tira la granada */
    if (p.attackCd) p.attackCd--;
    if ((input & IN.JUMP) && !(this.prevInput[quien] & IN.JUMP) &&
        this.data.player.subs.length &&
        this.hearts >= this.data.player.subs[this.sub].cost)
      this.playerSub(quien);
    else if ((input & IN.ACTION) && !(this.prevInput[quien] & IN.ACTION))
      this.playerAttack(quien);

    if (p.invuln) p.invuln--;
    if (p.attackTimer) p.attackTimer--;

    if (p.attackTimer) pose = ANIM_ATTACK;
    else if (!dx && !dy) pose = ANIM_IDLE;
    else if (dy < 0 && !dx) pose = ANIM_UP;
    else if (dy > 0 && !dx) pose = ANIM_DOWN;
    else pose = ANIM_RUN;
    animSet(p, pose);
    animTick(a, p);
  };

  /* ------------------------------------------------------- el agarre
   *
   * Al que se tambalea de un golpe se le coge, se le zarandea a rodillazos y
   * se le lanza por encima del hombro. Traduccion literal de np_grab_update,
   * np_rodillazo y np_lanzar. */
  World.prototype.agarrado = function (quien) {
    var p = this.players[quien];
    if (!p.grab || p.grab > this.entityCount) return null;
    var e = this.entities[p.grab - 1];
    if (!e.active || e.kind !== KIND_ENEMY) { p.grab = 0; return null; }
    return e;
  };

  World.prototype.soltar = function (quien) {
    var p = this.players[quien];
    p.grab = 0; p.grabTimer = 0;
  };

  World.prototype.lanzar = function (quien, e) {
    var d = this.data.player, p = this.players[quien];
    e.vx = p.facing ? d.throw_speed : -d.throw_speed;
    e.vy = 0;
    e.valtura = d.jump;
    e.knock = d.grab_time ? 60 : 30;
    e.golpeado = 0;
    this.sfx |= SFX.STOMP;
    this.hitEntity(e, d.throw_damage);
    this.soltar(quien);
  };

  World.prototype.rodillazo = function (quien, e) {
    var d = this.data.player, p = this.players[quien];
    p.attackTimer = d.attack.duration;
    p.grabTimer = d.grab_time;
    this.sfx |= SFX.SHOOT;
    this.hitEntity(e, d.grab_damage);
    if (!e.active) this.soltar(quien);
  };

  World.prototype.grabUpdate = function (quien, input) {
    var d = this.data.player, p = this.players[quien], pa = d.actor;
    var e = this.agarrado(quien), ea;
    if (!e) return 0;
    if (p.stun || p.dying) { this.soltar(quien); return 0; }
    if (!p.grabTimer) { this.soltar(quien); return 0; }
    p.grabTimer--;

    ea = this.entityDef(e).actor;
    e.x = p.facing ? p.x + I2F(pa.box_w - 2) : p.x - I2F(ea.box_w - 2);
    e.y = p.y + I2F(pa.box_h - ea.box_h);
    e.vx = 0; e.vy = 0; e.knock = 0;
    e.facing = p.facing ? 0 : 1;
    animSet(e, ANIM_HURT);
    animTick(ea, e);

    if ((input & IN.JUMP) && !(this.prevInput[quien] & IN.JUMP)) {
      this.lanzar(quien, e);
      return 1;
    }
    if ((input & IN.ACTION) && !(this.prevInput[quien] & IN.ACTION)
        && !p.attackCd) {
      p.attackCd = d.attack.cooldown;
      this.rodillazo(quien, e);
    }
    if (p.attackTimer) p.attackTimer--;
    animSet(p, p.attackTimer ? ANIM_ATTACK : ANIM_IDLE);
    animTick(pa, p);
    return 1;
  };

  /* El jugador en la vista de cinta: el "yo contra el barrio". Se anda en
     ocho direcciones como desde arriba, pero se salta, porque hay una tercera
     coordenada -la altura sobre el suelo- con su gravedad. `y` sigue siendo
     donde se dibuja, asi que la linea del suelo es y + altura. Traduccion
     literal de np_player_update_cinta. */
  World.prototype.playerUpdateCinta = function (quien, input) {
    var d = this.data.player, a = d.actor, p = this.players[quien];
    var dx = 0, dy = 0, suelo, pose;

    /* Con alguien agarrado el frame es otro: no se anda, se le zarandea. */
    if (d.grab_time && this.grabUpdate(quien, input)) return;

    /* Aqui no se cae de ningun sitio: si no estas por el aire, estas de pie.
       Igual que np_player_update_cinta, y por el mismo motivo: recien colocado
       el jugador viene con onGround a cero y no podria saltar. */
    if (p.altura <= 0 && p.valtura <= 0) {
      p.altura = 0; p.valtura = 0; p.onGround = 1;
    }

    if (p.stun) { p.stun--; input = 0; }
    else {
      if (input & IN.RIGHT) dx += 1;
      if (input & IN.LEFT) dx -= 1;
      if (input & IN.DOWN) dy += 1;
      if (input & IN.UP) dy -= 1;
    }

    /* La carrera: dos toques seguidos en la misma direccion. Igual que
       np_player_update_cinta. */
    if (p.toque) p.toque--;
    if (!p.stun && dx && !(this.prevInput[quien] & (IN.LEFT | IN.RIGHT))) {
      if (p.toque && p.toqueDir === dx) { p.carrera = CARRERA; p.toque = 0; }
      else { p.toque = TOQUE_VENTANA; p.toqueDir = dx; }
    }
    if (p.carrera) {
      if (p.stun || !dx || dx !== p.toqueDir) p.carrera = 0;
      else p.carrera--;
    }

    /* Andar: solo con los pies en el suelo. En el aire manda el impulso. */
    if (p.onGround) {
      if (dx || dy) {
        var paso = p.carrera ? (d.speed * CARRERA_X2) >> 3 : d.speed;
        p.aim = aimDe(dx, dy);
        if (dx) p.facing = dx > 0 ? 1 : 0;
        p.vx = pasoCenital(paso, dx, dx && dy);
        p.vy = pasoCenital(paso, dy, dx && dy);
      } else if (p.stun) {
        p.vx = approach(p.vx, 0, d.friction);
        p.vy = approach(p.vy, 0, d.friction);
      } else {
        p.vx = 0;
        p.vy = 0;
      }
    }

    /* La linea del suelo, antes de tocar la altura: es lo que no se mueve al
       saltar. Igual que np_player_update_cinta. */
    suelo = p.y + p.altura;

    /* El salto, que aqui es la tercera coordenada. */
    if (!p.stun && (input & IN.JUMP) && !(this.prevInput[quien] & IN.JUMP)
        && p.onGround) {
      p.valtura = d.jump;
      p.onGround = 0;
      this.sfx |= SFX.JUMP;
    }
    if (!p.onGround) {
      p.altura += p.valtura;
      p.valtura -= d.gravity;
      if (p.valtura < -d.max_fall) p.valtura = -d.max_fall;
      if (p.altura <= 0) { p.altura = 0; p.valtura = 0; p.onGround = 1; }
    }

    /* Andar y chocar, en la linea del suelo: saltando se pasa por encima de un
       enemigo, pero no de una pared. */
    p.x = this.moveX(p.x, suelo, a.box_w, a.box_h, p.vx, moveOut);
    if (moveOut.hit) p.vx = 0;
    suelo = this.moveY(p.x, suelo, a.box_w, a.box_h, p.vy, 1, moveOut);
    if (moveOut.hitDown || moveOut.hitUp) p.vy = 0;
    p.y = suelo - p.altura;

    p.jumpsLeft = 0;
    p.stairs = 0;
    p.trepa = 0;
    p.crouch = 0;

    if (p.attackCd) p.attackCd--;
    if ((input & IN.ACTION) && !(this.prevInput[quien] & IN.ACTION)) {
      /* El codazo hacia atras y la patada en salto. Igual que
         np_player_update_cinta. */
      if (!this.hayALado(quien, p.facing) && this.hayALado(quien, !p.facing))
        p.facing = p.facing ? 0 : 1;
      p.fuerte = (!p.onGround || p.carrera) ? 1 : 0;
      p.carrera = 0;
      this.playerAttack(quien);
    }

    if (p.invuln) p.invuln--;
    /* La caja del punetazo, que ademas lleva el reloj del golpe. Igual que
       np_player_update_cinta, y por el mismo motivo no se llama en cenital. */
    this.meleeUpdate(quien);

    if (p.attackTimer) pose = this.esRemate(quien) ? ANIM_FINISH : ANIM_ATTACK;
    else if (!p.onGround) pose = p.valtura > 0 ? ANIM_JUMP : ANIM_FALL;
    else if (!dx && !dy) pose = ANIM_IDLE;
    else if (dy < 0 && !dx) pose = ANIM_UP;
    else if (dy > 0 && !dx) pose = ANIM_DOWN;
    else pose = ANIM_RUN;
    animSet(p, pose);
    animTick(a, p);
  };

  /* --- el jugador isometrico ----------------------------------------
   *
   * Se anda por la planta de la sala en las cuatro direcciones del mapa -que
   * en pantalla salen en diagonal- y se salta de verdad: la altura es la
   * tercera coordenada y el suelo es el relieve de las casillas. Traduccion
   * literal de np_player_update_iso. */
  World.prototype.playerUpdateIso = function (quien, input) {
    var d = this.data.player, a = d.actor, p = this.players[quien];
    var dx = 0, dy = 0, pose, cota;
    var out = {};

    /* Si no estas por el aire, estas de pie: sin esto un jugador recien
       colocado -que viene con onGround a cero- no podria saltar en su primer
       frame. Igual que np_player_update_iso. */
    if (p.altura <= 0 && p.valtura <= 0) {
      p.altura = 0;
      p.valtura = 0;
      p.onGround = 1;
    }

    if (p.stun) { p.stun--; input = 0; }
    else {
      if (input & IN.RIGHT) dx += 1;
      if (input & IN.LEFT) dx -= 1;
      if (input & IN.DOWN) dy += 1;
      if (input & IN.UP) dy -= 1;
    }

    /* Por el aire manda el impulso con el que despegaste. */
    if (p.onGround) {
      if (dx || dy) {
        p.aim = aimDe(dx, dy);
        p.vx = pasoCenital(d.speed, dx, dx && dy);
        p.vy = pasoCenital(d.speed, dy, dx && dy);
        /* el espejo se mira por donde cae en la pantalla (x - y) */
        p.facing = (dx - dy > 0) ? 1 : 0;
      } else if (p.stun) {
        p.vx = approach(p.vx, 0, d.friction);
        p.vy = approach(p.vy, 0, d.friction);
      } else { p.vx = 0; p.vy = 0; }
    }

    if (!p.stun && (input & IN.JUMP) && !(this.prevInput[quien] & IN.JUMP)
        && p.onGround) {
      p.valtura = d.jump;
      p.onGround = 0;
      this.sfx |= SFX.JUMP;
    }
    if (!p.onGround) {
      p.altura += p.valtura;
      p.valtura -= d.gravity;
      if (p.valtura < -d.max_fall) p.valtura = -d.max_fall;
    }

    var chocoX, chocoY;
    p.x = this.isoMove(p.x, p.y, a.box_w, a.box_h, p.vx, p.altura, 0, out);
    chocoX = out.hit;
    p.y = this.isoMove(p.x, p.y, a.box_w, a.box_h, p.vy, p.altura, 1, out);
    chocoY = out.hit;
    /* Chocar solo te para de pie: por el aire el impulso se guarda aunque de
       momento no quepas. Igual que np_player_update_iso. */
    if (p.onGround) {
      if (chocoX) p.vx = 0;
      if (chocoY) p.vy = 0;
    }

    cota = this.isoSuelo(p.x, p.y, a.box_w, a.box_h);
    if (p.valtura <= 0 && p.altura <= cota) {
      p.altura = cota;
      p.valtura = 0;
      p.onGround = 1;
    } else if (p.altura > cota) {
      p.onGround = 0;
    }

    p.jumpsLeft = 0;
    p.stairs = 0;
    p.trepa = 0;
    p.crouch = 0;
    p.riding = 0;

    this.playerAction(quien, input);
    if (p.invuln) p.invuln--;

    if (p.attackTimer) pose = ANIM_ATTACK;
    else if (!p.onGround) pose = (p.valtura > 0) ? ANIM_JUMP : ANIM_FALL;
    else if (!dx && !dy) pose = ANIM_IDLE;
    else pose = (dx + dy < 0) ? ANIM_UP : ANIM_DOWN;
    animSet(p, pose);
    animTick(a, p);
  };

  World.prototype.playerUpdate = function (quien, input) {
    var d = this.data.player, a = d.actor, p = this.players[quien];
    var dir = 0;
    /* Si venia montado en una plataforma, se va con ella antes de nada. */
    if (p.riding && p.riding <= this.entityCount) {
      var montado = this.entities[p.riding - 1];
      if (montado.active && montado.kind === KIND_PLATFORM) {
        if (montado.vx)
          p.x = this.moveX(p.x, p.y, a.box_w, a.box_h, montado.vx, moveOut);
        if (montado.vy)
          p.y = this.moveY(p.x, p.y, a.box_w, a.box_h, montado.vy, 0, moveOut);
      }
    }
    /* Aturdido: el mando no se lee. Igual que en np_player_update. */
    if (p.stun) {
      p.stun--;
      input = 0;
    } else {
      if (input & IN.RIGHT) dir += 1;
      if (input & IN.LEFT) dir -= 1;
    }

    /* Subido a una escalera manda la escalera: ni gravedad, ni saltos, ni
       choques. Igual que en np_player_update. */
    if (p.stairs) {
      p.crouch = 0;                 /* en la escalera no se agacha nadie */
      this.playerAction(quien, input);
      if (!this.stairUpdate(quien, input)) animSet(p, ANIM_IDLE);
      return;
    }
    if (!p.stun && this.stairMount(quien, input)) {
      animSet(p, ANIM_STAIR);
      return;
    }

    /* Colgado de una liana manda la liana. A ella se llega tambien por el
       aire, asi que se prueba a agarrarse sin pisar suelo. Igual que en
       np_player_update. */
    if (p.trepa) {
      p.crouch = 0;
      this.playerAction(quien, input);
      if (!this.climbUpdate(quien, input)) animSet(p, ANIM_IDLE);
      return;
    }
    if (!p.stun && this.climbMount(quien, input)) {
      animSet(p, ANIM_STAIR);
      return;
    }

    /* Con abajo, en el suelo: ni se anda ni se salta, pero se pega y el golpe
       sale por abajo. Igual que en np_player_update. */
    if (d.crouch_drop && p.onGround && (input & IN.DOWN)) {
      p.crouch = 1;
      dir = 0;
    } else {
      p.crouch = 0;
    }

    /* Con `clavado: si` te quedas plantado mientras dura el golpe: ni andas ni
       te giras. Igual que en np_player_update. */
    if (p.attackTimer && d.attack.locks && p.onGround) {
      p.vx = 0;
    } else if (p.stun) {
      /* ni acelerar ni frenar */
    } else if (!d.air_control && !p.onGround) {
      /* El salto de las aventuras: al despegar se decide hacia donde vas y ya
         no se cambia. Igual que en np_player_update. */
    } else if (dir > 0) { p.vx = approach(p.vx, d.speed, p.onGround ? d.accel : d.air_accel); p.facing = 1; }
    else if (dir < 0) { p.vx = approach(p.vx, -d.speed, p.onGround ? d.accel : d.air_accel); p.facing = 0; }
    else if (p.onGround) p.vx = approach(p.vx, 0, d.friction);

    /* El ataque va por flanco: mantener el boton no dispara sin parar. */
    this.playerAction(quien, input);

    /* agachado no se salta: hay que levantarse primero */
    var pressedJump = !p.crouch
      && (input & IN.JUMP) && !(this.prevInput[quien] & IN.JUMP);
    if (pressedJump) p.buffer = d.jump_buffer + 1;
    if (p.buffer) p.buffer--;

    if (p.onGround) {
      p.coyote = d.coyote;
      p.jumpsLeft = d.double_jump ? 1 : 0;
    } else if (p.coyote) p.coyote--;

    if (p.buffer && (p.coyote || p.jumpsLeft)) {
      this.sfx |= p.coyote ? SFX.JUMP : SFX.DJUMP;
      if (!p.coyote) p.jumpsLeft--;
      p.vy = -d.jump;
      p.buffer = 0; p.coyote = 0; p.onGround = 0;
      /* sin control en el aire, el impulso se fija al despegar */
      if (!d.air_control) p.vx = dir > 0 ? d.speed : (dir < 0 ? -d.speed : 0);
    }
    /* el arco fijo de las aventuras: soltar el boton no corta el salto */
    if (d.air_control && !(input & IN.JUMP) && p.vy < -d.jump_cut)
      p.vy = -d.jump_cut;

    p.vy += d.gravity;
    if (p.vy > d.max_fall) p.vy = d.max_fall;

    p.x = this.moveX(p.x, p.y, a.box_w, a.box_h, p.vx, moveOut);
    if (moveOut.hit) p.vx = 0;
    var antesY = p.y;
    p.y = this.moveY(p.x, p.y, a.box_w, a.box_h, p.vy, (input & IN.DOWN) ? 1 : 0, moveOut);
    p.onGround = moveOut.hitDown;
    if (moveOut.hitDown && p.vy > 0) p.vy = 0;
    if (moveOut.hitUp && p.vy < 0) p.vy = 0;
    this.rideUpdate(quien, antesY, (input & IN.DOWN) ? 1 : 0);

    if (p.invuln) p.invuln--;

    /* Agachado manda la pose de agachado, tambien pegando. Igual que en C. */
    if (p.crouch) animSet(p, ANIM_CROUCH);
    else if (p.attackTimer)
      /* en el aire con `patada:`, la pose es la de la patada: lo que se ve
         tiene que ser lo que pega. Igual que np_player_update. */
      animSet(p, this.esPatada(quien) ? ANIM_KICK : ANIM_ATTACK);
    else if (!p.onGround) animSet(p, p.vy < 0 ? ANIM_JUMP : ANIM_FALL);
    else if (p.vx > idiv(FIX_ONE, 8) || p.vx < -idiv(FIX_ONE, 8)) animSet(p, ANIM_RUN);
    else animSet(p, ANIM_IDLE);
    animTick(a, p);
  };

  /* A quien persigue un enemigo: al jugador en juego que tenga mas cerca.
     Igual que np_nearest_player en C. */
  World.prototype.nearestPlayer = function (x) {
    var mejor = this.players[0], distancia = 0, primero = true, i;
    for (i = 0; i < MAX_PLAYERS; i++) {
      var p = this.players[i];
      if (!p.playing || p.dying) continue;
      var d = Math.abs(p.x - x);
      if (primero || d < distancia) { mejor = p; distancia = d; primero = false; }
    }
    return mejor;
  };

  /* Si hay donde pisar al otro lado del borde. Igual que np_suelo_delante. */
  World.prototype.sueloDelante = function (e, a, haciaLaDerecha) {
    var borde = haciaLaDerecha ? F2I(e.x + I2F(a.box_w) - 1) + 1 : F2I(e.x) - 1;
    var debajo = F2I(e.y + I2F(a.box_h));
    var tipo = this.tileKindAt(borde >> TILE_SHIFT, debajo >> TILE_SHIFT);
    return tipo === TILE_SOLID || tipo === TILE_PLATFORM;
  };

  /* --------------------------------------- lo que tiran los enemigos
   *
   * Traduccion literal de np_enemy_shoot / np_enemy_shot_update. La cuenta
   * atras del enemigo va en `vida`, que en un enemigo no se usa para nada
   * mas. */
  World.prototype.enemyShoot = function (e, d) {
    var sd = this.data.enemy_shots[d.shot - 1];
    var ea = d.actor, pa = this.data.player.actor;
    var p = this.nearestPlayer(e.x);
    var dx = (p.x + I2F(idiv(pa.box_w, 2))) - (e.x + I2F(idiv(ea.box_w, 2)));
    var dy = (p.y + I2F(idiv(pa.box_h, 2))) - (e.y + I2F(idiv(ea.box_h, 2)));
    var ax, ay, b, hueco;
    if (abs(dx) > I2F(sd.range) || abs(dy) > I2F(sd.range)) return;
    hueco = this.huecoLibre();
    if (hueco < 0) return;
    e.vida = sd.cooldown;

    if (this.cenital()) {
      var ex = abs(dx), ey = abs(dy);
      ax = (ex * 2 > ey) ? ((dx > 0) - (dx < 0)) : 0;
      ay = (ey * 2 > ex) ? ((dy > 0) - (dy < 0)) : 0;
      if (!ax && !ay) ax = e.facing ? 1 : -1;
    } else {
      ax = dx > 0 ? 1 : -1;
      ay = 0;
      e.facing = ax > 0 ? 1 : 0;
    }

    b = this.entities[hueco];
    b.active = 1;
    b.kind = KIND_ENEMY_SHOT;
    b.def = d.shot - 1;
    b.facing = ax >= 0 ? 1 : 0;
    b.x = e.x + I2F(idiv(ea.box_w - sd.actor.box_w, 2)
                    + ax * (idiv(ea.box_w, 2) + 1));
    b.y = e.y + I2F(idiv(ea.box_h - sd.actor.box_h, 2)
                    + ay * (idiv(ea.box_h, 2) + 1));
    b.vx = pasoCenital(sd.speed, ax, ax && ay);
    b.vy = pasoCenital(sd.speed, ay, ax && ay);
    b.homeX = b.x; b.homeY = b.y;
    b.health = 1; b.hurt = 0; b.timer = 0;
    b.anim = ANIM_IDLE; b.animFrame = 0; b.animTimer = 0;
    b.vida = sd.speed ? idiv(I2F(sd.range), sd.speed) + 1 : 1;
    this.sfx |= SFX.SHOOT;
  };

  World.prototype.enemyShotUpdate = function (e) {
    var sd = this.data.enemy_shots[e.def], a = sd.actor;
    var pa = this.data.player.actor, quien;
    if (!e.vida) { e.active = 0; return; }
    e.vida--;
    if (e.vx) {
      e.x = this.moveX(e.x, e.y, a.box_w, a.box_h, e.vx, moveOut);
      if (moveOut.hit) { e.active = 0; return; }
    }
    if (e.vy) {
      e.y = this.moveY(e.x, e.y, a.box_w, a.box_h, e.vy, 1, moveOut);
      if (moveOut.hitDown || moveOut.hitUp) { e.active = 0; return; }
    }
    for (quien = 0; quien < MAX_PLAYERS; quien++) {
      var p = this.players[quien];
      if (!p.playing || p.dying) continue;
      if (!overlap(e.x, e.y, a.box_w, a.box_h,
                   p.x, this.playerTop(quien),
                   pa.box_w, this.playerHeight(quien))) continue;
      this.playerHurt(quien, sd.damage);
      e.active = 0;
      return;
    }
    animTick(a, e);
  };

  /* ------------------------------------------------ los prisioneros
   *
   * Traduccion literal de np_prisoner_free / np_prisoner_update. `timer` a
   * cero quiere decir que sigue atado. */
  World.prototype.prisonerFree = function (e, p) {
    var d = this.data.prisoners[e.def];
    if (e.timer) return;
    e.timer = d.escape ? d.escape : 1;
    this.score += d.score;
    this.sfx |= SFX.COIN;
    if (this.cenital()) {
      e.vy = (e.y < p.y) ? -d.speed : d.speed;
      e.vx = 0;
    } else {
      e.vx = (e.x < p.x) ? -d.speed : d.speed;
      e.facing = e.vx > 0 ? 1 : 0;
    }
  };

  /* ------------------------------------------ generadores de bichos */
  /* Los nidos de Gauntlet: cada `cooldown` frames sacan un enemigo, hasta que
     los destruyes. Igual que np_generator_update en C, paso por paso: el orden
     en que se pide hueco en la lista tiene que ser el mismo o la paridad
     falla. */
  World.prototype.cuantosBichos = function (def) {
    var i, cuantos = 0;
    for (i = 0; i < this.entityCount; i++) {
      var e = this.entities[i];
      if (e.active && e.kind === KIND_ENEMY && e.def === def) cuantos++;
    }
    return cuantos;
  };

  World.prototype.generatorUpdate = function (e) {
    var d = this.data.generators[e.def], a = d.actor;
    animSet(e, ANIM_IDLE);
    animTick(a, e);
    /* la cuenta va hacia arriba, igual que la del desgaste */
    if (++e.timer < d.cooldown) return;
    e.timer = 0;
    if (this.cuantosBichos(d.enemy) >= d.cap) return;
    var hueco = this.huecoLibre();
    if (hueco < 0) return;               /* no cabe: este bicho no sale */
    var b = this.entities[hueco];
    var ed = this.data.enemies[d.enemy], ba = ed.actor;
    b.active = 1;
    b.kind = KIND_ENEMY;
    b.def = d.enemy;
    b.x = e.x + I2F((a.box_w >> 1) - (ba.box_w >> 1));
    b.y = e.y + I2F(a.box_h - ba.box_h);
    b.homeX = b.x;
    b.homeY = b.y;
    b.vx = ed.speed;
    b.vy = 0;
    b.facing = 1;
    b.health = ed.health;
    b.hurt = 0;
    b.vida = 0;
    b.timer = ed.interval;
    b.anim = ANIM_IDLE;
    b.animFrame = 0;
    b.animTimer = 0;
  };

  World.prototype.prisonerUpdate = function (e) {
    var d = this.data.prisoners[e.def], a = d.actor;
    if (!e.timer) {
      animSet(e, ANIM_IDLE);
      animTick(a, e);
      return;
    }
    e.timer--;
    if (!e.timer) { e.active = 0; return; }
    if (e.vx) {
      e.x = this.moveX(e.x, e.y, a.box_w, a.box_h, e.vx, moveOut);
      if (moveOut.hit) e.vx = -e.vx;
    }
    if (e.vy) {
      e.y = this.moveY(e.x, e.y, a.box_w, a.box_h, e.vy, 1, moveOut);
      if (moveOut.hitDown || moveOut.hitUp) e.vy = -e.vy;
    }
    animSet(e, ANIM_RUN);
    animTick(a, e);
  };

  /* ----------------------------------------------------- el luchador */
  /*
   * Un enemigo que anda en linea recta hacia ti y te hace dano al rozarte no da
   * una pelea: da un enjambre. Estas cuatro cosas son las que la convierten en
   * una pelea, y son las mismas que hace np_lucha_update en C:
   *
   *   1. se coloca a la distancia de su golpe y no se te mete dentro;
   *   2. espera turno: solo `agresivos` pegan a la vez;
   *   3. se le ve venir (`preparacion:`);
   *   4. despues del golpe se queda plantado: esa es tu ventana.
   */

  /* La distancia a la que se pelea: lo justo para que su golpe llegue. */
  function luchaCerca(d, a) { return I2F(a.box_w + d.reach - 8); }

  /* Su golpe: una caja delante, mientras dura la fase de pegar. */
  World.prototype.luchaPegar = function (e, d, a) {
    var pa = this.data.player.actor, quien;
    var gx = e.facing ? e.x + I2F(a.box_w) : e.x - I2F(d.reach);
    for (quien = 0; quien < MAX_PLAYERS; quien++) {
      var p = this.players[quien];
      if (!p.playing || p.dying) continue;
      if (e.tocado & (1 << quien)) continue;
      if (!overlap(gx, e.y, d.reach, a.box_h,
                   p.x, this.playerTop(quien), pa.box_w, this.playerHeight(quien)))
        continue;
      e.tocado |= (1 << quien);
      if (p.invuln) continue;
      this.playerHurt(quien, d.punch ? d.punch : d.damage);
      this.congelado = CONGELADO;
    }
    /* Y con `entre_ellos:`, ese mismo golpe le da al de al lado. Es lo que
       convierte a dos perseguidores en una herramienta. Igual que en
       np_lucha_pegar. */
    if (this.data.entre_ellos) {
      for (var i = 0; i < this.entityCount; i++) {
        var o = this.entities[i];
        if (o === e || !o.active || o.kind !== KIND_ENEMY) continue;
        if (o.hurt) continue;
        var oa = this.entityDef(o).actor;
        if (!overlap(gx, e.y, d.reach, a.box_h, o.x, o.y, oa.box_w, oa.box_h))
          continue;
        this.hitEnemy(o, d.punch ? d.punch : d.damage);
        this.congelado = CONGELADO;
      }
    }
  };

  /* Que no se amontonen: si esta encima de otro se aparta por profundidad, que
     es por donde hay sitio en una calle. Igual que np_lucha_separar. */
  World.prototype.luchaSeparar = function (e, a) {
    for (var i = 0; i < this.entityCount; i++) {
      var o = this.entities[i];
      if (o === e || !o.active || o.kind !== KIND_ENEMY) continue;
      var oa = this.entityDef(o).actor;
      if (!overlap(e.x, e.y, a.box_w, a.box_h, o.x, o.y, oa.box_w, oa.box_h))
        continue;
      e.y += (e.y <= o.y) ? -I2F(1) : I2F(1);
      return;
    }
  };

  World.prototype.luchaUpdate = function (e, d, a, p) {
    var dx = p.x - e.x;
    var dy = (p.y + p.altura) - e.y;
    var lejos = abs(dx);
    var cerca = luchaCerca(d, a);
    var anillo = cerca + I2F(22);
    /* De perfil no hay profundidad: la `y` es lo alto y ahi manda la gravedad.
       El que pelea de perfil hace lo mismo pero solo en x. Igual que el
       `plano` de np_lucha_update. */
    var plano = !this.cinta();
    var ranura = plano ? 0 : (this.entities.indexOf(e) % 3 - 1) * 14;
    var haciaY, ex = 0, ey = 0, puede;

    if (!plano) this.luchaSeparar(e, a);
    if (e.timer) e.timer--;
    if (dx) e.facing = dx > 0 ? 1 : 0;

    switch (e.fase) {
      case LUCHA_PREPARAR:
        e.vx = 0; if (!plano) e.vy = 0;
        if (!e.timer) { e.fase = LUCHA_GOLPEAR; e.timer = d.active; e.tocado = 0; }
        animSet(e, ANIM_ATTACK);
        return;
      case LUCHA_GOLPEAR:
        e.vx = 0; if (!plano) e.vy = 0;
        this.luchaPegar(e, d, a);
        if (!e.timer) { e.fase = LUCHA_RECUPERAR; e.timer = d.recover; }
        animSet(e, ANIM_ATTACK);
        return;
      case LUCHA_RECUPERAR:
        e.vx = 0; if (!plano) e.vy = 0;
        if (!e.timer) { e.fase = LUCHA_REPLEGAR; e.timer = d.wait; }
        animSet(e, ANIM_IDLE);
        return;
      case LUCHA_REPLEGAR:
        ex = dx > 0 ? -1 : 1;
        if (abs(dy) > I2F(2)) ey = dy > 0 ? -1 : 1;
        if (lejos > anillo + I2F(16)) { ex = 0; ey = 0; }
        if (!e.timer) e.fase = LUCHA_IR;
        break;
      default: {
        /* Te rodean -cada uno por su lado- y el que tiene turno se pone en tu
           linea mientras los demas se apartan a la suya. Igual que
           np_lucha_update. */
        puede = this.atacando < this.data.agresivos;
        var lado = (this.entities.indexOf(e) & 1) ? -1 : 1;
        var quiero = puede ? cerca : anillo;
        var destino = p.x + lado * quiero;
        var huecoX = destino - e.x;
        /* "Estar en su sitio" es la misma medida que decide si puede pegar,
           y no dos parecidas. Igual que np_lucha_update. */
        var enSuSitio = abs(huecoX) <= I2F(6);
        if (!enSuSitio) ex = huecoX > 0 ? 1 : -1;
        haciaY = (p.y + p.altura) + I2F((puede && enSuSitio) ? 0 : ranura);
        if (!plano) {
          var hueco = haciaY - e.y;
          if (abs(hueco) > I2F(2)) ey = hueco > 0 ? 1 : -1;
        }
        e.fase = (lejos <= anillo + I2F(8)) ? LUCHA_RONDAR : LUCHA_IR;
        if (puede && !e.timer && enSuSitio && abs(dy) <= I2F(7)) {
          e.fase = LUCHA_PREPARAR;
          e.timer = d.windup;
          e.vx = 0; if (!plano) e.vy = 0;
          this.atacando++;
          animSet(e, ANIM_ATTACK);
          return;
        }
        break;
      }
    }
    e.vx = pasoCenital(d.speed, ex, ex && ey);
    if (!plano) e.vy = pasoCenital(d.speed, ey, ex && ey);
    animSet(e, (ex || ey) ? ANIM_RUN : ANIM_IDLE);
  };

  World.prototype.enemyUpdate = function (e) {
    var d = this.data.enemies[e.def], a = d.actor, p = this.nearestPlayer(e.x);
    /* Derribado por un remate: no decide nada, solo resbala con el empujon que
       se llevo. Igual que np_enemy_update. */
    if (e.knock) {
      var suelo = e.y + e.altura;
      e.knock--;
      /* tumbado se pierde el turno. Igual que np_enemy_update. */
      e.fase = LUCHA_IR;
      /* Si viene de un lanzamiento, ademas vuela. Igual que np_enemy_update. */
      if (e.altura > 0 || e.valtura) {
        e.altura += e.valtura;
        e.valtura -= this.data.player.gravity;
        if (e.altura <= 0) { e.altura = 0; e.valtura = 0; }
      }
      e.x = this.moveX(e.x, suelo, a.box_w, a.box_h, e.vx, moveOut);
      if (moveOut.hit) e.vx = 0;
      e.y = suelo - e.altura;
      /* por el aire no se frena: se frena al tocar el suelo */
      if (!e.altura) e.vx = approach(e.vx, 0, this.data.player.friction);
      animSet(e, ANIM_HURT);
      animTick(a, e);
      return;
    }
    /* Tambaleandose de un golpe: ni decide ni anda. Igual que
       np_enemy_update: va antes que la IA y despues del derribo. */
    if (e.aturdido) {
      e.aturdido--;
      e.vx = approach(e.vx, 0, this.data.player.friction);
      e.vy = approach(e.vy, 0, this.data.player.friction);
      e.x = this.moveX(e.x, e.y, a.box_w, a.box_h, e.vx, moveOut);
      if (moveOut.hit) e.vx = 0;
      animSet(e, ANIM_HURT);
      animTick(a, e);
      return;
    }

    switch (d.behavior) {
      case AI_PATROL:
        e.vx = e.facing ? d.speed : -d.speed;
        break;
      case AI_FLYER: {
        var period = d.period ? d.period : 1;
        e.vx = e.facing ? d.speed : -d.speed;
        e.timer = (e.timer + 1) % period;
        var phase = this.data.sin[(idiv(e.timer * 64, period)) & 63];
        /* En la isometrica lo que sube y baja es la altura, no la fila del
           mapa: un bicho que flota sobre los cubos. Igual que en C. */
        if (this.iso())
          e.altura = d.amplitude + ((d.amplitude * phase) >> FIX_SHIFT);
        else
          e.y = e.homeY + ((d.amplitude * phase) >> FIX_SHIFT);
        break;
      }
      case AI_CHASER: {
        var dx = p.x - e.x;
        /* En la vista de cinta un perseguidor no persigue: pelea. Igual que
           np_enemy_update en C. */
        if (d.reach) { this.luchaUpdate(e, d, a, p); break; }
        if (this.cenital()) {
          /* desde arriba se persigue en los dos ejes: igual que en C */
          var dyc = p.y - e.y;
          if (abs(dx) <= d.range && abs(dyc) <= d.range) {
            var ex = (dx > 0) - (dx < 0), ey = (dyc > 0) - (dyc < 0);
            e.vx = pasoCenital(d.speed, ex, ex && ey);
            e.vy = pasoCenital(d.speed, ey, ex && ey);
            if (ex) e.facing = ex > 0 ? 1 : 0;
          } else {
            e.vx = approach(e.vx, 0, d.speed);
            e.vy = approach(e.vy, 0, d.speed);
          }
          break;
        }
        if (abs(dx) <= d.range) { e.vx = dx > 0 ? d.speed : -d.speed; e.facing = dx > 0 ? 1 : 0; }
        else e.vx = approach(e.vx, 0, d.speed);
        /* con un agujero delante se planta en el borde en vez de tirarse por
           el: ver np_enemy_update en np_world.c */
        if (d.edge_turn && e.vx !== 0 && e.vy === 0 &&
            !this.sueloDelante(e, a, e.vx > 0)) e.vx = 0;
        break;
      }
      case AI_JUMPER:
        e.vx = e.facing ? d.speed : -d.speed;
        if (e.timer) e.timer--;
        else if (e.vy === 0) { e.vy = -d.jump; e.timer = d.interval; }
        break;
      default:
        e.vx = 0;
        break;
    }

    /* la gravedad es de la vista lateral: desde arriba nadie cae */
    if (d.behavior !== AI_FLYER && !this.cenital()) {
      e.vy += d.gravity;
      if (e.vy > ENTITY_FALL) e.vy = ENTITY_FALL;
    }

    if (this.iso()) {
      /* Por la planta, con el relieve delante: un cubo frena a un bicho igual
         que a ti. Igual que np_enemy_update. */
      e.x = this.isoMove(e.x, e.y, a.box_w, a.box_h, e.vx, e.altura, 0, moveOut);
      if (moveOut.hit) { e.facing = e.facing ? 0 : 1; e.vx = 0; }
      e.y = this.isoMove(e.x, e.y, a.box_w, a.box_h, e.vy, e.altura, 1, moveOut);
      if (moveOut.hit) e.vy = 0;
      if (d.behavior !== AI_FLYER)
        e.altura = this.isoSuelo(e.x, e.y, a.box_w, a.box_h);
      animSet(e, (e.vx || e.vy) ? ANIM_RUN : ANIM_IDLE);
      animTick(a, e);
      if (d.shot) {
        if (e.vida) e.vida--;
        else this.enemyShoot(e, d);
      }
      return;
    }

    e.x = this.moveX(e.x, e.y, a.box_w, a.box_h, e.vx, moveOut);
    if (moveOut.hit) { e.facing = e.facing ? 0 : 1; e.vx = 0; }
    if (this.cenital()) {
      /* desde arriba las paredes frenan tambien por arriba y por abajo */
      if (e.vy) {
        e.y = this.moveY(e.x, e.y, a.box_w, a.box_h, e.vy, 1, moveOut);
        if (moveOut.hitDown || moveOut.hitUp) e.vy = 0;
      }
    } else if (d.behavior !== AI_FLYER) {
      e.y = this.moveY(e.x, e.y, a.box_w, a.box_h, e.vy, 0, moveOut);
      if (moveOut.hitDown && e.vy > 0) e.vy = 0;
      if (moveOut.hitUp && e.vy < 0) e.vy = 0;
      if (moveOut.hitDown && d.edge_turn && d.behavior === AI_PATROL &&
          !this.sueloDelante(e, a, e.facing)) e.facing = e.facing ? 0 : 1;
    }

    /* `facing` manda sobre `vx`: recalcularlo aqui deshacia el giro en los
     * bordes y en las paredes (ver np_world.c). */
    animSet(e, (e.vx || (this.cenital() && e.vy)) ? ANIM_RUN : ANIM_IDLE);
    animTick(a, e);

    /* y si lleva `dispara:`, te tirotea */
    if (d.shot) {
      if (e.vida) e.vida--;
      else this.enemyShoot(e, d);
    }

    /* caerse del mapa mata al enemigo (en cenital no hay de donde caerse) */
    if (!this.cenital() && F2I(e.y) > (this.level.height + 2) * TILE)
      e.active = 0;
  };

  World.prototype.itemUpdate = function (e) {
    var d = this.data.items[e.def];
    /* los frames de gracia de lo que se acaba de soltar */
    if (e.timer) e.timer--;
    animSet(e, ANIM_IDLE);
    animTick(d.actor, e);
  };

  /* La pocima de Gauntlet: todo lo que **se ve** recibe un golpe. Lo que se
     ve y no el nivel entero, que se cargaria el juego. Igual que np_bomba. */
  World.prototype.bomba = function (dano) {
    var i;
    if (!dano) dano = 1;
    for (i = 0; i < this.entityCount; i++) {
      var e = this.entities[i];
      if (!e.active) continue;
      if (e.kind !== KIND_ENEMY && e.kind !== KIND_GENERATOR
          && e.kind !== KIND_BREAKABLE) continue;
      var ea = this.entityDef(e).actor;
      if (F2I(e.x) + ea.box_w <= this.camX) continue;
      if (F2I(e.x) >= this.camX + SCREEN_W) continue;
      if (F2I(e.y) + ea.box_h <= this.camY) continue;
      if (F2I(e.y) >= this.camY + SCREEN_H) continue;
      this.hitEntity(e, dano);
    }
  };

  /* Lo recoge quien lo toca: la vida y la salud van a ese jugador, y los
     puntos y las llaves al marcador, que es comun. */
  /* ------------------------------------------------------------ la bolsa
   *
   * Lo que llevas encima, que en una aventura es medio juego. Traduccion
   * literal de np_bolsa_meter / np_bolsa_sacar / np_bolsa_busca. */
  World.prototype.bolsaMeter = function (objeto) {
    for (var i = 0; i < BOLSA; i++) {
      if (this.bolsa[i]) continue;
      this.bolsa[i] = objeto + 1;
      return true;
    }
    return false;                  /* llena: se queda en el suelo */
  };

  World.prototype.bolsaCuantos = function () {
    var n = 0;
    for (var i = 0; i < BOLSA; i++) if (this.bolsa[i]) n++;
    return n;
  };

  World.prototype.bolsaSacar = function () {
    var primero = this.bolsa[0], i;
    if (!primero) return 0;
    for (i = 1; i < BOLSA; i++) this.bolsa[i - 1] = this.bolsa[i];
    this.bolsa[BOLSA - 1] = 0;
    return primero;
  };

  World.prototype.bolsaBusca = function (objeto) {
    for (var i = 0; i < BOLSA; i++)
      if (this.bolsa[i] === objeto + 1) return i + 1;
    return 0;
  };

  /* Soltar lo primero: cae a tus pies, con unos frames de gracia para que no
     lo vuelvas a coger donde lo acabas de dejar. Igual que np_soltar_objeto. */
  World.prototype.soltarObjeto = function (quien) {
    var p = this.players[quien], pa = this.data.player.actor;
    var objeto = this.bolsa[0];
    if (!objeto) return;
    var hueco = this.huecoLibre();
    if (hueco < 0) return;
    this.bolsaSacar();
    objeto--;
    var d = this.data.items[objeto], ia = d.actor, e = this.entities[hueco];
    e.active = 1;
    e.kind = KIND_ITEM;
    e.def = objeto;
    e.x = p.x + I2F(idiv(pa.box_w - ia.box_w, 2));
    e.y = p.y + I2F(pa.box_h - ia.box_h);
    e.homeX = e.x; e.homeY = e.y;
    e.vx = 0; e.vy = 0;
    e.health = 1; e.hurt = 0; e.knock = 0; e.golpeado = 0;
    e.altura = 0; e.valtura = 0; e.vida = 0;
    e.fase = LUCHA_IR; e.tocado = 0; e.aturdido = 0;
    e.timer = GRACIA_SOLTAR;
    e.anim = ANIM_IDLE; e.animFrame = 0; e.animTimer = 0;
    this.sfx |= SFX.COIN;
  };

  World.prototype.collect = function (quien, e) {
    var d = this.data.items[e.def], p = this.players[quien];
    this.score += d.score;
    this.sfx |= (d.effect === 1) ? SFX.LIFE : SFX.COIN;
    if (d.effect === 1) { if (p.lives < 99) p.lives += d.amount; }
    else if (d.effect === 2) {
      p.health = Math.min(p.health + d.amount, this.data.player.health);
    } else if (d.effect === 3) { if (this.keys < 255) this.keys += d.amount; }
    else if (d.effect === 4) { this.hearts = Math.min(this.hearts + d.amount, 99); }
    else if (d.effect === 5) {
      var at = this.data.player.attack;
      p.power = Math.min(p.power + d.amount, at ? at.levels : 0);
    } else if (d.effect === 6) {
      /* cambia el arma secundaria: `amount` es su numero en la lista */
      if (d.amount < this.data.player.subs.length) this.sub = d.amount;
    } else if (d.effect === 7) {
      this.bomba(d.amount);
    } else if (d.effect === 8) {
      /* el objeto que se lleva: si no cabe en la bolsa **se queda donde
         estaba**, que es lo que obliga a elegir. Igual que np_collect. */
      if (!this.bolsaMeter(e.def)) return;
    }
    e.active = 0;
  };

  /* Los puntos de control. Se busca **la casilla**, no solo si toca alguna,
     porque lo que hay que guardar es donde estaba. Volver a pasar por el que
     ya esta marcado no hace nada; pasar por uno anterior si lo mueve hacia
     atras. Igual que np_check_touch en C. */
  /* Abrir lo que se pueda de lo que tienes al lado: la puerta se abre con el
     objeto que pide, el objeto se gasta y la casilla queda abierta para
     siempre. Igual que np_abrir_cerrojos. */
  /* Apunta una casilla como abierta; 0 si la lista ya estaba llena. */
  World.prototype.apuntarAbierta = function (casilla) {
    if (this.abiertos.length >= MAX_ABIERTOS) return 0;
    this.abiertos.push(casilla);
    return 1;
  };

  /* Una puerta de dos casillas es una puerta, no dos: se abre entera con un
     solo objeto. Igual que np_abrir_vecinas. */
  World.prototype.abrirVecinas = function (tx, ty, tile) {
    var pasos = [[0, -1], [0, 1], [-1, 0], [1, 0]], d;
    for (d = 0; d < 4; d++) {
      var x = tx, y = ty;
      for (;;) {
        x += pasos[d][0];
        y += pasos[d][1];
        if (x < 0 || y < 0 || x >= this.level.cells_w
            || y >= this.level.cells_h) break;
        var casilla = y * this.level.cells_w + x;
        if (this.level.cells[casilla] !== tile) break;
        if (this.tileVisto(x, y) !== TILE_LOCK) break;
        if (!this.apuntarAbierta(casilla)) return;
      }
    }
  };

  World.prototype.abrirCerrojos = function (tx0, ty0, tx1, ty1) {
    if (!this.data.bolsa_activa) return;
    for (var ty = ty0; ty <= ty1; ty++) {
      for (var tx = tx0; tx <= tx1; tx++) {
        if (tx < 0 || ty < 0 || tx >= this.level.cells_w
            || ty >= this.level.cells_h) continue;
        if (this.tileVisto(tx, ty) !== TILE_LOCK) continue;
        var casilla = ty * this.level.cells_w + tx;
        var pide = this.data.tiles.need[this.level.cells[casilla]];
        if (!pide) continue;
        var hueco = this.bolsaBusca(pide - 1);
        if (!hueco) continue;
        if (this.abiertos.length >= MAX_ABIERTOS) return;
        for (var i = hueco - 1; i + 1 < BOLSA; i++)
          this.bolsa[i] = this.bolsa[i + 1];
        this.bolsa[BOLSA - 1] = 0;
        this.apuntarAbierta(casilla);
        this.abrirVecinas(tx, ty, this.level.cells[casilla]);
        this.sfx |= SFX.CHECK;
      }
    }
  };

  World.prototype.checkTouch = function (quien) {
    var a = this.data.player.actor, p = this.players[quien];
    var tx0 = F2I(p.x) >> TILE_SHIFT;
    var tx1 = F2I(p.x + I2F(a.box_w) - 1) >> TILE_SHIFT;
    var ty0 = F2I(p.y) >> TILE_SHIFT;
    var ty1 = F2I(p.y + I2F(a.box_h) - 1) >> TILE_SHIFT;
    var tx, ty;
    /* Los cerrojos se miran un poco mas alla de la caja: una puerta se abre
       poniendote delante. Igual que np_check_touch. */
    this.abrirCerrojos(tx0 - 1, ty0, tx1 + 1, ty1);
    for (ty = ty0; ty <= ty1; ty++) {
      for (tx = tx0; tx <= tx1; tx++) {
        if (this.tileVisto(tx, ty) !== TILE_CHECK) continue;
        if (this.checkOn && this.checkX === tx && this.checkY === ty) return;
        this.checkOn = 1;
        this.checkX = tx;
        this.checkY = ty;
        this.sfx |= SFX.CHECK;
        return;
      }
    }
  };

  /* Jugador por jugador y, dentro, entidad por entidad: el mismo orden que
     np_touch_entities en C. */
  World.prototype.touchEntities = function () {
    var pa = this.data.player.actor, quien, i;
    for (quien = 0; quien < MAX_PLAYERS; quien++) {
      var p = this.players[quien];
      if (!p.playing || p.dying) continue;
      for (i = 0; i < this.entityCount; i++) {
        var e = this.entities[i];
        if (!e.active) continue;
        var ea = this.entityDef(e).actor;
        if (!overlap(p.x, this.playerTop(quien), pa.box_w,
                     this.playerHeight(quien),
                     e.x, e.y, ea.box_w, ea.box_h)) continue;
        /* En la isometrica hay que cruzarse tambien en altura: saltar por
           encima de un bicho es esquivarlo. Igual que np_touch_entities. */
        if (this.iso()) {
          var huecoZ = p.altura - e.altura;
          if (huecoZ > I2F(12) || huecoZ < -I2F(12)) continue;
        }
        if (e.kind === KIND_SHOT || e.kind === KIND_SUBSHOT)
          continue;                              /* es tuyo: no te toca */
        if (e.kind === KIND_MELEE) continue;     /* es tu propio latigo */
        if (e.kind === KIND_PLATFORM) continue;  /* es suelo, no un bicho */
        if (e.kind === KIND_GENERATOR) continue; /* hay que pegarle, y no hace dano */
        /* uno en el suelo no hace dano: por eso se remata */
        if (e.kind === KIND_ENEMY && e.knock) continue;
        /* Y al que se tambalea de un golpe se le coge. Igual que
           np_touch_entities: se mira el parpadeo, o sea que acabas de
           tocarle, para que el agarre sea algo que te ganas. */
        if (this.data.player.grab_time && e.kind === KIND_ENEMY
            && e.hurt && !p.grab && !p.dying) {
          p.grab = i + 1;
          p.grabTimer = this.data.player.grab_time;
          e.knock = 0;
          this.sfx |= SFX.STOMP;
          continue;
        }
        if (e.kind === KIND_BREAKABLE) continue; /* hay que pegarle */
        if (e.kind === KIND_ENEMY_SHOT) continue;   /* se mira en su update */
        if (e.kind === KIND_PRISONER) { this.prisonerFree(e, p); continue; }
        /* lo que acabas de soltar no se recoge solo */
        if (e.kind === KIND_ITEM) {
          if (!e.timer) this.collect(quien, e);
          continue;
        }
        var d = this.data.enemies[e.def];
        /* En una pelea, rozar a alguien no hace dano: hace dano su golpe.
           Igual que np_touch_entities en C. */
        if (d.reach) continue;
        /* Misma ventana de pisado que np_world.c: cayendo y con los pies por
           encima de la mitad del enemigo antes de moverse. */
        var fromAbove = p.vy > 0 &&
          (p.y + I2F(pa.box_h) - p.vy) <= e.y + I2F(idiv(ea.box_h, 2));
        if (this.data.player.stomp && d.stompable && fromAbove) {
          this.sfx |= SFX.STOMP;
          if (e.health > 1) { e.health--; e.hurt = 20; }
          else {
            e.active = 0;
            this.score += d.score;
            /* matar al jefe termina el nivel, como llegar a la meta */
            if (d.boss) this.finishLevel();
          }
          p.vy = -this.data.player.bounce;
          p.onGround = 0;
        } else {
          /* En un juego de tortas el que te acaba de pegar se aparta: pega y
             recula, como en los recreativos. Igual que np_touch_entities. */
          var cobrado = !p.invuln && !p.dying;
          this.playerHurt(quien, d.damage);
          if (this.cinta() && cobrado) {
            e.knock = RECULA;
            e.vx = e.x < p.x ? -this.data.player.knockback
                             : this.data.player.knockback;
            e.vy = 0;
          }
        }
      }
    }
  };

  /* Dos modos de camara, igual que np_world.c: 'scroll' desliza el escenario y
     'pantallas' salta de una pantalla fija a la siguiente. */
  /* En que orden se dibujan las entidades: de mas lejos a mas cerca en la
     vista de cinta -donde los actores se pisan a cada rato y hay un "detras"
     de verdad- y en el orden de la lista en las demas. Gemelo de
     np_orden_dibujo, para que el preview reparta como las siete maquinas. */
  /* La hondura de un puesto: cuanto mas grande, mas cerca de quien mira y mas
     tarde se dibuja. Igual que np_hondura. */
  World.prototype.hondura = function (puesto) {
    if (puesto >= MAX_ENTITIES) {
      var p = this.players[puesto - MAX_ENTITIES];
      return this.iso() ? (p.x + p.y + (p.altura >> 3)) : (p.y + p.altura);
    }
    var e = this.entities[puesto];
    return this.iso() ? (e.x + e.y + (e.altura >> 3)) : (e.y + e.altura);
  };

  World.prototype.ordenDibujo = function () {
    var orden = [], i;
    var iso = this.iso();
    for (i = 0; i < this.entityCount; i++) {
      if (!this.entities[i].active) continue;
      /* Lo que esta en otra habitacion no se dibuja, asi que tampoco entra en
         la fila ni se ordena. */
      if (iso && !this.enLaSala(this.entities[i])) continue;
      orden.push(i);
    }
    if (!this.cinta() && !iso) return orden;
    if (iso) {
      /* Los cubos de la sala, que viven al final de la lista, del ultimo hacia
         atras: asi salen en orden de profundidad. Y los jugadores, que en esta
         vista entran en la fila porque hay un detras de verdad. */
      for (i = 0; i < this.bloquesN; i++) orden.push(MAX_ENTITIES - 1 - i);
      for (i = 0; i < MAX_PLAYERS; i++) orden.push(MAX_ENTITIES + i);
    }
    for (i = 1; i < orden.length; i++) {
      var sitio = orden[i];
      var hondo = this.hondura(sitio);
      var j = i - 1;
      while (j >= 0 && this.hondura(orden[j]) > hondo) {
        orden[j + 1] = orden[j];
        j--;
      }
      orden[j + 1] = sitio;
    }
    return orden;
  };

  /* Que se dibuja en un puesto de la fila y donde cae (sin restar la camara).
     Devuelve null cuando ahi no hay nada que pintar. Gemelo de np_dibujo. */
  /* Esta esa entidad en la sala que se esta viendo? */
  World.prototype.enLaSala = function (e) {
    var px = Math.max(0, F2I(e.x)), py = Math.max(0, F2I(e.y));
    return (px >> SALA_SHIFT) === this.salaX && (py >> SALA_SHIFT) === this.salaY;
  };

  World.prototype.dibujo = function (puesto) {
    var def, punto;
    if (puesto >= MAX_ENTITIES) {
      var quien = puesto - MAX_ENTITIES;
      var p = this.players[quien];
      if (!this.playerVisible(quien)) return null;
      def = this.data.player.actor;
      punto = this.pantalla(p.x, p.y, p.altura, def);
      return { def: def, sx: punto.sx, sy: punto.sy,
               frame: actorFrame(def, p.anim, p.animFrame), flip: !p.facing };
    }
    var e = this.entities[puesto];
    if (!e || !e.active) return null;
    if (e.hurt && (this.frame & 1)) return null;
    /* Lo que esta en otra habitacion caeria encima de esta: no se pinta. */
    if (this.iso() && !this.enLaSala(e)) return null;
    def = this.entityDef(e).actor;
    punto = this.pantalla(e.x, e.y, e.altura, def);
    return { def: def, sx: punto.sx, sy: punto.sy,
             frame: actorFrame(def, e.anim, e.animFrame), flip: !e.facing };
  };

  /* Queda alguien vivo en la pantalla? Es de lo que vive el genero de tortas:
     mientras la respuesta sea que si, la camara no pasa de ahi. Igual que
     np_alguien_en_pantalla. */
  World.prototype.alguienEnPantalla = function () {
    for (var i = 0; i < this.entityCount; i++) {
      var e = this.entities[i];
      if (!e.active || e.kind !== KIND_ENEMY) continue;
      var ea = this.entityDef(e).actor;
      if (F2I(e.x) + ea.box_w <= this.camX) continue;
      if (F2I(e.x) >= this.camX + SCREEN_W) continue;
      return true;
    }
    return false;
  };

  /* Montar los cubos de la sala que se esta viendo. Van al final de la lista
     -de MAX_ENTITIES hacia atras- y por diagonales, o sea en orden de
     profundidad. Gemelo de np_bloques_sala. */
  World.prototype.bloquesSala = function () {
    var lv = this.level, i;
    var baseX = this.salaX * SALA, baseY = this.salaY * SALA;
    var tope = MAX_ENTITIES - this.entityCount;
    var nn = 0, d, cy;
    for (i = 0; i < this.bloquesN; i++)
      this.entities[MAX_ENTITIES - 1 - i].active = 0;
    this.bloquesN = 0;
    if (!this.iso()) return;
    /* la lista tiene que llegar hasta el final para poder poner cubos ahi */
    while (this.entities.length < MAX_ENTITIES)
      this.entities.push({ active: 0, kind: KIND_SHOT, def: 0, x: 0, y: 0,
        homeX: 0, homeY: 0, vx: 0, vy: 0, facing: 0, anim: ANIM_IDLE,
        animFrame: 0, animTimer: 0, hurt: 0, timer: 0, health: 1, vida: 0,
        knock: 0, golpeado: 0, altura: 0, valtura: 0, fase: LUCHA_IR,
        tocado: 0, aturdido: 0 });
    for (d = 0; d <= (SALA - 1) * 2; d++) {
      for (cy = 0; cy < SALA; cy++) {
        var cx = d - cy;
        if (cx < 0 || cx >= SALA) continue;
        if (nn >= tope) { this.bloquesN = nn;
                          this.bloquesAbiertos = this.abiertos.length; return; }
        var mx = baseX + cx, my = baseY + cy;
        if (mx < 0 || mx >= lv.cells_w || my < 0 || my >= lv.cells_h) continue;
        var tile = lv.cells[my * lv.cells_w + mx];
        var cubo = this.data.tiles.bloque[tile];
        if (!cubo) continue;
        if (this.data.tiles.kind[tile] === TILE_LOCK
            && this.tileVisto(mx, my) === TILE_EMPTY) continue;
        var e = this.entities[MAX_ENTITIES - 1 - nn];
        nn++;
        e.active = 1; e.kind = KIND_BLOQUE; e.def = cubo - 1;
        e.x = I2F(mx * TILE); e.y = I2F(my * TILE);
        e.homeX = e.x; e.homeY = e.y;
        e.vx = 0; e.vy = 0; e.altura = 0; e.valtura = 0;
        e.vida = 0; e.timer = 0;
        e.anim = ANIM_IDLE; e.animFrame = 0; e.animTimer = 0;
        e.facing = 1; e.health = 1; e.hurt = 0; e.knock = 0;
        e.golpeado = 0; e.fase = LUCHA_IR; e.tocado = 0; e.aturdido = 0;
      }
    }
    this.bloquesN = nn;
    this.bloquesAbiertos = this.abiertos.length;
  };

  /* La camara isometrica no sigue a nadie: ensena la sala en la que estas.
     Gemela de np_camara_iso. */
  World.prototype.camaraIso = function () {
    var a = this.data.player.actor;
    var p = this.players[0], i;
    for (i = 0; i < MAX_PLAYERS; i++)
      if (this.players[i].playing) { p = this.players[i]; break; }
    var px = F2I(p.x) + idiv(a.box_w, 2);
    var py = F2I(p.y) + idiv(a.box_h, 2);
    if (px < 0) px = 0;
    if (py < 0) py = 0;
    var sx = px >> SALA_SHIFT, sy = py >> SALA_SHIFT;
    var salasX = Math.max(1, idiv(this.level.cells_w, SALA));
    var salasY = Math.max(1, idiv(this.level.cells_h, SALA));
    sx = clamp(sx, 0, salasX - 1);
    sy = clamp(sy, 0, salasY - 1);
    /* Al abrir un cerrojo la puerta pasa a ser un hueco: hay que rehacer los
       cubos o la puerta se quedaria dibujada hasta salir de la habitacion. */
    if (sx !== this.salaX || sy !== this.salaY
        || this.bloquesAbiertos !== this.abiertos.length) {
      this.salaX = sx;
      this.salaY = sy;
      this.bloquesSala();
    }
    /* La camara se queda quieta: lo que cambia es lo que hay dentro. */
    this.camX = 0;
    this.camY = 0;
  };

  World.prototype.cameraUpdate = function () {
    if (this.iso()) { this.camaraIso(); return; }
    var a = this.data.player.actor;
    var maxX = this.level.width * TILE - SCREEN_W;
    var maxY = this.level.height * TILE - SCREEN_H;
    /* A dos jugadores, el punto medio; con uno sale la misma cuenta. */
    var cx = 0, cy = 0, cuantos = 0, i;
    for (i = 0; i < MAX_PLAYERS; i++) {
      if (!this.players[i].playing) continue;
      cx += F2I(this.players[i].x) + idiv(a.box_w, 2);
      /* En la cinta manda la linea del suelo y no donde se dibuja: si no, la
         camara daria un brinco con cada salto. Igual que np_camera_update. */
      cy += F2I(this.players[i].y + this.players[i].altura) + idiv(a.box_h, 2);
      cuantos++;
    }
    if (!cuantos) {
      /* game over: la camara se queda donde estaba, no se va al origen */
      cx = F2I(this.players[0].x) + idiv(a.box_w, 2);
      cy = F2I(this.players[0].y + this.players[0].altura) + idiv(a.box_h, 2);
    } else if (cuantos > 1) {
      cx = idiv(cx, cuantos); cy = idiv(cy, cuantos);
    }
    var tx, ty;
    if (maxX < 0) maxX = 0;
    if (maxY < 0) maxY = 0;
    if (this.data.camara_pantallas) {
      if (cx < 0) cx = 0;
      if (cy < 0) cy = 0;
      tx = idiv(cx, SCREEN_W) * SCREEN_W;
      ty = idiv(cy, SCREEN_H) * SCREEN_H;
    } else {
      tx = cx - idiv(SCREEN_W, 2);
      ty = cy - idiv(SCREEN_H, 2);
    }
    /* El cerrojo del genero de tortas: con alguien vivo en pantalla la camara
       no avanza. Igual que np_camera_update. */
    if (this.cinta() && tx > this.camX && this.alguienEnPantalla())
      tx = this.camX;
    this.camX = clamp(tx, 0, maxX);
    this.camY = clamp(ty, 0, maxY);
    /* La sacudida, hacia dentro del nivel y recortada otra vez para no verse
       nunca fuera del mapa. Igual que np_camera_update. */
    if (this.sacudida) {
      this.sacudida--;
      if (this.sacudida & 2) {
        this.camX += 3;
        if (this.camX > maxX) this.camX = maxX;
      }
    }
  };

  /* Se ha cambiado de pantalla? Entonces entran los perseguidores tenaces.
     Gemelo de np_cambio_de_pantalla: va aparte de cameraUpdate y solo lo llama
     el paso del frame, para que empezar un nivel -que tambien mueve la camara-
     no cuente como cruzar una puerta. */
  World.prototype.cambioDePantalla = function () {
    if (!this.data.camara_pantallas) return;
    var px = Math.floor(this.camX / SCREEN_W);
    var py = Math.floor(this.camY / SCREEN_H);
    if (px === this.pantallaX && py === this.pantallaY) return;
    var ddx = px - this.pantallaX, ddy = py - this.pantallaY;
    this.pantallaX = px;
    this.pantallaY = py;
    this.tenacesSiguen(ddx, ddy);
  };

  /* Los perseguidores tenaces: al cambiar de pantalla entran por el borde por
     el que has entrado tu. Gemelo de np_tenaces_siguen. */
  World.prototype.tenacesSiguen = function (dx, dy) {
    var p = this.players[0], i;
    var izq = this.camX, der = this.camX + SCREEN_W;
    var arr = this.camY, aba = this.camY + SCREEN_H;
    var cuantos = 0;
    for (i = 0; i < MAX_PLAYERS; i++)
      if (this.players[i].playing && !this.players[i].dying) { p = this.players[i]; break; }
    for (i = 0; i < this.entityCount; i++) {
      var e = this.entities[i];
      if (!e.active || e.kind !== KIND_ENEMY) continue;
      var ed = this.data.enemies[e.def];
      if (!ed.tenaz) continue;
      var x = F2I(p.x), y = F2I(p.y);
      if (dx > 0) x = izq + 2 + cuantos * (ed.actor.box_w + 8);
      else if (dx < 0) x = der - ed.actor.box_w - 2 - cuantos * (ed.actor.box_w + 8);
      if (dy > 0) y = arr + 2;
      else if (dy < 0) y = aba - ed.actor.box_h - 2;
      x = clamp(x, izq, der - ed.actor.box_w);
      y = clamp(y, arr, aba - ed.actor.box_h);
      e.x = I2F(x);
      e.y = I2F(y);
      e.vx = 0;
      e.vy = 0;
      e.homeX = e.x;
      e.homeY = e.y;
      e.facing = (dx >= 0) ? 1 : 0;
      e.hurt = 0;
      e.knock = 0;
      e.fase = LUCHA_IR;
      e.timer = ed.interval;
      cuantos++;
    }
  };

  /* A dos jugadores, el que se queda atras se para en el borde de la pantalla.
     Con uno no se toca nada: la camara lo lleva centrado y nunca se sale. */
  World.prototype.playersInView = function () {
    var a = this.data.player.actor, i;
    var izquierda = this.camX, derecha = this.camX + SCREEN_W - a.box_w;
    if (this.playerCount < 2 || this.iso()) return;
    for (i = 0; i < MAX_PLAYERS; i++) {
      var p = this.players[i];
      if (!p.playing || p.dying) continue;
      if (F2I(p.x) < izquierda) { p.x = I2F(izquierda); if (p.vx < 0) p.vx = 0; }
      if (F2I(p.x) > derecha) { p.x = I2F(derecha); if (p.vx > 0) p.vx = 0; }
    }
  };

  World.prototype.playerVisible = function (quien) {
    var p = this.players[quien || 0];
    if (!p.playing) return false;
    if (this.state === STATE.TITLE || this.state === STATE.GAME_OVER) return false;
    if (p.invuln && (this.frame & 2)) return false;
    return true;
  };

  /* Se acaba el nivel: por la meta o por matar al jefe, da igual. */
  World.prototype.finishLevel = function () {
    this.sfx |= SFX.GOAL;
    this.state = STATE.LEVEL_END;
    this.stateTimer = LEVEL_END_TIME;
    this.score += 100 + idiv(this.timeLeft, 60) * 10;
  };

  /* Un jugador que se muere mientras el otro sigue: cae, y al acabar la caida
     reaparece si le quedan vidas. Igual que np_player_falling en C. */
  World.prototype.playerFalling = function (quien) {
    var d = this.data.player, p = this.players[quien];
    p.vy += d.gravity;
    if (p.vy > d.max_fall) p.vy = d.max_fall;
    p.y += p.vy;
    if (p.dying) p.dying--;
    if (p.dying) return;
    if (p.lives > 1) { p.lives--; this.resetPlayer(quien); }
    else { p.lives = 0; p.playing = 0; }
  };

  World.prototype.playStep = function (input, input2) {
    var pa = this.data.player.actor, quien, i;
    var mandos = [input, input2 | 0];

    /* Cuantos estan pegando ahora mismo: de ahi salen las fichas de ataque.
       Igual que en np_play_step. */
    this.atacando = 0;
    if (this.cinta()) {
      for (i = 0; i < this.entityCount; i++) {
        var luchador = this.entities[i];
        if (!luchador.active || luchador.kind !== KIND_ENEMY) continue;
        if (luchador.knock || luchador.fase < LUCHA_PREPARAR
            || luchador.fase > LUCHA_RECUPERAR) continue;
        this.atacando++;
      }
    }

    /* Las plataformas moviles se mueven antes que nadie, y no se pausan fuera
       de pantalla: igual que en np_play_step. */
    for (i = 0; i < this.entityCount; i++) {
      var plat = this.entities[i];
      if (plat.active && plat.kind === KIND_PLATFORM) this.platformUpdate(plat);
    }

    for (quien = 0; quien < MAX_PLAYERS; quien++) {
      var jugador = this.players[quien];
      if (!jugador.playing) continue;
      /* La ventana para encadenar corre aqui, antes de leer el mando, igual
         que en np_play_step: asi la serie va igual en las dos. */
      if (jugador.comboTimer) jugador.comboTimer--;
      if (jugador.dying) this.playerFalling(quien);
      else if (this.iso()) this.playerUpdateIso(quien, mandos[quien]);
      else if (this.cinta()) this.playerUpdateCinta(quien, mandos[quien]);
      else if (this.cenital()) this.playerUpdateCenital(quien, mandos[quien]);
      else this.playerUpdate(quien, mandos[quien]);
    }

    for (i = 0; i < this.entityCount; i++) {
      var e = this.entities[i];
      if (!e.active) continue;
      if (e.kind === KIND_BLOQUE) continue;   /* los cubos no hacen nada */
      var fuera;
      if (this.iso()) {
        /* Aqui "fuera de la vista" es "en otra habitacion". Igual que en C. */
        fuera = !this.enLaSala(e);
      } else {
        var dx = F2I(e.x) - this.camX;
        fuera = (dx < -CULL_MARGIN || dx > SCREEN_W + CULL_MARGIN);
      }
      if (fuera) {
        /* Lejos de la vista, los enemigos se quedan en pausa y los
           proyectiles se apagan: uno que sale de la pantalla ya no vuelve. */
        if (e.kind === KIND_SHOT || e.kind === KIND_SUBSHOT) {
          e.active = 0;
          continue;
        }
        if (e.kind === KIND_ENEMY) continue;
      }
      if (e.kind === KIND_PLATFORM) continue;        /* ya se ha movido */
      if (e.kind === KIND_MELEE) continue;          /* lo lleva el jugador */
      if (e.hurt) e.hurt--;
      if (e.kind === KIND_SHOT) this.shotUpdate(e);
      else if (e.kind === KIND_SUBSHOT) this.subshotUpdate(e);
      else if (e.kind === KIND_ENEMY_SHOT) this.enemyShotUpdate(e);
      else if (e.kind === KIND_PRISONER) this.prisonerUpdate(e);
      else if (e.kind === KIND_GENERATOR) this.generatorUpdate(e);
      else if (e.kind === KIND_ENEMY) this.enemyUpdate(e);
      else if (e.kind === KIND_BREAKABLE) this.breakableUpdate(e);
      else this.itemUpdate(e);
    }

    this.touchEntities();

    /* Que jefe hay en pantalla, para el marcador (igual que np_world.c). */
    this.bossHealth = 0;
    this.bossMax = 0;
    for (i = 0; i < this.entityCount; i++) {
      var b = this.entities[i];
      if (b.active && b.kind === KIND_ENEMY && this.data.enemies[b.def].boss) {
        this.bossHealth = b.health;
        this.bossMax = this.data.enemies[b.def].health;
        break;
      }
    }
    if (this.state !== STATE.PLAY) return;

    for (quien = 0; quien < MAX_PLAYERS; quien++) {
      var q = this.players[quien];
      if (!q.playing || q.dying) continue;
      /* Saltando por encima de un pincho no pasa nada: en la isometrica la
         altura es de verdad. Igual que en C. */
      if ((!this.iso() || q.altura <= I2F(ISO_PISA)) &&
          this.boxTouches(q.x + I2F(HAZARD_INSET_X),
                          this.playerTop(quien) + I2F(HAZARD_INSET_Y),
                          pa.box_w - HAZARD_INSET_X * 2,
                          this.playerHeight(quien) - HAZARD_INSET_Y,
                          TILE_HAZARD)) {
        this.playerHurt(quien, 99);
        continue;
      }
      this.playerWear(quien);
      if (q.dying) continue;
      this.checkTouch(quien);
      /* La meta solo se abre si se llevan las llaves que pide el nivel. Las
         llaves son de la partida, no de cada jugador. */
      if (this.keys >= (this.level.keys_needed || 0) &&
          (!this.iso() || q.altura <= I2F(ISO_PISA)) &&
          this.boxTouches(q.x, q.y, pa.box_w, pa.box_h, TILE_GOAL)) {
        this.finishLevel();            /* llega uno, se acaba para los dos */
        return;
      }
      /* Caerse del mapa: en la isometrica no hay de donde caerse. */
      if (!this.iso() && F2I(q.y) > (this.level.height + 2) * TILE)
        this.playerHurt(quien, 99);
    }
    if (this.state !== STATE.PLAY) return;

    /* el tiempo es de la partida, no de cada uno */
    if (this.data.time_limit) {
      if (this.timeLeft) this.timeLeft--;
      else for (quien = 0; quien < MAX_PLAYERS; quien++) this.playerHurt(quien, 99);
    }
  };

  /* Volver a empezar el nivel despues de perder una vida: cargarlo, pero
     conservando el punto de control. Igual que np_level_restart en C. */
  World.prototype.levelRestart = function () {
    var on = this.checkOn, cx = this.checkX, cy = this.checkY, i;
    this.loadLevel(this.levelIndex);
    if (!on) return;
    this.checkOn = on;
    this.checkX = cx;
    this.checkY = cy;
    for (i = 0; i < MAX_PLAYERS; i++) this.placePlayer(i);
  };

  /* Que musica toca ahora, en numero de musica (indice + 1, cero = silencio).
     Igual que np_music_now en np_world.c: la regla es del motor y no de quien
     dibuja, asi suena lo mismo en el navegador y en las seis maquinas. */
  World.prototype.musicaAhora = function () {
    var s = this.data.sonido || {};
    if (this.state === STATE.TITLE) return s.titulo || 0;
    if (this.state !== STATE.PLAY) return 0;
    if (s.jefe && this.bossMax) return s.jefe;
    return this.level.music || 0;
  };

  World.prototype.step = function (input, input2) {
    var i, quien;
    input2 = input2 | 0;
    /* Start vale desde cualquiera de los dos mandos. */
    var ambos = input | (this.playerCount > 1 ? input2 : 0);
    var antes = this.prevInput[0] | (this.playerCount > 1 ? this.prevInput[1] : 0);
    var startPressed = (ambos & IN.START) && !(antes & IN.START);
    this.frame++;
    this.sfx = 0;                 /* los eventos duran un solo frame */

    switch (this.state) {
      case STATE.TITLE:
        if (startPressed) {
          this.sfx |= SFX.START;
          this.score = 0;
          for (i = 0; i < MAX_PLAYERS; i++) {
            this.players[i].playing = i < this.playerCount ? 1 : 0;
            this.players[i].lives = this.data.lives;
          }
          this.loadLevel(0);
        }
        break;
      case STATE.PLAY:
        /* El congelado. El mando no se apunta: lo que se pulse durante la
           parada sigue contando como recien pulsado. Igual que
           np_world_step. */
        if (this.congelado) { this.congelado--; return; }
        this.playStep(input, input2);
        break;
      case STATE.DYING: {
        /* Aqui se llega cuando no queda nadie en pie: caen todos y, al acabar
           la cuenta, el nivel vuelve a empezar si a alguno le quedan vidas. */
        for (i = 0; i < MAX_PLAYERS; i++) {
          var pd = this.players[i];
          if (!pd.playing || !pd.dying) continue;
          pd.vy += this.data.player.gravity;
          if (pd.vy > this.data.player.max_fall) pd.vy = this.data.player.max_fall;
          pd.y += pd.vy;
        }
        if (this.stateTimer) { this.stateTimer--; break; }
        var quedan = 0;
        for (i = 0; i < MAX_PLAYERS; i++) {
          var pv = this.players[i];
          if (!pv.playing) continue;
          if (pv.lives > 1) { pv.lives--; quedan++; }
          else { pv.lives = 0; pv.playing = 0; }
        }
        if (quedan) this.levelRestart();
        else { this.state = STATE.GAME_OVER; this.stateTimer = GAME_OVER_TIME; }
        break;
      }
      case STATE.LEVEL_END:
        if (this.stateTimer) this.stateTimer--;
        else if (this.levelIndex + 1 < this.data.levels.length) this.loadLevel(this.levelIndex + 1);
        else { this.state = STATE.FINISHED; this.stateTimer = GAME_OVER_TIME; }
        break;
      default:
        if (this.stateTimer) this.stateTimer--;
        if (startPressed || this.stateTimer === 0) {
          this.state = STATE.TITLE;
          this.stateTimer = 0;
          this.levelIndex = 0;
          this.level = this.data.levels[0];
        }
        break;
    }

    this.cameraUpdate();
    this.cambioDePantalla();
    this.playersInView();
    this.prevInput[0] = input;
    this.prevInput[1] = input2;
  };

  var api = {
    World: World, IN: IN, STATE: STATE, SFX: SFX, FIX_ONE: FIX_ONE, TILE: TILE,
    SCREEN_W: SCREEN_W, SCREEN_H: SCREEN_H, F2I: F2I, I2F: I2F,
    actorFrame: actorFrame,
    create: function (data) { var w = new World(data); w.level = data.levels[0]; return w; }
  };

  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.NPCore = api;
})(typeof window !== "undefined" ? window : this);
