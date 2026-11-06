/* The Jetson protocol's frames (gp_jetson.h has the layout). */
#include "gp/gp_jetson.h"

#include <math.h>
#include <string.h>

#include "gp/gp_config.h"

static int16_t sat16(float v)
{
    if (!isfinite(v)) return 0;
    v = roundf(v);
    return (int16_t)(v > 32767.0f ? 32767.0f : (v < -32768.0f ? -32768.0f : v));
}

static uint16_t satu16(float v)
{
    if (!isfinite(v)) return 0;
    v = roundf(v);
    return (uint16_t)(v > 65535.0f ? 65535.0f : (v < 0.0f ? 0.0f : v));
}

static void wr16(uint8_t *d, uint16_t v)
{
    d[0] = (uint8_t)v;
    d[1] = (uint8_t)(v >> 8);
}

static int16_t rd16(const uint8_t *d)
{
    return (int16_t)(d[0] | (d[1] << 8));
}

static void std_frame(gp_can_frame *f, uint32_t id)
{
    memset(f, 0, sizeof *f);
    f->id = id;
    f->len = 8;
}

bool gp_jet_decode_setpoint(const gp_can_frame *f, gp_jet_setpoint *s)
{
    if (f->ext || f->id != GP_ID_JET_SETPOINT || f->len != 8) {
        return false;
    }
    const uint8_t *d = f->data;
    s->speed = rd16(d) * 1e-3f;
    s->yaw_rate = rd16(d + 2) * 1e-3f;
    s->height = (d[4] > 200 ? 200 : d[4]) * 0.005f;
    s->lean = (int8_t)d[5] * 0.01f;
    s->run = (d[6] & 0x01u) != 0;
    s->people_near = (d[6] & 0x02u) != 0;
    s->jump_seq = (uint8_t)((d[6] >> 2) & 0x3u);
    s->jump_height = (uint8_t)(d[6] >> 4);
    s->seq = d[7];
    return true;
}

void gp_jet_encode_setpoint(const gp_jet_setpoint *s, gp_can_frame *f)
{
    std_frame(f, GP_ID_JET_SETPOINT);
    wr16(f->data, (uint16_t)sat16(s->speed * 1e3f));
    wr16(f->data + 2, (uint16_t)sat16(s->yaw_rate * 1e3f));
    float h = roundf(s->height * 200.0f);
    f->data[4] = (uint8_t)(h < 0.0f ? 0.0f : (h > 200.0f ? 200.0f : h));
    float l = roundf(s->lean * 100.0f);
    f->data[5] = (uint8_t)(int8_t)(l < -128.0f ? -128.0f : (l > 127.0f ? 127.0f : l));
    f->data[6] = (uint8_t)((s->run ? 0x01u : 0u) | (s->people_near ? 0x02u : 0u) | ((s->jump_seq & 0x3u) << 2) |
                           ((s->jump_height & 0xFu) << 4));
    f->data[7] = s->seq;
}

void gp_jet_encode_state_a(const gp_jet_state *s, gp_can_frame *f)
{
    std_frame(f, GP_ID_MCU_STATE_A);
    wr16(f->data, (uint16_t)sat16(s->pitch * 1e4f));
    wr16(f->data + 2, (uint16_t)sat16(s->pitch_rate * 1e3f));
    wr16(f->data + 4, (uint16_t)sat16(s->speed * 1e3f));
    wr16(f->data + 6, (uint16_t)sat16(s->yaw_rate * 1e3f));
}

void gp_jet_encode_state_b(const gp_jet_state *s, gp_can_frame *f)
{
    std_frame(f, GP_ID_MCU_STATE_B);
    wr16(f->data, satu16(s->L[0] * 1e4f));
    wr16(f->data + 2, satu16(s->L[1] * 1e4f));
    wr16(f->data + 4, (uint16_t)sat16(s->lean[0] * 1e4f));
    wr16(f->data + 6, (uint16_t)sat16(s->lean[1] * 1e4f));
}

void gp_jet_encode_status(const gp_jet_state *s, gp_can_frame *f)
{
    std_frame(f, GP_ID_MCU_STATUS);
    f->data[0] = s->mode;
    f->data[1] = s->flags;
    wr16(f->data + 2, satu16(s->vbus * 100.0f));
    wr16(f->data + 4, (uint16_t)sat16(s->ibus * 100.0f));
    f->data[6] = s->reason;
    f->data[7] = s->seq;
}
