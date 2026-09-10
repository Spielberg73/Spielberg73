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
/* Casilla que **no para pero frena**: hierba, arena, barro, el arcen de una
 * carretera. Se pasa por encima como si no hubiera nada, pero mientras estas
 * ahi no puedes correr: la velocidad se te cae a la que aguante ese suelo.
 *
 * No es un pincho ni una pared: es la diferencia entre irse de una curva y
 * estrellarse, y es lo que hace que salirse de la carretera cueste tiempo en
 * vez de matarte. Fuera de la vista de carretera vale igual -un charco en un
 * juego cenital, un arenal en uno de plataformas-, asi que no es de un genero:
 * es un tipo de suelo mas. */
#define NP_TILE_LENTO   11

/* --- la vista de carretera (los juegos de conducir) ----------------------
 *
 * La pantalla no ensena el mapa: ensena la carretera yendose al horizonte. La
 * camara va **detras y por encima** del coche, mirando siempre hacia arriba
 * del mapa, y lo que se dibuja es la proyeccion de la cinta de asfalto.
 *
 * La cuenta es la de toda la vida: algo que esta a distancia z de la camara,
 * a una altura ALTO por debajo de ella, cae en la linea
 *
 *     sy = HORIZONTE + (ALTO * FOCAL / z)
 *
 * y lo que mide de ancho se encoge en la misma proporcion, FOCAL/z. A esa
 * proporcion la llamamos `k` y es lo unico que hace falta: multiplica la
 * distancia al eje de la carretera y multiplica su ancho.
 *
 * Las tres cifras no son ajustables desde el game.yaml **a proposito**: son la
 * camara del genero, no una opcion. Cambiarlas cambia como se ve un juego de
 * conducir, no como se juega, y con ocho maquinas que tienen que dibujar lo
 * mismo, una camara distinta por juego es una pantalla distinta por maquina
 * esperando a pasar. */
#define NP_HORIZONTE    88       /* la linea del horizonte, de 224 */
#define NP_CAMARA_ALTO  48       /* lo alto que va la camara sobre el asfalto */
#define NP_FOCAL       135       /* la distancia focal, en pixeles */
#define NP_CAMARA_ATRAS 24       /* lo que va la camara detras del coche */
#define NP_CERCA        16       /* el primer tramo, a un tile de la camara */
/* Cuantos tramos se miran hacia delante. Mas alla de estos la carretera cae en
 * las dos lineas de encima del horizonte y no se distingue de una raya, asi
 * que mirarlos seria pagar por nada. Son 160 casillas: 2560 pixeles, que es
 * mas de lo que ve un juego de la epoca. */
#define NP_TRAMOS_VISTA 160
/* Y cuantos tramos caben en la cinta de un nivel: uno por fila del mapa, que
 * como mucho son 256 (el limite de alto de un nivel). */
#define NP_MAX_TRAMOS   256
/* Y lo mas ancha que puede ser una calzada, en casillas: el ancho maximo de un
 * nivel. Es el tamano de la cuenta con la que se busca el ancho que mas se
 * repite. */
#define NP_MAX_ANCHO    64
/* Lo que se deja por debajo del coche del jugador: el morro no pega con el
 * borde de la pantalla, que quedaria raro, ni tapa la carretera de delante. */
#define NP_CARRETERA_MARGEN 14
/* Cuanto mas deprisa pasa la animacion del coche cuando va a tope. A cero, la
 * melena de ella iria siempre al mismo ritmo -y parada tambien-, que es
 * justo lo que no se quiere: lo que dice a que velocidad vas, con el coche
 * clavado en el centro de la pantalla, son la carretera y el pelo. */
#define NP_MELENA_MAX 5
/* Lo que se corre el coche a un lado al girar el volante. Es lo unico que dice
 * que estas girando, porque el coche se ve de culo y no se puede espejar sin
 * cambiar de asiento a los dos que van dentro. */
#define NP_CARRETERA_LADEO 6

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
/* El trafico de un juego de conducir: un coche que va a lo suyo. No te
 * persigue ni te busca -no es un enemigo, es un estorbo-: sube por la
 * carretera por **su carril** y a su velocidad, y esta ahi para que tengas que
 * elegir por donde pasarlo. Tocarlo no quita vida: te hace un trompo, y eso
 * cuesta tiempo, que es la unica moneda del genero. */
#define NP_AI_TRAFICO 5

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

