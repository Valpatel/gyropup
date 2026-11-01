"""The leg's strength cases load each part with forces and torques that balance the wheel's (cad/leg_studies.py).

    .venv/bin/python -m pytest cad/test_leg_loads.py -q
"""
import math
import sys
from pathlib import Path

import pytest

R = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(R / 'cad'), str(R)]

import fivebar as fb  # noqa: E402
import leg_studies as ls  # noqa: E402
from sim.leg_rig import pin_forces  # noqa: E402


@pytest.mark.parametrize('h, lean', [(300.0, 0.0), (342.3, 0.0), (220.0, 12.0), (180.0, -15.0)])
def test_motor_torques_match_virtual_work(h, lean):
    """The motors' real torques on their links: tau_k = -F . dE/dphi_k for a force F on the axle. pin_forces' tau_front
    is that torque; its tau_rear is minus it (both in its x-z cross convention), which motor_reactions_y undoes."""
    phi = fb.stance(h, lean)
    F = (40.0, 460.0)
    pf = pin_forces(*phi, F, at_axle=True)
    J = fb.jacobian(*phi)
    tau = [-(F[0] * J[0][k] + F[1] * J[1][k]) / 1000.0 for k in range(2)]
    assert pf['tau_front'] == pytest.approx(tau[0], rel=1e-5)
    assert pf['tau_rear'] == pytest.approx(-tau[1], rel=1e-5)


@pytest.mark.parametrize('key', ['R1', 'E1', 'R3'])
def test_hip_frame_loads_balance_the_wheel(key):
    """The hip frame's in-plane loads (both upper links' pin forces at the motor axes, the motors' reactions on their
    lugs) add up to the wheel's in-plane force and its moment about the hip midpoint: nothing the leg does not carry."""
    c = ls.cases()[key]
    ld = c['loads']
    E = ld['j']['E']
    Fx, _, Fz = c['Fw3']
    (ax, _), (bx, _) = fb.motors()
    Ff, Fr = ld['F_C_on_upper'], ld['F_D_on_upper']
    tf, tr = ls.motor_reactions_y(ld)
    assert Ff[0] + Fr[0] == pytest.approx(Fx, abs=1e-6)
    assert Ff[1] + Fr[1] == pytest.approx(Fz, abs=1e-6)
    my_applied = (-ax * Ff[1] - bx * Fr[1]) / 1000.0 + tf + tr       # about +y: z Fx - x Fz, the pins at z = 0
    my_wheel = (E[1] * Fx - E[0] * Fz) / 1000.0
    assert my_applied == pytest.approx(my_wheel, abs=1e-6)
    if key == 'E1':                                                  # a straight stance: the two reactions cancel
        assert tf == pytest.approx(-tr, rel=1e-9) and math.isclose(abs(tf), 46.48, abs_tol=0.05)
