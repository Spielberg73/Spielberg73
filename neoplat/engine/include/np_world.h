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
    /* Solo en vista cenital: hacia donde mira, de 0 a 7 empezando por la
       derecha y girando en el sentido del reloj. Es lo que decide por
       donde sale el disparo, y `facing` sigue siendo el espejo del
       dibujo. */
    uint8_t aim;
    uint8_t coyote, buffer;
    uint16_t attack_timer;   /* frames que le quedan al golpe (cuerpo a cuerpo) */
    uint16_t attack_cd;      /* frames hasta poder atacar otra vez */
    uint16_t stun;           /* frames sin control tras recibir un golpe */
    uint8_t riding;          /* plataforma que le lleva: indice + 1, 0 = ninguna */
    uint8_t whip;            /* el dibujo del latigo: indice + 1, 0 = ninguno */
    uint8_t power;           /* mejoras del arma recogidas (0 = sin mejorar) */
    uint8_t stairs;          /* 1 = subido a una escalera */
    /* 1 = agarrado a una liana. No es lo mismo que `stairs`: a una escalera se
       sube desde el suelo y va en diagonal; a una liana te agarras **tambien
       en el aire** y se sube recta. */
    uint8_t trepa;
    uint8_t crouch;          /* 1 = agachado */
    int8_t stair_dir;        /* hacia donde avanza en x al subir: +1 o -1 */
    uint16_t wear_timer;     /* frames para el siguiente punto de `desgaste:` */
    /* La tercera coordenada de la vista de cinta: lo alto que estas sobre el
       suelo, y a que velocidad subes o bajas. En las otras vistas valen cero
       siempre. `y` sigue siendo donde se dibuja, asi que la linea del suelo
       -por donde se anda y con lo que se choca- es y + altura. */
    np_fix altura, valtura;
    /* La serie de golpes: por cual va y cuanto queda para que se corte. */
    uint16_t combo_timer;
    uint8_t combo_link;
    /* A quien tienes agarrado: su sitio en la lista **mas uno** (0 = a nadie),
       y lo que le queda de agarre antes de soltarse. */
    uint16_t grab_timer;
    uint8_t grab;
    /* --- el repertorio de los juegos de tortas --------------------------
     *
     * `fuerte` marca que el golpe que esta saliendo vale por un remate: o se
     * solto **por el aire** (la patada en salto) o **en carrera** (el hombro).
     * Los dos cuestan algo -uno te deja en el aire sin corregir, el otro gasta
     * el esprint- y por eso los dos pegan mas y tumban. Es lo que hace que un
     * grupo de tres se pueda romper por un lado en vez de aguantarlo de
     * frente.
     *
     * `carrera` es lo que queda de un esprint, y `toque`/`toque_dir` el doble
     * toque que lo enciende: dos veces la misma direccion antes de que se
     * acabe la ventana. */
    uint8_t fuerte;
    uint8_t carrera;
    uint8_t toque;
    int8_t toque_dir;
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
    /* Derribado: frames que se queda sin gobernarse, resbalando con el empujon
       del ultimo golpe de una serie. Mientras dura no decide nada ni hace dano
       al tocarte, que es lo que hace que rematar sirva de algo. */
    uint8_t knock;
    /* Lo alto que esta sobre el suelo, para el que sale volando de un
       lanzamiento. Vale lo mismo que en el jugador: `y` es donde se dibuja y
       la linea del suelo es y + altura. Fuera de la vista de cinta es cero. */
    np_fix altura, valtura;
    /* A quien ya ha tocado **este** golpe: un bit por jugador. La caja del
       cuerpo a cuerpo se queda puesta varios frames y acertaria en todos, asi
       que se marca al tocar y se limpia al empezar el golpe siguiente. Antes
       esto lo hacia el parpadeo (`hurt`), y por eso una serie de tres solo
       acertaba el primero: el segundo llegaba con el enemigo aun parpadeando. */
    uint8_t golpeado;
    /* --- el luchador de los juegos de tortas ----------------------------
     *
     * En que va: acercarse, rondar esperando turno, prepararse, pegar,
     * recuperarse o replegarse (NP_LUCHA_*). Lo que queda de la fase va en
     * `timer`, que en esta vista no lo usa nadie mas.
     *
     * `tocado` es a quien ya ha alcanzado **este** golpe, un bit por jugador:
     * la caja se queda puesta varios frames y si no acertaria en todos. Es lo
     * mismo que `golpeado` pero al reves -aquel es el golpe del jugador-. */
    uint8_t fase;
    uint8_t tocado;
    /* Lo que le queda de tambaleo: mientras dura no decide nada y aguanta el
       empujon del golpe. Es el hueco por el que entra el golpe siguiente. */
    uint8_t aturdido;
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
    /* Lo que se lleva encima: el objeto de cada hueco **mas uno** (0 = vacio).
       Es de la partida y no de cada jugador, como las llaves: a dos, lo que
       coge uno le sirve al otro.
       Van en palabras y no en bytes aunque quepan de sobra en un byte: son
       tres huecos seguidos que se recorren en bucle, y gcc junta dos lecturas
       de byte pegadas en una sola de palabra. Si la bolsa cae en una direccion
       impar -y con tres bytes cae la mitad de las veces-, esa palabra es un
       "address error" y el 68000 se para en seco. En palabras la direccion es
       par siempre y no hay nada que juntar mal. */
    uint16_t bolsa[NP_BOLSA];
    /* Los cerrojos que ya se han abierto en este nivel, por su casilla. Se
       guardan aparte porque el mapa vive en ROM y no se puede tocar: son ocho
       huecos, que es lo que cabe en una aventura de una tarde. */
    uint16_t abiertos[NP_MAX_ABIERTOS];
    uint8_t abiertos_n;
    /* El arma secundaria que se lleva en la mano, indice en np_subs. Es de la
       partida y no de cada jugador, igual que la municion: a dos, la que coge
       uno la llevan los dos. */
    uint8_t sub;
    /* El punto de control tocado en este nivel, en casillas. `check_on` a cero
       quiere decir que todavia no se ha tocado ninguno y se reaparece en la
       salida. Se guarda en el mundo y no en el jugador porque a dos vale para
       los dos: el que muere vuelve al ultimo que haya tocado cualquiera. */
    int16_t check_x, check_y;
    uint8_t check_on;
    /* El jefe que hay en pantalla, para que el marcador pueda ensenarlo: los
       golpes que le quedan y los que aguantaba entero. 0 = no hay jefe. */
    uint8_t boss_health, boss_max;
    /* --- lo que hace que una pelea sea una pelea ------------------------
     *
     * `atacando` es cuantos enemigos estan pegando **ahora mismo**: se cuenta
     * una vez por frame y con eso se reparten las fichas, porque si pegaran
     * todos a la vez no habria juego, habria un enjambre. `congelado` son los
     * frames de parada al acertar un golpe -lo que hace que se sienta- y
     * `sacudida` los que la camara tiembla despues de un derribo. */
    uint8_t atacando;
    uint8_t congelado;
    uint8_t sacudida;
    /* --- la vista isometrica --------------------------------------------
     *
     * La sala que se esta viendo, en salas de 8x8 casillas, y cuantos cubos
     * suyos hay montados. Los cubos viven al **final** de la lista de
     * entidades -de NP_MAX_ENTITIES hacia atras- y se rehacen enteros cada vez
     * que se cambia de sala: asi solo ocupan hueco los de la sala de ahora y
     * los bucles de siempre, que llegan hasta `entity_count`, ni los miran.
     *
     * Van en palabras y no en bytes por lo mismo que la bolsa: dos bytes
     * pegados que se leen seguidos los junta gcc en una palabra, y si cae en
     * direccion impar el 68000 se para en seco. */
    /* En que pantalla estabamos el frame pasado, con `camara: pantallas`. Sirve
       para enterarse de que se ha cambiado de una a otra, que es cuando entran
       los perseguidores tenaces por el borde por el que has entrado tu. */
    uint16_t pantalla_x, pantalla_y;
    uint16_t sala_x, sala_y;
    uint8_t bloques_n;
    uint8_t bloques_abiertos;    /* cuantos cerrojos habia abiertos al montarla */
} NpWorld;

