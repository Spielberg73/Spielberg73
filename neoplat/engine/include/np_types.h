/* np_types.h - tipos basicos y coma fija del motor NeoPlat.
 *
 * Todo el motor usa enteros: la Neo Geo no tiene coma flotante y ademas asi
 * la simulacion es identica en la consola y en el preview del navegador.
 * El formato es 24.8 -> una unidad = 1/256 de pixel.
 */
#ifndef NP_TYPES_H
#define NP_TYPES_H

#include <stdint.h>

typedef int32_t np_fix;   /* posiciones y velocidades en 24.8 */

#define NP_FIX_SHIFT 8
#define NP_FIX_ONE   (1 << NP_FIX_SHIFT)

#define NP_I2F(v)  ((np_fix)(v) << NP_FIX_SHIFT)          /* pixeles -> 24.8 */
#define NP_F2I(v)  ((int32_t)((v) >> NP_FIX_SHIFT))       /* 24.8 -> pixeles */
#define NP_ABS(v)  ((v) < 0 ? -(v) : (v))
#define NP_SIGN(v) ((v) > 0 ? 1 : ((v) < 0 ? -1 : 0))
#define NP_MIN(a, b) ((a) < (b) ? (a) : (b))
#define NP_MAX(a, b) ((a) > (b) ? (a) : (b))
#define NP_CLAMP(v, lo, hi) NP_MIN(NP_MAX(v, lo), hi)

#define NP_TILE      16                 /* lado del tile en pixeles */
#define NP_TILE_SHIFT 4
#define NP_SCREEN_W  320
#define NP_SCREEN_H  224

/* Botones (un bit cada uno). El jugador solo necesita cruceta + A + start. */
#define NP_IN_LEFT   0x0001
#define NP_IN_RIGHT  0x0002
#define NP_IN_UP     0x0004
#define NP_IN_DOWN   0x0008
#define NP_IN_JUMP   0x0010
#define NP_IN_ACTION 0x0020
#define NP_IN_START  0x0040

/* Tipos de tile; coinciden con TILE_KIND_ID de tools/ngplat/project.py. */
#define NP_TILE_EMPTY    0
#define NP_TILE_SOLID    1
#define NP_TILE_PLATFORM 2
#define NP_TILE_HAZARD   3
#define NP_TILE_GOAL     4
#define NP_TILE_DECOR    5
/* Escaleras: se suben con arriba y se bajan con abajo, en diagonal. Hay dos
 * porque una escalera tiene sentido: la que sube hacia la derecha y la que
 * sube hacia la izquierda. No frenan a nadie -se pasa por delante andando- y
 * solo cuentan cuando el jugador se sube a ellas. */
#define NP_TILE_STAIR_R  6       /* sube hacia la derecha */
#define NP_TILE_STAIR_L  7       /* sube hacia la izquierda */
/* Punto de control: no estorba (se atraviesa), pero al tocarlo se apunta donde
 * estas. Si te matan y te quedan vidas, vuelves ahi en vez de al principio del
 * nivel, que es lo que hace que un nivel largo no sea un castigo. */
#define NP_TILE_CHECK    8

/* Tipos de ataque del jugador (NpAttackDef.kind). */
#define NP_ATTACK_NONE  0
#define NP_ATTACK_SHOT  1
#define NP_ATTACK_MELEE 2

/* Que es cada entidad (NpEntity.kind). */
#define NP_KIND_ENEMY 0
#define NP_KIND_ITEM  1
#define NP_KIND_SHOT  2
#define NP_KIND_PLATFORM 3
#define NP_KIND_BREAKABLE 4      /* candelabro: se rompe y suelta algo */
#define NP_KIND_SUBSHOT 5        /* lo que tira el arma secundaria */
#define NP_KIND_MELEE 6          /* el latigo: solo se ve, no toca a nadie */

/* El arma secundaria: se lanza con arriba + accion y gasta municion. */
#define NP_SUB_NONE  0
#define NP_SUB_LINE  1           /* va recto */
#define NP_SUB_ARC   2           /* describe un arco (le afecta la gravedad) */

/* Por donde va y viene una plataforma movil. */
#define NP_PLAT_X 0                  /* de lado */
#define NP_PLAT_Y 1                  /* arriba y abajo */

/* Comportamientos de enemigo; coinciden con BEHAVIOR_ID de project.py. */
#define NP_AI_PATROL 0
#define NP_AI_FLYER  1
#define NP_AI_CHASER 2
#define NP_AI_JUMPER 3
#define NP_AI_STATIC 4

/* Efectos de objeto; coinciden con ITEM_EFFECT_ID de project.py. */
#define NP_ITEM_POINTS 0
#define NP_ITEM_LIFE   1
#define NP_ITEM_HEALTH 2
#define NP_ITEM_KEY    3
#define NP_ITEM_AMMO   4         /* municion del arma secundaria */
#define NP_ITEM_UPGRADE 5        /* mejora el arma: cada uno la alarga un paso */
#define NP_ITEM_WEAPON  6        /* cambia el arma secundaria que llevas */

/* Ranuras de animacion (las que genera el compilador para cada actor). */
#define NP_ANIM_IDLE 0
#define NP_ANIM_RUN  1
#define NP_ANIM_JUMP 2
#define NP_ANIM_FALL 3
#define NP_ANIM_HURT 4
#define NP_ANIM_ATTACK 5
#define NP_ANIM_STAIR 6          /* subiendo una escalera */
#define NP_ANIM_CROUCH 7         /* agachado */
#define NP_ANIM_SLOTS 8

/* Eventos de sonido que produce la simulacion (un bit cada uno). Coinciden con
 * EVENTO_BIT de tools/ngplat/sonido.py. La simulacion solo los marca; quien los
 * hace sonar es la capa de sonido (la ROM M1 en la consola, Web Audio en el
 * preview), asi que no afectan a la fisica. */
#define NP_SFX_START   0x0001
#define NP_SFX_JUMP    0x0002
#define NP_SFX_DJUMP   0x0004
#define NP_SFX_COIN    0x0008
#define NP_SFX_STOMP   0x0010
#define NP_SFX_HURT    0x0020
#define NP_SFX_DIE     0x0040
#define NP_SFX_GOAL    0x0080
#define NP_SFX_LIFE    0x0100
#define NP_SFX_SHOOT   0x0200
#define NP_SFX_BREAK   0x0400    /* se ha roto un candelabro */
#define NP_SFX_CHECK   0x0800    /* se ha activado un punto de control */
#define NP_SFX_SLOTS   12        /* cuantos eventos distintos hay */

/* Estados del juego. */
#define NP_STATE_TITLE     0
#define NP_STATE_PLAY      1
#define NP_STATE_DYING     2
#define NP_STATE_LEVEL_END 3
#define NP_STATE_GAME_OVER 4
#define NP_STATE_FINISHED  5

#endif /* NP_TYPES_H */
