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

int main(int argc, char **argv)
{
    FILE *fh;
    int input;
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
    while (fscanf(fh, "%d", &input) == 1) {
        np_world_step(&world, (uint16_t)input);
        printf("%lu %ld %ld %ld %ld %u %u %u %lu %ld %ld %u %u %08x\n",
               (unsigned long)world.frame,
               (long)world.player.x, (long)world.player.y,
               (long)world.player.vx, (long)world.player.vy,
               (unsigned)world.state, (unsigned)world.player.health,
               (unsigned)world.lives, (unsigned long)world.score,
               (long)world.cam_x, (long)world.cam_y,
               (unsigned)world.level_index, (unsigned)world.sfx,
               entity_hash(&world));
    }
    fclose(fh);
    return 0;
}
