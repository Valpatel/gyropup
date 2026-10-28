/* The balance firmware's application: devices, supervisor and the 1 kHz loop (gp_app.h). docs/body-firmware.md 5
 * describes every behaviour with its number. */
#include "gp/gp_app.h"

#include <math.h>
#include <string.h>

#include "gp/gp_config.h"
#include "gp/gp_model.h"
#include "gp/gp_rs04.h"

#define PI_F 3.14159265358979f
#define DEG 0.0174532925f

static float clampf(float v, float lo, float hi)
{
    return v < lo ? lo : (v > hi ? hi : v);
}

static float smooth(float t)
{
    t = clampf(t, 0.0f, 1.0f);
    return t * t * (3.0f - 2.0f * t);
}

static float secs(uint32_t dt_us)
{
    return (float)dt_us * 1e-6f;
}

static uint32_t since(const gp_app *a, uint32_t t)
{
    return a->now - t;
}

static void send(gp_app *a, uint8_t bus, const gp_can_frame *f)
{
    if (!gp_plat_can_send(bus, f)) {
        a->tx_drops++;
    }
}

/* ======================================================================================== configuration */

void gp_config_default(gp_config *c, uint8_t profile)
{
    memset(c, 0, sizeof *c);
    c->profile = profile;
    c->vbus_source = GP_VBUS_INA228;
    c->bench_scenario = GP_BENCH_STAND_UP;
    c->imu_required = profile == GP_PROFILE_ROBOT;
    /* placeholders until rig/calibrate.py zeroes each motor on its bare knee-out post (B13): ids 1-4, direction +1, the
     * zero at the designed knee-out stop */
    for (int i = 0; i < 4; i++) {
        c->motor[i].id = (uint8_t)(i + 1);
        c->motor[i].bus = i < 2 ? GP_BUS_A : GP_BUS_B;
        c->motor[i].dir = 1;
        c->motor[i].phi_zero = (i % 2 == 0) ? GP_FB_STOP_FRONT_OUT : GP_FB_STOP_REAR_OUT;
    }
    c->vesc_id[0] = GP_VESC_ID_LEFT;
    c->vesc_id[1] = GP_VESC_ID_RIGHT;
    c->wheel_dir[0] = 1;
    c->wheel_dir[1] = -1; /* the right hub motor is the left one turned round */
#ifdef GP_SHUNT_OHM
    c->r_shunt = GP_SHUNT_OHM; /* the build's choice (cmake -DGP_SHUNT=blue_sea for P0-P2) */
#else
    c->r_shunt = GP_SHUNT_FUSE_BOARD_OHM;
#endif
    c->ina_sign = -1.0f;
    c->r_pack = GP_R_PACK_OHM;
    if (profile == GP_PROFILE_ROBOT) {
        c->sit_L = GP_SIT_L_ROBOT_M;
        c->ctl.balance = true;
        c->ctl.legs = (gp_leg_gains){GP_LEG_KP_L, GP_LEG_KD_L, GP_LEG_KP_TH, GP_LEG_KD_TH};
        c->ctl.leg_ff_n = GP_ROBOT_LEG_FF_N;
    } else {
        c->sit_L = GP_SIT_L_RIG_M;
        c->ctl.balance = false;
        c->ctl.legs = (gp_leg_gains){GP_RIG_KP_L, GP_RIG_KD_L, GP_RIG_KP_TH, GP_RIG_KD_TH};
        c->ctl.leg_ff_n = GP_RIG_LEG_FF_N;
    }
    c->ctl.tuck = (gp_leg_gains){GP_TUCK_KP_L, GP_TUCK_KD_L, c->ctl.legs.kp_th, c->ctl.legs.kd_th};
    c->ctl.theta_trim = 0.0f;
}

void gp_app_init(gp_app *a, const gp_config *cfg, uint32_t now_us)
{
    memset(a, 0, sizeof *a);
    a->cfg = *cfg;
    gp_ctl_init(&a->ctl, &cfg->ctl);
    gp_ina228_setup(&a->ina, cfg->r_shunt);
    gp_vn100_init(&a->vn);
    a->now = now_us;
    a->t_mode = now_us;
    a->mode = GP_MODE_BOOT;
    a->t_boot_retry = now_us;
}

/* ======================================================================================== receiving */

static int motor_index(const gp_app *a, uint8_t bus, uint8_t id)
{
    for (int i = 0; i < 4; i++) {
        if (a->cfg.motor[i].id == id && a->cfg.motor[i].bus == bus) {
            return i;
        }
    }
    return -1;
}

static void take_feedback(gp_app *a, int i, const gp_rs04_feedback *fb)
{
    gp_motor_state *m = &a->mot[i];
    const gp_motor_cal *c = &a->cfg.motor[i];
    float p = fb->p;
    if (m->have) { /* continuous through the field's +-4 pi wrap */
        float d = p - m->p;
        d = fmodf(d + 2.0f * GP_RS04_P_MAX, 4.0f * GP_RS04_P_MAX);
        if (d < 0.0f) d += 4.0f * GP_RS04_P_MAX;
        p = m->p + d - 2.0f * GP_RS04_P_MAX;
    }
    float v = fb->v;
    if (fabsf(v) >= GP_RS04_V_RAIL && m->have && a->now != m->t_fb) {
        v = (p - m->p) / secs(a->now - m->t_fb); /* the speed field is on its rail: the angle's rate */
    }
    m->p_prev = m->p;
    m->t_prev = m->t_fb;
    m->p = p;
    m->v = v;
    m->t = fb->t;
    m->temp_c = fb->temp_c;
    m->mode = fb->mode;
    m->faults = fb->faults;
    m->t_fb = a->now;
    m->have = true;
    m->fresh = true;
    m->phi = c->phi_zero + (float)c->dir * p;
    m->w = (float)c->dir * v;
}

