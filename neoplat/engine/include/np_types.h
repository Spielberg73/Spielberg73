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
/* Cerrojo: una casilla que **no se pasa** hasta que llegas con el objeto que
 * pide. Es la otra mitad de una aventura: lo que te para no es un bicho, es
 * una puerta, y la llave esta tres pantallas atras. Al abrirla se gasta el
 * objeto y el paso se queda abierto para siempre.
 *
 * Que objeto abre cada cerrojo lo dice `np_tile_need` (el objeto mas uno). */
#define NP_TILE_LOCK     9
/* Liana, verja, cadena, enredadera: una casilla por la que se **trepa**.
 *
 * No es una escalera. Una escalera de las de arriba va en diagonal, se coge
 * desde el suelo y te lleva de un piso a otro. Una liana es vertical, se coge
 * **tambien en el aire** -saltas y te agarras, que es la mitad del genero de
 * Bruce Lee- y desde ella se salta a donde sea. No frena a nadie: se pasa por
 * delante andando, como una escalera. */
#define NP_TILE_CLIMB   10

/* --- la vista isometrica (los juegos de tipo filmation) ------------------
 *
 * Ahi el mapa no es lo que se ve: es la **planta** de la sala, y cada casilla
 * tiene ademas una altura. Una casilla de altura cero es suelo por el que se
 * anda; una de altura 16 es un cubo al que hay que subirse de un salto; una de
 * 48 es una pared. Lo que frena no es el tipo de la casilla sino lo alto que
 * esta comparado con tus pies, y por eso no hace falta un tipo nuevo: el mismo
 * `solido` de siempre, con su `alto:`, hace de cubo, de escalon y de muro.
 *
 * NP_SALA es lo que mide una sala en casillas. Ocho por ocho es lo que cabe en
 * una pantalla de 320x224 con la proyeccion de abajo, y es tambien el tamano
 * de las salas de los juegos del genero: una habitacion, un puzle. */
#define NP_SALA        8
#define NP_SALA_PX     (NP_SALA * NP_TILE)      /* 128 px de planta */
#define NP_SALA_SHIFT  7                        /* ...que son 2^7 */

/* La proyeccion: un punto de la planta (x, y) en pixeles cae en la pantalla en
 *
 *     sx = NP_ISO_OX + (x - y)
 *     sy = NP_ISO_OY + (x + y) / 2 - altura
 *
 * o sea rombos de 32x16, los de toda la vida. Con eso la planta de 128x128 px
 * de una sala ocupa 256x128 en pantalla, y NP_ISO_OX / NP_ISO_OY la centran
 * dejando sitio arriba para lo que sobresalga y para el marcador.
 *
 * Los dos son multiplos de 16 a proposito: el suelo de la sala se pega en la
 * rejilla de tiles de la pantalla, y con un origen a medio tile no cuadraria.
 * Y 80 y no 64 porque una pared de tres alturas en la casilla del fondo sube
 * hasta 48 pixeles por encima del rombo: con 64 se le comeria la punta el
 * marcador, que ocupa las tres primeras filas. */
#define NP_ISO_OX      160
#define NP_ISO_OY      80

/* Lo que se sube andando. Un escalon de seis pixeles se sube solo -asi un
 * suelo con relieve no se pelea contigo- y un cubo de dieciseis no: a los
 * cubos se salta, que es de lo que va el genero. */
#define NP_ESCALON     6

/* Y lo cerca del suelo que hay que estar para que un pincho pinche o para que
 * una meta cuente: saltando por encima no pasa nada. */
#define NP_ISO_PISA    6

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
#define NP_KIND_ENEMY_SHOT 7     /* lo que tira un enemigo con `dispara:` */
#define NP_KIND_PRISONER 8       /* el rehen: se suelta tocandolo */
#define NP_KIND_GENERATOR 9      /* el nido: saca bichos hasta que lo rompes */
/* El cubo de la vista isometrica: no anda, no hace dano y no se le pega. Es
 * escenario, y esta en la lista de entidades por una sola razon: para que se
 * dibuje **en su sitio** en la fila de profundidad, delante o detras de quien
 * pase por al lado. Se crean y se borran al cambiar de sala, asi que solo
 * ocupan huecos los de la sala que se esta viendo. */
#define NP_KIND_BLOQUE 10

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
#define NP_ITEM_BOMB    7        /* la pocima: hace dano a todo lo que se ve */
/* El objeto que se **lleva**: no hace nada al cogerlo, se guarda en la bolsa y
   sirve para abrir el sitio que lo pide. Es la mecanica de los Dizzy, y es lo
   que convierte un juego de saltar en una aventura: lo que te para no es un
   bicho, es una puerta cerrada y el objeto esta tres pantallas atras. */
