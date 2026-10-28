"""The rig's integrity checks (cad/assembly_checks.py on the rig's parts), run by cad/build_rig.py; exits 1 on a
violation so a build cannot pass with one:

    .venv/bin/python cad/rig_integrity.py            # -> exports/rig/integrity.json

1. Nothing floats: each body (the fixed rig, the carriage with the leg's frame and motors, the leg's moving links) is
   one connected group of parts that touch, or that a screw of the joint table holds together; the carriage meets the
   rig only at its four blocks on the two rails.
2. No interference: every part against every other at the carriage's whole travel (on its bumpers to the top stop,
   the leg at both ends of its range) and over the leg's range with the wheel on the deck.
3. Every screw's length fits its stack (rig_hardware.JOINTS): enough thread, and the tip clear of what is behind it.

What is excused, and why, is listed here (ALLOWED); nothing else is.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import assembly_checks as ac  # noqa: E402
import build_rig as br  # noqa: E402
import fivebar as fb  # noqa: E402
import rig_hardware as hw  # noqa: E402
import rig_parts as rp  # noqa: E402

OUT = br.OUT / 'integrity.json'

# The leg's own model (cad/fivebar.py, the main session's): overlaps that are the model's way of drawing a fit, reported
# to its owner, excused here so the rig's checks stay about the rig.
LEG_OVERLAPS = {
    ('leg_upper_link_front', 'leg_eye_sleeve_front'): 'the DIN 179 sleeves are a press fit in the eye (0.04 mm on Ø18)',
    ('leg_upper_link_rear', 'leg_eye_sleeve_rear'): 'the same press fit',
    ('leg_output_adapter_front', 'leg_screws_links'): 'the link screws\' threads in the adapter\'s tapped holes (drawn solid)',
    ('leg_output_adapter_rear', 'leg_screws_links'): 'the same',
    ('leg_motor_front', 'leg_screws_lugs'): 'the lug screws\' threads in the motor (the motor is an envelope)',
    ('leg_motor_rear', 'leg_screws_lugs'): 'the same',
    ('leg_motor_front', 'leg_screws_outputs'): 'the output screws\' threads in the motor\'s flange (envelope)',
    ('leg_motor_rear', 'leg_screws_outputs'): 'the same',
    ('leg_wheel_link', 'leg_screws_wheel'): 'the wheel screws\' threads (drawn through the link)',
    ('leg_screws_wheel', 'leg_wheel_hub'): 'the wheel screws\' threads in the BotWheel\'s flange (envelope)',
    ('leg_wheel_link', 'leg_wheel_hub'): 'REPORTED to the leg\'s owner: 250 mm3 between the wheel link and the BotWheel\'s hub '
                                         '(the boss in its recess, or the envelope larger than the part)',
}
# parts of the leg's model that are held by a thread only (no face contact in the model): fastened, not floating
LEG_FASTENED = [('leg_stop_posts', 'leg_hip_frame')]
SLIDES = [('carriage', 'frame', f'block_{sx:+d}{sz:+d}', f'rail_{"left" if sx < 0 else "right"}', 0.5)
          for sx in (-1, 1) for sz in (-1, 1)]


def thread_partner(J):
    """{screw: the part its thread goes into} for the threads drawn without their holes (tapped, inserts)."""
    return {j['name']: j['holds'][1] for j in J if j['thread_in']['kind'] in ('tapped', 'insert', 'wood')}


def allowed(J):
    partner = thread_partner(J)
    leg = {frozenset(k) for k in LEG_OVERLAPS}

    def ok(a, b):
        if frozenset((a, b)) in leg:
            return True
        if partner.get(a) == b or partner.get(b) == a:
            return True
        if (a.startswith('leg_wheel_tyre') and b == 'deck') or (b.startswith('leg_wheel_tyre') and a == 'deck'):
            return True                                         # the tyre stands on the deck
        return False
    return ok


def assembly(zh: float, L: float, lean: float = 0.0, plates: int = 1):
    fixed = br.fixed_parts(hardware=True)
    car = br.carriage_parts(zh, n_plates=plates, hardware=True)
    leg = br.leg_parts(L, lean, zh)
    static = {n: s for n, (s, k) in leg.items() if k == 'static'}
    moving = {n: s for n, (s, k) in leg.items() if k == 'moving'}
    return fixed, car, static, moving


def connectivity(zh: float, J) -> dict:
    fixed, car, static, moving = assembly(zh, 300.0)
    parts = {**fixed, **car, **static, **moving}
    fastened = [(j['name'], j['holds'][1]) for j in J] + LEG_FASTENED
    bodies = {'frame': list(fixed), 'carriage': list(car) + list(static), 'linkage': list(moving)}
    res = ac.floating(parts, bodies, tol=0.1, fastened=fastened)
    res['slides'] = ac.joints_hold(parts, SLIDES)
    return res


def poses():
    """(tag, zh, L, lean): the carriage's travel with the leg at both ends of its range, and the leg's range with the
    wheel on the deck."""
    out = []
    zb = br.zh_on_deck(rp.BUMPER['contact_leg_mm'])                       # on the bumpers
    zt = rp.top_stop_z(br.RAIL_TOP) - rp.PLATE_H / 2                      # the plate's top edge at the top stop
    for zh in (zb, zb + 150, 450.0, 600.0, 750.0, zt - 1.0):
        for L in (110.0, min(390.0, zh - rp.WHEEL_R - 5.0)):          # folded, and as long as the wheel stays off the deck
            if L >= 110.0:
                out.append(('travel', round(zh, 1), round(L, 1), 0.0))
    for L in (rp.BUMPER['contact_leg_mm'], 160.0, 220.0, 300.0, 360.0, 390.0):   # below 140 the carriage rests on the bumpers
        for lean in (-20.0, 0.0, 20.0):
            phi = fb.stance(L, lean)
            fo, fi, ro, ri = fb.stop_angles()
            if phi is None or not (fi - 1e-6 <= phi[0] <= fo + 1e-6 and ro - 1e-6 <= phi[1] <= ri + 1e-6):
                continue
            out.append(('on_deck', round(br.zh_on_deck(L, lean), 1), L, lean))
    return out


def interference(J) -> dict:
    allow = allowed(J)
    fixed = br.fixed_parts(hardware=True)
    hits, n = [], 0
    for tag, zh, L, lean in poses():
        try:
            _, car, static, moving = assembly(zh, L, lean)
        except Exception as e:                                  # noqa: BLE001 - a pose the leg cannot take
            hits.append({'pose': [tag, zh, L, lean], 'parts': ['leg', 'pose'], 'overlap_mm3': None, 'error': str(e)[:120]})
            continue
        mv = {**car, **static, **moving}
        n += 1
        for r in ac.interferences(mv, allow, 1.0, against=fixed):
            hits.append({'pose': [tag, zh, L, lean], **r})
        for r in ac.interferences(mv, allow, 1.0):
            hits.append({'pose': [tag, zh, L, lean], **r})
    st = ac.interferences(fixed, allow, 1.0)                    # the fixed rig against itself, once
    return {'poses': n, 'fixed_self': st, 'hits': hits, 'ok': not hits and not st}


def main(argv=None) -> int:
    t0 = time.time()
    J = hw.joints()
    stacks = ac.screw_stacks(hw.screw_rows(J))
    zh = br.zh_on_deck(300.0)
    conn = connectivity(zh, hw.joints(zh))
    Jz = hw.joints(zh)
    inter = interference(Jz)
    doc = {'screws': stacks, 'screws_ok': all(r['ok'] for r in stacks), 'connectivity': conn, 'interference': inter,
           'leg_overlaps_excused': {f'{a} / {b}': why for (a, b), why in LEG_OVERLAPS.items()},
           'slot_assumptions': hw.SLOT, 'seconds': round(time.time() - t0)}
    bad = [f"screw {r['joint']}: {r['why']}" for r in stacks if not r['ok']]
    bad += [f"{b}: floating {v['floating']}" for b, v in conn.items() if isinstance(v, dict) and v.get('ok') is False]
    bad += [f"slide {r['joint']}: gap {r['gap_mm']}" for r in conn['slides'] if not r['ok']]
    bad += [f"interference {h['parts']} {h.get('overlap_mm3')} mm3 at {h.get('pose', 'fixed')}" for h in inter['hits'] + inter['fixed_self']]
    doc['failures'] = bad
    doc['ok'] = not bad
    OUT.write_text(json.dumps(doc, indent=1, default=str) + '\n')
    print(f"integrity: {len(stacks)} screws, {inter['poses']} poses, {len(bad)} failures ({doc['seconds']} s) -> {OUT.relative_to(br.R)}")
    for b in bad[:60]:
        print('  ', b)
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