void np_world_init(NpWorld *w);
void np_world_load_level(NpWorld *w, uint16_t index);
/* Un mando por jugador. Con un solo jugador, `input2` se ignora. */
void np_world_step(NpWorld *w, uint16_t input, uint16_t input2);

/* Consultas que usa la capa grafica. */
uint8_t np_tile_kind_at(const NpLevel *level, int32_t tx, int32_t ty);
/* Donde cae en la pantalla un actor del mundo: la esquina de arriba a la
 * izquierda de su dibujo, sin restar la camara.
 *
 * En las vistas de siempre es la cuenta de toda la vida (x - box_x, y - box_y)
 * y por eso los dibujantes no la llaman: la resuelve la macro NP_PANTALLA de
 * gamedata.h en el propio sitio. En la isometrica hay que proyectar, y ahi el
 * punto que manda es **donde apoya los pies** -el centro de su caja en la
 * planta-, que es lo unico que tiene sentido cuando el suelo son rombos. */
void np_pantalla(const NpWorld *w, np_fix x, np_fix y, np_fix altura,
                 const NpActorDef *def, int32_t *sx, int32_t *sy);
uint16_t np_tile_gfx_at(const NpWorld *w, int32_t tx, int32_t ty);
void np_tile_gfx_column(const NpWorld *w, int32_t tx, int32_t ty,
                        uint16_t count, uint16_t *out);
