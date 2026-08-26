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
  var ANIM_IDLE = 0, ANIM_RUN = 1, ANIM_JUMP = 2, ANIM_FALL = 3, ANIM_HURT = 4;
  var STATE = { TITLE: 0, PLAY: 1, DYING: 2, LEVEL_END: 3, GAME_OVER: 4, FINISHED: 5 };
  /* Eventos de sonido; mismos bits que NP_SFX_* en np_types.h. */
  var SFX = { START: 1, JUMP: 2, DJUMP: 4, COIN: 8, STOMP: 16, HURT: 32,
              DIE: 64, GOAL: 128, LIFE: 256 };

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

  function World(data) {
    this.data = data;
    this.level = data.levels[0];
    this.player = {
      x: 0, y: 0, vx: 0, vy: 0, animTimer: 0, invuln: 0, anim: 0, animFrame: 0,
      onGround: 0, facing: 1, jumpsLeft: 0, health: 1, coyote: 0, buffer: 0
    };
    this.entities = [];
    this.camX = 0; this.camY = 0;
    this.score = 0; this.frame = 0;
    this.levelIndex = 0;
    this.state = STATE.TITLE; this.stateTimer = 0;
    this.timeLeft = 0; this.prevInput = 0;
    this.sfx = 0;                 /* eventos de sonido de este frame */
    this.lives = data.lives; this.keys = 0; this.entityCount = 0;
    this.bossHealth = 0; this.bossMax = 0;
    /* Igual que np_world_init en C: en el titulo ya se ve el principio del
       nivel, con el jugador colocado en su salida. */
    this.player.x = I2F(this.level.start[0]);
    this.player.y = I2F(this.level.start[1]);
    this.cameraUpdate();
  }

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
    return e.kind === 0 ? this.data.enemies[e.def] : this.data.items[e.def];
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
    this.entities = [];
    this.entityCount = 0;
    for (i = 0; i < lv.spawns.length && this.entityCount < MAX_ENTITIES; i++) {
      var s = lv.spawns[i];
      var e = {
        active: 1, kind: s[2], def: s[3], x: I2F(s[0]), y: I2F(s[1]),
        homeY: I2F(s[1]), vx: 0, vy: 0, facing: 0, anim: ANIM_IDLE,
        animFrame: 0, animTimer: 0, hurt: 0, timer: 0, health: 1
      };
      if (e.kind === 0) {
        var ed = this.data.enemies[e.def];
        e.health = ed.health;
        e.timer = ed.interval;
        e.vx = ed.speed;
        e.facing = 1;
      }
      this.entities.push(e);
      this.entityCount++;
    }
  };

  World.prototype.loadLevel = function (index) {
    var d = this.data.player, p = this.player;
    if (index >= this.data.levels.length) index = 0;
    this.levelIndex = index;
    this.level = this.data.levels[index];
    p.x = I2F(this.level.start[0]);
    p.y = I2F(this.level.start[1]);
    p.vx = 0; p.vy = 0; p.onGround = 0; p.facing = 1;
    p.health = d.health; p.invuln = 0; p.coyote = 0; p.buffer = 0;
    p.jumpsLeft = d.double_jump ? 1 : 0;
    p.anim = ANIM_IDLE; p.animFrame = 0; p.animTimer = 0;
    this.keys = 0;
    this.bossHealth = 0; this.bossMax = 0;
    this.timeLeft = this.data.time_limit * 60;
    this.state = STATE.PLAY;
    this.stateTimer = 0;
    this.spawnEntities();
  };

  World.prototype.playerDie = function () {
    this.sfx |= SFX.DIE;
    this.state = STATE.DYING;
    this.stateTimer = DYING_TIME;
    this.player.vy = -this.data.player.jump;
    this.player.vx = 0;
    this.player.anim = ANIM_HURT;
    this.player.animFrame = 0;
  };

  World.prototype.playerHurt = function (damage) {
    var d = this.data.player, p = this.player;
    if (p.invuln || this.state !== STATE.PLAY) return;
    if (damage >= p.health) { p.health = 0; this.playerDie(); return; }
    p.health -= damage;
    this.sfx |= SFX.HURT;
    p.invuln = d.invuln;
    p.vy = -idiv(d.bounce, 2);
    p.vx = p.facing ? -d.speed : d.speed;
  };

  var moveOut = { hit: 0, hitDown: 0, hitUp: 0 };

  World.prototype.playerUpdate = function (input) {
    var d = this.data.player, a = d.actor, p = this.player;
    var dir = 0;
    if (input & IN.RIGHT) dir += 1;
    if (input & IN.LEFT) dir -= 1;

    if (dir > 0) { p.vx = approach(p.vx, d.speed, p.onGround ? d.accel : d.air_accel); p.facing = 1; }
    else if (dir < 0) { p.vx = approach(p.vx, -d.speed, p.onGround ? d.accel : d.air_accel); p.facing = 0; }
    else if (p.onGround) p.vx = approach(p.vx, 0, d.friction);

    var pressedJump = (input & IN.JUMP) && !(this.prevInput & IN.JUMP);
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
    p.y = this.moveY(p.x, p.y, a.box_w, a.box_h, p.vy, (input & IN.DOWN) ? 1 : 0, moveOut);
    p.onGround = moveOut.hitDown;
    if (moveOut.hitDown && p.vy > 0) p.vy = 0;
    if (moveOut.hitUp && p.vy < 0) p.vy = 0;

    if (p.invuln) p.invuln--;

    if (!p.onGround) animSet(p, p.vy < 0 ? ANIM_JUMP : ANIM_FALL);
    else if (p.vx > idiv(FIX_ONE, 8) || p.vx < -idiv(FIX_ONE, 8)) animSet(p, ANIM_RUN);
    else animSet(p, ANIM_IDLE);
    animTick(a, p);
  };

  World.prototype.enemyUpdate = function (e) {
    var d = this.data.enemies[e.def], a = d.actor, p = this.player;
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

  World.prototype.collect = function (e) {
    var d = this.data.items[e.def];
    this.score += d.score;
    this.sfx |= (d.effect === 1) ? SFX.LIFE : SFX.COIN;
    if (d.effect === 1) { if (this.lives < 99) this.lives += d.amount; }
    else if (d.effect === 2) {
      this.player.health = Math.min(this.player.health + d.amount, this.data.player.health);
    } else if (d.effect === 3) { if (this.keys < 255) this.keys += d.amount; }
    e.active = 0;
  };

  World.prototype.touchEntities = function () {
    var pa = this.data.player.actor, p = this.player, i;
    for (i = 0; i < this.entityCount; i++) {
      var e = this.entities[i];
      if (!e.active) continue;
      var ea = this.entityDef(e).actor;
      if (!overlap(p.x, p.y, pa.box_w, pa.box_h, e.x, e.y, ea.box_w, ea.box_h)) continue;
      if (e.kind === 1) { this.collect(e); continue; }
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
        this.playerHurt(d.damage);
      }
    }
  };

  /* Dos modos de camara, igual que np_world.c: 'scroll' desliza el escenario y
     'pantallas' salta de una pantalla fija a la siguiente. */
  World.prototype.cameraUpdate = function () {
    var a = this.data.player.actor;
    var maxX = this.level.width * TILE - SCREEN_W;
    var maxY = this.level.height * TILE - SCREEN_H;
    var cx = F2I(this.player.x) + idiv(a.box_w, 2);
    var cy = F2I(this.player.y) + idiv(a.box_h, 2);
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

  World.prototype.playerVisible = function () {
    if (this.state === STATE.TITLE || this.state === STATE.GAME_OVER) return false;
    if (this.player.invuln && (this.frame & 2)) return false;
    return true;
  };

  /* Se acaba el nivel: por la meta o por matar al jefe, da igual. */
  World.prototype.finishLevel = function () {
    this.sfx |= SFX.GOAL;
    this.state = STATE.LEVEL_END;
    this.stateTimer = LEVEL_END_TIME;
    this.score += 100 + idiv(this.timeLeft, 60) * 10;
  };

  World.prototype.playStep = function (input) {
    var pa = this.data.player.actor, p = this.player, i;
    this.playerUpdate(input);

    for (i = 0; i < this.entityCount; i++) {
      var e = this.entities[i];
      if (!e.active) continue;
      var dx = F2I(e.x) - this.camX;
      if (dx < -CULL_MARGIN || dx > SCREEN_W + CULL_MARGIN) {
        if (e.kind === 0) continue;
      }
      if (e.hurt) e.hurt--;
      if (e.kind === 0) this.enemyUpdate(e);
      else this.itemUpdate(e);
    }

    this.touchEntities();

    /* Que jefe hay en pantalla, para el marcador (igual que np_world.c). */
    this.bossHealth = 0;
    this.bossMax = 0;
    for (i = 0; i < this.entityCount; i++) {
      var b = this.entities[i];
      if (b.active && b.kind === 0 && this.data.enemies[b.def].boss) {
        this.bossHealth = b.health;
        this.bossMax = this.data.enemies[b.def].health;
        break;
      }
    }
    if (this.state !== STATE.PLAY) return;

    if (this.boxTouches(p.x + I2F(HAZARD_INSET_X), p.y + I2F(HAZARD_INSET_Y),
                        pa.box_w - HAZARD_INSET_X * 2, pa.box_h - HAZARD_INSET_Y,
                        TILE_HAZARD)) {
      this.playerHurt(99);
      return;
    }
    if (this.boxTouches(p.x, p.y, pa.box_w, pa.box_h, TILE_GOAL)) {
      this.finishLevel();
      return;
    }
    if (F2I(p.y) > (this.level.height + 2) * TILE) {
      this.playerHurt(99);
      return;
    }
    if (this.data.time_limit) {
      if (this.timeLeft) this.timeLeft--;
      else this.playerHurt(99);
    }
  };

  World.prototype.step = function (input) {
    var startPressed = (input & IN.START) && !(this.prevInput & IN.START);
    this.frame++;
    this.sfx = 0;                 /* los eventos duran un solo frame */

    switch (this.state) {
      case STATE.TITLE:
        if (startPressed) {
          this.sfx |= SFX.START;
          this.score = 0;
          this.lives = this.data.lives;
          this.loadLevel(0);
        }
        break;
      case STATE.PLAY:
        this.playStep(input);
        break;
      case STATE.DYING:
        this.player.vy += this.data.player.gravity;
        if (this.player.vy > this.data.player.max_fall) this.player.vy = this.data.player.max_fall;
        this.player.y += this.player.vy;
        if (this.stateTimer) this.stateTimer--;
        else if (this.lives > 1) { this.lives--; this.loadLevel(this.levelIndex); }
        else {
          this.lives = 0;
          this.state = STATE.GAME_OVER;
          this.stateTimer = GAME_OVER_TIME;
        }
        break;
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
    this.prevInput = input;
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
