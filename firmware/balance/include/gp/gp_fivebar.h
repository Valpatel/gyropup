/* The five-bar leg's kinematics (cad/fivebar.py fk / ik / jacobian and sim/leg_control.py polar / vmc_from_state), in
 * metres and radians, single precision, no platform code.
 *
 * The leg's plane is the robot's x-z plane (x forward, z up), the origin midway between the two motor axes:
 * the front motor A at (+D/2, 0), the rear B at (-D/2, 0). phi1 (front) and phi2 (rear) are the upper links' angles
 * from +x towards +z; the rear runs continuously from -183 to -83 deg. E is the wheel axle. */
#ifndef GP_FIVEBAR_H
#define GP_FIVEBAR_H

#include "gp/gp_types.h"

typedef struct {
    float x, z;
} gp_v2;

typedef struct {
    gp_v2 A, B, C, D, E; /* m */
} gp_fb_joints;

/* The virtual leg: hip midpoint to axle. */
typedef struct {
    float L;          /* m */
    float th;         /* rad, + = the wheel forward of the hips */
    float dL, dth;    /* m/s, rad/s */
    float J[2][2];    /* dE/dphi, m/rad: J[row x|z][col phi1|phi2] */
    float x, z;       /* the axle, m */
} gp_fb_polar;

/* Joint points for two motor angles; false when the lower links cannot meet. */
bool gp_fb_fk(float phi1, float phi2, gp_fb_joints *j);

/* dE/dphi from the closure (E - C).(dE - dC) = 0, (E - D).(dE - dD) = 0: exact, on either branch.
 * False at a dead point (the lower links in line). */
bool gp_fb_jacobian(float phi1, float phi2, const gp_fb_joints *j, float J[2][2]);

/* Motor angles that put the axle at (x, z), knees out (cad/fivebar.py ik); false if out of reach. */
bool gp_fb_ik(float x, float z, float phi[2]);

/* Motor angles for a leg length and lean (cad/fivebar.py stance). */
bool gp_fb_stance(float L, float lean, float phi[2]);

/* The virtual leg's state from the motor angles and rates. */
bool gp_fb_polar_state(float phi1, float phi2, float dphi1, float dphi2, gp_fb_polar *p);

/* Motor torques (front, rear; N m) for a force F along the leg (+ = pushing the axle away from the hips) and a torque
 * T about the hips on its lean: tau = J^T (F uL + T / L uth). */
void gp_fb_vmc(const gp_fb_polar *p, float F, float T, float tau[2]);

#endif