static void boot_reply(gp_app *a, int i, const gp_rs04_msg *msg);

void gp_app_can_rx(gp_app *a, uint8_t bus, const gp_can_frame *f, uint32_t now_us)
{
    a->now = now_us;
    a->can_rx++;
    if (bus == GP_BUS_A || bus == GP_BUS_B) {
        if (!f->ext) { /* the leg rig node (rig/node.py): RUN 0x700, VBUS 0x702 */
            if (f->id == GP_ID_RIG_VBUS && f->len >= 7 && a->cfg.vbus_source == GP_VBUS_RIG_NODE) {
                const float mean = (float)(f->data[4] | (f->data[5] << 8)) * 1e-3f;
                const float vmax = (float)(f->data[0] | (f->data[1] << 8)) * 1e-3f;
                const float dt = a->have_vbus ? fminf(secs(now_us - a->t_vbus), 0.1f) : 0.0f;
                a->vbus = vmax; /* the max of its 10 ms: a regeneration spike is seen */
                a->ibus = 0.0f;
                a->vrest = a->have_vbus ? a->vrest + dt / GP_VREST_TAU_S * (mean - a->vrest) : mean;
                a->t_vbus = now_us;
                a->have_vbus = true;
            }
            return;
        }
        gp_rs04_msg msg;
        if (!gp_rs04_parse(f, &msg)) {
            return;
        }
        const uint8_t id = msg.kind == GP_RS04_FEEDBACK ? msg.fb.motor
                           : msg.kind == GP_RS04_READ   ? msg.param.motor
                                                        : msg.fault.motor;
        const int i = motor_index(a, bus, id);
        if (i < 0) {
            return;
        }
        if (msg.kind == GP_RS04_FEEDBACK) {
            take_feedback(a, i, &msg.fb);
        }
        if (a->mode == GP_MODE_BOOT) {
            boot_reply(a, i, &msg);
        }
        return;
    }
    /* bus C */
    if (f->ext) {
        uint8_t id, cmd;
        gp_vesc_status st;
        for (int w = 0; w < 2; w++) {
            if ((f->id & 0xFFu) == a->cfg.vesc_id[w]) {
                st = a->vesc[w];
                if (gp_vesc_parse(f, &id, &cmd, &st)) {
                    a->vesc[w] = st;
                    if (cmd == GP_VESC_STATUS_1) {
                        a->t_vesc[w] = now_us;
                        a->have_vesc[w] = true;
                    }
                }
            }
        }
        return;
    }
    gp_jet_setpoint sp;
    if (gp_jet_decode_setpoint(f, &sp)) {
        if (!a->have_sp || sp.seq != a->sp.seq) { /* a repeated sequence number is not a heartbeat */
            a->t_link = now_us;
        }
        if (sp.run && !a->run_prev) {
            a->run_rise = true;
        }
        a->run_prev = sp.run;
        a->sp = sp;
        a->have_sp = true;
        return;
    }
    if (f->id == GP_ID_JET_BENCH && f->len >= 2 && f->data[0] == 1 && a->cfg.profile == GP_PROFILE_RIG &&
        (a->mode == GP_MODE_IDLE || a->mode == GP_MODE_BOOT)) {
        a->cfg.bench_scenario = f->data[1];
    }
}

void gp_app_uart_rx(gp_app *a, const uint8_t *data, size_t n, uint32_t now_us)
{
    gp_vn100_sample s;
    if (gp_vn100_feed(&a->vn, data, n, &s) > 0) {
        a->imu = s;
        a->t_imu = now_us;
        a->have_imu = true;
    }
}

void gp_app_ina228(gp_app *a, const uint8_t vbus[3], const uint8_t current[3], uint32_t now_us)
{
    if (a->cfg.vbus_source != GP_VBUS_INA228) {
        return;
    }
    const float v = gp_ina228_vbus(vbus);
    const float i = a->cfg.ina_sign * gp_ina228_current(&a->ina, current); /* + = discharge */
    const float rest = v + i * a->cfg.r_pack;                           /* the sag taken back out */
    const float dt = a->have_vbus ? fminf(secs(now_us - a->t_vbus), 0.1f) : 0.0f;
    a->vrest = a->have_vbus ? a->vrest + dt / GP_VREST_TAU_S * (rest - a->vrest) : rest;
    a->vbus = v;
    a->ibus = i;
    a->t_vbus = now_us;
    a->have_vbus = true;
}

/* ======================================================================================== boot: configure the RS-04s */

enum { B_STOP, B_W_MODE, B_W_LIMIT, B_W_TIMEOUT, B_W_ZERO, B_R_MODE, B_R_LIMIT, B_R_TIMEOUT, B_R_ZERO, B_R_VBUS, B_DONE };

