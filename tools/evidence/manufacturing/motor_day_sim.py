"""Motor day: the rig simulation at the day-one torque caps (docs/motor-day.md, issue #156).

    .venv/bin/python tools/motor_day_sim.py            # ~6 min on one core -> exports/motor-day/sim.json

The rig's own controller and MuJoCo model (rig/run.py run_sim, sim/leg_rig.py) with the jump's push capped at each
day-one cap, at the lightest mass the model can carry (the leg and the carriage with no ballast: the boom stand is
ballasted to the same mass, docs/motor-day.md). The stand-up and the squat run at the ladder's stand cap; the power
cut runs with the floor stop where the rig's bumpers are (140 mm), as the stand's floor stop is set.

tools/motor_day.py reads the loads from this file and scales the leg's FEA record (exports/leg/fea/summary.json) to PLA.
"""
from __future__ import annotations

# Support direct-file CLI execution as well as checkout package imports.
if __package__ in (None, ''):
    import sys as _checkout_sys
    from pathlib import Path as _CheckoutPath
    _checkout_sys.path.insert(0, str(_CheckoutPath(__file__).resolve().parents[3]))


import dataclasses
import json
import sys
import time
from pathlib import Path

R = (Path(__file__).resolve().parents[3])
sys.path.insert(0, str(R))
from software.control.rig import leg_control as lc, run  # noqa: E402

OUT = (R / 'hardware/exports/motor-day')
JUMP_CAPS = (12.0, 15.0, 20.0, 25.0, 30.0, 40.0)   # N m at the motors (limit_torque) and in the laptop's clip
STAND_CAP = 12.0                                    # the stand-up, squat and power-cut rungs: no rung above the
                                                    # PLA cap (tools/motor_day.py refuses a stand cap above it)
KEYS = ('jump_height_mm', 'peak_motor_nm', 'peak_axle_force_n', 'peak_wheel_force_n', 'peak_knee_pin_n', 'peak_gearbox_nm',
        'peak_stop_nm', 'stop_hits', 'L_range_mm', 'peak_joint_force_n', 'peak_front_link_n', 'peak_motor_speed_rad_s')


def _clean(v):
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    try:
        return round(float(v), 2) if not isinstance(v, (bool, str)) and v is not None else v
    except (TypeError, ValueError):
        return v


def one(test: str, cap: float | None, mass: float) -> dict:
    base = lc.SCENARIOS[test]
    lc.SCENARIOS[test] = dataclasses.replace(base, cap=cap)
    try:
        t0 = time.time()
        o = run.run_sim(test, mass, 500.0, run.pack_for(test), 1, rail_low=run.BUMPER_CONTACT_M, save=False)
    finally:
        lc.SCENARIOS[test] = base
    res = o['results']
    row = {k: _clean(res.get(k)) for k in KEYS}
    row.update(test=test, cap_nm=cap, rig=_clean(res.get('rig')), seconds=round(time.time() - t0, 1))
    print(f"  {test:10} cap {cap}: jump {row['jump_height_mm']} axle {row['peak_axle_force_n']} knee "
          f"{row['peak_joint_force_n']} gearbox {row['peak_gearbox_nm']} stop {row['peak_stop_nm']}", flush=True)
    return row


def floor_mass() -> float:
    """The lightest the model carries: its leg and its carriage with no ballast (sim/leg_rig.py mjcf's dummy at 0). The
    controller's feed-forward is set from the mass it is given, so it is given this, not less."""
    from software.simulation.leg_rig import mjcf
    info = mjcf(0.0)[1]
    return round(info['moving_kg'] + info['frame_kg'], 3)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    m = floor_mass()
    rows = [one('jump', c, m) for c in JUMP_CAPS]
    rows += [one(t, STAND_CAP, m) for t in ('stand_up', 'squat', 'power_off', 'power_off_damped')]
    mass = rows[0]['rig']
    doc = {'made_by': 'tools/motor_day_sim.py', 'controller': 'rig/leg_control.py on rig/sim_bus.py (MuJoCo, sim/leg_rig.py)',
           'rate_hz': 500.0, 'latency_ticks': 1, 'pack': 'rig/run.py pack_for (the FLEXVOLT pair at the start rule)',
           'floor_stop_leg_mm': run.BUMPER_CONTACT_M * 1000,
           'mass_kg': round(mass['moving_kg'] + mass['frame_kg'] + mass['dummy_kg'], 2), 'mass': mass,
           'note': 'the model\'s leg is the PA6-CF leg with its BotWheel; the day-one leg is PLA with a printed foot. '
                   'The mass the stand is ballasted to is this total.',
           'runs': rows}
    (OUT / 'sim.json').write_text(json.dumps(doc, indent=1) + '\n')
    print(f'-> {OUT / "sim.json"}')


if __name__ == '__main__':
    main()
