"""The battery bay's crush pads against the side fall (issue #19): what lands, how fast, and how soft the pads must be.

    python -m sim.bay_pad_study            # needs build/sim/v2 (python -m sim.robot_v2); -> exports/body/bay-pad-study.json

sim/scenarios.py's fall_side cuts the motors and pushes the robot sideways; its 'body impact' is the largest contact
force between the base's collision geoms and the world. This study (1) runs it as modelled and names the geom that takes
the peak and the base's speed when it first touches, then (2) sweeps the bay's contact (MuJoCo solref on the
battery_bay geom: the pad's time constant) and (3) measures each setting's static stiffness (the robot resting on the
bay with the motors off: weight over penetration), so the pad can be specified as a stiffness and a stroke rather than
a sim parameter.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

import mujoco
import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
from sim import scenarios as S  # noqa: E402

BUILD = R / 'build' / 'sim' / 'v2'
OUT = R / 'exports' / 'body' / 'bay-pad-study.json'
_rec = {'peak': 0.0, 'pair': None}
_orig = mujoco.mj_contactForce


def _spy(model, data, ci, f):
    _orig(model, data, ci, f)
    c = data.contact[ci]
    if abs(f[0]) > _rec['peak']:
        _rec.update(peak=abs(float(f[0])), pair=(model.geom(c.geom1).name, model.geom(c.geom2).name), t=float(data.time),
                    depth=float(-c.dist))


def with_pad(xml: str, solref=None) -> str:
    if solref is None:
        return xml
    return re.sub(r'(<geom name="battery_bay" [^>]*?)/>', lambda m: m.group(1) + f' solref="{solref[0]} {solref[1]}"/>', xml, count=1)


def fall(xml_text, info):
    with tempfile.NamedTemporaryFile('w', suffix='.xml', dir=BUILD, delete=False) as f:
        f.write(xml_text)
        p = Path(f.name)
    try:
        _rec.update(peak=0.0, pair=None)
        mujoco.mj_contactForce = _spy
        r = S.run(p, info, S.SCENARIOS['fall_side'])
    finally:
        mujoco.mj_contactForce = _orig
        p.unlink()
    return {'body_impact_peak_n': r.get('body_impact_peak_n'), 'peak_pair': _rec['pair'], 'peak_at_s': round(_rec.get('t', 0.0), 3),
            'depth_mm_at_peak': round(_rec.get('depth', 0.0) * 1000, 2)}


def static_stiffness(xml_text):
    """The robot resting on the bay, motors off: its weight over the bay's steady penetration (N/mm)."""
    m = mujoco.MjModel.from_xml_string(xml_text)
    d = mujoco.MjData(m)
    bay = m.geom('battery_bay').id
    zb = m.geom_pos[bay][2] - m.geom_size[bay][2]
    d.qpos[2] = -zb + 0.002                         # the bay's bottom 2 mm over the floor
    mujoco.mj_forward(m, d)
    for _ in range(3000):
        d.ctrl[:] = 0.0
        mujoco.mj_step(m, d)
    pen, fz = 0.0, 0.0
    f6 = np.zeros(6)
    for ci in range(d.ncon):
        c = d.contact[ci]
        if bay in (c.geom1, c.geom2):
            pen = max(pen, -c.dist)
            _orig(m, d, ci, f6)
            fz += abs(f6[0])
    return {'bay_force_n': round(fz, 1), 'penetration_mm': round(pen * 1000, 3), 'k_n_per_mm': round(fz / (pen * 1000), 1) if pen > 0 else None}


def main():
    xml = (BUILD / 'robot.xml').read_text()
    info = json.loads((BUILD / 'model.json').read_text())
    out = {'model_kg': info.get('total_mass_kg'), 'as_modelled': fall(xml, info), 'sweep': []}
    print('as modelled:', out['as_modelled'])
    for tc in (0.02, 0.03, 0.04, 0.06, 0.08):
        x = with_pad(xml, (tc, 1.0))
        row = {'solref': [tc, 1.0], **fall(x, info), 'static': static_stiffness(x)}
        out['sweep'].append(row)
        print(row)
    OUT.write_text(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()
