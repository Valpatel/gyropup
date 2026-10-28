/* The balance firmware's application: the devices (four RS-04s, two VESCs, the VN-100, the INA228, the Jetson), the
 * supervisor (the radio stop and MCU_RUN, the Jetson's heartbeat, UVLO, the jump gate, people near, the faults) and
 * the 1 kHz loop around the balance law (gp_control.h). Portable: the platform calls it from one context only (the
 * MCU's control tick, or the host library's caller), so nothing here needs a lock.
 *
 *   gp_app_init()            once
 *   gp_app_can_rx()          every received frame, gp_app_uart_rx() the VN-100's bytes, gp_app_ina228() a reading
 *   gp_app_tick()            every 1 ms: reads the stop sense, runs the supervisor and the law, sends the frames
 */
#ifndef GP_APP_H
#define GP_APP_H

#include "gp/gp_control.h"
#include "gp/gp_ina228.h"
#include "gp/gp_jetson.h"
#include "gp/gp_types.h"
#include "gp/gp_vesc.h"
#include "gp/gp_vn100.h"

enum { GP_PROFILE_ROBOT = 0, GP_PROFILE_RIG = 1 };
enum { GP_VBUS_INA228 = 0, GP_VBUS_RIG_NODE = 1 };
enum { GP_BENCH_STAND_UP = 0, GP_BENCH_SQUAT = 1 };

enum {
    GP_MODE_BOOT = 0,   /* configuring the motors, waiting for the sensors */
    GP_MODE_IDLE = 1,   /* sat, motors stopped, MCU_RUN low */
    GP_MODE_ARMING = 2, /* MCU_RUN high, the motors enabled */
    GP_MODE_RUN = 3,    /* balancing (robot) or the bench scenario (rig) */
    GP_MODE_JUMP = 4,
    GP_MODE_SIT = 5,    /* going down to the sit length */
    GP_MODE_SETTLE = 6, /* at the bottom, the feed-forward fading */
    GP_MODE_LIMP = 7,   /* a fault: no torque at once */
};

enum { /* why the robot last sat or limped (STATUS b6) */
    GP_R_NONE = 0,
    GP_R_STOP = 1,          /* the radio stop */
    GP_R_LINK = 2,          /* the Jetson's heartbeat lost for 2 s */
    GP_R_PEOPLE = 3,        /* people near for 2 s */
    GP_R_UVLO = 4,          /* resting voltage under 32.0 V (3.2 V a cell) */
    GP_R_JETSON = 5,        /* the Jetson asked (RUN = 0) */
    GP_R_VBUS_STALE = 6,
    GP_R_CUTOFF = 7,        /* the bus under load under 30.0 V (3.0 V a cell): latched until power cycle */
    GP_R_MOTOR_MISSING = 10,
    GP_R_MOTOR_FAULT = 11,
    GP_R_LEG_WINDOW = 12,
    GP_R_OVERVOLT = 13,
    GP_R_IMU = 14,
    GP_R_FALLEN = 15,
    GP_R_ARM_TIMEOUT = 16,
};

enum { /* why a jump was refused (FAULTS b6) */
    GP_J_OK = 0,
    GP_J_PEOPLE = 1,
    GP_J_VOLTAGE = 2,   /* resting voltage under 34.0 V (3.4 V a cell), or the cut-off latched */
    GP_J_NOT_RUNNING = 3,
    GP_J_LINK = 4,
    GP_J_HEIGHT_ZERO = 5,
};

enum { GP_JP_NONE = 0, GP_JP_CROUCH, GP_JP_PUSH, GP_JP_AIR, GP_JP_LAND, GP_JP_RECOVER };

typedef struct {
    uint8_t id;     /* CAN id */
    uint8_t bus;    /* GP_BUS_A or GP_BUS_B */
    int8_t dir;     /* +1: the motor's positive angle turns phi up */
    float phi_zero; /* rad: the leg angle at the motor's zero (rig/calibrate.py) */
} gp_motor_cal;

typedef struct {
    uint8_t profile;
    uint8_t vbus_source;
    uint8_t bench_scenario;
    uint8_t imu_required;
    gp_motor_cal motor[4];  /* left front, left rear, right front, right rear */
    uint8_t vesc_id[2];
    int8_t wheel_dir[2];    /* +1: a positive current rolls this wheel forward */
    float r_shunt;          /* ohm */
    float ina_sign;         /* -1: the low-side shunt of W30/W31 reads discharge negative */
    float r_pack;           /* ohm, the resting-voltage estimate */
    float i_cont, i_peak;   /* A: the bus current limit (GP_BUS_I_CONT_A, GP_BUS_I_PEAK_A) */
    float sit_L;            /* m */
    gp_ctl_params ctl;
} gp_config;