static void boot_request(gp_app *a, int i)
{
    gp_can_frame f;
    const uint8_t id = a->cfg.motor[i].id;
    switch (a->mot[i].boot_step) {
    case B_STOP: gp_rs04_stop(id, false, &f); break;
    case B_W_MODE: gp_rs04_write_u8(id, GP_RS04_P_RUN_MODE, 0, &f); break;
    case B_W_LIMIT: gp_rs04_write_f32(id, GP_RS04_P_LIMIT_TORQUE, GP_RS04_LIMIT_TORQUE, &f); break;
    case B_W_TIMEOUT: gp_rs04_write_u32(id, GP_RS04_P_CAN_TIMEOUT, GP_RS04_CAN_TIMEOUT, &f); break;
    case B_W_ZERO: gp_rs04_write_u8(id, GP_RS04_P_ZERO_STA, 1, &f); break;
    case B_R_MODE: gp_rs04_read(id, GP_RS04_P_RUN_MODE, &f); break;
    case B_R_LIMIT: gp_rs04_read(id, GP_RS04_P_LIMIT_TORQUE, &f); break;
    case B_R_TIMEOUT: gp_rs04_read(id, GP_RS04_P_CAN_TIMEOUT, &f); break;
    case B_R_ZERO: gp_rs04_read(id, GP_RS04_P_ZERO_STA, &f); break;
    case B_R_VBUS: gp_rs04_read(id, GP_RS04_P_VBUS, &f); break;
    default: return;
    }
    send(a, a->cfg.motor[i].bus, &f);
    a->mot[i].req_out = true;
    a->mot[i].t_req = a->now;
}

static void boot_reply(gp_app *a, int i, const gp_rs04_msg *msg)
{
    gp_motor_state *m = &a->mot[i];
    if (!m->req_out || m->boot_step >= B_DONE) {
        return;
    }
    const uint8_t s = m->boot_step;
    bool ok = false, bad = false;
    if (s <= B_W_ZERO) {
        ok = msg->kind == GP_RS04_FEEDBACK;
    } else if (msg->kind == GP_RS04_READ) {
        const gp_rs04_param *p = &msg->param;
        const uint16_t want = s == B_R_MODE ? GP_RS04_P_RUN_MODE : s == B_R_LIMIT ? GP_RS04_P_LIMIT_TORQUE
                              : s == B_R_TIMEOUT ? GP_RS04_P_CAN_TIMEOUT : s == B_R_ZERO ? GP_RS04_P_ZERO_STA : GP_RS04_P_VBUS;
        if (p->index != want) {
            return;
        }
        ok = p->ok;
        if (s == B_R_MODE) bad = p->raw[0] != 0;
        if (s == B_R_LIMIT) bad = fabsf(gp_rs04_param_f32(p) - GP_RS04_LIMIT_TORQUE) > 0.01f;
        if (s == B_R_TIMEOUT) bad = gp_rs04_param_u32(p) != GP_RS04_CAN_TIMEOUT;
        if (s == B_R_ZERO) bad = p->raw[0] != 1;
        if (s == B_R_VBUS) m->vbus = gp_rs04_param_f32(p);
    }
    if (!ok) {
        return;
    }
    m->req_out = false;
    if (bad) { /* a written value did not read back: start this motor again */
        m->boot_step = B_STOP;
        m->retries++;
        return;
    }
    m->retries = 0;
    m->boot_step++;
    if (m->boot_step == B_DONE) {
        m->configured = true;
    }
}

static void boot_tick(gp_app *a)
{
    for (int i = 0; i < 4; i++) {
        gp_motor_state *m = &a->mot[i];
        if (m->boot_step >= B_DONE) {
            continue;
        }
        if (m->retries >= GP_BOOT_RETRIES) { /* absent or refusing: try again in a second */
            if (since(a, a->t_boot_retry) < 1000000u) {
                continue;
            }
            m->retries = 0;
            m->boot_step = B_STOP;
            m->req_out = false;
        }
        if (m->req_out && since(a, m->t_req) >= GP_BOOT_STEP_US) {
            m->req_out = false;
            m->retries++;
            a->t_boot_retry = a->now;
            continue;
        }
        if (!m->req_out) {
            boot_request(a, i);
        }
    }
}

/* ======================================================================================== the supervisor */

float gp_jump_scale(float vrest)
{
    if (!(vrest >= GP_JUMP_MIN_V)) {
        return 0.0f;
    }
    return clampf((vrest - GP_JUMP_FLOOR_V) / (GP_JUMP_FULL_V - GP_JUMP_FLOOR_V), 0.0f, 1.0f);
}

static bool all_configured(const gp_app *a)
{
    for (int i = 0; i < 4; i++) {
        if (!a->mot[i].configured) return false;
    }
    return true;
}

static bool link_ok(const gp_app *a)
{
    return a->have_sp && since(a, a->t_link) < GP_HEARTBEAT_LOST_US;
}

static bool vbus_fresh(const gp_app *a)
{
    return a->have_vbus && since(a, a->t_vbus) < GP_VBUS_TIMEOUT_US;
}

static bool imu_fresh(const gp_app *a)
{
    return a->have_imu && since(a, a->t_imu) < 20000u;
}

static void set_mode(gp_app *a, uint8_t mode)
{
    a->mode = mode;
    a->t_mode = a->now;
}

