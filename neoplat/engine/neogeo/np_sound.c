/* np_sound.c - traduce lo que pasa en el juego a ordenes para el Z80. */

#include "np_sound.h"
#include "gamedata.h"

/* Las ordenes salen de una en una por frame: el puerto solo guarda un byte y
 * dos escrituras seguidas podrian pisarse. Con una cola pequena no se pierde
 * ningun sonido aunque coincidan varios en el mismo frame. */
#define NP_SOUND_QUEUE 8

static uint8_t np_queue[NP_SOUND_QUEUE];
static uint8_t np_queue_head, np_queue_tail;
static uint8_t np_toggle;
static uint8_t np_music_playing;

static void np_queue_push(uint8_t payload)
{
    uint8_t next = (uint8_t)((np_queue_tail + 1) % NP_SOUND_QUEUE);
    if (next == np_queue_head) return;         /* cola llena: se descarta */
    np_queue[np_queue_tail] = payload;
    np_queue_tail = next;
}

void np_sound_init(void)
{
    np_queue_head = np_queue_tail = 0;
    np_toggle = 0;
    np_music_playing = 0xFF;
}

void np_sound_command(uint8_t payload)
{
    np_toggle ^= 0x40;
    *NP_REG_SOUND = (uint8_t)((payload & 0x3F) | np_toggle);
}

void np_sound_update(const NpWorld *w)
{
#if NP_SOUND_ENABLED
    uint8_t music = (w->state == NP_STATE_PLAY) ? w->level->music : 0;
    uint8_t i;

    if (music != np_music_playing) {
        np_music_playing = music;
        np_queue_push(music ? (uint8_t)(NP_CMD_MUSIC_BASE + music - 1)
                            : (uint8_t)NP_CMD_MUSIC_STOP);
    }
    if (w->sfx) {
        for (i = 0; i < NP_SFX_SLOTS; i++) {
            if ((w->sfx & (1 << i)) && np_sfx_command[i]) {
                np_queue_push(np_sfx_command[i]);
                break;                          /* solo hay un canal de efectos */
            }
        }
    }
    if (np_queue_head != np_queue_tail) {
        np_sound_command(np_queue[np_queue_head]);
        np_queue_head = (uint8_t)((np_queue_head + 1) % NP_SOUND_QUEUE);
    }
#else
    (void)w;
#endif
}