#define NP_ITEM_CARRY   8

/* Cuantos cerrojos puede haber abiertos a la vez en un nivel. Ocho puertas
   dan de sobra para una aventura de las de entonces, y son ocho bytes. */
#define NP_MAX_ABIERTOS 12

/* Cuantas cosas se llevan a la vez. Tres, como en los Dizzy: con dos no hay
   puzle y con cinco te llevas media pantalla encima y ya no eliges. */
#define NP_BOLSA 3

/* --- las fases del luchador (juegos de tortas) ---------------------------
 *
 * Un enemigo que anda hacia ti y te roza no es una pelea: es un obstaculo. Lo
 * que hace una pelea es que se **coloque**, espere su turno, se prepare -y se
 * le vea venir- y suelte el golpe dejando una ventana para responder. Estas
 * seis fases son eso, y son las mismas que usa cualquier juego del genero. */
#define NP_LUCHA_IR        0     /* acercarse hasta la distancia de pelea */
#define NP_LUCHA_RONDAR    1     /* a distancia, esperando turno y moviendose */
#define NP_LUCHA_PREPARAR  2     /* el aviso: levanta el brazo y no se mueve */
#define NP_LUCHA_GOLPEAR   3     /* la caja hace dano */
#define NP_LUCHA_RECUPERAR 4     /* plantado despues: tu ventana */
#define NP_LUCHA_REPLEGAR  5     /* se aparta antes de volver a intentarlo */

/* Lo que se tambalea el que cobra un golpe: unos frames sin decidir nada, con
 * el empujon del golpe y la pose de dolor. Es lo que hace que una serie sea una
 * serie: sin ese hueco, el segundo puno llega cuando el otro ya se ha apartado
 * y encadenar es imposible. No lo tumba -para eso esta el remate-, lo deja
 * vendido, que es distinto y se ve distinto. */
#define NP_ATURDE 16

/* La carrera: cuanto dura un esprint y cuanto se espera al segundo toque.
 * Doce frames de ventana es lo que da un doble toque comodo sin que salte
 * corriendo cada vez que corriges el paso; ochenta de carrera son poco mas de
 * un segundo, lo justo para cruzar la pantalla y meterle un hombro a alguien.
 * Y `NP_CARRERA_X2` es lo que multiplica la velocidad, en octavos: 12/8 = una
 * vez y media, que se nota sin volverse ingobernable. */
#define NP_TOQUE_VENTANA 12
#define NP_CARRERA       80
#define NP_CARRERA_X2    12

/* Cuantos frames se para el mundo al acertar un golpe. Es el truco mas viejo
 * del genero: sin esa parada, el puno atraviesa al otro y no se siente nada;
 * con ella, pega. El remate para mas, porque es el golpe que cuenta. */
#define NP_CONGELADO      4
#define NP_CONGELADO_REMATE 9
/* Y lo que tiembla la camara al tumbar a alguien. */
#define NP_SACUDIDA       10

/* Ranuras de animacion (las que genera el compilador para cada actor). */
#define NP_ANIM_IDLE 0
#define NP_ANIM_RUN  1
#define NP_ANIM_JUMP 2
#define NP_ANIM_FALL 3
#define NP_ANIM_HURT 4
#define NP_ANIM_ATTACK 5
#define NP_ANIM_STAIR 6          /* subiendo una escalera */
#define NP_ANIM_CROUCH 7         /* agachado */
/* Las dos ultimas son de la vista cenital: ahi el heroe se ve de espaldas
   cuando anda hacia arriba y de frente cuando anda hacia abajo. En vista
   lateral no se usan nunca. */
#define NP_ANIM_UP   8           /* andando hacia arriba (de espaldas) */
#define NP_ANIM_DOWN 9           /* andando hacia abajo (de frente) */
/* Y la del remate: el ultimo golpe de una serie, el que tumba. Quien no la
   traiga se queda con la de atacar, asi que un juego sin series ni se entera. */
#define NP_ANIM_FINISH 10
/* La patada voladora: pegar **en el aire** es otro golpe, y por eso es otro
 * dibujo. Sin `patada:` en el game.yaml este hueco se queda vacio y en el aire
 * se pega con el fotograma de siempre, que es como estaba el kit. */
#define NP_ANIM_KICK 11
#define NP_ANIM_SLOTS 12

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
