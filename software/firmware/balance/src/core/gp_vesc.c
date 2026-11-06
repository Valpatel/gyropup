/* VESC CAN frames: current mode out, status 1-5 in. */
#include "gp/gp_vesc.h"

#include <math.h>
#include <string.h>

static int32_t rd32(const uint8_t *d)
{
    return (int32_t)(((uint32_t)d[0] << 24) | ((uint32_t)d[1] << 16) | ((uint32_t)d[2] << 8) | d[3]);
}

static int16_t rd16(const uint8_t *d)
{
    return (int16_t)((d[0] << 8) | d[1]);
}

void gp_vesc_set_current(uint8_t id, float amps, gp_can_frame *f)
{
    memset(f, 0, sizeof *f);
    if (!isfinite(amps)) {
        amps = 0.0f;
    }
    const float ma = amps * 1000.0f;
    const int32_t v = (int32_t)(ma > 2.0e9f ? 2.0e9f : (ma < -2.0e9f ? -2.0e9f : ma));
    f->id = ((uint32_t)GP_VESC_SET_CURRENT << 8) | id;
    f->ext = 1;
    f->len = 4;
    f->data[0] = (uint8_t)((uint32_t)v >> 24);
    f->data[1] = (uint8_t)((uint32_t)v >> 16);
    f->data[2] = (uint8_t)((uint32_t)v >> 8);
    f->data[3] = (uint8_t)v;
}

bool gp_vesc_parse(const gp_can_frame *f, uint8_t *id, uint8_t *cmd, gp_vesc_status *s)
{
    if (!f->ext || (f->id >> 16) != 0u) {
        return false; /* VESC ids are (command << 8 | id) with a command under 256 */
    }
    *id = (uint8_t)(f->id & 0xFFu);
    *cmd = (uint8_t)((f->id >> 8) & 0xFFu);
    const uint8_t *d = f->data;
    switch (*cmd) {
    case GP_VESC_STATUS_1:
        if (f->len < 8) return false;
        s->erpm = rd32(d);
        s->current = rd16(d + 4) / 10.0f;
        s->duty = rd16(d + 6) / 1000.0f;
        return true;
    case GP_VESC_STATUS_2:
        if (f->len < 8) return false;
        s->ah = rd32(d) / 1e4f;
        s->ah_charged = rd32(d + 4) / 1e4f;
        return true;
    case GP_VESC_STATUS_3:
        if (f->len < 8) return false;
        s->wh = rd32(d) / 1e4f;
        s->wh_charged = rd32(d + 4) / 1e4f;
        return true;
    case GP_VESC_STATUS_4:
        if (f->len < 8) return false;
        s->temp_fet = rd16(d) / 10.0f;
        s->temp_motor = rd16(d + 2) / 10.0f;
        s->current_in = rd16(d + 4) / 10.0f;
        s->pid_pos = rd16(d + 6) / 50.0f;
        return true;
    case GP_VESC_STATUS_5:
        if (f->len < 6) return false;
        s->tach = rd32(d);
        s->v_in = rd16(d + 4) / 10.0f;
        return true;
    default:
        return false;
    }
}
