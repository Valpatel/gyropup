/* RobStride RS-04 private protocol: frames as rig/rs04.py packs and parses them (that module cites the manual). */
#include "gp/gp_rs04.h"

#include <math.h>
#include <string.h>

#include "gp/gp_config.h"

uint32_t gp_rs04_id(uint8_t kind, uint16_t data2, uint8_t dest)
{
    return ((uint32_t)(kind & 0x1Fu) << 24) | ((uint32_t)data2 << 8) | dest;
}

uint16_t gp_rs04_f2u(float x, float lo, float hi)
{
    if (!isfinite(x)) {
        x = (lo < 0.0f && hi > 0.0f) ? 0.0f : lo; /* a motor is never sent a NaN */
    }
    if (x <= lo) {
        return 0;
    }
    if (x >= hi) {
        return 0xFFFFu;
    }
    return (uint16_t)((x - lo) * (65535.0f / (hi - lo)));
}

float gp_rs04_u2f(uint16_t u, float lo, float hi)
{
    return lo + (float)u * ((hi - lo) / 65535.0f);
}

static void be16(uint8_t *d, uint16_t v)
{
    d[0] = (uint8_t)(v >> 8);
    d[1] = (uint8_t)v;
}

static uint16_t rd_be16(const uint8_t *d)
{
    return (uint16_t)((d[0] << 8) | d[1]);
}

static void frame(gp_can_frame *f, uint8_t kind, uint16_t data2, uint8_t dest)
{
    memset(f, 0, sizeof *f);
    f->id = gp_rs04_id(kind, data2, dest);
    f->ext = 1;
    f->len = 8;
}

void gp_rs04_mit(uint8_t motor, float p, float v, float kp, float kd, float t, gp_can_frame *f)
{
    frame(f, GP_RS04_MIT, gp_rs04_f2u(t, -GP_RS04_T_MAX, GP_RS04_T_MAX), motor);
    be16(&f->data[0], gp_rs04_f2u(p, -GP_RS04_P_MAX, GP_RS04_P_MAX));
    be16(&f->data[2], gp_rs04_f2u(v, -GP_RS04_V_MAX, GP_RS04_V_MAX));
    be16(&f->data[4], gp_rs04_f2u(kp, 0.0f, GP_RS04_KP_MAX));
    be16(&f->data[6], gp_rs04_f2u(kd, 0.0f, GP_RS04_KD_MAX));
}

void gp_rs04_enable(uint8_t motor, gp_can_frame *f)
{
    frame(f, GP_RS04_ENABLE, GP_RS04_HOST, motor);
}

void gp_rs04_stop(uint8_t motor, bool clear_fault, gp_can_frame *f)
{
    frame(f, GP_RS04_STOP, GP_RS04_HOST, motor);
    f->data[0] = clear_fault ? 1u : 0u; /* must be 0 in normal running (4.1.4) */
}

void gp_rs04_read(uint8_t motor, uint16_t index, gp_can_frame *f)
{
    frame(f, GP_RS04_READ, GP_RS04_HOST, motor);
    f->data[0] = (uint8_t)index;
    f->data[1] = (uint8_t)(index >> 8);
}

static void write_head(uint8_t motor, uint16_t index, gp_can_frame *f)
{
    frame(f, GP_RS04_WRITE, GP_RS04_HOST, motor);
    f->data[0] = (uint8_t)index;
    f->data[1] = (uint8_t)(index >> 8);
}

void gp_rs04_write_u8(uint8_t motor, uint16_t index, uint8_t v, gp_can_frame *f)
{
    write_head(motor, index, f);
    f->data[4] = v;
}

void gp_rs04_write_u32(uint8_t motor, uint16_t index, uint32_t v, gp_can_frame *f)
{
    write_head(motor, index, f);
    for (int k = 0; k < 4; k++) {
        f->data[4 + k] = (uint8_t)(v >> (8 * k));
    }
}

void gp_rs04_write_f32(uint8_t motor, uint16_t index, float v, gp_can_frame *f)
{
    uint32_t u;
    memcpy(&u, &v, 4);
    gp_rs04_write_u32(motor, index, u, f);
}

float gp_rs04_param_f32(const gp_rs04_param *p)
{
    uint32_t u = (uint32_t)p->raw[0] | ((uint32_t)p->raw[1] << 8) | ((uint32_t)p->raw[2] << 16) | ((uint32_t)p->raw[3] << 24);
    float v;
    memcpy(&v, &u, 4);
    return v;
}

uint32_t gp_rs04_param_u32(const gp_rs04_param *p)
{
    return (uint32_t)p->raw[0] | ((uint32_t)p->raw[1] << 8) | ((uint32_t)p->raw[2] << 16) | ((uint32_t)p->raw[3] << 24);
}

bool gp_rs04_parse(const gp_can_frame *f, gp_rs04_msg *m)
{
    m->kind = -1;
    if (!f->ext || f->len != 8) {
        return false;
    }
    const uint8_t kind = (uint8_t)((f->id >> 24) & 0x1Fu);
    const uint16_t d2 = (uint16_t)((f->id >> 8) & 0xFFFFu);
    const uint8_t dest = (uint8_t)(f->id & 0xFFu);
    if (dest != GP_RS04_HOST) {
        return false; /* addressed to a motor: some host's request, not a reply */
    }
    if (kind == GP_RS04_FEEDBACK || kind == GP_RS04_REPORT) {
        if (f->data[0] == 0x00 && f->data[1] == 0xC4 && f->data[2] == 0x56) {
            return false; /* the firmware-version frame */
        }
        gp_rs04_feedback *b = &m->fb;
        b->motor = (uint8_t)(d2 & 0xFFu);
        b->faults = (uint8_t)((d2 >> 8) & 0x3Fu);
        b->mode = (uint8_t)((d2 >> 14) & 0x3u);
        b->host = dest;
        b->p = gp_rs04_u2f(rd_be16(&f->data[0]), -GP_RS04_P_MAX, GP_RS04_P_MAX);
        b->v = gp_rs04_u2f(rd_be16(&f->data[2]), -GP_RS04_V_MAX, GP_RS04_V_MAX);
        b->t = gp_rs04_u2f(rd_be16(&f->data[4]), -GP_RS04_T_MAX, GP_RS04_T_MAX);
        b->temp_c = (float)rd_be16(&f->data[6]) / 10.0f;
        m->kind = GP_RS04_FEEDBACK;
        return true;
    }
    if (kind == GP_RS04_READ) {
        gp_rs04_param *p = &m->param;
        p->motor = (uint8_t)(d2 & 0xFFu);
        p->ok = ((d2 >> 8) & 0xFFu) == 0u;
        p->host = dest;
        p->index = (uint16_t)(f->data[0] | (f->data[1] << 8));
        memcpy(p->raw, &f->data[4], 4);
        m->kind = GP_RS04_READ;
        return true;
    }
    if (kind == GP_RS04_FAULT) {
        gp_rs04_fault *q = &m->fault;
        q->motor = (uint8_t)(d2 & 0xFFu);
        q->host = dest;
        q->fault = (uint32_t)f->data[0] | ((uint32_t)f->data[1] << 8) | ((uint32_t)f->data[2] << 16) | ((uint32_t)f->data[3] << 24);
        q->warning = (uint32_t)f->data[4] | ((uint32_t)f->data[5] << 8) | ((uint32_t)f->data[6] << 16) | ((uint32_t)f->data[7] << 24);
        m->kind = GP_RS04_FAULT;
        return true;
    }
    return false;
}