static float leg_length(const gp_app *a, int side)
{
    gp_fb_polar p;
    if (gp_fb_polar_state(a->mot[2 * side].phi, a->mot[2 * side + 1].phi, 0.0f, 0.0f, &p)) {
        return p.L;
    }
    return a->cfg.sit_L;
}

static void start_sit(gp_app *a, uint8_t reason, bool fast)
{
    if (a->mode == GP_MODE_SIT || a->mode == GP_MODE_SETTLE || a->mode == GP_MODE_LIMP) {
        return;
    }
    a->reason = reason;
    for (int s = 0; s < 2; s++) {
        a->sit_from[s] = leg_length(a, s);
    }
    a->sit_T = fast ? GP_SIT_FAST_S : GP_SIT_NORMAL_S;
    a->jump_phase = GP_JP_NONE;
    set_mode(a, GP_MODE_SIT);
}

static void limp(gp_app *a, uint8_t reason)
{
    if (a->mode == GP_MODE_LIMP) {
        return;
    }
    a->reason = reason;
    a->latched = true;
    a->jump_phase = GP_JP_NONE;
    set_mode(a, GP_MODE_LIMP);
}

static bool active(uint8_t mode)
{
    return mode == GP_MODE_ARMING || mode == GP_MODE_RUN || mode == GP_MODE_JUMP || mode == GP_MODE_SIT ||
           mode == GP_MODE_SETTLE;
}

/* The faults that take the torque away at once. */
static void check_limp(gp_app *a)
{
    for (int i = 0; i < 4; i++) {
        if (a->mot[i].miss >= GP_MISS_MAX) { limp(a, GP_R_MOTOR_MISSING); return; }
        if (a->mot[i].faults) { limp(a, GP_R_MOTOR_FAULT); return; }
    }
    for (int s = 0; s < 2; s++) {
        const float L = leg_length(a, s);
        if (L < GP_L_MIN_M || L > GP_L_MAX_M) { limp(a, GP_R_LEG_WINDOW); return; }
    }
    if (a->have_vbus && a->vbus > GP_VBUS_OVER_V) { limp(a, GP_R_OVERVOLT); return; }
    if (a->cfg.imu_required && a->mode != GP_MODE_ARMING) {
        if (!imu_fresh(a)) { limp(a, GP_R_IMU); return; }
        if (a->cfg.ctl.balance && fabsf(a->out.theta) > GP_FALLEN_RAD) { limp(a, GP_R_FALLEN); return; }
    }
}

static void update_flags(gp_app *a)
{
    if (a->have_vbus) {
        if (a->vrest < GP_UVLO_WARN_V) a->uvlo_warn = true;
        else if (a->vrest > GP_UVLO_WARN_CLEAR_V) a->uvlo_warn = false;
        if (a->vrest < GP_UVLO_SIT_V) a->uvlo_sat = true;
        else if (a->vrest >= GP_UVLO_STAND_V) a->uvlo_sat = false;
    }
    /* people near: the caps hold while the flag is up; 2 s of it sits the robot */
    const bool people = a->have_sp && a->sp.people_near && link_ok(a);
    if (people && !a->people) {
        a->t_people = a->now;
        a->hold_height = a->sp.height;
        a->hold_lean = a->sp.lean;
    }
    a->people = people;
}

static uint8_t jump_refusal(const gp_app *a)
{
    if (a->mode != GP_MODE_RUN) return GP_J_NOT_RUNNING;
    if (!link_ok(a)) return GP_J_LINK;
    if (a->people) return GP_J_PEOPLE;
    if (!vbus_fresh(a) || gp_jump_scale(a->vrest) <= 0.0f) return GP_J_VOLTAGE;
    if (a->sp.jump_height == 0) return GP_J_HEIGHT_ZERO;
    return GP_J_OK;
}

