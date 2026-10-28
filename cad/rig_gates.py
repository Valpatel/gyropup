"""The rig's integrity on cad-agent's gates (cadagent.gates, issue #14), run at the end of cad/build_rig.py, which fails
when a gate fails:

    .venv/bin/python cad/rig_gates.py          # -> exports/rig/gates/*.json, .md, .dot; exit 1 on a failure

- **connectivity** (cadagent.gates.connectivity): three groups. The static frame is grounded on the base's side members;
  the carriage body is the plate, blocks, ballast and screws with the leg's frame and motors; the linkage body is the
  leg's links and wheel. Each must be one connected group. The carriage rides four slider joints, its blocks on the
  rails; the linkage rides the two hip joints on the output adapters. Every screw of rig_hardware's joint table is a
  declared fastener, from what it clamps into its drop-in nut, insert or tapped part.
- **motion** (cadagent.gates.motion): the carriage, with the leg folded at 110 mm and carried with it, slides its whole
  travel, from the bumpers' contact to the top stop's. Nothing may collide.
- **leg_range** (the relation table, cadagent.gates.relations, at each pose): the leg over its range with the wheel on
  the deck, at -20, 0 and +20 deg of lean (the five-bar is a closed loop the motion gate does not sample). Nothing may
  interfere.
- **screws** (rig_hardware's stacks): each screw's length against the stack it clamps, until the fastener gate's tool
  sweep has the assembly steps.

What is excused, and why, is the declarations below (intended overlaps); nothing else is.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_rig as br  # noqa: E402
import fivebar as fb  # noqa: E402
import rig_hardware as hw  # noqa: E402
import rig_parts as rp  # noqa: E402

GATES = br.OUT / 'gates'
CACHE = br.R / '.cadagent-cache' / 'gates'
GROUND = ['side_left', 'side_right']
FOLDED_MM = 110.0                       # the leg while the carriage travels: the wheel clears the deck on the bumpers

# The leg's own model (cad/fivebar.py, the main session's): its fits are drawn as overlaps.
LEG_OVERLAPS = {
    ('leg_upper_link_front', 'leg_eye_sleeve_front'): 'the DIN 179 sleeves are a press fit in the eye (0.04 mm on Ø18)',
    ('leg_upper_link_rear', 'leg_eye_sleeve_rear'): 'the same press fit',
    ('leg_output_adapter_front', 'leg_screws_links'): 'the link screws\' threads in the adapter\'s tapped holes (drawn solid)',
    ('leg_output_adapter_rear', 'leg_screws_links'): 'the same',
    ('leg_motor_front', 'leg_screws_lugs'): 'the lug screws\' threads in the motor (an envelope)',
    ('leg_motor_rear', 'leg_screws_lugs'): 'the same',
    ('leg_motor_front', 'leg_screws_outputs'): 'the output screws\' threads in the motor\'s flange (an envelope)',
    ('leg_motor_rear', 'leg_screws_outputs'): 'the same',
    ('leg_wheel_link', 'leg_screws_wheel'): 'the wheel screws\' threads (drawn through the link)',
    ('leg_wheel_link', 'leg_wheel_hub'): 'W2 (#25): the 10 in hub wheel\'s axle mount replaces the BotWheel\'s flange; until '
                                         'then its envelope sits on the old foot',
    ('leg_screws_wheel', 'leg_wheel_hub'): 'the same (W2, #25)',
    ('leg_wheel_link', 'leg_wheel_tyre'): 'the same (W2, #25): the 54 mm tyre on the BotWheel\'s mid-plane',
}


def intended(J) -> list:
    out = [{'parts': list(k), 'reason': v} for k, v in LEG_OVERLAPS.items()]
    for j in J:
        k = j['thread_in']['kind']
        if k in ('tapped', 'wood'):
            out.append({'parts': [j['name'], j['holds'][1]], 'reason': f"its thread in {j['holds'][1]} (drawn at the minor)"})
        if k == 'insert':
            out.append({'parts': [hw.receiver_name(j), j['holds'][1]], 'reason': 'a heat-set insert\'s knurl in its pilot'})
    return out


def assembly(zh: float, L: float, lean: float = 0.0, plates: int = 1):
    from cadagent.gates.relations import Assembly
    fixed = br.fixed_parts(hardware=True)
    car = br.carriage_parts(zh, n_plates=plates, hardware=True)
    leg = br.leg_parts(L, lean, zh)
    asm = Assembly()
    for n, s in fixed.items():
        asm.add(n, s.val() if hasattr(s, 'val') else s)
    for n, s in car.items():
        asm.add(n, s.val() if hasattr(s, 'val') else s, body='carriage')
    for n, (s, k) in leg.items():
        asm.add(n, s, body='carriage' if k == 'static' else 'linkage')
    return asm


def joints(zh: float) -> dict:
    J = {f'slide_{sx:+d}{sz:+d}': {'kind': 'slider', 'moving': f'block_{sx:+d}{sz:+d}',
                                    'fixed': f'rail_{"left" if sx < 0 else "right"}'} for sx in (-1, 1) for sz in (-1, 1)}
    for side in ('front', 'rear'):
        J[f'hip_{side}'] = {'kind': 'revolute', 'moving': f'leg_upper_link_{side}', 'fixed': f'leg_output_adapter_{side}'}
    return J


def declarations(J, zh: float):
    from cadagent.gates.connectivity import Declarations
    fasteners = {j['name']: {'clamps': j['holds'][0], 'into': hw.receiver_name(j)} for j in J}
    return Declarations(grounded=GROUND, joints=joints(zh), fasteners=fasteners, intended_overlaps=intended(J),
                        max_joint_gap_mm=0.5)


def connectivity(cache) -> dict:
    from cadagent.gates.connectivity import connectivity_gate
    from cadagent.gates.relations import Tolerances
    zh = br.zh_on_deck(300.0)
    J = hw.joints(zh)
    asm = assembly(zh, 300.0)
    return connectivity_gate(asm, declarations(J, zh), tol=Tolerances(touch_mm=0.05), cache=cache,
                             out=GATES / 'connectivity.json')


def motion(cache) -> dict:
    """The carriage's travel with the leg folded, as cadagent.gates.motion samples a slider."""
    from cadagent.gates.motion import motion_gate
    from cadagent.gates.relations import Tolerances
    zb = br.zh_on_deck(rp.BUMPER['contact_leg_mm'])                     # resting on the bumpers
    zt = rp.top_stop_z(br.RAIL_TOP) - rp.PLATE_H / 2                    # the plate's top edge at the top stop
    J = hw.joints(zb)
    asm = assembly(zb, FOLDED_MM)
    (ax, _), _ = fb.motors()
    js = {'slide': {'kind': 'slider', 'moving': 'block_-1-1', 'fixed': 'rail_left', 'axis': ((0.0, 0.0, zb), (0.0, 0.0, 1.0)),
                    'range_mm': [0.0, round(zt - zb - 0.5, 1)], 'samples': 40},
          'hip_front': {'kind': 'revolute', 'moving': 'leg_upper_link_front', 'fixed': 'leg_output_adapter_front',
                        'axis': ((ax, 0.0, zb), (0.0, 1.0, 0.0)), 'range_deg': [0.0, 0.0]}}
    contacts = [(f'block_{sx:+d}{sz:+d}', f'rail_{"left" if sx < 0 else "right"}') for sx in (-1, 1) for sz in (-1, 1)]
    contacts += [('carriage_plate', f'bumper_cap_{s}') for s in ('left', 'right')]   # it rests on them at the bottom
    return motion_gate(asm, js, tol=Tolerances(touch_mm=0.05), cache=cache, intended_contacts=contacts,
                       intended_overlaps=intended(J), max_step_mm=20.0, out=GATES / 'motion.json')


