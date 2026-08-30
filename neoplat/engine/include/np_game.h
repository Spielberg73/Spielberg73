/* np_game.h - estructuras de datos que genera `ngplat build`.
 *
 * Todo lo que hay aqui vive en ROM (const): el compilador de NeoPlat escribe
 * un gamedata.c con estas tablas a partir de game.yaml.
 */
#ifndef NP_GAME_H
#define NP_GAME_H

#include "np_types.h"

typedef struct {
    const uint8_t *frames;   /* indices de fotograma dentro de la hoja */
    uint8_t count;
    uint8_t speed;           /* frames de juego por fotograma */
    uint8_t loop;
} NpAnim;

typedef struct {
    uint16_t first_tile;     /* primer tile de la hoja en la ROM C */
    uint8_t palette;         /* paleta asignada */
    uint8_t cols, rows;      /* tamano del fotograma en tiles de 16x16 */
    int16_t box_x, box_y;    /* caja de colision dentro del fotograma */
    int16_t box_w, box_h;
    NpAnim anims[NP_ANIM_SLOTS];
} NpActorDef;

/* El ataque del jugador. `kind` a cero quiere decir que el juego no lleva
 * ataque y el boton no hace nada, que es como estaba el kit hasta ahora.
 *
 *   NP_ATTACK_SHOT   sale un proyectil que vuela de frente hasta chocar con
 *                    una pared, dar a un enemigo o agotar su alcance;
 *   NP_ATTACK_MELEE  no sale nada: durante `duration` frames hay una caja
 *                    delante del jugador que hace dano a lo que toque.
 *
 * `actor` es el dibujo: con NP_ATTACK_SHOT es el proyectil que sale volando y
 * con NP_ATTACK_MELEE es el **arma en si** (el latigo), que se dibuja delante
 * del jugador mientras el golpe hace dano. `fx` a uno quiere decir que ese
 * dibujo existe; a cero el golpe es invisible, que es como estaba el kit. */
typedef struct {
    NpActorDef actor;
    np_fix speed;            /* velocidad del proyectil */
    uint16_t range;          /* pixeles que recorre, o alcance del golpe */
    uint16_t cooldown;       /* frames entre un ataque y el siguiente */
    uint16_t duration;       /* frames que dura el golpe */
    /* Frames de preparacion antes de que el golpe haga dano. En un latigo el
     * brazo tarda en llegar, y es lo que obliga a medir la distancia en vez de
     * pegar botones. 0 = el golpe vale desde el primer frame. */
    uint16_t windup;
    /* Las mejoras del arma. Un objeto con `efecto: mejora` sube un nivel, cada
     * nivel suma `range_step` pixeles de alcance y se pierden todos al morir,
     * que es lo que hace que perder una vida duela mas que perder una vida.
     * `levels` a cero deja el arma como estaba y el objeto no hace nada. */
    uint16_t range_step;     /* pixeles que alarga cada mejora */
    uint8_t levels;          /* cuantas mejoras admite (0 = ninguna) */
    uint8_t kind;            /* NP_ATTACK_* */
    uint8_t damage;
    uint8_t locks;           /* 1 = mientras pegas no te puedes mover */
    uint8_t fx;              /* 1 = `actor` es un dibujo de verdad */
} NpAttackDef;

/* El arma secundaria: se lanza con **arriba + accion** y gasta municion, que
 * es una cuenta aparte de la vida (los objetos con `efecto: municion` la
 * suben). Con `gravity` a cero va recta; con gravedad describe un arco y cae,
 * que es lo que distingue un hacha de un cuchillo. */
typedef struct {
    NpActorDef actor;
    np_fix speed;
    np_fix gravity;          /* 0 = recta */
    np_fix jump;             /* impulso hacia arriba al salir, para el arco */
    uint16_t range;          /* pixeles que recorre antes de apagarse */
    uint16_t cooldown;
    uint8_t kind;            /* NP_SUB_* */
    uint8_t cost;            /* municion que gasta cada tirada */
    uint8_t damage;
} NpSubDef;

typedef struct {
    NpActorDef actor;
    np_fix speed, accel, friction, air_accel;
    np_fix jump, jump_cut, gravity, max_fall, bounce;
    /* Al recibir un golpe sales despedido hacia atras con esta fuerza y te
     * quedas `stun` frames sin control. Es lo que convierte un roce en una
     * caida al vacio, y de eso vive medio diseno de niveles clasico. */
    np_fix knockback;
    /* Lo que se avanza por cada frame en una escalera, en diagonal. Va aparte
     * de `speed` porque en los clasicos se sube despacio, y esa lentitud es la
     * que hace que una escalera sea un sitio donde te pueden cazar. */
    np_fix stair_speed;
    uint16_t invuln, stun;
    uint8_t coyote, jump_buffer, double_jump, stomp, health;
    NpAttackDef attack;
    NpSubDef sub;
} NpPlayerDef;