static void supervise(gp_app *a)
{
    update_flags(a);
    /* a jump request is the 2-bit counter changing */
    if (a->have_sp && a->sp.jump_seq != a->jump_seq_prev) {
        a->jump_seq_prev = a->sp.jump_seq;
        const uint8_t why = jump_refusal(a);
        a->jump_refusal = why;
        if (why == GP_J_OK) {
            const float s = gp_jump_scale(a->vrest);
            a->jump_scale = s;
            a->jump_v_target = GP_JUMP_V_MAX * sqrtf((float)a->sp.jump_height / 15.0f) * s;
            a->jump_from = 0.5f * (leg_length(a, 0) + leg_length(a, 1));
            a->jump_phase = GP_JP_CROUCH;
            a->t_jump = a->t_phase = a->now;
            a->jumps++;
            set_mode(a, GP_MODE_JUMP);
        } else {
            a->jumps_refused++;
        }
    }
    if (active(a->mode)) {
        check_limp(a);
    }
    switch (a->mode) {
    case GP_MODE_BOOT:
        if (all_configured(a) && (!a->cfg.imu_required || imu_fresh(a)) && vbus_fresh(a)) {
            set_mode(a, GP_MODE_IDLE);
        }
        break;
    case GP_MODE_LIMP:
        if (since(a, a->t_mode) > 1000000u) {
            set_mode(a, GP_MODE_IDLE);
        }
        break;
    case GP_MODE_IDLE: {
        if (a->have_sp && !a->sp.run) {
            a->latched = false; /* the Jetson has seen it sit: a new RUN may arm it */
            a->run_rise = false;
        }
        const bool stop_ok = a->stop_run && since(a, a->t_stop_high) >= GP_RUN_HOLD_US;
        if (a->run_rise && link_ok(a) && a->sp.run && stop_ok && !a->latched && all_configured(a) && vbus_fresh(a) &&
            !a->uvlo_sat && !a->people && (!a->cfg.imu_required || imu_fresh(a))) {
            a->run_rise = false;
            a->reason = GP_R_NONE;
            for (int i = 0; i < 4; i++) {
                gp_can_frame f;
                gp_rs04_enable(a->cfg.motor[i].id, &f);
                send(a, a->cfg.motor[i].bus, &f);
                a->mot[i].miss = 0;
                a->mot[i].fresh = true;
            }
            set_mode(a, GP_MODE_ARMING);
        }
        break;
    }
    case GP_MODE_ARMING: {
        bool all_run = true;
        for (int i = 0; i < 4; i++) {
            all_run = all_run && a->mot[i].mode == GP_RS04_MODE_RUN;
        }
        if (!a->stop_run) {
            start_sit(a, GP_R_STOP, true);
        } else if (all_run) {
            const float h = gp_ctl_height_frac(0.5f * (leg_length(a, 0) + leg_length(a, 1)));
            gp_ctl_reset(&a->ctl, h);
            a->t_run = a->now;
            set_mode(a, GP_MODE_RUN);
        } else if (since(a, a->t_mode) > GP_ARM_TIMEOUT_US) {
            limp(a, GP_R_ARM_TIMEOUT);
        }
        break;
    }
    case GP_MODE_RUN:
    case GP_MODE_JUMP: {
        uint8_t why = GP_R_NONE;
        bool fast = false;
        if (!a->stop_run) { why = GP_R_STOP; fast = true; }
        else if (!vbus_fresh(a)) why = GP_R_VBUS_STALE;
        else if (a->uvlo_sat) why = GP_R_UVLO;
        else if (!link_ok(a) && since(a, a->t_link) >= GP_HEARTBEAT_LOST_US + GP_HEARTBEAT_HOLD_US) why = GP_R_LINK;
        else if (link_ok(a) && !a->sp.run) why = GP_R_JETSON;
        else if (a->people && since(a, a->t_people) >= GP_PEOPLE_SIT_US) why = GP_R_PEOPLE;
        if (why != GP_R_NONE) {
            if (a->mode == GP_MODE_JUMP && (a->jump_phase == GP_JP_PUSH || a->jump_phase == GP_JP_AIR)) {
                a->stop_pending = true; /* finish the flight and land first; a push is cut short */
                a->reason = why;
                if (a->jump_phase == GP_JP_PUSH) {
                    a->jump_phase = GP_JP_AIR;
                    a->t_phase = a->now;
                }
            } else {
                start_sit(a, why, fast);
            }
        }
        break;
    }
    case GP_MODE_SIT:
        if (secs(since(a, a->t_mode)) >= a->sit_T) {
            set_mode(a, GP_MODE_SETTLE);
        }
        break;
    case GP_MODE_SETTLE:
        if (secs(since(a, a->t_mode)) >= GP_SETTLE_S) {
            set_mode(a, GP_MODE_IDLE);
        }
        break;
    default:
        break;
    }
}

/* ======================================================================================== the legs' commands */

static float bench_L(const gp_app *a)
{
    const float t = secs(since(a, a->t_run));
    if (a->cfg.bench_scenario == GP_BENCH_SQUAT) { /* sim/leg_rig.py 'squat' */
        return 0.225f + 0.075f * cosf(2.0f * PI_F * 0.5f * fmaxf(0.0f, t - 0.25f));
    }
    return 0.140f + (0.300f - 0.140f) * smooth((t - 0.3f) / 1.0f); /* 'stand_up': the deepest crouch to 300 mm in 1 s */
}

/* The length the legs would follow in RUN now (the bench player, or the height command). */
static float normal_L(const gp_app *a)
{
    if (a->cfg.profile == GP_PROFILE_RIG) {
        return bench_L(a);
    }
    return gp_ctl_height_m(a->ctl.height);
}

