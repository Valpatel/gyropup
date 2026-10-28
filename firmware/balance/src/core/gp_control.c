/* The balance law: a port of sim/controller_v2.py ControllerV2.control(). Line-by-line notes name the Python. */
#include "gp/gp_control.h"

#include <math.h>
#include <string.h>

#define GP_MODEL_TABLES
#include "gp/gp_model.h"
#include "gp/gp_config.h"

static float clampf(float v, float lo, float hi)
{
    return v < lo ? lo : (v > hi ? hi : v);
}

float gp_ctl_height_m(float frac)
{
    return GP_H_MIN_M + (GP_H_MAX_M - GP_H_MIN_M) * frac;
}

float gp_ctl_height_frac(float L)
{
    return (L - GP_H_MIN_M) / (GP_H_MAX_M - GP_H_MIN_M);
}

void gp_ctl_lqr_gains(float height, float K[4])
{
    const float x = clampf(height, 0.0f, 1.0f) * (float)(GP_LQR_N - 1);
    int i = (int)x;
    if (i >= GP_LQR_N - 1) {
        i = GP_LQR_N - 2;
    }
    const float a = x - (float)i;
    for (int k = 0; k < 4; k++) {
        K[k] = gp_lqr_k[i][k] + a * (gp_lqr_k[i + 1][k] - gp_lqr_k[i][k]);
    }
}

float gp_clip_motor(float tau, float omega, float peak, float omega_max, float cap)
{
    float lim = (tau * omega <= 0.0f) ? peak : peak * fmaxf(0.0f, 1.0f - fabsf(omega) / omega_max);
    if (cap > 0.0f) {
        lim = fminf(lim, cap);
    }
    return clampf(tau, -lim, lim);
}

/* One leg's share of the centre-of-mass sum (mass-weighted position and velocity of its four links) and its axle. */
static bool leg_mass(float p1, float p2, float w1, float w2, float mc[2], float mv[2], float *m, float E[2], float dE[2])
{
    gp_fb_joints j;
    float J[2][2];
    if (!gp_fb_fk(p1, p2, &j) || !gp_fb_jacobian(p1, p2, &j, J)) {
        return false;
    }
    const float l1 = GP_FB_L1_M, l2 = GP_FB_L2_M;
    dE[0] = J[0][0] * w1 + J[0][1] * w2;
    dE[1] = J[1][0] * w1 + J[1][1] * w2;
    E[0] = j.E.x;
    E[1] = j.E.z;
    const float dC[2] = {-l1 * sinf(p1) * w1, l1 * cosf(p1) * w1};
    const float dD[2] = {-l1 * sinf(p2) * w2, l1 * cosf(p2) * w2};
    const float cex = j.E.x - j.C.x, cez = j.E.z - j.C.z, dex = j.E.x - j.D.x, dez = j.E.z - j.D.z;
    const float a[4] = {p1, atan2f(cez, cex), p2, atan2f(dez, dex)};
    const float da[4] = {w1, (cex * (dE[1] - dC[1]) - cez * (dE[0] - dC[0])) / (l2 * l2), w2,
                         (dex * (dE[1] - dD[1]) - dez * (dE[0] - dD[0])) / (l2 * l2)};
    const gp_v2 org[4] = {j.A, j.C, j.B, j.D};
    const float *dorg[4] = {NULL, dC, NULL, dD};
    for (int k = 0; k < 4; k++) {
        const float mk = gp_com_link[k][0], lx = gp_com_link[k][1], lz = gp_com_link[k][2];
        const float s = sinf(a[k]), c = cosf(a[k]);
        const float rx = lx * c - lz * s, rz = lx * s + lz * c;
        mc[0] += mk * (org[k].x + rx);
        mc[1] += mk * (org[k].z + rz);
        mv[0] += mk * ((dorg[k] ? dorg[k][0] : 0.0f) - da[k] * rz);
        mv[1] += mk * ((dorg[k] ? dorg[k][1] : 0.0f) + da[k] * rx);
        *m += mk;
    }
    return true;
}

