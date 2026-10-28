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
    gp_ina228_encode_vbus(48.1f, v);
    NEAR(gp_ina228_vbus(v), 48.1, 2e-4);
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
    s->vbus = 48.1f;
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
    boot_and_stand(48.1f);
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

    /* the jump gate: 44.0 V resting and up, the take-off speed scaled */
    NEAR(gp_jump_scale(43.99f), 0.0, 0);
    NEAR(gp_jump_scale(44.0f), (44.0 - 35.0) / 13.1, 1e-6);
    NEAR(gp_jump_scale(48.1f), 1.0, 1e-6);
    NEAR(gp_jump_scale(53.3f), 1.0, 0);
    boot_and_stand(43.9f);
    jump_seq = 1;
    tick(20);
    CHECK(A.mode == GP_MODE_RUN && A.jump_refusal == GP_J_VOLTAGE && A.jumps_refused == 1);
    boot_and_stand(44.1f);
    jump_seq = 1;
    tick(20);
    CHECK(A.mode == GP_MODE_JUMP && A.jumps == 1);
    NEAR(A.jump_scale, (44.1 - 35.0) / 13.1, 1e-4);
    /* people near: no jump, then sit after 2 s */
    boot_and_stand(48.1f);
    env.people = true;
    tick(20);
    jump_seq = 2;
    tick(20);
    CHECK(A.mode == GP_MODE_RUN && A.jump_refusal == GP_J_PEOPLE);
    tick(1950);
    CHECK(A.mode == GP_MODE_RUN);
    tick(50);
    CHECK(A.mode == GP_MODE_SIT && A.reason == GP_R_PEOPLE);

    /* UVLO: warn under 45.5 V, sit under 41.6 V (resting, filtered over 1 s) */
    boot_and_stand(45.6f);
    tick(3000);
    CHECK(!A.uvlo_warn);
    env.vbus = 45.4f;
    tick(5000);
    CHECK(A.uvlo_warn && A.mode == GP_MODE_RUN);
    env.vbus = 41.5f;
    float before = A.vrest;
    while (A.mode == GP_MODE_RUN && now < 60000000u) {
        before = A.vrest;
        tick(1);
    }
    CHECK(A.mode == GP_MODE_SIT && A.reason == GP_R_UVLO);
    CHECK(before >= 41.6f && A.vrest < 41.6f);
    /* the sag is taken back out: 30 A at 41.0 V on the wire is 44.4 V resting */
    boot_and_stand(48.1f);
    env.vbus = 41.0f;
    env.ibus = 30.0f;
    tick(6000);
    NEAR(A.vrest, 41.0 + 30.0 * (double)GP_R_PACK_OHM, 0.02);
    CHECK(A.mode == GP_MODE_RUN);

    /* the Jetson's heartbeat: 200 ms lost, 2 s holding, then sit */
    boot_and_stand(48.1f);
    env.link = false;
    tick(2150);
    CHECK(A.mode == GP_MODE_RUN);
    tick(100);
    CHECK(A.mode == GP_MODE_SIT && A.reason == GP_R_LINK);

    /* a motor that stops answering: limp after 3 ticks, torque off */
    boot_and_stand(48.1f);
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
    test_supervisor();
    printf("%d checks, %d failed\n", checks, fails);
    return fails ? 1 : 0;
}