typedef struct {
    NpActorDef actor;
    np_fix speed, gravity, jump, range, amplitude;
    uint16_t period, interval, score;
    uint8_t behavior, health, damage, stompable, edge_turn;
    uint8_t boss;            /* 1 = matarlo termina el nivel */
} NpEnemyDef;

typedef struct {
    NpActorDef actor;
    uint16_t score;
    uint8_t effect, amount;
} NpItemDef;

/* Un candelabro: no hace nada hasta que le pegas, y entonces suelta lo que
 * lleve dentro. Es el bucle de los clasicos de latigo -pegar a todo lo que se
 * mueva y a todo lo que no- y por eso es una entidad y no un tile: asi las
 * cinco maquinas lo dibujan gratis y entra en el hash de la traza. */
typedef struct {
    NpActorDef actor;
    uint16_t score;
    uint8_t drop;            /* indice del objeto que suelta + 1; 0 = nada */
    uint8_t health;          /* golpes que aguanta */
} NpBreakableDef;

typedef struct {
    uint16_t x, y;           /* posicion en pixeles (esquina superior izquierda) */
    uint8_t kind;            /* 0 = enemigo, 1 = objeto */
    uint8_t def;             /* indice en np_enemies / np_items */
} NpSpawn;

/* Capa de fondo con scroll propio (parallax). Es solo decorado: no participa
 * en la simulacion, asi que no afecta a la paridad con el preview. */
typedef struct {
    const uint16_t *tiles;   /* cols * rows numeros de tile de la ROM C */
    uint16_t speed_x;        /* 8.8: 256 = se mueve igual que el escenario */
    uint16_t speed_y;
    int16_t offset_y;        /* donde empieza la capa en la pantalla */
    uint8_t cols, rows;
    uint8_t palette;
    uint8_t repeat;          /* 1 = se repite horizontalmente */
} NpLayer;

/* Una plataforma movil: va y viene entre donde sale y `distance` pixeles mas
 * alla, y el que se sube encima va con ella. No hace dano ni se puede matar:
 * es escenario que se mueve. */
typedef struct {
    NpActorDef actor;
    np_fix speed;                    /* pixeles por frame */
    uint16_t distance;               /* recorrido, en pixeles */
    uint8_t axis;                    /* NP_PLAT_X o NP_PLAT_Y */
} NpPlatformDef;

typedef struct {
    const char *name;
    uint16_t width, height;          /* en tiles */
    const uint8_t *cells;            /* width * height indices de np_tile_* */
    const NpSpawn *spawns;
    uint16_t spawn_count;
    uint16_t start_x, start_y;       /* salida del jugador, en pixeles */
    uint16_t background;             /* color de fondo ya en formato Neo Geo */
    const uint8_t *layers;           /* indices en np_layers, de lejos a cerca */
    uint8_t layer_count;
    uint8_t music;                   /* 0 = sin musica, si no indice + 1 */
    uint8_t keys_needed;             /* llaves que pide la meta, 0 = ninguna */
} NpLevel;

/* Tablas que genera el compilador (definidas en gamedata.c). */
extern const NpPlayerDef np_player_def;
extern const NpEnemyDef np_enemies[];
extern const NpItemDef np_items[];
extern const NpPlatformDef np_platforms[];
extern const NpBreakableDef np_breakables[];
extern const NpLevel np_levels[];
extern const NpLayer np_layers[];
extern const uint8_t np_tile_kind[];     /* tipo de cada tile del proyecto */
extern const uint16_t np_tile_gfx[];     /* tile grafico dentro de la ROM C */
extern const np_fix np_sin_table[64];    /* seno en 24.8, un ciclo completo */
/* Orden que hay que mandar al Z80 por cada evento de sonido (0 = sin sonido).
 * El indice es el numero de bit de NP_SFX_*. */
extern const uint8_t np_sfx_command[NP_SFX_SLOTS];

extern const uint16_t np_level_count;
extern const uint16_t np_layer_count;
extern const uint16_t np_enemy_count;
extern const uint16_t np_item_count;
extern const uint16_t np_platform_count;
extern const uint16_t np_breakable_count;
extern const uint16_t np_tile_count;
extern const uint16_t np_tileset_first_tile;
extern const uint8_t np_tileset_palette;
extern const uint8_t np_start_lives;
extern const uint8_t np_player_count;     /* 1 o 2 jugadores a la vez */
extern const uint16_t np_time_limit;      /* en segundos, 0 = sin limite */
extern const uint8_t np_camara_pantallas; /* 1 = pantalla a pantalla, 0 = scroll */
extern const char np_game_title[];
extern const char np_game_author[];

#endif /* NP_GAME_H */