bool gp_ctl_theta(const gp_sense *s, float *theta, float *theta_dot)
{
    float mc[2] = {GP_COM_BASE_KG * GP_COM_BASE_X, GP_COM_BASE_KG * GP_COM_BASE_Z};
    float mv[2] = {0.0f, 0.0f};
    float m = GP_COM_BASE_KG, ax = 0.0f, az = 0.0f, vax = 0.0f, vaz = 0.0f;
    for (int side = 0; side < 2; side++) {
        float E[2], dE[2];
        if (!leg_mass(s->phi[side][0], s->phi[side][1], s->dphi[side][0], s->dphi[side][1], mc, mv, &m, E, dE)) {
            return false;
        }
        ax += 0.5f * E[0];
        az += 0.5f * E[1];
        vax += 0.5f * dE[0];
        vaz += 0.5f * dE[1];
    }
    /* d = com - axle in the body frame; theta = its angle from vertical + the body's rotation about +y */
    const float dx = mc[0] / m - ax, dz = mc[1] / m - az;
    const float ddx = mv[0] / m - vax, ddz = mv[1] / m - vaz;
    *theta = atan2f(dx, dz) + s->pitch;
    *theta_dot = (dz * ddx - dx * ddz) / (dx * dx + dz * dz) + s->pitch_rate;
    return true;
}

void gp_ctl_init(gp_ctl *c, const gp_ctl_params *p)
{
    memset(c, 0, sizeof *c);
    c->p = *p;
}

void gp_ctl_reset(gp_ctl *c, float height)
{
    c->height = clampf(height, 0.0f, 1.0f);
    c->dh = 0.0f;
    c->look = 0.0f;
    c->v_cmd = 0.0f;
    c->x_err = 0.0f;
}

/* The wheel link's angular rate in the body frame (about +y) and the wheel's speed over the ground. */
static float wheel_ground_speed(const gp_sense *s, int side)
{
    gp_fb_joints j;
    float J[2][2];
    const float p1 = s->phi[side][0], p2 = s->phi[side][1], w1 = s->dphi[side][0], w2 = s->dphi[side][1];
    if (!gp_fb_fk(p1, p2, &j) || !gp_fb_jacobian(p1, p2, &j, J)) {
        return 0.0f;
    }
    const float l1 = GP_FB_L1_M, l2 = GP_FB_L2_M;
    const float dEx = J[0][0] * w1 + J[0][1] * w2, dEz = J[1][0] * w1 + J[1][1] * w2;
    const float dDx = -l1 * sinf(p2) * w2, dDz = l1 * cosf(p2) * w2;
    const float ex = j.E.x - j.D.x, ez = j.E.z - j.D.z;
    const float psi_dot = (ex * (dEz - dDz) - ez * (dEx - dDx)) / (l2 * l2); /* from +x towards +z: about -y */
    const float w_abs = s->wheel_w[side] + s->pitch_rate - psi_dot;
    return GP_WHEEL_R_M * w_abs;
}

