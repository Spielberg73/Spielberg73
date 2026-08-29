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
  var AI_PATROL = 0, AI_FLYER = 1, AI_CHASER = 2, AI_JUMPER = 3;
  var ANIM_IDLE = 0, ANIM_RUN = 1, ANIM_JUMP = 2, ANIM_FALL = 3, ANIM_HURT = 4,
      ANIM_ATTACK = 5;
  var KIND_ENEMY = 0, KIND_ITEM = 1, KIND_SHOT = 2, KIND_PLATFORM = 3;
  /* por donde va y viene una plataforma movil */
  var PLAT_X = 0, PLAT_Y = 1;
  var ATTACK_NONE = 0, ATTACK_SHOT = 1, ATTACK_MELEE = 2;
  var STATE = { TITLE: 0, PLAY: 1, DYING: 2, LEVEL_END: 3, GAME_OVER: 4, FINISHED: 5 };
  /* Eventos de sonido; mismos bits que NP_SFX_* en np_types.h. */
  var SFX = { START: 1, JUMP: 2, DJUMP: 4, COIN: 8, STOMP: 16, HURT: 32,
              DIE: 64, GOAL: 128, LIFE: 256, SHOOT: 512 };

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
        attackTimer: 0, attackCd: 0, riding: 0
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
    this.keys = 0; this.entityCount = 0;
    this.bossHealth = 0; this.bossMax = 0;
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
     derecha, para que no empiecen uno dentro del otro. */
  World.prototype.placePlayer = function (quien) {
    var p = this.players[quien];
    p.x = I2F(this.level.start[0] + (quien ? HUECO_2P : 0));
    p.y = I2F(this.level.start[1]);
  };

  World.prototype.tileKindAt = function (tx, ty) {
    var lv = this.level;
    if (tx < 0 || tx >= lv.width) return TILE_SOLID;
    if (ty < 0 || ty >= lv.height) return TILE_EMPTY;
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
    p.vx = 0; p.vy = 0; p.onGround = 0; p.facing = 1;
    p.health = d.health; p.invuln = 0; p.coyote = 0; p.buffer = 0;
    p.dying = 0; p.attackTimer = 0; p.attackCd = 0; p.riding = 0;
    p.jumpsLeft = d.double_jump ? 1 : 0;
    p.anim = ANIM_IDLE; p.animFrame = 0; p.animTimer = 0;
  };

  World.prototype.loadLevel = function (index) {
    var i;
    if (index >= this.data.levels.length) index = 0;
    this.levelIndex = index;
    this.level = this.data.levels[index];
    for (i = 0; i < MAX_PLAYERS; i++) this.resetPlayer(i);
    this.keys = 0;
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
    p.vy = -idiv(d.bounce, 2);
    p.vx = p.facing ? -d.speed : d.speed;
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

  World.prototype.playerAttack = function (quien) {
    var at = this.data.player.attack, p = this.players[quien];
    var pa = this.data.player.actor;
    if (!at || at.kind === ATTACK_NONE || p.attackCd) return;
    p.attackCd = at.cooldown;
    this.sfx |= SFX.SHOOT;
    if (at.kind === ATTACK_MELEE) { p.attackTimer = at.duration; return; }

    var hueco = this.huecoLibre();
    if (hueco < 0) return;
    var e = this.entities[hueco];
    e.active = 1;
    e.kind = KIND_SHOT;
    e.def = 0;
    e.facing = p.facing;
    e.x = p.x + I2F(p.facing ? pa.box_w : -at.actor.box_w);
    e.y = p.y + I2F(idiv(pa.box_h - at.actor.box_h, 2));
    e.vx = p.facing ? at.speed : -at.speed;
    e.vy = 0;
    e.homeY = e.y;
    e.health = 1;
    e.hurt = 0;
    e.timer = 0;
    e.anim = ANIM_IDLE;
    e.animFrame = 0;
    e.animTimer = 0;
    e.vida = at.speed ? idiv(I2F(at.range), at.speed) + 1 : 1;
  };

  World.prototype.shotUpdate = function (e) {
    var at = this.data.player.attack, a = at.actor, i;
    if (!e.vida) { e.active = 0; return; }
    e.vida--;
    e.x = this.moveX(e.x, e.y, a.box_w, a.box_h, e.vx, moveOut);
    if (moveOut.hit) { e.active = 0; return; }
    for (i = 0; i < this.entityCount; i++) {
      var otra = this.entities[i];
      if (!otra.active || otra.kind !== KIND_ENEMY) continue;
      var ea = this.entityDef(otra).actor;
      if (!overlap(e.x, e.y, a.box_w, a.box_h,
                        otra.x, otra.y, ea.box_w, ea.box_h)) continue;
      this.hitEnemy(otra, at.damage);
      e.active = 0;
      return;
    }
    animTick(a, e);
  };

  World.prototype.meleeUpdate = function (quien) {
    var at = this.data.player.attack, p = this.players[quien];
    var pa = this.data.player.actor, i;
    if (!p.attackTimer) return;
    p.attackTimer--;
    var gx = p.facing ? p.x + I2F(pa.box_w) : p.x - I2F(at.range);
    var gy = p.y;
    for (i = 0; i < this.entityCount; i++) {
      var e = this.entities[i];
      if (!e.active || e.kind !== KIND_ENEMY) continue;
      var ea = this.entityDef(e).actor;
      if (!overlap(gx, gy, at.range, pa.box_h,
                        e.x, e.y, ea.box_w, ea.box_h)) continue;
      this.hitEnemy(e, at.damage);
    }
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
    if (input & IN.RIGHT) dir += 1;
    if (input & IN.LEFT) dir -= 1;

    if (dir > 0) { p.vx = approach(p.vx, d.speed, p.onGround ? d.accel : d.air_accel); p.facing = 1; }
    else if (dir < 0) { p.vx = approach(p.vx, -d.speed, p.onGround ? d.accel : d.air_accel); p.facing = 0; }
    else if (p.onGround) p.vx = approach(p.vx, 0, d.friction);

    /* El ataque va por flanco: mantener el boton no dispara sin parar. */
    if (p.attackCd) p.attackCd--;
    if ((input & IN.ACTION) && !(this.prevInput[quien] & IN.ACTION))
      this.playerAttack(quien);
    this.meleeUpdate(quien);

    var pressedJump = (input & IN.JUMP) && !(this.prevInput[quien] & IN.JUMP);
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

    if (p.attackTimer) animSet(p, ANIM_ATTACK);
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
        if (abs(dx) <= d.range) { e.vx = dx > 0 ? d.speed : -d.speed; e.facing = dx > 0 ? 1 : 0; }
        else e.vx = approach(e.vx, 0, d.speed);
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

    if (d.behavior !== AI_FLYER) {
      e.vy += d.gravity;
      if (e.vy > ENTITY_FALL) e.vy = ENTITY_FALL;
    }

    e.x = this.moveX(e.x, e.y, a.box_w, a.box_h, e.vx, moveOut);
    if (moveOut.hit) { e.facing = e.facing ? 0 : 1; e.vx = 0; }
    if (d.behavior !== AI_FLYER) {
      e.y = this.moveY(e.x, e.y, a.box_w, a.box_h, e.vy, 0, moveOut);
      if (moveOut.hitDown && e.vy > 0) e.vy = 0;
      if (moveOut.hitUp && e.vy < 0) e.vy = 0;
      if (moveOut.hitDown && d.edge_turn && d.behavior === AI_PATROL) {
        var edge = e.facing ? F2I(e.x + I2F(a.box_w) - 1) + 1 : F2I(e.x) - 1;
        var below = F2I(e.y + I2F(a.box_h));
        var kind = this.tileKindAt(edge >> TILE_SHIFT, below >> TILE_SHIFT);
        if (kind !== TILE_SOLID && kind !== TILE_PLATFORM) e.facing = e.facing ? 0 : 1;
      }
    }

    /* `facing` manda sobre `vx`: recalcularlo aqui deshacia el giro en los
     * bordes y en las paredes (ver np_world.c). */
    animSet(e, e.vx ? ANIM_RUN : ANIM_IDLE);
    animTick(a, e);

    if (F2I(e.y) > (this.level.height + 2) * TILE) e.active = 0;
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
    e.active = 0;
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
        if (!overlap(p.x, p.y, pa.box_w, pa.box_h, e.x, e.y, ea.box_w, ea.box_h)) continue;
        if (e.kind === KIND_SHOT) continue;      /* es tuyo: no te toca */
        if (e.kind === KIND_PLATFORM) continue;  /* es suelo, no un bicho */
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
      else this.playerUpdate(quien, mandos[quien]);
    }

    for (i = 0; i < this.entityCount; i++) {
      var e = this.entities[i];
      if (!e.active) continue;
      var dx = F2I(e.x) - this.camX;
      if (dx < -CULL_MARGIN || dx > SCREEN_W + CULL_MARGIN) {
        /* Lejos de la vista, los enemigos se quedan en pausa y los
           proyectiles se apagan: uno que sale de la pantalla ya no vuelve. */
        if (e.kind === KIND_SHOT) { e.active = 0; continue; }
        if (e.kind === KIND_ENEMY) continue;
      }
      if (e.kind === KIND_PLATFORM) continue;        /* ya se ha movido */
      if (e.hurt) e.hurt--;
      if (e.kind === KIND_SHOT) this.shotUpdate(e);
      else if (e.kind === KIND_ENEMY) this.enemyUpdate(e);
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
      if (this.boxTouches(q.x + I2F(HAZARD_INSET_X), q.y + I2F(HAZARD_INSET_Y),
                          pa.box_w - HAZARD_INSET_X * 2, pa.box_h - HAZARD_INSET_Y,
                          TILE_HAZARD)) {
        this.playerHurt(quien, 99);
        continue;
      }
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
        if (quedan) this.loadLevel(this.levelIndex);
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
