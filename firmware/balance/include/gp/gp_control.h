/* The balance law: sim/controller_v2.py ControllerV2.control() (with sim/controller.py's Controller) in portable C.
 *
 *  - the wheels: a wheeled-pendulum LQR on [x - x_ref, theta, v - v_cmd, theta_dot] with K interpolated from the
 *    generated table by height, and yaw-rate control by differential torque;
 *  - each leg: a virtual spring-damper on its hip-to-axle line (length and lean) with a gravity feed-forward, mapped
 *    to the two motors by the five-bar's Jacobian;
 *  - every torque clipped to its motor's torque-speed line at the measured bus voltage; the legs also to the 60 N m cap.
 * The simulation reads its state from MuJoCo; here it comes from the sensors (gp_sense): theta is estimated from the
 * body's pitch and a centre-of-mass model of the base and the leg links (gp_model.h), v from the wheels' speeds.
 * Conventions are the simulation's: robot frame x forward, y left, z up; positive wheel torque rolls forward. */
#ifndef GP_CONTROL_H
#define GP_CONTROL_H

#include "gp/gp_fivebar.h"
#include "gp/gp_types.h"

#define GP_LEFT 0
#define GP_RIGHT 1
#define GP_FRONT 0
#define GP_REAR 1

typedef struct {
    float kp_L, kd_L, kp_th, kd_th;
} gp_leg_gains;

typedef struct {
    bool balance;       /* drive the wheels (the robot); false on the leg rig */
    gp_leg_gains legs;  /* the virtual legs */
    gp_leg_gains tuck;  /* in the air after a jump's push */
    float leg_ff_n;     /* the weight each leg holds up, N */
    float theta_trim;   /* rad added to the estimated pendulum angle (calibrated on the robot, B13) */
} gp_ctl_params;

/* sim/controller.py Command */
typedef struct {
    float height;   /* 0 = deepest crouch .. 1 = full stand */
    float speed;    /* m/s */
    float yaw_rate; /* rad/s, + = left */
    float look_up;  /* rad: lean the body back on the legs */
    float dip;      /* instant height offset (fraction) */
    float kick;     /* rad, instant lean back */
} gp_cmd;

typedef struct {
    float pitch;       /* rad, rotation about the robot's +y (left): + = nose down */
    float pitch_rate;  /* rad/s about +y */
    float roll;        /* rad, + = left side up */
    float yaw_rate;    /* rad/s about the world's +z */
    float phi[2][2];   /* [left|right][front|rear] the five-bar's motor angles, rad */
    float dphi[2][2];  /* rad/s */
    float wheel_w[2];  /* rad/s, each wheel relative to its leg about +y (+ rolls forward) */
    float vbus;        /* V: the torque-speed lines */
} gp_sense;

enum {
    GP_LEG_TRACK = 0, /* the length from the height command, levelled for roll (the simulation's law) */
    GP_LEG_LENGTH,    /* an explicit length (the bench player, the sit, the jump's crouch and landing) */
    GP_LEG_FORCE,     /* a straight push of F along the leg (the jump) */
    GP_LEG_OFF,       /* no torque */
};

typedef struct {
    uint8_t mode;
    bool tuck;       /* the tuck gains */
    float L;         /* m (GP_LEG_LENGTH) */
    float F;         /* N (GP_LEG_FORCE) */
    float ff_scale;  /* 1: the feed-forward; 0: none (in the air, settling) */
} gp_leg_cmd;

typedef struct {
    float tau[2][2];  /* leg motors, N m, the five-bar's sense */
    float wheel[2];   /* N m, + rolls forward */
    float theta, theta_dot, x_err, v, v_cmd, u, tau_yaw;
    float L_cmd[2];
    gp_fb_polar leg[2];
    bool leg_ok[2];
    uint8_t clipped;  /* bit per output that the torque limit cut: 0-3 legs (LF LR RF RR), 4-5 wheels */
} gp_ctl_out;

typedef struct {
    gp_ctl_params p;
    float height, dh, look, v_cmd, x_err;
} gp_ctl;

void gp_ctl_init(gp_ctl *c, const gp_ctl_params *p);
/* Start from a stance: the height state at the given fraction, the slews and the position reference zeroed. */
void gp_ctl_reset(gp_ctl *c, float height);
void gp_ctl_step(gp_ctl *c, const gp_sense *s, const gp_cmd *cmd, const gp_leg_cmd leg[2], bool wheels, gp_ctl_out *o);

float gp_ctl_height_m(float frac);
float gp_ctl_height_frac(float L);
void gp_ctl_lqr_gains(float height, float K[4]);

/* The motors' torque limits (sim/leg_control.py clip_motor, sim/controller.py clip_torque) */
float gp_clip_motor(float tau, float omega, float peak, float omega_max, float cap);

/* The pendulum angle (rad, + = the centre of mass ahead of the axle) and its rate from the stance and the pitch. */
bool gp_ctl_theta(const gp_sense *s, float *theta, float *theta_dot);

#endif
