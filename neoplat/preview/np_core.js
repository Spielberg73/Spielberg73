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
  var AI_PATROL = 0, AI_FLYER = 1, AI_CHASER = 2, AI_JUMPER = 3;
  var ANIM_IDLE = 0, ANIM_RUN = 1, ANIM_JUMP = 2, ANIM_FALL = 3, ANIM_HURT = 4,
      ANIM_ATTACK = 5, ANIM_STAIR = 6, ANIM_CROUCH = 7,
      /* solo en vista cenital: de espaldas y de frente */
      ANIM_UP = 8, ANIM_DOWN = 9;
  var KIND_ENEMY = 0, KIND_ITEM = 1, KIND_SHOT = 2, KIND_PLATFORM = 3;
  var KIND_BREAKABLE = 4, KIND_SUBSHOT = 5, KIND_MELEE = 6;
  var KIND_ENEMY_SHOT = 7;      /* lo que tira un enemigo con `dispara:` */
  var KIND_PRISONER = 8;        /* el rehen: se suelta tocandolo */
  /* el arma secundaria: 0 ninguna, 1 recta, 2 en arco */
  var SUB_NONE = 0, SUB_LINE = 1, SUB_ARC = 2;
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
        health: 1, coyote: 0, buffer: 0, lives: 0, playing: 0,
        attackTimer: 0, attackCd: 0, riding: 0, whip: 0, crouch: 0,
        stun: 0, power: 0,
        stairs: 0, stairDir: 1
      });
    }
    this.playerCount = data.players || 1;
    this.entities = [];
    this.camX = 0; this.camY = 0;
    this.score = 0; this.frame = 0;
    this.levelIndex = 0;
    this.state = STATE.TITLE; this.stateTimer = 0;
    this.timeLeft = 0; this.prevInput = [0, 0];
    this.sfx = 0;                 /* eventos de sonido de este frame */
    this.keys = 0; this.hearts = 0; this.entityCount = 0;
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
    return !!(this.data.view === "cenital");
  };

  World.prototype.tileKindAt = function (tx, ty) {
    var lv = this.level;
    if (tx < 0 || tx >= lv.width) return TILE_SOLID;
    /* De lado, arriba hay cielo y abajo un abismo. Desde arriba el mapa es
       una caja cerrada y sus cuatro lados son pared. */
    if (ty < 0 || ty >= lv.height)
      return this.cenital() ? TILE_SOLID : TILE_EMPTY;
    return this.data.tiles.kind[lv.cells[ty * lv.width + tx]];
  };

  World.prototype.tileGfxAt = function (tx, ty) {
    var lv = this.level;
    if (tx < 0 || tx >= lv.width || ty < 0 || ty >= lv.height) return -1;
    return this.data.tiles.gfx[lv.cells[ty * lv.width + tx]];
  };

  function blocks(kind) { return kind === TILE_SOLID; }

  function overlap(ax, ay, aw, ah, bx, by, bw, bh) {
    if (ax + I2F(aw) <= bx) return false;
    if (bx + I2F(bw) <= ax) return false;
    if (ay + I2F(ah) <= by) return false;
    if (by + I2F(bh) <= ay) return false;
    return true;
  }

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
          if (blocks(this.tileKindAt(tx, ty))) {
            nx = I2F(tx * TILE - bw); out.hit = 1; dx = 0; break;
          }
        }
      } else {
        tx = F2I(nx) >> TILE_SHIFT;
        for (ty = ty0; ty <= ty1; ty++) {
          if (blocks(this.tileKindAt(tx, ty))) {
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
          var kind = this.tileKindAt(tx, ty);
          var stops = blocks(kind);
          if (!stops && kind === TILE_PLATFORM && !dropThrough)
            stops = oldBottom < ty * TILE;
          if (stops) { ny = I2F(ty * TILE - bh); out.hitDown = 1; dy = 0; break; }
        }
      } else {
        ty = F2I(ny) >> TILE_SHIFT;
        for (tx = tx0; tx <= tx1; tx++) {
          if (blocks(this.tileKindAt(tx, ty))) {
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
        if (this.tileKindAt(tx, ty) === kind) return true;
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
    for (i = 0; i < lv.spawns.length && this.entityCount < MAX_ENTITIES; i++) {
      var s = lv.spawns[i];
      var e = {
        active: 1, kind: s[2], def: s[3], x: I2F(s[0]), y: I2F(s[1]),
        homeX: I2F(s[0]), homeY: I2F(s[1]), vx: 0, vy: 0, facing: 0,
        anim: ANIM_IDLE,
        animFrame: 0, animTimer: 0, hurt: 0, timer: 0, health: 1, vida: 0
      };
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
    p.dying = 0; p.attackTimer = 0; p.attackCd = 0; p.riding = 0; p.stun = 0;
    p.power = 0;                /* el arma vuelve a la de serie */
    p.crouch = 0;
    this.whipOff(quien);
    p.stairs = 0; p.stairDir = 1;
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
    this.sub = 0;                 /* se empieza con la primera arma */
    this.bossHealth = 0; this.bossMax = 0;
    this.timeLeft = this.data.time_limit * 60;
    this.state = STATE.PLAY;
    this.stateTimer = 0;
    this.spawnEntities();
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
    for (i = 0; i < this.entities.length; i++) {
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
      timer: 0, health: 1, vida: 0
    });
    i = this.entities.length - 1;
    if (i >= this.entityCount) this.entityCount = i + 1;
    return i;
  };

  World.prototype.hitEnemy = function (e, damage) {
    var d = this.data.enemies[e.def];
    if (e.health > damage) {
      e.health -= damage;
      e.hurt = 20;
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
    e.health = 1; e.hurt = 0; e.timer = 0; e.vida = 0;
    e.anim = ANIM_IDLE; e.animFrame = 0; e.animTimer = 0;
  };

  /* Lo que hace un ataque al tocar algo. Igual que np_hit_entity. */
  World.prototype.hitEntity = function (e, damage) {
    if (e.kind === KIND_ENEMY) this.hitEnemy(e, damage);
    else if (e.kind === KIND_BREAKABLE) this.hitBreakable(e, damage);
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

  World.prototype.attackRange = function (quien) {
    var at = this.data.player.attack;
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
      if (otra.kind !== KIND_ENEMY && otra.kind !== KIND_BREAKABLE) continue;
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
    if (!p.attackTimer) { this.whipOff(quien); return; }
    p.attackTimer--;
    if (at.kind !== ATTACK_MELEE) return;     /* un disparo no pega de cerca */
    /* Los primeros `preparacion:` frames el golpe se ve pero no toca. El
       latigo aparece justo cuando empieza a hacer dano. */
    if (p.attackTimer + at.windup >= at.duration) { this.whipOff(quien); return; }
    this.whipOn(quien);
    var alcance = this.attackRange(quien);
    var gx = p.facing ? p.x + I2F(pa.box_w) : p.x - I2F(alcance);
    var gy = this.playerTop(quien);
    for (i = 0; i < this.entityCount; i++) {
      var e = this.entities[i];
      if (!e.active) continue;
      if (e.kind !== KIND_ENEMY && e.kind !== KIND_BREAKABLE) continue;
      /* Lo que esta parpadeando no se vuelve a tocar: la caja del golpe dura
         varios frames y acertaria en todos. Igual que np_melee_update. */
      if (e.hurt) continue;
      var ea = this.entityDef(e).actor;
      if (!overlap(gx, gy, alcance, this.playerHeight(quien),
                        e.x, e.y, ea.box_w, ea.box_h)) continue;
      this.hitEntity(e, at.damage);
    }
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
      if (otra.kind !== KIND_ENEMY && otra.kind !== KIND_BREAKABLE) continue;
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
    var kind = this.tileKindAt(F2I(x) >> TILE_SHIFT, F2I(y) >> TILE_SHIFT);
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

  /* El boton de accion, aparte porque vale igual andando que en la escalera. */
  World.prototype.playerAction = function (quien, input) {
    var p = this.players[quien];
    if (p.attackCd) p.attackCd--;
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
    }
    if (!(input & IN.JUMP) && p.vy < -d.jump_cut) p.vy = -d.jump_cut;

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
    else if (p.attackTimer) animSet(p, ANIM_ATTACK);
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

  World.prototype.enemyUpdate = function (e) {
    var d = this.data.enemies[e.def], a = d.actor, p = this.nearestPlayer(e.x);
    switch (d.behavior) {
      case AI_PATROL:
        e.vx = e.facing ? d.speed : -d.speed;
        break;
      case AI_FLYER: {
        var period = d.period ? d.period : 1;
        e.vx = e.facing ? d.speed : -d.speed;
        e.timer = (e.timer + 1) % period;
        var phase = this.data.sin[(idiv(e.timer * 64, period)) & 63];
        e.y = e.homeY + ((d.amplitude * phase) >> FIX_SHIFT);
        break;
      }
      case AI_CHASER: {
        var dx = p.x - e.x;
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
    animSet(e, ANIM_IDLE);
    animTick(d.actor, e);
  };

  /* Lo recoge quien lo toca: la vida y la salud van a ese jugador, y los
     puntos y las llaves al marcador, que es comun. */
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
    }
    e.active = 0;
  };

  /* Los puntos de control. Se busca **la casilla**, no solo si toca alguna,
     porque lo que hay que guardar es donde estaba. Volver a pasar por el que
     ya esta marcado no hace nada; pasar por uno anterior si lo mueve hacia
     atras. Igual que np_check_touch en C. */
  World.prototype.checkTouch = function (quien) {
    var a = this.data.player.actor, p = this.players[quien];
    var tx0 = F2I(p.x) >> TILE_SHIFT;
    var tx1 = F2I(p.x + I2F(a.box_w) - 1) >> TILE_SHIFT;
    var ty0 = F2I(p.y) >> TILE_SHIFT;
    var ty1 = F2I(p.y + I2F(a.box_h) - 1) >> TILE_SHIFT;
    var tx, ty;
    for (ty = ty0; ty <= ty1; ty++) {
      for (tx = tx0; tx <= tx1; tx++) {
        if (this.tileKindAt(tx, ty) !== TILE_CHECK) continue;
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
        if (e.kind === KIND_SHOT || e.kind === KIND_SUBSHOT)
          continue;                              /* es tuyo: no te toca */
        if (e.kind === KIND_MELEE) continue;     /* es tu propio latigo */
        if (e.kind === KIND_PLATFORM) continue;  /* es suelo, no un bicho */
        if (e.kind === KIND_BREAKABLE) continue; /* hay que pegarle */
        if (e.kind === KIND_ENEMY_SHOT) continue;   /* se mira en su update */
        if (e.kind === KIND_PRISONER) { this.prisonerFree(e, p); continue; }
        if (e.kind === KIND_ITEM) { this.collect(quien, e); continue; }
        var d = this.data.enemies[e.def];
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
          this.playerHurt(quien, d.damage);
        }
      }
    }
  };

  /* Dos modos de camara, igual que np_world.c: 'scroll' desliza el escenario y
     'pantallas' salta de una pantalla fija a la siguiente. */
  World.prototype.cameraUpdate = function () {
    var a = this.data.player.actor;
    var maxX = this.level.width * TILE - SCREEN_W;
    var maxY = this.level.height * TILE - SCREEN_H;
    /* A dos jugadores, el punto medio; con uno sale la misma cuenta. */
    var cx = 0, cy = 0, cuantos = 0, i;
    for (i = 0; i < MAX_PLAYERS; i++) {
      if (!this.players[i].playing) continue;
      cx += F2I(this.players[i].x) + idiv(a.box_w, 2);
      cy += F2I(this.players[i].y) + idiv(a.box_h, 2);
      cuantos++;
    }
    if (!cuantos) {
      /* game over: la camara se queda donde estaba, no se va al origen */
      cx = F2I(this.players[0].x) + idiv(a.box_w, 2);
      cy = F2I(this.players[0].y) + idiv(a.box_h, 2);
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
    this.camX = clamp(tx, 0, maxX);
    this.camY = clamp(ty, 0, maxY);
  };

  /* A dos jugadores, el que se queda atras se para en el borde de la pantalla.
     Con uno no se toca nada: la camara lo lleva centrado y nunca se sale. */
  World.prototype.playersInView = function () {
    var a = this.data.player.actor, i;
    var izquierda = this.camX, derecha = this.camX + SCREEN_W - a.box_w;
    if (this.playerCount < 2) return;
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

    /* Las plataformas moviles se mueven antes que nadie, y no se pausan fuera
       de pantalla: igual que en np_play_step. */
    for (i = 0; i < this.entityCount; i++) {
      var plat = this.entities[i];
      if (plat.active && plat.kind === KIND_PLATFORM) this.platformUpdate(plat);
    }

    for (quien = 0; quien < MAX_PLAYERS; quien++) {
      var jugador = this.players[quien];
      if (!jugador.playing) continue;
      if (jugador.dying) this.playerFalling(quien);
      else if (this.cenital()) this.playerUpdateCenital(quien, mandos[quien]);
      else this.playerUpdate(quien, mandos[quien]);
    }

    for (i = 0; i < this.entityCount; i++) {
      var e = this.entities[i];
      if (!e.active) continue;
      var dx = F2I(e.x) - this.camX;
      if (dx < -CULL_MARGIN || dx > SCREEN_W + CULL_MARGIN) {
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
      if (this.boxTouches(q.x + I2F(HAZARD_INSET_X),
                          this.playerTop(quien) + I2F(HAZARD_INSET_Y),
                          pa.box_w - HAZARD_INSET_X * 2,
                          this.playerHeight(quien) - HAZARD_INSET_Y,
                          TILE_HAZARD)) {
        this.playerHurt(quien, 99);
        continue;
      }
      this.checkTouch(quien);
      /* La meta solo se abre si se llevan las llaves que pide el nivel. Las
         llaves son de la partida, no de cada jugador. */
      if (this.keys >= (this.level.keys_needed || 0) &&
          this.boxTouches(q.x, q.y, pa.box_w, pa.box_h, TILE_GOAL)) {
        this.finishLevel();            /* llega uno, se acaba para los dos */
        return;
      }
      if (F2I(q.y) > (this.level.height + 2) * TILE) this.playerHurt(quien, 99);
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
