/* Unit tests of the portable core (no HAL, no Python): ctest runs them in CI.
 * Golden numbers marked "(Python)" were computed with the leg rig's rig/rs04.py and cad/fivebar.py
 * (legrig/program 277288a) and are copied here so CI needs neither. */
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "gp/gp_app.h"
#include "gp/gp_config.h"
#include "gp/gp_control.h"
#include "gp/gp_fivebar.h"
#include "gp/gp_guard.h"
#include "gp/gp_limits.h"
#include "gp/gp_ina228.h"
#include "gp/gp_jetson.h"
#include "gp/gp_model.h"
#include "gp/gp_rs04.h"
#include "gp/gp_vesc.h"
#include "gp/gp_vn100.h"
#include "test_platform.h"

static int fails, checks;
#define CHECK(c) do { checks++; if (!(c)) { fails++; printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)
#define NEAR(a, b, tol) do { checks++; double _a = (a), _b = (b); if (!(fabs(_a - _b) <= (tol))) { fails++; \
    printf("FAIL %s:%d: %s = %.9g, want %.9g (+-%g)\n", __FILE__, __LINE__, #a, _a, _b, (double)(tol)); } } while (0)

/* ------------------------------------------------------------------------------------------- five-bar */
static void test_fivebar(void)
{
    /* (Python) fivebar.stance(h, lean) and fivebar.jacobian (mm/rad) */
    const struct { float L, lean_deg; double p1, p2, Ex, Ez, J[2][2]; } g[] = {
        {0.300f, 0.0f, -0.8879823170668525, -2.2536103365229407, 0.0, -300.0, {{109.40905437, 109.40905436}, {101.07770282, -101.07770279}}},
        {0.140f, 0.0f, -0.1765193108996448, -2.9650733426901486, 0.0, -140.0, {{50.85847270, 50.85847269}, {99.63639245, -99.63639242}}},
        {0.250f, 10.0f, -0.4220839909365289, -2.2569733107840007, 43.41204442, -246.20193825, {{75.58052997, 111.83554699}, {123.95337242, -101.95115414}}},
    };
    for (int k = 0; k < (int)(sizeof g / sizeof g[0]); k++) {
        float phi[2];
        CHECK(gp_fb_stance(g[k].L, g[k].lean_deg * 0.0174532925f, phi));
        NEAR(phi[0], g[k].p1, 2e-5);
        NEAR(phi[1], g[k].p2, 2e-5);
        gp_fb_joints j;
        CHECK(gp_fb_fk((float)g[k].p1, (float)g[k].p2, &j));
        NEAR(j.E.x * 1000.0f, g[k].Ex, 2e-3);
        NEAR(j.E.z * 1000.0f, g[k].Ez, 2e-3);
        float J[2][2];
        CHECK(gp_fb_jacobian((float)g[k].p1, (float)g[k].p2, &j, J));
        for (int r = 0; r < 2; r++)
            for (int c = 0; c < 2; c++) NEAR(J[r][c] * 1000.0f, g[k].J[r][c], 2e-2);
        gp_fb_polar p;
        CHECK(gp_fb_polar_state((float)g[k].p1, (float)g[k].p2, 0.3f, -0.2f, &p));
        NEAR(p.L, g[k].L, 2e-6);
        NEAR(p.th, (double)g[k].lean_deg * 0.0174532925, 2e-5);
        /* virtual work: tau . dphi = F . dE for any small motion */
        float tau[2];
        gp_fb_vmc(&p, 100.0f, 5.0f, tau);
        const float dphi[2] = {1e-3f, -2e-3f};
        const float dEx = p.J[0][0] * dphi[0] + p.J[0][1] * dphi[1], dEz = p.J[1][0] * dphi[0] + p.J[1][1] * dphi[1];
        const float s = sinf(p.th), c = cosf(p.th);
        const float fx = 100.0f * s + 5.0f / p.L * c, fz = -100.0f * c + 5.0f / p.L * s;
        NEAR(tau[0] * dphi[0] + tau[1] * dphi[1], fx * dEx + fz * dEz, 1e-5);
    }
    /* standing still with a pure push down the leg: both motors must turn their links down (towards -z) */
    gp_fb_polar p;
    gp_fb_polar_state(-0.88798f, -2.25361f, 0, 0, &p);
    float tau[2];
    gp_fb_vmc(&p, 150.0f, 0.0f, tau);
    CHECK(tau[0] < 0.0f && tau[1] > 0.0f); /* front turns phi1 down, rear turns phi2 up (its mirror) */
}

/* ------------------------------------------------------------------------------------------- RS-04 */
static void test_rs04(void)
{
    gp_can_frame f;
    /* (Python) rs04.pack_mit(3, 0.5, -2.0, 0.0, 1.5, 12.34) -> 0x18d2903, 85176eee000003d7 */
    gp_rs04_mit(3, 0.5f, -2.0f, 0.0f, 1.5f, 12.34f, &f);
    NEAR((double)((f.id >> 8) & 0xFFFF), 0x8d29, 1);
    CHECK((f.id & 0xFF) == 3 && (f.id >> 24) == 1 && f.ext && f.len == 8);
    const uint8_t want[8] = {0x85, 0x17, 0x6e, 0xee, 0x00, 0x00, 0x03, 0xd7};
    for (int k = 0; k < 8; k += 2) NEAR((f.data[k] << 8) | f.data[k + 1], (want[k] << 8) | want[k + 1], 1);
    /* (Python) encode_feedback(2, 0xFD, 2, 0, -1.25, 3.5, -7.5, 31.4) -> 0x28002fd, 73449ddd77ff013a */
    gp_can_frame r = {0x28002FDu, 8, 1, {0x73, 0x44, 0x9d, 0xdd, 0x77, 0xff, 0x01, 0x3a}};
    gp_rs04_msg m;
    CHECK(gp_rs04_parse(&r, &m) && m.kind == GP_RS04_FEEDBACK);
    CHECK(m.fb.motor == 2 && m.fb.mode == 2 && m.fb.faults == 0);
    NEAR(m.fb.p, -1.25, 4e-4);
    NEAR(m.fb.v, 3.5, 5e-4);
    NEAR(m.fb.t, -7.5, 4e-3);
    NEAR(m.fb.temp_c, 31.4, 1e-4);
    /* (Python) encode_param_reply(1, 0xFD, 0x700B, 60.0) -> 0x110001fd, 0b70000000007042 */
    gp_can_frame q = {0x110001FDu, 8, 1, {0x0b, 0x70, 0, 0, 0, 0, 0x70, 0x42}};
    CHECK(gp_rs04_parse(&q, &m) && m.kind == GP_RS04_READ && m.param.ok && m.param.index == 0x700B && m.param.motor == 1);
    NEAR(gp_rs04_param_f32(&m.param), 60.0, 0);
    /* (Python) pack_write(1, 'canTimeout', 2000) -> 0x1200fd01, 28700000d0070000; limit_torque 60 -> 0b70000000007042 */
    gp_rs04_write_u32(1, GP_RS04_P_CAN_TIMEOUT, 2000, &f);
    const uint8_t w1[8] = {0x28, 0x70, 0, 0, 0xd0, 0x07, 0, 0};
    CHECK(f.id == 0x1200FD01u && memcmp(f.data, w1, 8) == 0);
    gp_rs04_write_f32(1, GP_RS04_P_LIMIT_TORQUE, 60.0f, &f);
    const uint8_t w2[8] = {0x0b, 0x70, 0, 0, 0, 0, 0x70, 0x42};
    CHECK(f.id == 0x1200FD01u && memcmp(f.data, w2, 8) == 0);
    /* the manual's scaling: the ends map exactly, NaN never reaches a motor */
    CHECK(gp_rs04_f2u(-120.0f, -120.0f, 120.0f) == 0 && gp_rs04_f2u(500.0f, -120.0f, 120.0f) == 0xFFFF);
    NEAR(gp_rs04_u2f(gp_rs04_f2u(NAN, -120.0f, 120.0f), -120.0f, 120.0f), 0.0, 4e-3);
    /* a host's request (addressed to a motor) is not taken for a reply */
    gp_rs04_read(1, GP_RS04_P_VBUS, &f);
    CHECK(!gp_rs04_parse(&f, &m));
}

/* ------------------------------------------------------------------------------------------- VESC, Jetson, VN-100, INA228 */
static void test_vesc(void)
{
    gp_can_frame f;
    gp_vesc_set_current(10, -12.5f, &f);
    CHECK(f.ext && f.id == 0x10A && f.len == 4);
    const int32_t v = (int32_t)(((uint32_t)f.data[0] << 24) | ((uint32_t)f.data[1] << 16) | (f.data[2] << 8) | f.data[3]);
    CHECK(v == -12500);
    gp_can_frame s = {(9u << 8) | 11u, 8, 1, {0xFF, 0xFF, 0xF0, 0x60, 0x00, 0x7B, 0xFE, 0x0C}};
    uint8_t id, cmd;
    gp_vesc_status st;
    memset(&st, 0, sizeof st);
    CHECK(gp_vesc_parse(&s, &id, &cmd, &st) && id == 11 && cmd == 9);
    CHECK(st.erpm == -4000);
    NEAR(st.current, 12.3, 1e-5);
    NEAR(st.duty, -0.5, 1e-6);
}

static void test_jetson(void)
{
    gp_jet_setpoint a = {0.75f, -0.4f, 0.6f, 0.2f, true, true, 2, 9, 77}, b;
    gp_can_frame f;
    gp_jet_encode_setpoint(&a, &f);
    CHECK(f.id == 0x110 && !f.ext && f.len == 8);
    CHECK(gp_jet_decode_setpoint(&f, &b));
    NEAR(b.speed, 0.75, 1e-6);
    NEAR(b.yaw_rate, -0.4, 1e-6);
    NEAR(b.height, 0.6, 1e-6);
    NEAR(b.lean, 0.2, 1e-6);
    CHECK(b.run && b.people_near && b.jump_seq == 2 && b.jump_height == 9 && b.seq == 77);
}

static void test_vn100(void)
{
    gp_vn100_sample s = {12.5f, -3.25f, 1.5f, 0.01f, -0.2f, 0.3f}, o;
    uint8_t pk[GP_VN100_PACKET];
    gp_vn100_encode(&s, pk);
    CHECK(gp_vn100_crc(pk + 1, GP_VN100_PACKET - 1) == 0);
    gp_vn100_parser p;
    gp_vn100_init(&p);
    const uint8_t junk[] = {'$', 'V', 'N', 0xFA, 0x01, 0x00, 0xFA};
    CHECK(gp_vn100_feed(&p, junk, sizeof junk, &o) == 0);
    int got = 0;
    for (int k = 0; k < (int)GP_VN100_PACKET; k++) got += gp_vn100_feed(&p, pk + k, 1, &o);
    CHECK(got == 1);
    NEAR(o.pitch, -3.25f, 0);
    NEAR(o.gy, -0.2f, 0);
    pk[10] ^= 0x40; /* a bit error */
    CHECK(gp_vn100_feed(&p, pk, sizeof pk, &o) == 0 && p.crc_errors == 1);
    /* a correct packet right after a bad one */
    gp_vn100_encode(&s, pk);
    CHECK(gp_vn100_feed(&p, pk, sizeof pk, &o) == 1);
    char cmd[64];
    const size_t n = gp_vn100_command("VNWRG,75,3,1,01,0028", cmd, sizeof cmd);
    CHECK(n > 0 && cmd[0] == '$' && cmd[n - 5] == '*');
    uint8_t x = 0;
    for (const char *c = cmd + 1; *c != '*'; c++) x ^= (uint8_t)*c;
    char hx[3];
    snprintf(hx, sizeof hx, "%02X", x);
    CHECK(cmd[n - 4] == hx[0] && cmd[n - 3] == hx[1]);
}

static void test_ina228(void)
{
    gp_ina228_cfg c;
    gp_ina228_setup(&c, GP_SHUNT_FUSE_BOARD_OHM);
    CHECK(c.adcrange == 0 && c.shunt_cal == 4096);
    NEAR(c.current_lsb, 312.5e-6, 1e-9);
    uint8_t v[3], i[3];
    gp_ina228_encode_vbus(41.0f, v);
    NEAR(gp_ina228_vbus(v), 41.0, 2e-4);
    gp_ina228_encode_current(&c, -80.0f, i);
    NEAR(gp_ina228_current(&c, i), -80.0, 4e-4);
    /* the datasheet's own example of the register: VBUS 0x3D0900 << 4 is 48.828 V... here 0x00F424 -> 1.2207 V */
    const uint8_t vb[3] = {0x0F, 0x42, 0x40};
    NEAR(gp_ina228_vbus(vb), 62500 * 195.3125e-6, 1e-6);
    gp_ina228_setup(&c, GP_SHUNT_BLUE_SEA_OHM);
    CHECK(c.adcrange == 1 && c.shunt_cal == 4096);
    const uint8_t t[2] = {0x0C, 0x80}; /* 3200 x 7.8125 mC = 25 C */
    NEAR(gp_ina228_dietemp(t), 25.0, 1e-6);
}

/* ------------------------------------------------------------------------------------------- the law */
static void stance_sense(gp_sense *s, float L)
{
    memset(s, 0, sizeof *s);
    float phi[2];
    gp_fb_stance(L, 0.0f, phi);
    for (int side = 0; side < 2; side++) {
        s->phi[side][0] = phi[0];
        s->phi[side][1] = phi[1];
    }
    s->vbus = GP_PACK_NOMINAL_V;
}

static void test_control(void)
{
    NEAR(gp_clip_motor(100.0f, 0.0f, 120.0f, 21.0f, 60.0f), 60.0, 0);
    NEAR(gp_clip_motor(50.0f, 10.5f, 120.0f, 21.0f, 0.0f), 50.0, 0);       /* 60 N m left at half speed */
    NEAR(gp_clip_motor(100.0f, 10.5f, 120.0f, 21.0f, 0.0f), 60.0, 1e-5);
    NEAR(gp_clip_motor(-100.0f, 10.5f, 120.0f, 21.0f, 0.0f), -100.0, 0);   /* braking: the full peak */
    float K[4];
    gp_ctl_lqr_gains(0.6f, K);
    CHECK(K[1] < 0.0f && K[3] < 0.0f); /* theta > 0 (falling forward) drives forward */

    gp_config cfg;
    gp_config_default(&cfg, GP_PROFILE_ROBOT);
    gp_ctl c;
    gp_ctl_init(&c, &cfg.ctl);
    const float L = gp_ctl_height_m(0.6f);
    gp_ctl_reset(&c, 0.6f);
    gp_sense s;
    stance_sense(&s, L);
    float th, thd;
    CHECK(gp_ctl_theta(&s, &th, &thd));
    s.pitch = -th; /* tilted so the centre of mass is over the axle: theta 0 */
    CHECK(gp_ctl_theta(&s, &th, &thd));
    NEAR(th, 0.0, 1e-6);
    gp_cmd cmd = {0.6f, 0, 0, 0, 0, 0};
    gp_leg_cmd leg[2] = {{GP_LEG_TRACK, false, 0, 0, 1}, {GP_LEG_TRACK, false, 0, 0, 1}};
    gp_ctl_out o;
    gp_ctl_step(&c, &s, &cmd, leg, true, &o);
    NEAR(o.u, 0.0, 1e-3);
    NEAR(o.L_cmd[0], L, 1e-6);
    /* standing on the length it wants, each leg holds the feed-forward: the force through the Jacobian */
    float tau[2];
    gp_fb_vmc(&o.leg[0], cfg.ctl.leg_ff_n, cfg.ctl.legs.kp_th * (0.0f - o.leg[0].th), tau);
    NEAR(o.tau[0][0], tau[0], 1e-3);
    NEAR(o.tau[0][1], tau[1], 1e-3);
    /* nose down by 0.05 rad: the centre of mass goes ahead of the axle, both wheels drive forward */
    s.pitch += 0.05f;
    gp_ctl_reset(&c, 0.6f);
    gp_ctl_step(&c, &s, &cmd, leg, true, &o);
    NEAR(o.theta, 0.05, 1e-5);
    CHECK(o.u > 0.0f && o.wheel[0] > 0.0f && o.wheel[1] > 0.0f);
    /* the body pitching nose down at 1 rad/s: theta_dot follows the gyro */
    s.pitch_rate = 1.0f;
    gp_ctl_step(&c, &s, &cmd, leg, true, &o);
    NEAR(o.theta_dot, 1.0, 1e-5);
    /* a turn left: the right wheel more forward */
    s.pitch_rate = 0.0f;
    s.pitch -= 0.05f;
    cmd.yaw_rate = 0.5f;
    gp_ctl_step(&c, &s, &cmd, leg, true, &o);
    CHECK(o.wheel[1] > o.wheel[0]);
    /* the wheel's ground speed: the wheel turning at w relative to a still leg rolls at r w */
    cmd.yaw_rate = 0.0f;
    s.wheel_w[0] = s.wheel_w[1] = 2.0f;
    gp_ctl_step(&c, &s, &cmd, leg, true, &o);
    NEAR(o.v, 2.0 * (double)GP_WHEEL_R_M, 1e-6);
    /* roll, left side up: the left leg shortens */
    memset(s.wheel_w, 0, sizeof s.wheel_w);
    s.roll = 0.1f;
    for (int k = 0; k < 100; k++) gp_ctl_step(&c, &s, &cmd, leg, true, &o);
    CHECK(o.L_cmd[0] < o.L_cmd[1]);
}


/* ------------------------------------------------------------------------------------------- the leg guards */
static void test_guard(void)
{
    gp_torque_limits t;
    gp_guard_limits(GP_BUILD_ROBOT, &t);
    NEAR(t.everyday_nm, GP_LIM_ROBOT_EVERYDAY_NM, 0);
    NEAR(t.motor_nm, t.peak_nm, 0); /* the motors' own limit lets the push through, and nothing more */
    CHECK(t.peak_nm >= t.everyday_nm && t.peak_nm <= GP_LEG_PEAK_NM && t.rms_nm < t.everyday_nm);
    gp_guard_limits(GP_BUILD_PLA_BENCH, &t);
    NEAR(t.everyday_nm, 12.0, 0); /* docs/motor-day.md: the PLA cap */
    NEAR(t.motor_nm, 12.0, 0);
    gp_guard_limits(7, &t); /* an unknown build is the weakest */
    CHECK(t.build == GP_BUILD_PLA_BENCH && t.motor_nm == 12.0f);
    NEAR(GP_LIM_PEAK_MAX_S, GP_JUMP_PUSH_MAX_S, 0); /* the peak lasts no longer than the push it is for */
    /* robot and rig profiles: the robot's leg always; the rig the PLA bench leg unless built for the robot's */
    gp_config cfg;
    gp_config_default(&cfg, GP_PROFILE_ROBOT);
    CHECK(cfg.lim.build == GP_BUILD_ROBOT && cfg.ctl.cap_nm == cfg.lim.everyday_nm);
    gp_config_default(&cfg, GP_PROFILE_RIG);
    CHECK(cfg.lim.build == GP_RIG_BUILD);

    /* (Python) sim/leg_limits.py soft_stop on the front motor (stops -97 / +3 deg) */
    const float lo = GP_FB_STOP_FRONT_IN, hi = GP_FB_STOP_FRONT_OUT, d1 = 0.0174532925f;
    const struct { float T, tau, phi, w, want; } g[] = {
        {61.0f, 10.0f, 0.034907f, 0.0f, 0.0f},        /* 1 deg from the knee-out stop: nothing more into it */
        {61.0f, -10.0f, 0.034907f, 0.0f, -10.0f},     /* away from it: allowed */
        {61.0f, 10.0f, -0.034907f, 0.0f, 10.0f},      /* 5 deg away: outside the margin */
        {61.0f, 10.0f, -0.034907f, 14.0f, 10.0f},     /* 14 rad/s at 5 deg: the robot's stop takes it */
        {12.0f, 10.0f, -0.034907f, 14.0f, -12.0f},    /* the PLA leg's does not: brake at its cap */
        {12.0f, 5.0f, -1.640609f, -15.0f, 12.0f},     /* towards the knee-in stop, 3 deg off */
        {12.0f, 5.0f, -0.698132f, 15.0f, 5.0f},       /* mid-range: untouched */
        {61.0f, -30.0f, 0.043633f, 13.0f, -30.0f},    /* already braking harder than the guard would */
    };
    for (unsigned k = 0; k < sizeof g / sizeof g[0]; k++) {
        NEAR(gp_guard_soft_stop(g[k].tau, g[k].phi, g[k].w, lo, hi, g[k].T), g[k].want, 1e-4);
    }
    NEAR(gp_guard_approach(0.0f, 61.0f), 12.504622, 1e-4);
    NEAR(gp_guard_approach(0.05f, 61.0f), 19.385304, 1e-4);
    /* the rear motor's stops run -183 .. -83 deg: at its knee-in stop (-83) no more torque towards it */
    NEAR(gp_guard_soft_stop(8.0f, GP_FB_STOP_REAR_IN - d1, 0.0f, GP_FB_STOP_REAR_OUT, GP_FB_STOP_REAR_IN, 61.0f), 0.0, 0);

    /* (Python) the commanded window by lean (sim/leg_limits.py window_at) */
    const struct { float lean, lo, hi; } wv[] = {{-0.35f, 0.207f, 0.343f}, {-0.12f, 0.1366f, 0.3744f}, {0.0f, 0.107f, 0.383f},
                                                 {0.33f, 0.2006f, 0.3466f}, {0.6f, 0.258f, 0.317f}, {-0.6f, 0.258f, 0.317f}};
    for (unsigned k = 0; k < sizeof wv / sizeof wv[0]; k++) {
        float a, b;
        gp_guard_window(wv[k].lean, &a, &b);
        NEAR(a, wv[k].lo, 1e-4);
        NEAR(b, wv[k].hi, 1e-4);
    }
    /* every height the controller has, upright, is inside the window; full height leaning back 0.35 rad is not */
    NEAR(gp_guard_clamp_L(GP_H_MAX_M, 0.0f), GP_H_MAX_M, 0);
    NEAR(gp_guard_clamp_L(GP_H_MIN_M, 0.0f), GP_H_MIN_M, 0);
    NEAR(gp_guard_clamp_L(GP_SIT_L_ROBOT_M, 0.0f), GP_SIT_L_ROBOT_M, 0);
    NEAR(gp_guard_clamp_L(GP_JUMP_CROUCH_L_M, 0.0f), GP_JUMP_CROUCH_L_M, 0);
    NEAR(gp_guard_clamp_L(GP_H_MAX_M, -0.35f), 0.343, 1e-4);
    /* every window pose is one the five-bar reaches inside its stops */
    for (int k = 0; k <= 40; k++) {
        const float lean = -0.5f + 0.025f * (float)k;
        float a, b, phi[2];
        gp_guard_window(lean, &a, &b);
        for (int e = 0; e < 2; e++) {
            CHECK(gp_fb_stance(e ? b : a, lean, phi));
            CHECK(phi[0] <= GP_FB_STOP_FRONT_OUT && phi[0] >= GP_FB_STOP_FRONT_IN);
            CHECK(phi[1] <= GP_FB_STOP_REAR_IN && phi[1] >= GP_FB_STOP_REAR_OUT);
        }
    }
    /* the measured-angle window: the sleeve's squeeze at the fault torque and 2 deg */
    CHECK(gp_guard_angle_ok(hi + 0.17f, lo, hi));
    CHECK(!gp_guard_angle_ok(hi + 0.18f, lo, hi));
    CHECK(!gp_guard_angle_ok(lo - 0.18f, lo, hi));
    /* rms: a held 30 N m reaches 30 after a few time constants; zero decays */
    float ms = 0.0f, r = 0.0f;
    for (int k = 0; k < (int)(5.0f * GP_LIM_RMS_TAU_S / GP_DT); k++) r = gp_guard_rms(&ms, 30.0f, GP_DT);
    NEAR(r, 30.0, 0.15);

    /* the law: full height leaning back as far as it can is clamped to the window, and the soft stop shows */
    gp_config_default(&cfg, GP_PROFILE_ROBOT);
    gp_ctl c;
    gp_ctl_init(&c, &cfg.ctl);
    gp_ctl_reset(&c, 1.0f);
    gp_sense s;
    stance_sense(&s, 0.34f);
    gp_cmd cmd = {1.0f, 0, 0, 0.35f, 0, 0};
    gp_leg_cmd leg[2] = {{GP_LEG_TRACK, false, 0, 0, 1}, {GP_LEG_TRACK, false, 0, 0, 1}};
    gp_ctl_out o;
    for (int k = 0; k < 1000; k++) gp_ctl_step(&c, &s, &cmd, leg, false, &o);
    CHECK(o.windowed == 3u);
    float wl, wh;
    gp_guard_window(-0.35f, &wl, &wh);
    NEAR(o.L_cmd[0], wh, 1e-4);
    /* a commanded push into the knee-out stops (the shortest leg) at the stop: no torque into them */
    stance_sense(&s, 0.1016f);
    leg[0] = leg[1] = (gp_leg_cmd){GP_LEG_FORCE, false, 0, -2000.0f, 0};
    gp_ctl_step(&c, &s, &cmd, leg, false, &o);
    CHECK(o.guarded != 0u);
    CHECK(o.tau[0][0] <= 1e-6f && o.tau[0][1] >= -1e-6f); /* front: + is towards its knee-out stop; rear: - */
}

/* ------------------------------------------------------------------------------------------- the supervisor */
static gp_app A;
static uint32_t now;
static uint8_t seq, jump_seq;
static struct { bool run, people, link; float vbus, ibus; uint8_t jump_h; bool stop; } env;

static void tick(int n)
{
    for (int k = 0; k < n; k++) {
        now += 1000;
        if (env.link && now % 10000 == 0) {
            gp_jet_setpoint sp = {0, 0, 0.6f, 0, env.run, env.people, jump_seq, env.jump_h, ++seq};
            gp_can_frame f;
            gp_jet_encode_setpoint(&sp, &f);
            gp_app_can_rx(&A, GP_BUS_C, &f, now);
        }
        if (now % 2000 == 0) {
            uint8_t v[3], i[3];
            gp_ina228_encode_vbus(env.vbus, v);
            gp_ina228_encode_current(&A.ina, -env.ibus, i);
            gp_app_ina228(&A, v, i, now);
        }
        gp_inputs in = {env.stop};
        gp_outputs out;
        gp_app_tick(&A, now, &in, &out);
        tp_answer(&A, now);
    }
}

static void boot_and_stand(float vbus)
{
    memset(&TP, 0, sizeof TP);
    float phi[2];
    gp_fb_stance(0.30f, 0.0f, phi);
    gp_config cfg;
    gp_config_default(&cfg, GP_PROFILE_RIG);
    for (int i = 0; i < 4; i++) {
        cfg.motor[i].phi_zero = 0.0f;
        TP.angle[i] = phi[i % 2];
    }
    now = 0;
    seq = 0;
    jump_seq = 0;
    env.run = false;
    env.people = false;
    env.link = true;
    env.vbus = vbus;
    env.ibus = 0.0f;
    env.jump_h = 15;
    env.stop = true;
    gp_app_init(&A, &cfg, now);
    tick(100);
    CHECK(A.mode == GP_MODE_IDLE);
    env.run = true;
    tick(50);
    CHECK(A.mode == GP_MODE_RUN && A.mcu_run);
}

static void test_supervisor(void)
{
    gp_snapshot s;
    /* boot: every motor configured and read back; no arm without the radio's run */
    boot_and_stand(36.0f);
    gp_app_snapshot(&A, &s);
    CHECK(s.boot_mask == 0xF);
    env.stop = false;
    tick(1);
    CHECK(A.mode == GP_MODE_RUN); /* one low sample is a glitch */
    tick(1);
    CHECK(A.mode == GP_MODE_SIT && A.reason == GP_R_STOP && !A.mcu_run); /* 2 ms: the stop, MCU_RUN open at once */
    tick(650);
    CHECK(A.mode == GP_MODE_IDLE);
    env.stop = true;
    tick(300);
    CHECK(A.mode == GP_MODE_IDLE); /* the stand needs a new RUN from the Jetson */
    env.run = false;
    tick(30);
    env.run = true;
    tick(50);
    CHECK(A.mode == GP_MODE_RUN);

    /* the jump gate (D65): 34.0 V resting and up; the push's bus current limit s(V) x 72 A, s from the 31 V floor */
    NEAR(gp_jump_scale(33.99f), 0.0, 0);
    NEAR(gp_jump_scale(34.0f), (34.0 - 31.0) / 7.2, 1e-5);
    NEAR(gp_jump_scale(38.2f), 1.0, 1e-6);
    NEAR(gp_jump_scale(41.0f), 1.0, 0);
    boot_and_stand(33.9f);
    jump_seq = 1;
    tick(20);
    CHECK(A.mode == GP_MODE_RUN && A.jump_refusal == GP_J_VOLTAGE && A.jumps_refused == 1);
    boot_and_stand(34.1f);
    jump_seq = 1;
    tick(20);
    CHECK(A.mode == GP_MODE_JUMP && A.jumps == 1);
    NEAR(A.jump_scale, (34.1 - 31.0) / 7.2, 1e-4);
    NEAR(A.push_ilimit, (34.1 - 31.0) / 7.2 * 72.0, 1e-3);
    NEAR(A.jump_v_target, GP_JUMP_V_MAX, 1e-6);
    /* people near: no jump, then sit after 2 s */
    boot_and_stand(36.0f);
    env.people = true;
    tick(20);
    jump_seq = 2;
    tick(20);
    CHECK(A.mode == GP_MODE_RUN && A.jump_refusal == GP_J_PEOPLE);
    tick(1950);
    CHECK(A.mode == GP_MODE_RUN);
    tick(50);
    CHECK(A.mode == GP_MODE_SIT && A.reason == GP_R_PEOPLE);

    /* UVLO (D65): warn under 35.0 V, sit under 32.0 V (resting, filtered over 1 s) */
    boot_and_stand(35.1f);
    tick(3000);
    CHECK(!A.uvlo_warn);
    env.vbus = 34.9f;
    tick(5000);
    CHECK(A.uvlo_warn && A.mode == GP_MODE_RUN);
    env.vbus = 31.9f;
    float before = A.vrest;
    while (A.mode == GP_MODE_RUN && now < 60000000u) {
        before = A.vrest;
        tick(1);
    }
    CHECK(A.mode == GP_MODE_SIT && A.reason == GP_R_UVLO);
    CHECK(before >= 32.0f && A.vrest < 32.0f);
    CHECK(!A.cutoff);
    /* the sag is taken back out: 30 A at 31.0 V on the wire is 34.0 V resting; under load it is over the cut-off */
    boot_and_stand(36.0f);
    env.vbus = 31.0f;
    env.ibus = 30.0f;
    tick(6000);
    NEAR(A.vrest, 31.0 + 30.0 * (double)GP_R_PACK_OHM, 0.02);
    CHECK(A.mode == GP_MODE_RUN && !A.cutoff);

    /* no arming under 33.0 V resting (3.3 V a cell) */
    boot_and_stand(36.0f);
    env.run = false;
    env.vbus = 32.9f;
    tick(4000); /* sat (the Jetson's RUN 0), the resting voltage down to 32.9 */
    CHECK(A.mode == GP_MODE_IDLE && !A.uvlo_sat);
    env.run = true;
    tick(200);
    CHECK(A.mode == GP_MODE_IDLE);
    env.vbus = 33.1f;
    env.run = false;
    tick(3000);
    env.run = true;
    tick(50);
    CHECK(A.mode == GP_MODE_RUN);

    /* the cut-off (D65): 30.0 V a cell under load, 0.1 s filter; a 6 ms dip to 25 V does not trip it */
    boot_and_stand(36.0f);
    env.vbus = 25.0f;
    tick(6);
    env.vbus = 36.0f;
    tick(500);
    CHECK(A.mode == GP_MODE_RUN && !A.cutoff);
    env.vbus = 29.9f;
    env.ibus = 20.0f; /* 31.9 V resting: under load is what counts */
    tick(1000);
    CHECK(A.cutoff && A.reason == GP_R_CUTOFF && (A.mode == GP_MODE_SIT || A.mode == GP_MODE_SETTLE || A.mode == GP_MODE_IDLE));
    tick(2000);
    CHECK(A.mode == GP_MODE_IDLE && !A.mcu_run);
    env.vbus = 41.0f; /* a fresh pack on the wire does not clear it: only a power cycle */
    env.ibus = 0.0f;
    env.run = false;
    tick(3000);
    env.run = true;
    tick(200);
    CHECK(A.mode == GP_MODE_IDLE && A.cutoff);
    jump_seq = 3;
    tick(20);
    CHECK(A.jump_refusal == GP_J_NOT_RUNNING);
    boot_and_stand(36.0f); /* gp_app_init: the power cycle */
    CHECK(!A.cutoff);

    /* the bus current limit (D65, the dock adapters' 30 A): 80 A for at most 0.5 s, else 30 A; one factor on every
     * motor's command */
    boot_and_stand(36.0f);
    env.ibus = 29.0f;
    tick(5000);
    CHECK(A.bus_scale == 1.0f && A.ilimit == GP_BUS_I_PEAK_A); /* 29 A held: under the continuous limit */
    env.ibus = 5.0f;
    tick(4000);
    env.ibus = 50.0f; /* over the continuous, under the peak (the average stays under 30 A: 23 A at 0.5 s) */
    tick(400);
    CHECK(A.bus_scale == 1.0f && A.ilimit == GP_BUS_I_PEAK_A);
    tick(200);
    CHECK(A.ilimit == GP_BUS_I_CONT_A && A.bus_scale < 1.0f && A.bus_scale >= GP_BUS_SCALE_MIN);
    CHECK(A.mode == GP_MODE_RUN); /* scaled, not tripped */
    env.ibus = 10.0f;
    tick(1500);
    CHECK(A.bus_scale == 1.0f && A.ilimit == GP_BUS_I_PEAK_A);
    env.ibus = 100.0f; /* over the peak: down by 80/100 at once */
    tick(2);
    NEAR(A.bus_scale, 0.8, 1e-5);
    tick(100);
    NEAR(A.bus_scale, GP_BUS_SCALE_MIN, 0); /* this test's current does not follow the factor: it sits at its floor */
    env.ibus = 20.0f;
    tick(2000);
    CHECK(A.bus_scale == 1.0f);
    env.ibus = 35.0f; /* the 1 s average over 30 A takes the peak away even inside the 0.5 s */
    tick(1500);
    CHECK(A.ilimit == GP_BUS_I_CONT_A);
    /* the regen clamp (D65): the charging current allowed falls from 15 A at 41.5 V to 0 at 42.5 V on the bus; over
     * it the braking factor falls 5 /(A s) of excess, and recovers at 10 /s */
    boot_and_stand(40.0f);
    env.vbus = 42.0f; /* 7.5 A allowed */
    env.ibus = -5.0f;
    tick(20);
    NEAR(A.regen_scale, 1.0, 0);
    env.ibus = -12.0f; /* 4.5 A over: 0.045 a sample */
    tick(10);
    NEAR(A.regen_scale, 1.0 - 5.0 * 0.045, 1e-4);
    env.vbus = 42.6f; /* none allowed: 52 A takes it to 0 in two samples */
    env.ibus = -52.0f;
    tick(4);
    NEAR(A.regen_scale, 0.0, 0);
    env.vbus = 41.4f; /* under 41.5 V: no limit, up at 10 a second */
    env.ibus = -30.0f;
    tick(50);
    NEAR(A.regen_scale, 0.5, 0.02);
    tick(60);
    NEAR(A.regen_scale, 1.0, 0);
    env.vbus = 43.0f; /* high but discharging (an over-full pack holding the legs): not regeneration */
    env.ibus = 5.0f;
    tick(10);
    NEAR(A.regen_scale, 1.0, 0);
    CHECK(A.mode == GP_MODE_RUN && !A.overcharge);
    /* the over-charge latch: 44.0 V on the bus (20 ms filter); a 6 ms spike to 46 V is not one */
    boot_and_stand(40.0f);
    env.vbus = 46.0f;
    tick(6);
    env.vbus = 40.0f;
    tick(200);
    CHECK(A.mode == GP_MODE_RUN && !A.overcharge);
    env.vbus = 44.5f;
    tick(100);
    CHECK(A.overcharge && A.reason == GP_R_OVERCHARGE);
    tick(2000);
    CHECK(A.mode == GP_MODE_IDLE && !A.mcu_run);
    env.vbus = 40.0f; /* only a power cycle clears it */
    env.run = false;
    tick(3000);
    env.run = true;
    tick(200);
    CHECK(A.mode == GP_MODE_IDLE && A.overcharge);
    /* no arming over 42.0 V resting (an over-full or wrong pack) */
    boot_and_stand(40.0f);
    env.run = false;
    env.vbus = 42.1f;
    tick(4000);
    env.run = true;
    tick(200);
    CHECK(A.mode == GP_MODE_IDLE && !A.overcharge);
    env.vbus = 41.9f;
    env.run = false;
    tick(4000);
    env.run = true;
    tick(50);
    CHECK(A.mode == GP_MODE_RUN);
    {
        gp_app_snapshot(&A, &s);
        NEAR(s.bus_scale, A.bus_scale, 0);
        CHECK(A.mode == GP_MODE_RUN);
    }

    /* the Jetson's heartbeat: 200 ms lost, 2 s holding, then sit */
    boot_and_stand(36.0f);
    env.link = false;
    tick(2150);
    CHECK(A.mode == GP_MODE_RUN);
    tick(100);
    CHECK(A.mode == GP_MODE_SIT && A.reason == GP_R_LINK);

    /* the leg build's torque (docs/leg-protection.md): the rig profile writes the PLA bench leg's limit_torque into every
     * motor and reads it back; the cap is the every-day one outside a jump's push and the peak inside it */
    boot_and_stand(41.0f);
    {
        bool found = false;
        for (int p = 0; p < TP_PARAMS; p++) {
            if (TP.pidx[0][p] == GP_RS04_P_LIMIT_TORQUE) {
                float v;
                memcpy(&v, TP.pval[0][p], 4);
                NEAR(v, A.cfg.lim.motor_nm, 0);
                found = true;
            }
        }
        CHECK(found);
        CHECK(A.cfg.lim.build == GP_RIG_BUILD);
    }
    /* a rig built for the robot's leg: the same, at the robot's numbers; a jump's push runs at the peak only */
    {
        gp_config cfg = A.cfg;
        gp_guard_limits(GP_BUILD_ROBOT, &cfg.lim);
        cfg.ctl.cap_nm = cfg.ctl.everyday_nm = cfg.lim.everyday_nm;
        memset(&TP, 0, sizeof TP);
        float phi[2];
        gp_fb_stance(0.30f, 0.0f, phi);
        for (int i = 0; i < 4; i++) TP.angle[i] = phi[i % 2];
        now = 0; seq = 0; jump_seq = 0; env.run = false;
        gp_app_init(&A, &cfg, now);
        tick(100);
        env.run = true;
        tick(50);
        CHECK(A.mode == GP_MODE_RUN);
        NEAR(A.cap_now, GP_LIM_ROBOT_EVERYDAY_NM, 0);
        jump_seq = 1;
        float cap_push = 0.0f, cap_other = 0.0f;
        /* the motors' angles are fixed here: the push ends on time and the leg stays in the air phase */
        for (int k = 0; k < 1500; k++) {
            tick(1);
            if (A.jump_phase == GP_JP_PUSH) cap_push = fmaxf(cap_push, A.cap_now);
            else cap_other = fmaxf(cap_other, A.cap_now);
        }
        NEAR(cap_push, GP_LIM_ROBOT_PEAK_NM, 0);
        NEAR(cap_other, GP_LIM_ROBOT_EVERYDAY_NM, 0);
        CHECK(A.mode == GP_MODE_JUMP && A.jump_phase == GP_JP_AIR && A.jumps == 1);
        /* the next jump waits GP_JUMP_GAP_S from the last one's end (as the recovery records it) */
        gp_app_init(&A, &cfg, now); /* a power cycle: the fixed angles never land */
        env.run = false;
        tick(100);
        env.run = true;
        tick(50);
        CHECK(A.mode == GP_MODE_RUN);
        A.jumped = true;
        A.t_jump_end = now;
        jump_seq = 2;
        tick(20);
        CHECK(A.mode == GP_MODE_RUN && A.jump_refusal == GP_J_COOLDOWN);
        tick((int)(GP_JUMP_GAP_S * 1000.0f));
        jump_seq = 3;
        tick(20);
        CHECK(A.mode == GP_MODE_JUMP && A.jumps == 1); /* counted since the power cycle */
    }
    /* a motor's rms torque: over 0.8 of its limit no jump; over the limit the cap is the rms limit until it falls
     * under 0.9 of it */
    boot_and_stand(41.0f);
    A.tau_ms[1] = (0.85f * A.cfg.lim.rms_nm) * (0.85f * A.cfg.lim.rms_nm);
    jump_seq = 1;
    tick(20);
    CHECK(A.mode == GP_MODE_RUN && A.jump_refusal == GP_J_HOT);
    A.tau_ms[1] = (1.1f * A.cfg.lim.rms_nm) * (1.1f * A.cfg.lim.rms_nm);
    tick(2); /* the cap is chosen on the rms the tick before */
    CHECK(A.hot);
    NEAR(A.cap_now, fminf(A.cfg.lim.everyday_nm, A.cfg.lim.rms_nm), 0);
    A.tau_ms[1] = 0.0f;
    tick(2);
    CHECK(!A.hot);
    NEAR(A.cap_now, A.cfg.lim.everyday_nm, 0);
    /* a motor reporting over 70 C: no jump; over 80 C: sit */
    boot_and_stand(36.0f);
    TP.temp_c[3] = 75.0f;
    tick(5);
    jump_seq = 1;
    tick(20);
    CHECK(A.mode == GP_MODE_RUN && A.jump_refusal == GP_J_HOT);
    TP.temp_c[3] = 85.0f;
    tick(5);
    CHECK(A.mode == GP_MODE_SIT && A.reason == GP_R_MOTOR_HOT);
    /* a motor measured well past its stop (a broken post, a slipped zero): limp */
    boot_and_stand(36.0f);
    TP.angle[0] = GP_FB_STOP_FRONT_IN - GP_LIM_ANGLE_WINDOW_RAD - 0.02f;
    tick(3);
    CHECK(A.mode == GP_MODE_LIMP && (A.reason == GP_R_JOINT_RANGE || A.reason == GP_R_LEG_WINDOW));
    boot_and_stand(36.0f);
    TP.angle[0] = GP_FB_STOP_FRONT_IN - 0.5f * GP_LIM_ANGLE_WINDOW_RAD; /* the sleeve squeezed: not a fault */
    float phr[2];
    gp_fb_stance(0.30f, 0.0f, phr);
    tick(3);
    CHECK(A.reason != GP_R_JOINT_RANGE);
    TP.angle[0] = phr[0];

    /* a motor that stops answering: limp after 3 ticks, torque off */
    boot_and_stand(36.0f);
    TP.mute[2] = true;
    tick(3); /* the answers to the tick before still came */
    CHECK(A.mode == GP_MODE_RUN);
    tick(1);
    CHECK(A.mode == GP_MODE_LIMP && A.reason == GP_R_MOTOR_MISSING && !A.mcu_run);
}

int main(void)
{
    test_fivebar();
    test_rs04();
    test_vesc();
    test_jetson();
    test_vn100();
    test_ina228();
    test_control();
    test_guard();
    test_supervisor();
    printf("%d checks, %d failed\n", checks, fails);
    return fails ? 1 : 0;
}