def leg_range(cache) -> dict:
    """The leg over its range, the wheel on the deck: the relation table's interferences at each pose."""
    from cadagent.gates.relations import Tolerances, relation_table
    from cadagent.gates.verdict import Check, verdict, write_verdict
    checks, poses = [], []
    for L in (rp.BUMPER['contact_leg_mm'], 185.0, 220.0, 300.0, 360.0, 390.0):
        for lean in (-20.0, 0.0, 20.0):
            phi = fb.stance(L, lean)
            fo, fi, ro, ri = fb.stop_angles()
            if phi is None or not (fi - 1e-6 <= phi[0] <= fo + 1e-6 and ro - 1e-6 <= phi[1] <= ri + 1e-6):
                continue
            zh = br.zh_on_deck(L, lean)
            J = hw.joints(zh)
            asm = assembly(zh, L, lean)
            skip = [o['parts'] for o in intended(J)] + [['leg_wheel_tyre', 'deck']]          # the tyre stands on the deck
            t = relation_table(asm, Tolerances(touch_mm=0.05), cache=cache, skip_pairs=skip)
            hits = [r for r in t.interferences()]
            poses.append({'leg_mm': L, 'lean_deg': lean, 'hip_mm': round(zh, 1), 'interferences': len(hits)})
            for r in hits:
                checks.append(Check(f'interference:{r.a}|{r.b}@{L:g}/{lean:+g}', 'fail',
                                    f'{r.a} and {r.b} share {(r.overlap_mm3 or 0):.1f} mm3 ({r.state}) at a {L:g} mm leg, {lean:+g} deg',
                                    parts=[r.a, r.b], evidence={'overlap_mm3': r.overlap_mm3, 'pose': [L, lean]}))
            checks.append(Check(f'pose:{L:g}/{lean:+g}', 'pass' if not hits else 'fail', f'{len(hits)} interferences',
                                evidence={'hip_mm': round(zh, 1)}))
    v = verdict('leg_range', checks, assumptions=[
        'the leg at each pose of the list, the wheel standing on the deck; the five-bar is posed by fivebar.stance(), not '
        'by the motion gate (a closed loop)', 'the relation table\'s tolerances (touch 0.05 mm); the intended overlaps '
        'listed in cad/rig_gates.py are left out'], extra={'poses': poses})
    write_verdict(GATES / 'leg_range.json', v)
    return v


