/* np_world.h - estado y simulacion del juego (independiente del hardware).
 *
 * El mismo np_world_step() corre en la Neo Geo y en las pruebas de escritorio.
 * No usa memoria dinamica ni coma flotante.
 */
#ifndef NP_WORLD_H
#define NP_WORLD_H

#include "np_game.h"

#ifndef NP_MAX_ENTITIES
#define NP_MAX_ENTITIES 64
#endif

#ifndef NP_MAX_PLAYERS
#define NP_MAX_PLAYERS 2
#endif

typedef struct {
    np_fix x, y, vx, vy;
    uint16_t anim_timer;
    uint16_t invuln;
    uint16_t dying;          /* frames de caida al morir; 0 = no se esta muriendo */
    uint8_t anim, anim_frame;
    uint8_t on_ground, facing, jumps_left, health;
    uint8_t coyote, buffer;
    uint16_t attack_timer;   /* frames que le quedan al golpe (cuerpo a cuerpo) */
    uint16_t attack_cd;      /* frames hasta poder atacar otra vez */
    uint16_t stun;           /* frames sin control tras recibir un golpe */
    uint8_t riding;          /* plataforma que le lleva: indice + 1, 0 = ninguna */
    uint8_t power;           /* mejoras del arma recogidas (0 = sin mejorar) */
    uint8_t stairs;          /* 1 = subido a una escalera */
    int8_t stair_dir;        /* hacia donde avanza en x al subir: +1 o -1 */
    uint8_t lives;           /* las vidas son de cada uno */
    uint8_t playing;         /* 0 = fuera (segundo jugador de una partida a uno,
                                o el que se ha quedado sin vidas) */
} NpPlayer;

typedef struct {
    np_fix x, y, vx, vy;
    np_fix home_x;           /* donde salio (plataformas moviles) */
    np_fix home_y;           /* altura de origen (voladores y plataformas) */
    uint16_t vida;           /* proyectiles: frames que le quedan de vuelo */
    uint16_t timer;          /* cuenta atras de salto / fase del seno */
    uint16_t anim_timer;
    uint8_t active, kind, def;
    uint8_t anim, anim_frame, facing, health, hurt;
} NpEntity;

typedef struct {
    const NpLevel *level;
    /* Los jugadores. Con `jugadores: 1` solo el primero esta en juego; el
     * segundo existe igual, con `playing` a cero, para que el motor sea el
     * mismo y no haya dos caminos que mantener. */
    NpPlayer players[NP_MAX_PLAYERS];
    NpEntity entities[NP_MAX_ENTITIES];
    int32_t cam_x, cam_y;
    uint32_t score;          /* el marcador es comun: es una partida a dos */
    uint32_t frame;
    uint16_t level_index;
    uint16_t state, state_timer;
    uint16_t time_left;      /* en frames */
    uint16_t prev_input[NP_MAX_PLAYERS];
    uint16_t sfx;            /* eventos de sonido de este frame (NP_SFX_*) */
    uint8_t keys, hearts, entity_count;
    /* El punto de control tocado en este nivel, en casillas. `check_on` a cero
       quiere decir que todavia no se ha tocado ninguno y se reaparece en la
       salida. Se guarda en el mundo y no en el jugador porque a dos vale para
       los dos: el que muere vuelve al ultimo que haya tocado cualquiera. */
    int16_t check_x, check_y;
    uint8_t check_on;
    /* El jefe que hay en pantalla, para que el marcador pueda ensenarlo: los
       golpes que le quedan y los que aguantaba entero. 0 = no hay jefe. */
    uint8_t boss_health, boss_max;
} NpWorld;

void np_world_init(NpWorld *w);
void np_world_load_level(NpWorld *w, uint16_t index);
/* Un mando por jugador. Con un solo jugador, `input2` se ignora. */
void np_world_step(NpWorld *w, uint16_t input, uint16_t input2);

/* Consultas que usa la capa grafica. */
uint8_t np_tile_kind_at(const NpLevel *level, int32_t tx, int32_t ty);
uint16_t np_tile_gfx_at(const NpLevel *level, int32_t tx, int32_t ty);
void np_tile_gfx_column(const NpLevel *level, int32_t tx, int32_t ty,
                        uint16_t count, uint16_t *out);
const NpActorDef *np_entity_def(const NpEntity *e);
uint8_t np_actor_frame(const NpActorDef *def, uint8_t anim, uint8_t anim_frame);
/* Si hay que dibujar al jugador `quien` (0 o 1): fuera de juego, en el titulo o
   en mitad del parpadeo de invulnerabilidad, no. */
int np_player_visible(const NpWorld *w, uint8_t quien);

/* Barra de vida del jefe para el marcador; hace falta un buffer de
   NP_BOSS_BAR + 6 caracteres. */
#define NP_BOSS_BAR 10
void np_boss_bar(char *out, const NpWorld *w);

/* La linea de "lo que llevas" del marcador: las llaves que pide el nivel y la
   municion del arma secundaria, "KEYS 01/03 AMMO 05". Cada mitad sale en
   blanco si el juego no la usa, asi que el marcador no tiene que saber nada:
   escribe lo que salga. Hace falta un buffer de NP_EXTRAS_BAR + 1 caracteres. */
#define NP_EXTRAS_BAR 20
void np_extras_bar(char *out, const NpWorld *w);

/* La vida del jugador para el marcador: "LIFE ##...". Los llenos son los
   golpes que le quedan y los puntos los que ha perdido, asi que se ve de un
   vistazo cuanto aguanta y cuanto aguantaba entero. Sale en blanco con
   `vida: 1` (ahi no hay nada que mirar) y para un jugador que no juega. Hace
   falta un buffer de NP_LIFE_BAR + 6 caracteres. */
#define NP_LIFE_BAR 9
#define NP_LIFE_LABEL 5     /* lo que ocupa la etiqueta, antes de los cuadrados */
void np_life_bar(char *out, const NpWorld *w, uint8_t quien);
/* Cuantos cuadrados lleva la barra en este juego (0 = no hay barra). No cambia
   en toda la partida, asi que el marcador puede pintar la etiqueta una sola vez
   y repintar solo los cuadrados, que es lo unico que se mueve. */
uint8_t np_life_pips(void);

#endif /* NP_WORLD_H */
