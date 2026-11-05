/* The leg's guards (docs/leg-protection.md): the soft stops, the commanded leg-length window by lean, the measured-angle
 * window and each motor's rms torque. A port of sim/leg_limits.py (soft_stop, approach_limit, window_at); the numbers are
 * generated into gp_limits.h from exports/leg/limits.json. Portable, no state of its own. */
#ifndef GP_GUARD_H
#define GP_GUARD_H

#include "gp/gp_types.h"

/* The torque set a leg build runs with (gp_limits.h), N m and s. */
typedef struct {
    uint8_t build;        /* GP_BUILD_PLA_BENCH or GP_BUILD_ROBOT */
    float everyday_nm;    /* the cap in any pose, outside the jump's push */
    float peak_nm;        /* the cap in the jump's push (the legs mid-range), at most GP_LIM_PEAK_MAX_S */
    float motor_nm;       /* each RS-04's limit_torque, written and read back at boot */
    float rms_nm;         /* a motor's rms torque over GP_LIM_RMS_TAU_S: over it, the cap comes down to it */
} gp_torque_limits;

void gp_guard_limits(uint8_t build, gp_torque_limits *t);

/* The fastest a motor may approach a stop d rad away (rad/s): it meets the stop no faster than the stop takes at the
 * every-day torque (1/2 J w^2 = T^2 / 2k), braking at the every-day torque on the way. */
float gp_guard_approach(float d, float everyday_nm);

/* One motor's torque with its soft stops at lo and hi (rad; + torque and + speed towards hi): inside the margin no
 * torque into a stop; anywhere, faster than gp_guard_approach() towards a stop brakes. */
float gp_guard_soft_stop(float tau, float phi, float omega, float lo, float hi, float everyday_nm);

/* The leg lengths (m) the controller may be commanded at a lean (rad, + = wheel forward): between the window's rows,
 * linear; past its ends, the end rows. */
void gp_guard_window(float lean, float *L_min, float *L_max);
/* L clamped to the overlap of the windows at the commanded lean and the leg's measured lean */
float gp_guard_clamp_L(float L, float lean, float lean_measured);

/* The least angle (rad) between a link pair of the five-bar that lines up at a dead point (each knee, the apex); 0
 * where the lower links cannot meet (sim/leg_limits.py dead_point_margin). */
float gp_guard_dead_margin(float phi1, float phi2);

/* The largest |yaw rate| (rad/s) at a ground speed v (m/s; the larger of the commanded and the measured): the outer
 * wheel inside vmax (the speed clamp's) and the lateral acceleration inside GP_LIM_YAW_A_LAT (sim/leg_limits.py
 * yaw_rate_limit). */
float gp_guard_yaw_limit(float v, float vmax);
/* a commanded yaw rate clamped to it (never refused) */
float gp_guard_yaw_rate(float yaw_rate, float v, float vmax);

/* true while a motor's angle is no further past a hard stop than GP_LIM_ANGLE_WINDOW_RAD */
bool gp_guard_angle_ok(float phi, float lo, float hi);

/* A motor's mean square torque, first order over GP_LIM_RMS_TAU_S; returns the rms (N m). */
float gp_guard_rms(float *ms, float tau, float dt);

#endif