/* --- las variables y los guiones -----------------------------------------
 *
 * Una variable es la memoria del juego: un numero con nombre que se pone, se
 * suma y se mira. Sin ellas un nivel es siempre igual la primera vez y la
 * decima; con ellas el juego se acuerda de lo que has hecho, y eso es lo que
 * separa "un nivel" de "un juego".
 *
 * Treinta y dos dan de sobra para lo que se hace con esto -banderas de puertas
 * abiertas, cuantas monedas llevas, si ya has hablado con alguien- y son 64
 * bytes de RAM, que es lo que hay que mirar cuando el destino es una maquina de
 * 1988. */
#define NP_MAX_VARS 32

/* Los pasos de un guion. Un guion es una lista de estos, y el motor los va
 * ejecutando **en el mismo frame** hasta que llega a uno que espera (`decir` y
 * `esperar`): asi poner tres variables y dar un objeto no cuesta cuatro frames,
 * que es lo que pasaria si cada paso durase uno. */
#define NP_PASO_FIN     0        /* se acabo el guion */
#define NP_PASO_DECIR   1        /* cuadro de texto; para hasta que se pulsa */
#define NP_PASO_ESPERAR 2        /* espera unos frames */
#define NP_PASO_PONER   3        /* variable = valor */
#define NP_PASO_SUMAR   4        /* variable += valor (puede ser negativo) */
#define NP_PASO_SI      5        /* si no se cumple, salta unos pasos */
#define NP_PASO_SALTAR  6        /* salta unos pasos, sin mirar nada */
#define NP_PASO_SONIDO  7        /* dispara un efecto de los del game.yaml */
#define NP_PASO_DAR     8        /* da un objeto, como si lo hubieras cogido */
#define NP_PASO_NIVEL   9        /* cambia de nivel */
#define NP_PASO_LLEVAR 10        /* pone al jugador en una casilla */
#define NP_PASO_QUITAR 11        /* borra una casilla del mapa (ya no esta) */
#define NP_PASO_ACABAR 12        /* se acabo el nivel (y con el ultimo, el juego) */

/* Como se compara en un `si`. */
#define NP_CMP_IGUAL    0
#define NP_CMP_DISTINTO 1
#define NP_CMP_MENOR    2
#define NP_CMP_MENOR_IG 3
#define NP_CMP_MAYOR    4
#define NP_CMP_MAYOR_IG 5

/* Lo que cabe en un cuadro de texto: dos lineas de 36 caracteres. El limite no
 * es de la RAM sino de la pantalla mas estrecha de las siete -40 columnas de
 * ocho pixeles-, dejando dos de margen a cada lado. El compilador parte el
 * texto en paginas de este tamano; el motor solo sabe ensenar una pagina. */
#define NP_DIALOGO_COLS 36
#define NP_DIALOGO_FILAS 2
/* La columna donde empieza el cuadro y la primera de sus dos filas. Cada
 * maquina puede mover la fila: en la Neo Geo el marcador vive arriba del todo
 * y los mensajes en medio de la pantalla, asi que alli el cuadro va donde ya
 * sale "LEVEL CLEAR" y no debajo del tanteo. */
#define NP_DIALOGO_COL 2
#ifndef NP_DIALOGO_FILA
#define NP_DIALOGO_FILA 1
#endif

/* --- los verbos de la aventura grafica ------------------------------------
 *
 * En una aventura de puntero no se salta ni se pega: se **elige que hacer** y
 * se senala donde. Los cuatro verbos son los de siempre, los que caben en la
 * cabeza de cualquiera sin leer instrucciones: mirar una cosa, cogerla, usarla
 * y hablar con quien sea. Cada casilla del mapa puede llevar un guion por
 * verbo, y eso -y no un tipo de tile nuevo- es lo que hace que la misma puerta
 * conteste una cosa al mirarla y otra al abrirla.
 *
 * Cuatro y no doce: con doce verbos la mitad no se usa nunca y el juego se
 * convierte en probarlos todos, que es lo que mato al genero. */
#define NP_VERBO_MIRAR  0
#define NP_VERBO_COGER  1
#define NP_VERBO_USAR   2
#define NP_VERBO_HABLAR 3
#define NP_VERBOS       4

/* Cuantos pasos seguidos se ejecutan en un frame antes de cortar. Es la red
 * contra un guion que se llame a si mismo dando vueltas: mejor que se note que
 * va lento a que la maquina se quede colgada. */
#define NP_PASOS_POR_FRAME 64

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
