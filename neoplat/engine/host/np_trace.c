/* np_trace.c - ejecuta la simulacion sin hardware y escribe una traza.
 *
 * Se compila con el gcc del ordenador (no hace falta ngdevkit) y sirve para:
 *   - probar el motor en el ordenador,
 *   - comparar el motor en C con el preview en JavaScript
 *     (tests/test_paridad.py ejecuta los dos con las mismas pulsaciones).
 *
 *   gcc -I src -o np_trace np_trace.c src/np_world.c src/gamedata.c
 *   ./np_trace inputs.txt
 */

#include <stdio.h>
#include <stdlib.h>

#include "np_world.h"

static NpWorld world;
static NpLinea lineas[NP_SCREEN_H];

/* La carretera de este frame en un solo numero: por donde pasa el eje, cuanto
 * mide de ancho y que franja toca, linea a linea.
 *
 * Va a la traza porque es **lo que se ve**, y lo que se ve tiene que salir
 * igual en las ocho maquinas y en el preview. Comparar las 224 lineas una a
 * una haria una traza de un megabyte por partida; una firma las compara todas
 * y ocupa una columna. Fuera de la vista de carretera vale cero. */
static uint32_t carretera_firma(const NpWorld *w)
{
    uint32_t firma = 2166136261u;
    uint16_t horizonte = np_carretera(w, lineas);
    uint16_t y;
    if (horizonte >= NP_SCREEN_H) return 0;
    firma = (firma ^ horizonte) * 16777619u;
    for (y = horizonte; y < NP_SCREEN_H; y++) {
        firma = (firma ^ (uint32_t)(uint16_t)lineas[y].centro) * 16777619u;
        firma = (firma ^ (uint32_t)(uint16_t)lineas[y].medio) * 16777619u;
        firma = (firma ^ lineas[y].franja) * 16777619u;
    }
    return firma;
}

static uint32_t entity_hash(const NpWorld *w)
{
    uint32_t hash = 2166136261u;
    uint8_t i;
    for (i = 0; i < w->entity_count; i++) {
        const NpEntity *e = &w->entities[i];
        uint32_t values[6];
        uint8_t k;
        values[0] = (uint32_t)e->active;
        values[1] = (uint32_t)e->x;
        values[2] = (uint32_t)e->y;
        values[3] = (uint32_t)e->vy;
        values[4] = (uint32_t)((e->anim << 8) | e->anim_frame);
        values[5] = (uint32_t)((e->facing << 8) | e->health);
        for (k = 0; k < 6; k++) {
            hash ^= values[k];
            hash *= 16777619u;
        }
    }
    return hash;
}

/* Las variables en un solo numero, para que quepan en una columna. Es la
 * misma cuenta que hace trace.js: no vale para nada mas que para comparar. */
static uint32_t vars_firma(const NpWorld *w)
{
    uint32_t firma = 2166136261u;
    uint16_t i;
    for (i = 0; i < NP_MAX_VARS; i++) {
        firma ^= (uint32_t)w->vars[i];
        firma *= 16777619u;
    }
    return firma;
}

/* El archivo de pulsaciones lleva **dos numeros por linea**, uno por mando.
 * Las quince primeras columnas de la traza son las de siempre (el primer
 * jugador) y detras van las del segundo: asi las pruebas que miran una columna
 * por su numero siguen valiendo. */
int main(int argc, char **argv)
{
    FILE *fh;
    int input, input2;
    if (argc < 2) {
        fprintf(stderr, "uso: np_trace <archivo-de-pulsaciones>\n");
        return 1;
    }
    fh = fopen(argv[1], "r");
    if (!fh) {
        fprintf(stderr, "no puedo abrir %s\n", argv[1]);
        return 1;
    }

    np_world_init(&world);
    while (fscanf(fh, "%d %d", &input, &input2) == 2) {
        const NpPlayer *p0 = &world.players[0];
        const NpPlayer *p1 = &world.players[1];
        np_world_step(&world, (uint16_t)input, (uint16_t)input2);
        printf("%lu %ld %ld %ld %ld %u %u %u %lu %ld %ld %u %u %u %08x"
               " %ld %ld %ld %ld %u %u %u %u %u %u %u %u %u %d %d %u %u %u %u"
               " %lu %u %u %u %u %lu %u %u %u %08x %u\n",
               (unsigned long)world.frame,
               (long)p0->x, (long)p0->y, (long)p0->vx, (long)p0->vy,
               (unsigned)world.state, (unsigned)p0->health,
               (unsigned)p0->lives, (unsigned long)world.score,
               (long)world.cam_x, (long)world.cam_y,
               (unsigned)world.level_index, (unsigned)world.sfx,
               (unsigned)world.boss_health,
               entity_hash(&world),
               (long)p1->x, (long)p1->y, (long)p1->vx, (long)p1->vy,
               (unsigned)p1->health, (unsigned)p1->lives,
               (unsigned)p0->playing, (unsigned)p0->dying,
               (unsigned)p1->playing, (unsigned)p1->dying,
               (unsigned)world.keys, (unsigned)world.hearts,
               (unsigned)world.check_on, (int)world.check_x, (int)world.check_y,
               (unsigned)p0->power,
               /* el dibujo del latigo: 0 = no hay ninguno en la lista */
               (unsigned)(p0->whip ? 1 : 0),
               (unsigned)p0->crouch,
               (unsigned)world.sub,     /* el arma secundaria que se lleva */
               /* y la aventura: lo que llevas encima y cuantas casillas has
                  abierto. Sin esto la traza no miraria la bolsa y una de las
                  dos implementaciones podria guardar lo que le diera la gana
                  mientras el jugador acabara en el mismo sitio. */
               (unsigned long)np_bolsa_firma(&world),
               (unsigned)world.abiertos_n,
               /* Y el guion: por cual va, en que paso, que pagina de texto se
                  ve y que valen las variables. Sin esto la traza no miraria
                  nada de los guiones, y dos interpretes podrian decidir
                  distinto mientras el jugador acabara en el mismo sitio -que
                  es justo lo que pasa cuando el guion **para** la partida-. */
               (unsigned)world.guion, (unsigned)world.paso,
               (unsigned)world.paginas,
               (unsigned long)vars_firma(&world),
               /* y la aventura grafica: que verbo esta elegido */
               (unsigned)world.verbo,
               /* y el coche: que marcha lleva y si esta dando vueltas. Sin
                  esto la traza no miraria el cambio ni el choque, y las dos
                  implementaciones podrian llevar marchas distintas mientras
                  el coche acabara en el mismo sitio. */
               (unsigned)p0->marcha, (unsigned)p0->trompo,
               /* y la carretera que se ve, entera, en una firma */
               carretera_firma(&world),
               /* y el crono, que en un juego de conducir no es un adorno: es
                  la unica moneda que hay. Los controles de paso lo alargan y
                  las dos implementaciones tienen que contar igual. */
               (unsigned)world.time_left);
    }
    fclose(fh);
    return 0;
}
