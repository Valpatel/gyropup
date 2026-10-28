"""The leg's controller with no simulator in it: the virtual leg from the two hip angles, the virtual-model control law
and the RS-04's torque-speed limit. sim/leg_rig.py drives MuJoCo with it; the real rig (docs/leg-prototype-plan.md)
drives two RS-04s with it from their measured angles.

Angles are the five-bar's (cad/fivebar.py): phi1 the front hip, phi2 the rear, radians, rates in rad/s.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import fivebar as fb  # noqa: E402


def clip_motor(tau, omega, peak, omega_max, cap=None):
    """A motor's torque limit at a speed: the full peak when braking, falling to zero at omega_max when driving;
    then the firmware's cap."""
    lim = peak if tau * omega <= 0 else peak * max(0.0, 1.0 - abs(omega) / omega_max)
    if cap:
        lim = min(lim, cap)
    return max(-lim, min(lim, tau))


@dataclass
class Gains:
    kp_L: float = 3000.0          # N/m on the virtual leg's length
    kd_L: float = 250.0
    kp_th: float = 150.0          # N m/rad on its lean
    kd_th: float = 6.0


def polar(phi1: float, phi2: float, dphi1: float = 0.0, dphi2: float = 0.0):
    """The virtual leg from the hip angles: length (m), lean (rad, + = wheel forward), their rates, the Jacobian
    d(x, z)/d(phi) (m/rad) and the axle's (x, z) (m) from the hip axes' midpoint."""
    E = fb.fk(phi1, phi2)['E']
    J = np.array(fb.jacobian(phi1, phi2)) / 1000.0
    x, z = E[0] / 1000, E[1] / 1000
    dx, dz = J @ np.array([dphi1, dphi2])
    L = math.hypot(x, z)
    th = math.atan2(x, -z)
    dL = (x * dx + z * dz) / L
    dth = (-z * dx + x * dz) / (L * L)
    return L, th, dL, dth, J, (x, z)


def vmc_from_state(phi, dphi, L_cmd, th_cmd=0.0, ff=0.0, g: Gains = Gains(), force=None):
    """Hip torques (front, rear; N m) for a virtual spring-damper leg, or a straight push of `force` N along it.
    ff is a feed-forward along the leg (N): the weight it holds up."""
    L, th, dL, dth, J, _ = polar(phi[0], phi[1], dphi[0], dphi[1])
    F = force if force is not None else g.kp_L * (L_cmd - L) - g.kd_L * dL + ff
    T = g.kp_th * (th_cmd - th) - g.kd_th * dth
    uL = np.array([math.sin(th), -math.cos(th)])
    uth = np.array([math.cos(th), math.sin(th)])
    FE = F * uL + (T / L) * uth                                  # the force the leg puts on the ground at the axle
    return J.T @ FE