static void jump_legs(gp_app *a, gp_leg_cmd leg[2], bool *wheels)
{
    const float tj = secs(since(a, a->t_jump));
    float tp = secs(since(a, a->t_phase));
    const gp_fb_polar *p = a->out.leg; /* last tick's legs */
    const float L = 0.5f * (p[0].L + p[1].L), dL = 0.5f * (p[0].dL + p[1].dL);
    switch (a->jump_phase) {
    case GP_JP_CROUCH:
        if (!a->stop_run) { /* the stop before the push: sit at once */
            start_sit(a, GP_R_STOP, true);
            return;
        }
        if (tj >= GP_JUMP_PUSH_AT_S) {
            a->jump_phase = GP_JP_PUSH;
            a->t_phase = a->now;
            tp = 0.0f;
        } else {
            for (int s = 0; s < 2; s++) {
                leg[s] = (gp_leg_cmd){GP_LEG_LENGTH, false,
                                      a->jump_from + (GP_JUMP_CROUCH_L_M - a->jump_from) * smooth(tj / GP_JUMP_CROUCH_S), 0, 1};
            }
            return;
        }
        /* fall through */
    case GP_JP_PUSH:
        /* stop pushing at the leg's end (looking ahead half a tick, as rig/leg_control.py), on time, or at the
         * take-off speed the voltage allows */
        if (L + dL * (0.5f * GP_DT - 0.00075f) > GP_JUMP_PUSH_END_L_M || tp > GP_JUMP_PUSH_MAX_S || dL >= a->jump_v_target) {
            a->jump_phase = GP_JP_AIR;
            a->t_phase = a->now;
            tp = 0.0f;
        } else {
            for (int s = 0; s < 2; s++) {
                leg[s] = (gp_leg_cmd){GP_LEG_FORCE, false, 0, GP_JUMP_PUSH_F_N, 1};
            }
            return;
        }
        /* fall through */
    case GP_JP_AIR:
        if (tp >= GP_JUMP_MIN_AIR_S && dL < GP_JUMP_LAND_DL && L < GP_JUMP_LAND_L_M) {
            a->jump_phase = GP_JP_LAND;
            a->t_phase = a->now;
            tp = 0.0f;
        } else {
            *wheels = false;
            for (int s = 0; s < 2; s++) {
                leg[s] = (gp_leg_cmd){GP_LEG_LENGTH, true, GP_JUMP_LAND_L_M, 0, 0};
            }
            return;
        }
        /* fall through */
    case GP_JP_LAND:
        if (a->stop_pending) {
            a->stop_pending = false;
            start_sit(a, a->reason, a->reason == GP_R_STOP);
            return;
        }
        if (tp >= GP_JUMP_RECOVER_S && a->jump_phase == GP_JP_LAND) {
            a->jump_phase = GP_JP_RECOVER;
            a->t_phase = a->now;
            tp = 0.0f;
        } else {
            for (int s = 0; s < 2; s++) {
                leg[s] = (gp_leg_cmd){GP_LEG_LENGTH, false, GP_JUMP_LAND_L_M, 0, 1};
            }
            return;
        }
        /* fall through */
    case GP_JP_RECOVER:
        if (tp >= GP_JUMP_RECOVER_S) {
            a->jump_phase = GP_JP_NONE;
            a->ctl.height = gp_ctl_height_frac(normal_L(a));
            set_mode(a, GP_MODE_RUN);
            return; /* this tick's legs come from RUN's law */
        }
        for (int s = 0; s < 2; s++) {
            leg[s] = (gp_leg_cmd){GP_LEG_LENGTH, false,
                                  GP_JUMP_LAND_L_M + (normal_L(a) - GP_JUMP_LAND_L_M) * smooth(tp / GP_JUMP_RECOVER_S), 0, 1};
        }
        return;
    default:
        return;
    }
}

/* ======================================================================================== the loop */

static void build_sense(const gp_app *a, gp_sense *s)
{
    memset(s, 0, sizeof *s);
    for (int i = 0; i < 4; i++) {
        s->phi[i / 2][i % 2] = a->mot[i].phi;
        s->dphi[i / 2][i % 2] = a->mot[i].w;
    }
    for (int w = 0; w < 2; w++) {
        const float erpm = (float)a->vesc[w].erpm;
        s->wheel_w[w] = (float)a->cfg.wheel_dir[w] * erpm / (float)GP_WHEEL_POLE_PAIRS * (2.0f * PI_F / 60.0f);
    }
    s->vbus = a->have_vbus ? a->vbus : GP_JUMP_FULL_V;
    if (a->have_imu) {
        /* the VN-100's frame (x forward, y right, z down) to the robot's (x forward, y left, z up) */
        const float roll = a->imu.roll * DEG;
        const float pitch = -a->imu.pitch * DEG; /* + = nose down: rotation about +y (left) */
        const float p = a->imu.gx, q = -a->imu.gy, r = -a->imu.gz;
        s->pitch = pitch;
        s->pitch_rate = q;
        s->roll = asinf(clampf(cosf(pitch) * sinf(roll), -1.0f, 1.0f));
        s->yaw_rate = -sinf(pitch) * p + cosf(pitch) * sinf(roll) * q + cosf(pitch) * cosf(roll) * r;
    }
}

static void build_cmd(gp_app *a, gp_cmd *c)
{
    memset(c, 0, sizeof *c);
    c->height = a->ctl.height;
    if (a->cfg.profile == GP_PROFILE_RIG || !a->have_sp) {
        return;
    }
    if (link_ok(a)) {
        c->height = clampf(a->sp.height, 0.0f, 1.0f);
        c->look_up = a->sp.lean;
        c->speed = a->sp.speed;
        c->yaw_rate = a->sp.yaw_rate;
        if (a->people) { /* legs hold, 0.5 m/s at most */
            c->height = a->hold_height;
            c->look_up = a->hold_lean;
            c->speed = clampf(c->speed, -GP_PEOPLE_SPEED_MAX, GP_PEOPLE_SPEED_MAX);
        }
        a->hold_height = c->height;
        a->hold_lean = c->look_up;
    } else { /* the link lost: balance in place, the legs where they were */
        c->height = a->hold_height;
        c->look_up = a->hold_lean;
    }
}

static void motors_stop(gp_app *a)
{
    for (int i = 0; i < 4; i++) {
        gp_can_frame f;
        gp_rs04_stop(a->cfg.motor[i].id, false, &f);
        send(a, a->cfg.motor[i].bus, &f);
    }
}

