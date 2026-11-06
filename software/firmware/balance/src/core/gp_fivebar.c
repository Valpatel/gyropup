/* The five-bar leg's kinematics: a port of cad/fivebar.py (fk, ik, stance) and sim/leg_control.py (polar,
 * vmc_from_state). The Jacobian is analytic here where fivebar.jacobian() differences fk() numerically; the unit tests
 * hold the two to each other. */
#include "gp/gp_fivebar.h"

#include <math.h>

#include "gp/gp_model.h"

#define PI_F 3.14159265358979f

bool gp_fb_fk(float phi1, float phi2, gp_fb_joints *j)
{
    const float l1 = GP_FB_L1_M, l2 = GP_FB_L2_M;
    j->A.x = 0.5f * GP_FB_D_M;
    j->A.z = 0.0f;
    j->B.x = -0.5f * GP_FB_D_M;
    j->B.z = 0.0f;
    j->C.x = j->A.x + l1 * cosf(phi1);
    j->C.z = l1 * sinf(phi1);
    j->D.x = j->B.x + l1 * cosf(phi2);
    j->D.z = l1 * sinf(phi2);
    const float vx = j->C.x - j->D.x, vz = j->C.z - j->D.z;
    const float r = sqrtf(vx * vx + vz * vz);
    if (r > 2.0f * l2 || r < 1e-9f) {
        return false;
    }
    const float mx = 0.5f * (j->C.x + j->D.x), mz = 0.5f * (j->C.z + j->D.z);
    const float h = sqrtf(fmaxf(0.0f, l2 * l2 - 0.25f * r * r));
    const float nx = -vz / r, nz = vx / r;
    const float e1z = mz + h * nz, e2z = mz - h * nz;
    if (e1z < e2z) { /* the apex below the knees */
        j->E.x = mx + h * nx;
        j->E.z = e1z;
    } else {
        j->E.x = mx - h * nx;
        j->E.z = e2z;
    }
    return true;
}

bool gp_fb_jacobian(float phi1, float phi2, const gp_fb_joints *j, float J[2][2])
{
    const float l1 = GP_FB_L1_M;
    const float ax = j->E.x - j->C.x, az = j->E.z - j->C.z; /* a = E - C */
    const float bx = j->E.x - j->D.x, bz = j->E.z - j->D.z; /* b = E - D */
    const float det = ax * bz - az * bx;
    if (fabsf(det) < 1e-9f) {
        return false;
    }
    /* dC/dphi1 and dD/dphi2 */
    const float c1x = -l1 * sinf(phi1), c1z = l1 * cosf(phi1);
    const float c2x = -l1 * sinf(phi2), c2z = l1 * cosf(phi2);
    const float r1 = ax * c1x + az * c1z; /* a . dC */
    const float r2 = bx * c2x + bz * c2z; /* b . dD */
    /* [ax az; bx bz] dE = [r1 dphi1; r2 dphi2]  ->  dE = M^-1 [...] */
    J[0][0] = (bz * r1) / det;
    J[1][0] = (-bx * r1) / det;
    J[0][1] = (-az * r2) / det;
    J[1][1] = (ax * r2) / det;
    return true;
}

bool gp_fb_ik(float x, float z, float phi[2])
{
    const float l1 = GP_FB_L1_M, l2 = GP_FB_L2_M;
    const float px[2] = {0.5f * GP_FB_D_M, -0.5f * GP_FB_D_M};
    const float side[2] = {1.0f, -1.0f};
    for (int k = 0; k < 2; k++) {
        const float vx = x - px[k], vz = z;
        const float r = sqrtf(vx * vx + vz * vz);
        if (r > l1 + l2 || r < fabsf(l1 - l2) || r < 1e-9f) {
            return false;
        }
        const float a = (l1 * l1 - l2 * l2 + r * r) / (2.0f * r);
        const float h = sqrtf(fmaxf(0.0f, l1 * l1 - a * a));
        const float mx = px[k] + a * vx / r, mz = a * vz / r;
        const float c1x = mx - h * vz / r, c1z = mz + h * vx / r;
        const float c2x = mx + h * vz / r, c2z = mz - h * vx / r;
        const bool first = (c1x - c2x) * side[k] > 0.0f;
        const float cx = first ? c1x : c2x, cz = first ? c1z : c2z;
        float ang = atan2f(cz, cx - px[k]);
        if (side[k] < 0.0f && ang > 0.0f) {
            ang -= 2.0f * PI_F; /* the rear link's angles run continuously from -183 to -83 deg */
        }
        phi[k] = ang;
    }
    return true;
}

bool gp_fb_stance(float L, float lean, float phi[2])
{
    return gp_fb_ik(L * sinf(lean), -L * cosf(lean), phi);
}

bool gp_fb_polar_state(float phi1, float phi2, float dphi1, float dphi2, gp_fb_polar *p)
{
    gp_fb_joints j;
    if (!gp_fb_fk(phi1, phi2, &j) || !gp_fb_jacobian(phi1, phi2, &j, p->J)) {
        return false;
    }
    const float x = j.E.x, z = j.E.z;
    const float dx = p->J[0][0] * dphi1 + p->J[0][1] * dphi2;
    const float dz = p->J[1][0] * dphi1 + p->J[1][1] * dphi2;
    const float L = sqrtf(x * x + z * z);
    p->x = x;
    p->z = z;
    p->L = L;
    p->th = atan2f(x, -z);
    p->dL = (x * dx + z * dz) / L;
    p->dth = (-z * dx + x * dz) / (L * L);
    return true;
}

void gp_fb_vmc(const gp_fb_polar *p, float F, float T, float tau[2])
{
    const float s = sinf(p->th), c = cosf(p->th);
    /* uL = (sin th, -cos th): hips to axle; uth = (cos th, sin th) */
    const float fx = F * s + (T / p->L) * c;
    const float fz = -F * c + (T / p->L) * s;
    tau[0] = p->J[0][0] * fx + p->J[1][0] * fz;
    tau[1] = p->J[0][1] * fx + p->J[1][1] * fz;
}