typedef struct {
    bool stop_run; /* the stop relay's coil is powered (the radio says run) */
} gp_inputs;

typedef struct {
    bool mcu_run;  /* drive the stop relay's low-side MOSFET */
    uint8_t led;   /* 0 off, 1 on */
} gp_outputs;

typedef struct {
    bool have, fresh, configured;
    uint8_t mode, faults, miss, boot_step, retries;
    bool req_out;
    uint32_t t_req, t_fb, t_prev;
    float p, p_prev, v, t, temp_c, vbus;
    float phi, w; /* the leg's angle and rate */
} gp_motor_state;

/* A flat view of the state for logging and the host library (hil/fwlib.py mirrors it: keep it floats and uint32s) */
typedef struct {
    uint32_t t_us, mode, reason, flags, jump_phase, jump_refusal, jumps, jumps_refused;
    uint32_t boot_mask, latched, link_ok, people, mcu_run, stop_run, uvlo_warn, uvlo_sat;
    float vbus, ibus, vrest, jump_scale, jump_v_target;
    float L[2], th[2], L_cmd[2], tau[4], wheel[2], wheel_current[2];
    float theta, theta_dot, v, x_err, height;
    float phi[4], w[4];
    uint32_t misses[4];
    uint32_t tx_drops, can_rx, imu_packets, imu_crc_errors;
    uint32_t cutoff;                         /* the 3.0 V a cell cut-off latched (until power cycle) */
    float vload, iavg, ilimit, bus_scale;    /* the cut-off's filtered bus; the current limit's average, limit, factor */
    float push_ilimit, push_scale;           /* the jump push's bus current limit and its factor on the legs */
} gp_snapshot;

typedef struct {
    gp_config cfg;
    gp_ctl ctl;
    gp_ctl_out out;
    gp_ina228_cfg ina;
    gp_vn100_parser vn;
    uint32_t now, t_mode, tick;
    uint8_t mode, reason;
    /* motors */
    gp_motor_state mot[4];
    uint32_t t_boot_retry;
    /* wheels */
    gp_vesc_status vesc[2];
    uint32_t t_vesc[2];
    bool have_vesc[2];
    float wheel_current[2];
    /* IMU */
    gp_vn100_sample imu;
    uint32_t t_imu;
    bool have_imu;
    /* bus voltage */
    float vbus, ibus, vrest;
    uint32_t t_vbus;
    bool have_vbus, uvlo_warn, uvlo_sat;
    float vload;          /* the bus under load, the cut-off's short filter */
    bool cutoff;          /* latched: only a power cycle (gp_app_init) clears it */
    /* the bus current limit */
    float iavg, ilimit, peak_used, bus_scale;
    float push_ilimit, push_scale; /* the jump's push: s(V) x GP_JUMP_I_FULL_A, a factor on the leg torques only */
    /* the stop */
    uint8_t stop_low;
    uint32_t t_stop_high;
    bool stop_run, stop_seen_run;
    /* the Jetson */
    gp_jet_setpoint sp;
    bool have_sp, run_prev, run_rise;
    uint32_t t_link;
    uint8_t jump_seq_prev;
    bool people, latched;
    uint32_t t_people;
    float hold_height, hold_lean;
    /* sitting and the bench */
    float sit_from[2], sit_T;
    uint32_t t_run;
    /* the jump */
    uint8_t jump_phase, jump_refusal;
    uint32_t t_jump, t_phase, jumps, jumps_refused;
    float jump_from, jump_v_target, jump_scale;
    bool stop_pending;
    /* diagnostics */
    uint32_t tx_drops, can_rx;
    uint8_t seq_status;
    bool mcu_run;
} gp_app;

void gp_config_default(gp_config *c, uint8_t profile);
void gp_app_init(gp_app *a, const gp_config *cfg, uint32_t now_us);
void gp_app_can_rx(gp_app *a, uint8_t bus, const gp_can_frame *f, uint32_t now_us);
void gp_app_uart_rx(gp_app *a, const uint8_t *data, size_t n, uint32_t now_us);
void gp_app_ina228(gp_app *a, const uint8_t vbus[3], const uint8_t current[3], uint32_t now_us);
void gp_app_tick(gp_app *a, uint32_t now_us, const gp_inputs *in, gp_outputs *out);
void gp_app_snapshot(const gp_app *a, gp_snapshot *s);

/* The jump gate's numbers: the take-off speed scale for a resting voltage (0 below GP_JUMP_MIN_V: refused). */
float gp_jump_scale(float vrest);

#endif
