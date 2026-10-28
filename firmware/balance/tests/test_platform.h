#ifndef TEST_PLATFORM_H
#define TEST_PLATFORM_H

#include "gp/gp_app.h"

#define TP_MAX 512
#define TP_PARAMS 8

typedef struct {
    struct {
        uint8_t bus;
        gp_can_frame f;
    } sent[TP_MAX];
    int n_sent;
    float angle[4];
    uint8_t mode[4], fault_bits[4];
    bool mute[4];
    float torque[4];
    uint16_t pidx[4][TP_PARAMS];
    uint8_t pval[4][TP_PARAMS][4];
    gp_can_frame last_status;
} tp_state;

extern tp_state TP;

/* Answer every frame sent since the last call as four RS-04s would (motor ids 1-4: 1, 2 on bus A, 3, 4 on bus B). */
void tp_answer(gp_app *a, uint32_t now);

#endif
