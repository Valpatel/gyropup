/* The leg's guards: a port of sim/leg_limits.py (gp_guard.h). */
#include "gp/gp_guard.h"

#include <math.h>

#define GP_LIMITS_TABLES
#include "gp/gp_limits.h"

void gp_guard_limits(uint8_t build, gp_torque_limits *t)
{
    t->build = build;
    if (build == GP_BUILD_ROBOT) {
        t->everyday_nm = GP_LIM_ROBOT_EVERYDAY_NM;
        t->peak_nm = GP_LIM_ROBOT_PEAK_NM;
        t->motor_nm = GP_LIM_ROBOT_MOTOR_NM;
    } else {
        t->build = GP_BUILD_PLA_BENCH;
        t->everyday_nm = GP_LIM_PLA_EVERYDAY_NM;
        t->peak_nm = GP_LIM_PLA_PEAK_NM;
        t->motor_nm = GP_LIM_PLA_MOTOR_NM;
    }
    t->rms_nm = GP_LIM_RMS_NM;
}

float gp_guard_approach(float d, float everyday_nm)
{
    const float w_contact = everyday_nm / sqrtf(GP_LIM_STOP_K * GP_LIM_J_MOTOR);
    return sqrtf(w_contact * w_contact + 2.0f * (everyday_nm / GP_LIM_J_MOTOR) * fmaxf(0.0f, d));
}

float gp_guard_soft_stop(float tau, float phi, float omega, float lo, float hi, float everyday_nm)
{
    const float sgn[2] = {1.0f, -1.0f}, d[2] = {hi - phi, phi - lo}; /* towards hi: +, towards lo: - */
    for (int k = 0; k < 2; k++) {
        if (d[k] >= GP_LIM_SOFT_ZONE_RAD) {
            continue;
        }
        if (d[k] < GP_LIM_SOFT_MARGIN_RAD && tau * sgn[k] > 0.0f) {
            tau = 0.0f;
        }
        const float excess = omega * sgn[k] - gp_guard_approach(d[k] - GP_LIM_SOFT_MARGIN_RAD, everyday_nm);
        if (excess > 0.0f) { /* at least this much braking, away from the stop */
            tau = sgn[k] * fminf(tau * sgn[k], -fminf(everyday_nm, GP_LIM_SOFT_KD * excess));
        }
    }
    return tau;
}

void gp_guard_window(float lean, float *L_min, float *L_max)
{
    const int n = GP_LIM_WIN_N;
    if (lean <= gp_lim_window[0][0]) {
        *L_min = gp_lim_window[0][1];
        *L_max = gp_lim_window[0][2];
        return;
    }
    for (int i = 0; i + 1 < n; i++) {
        const float *a = gp_lim_window[i], *b = gp_lim_window[i + 1];
        if (lean <= b[0]) {
            const float w = (lean - a[0]) / (b[0] - a[0]);
            *L_min = a[1] + w * (b[1] - a[1]);
            *L_max = a[2] + w * (b[2] - a[2]);
            return;
        }
    }
    *L_min = gp_lim_window[n - 1][1];
    *L_max = gp_lim_window[n - 1][2];
}

float gp_guard_clamp_L(float L, float lean)
{
    float lo, hi;
    gp_guard_window(lean, &lo, &hi);
    return L < lo ? lo : (L > hi ? hi : L);
}

bool gp_guard_angle_ok(float phi, float lo, float hi)
{
    return phi >= lo - GP_LIM_ANGLE_WINDOW_RAD && phi <= hi + GP_LIM_ANGLE_WINDOW_RAD;
}

float gp_guard_rms(float *ms, float tau, float dt)
{
    *ms += fminf(dt / GP_LIM_RMS_TAU_S, 1.0f) * (tau * tau - *ms);
    return sqrtf(*ms);
}
