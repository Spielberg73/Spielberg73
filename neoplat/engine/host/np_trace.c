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
               " %ld %ld %ld %ld %u %u %u %u %u %u %u %u %u %d %d %u %u %u\n",
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
               (unsigned)p0->crouch);
    }
    fclose(fh);
    return 0;
}
