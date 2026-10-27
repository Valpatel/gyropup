"""The legs' forces on the body at the body's real mass: the leg rig (sim/leg_rig.py, the leg workstream's) run at half
the robot's total from the mass ledger, through its public run() (nothing of the leg's is written).

    .venv/bin/python cad/body_legloads.py [--half-mass 15.2]   # -> exports/body/leg-loads.json

docs/body-plan.md T4 asks the rig at half of T3's real mass: the body's strength cases take their loads from here.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
sys.path.insert(0, str(R / 'cad'))
OUT = R / 'exports' / 'body' / 'leg-loads.json'
KEYS = ('peak_motor_nm', 'peak_motor_speed_rad_s', 'peak_wheel_force_n', 'peak_axle_force_n', 'peak_knee_pin_n', 'peak_gearbox_nm',
        'peak_stop_nm', 'jump_height_mm', 'L_range_mm', 'peak_joint_force_n', 'pose_at_peak_axle_force')
RARE = ('jump', 'jump_peak', 'drop_150')          # events the body is designed for at SF >= 2
FAULT = ('power_off',)                            # the undamped power cut (D39's fault case): SF >= 1.2


def half_mass_from_ledger():
    m = json.loads((R / 'exports/body/mass.json').read_text())['P3']['total_kg']
    return round(m / 2, 2)


def run(half_mass: float) -> dict:
    from sim import leg_rig as lr
    out = {'half_mass_kg': half_mass, 'robot_kg': round(2 * half_mass, 2), 'source': 'sim/leg_rig.py run() at this half mass',
           'rig_committed_half_mass_kg': lr.HALF_MASS, 'scenarios': {}}
    for name, sc in lr.SCENARIOS.items():
        r = lr.run(sc, half_mass)
        out['scenarios'][name] = {k: r.get(k) for k in KEYS}
    sc = out['scenarios']
    out['rare'] = max((sc[n]['peak_axle_force_n'], n) for n in RARE if n in sc)
    out['fault'] = max((sc[n]['peak_axle_force_n'], n) for n in FAULT if n in sc)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--half-mass', type=float)
    a = ap.parse_args()
    hm = a.half_mass or half_mass_from_ledger()
    t0 = time.time()
    d = run(hm)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(d, indent=1) + '\n')
    print(f"half mass {hm} kg: rare {d['rare']}, fault {d['fault']} ({time.time() - t0:.0f} s)")


if __name__ == '__main__':
    main()