void gp_ctl_step(gp_ctl *c, const gp_sense *s, const gp_cmd *cmd, const gp_leg_cmd leg[2], bool wheels, gp_ctl_out *o)
{
    const float dt = GP_DT;
    memset(o, 0, sizeof *o);
    /* height slew */
    const float step = GP_G_HEIGHT_RATE * dt;
    c->height += clampf(cmd->height - c->height, -step, step);
    /* body levelling: roll > 0 (left side up) shortens the left leg */
    const float h0 = clampf(c->height + cmd->dip, 0.0f, 1.0f);
    const float lim = fminf(GP_G_ROLL_MAX, fminf(h0, 1.0f - h0));
    c->dh = clampf(c->dh + GP_G_ROLL_RATE * s->roll * dt, -lim, lim);
    const float dl = 0.5f * dt;
    c->look += clampf(clampf(cmd->look_up, -0.1f, 0.35f) - c->look, -dl, dl);

    /* the wheeled pendulum (v1's law) */
    float K[4];
    gp_ctl_lqr_gains(c->height, K);
    float theta = 0.0f, theta_dot = 0.0f;
    gp_ctl_theta(s, &theta, &theta_dot);
    theta += c->p.theta_trim;
    const float v = 0.5f * (wheel_ground_speed(s, GP_LEFT) + wheel_ground_speed(s, GP_RIGHT));
    const float vbus = clampf(s->vbus, 20.0f, 60.0f);
    const float wheel_omega = GP_WHEEL_W_PER_V * vbus;
    const float vmax = GP_G_SPEED_MARGIN * wheel_omega * GP_WHEEL_R_M;
    const float target = clampf(cmd->speed, -vmax, vmax);
    const float dv = GP_G_ACCEL * dt;
    c->v_cmd += clampf(target - c->v_cmd, -dv, dv);
    c->x_err = clampf(c->x_err + (v - c->v_cmd) * dt, -0.3f, 0.3f); /* x - x_ref, the reference kept within 0.3 m */
    const float u = -(K[0] * c->x_err + K[1] * theta + K[2] * (v - c->v_cmd) + K[3] * theta_dot);
    const float ylim = GP_G_YAW_SHARE * GP_WHEEL_PEAK_NM;
    const float tau_yaw = clampf(GP_G_YAW_KP_PER_NM * GP_WHEEL_PEAK_NM * (cmd->yaw_rate - s->yaw_rate), -ylim, ylim);

    /* the legs: a virtual spring-damper each, the feed-forward, the five-bar's Jacobian */
    const float leg_omega = GP_LEG_W_PER_V * vbus;
    const float lean_cmd = -(c->look + cmd->kick); /* the body leans back on its legs: the wheels move forward */
    for (int side = 0; side < 2; side++) {
        const float sgn = side == GP_LEFT ? -1.0f : 1.0f;
        const gp_leg_cmd *lc = &leg[side];
        gp_fb_polar *p = &o->leg[side];
        o->leg_ok[side] = gp_fb_polar_state(s->phi[side][0], s->phi[side][1], s->dphi[side][0], s->dphi[side][1], p);
        if (!o->leg_ok[side] || lc->mode == GP_LEG_OFF) {
            continue;
        }
        const gp_leg_gains *g = lc->tuck ? &c->p.tuck : &c->p.legs;
        float F;
        if (lc->mode == GP_LEG_FORCE) {
            F = lc->F;
            o->L_cmd[side] = p->L;
        } else {
            const float L_cmd = lc->mode == GP_LEG_LENGTH ? lc->L : gp_ctl_height_m(h0 + sgn * c->dh);
            o->L_cmd[side] = L_cmd;
            F = g->kp_L * (L_cmd - p->L) - g->kd_L * p->dL + c->p.leg_ff_n * lc->ff_scale;
        }
        const float T = g->kp_th * (lean_cmd - p->th) - g->kd_th * p->dth;
        float tau[2];
        gp_fb_vmc(p, F, T, tau);
        for (int m = 0; m < 2; m++) {
            const float t = gp_clip_motor(tau[m], s->dphi[side][m], GP_LEG_PEAK_NM, leg_omega, GP_LEG_CAP_NM);
            if (fabsf(t) < fabsf(tau[m]) - 1e-6f) {
                o->clipped |= (uint8_t)(1u << (2 * side + m));
            }
            o->tau[side][m] = t;
        }
    }
    if (c->p.balance && wheels) {
        const float want[2] = {0.5f * u - tau_yaw, 0.5f * u + tau_yaw};
        for (int side = 0; side < 2; side++) {
            const float t = gp_clip_motor(want[side], s->wheel_w[side], GP_WHEEL_PEAK_NM, wheel_omega, 0.0f);
            if (fabsf(t) < fabsf(want[side]) - 1e-6f) {
                o->clipped |= (uint8_t)(1u << (4 + side));
            }
            o->wheel[side] = t;
        }
    }
    o->theta = theta;
    o->theta_dot = theta_dot;
    o->x_err = c->x_err;
    o->v = v;
    o->v_cmd = c->v_cmd;
    o->u = u;
    o->tau_yaw = tau_yaw;
}