const NpActorDef *np_entity_def(const NpEntity *e);

/* En que orden se dibujan las entidades. Rellena `orden` con sus sitios en la
 * lista y devuelve cuantas hay que pintar.
 *
 * Fuera de la vista de cinta es el orden de siempre (0, 1, 2...) y no cuesta
 * nada. En la de cinta van **de mas lejos a mas cerca**, o sea por la linea del
 * suelo: en un juego de tortas los actores se pisan todo el rato y, sin esto,
 * el que esta detras se dibuja delante y no se entiende quien esta donde.
 *
 * Lo usan los seis dibujantes de maquina (y el preview hace lo mismo), asi que
 * el reparto es identico en todas.
 *
 * La lista la pone el motor y se devuelve prestada: asi ninguna maquina tiene
 * que reservar sesenta y cuatro bytes de pila en mitad del frame, que en el ST
 * -donde la pila vive apretada- se lleva por delante otras cosas. Vale hasta
 * la siguiente llamada, que es justo lo que dura el dibujado. */
const uint8_t *np_orden_dibujo(const NpWorld *w, uint8_t *cuantas);

/* Y como lo usan los dibujantes:
 *
 *     orden = np_orden_dibujo(w, &cuantas);
 *     for (i = 0; i < cuantas; i++) {
 *         const NpEntity *e = &w->entities[NP_DIBUJO(orden, i)];
 *
 * En un juego de cinta NP_DIBUJO mira la lista; en cualquier otro se resuelve
 * en `i` al compilar, asi que el bucle queda **exactamente** el de siempre: ni
 * una indireccion de mas. No es purismo: en el Atari ST esa indireccion, en el
 * bucle que dibuja a todos los actores, cuesta lo bastante como para que el
 * juego pierda el vblank y la musica suene lenta.
 *
 * NP_DIBUJO lo escribe el compilador en gamedata.h, que es donde se sabe que
 * vista lleva el juego. */

/* Que se dibuja en un puesto de la fila que devuelve np_orden_dibujo, y donde
 * cae en la pantalla (sin restar la camara: eso lo hace cada maquina a su
 * manera). Devuelve cero cuando en ese puesto no hay nada que pintar.
 *
 * Es el unico sitio donde se decide todo eso, y por eso los seis dibujantes
 * tienen un solo bucle:
 *
 *     orden = np_orden_dibujo(w, &cuantas);
 *     for (i = 0; i < cuantas; i++) {
 *         const NpActorDef *def = np_dibujo(w, NP_DIBUJO(orden, i),
 *                                           &sx, &sy, &frame, &flip);
 *         if (!def) continue;
 *
 * Solo lo usan los dibujantes **en la vista isometrica**, que es donde la fila
 * lleva ademas los cubos de la sala y a los jugadores -ahi hay un detras de
 * verdad: uno se mete tras un cubo cada dos pasos-. En las demas vistas cada
 * maquina sigue con sus dos bucles de siempre, y no por gusto: preguntar aqui
 * por cada actor cuesta lo justo para que la Mega Drive pierda el vblank y el
 * juego se vaya a la mitad de velocidad. */
const NpActorDef *np_dibujo(const NpWorld *w, uint8_t puesto,
                            int32_t *sx, int32_t *sy,
                            uint8_t *frame, uint8_t *flip);

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
/* Lo que lleva la bolsa en un solo numero, para que el marcador sepa si la
   linea de arriba ha cambiado. Cero con la bolsa vacia y en los juegos que no
   llevan bolsa, que es lo mismo que decir que nunca molesta. */
uint32_t np_bolsa_firma(const NpWorld *w);

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

/* Que musica toca ahora mismo, en numero de musica (indice + 1, cero =
   silencio). Lo decide el motor y no cada maquina: en el titulo suena la del
   titulo, jugando la del nivel, y si hay un jefe en pantalla y el juego lleva
   musica de jefe, esa. Asi la regla es una y suena igual en las seis. */
uint8_t np_music_now(const NpWorld *w);

#endif /* NP_WORLD_H */