static void wheels_current(gp_app *a, const float amps[2])
{
    for (int w = 0; w < 2; w++) {
        gp_can_frame f;
        a->wheel_current[w] = amps[w];
        gp_vesc_set_current(a->cfg.vesc_id[w], (float)a->cfg.wheel_dir[w] * amps[w], &f);
        send(a, GP_BUS_C, &f);
    }
}

static void tx_state(gp_app *a)
{
    gp_jet_state st;
    memset(&st, 0, sizeof st);
    gp_sense s;
    build_sense(a, &s);
    st.pitch = -s.pitch; /* + = nose up on the wire */
    st.pitch_rate = -s.pitch_rate;
    st.speed = a->out.v;
    st.yaw_rate = s.yaw_rate;
    for (int side = 0; side < 2; side++) {
        st.L[side] = a->out.leg_ok[side] ? a->out.leg[side].L : leg_length(a, side);
        st.lean[side] = a->out.leg[side].th;
    }
    gp_snapshot snap;
    gp_app_snapshot(a, &snap);
    st.mode = a->mode;
    st.flags = (uint8_t)snap.flags;
    st.vbus = a->vbus;
    st.ibus = a->ibus;
    st.reason = a->reason;
    st.seq = a->seq_status;
    gp_can_frame f;
    switch (a->tick % 5u) {
    case 0: gp_jet_encode_state_a(&st, &f); break;
    case 1: gp_jet_encode_state_b(&st, &f); break;
    case 2: gp_jet_encode_status(&st, &f); a->seq_status++; break;
    case 3:
        if (a->tick % 100u != 3u) return;
        memset(&f, 0, sizeof f);
        f.id = GP_ID_MCU_FAULTS;
        f.len = 8;
        for (int i = 0; i < 4; i++) {
            f.data[i] = (uint8_t)((a->mot[i].have ? 0x80u : 0u) | (a->mot[i].faults & 0x3Fu));
        }
        f.data[4] = (uint8_t)((a->have_vesc[0] ? 1u : 0u) | (a->have_vesc[1] ? 2u : 0u) | (imu_fresh(a) ? 4u : 0u) |
                              (vbus_fresh(a) ? 8u : 0u) | (a->latched ? 16u : 0u));
        f.data[5] = (uint8_t)lroundf(100.0f * gp_jump_scale(a->vrest) * gp_jump_scale(a->vrest));
        f.data[6] = a->jump_refusal;
        f.data[7] = (uint8_t)(a->tick / 100u);
        break;
    default: return;
    }
    send(a, GP_BUS_C, &f);
}

void gp_app_tick(gp_app *a, uint32_t now_us, const gp_inputs *in, gp_outputs *out)
{
    a->now = now_us;
    a->tick++;
    /* the stop sense, debounced: 2 ms low is a stop; high must hold 100 ms before an arm */
    if (in->stop_run) {
        if (!a->stop_seen_run || a->stop_low >= GP_STOP_DEBOUNCE_TICKS) {
            a->t_stop_high = now_us;
        }
        a->stop_low = 0;
        a->stop_run = true;
        a->stop_seen_run = true;
    } else if (++a->stop_low >= GP_STOP_DEBOUNCE_TICKS) {
        a->stop_run = false;
    }
    /* the motors' feedback this tick: count the misses while they are being driven */
    for (int i = 0; i < 4; i++) {
        gp_motor_state *m = &a->mot[i];
        if (active(a->mode) && a->mode != GP_MODE_ARMING) {
            m->miss = m->fresh ? 0 : (uint8_t)(m->miss + 1u);
        }
        m->fresh = false;
    }
    supervise(a);

    gp_sense s;
    build_sense(a, &s);
    gp_cmd cmd;
    build_cmd(a, &cmd);
    gp_leg_cmd leg[2] = {{GP_LEG_TRACK, false, 0, 0, 1}, {GP_LEG_TRACK, false, 0, 0, 1}};
    bool wheels = true;
    if (a->mode == GP_MODE_RUN && a->cfg.profile == GP_PROFILE_RIG) {
        leg[0] = leg[1] = (gp_leg_cmd){GP_LEG_LENGTH, false, bench_L(a), 0, 1};
    }
    if (a->mode == GP_MODE_JUMP) {
        jump_legs(a, leg, &wheels);
        if (a->mode == GP_MODE_RUN && a->cfg.profile == GP_PROFILE_RIG) {
            leg[0] = leg[1] = (gp_leg_cmd){GP_LEG_LENGTH, false, bench_L(a), 0, 1};
        }
    }
    if (a->mode == GP_MODE_SIT || a->mode == GP_MODE_SETTLE) {
        cmd.speed = 0.0f;
        cmd.yaw_rate = 0.0f;
        const float t = secs(since(a, a->t_mode));
        for (int side = 0; side < 2; side++) {
            if (a->mode == GP_MODE_SIT) {
                leg[side] = (gp_leg_cmd){GP_LEG_LENGTH, false,
                                         a->sit_from[side] + (a->cfg.sit_L - a->sit_from[side]) * smooth(t / a->sit_T), 0, 1};
            } else {
                leg[side] = (gp_leg_cmd){GP_LEG_LENGTH, false, a->cfg.sit_L, 0, clampf(1.0f - t / GP_SETTLE_S, 0.0f, 1.0f)};
                wheels = false;
            }
        }
    }
    const bool drive = a->mode == GP_MODE_RUN || a->mode == GP_MODE_JUMP || a->mode == GP_MODE_SIT || a->mode == GP_MODE_SETTLE;
    gp_ctl_step(&a->ctl, &s, &cmd, leg, wheels, &a->out);

    /* the motors */
    if (drive) {
        for (int i = 0; i < 4; i++) {
            gp_can_frame f;
            const float tau = (float)a->cfg.motor[i].dir * a->out.tau[i / 2][i % 2];
            gp_rs04_mit(a->cfg.motor[i].id, 0.0f, 0.0f, 0.0f, 0.0f, tau, &f);
            send(a, a->cfg.motor[i].bus, &f);
        }
        float amps[2];
        for (int w = 0; w < 2; w++) {
            amps[w] = clampf(a->out.wheel[w] / GP_WHEEL_KT_NM_PER_A, -GP_WHEEL_CURRENT_MAX_A, GP_WHEEL_CURRENT_MAX_A);
        }
        wheels_current(a, amps);
    } else if (a->mode == GP_MODE_ARMING) {
        for (int i = 0; i < 4; i++) { /* zero torque until every motor reports run mode */
            gp_can_frame f;
            gp_rs04_mit(a->cfg.motor[i].id, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, &f);
            send(a, a->cfg.motor[i].bus, &f);
        }
        const float zero[2] = {0.0f, 0.0f};
        wheels_current(a, zero);
    } else if (a->mode == GP_MODE_BOOT) {
        boot_tick(a);
    } else if (a->mode == GP_MODE_LIMP || a->tick % 10u == 0u) {
        /* limp: stop frames every tick for its first 50 ms, then as idle does: every 10 ms (the angles keep coming) */
        if (a->mode != GP_MODE_LIMP || since(a, a->t_mode) < 50000u || a->tick % 10u == 0u) {
            motors_stop(a);
            const float zero[2] = {0.0f, 0.0f};
            wheels_current(a, zero);
        }
    }
    if (!drive && a->mode != GP_MODE_ARMING) {
        memset(a->out.tau, 0, sizeof a->out.tau);
        memset(a->out.wheel, 0, sizeof a->out.wheel);
    }
    tx_state(a);
    a->mcu_run = a->mode == GP_MODE_ARMING || a->mode == GP_MODE_RUN || a->mode == GP_MODE_JUMP;
    out->mcu_run = a->mcu_run;
    out->led = (uint8_t)(a->mode == GP_MODE_RUN || a->mode == GP_MODE_JUMP ? 1u
                         : a->mode == GP_MODE_LIMP                     ? ((a->tick / 100u) & 1u)
                                                                       : ((a->tick / 500u) & 1u));
}