def screws() -> dict:
    from cadagent.gates.verdict import Check, verdict, write_verdict
    import assembly_checks as ac
    rows = ac.screw_stacks(hw.screw_rows(hw.joints()))
    checks = [Check(f"screw:{r['joint']}", 'pass' if r['ok'] else 'fail',
                    f"{r['screw']}: {r['engage_mm']} mm of thread ({r['need_mm']} needed), tip room {r['tip_room_mm']} mm"
                    + (f": {r['why']}" if r['why'] else ''), evidence=r) for r in rows]
    v = verdict('screws', checks, assumptions=[
        'each screw\'s stack from rig_hardware.joints(): the layers under the head, the receiver\'s thread length and the '
        'room behind it', 'the 8-series slot\'s lip, drop-in nut and groove (rig_hardware.SLOT) are assumed until measured'],
        limits={'slot': hw.SLOT})
    write_verdict(GATES / 'screws.json', v)
    return v


def main(argv=None) -> int:
    from cadagent.gates.cache import PairCache
    t0 = time.time()
    GATES.mkdir(parents=True, exist_ok=True)
    cache = PairCache(CACHE)
    results = {'connectivity': connectivity(cache), 'motion': motion(cache), 'leg_range': leg_range(cache), 'screws': screws()}
    bad = []
    for name, v in results.items():
        st = v.get('status')
        print(f"gate {name}: {st} ({v.get('counts')})")
        if not v.get('pass'):
            for f in (v.get('findings') or [])[:25]:
                if f.get('status') == 'fail':
                    bad.append(f"{name}: {f.get('id')}: {f.get('message', '')[:200]}")
    for b in bad:
        print('  ', b)
    print(f'gates: {len(bad)} failures ({time.time() - t0:.0f} s) -> {GATES.relative_to(br.R)}')
    return 0 if not bad and all(v.get('pass') for v in results.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
