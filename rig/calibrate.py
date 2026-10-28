"""Zero the leg's two motors and find their directions: rig/calibration.json, which rig/can_bus.py maps angles with.

    python -m rig.calibrate --iface can0            # after the upper links are on, before the knees (assembly step 11)
    python -m rig.calibrate --iface can0 --check    # the leg's angles and length as the motors report them now

Each motor in turn: the operator holds its upper link against its BARE knee-out stop post (the TPU sleeves are not on
yet: steel on PA6-CF is a repeatable contact; a sleeve would squeeze), the motor's zero is set there (type 6), then the
operator swings the link to its bare knee-in post: the reading there gives the motor's direction and checks the travel
against the CAD (fivebar's stop posts and link outline, the posts' 10 mm shoulders): within 3 deg or it stops.
zero_sta = 1 is written and saved so a power-on angle reads -pi..pi.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from rig import rs04 as P
from rig.can_bus import CAL_FILE, Calibration, MotorCal

R = Path(__file__).resolve().parents[1]
if str(R / 'cad') not in sys.path:
    sys.path.insert(0, str(R / 'cad'))
import fivebar as fb  # noqa: E402

BARE_R = 5.0                       # mm: the ISO 7379 10 mm shoulder of a stop post without its sleeve
TOL_DEG = 3.0


def bare_contact_half_angle(radius: float = BARE_R) -> float:
    """t (deg): a post of this radius at stop_r touches the upper link's edge when the link's axis is t from the post's
    direction (fivebar.stop_post_angles() with the sleeve's radius gives the designed stops)."""
    r = fb.P['stop_r']
    lo, hi = 0.0, math.pi / 2
    for _ in range(60):
        t = (lo + hi) / 2
        if r * math.sin(t) < fb.upper_half_width(r * math.cos(t)) + radius:
            lo = t
        else:
            hi = t
    return math.degrees(hi)


def bare_stop_angles():
    """(front out, front in, rear out, rear in), radians: where each upper link rests on its bare posts (the rear's
    continuous angles, -183 .. -83 deg with the sleeves)."""
    a_out, a_in = fb.stop_post_angles()
    t = bare_contact_half_angle()
    fo, fi = math.radians(a_out - t), math.radians(a_in + t)
    return fo, fi, -math.pi - fo, -math.pi - fi


def calibrate(bus: P.RS04Bus, front_id: int = 1, rear_id: int = 2, ask=input, out=print) -> Calibration:
    fo, fi, ro, ri = bare_stop_angles()
    cals = {}
    for name, mid, phi_out, phi_in in (('front', front_id, fo, fi), ('rear', rear_id, ro, ri)):
        m = P.Motor(bus, mid)
        m.stop()
        m.write_check('zero_sta', 1)
        ask(f'{name} motor (id {mid}): hold its upper link against its BARE knee-out post, then press Enter ')
        m.zero()
        p0 = m.read('mechPos')
        if abs(p0) > math.radians(0.5):
            raise RuntimeError(f'{name}: the zero did not take (reads {math.degrees(p0):.2f} deg)')
        ask(f'{name} motor: swing the link to its BARE knee-in post, hold it there, press Enter ')
        p1 = m.read('mechPos')
        want = phi_in - phi_out
        if abs(abs(p1) - abs(want)) > math.radians(TOL_DEG):
            raise RuntimeError(f'{name}: {math.degrees(abs(p1)):.1f} deg between the posts, the CAD says {math.degrees(abs(want)):.1f}: '
                               'check the posts, the link on its dowels, the motor\'s lugs')
        d = 1 if (p1 > 0) == (want > 0) else -1
        cals[name] = MotorCal(mid, d, phi_out)
        m.save()
        out(f'{name}: zero at {math.degrees(phi_out):.2f} deg (bare knee-out post), direction {d:+d}, travel {math.degrees(abs(p1)):.1f} deg '
            f'(CAD {math.degrees(abs(want)):.1f})')
    cal = Calibration(cals['front'], cals['rear'], 'zero on the bare knee-out posts (rig/calibrate.py); fivebar lug clock '
                      f'{fb.lug_clock()[0]} deg')
    return cal


def check(bus: P.RS04Bus, cal: Calibration, out=print) -> tuple:
    from rig.leg_control import polar
    phis = []
    for mc in (cal.front, cal.rear):
        phis.append(mc.to_leg(P.Motor(bus, mc.id).read('mechPos')))
    L, th = polar(phis[0], phis[1], 0.0, 0.0)[:2]
    out(f'front {math.degrees(phis[0]):.2f} deg, rear {math.degrees(phis[1]):.2f} deg: leg {L * 1000:.1f} mm, lean {math.degrees(th):.1f} deg')
    return phis, L


def main(argv=None, transport=None, ask=input, out=print) -> int:
    ap = argparse.ArgumentParser(prog='python -m rig.calibrate')
    ap.add_argument('--iface', default='can0')
    ap.add_argument('--front-id', type=int, default=1)
    ap.add_argument('--rear-id', type=int, default=2)
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--file', default=str(CAL_FILE))
    a = ap.parse_args(argv)
    if transport is None:
        from rig.canio import SocketCan
        transport = SocketCan(a.iface)
    bus = P.RS04Bus(transport)
    if a.check:
        check(bus, Calibration.load(Path(a.file)), out)
        return 0
    cal = calibrate(bus, a.front_id, a.rear_id, ask, out)
    cal.save(Path(a.file))
    out(f'wrote {a.file}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