void gp_app_snapshot(const gp_app *a, gp_snapshot *s)
{
    memset(s, 0, sizeof *s);
    s->t_us = a->now;
    s->mode = a->mode;
    s->reason = a->reason;
    s->link_ok = link_ok(a);
    s->people = a->people;
    s->mcu_run = a->mcu_run;
    s->stop_run = a->stop_run;
    s->uvlo_warn = a->uvlo_warn;
    s->uvlo_sat = a->uvlo_sat;
    s->latched = a->latched;
    const bool jump_ok = a->mode == GP_MODE_RUN && s->link_ok && !a->people && vbus_fresh(a) && gp_jump_scale(a->vrest) > 0.0f;
    s->flags = (a->stop_run ? GP_JF_STOP_RUN : 0u) | (a->mcu_run ? GP_JF_MCU_RUN : 0u) | (s->link_ok ? GP_JF_LINK_OK : 0u) |
               (a->people ? GP_JF_PEOPLE : 0u) | (a->uvlo_warn ? GP_JF_UVLO_WARN : 0u) | (a->uvlo_sat ? GP_JF_UVLO_SIT : 0u) |
               (jump_ok ? GP_JF_JUMP_OK : 0u) | (a->mode == GP_MODE_JUMP ? GP_JF_JUMPING : 0u);
    s->jump_phase = a->jump_phase;
    s->jump_refusal = a->jump_refusal;
    s->jumps = a->jumps;
    s->jumps_refused = a->jumps_refused;
    for (int i = 0; i < 4; i++) {
        s->boot_mask |= a->mot[i].configured ? (1u << i) : 0u;
        s->phi[i] = a->mot[i].phi;
        s->w[i] = a->mot[i].w;
        s->misses[i] = a->mot[i].miss;
        s->tau[i] = a->out.tau[i / 2][i % 2];
    }
    s->vbus = a->vbus;
    s->ibus = a->ibus;
    s->vrest = a->vrest;
    s->jump_scale = a->jump_scale;
    s->jump_v_target = a->jump_v_target;
    for (int side = 0; side < 2; side++) {
        s->L[side] = a->out.leg[side].L;
        s->th[side] = a->out.leg[side].th;
        s->L_cmd[side] = a->out.L_cmd[side];
        s->wheel[side] = a->out.wheel[side];
        s->wheel_current[side] = a->wheel_current[side];
    }
    s->theta = a->out.theta;
    s->theta_dot = a->out.theta_dot;
    s->v = a->out.v;
    s->x_err = a->out.x_err;
    s->height = a->ctl.height;
    s->tx_drops = a->tx_drops;
    s->can_rx = a->can_rx;
    s->imu_packets = a->vn.packets;
    s->imu_crc_errors = a->vn.crc_errors;
}
