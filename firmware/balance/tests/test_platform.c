/* The unit tests' platform: every frame the firmware sends is kept, and four minimal RS-04s answer the private
 * protocol (feedback, parameter reads of what was written) from a fixed stance, so the supervisor can run without the
 * Python HIL (which is not in CI). */
#include "test_platform.h"

#include <string.h>

#include "gp/gp_rs04.h"

tp_state TP;

bool gp_plat_can_send(uint8_t bus, const gp_can_frame *f)
{
    if (TP.n_sent >= TP_MAX) {
        return false;
    }
    TP.sent[TP.n_sent].bus = bus;
    TP.sent[TP.n_sent].f = *f;
    TP.n_sent++;
    return true;
}

static void put_be16(uint8_t *d, uint16_t v)
{
    d[0] = (uint8_t)(v >> 8);
    d[1] = (uint8_t)v;
}

static void feedback(int m, gp_can_frame *r)
{
    memset(r, 0, sizeof *r);
    r->ext = 1;
    r->len = 8;
    r->id = gp_rs04_id(GP_RS04_FEEDBACK, (uint16_t)((TP.mode[m] << 14) | (TP.fault_bits[m] << 8) | (m + 1)), 0xFD);
    put_be16(r->data, gp_rs04_f2u(TP.angle[m], -GP_RS04_P_MAX, GP_RS04_P_MAX));
    put_be16(r->data + 2, gp_rs04_f2u(0.0f, -GP_RS04_V_MAX, GP_RS04_V_MAX));
    put_be16(r->data + 4, gp_rs04_f2u(0.0f, -GP_RS04_T_MAX, GP_RS04_T_MAX));
    put_be16(r->data + 6, 300);
}

void tp_answer(gp_app *a, uint32_t now)
{
    for (int k = 0; k < TP.n_sent; k++) {
        const gp_can_frame *f = &TP.sent[k].f;
        const uint8_t bus = TP.sent[k].bus;
        if (bus == GP_BUS_C) {
            if (!f->ext && f->id == 0x122) {
                TP.last_status = *f;
            }
            continue;
        }
        if (!f->ext) continue;
        const uint8_t kind = (uint8_t)(f->id >> 24), motor = (uint8_t)f->id;
        const int m = motor - 1;
        if (m < 0 || m > 3 || TP.mute[m]) continue;
        if ((m < 2 && bus != GP_BUS_A) || (m >= 2 && bus != GP_BUS_B)) continue;
        gp_can_frame r;
        const uint16_t idx = (uint16_t)(f->data[0] | (f->data[1] << 8));
        switch (kind) {
        case GP_RS04_ENABLE: TP.mode[m] = 2; feedback(m, &r); break;
        case GP_RS04_STOP: TP.mode[m] = 0; feedback(m, &r); break;
        case GP_RS04_MIT:
            TP.torque[m] = gp_rs04_u2f((uint16_t)((f->id >> 8) & 0xFFFF), -GP_RS04_T_MAX, GP_RS04_T_MAX);
            feedback(m, &r);
            break;
        case GP_RS04_WRITE:
            for (int p = 0; p < TP_PARAMS; p++) {
                if (TP.pidx[m][p] == idx || TP.pidx[m][p] == 0) {
                    TP.pidx[m][p] = idx;
                    memcpy(TP.pval[m][p], f->data + 4, 4);
                    break;
                }
            }
            feedback(m, &r);
            break;
        case GP_RS04_READ: {
            memset(&r, 0, sizeof r);
            r.ext = 1;
            r.len = 8;
            r.id = gp_rs04_id(GP_RS04_READ, (uint16_t)(motor), 0xFD);
            r.data[0] = (uint8_t)idx;
            r.data[1] = (uint8_t)(idx >> 8);
            for (int p = 0; p < TP_PARAMS; p++) {
                if (TP.pidx[m][p] == idx) memcpy(r.data + 4, TP.pval[m][p], 4);
            }
            break;
        }
        default: continue;
        }
        gp_app_can_rx(a, bus, &r, now);
    }
    TP.n_sent = 0;
}
