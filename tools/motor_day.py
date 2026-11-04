"""Motor day: the first leg in PLA on a boom stand, its build package and its test ladder (docs/motor-day.md, #156).

    .venv/bin/python tools/motor_day_sim.py      # the rig simulation at the day-one caps -> exports/motor-day/sim.json
    .venv/bin/python tools/motor_day.py --slice  # Bambu Studio PLA slices of every print -> exports/motor-day/slices.json
    .venv/bin/python tools/motor_day.py          # everything else, from those two records

Writes exports/motor-day/: the new printed parts (the foot that stands in for the BotWheel, the end plate's drill
template) and the stand's plate, the print list, the McMaster-Carr and other-vendor order lists (CSV), the PLA
derating (derating.json), the stand's masses (stand.json), the exploded assembly steps (steps/step-NN.png), the
ballooned drawings (drawings/MD-NN.png and motor-day-drawings.pdf), the bundle (motor-day-package.zip), and the
generated sections of docs/motor-day.md.

The derating: the leg's FEA record (exports/leg/fea/summary.json, PA6-CF humid; the layer check from
research/leg-preprint/evidence/leg-layer-check-print-ready.json) is linear, so each row's safety factor scales with the
material's strength and inversely with the load. The PLA strength is cad-agent's own row (cadagent.fea.MATERIALS['pla']);
the loads are the rig simulation's at each day-one cap (sim.json) against the loads each case was run at.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import subprocess
import sys
import zipfile
from pathlib import Path

import cadquery as cq

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
sys.path.insert(0, str(R))
import fivebar as fb  # noqa: E402

OUT = R / 'exports' / 'motor-day'
DOC = R / 'docs' / 'motor-day.md'
WORK = R / 'work' / 'motor-day-slicer'           # gitignored; the snap slicer cannot write under /tmp or a hidden folder
WHEEL_R = 171.3 / 2                             # the BotWheel's tyre; the foot keeps its radius, so the leg's geometry holds
STANCE = 300.0                                  # mm, the leg's length on the stand at rest
FLOOR_Z = -(STANCE + WHEEL_R)                   # the floor, in the leg's frame (hip axis at z = 0)
FLOOR_STOP_LEG = 140.0                          # mm: the floor stop catches the boom here, as the rig's bumpers do
TETHER_RISE = 150.0                             # mm the hip may rise above the stance before the tether goes tight
LANDING_TARGET = 2.0                            # every day-one run lands: landings are held to the everyday target
FAULT_TARGET = 1.0

# ------------------------------------------------------------------------------------------------- prints

RECIPES = {   # Bambu Studio process overrides on cadagent.slicer's P1S 0.4 / 0.20 mm / PLA Basic defaults
    'solid': {'wall_loops': '4', 'sparse_infill_density': '100%', 'sparse_infill_pattern': 'zig-zag'},
    'foot': {'wall_loops': '4', 'sparse_infill_density': '30%', 'sparse_infill_pattern': 'gyroid'},
    'jig': {'wall_loops': '2', 'sparse_infill_density': '15%', 'sparse_infill_pattern': 'grid'},
    'tpu': {'wall_loops': '4', 'sparse_infill_density': '100%', 'sparse_infill_pattern': 'zig-zag'},
}
TPU = 'Bambu TPU 95A HF @BBL P1S'
C1 = [f'coupon_{n}_{v}' for n in ('knee_eye', 'frame_pins', 'knee_boss', 'apex_eye', 'hub_stub', 'hub_face') for v in ('m01', 'nom', 'p01')] \
    + ['coupon_frame_ring_m01', 'coupon_frame_ring_p01']

# (key, file, qty, recipe, phase, face on the bed and what to watch)
PRINTS = [
    ('coupon_frame_ring_nom', 'exports/rig/bench/coupon_frame_ring_nom.stl', 1, 'solid', '0',
     'the RS-04 seat cut from the hip frame, as printed in it: the motor\'s unpowered fit (Phase 0.3)'),
    *[(k, f'exports/rig/bench/{k}.stl', 1, 'solid', '1a', 'C1 in PLA: which bore offset fits (the CAD\'s hole '
       'compensation is set for PA6-CF)') for k in C1],
    ('hip_frame', 'exports/leg/hip_frame.3mf', 1, 'solid', '1b',
     'the web\'s outer face down, turned 45 deg (249 mm of the 256 mm bed: brim 3 mm at most); keep the stop-pin holes\' lead-ins clean'),
    ('upper_link', 'exports/leg/upper_link.3mf', 2, 'solid', '1b', 'the outer face down; the knee-eye sleeve holes open on the bed'),
    ('front_link', 'exports/leg/front_link.3mf', 1, 'solid', '1b',
     'the inner face down, turned 45 deg; add tree supports from the bed only (never in the bearing seats) by hand: the '
     'time and grams here are without them (the slicer\'s auto-arrange refuses the 247 mm part with supports on)'),
    ('wheel_link', 'exports/leg/wheel_link.3mf', 1, 'solid', '1b', 'the outer face down; the outer knee seat opens on the bed'),
    ('apex_spacer', 'exports/leg/apex_spacer.3mf', 1, 'solid', '1b', 'the inner face down'),
    ('output_adapter_pla', 'exports/leg/cnc/output_adapter.stl', 2, 'solid', '0',
     'day-one stand-in for the machined 6061 adapter: the motor face down; tap the eight face M5 holes by hand (M5 x 0.8 tap) '
     'before assembly step 4'),
    ('foot', 'exports/motor-day/parts/foot.stl', 1, 'foot', '1b',
     'the outer face down (nut pockets open on the bed), the boss up; stands in for the BotWheel'),
    ('stop_sleeve', 'exports/leg/stop_sleeve.3mf', 4, 'tpu', '1b', 'TPU 95A, cap down'),
    ('drill_template', 'exports/motor-day/parts/drill_template.stl', 1, 'jig', '1b',
     'flat; lay it on the plywood end plate to drill the six M5 holes and mark the two lead slots'),
]

# The order to print them in (docs/motor-day.md Phase 1): (step, key, qty, phase, what to watch, or None for PRINTS').
# The two Phase 0 fit checks come first: the frame-ring coupon is the hip frame's motor seat cut from it, and the first
# output adapter is the same file as the second, so a misfit shows before the 19 h frame and the second adapter.
PRINT_ORDER = [
    (1, 'coupon_frame_ring_nom', 1, '0', None),
    (2, 'output_adapter_pla', 1, '0',
     'the first of the two, printed before the leg: the motor\'s output fit (Phase 0.4). The motor face down (the three '
     'Ø6 pin sockets open on the bed); tap the eight face M5 holes by hand (M5 x 0.8 tap) before assembly step 4'),
    *[(3, k, 1, '1a', None) for k in C1],
    (4, 'hip_frame', 1, '1b', None),
    (5, 'output_adapter_pla', 1, '1b',
     'the second, as the first; if Phase 0.4 needed the pin sockets opened with a 6.0 mm drill, open this one\'s '
     'the same way before it goes on; tap the eight face M5 holes'),
    (6, 'upper_link', 2, '1b', None),
    (7, 'wheel_link', 1, '1b', None),
    (8, 'front_link', 1, '1b', None),
    (9, 'apex_spacer', 1, '1b', None),
    (10, 'foot', 1, '1b', None),
    (11, 'stop_sleeve', 4, '1b', None),
    (12, 'drill_template', 1, '1b', None),
]


def print_queue() -> list:
    """PRINT_ORDER with each row's file, recipe and note from PRINTS; every print's copies are in it exactly once."""
    by = {p[0]: p for p in PRINTS}
    steps = list(dict.fromkeys(r[0] for r in PRINT_ORDER))
    if steps != list(range(1, len(steps) + 1)) or [r[0] for r in PRINT_ORDER] != sorted(r[0] for r in PRINT_ORDER):
        raise SystemExit(f'PRINT_ORDER steps must run 1, 2, 3 ... in order, each in one run of rows: {steps}')
    for step, key, _, phase, _ in PRINT_ORDER:
        if phase not in ('0', '1a', '1b'):
            raise SystemExit(f'PRINT_ORDER step {step} ({key}): phase {phase!r} is not 0, 1a or 1b')
        if sum(1 for r in PRINT_ORDER if r[0] == step) > 1 and key not in C1:
            raise SystemExit(f'PRINT_ORDER step {step} is shared; only the C1 coupons share one')
    out = []
    for step, key, qty, phase, how in PRINT_ORDER:
        _, f, _, recipe, _, how0 = by[key]
        out.append({'order': step, 'key': key, 'qty': qty, 'phase': phase, 'file': f, 'recipe': recipe, 'how': how or how0})
    for key, _, qty, *_ in PRINTS:
        n = sum(r['qty'] for r in out if r['key'] == key)
        if n != qty:
            raise SystemExit(f'PRINT_ORDER prints {n} of {key}, PRINTS lists {qty}')
    return out

# ------------------------------------------------------------------------------------------------- the stand

PLY = 18.3                     # mm, 23/32 in plywood (catalog/rig.json plywood_18)
LUMBER = (38.0, 89.0)          # a 2x4, actual
BOOM_LEN = 1500.0              # each rail, mm
PIVOT_FROM_END = 60.0          # the pivot bolt this far from the rails' far end
PLATE = (300.0, 260.0)         # x by z
WOOD = {'plywood': 0.60, 'spf': 0.45}   # g/cm3: a typical softwood plywood and spruce-pine-fir 2x4 (estimates: weigh them)


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0).translate(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))


def _ycyl(r, y0, y1, x=0.0, z=0.0):
    return fb.ycyl(r, y0, y1, x, z)


def plate_y():
    """The end plate's two faces: the hip frame's mount plane is its front face (fivebar.frame_mounts)."""
    y1 = fb.frame_mounts()['plane_y']
    return y1 - PLY, y1


def end_plate():
    import rig_parts as rp
    y0, y1 = plate_y()
    p = _box(-PLATE[0] / 2, PLATE[0] / 2, y0, y1, -PLATE[1] / 2, PLATE[1] / 2)
    for (x, z) in fb.frame_mounts()['inserts_xz']:
        p = p.cut(_ycyl(2.75, y0 - 1, y1 + 1, x, z))
    for s in rp.harness_slots():
        p = p.cut(rp.stadium(s['x'], s['z'], s['w'], s['h'], y0 - 1, y1 + 1))
    return p


def drill_template():
    """A 1.2 mm PLA sheet the size of the plate's middle: six Ø5.5 holes on the inserts and the lead slots' outlines, to
    lay on the plywood and drill through. Built flat (x, y) with z up."""
    import rig_parts as rp
    t = cq.Workplane('XY').box(224.0, 184.0, 1.2).translate((0, 0, 0.6))
    for (x, z) in fb.frame_mounts()['inserts_xz']:
        t = t.cut(cq.Workplane('XY').circle(2.75).extrude(4).translate((x, z, -1)))
    for s in rp.harness_slots():
        t = t.cut(cq.Workplane('XY').rect(s['w'], s['h']).extrude(4).translate((s['x'], s['z'], -1)))
    t = t.cut(cq.Workplane('XY').rect(2.0, 30.0).extrude(4).translate((0, 75, -1)))   # a centre mark at the top edge
    return t


def boom_y():
    y0, _ = plate_y()
    y_back = y0 - LUMBER[1]                                   # the cleats' back faces
    return y_back, y0 - BOOM_LEN, y0 - BOOM_LEN + PIVOT_FROM_END   # cleat back, rails' far end, pivot


def stand_parts():
    """The stand in the leg's frame (hip axis at z = 0, the leg at STANCE, the floor at FLOOR_Z): name -> shape."""
    t, d = LUMBER
    y0, y1 = plate_y()
    y_back, y_end, y_piv = boom_y()
    xc = PLATE[0] / 2 - t / 2                                  # the cleats at the plate's edges
    xr = PLATE[0] / 2 + t / 2                                  # the rails outside them
    P = {'end_plate': end_plate()}
    for s, side in ((1, 'right'), (-1, 'left')):
        P[f'cleat_{side}'] = _box(s * xc - t / 2, s * xc + t / 2, y_back, y0, -PLATE[1] / 2, PLATE[1] / 2)
        P[f'rail_{side}'] = _box(s * xr - t / 2, s * xr + t / 2, y_end, y0, -d / 2, d / 2)
    P['cross_member'] = _box(-xr + t / 2, xr - t / 2, y_end, y_end + d, -d / 2, -d / 2 + t)
    base_t = PLY
    zb = FLOOR_Z + base_t
    xu = xr + t / 2 + 3.0 + t / 2                              # the uprights outside the rails, a washer between
    up_top = d / 2 + 60.0
    z_top = up_top - 40                                        # the brace meets the upright 40 mm under its top
    run = z_top - zb                                           # a 45 deg brace runs as far back as it drops
    P['base'] = _box(-xu - 120, xu + 120, y_piv - d / 2 - run - 40, y_piv + 250, FLOOR_Z, zb)
    for s, side in ((1, 'right'), (-1, 'left')):
        P[f'upright_{side}'] = _box(s * xu - t / 2, s * xu + t / 2, y_piv - d / 2, y_piv + d / 2, zb, up_top)
        # a brace from the upright's back face down to the base: a 2x4 at 45 deg, cut plumb at the upright and level
        # on the base (its 89 mm face in the YZ plane, so it is 89 x sqrt 2 tall where it meets the upright)
        yb, w = y_piv - d / 2, d * math.sqrt(2)
        P[f'brace_{side}'] = (cq.Workplane('YZ', origin=(s * xu - t / 2, 0, 0))
                              .polyline([(yb, z_top), (yb, z_top - w), (yb - (z_top - w - zb), zb), (yb - run, zb)]).close()
                              .extrude(t))
        a0, a1 = sorted((s * (xr - t / 2 - 6.0), s * (xu + t / 2 + 12.0)))
        P[f'pivot_bolt_{side}'] = cq.Workplane('YZ', origin=(a0, 0, 0)).center(y_piv, 0).circle(6.35).extrude(a1 - a0)
    # the floor stop: offcuts under each rail near the plate, topped with a rubber pad, on a floor board
    ys = y_back - 120.0
    drop = (STANCE - FLOOR_STOP_LEG) * (ys - y_piv) / (0.0 - y_piv)
    top = -d / 2 - drop
    P['stop_board'] = _box(-xr - 80, xr + 80, ys - 120, ys + 120, FLOOR_Z, FLOOR_Z + PLY)
    for s, side in ((1, 'right'), (-1, 'left')):
        P[f'floor_stop_{side}'] = _box(s * xr - d / 2, s * xr + d / 2, ys - 60, ys + 60, FLOOR_Z + PLY, top - 8.0)
        P[f'stop_pad_{side}'] = _box(s * xr - d / 2, s * xr + d / 2, ys - 60, ys + 60, top - 8.0, top)
    P['tether'] = _ycyl(4.0, ys - 4, ys + 4, 0.0, 0.0).union(_box(-3, 3, ys - 3, ys + 3, FLOOR_Z + PLY, -d / 2))
    P['mat'] = _box(-300, 300, -150, 330, FLOOR_Z - 8.0, FLOOR_Z)
    meta = {'plate_y': [round(y0, 1), round(y1, 1)], 'cleat_back_y': round(y_back, 1), 'rail_end_y': round(y_end, 1),
            'pivot_y': round(y_piv, 1), 'pivot_z': 0.0, 'upright_x': round(xu, 1), 'rail_x': round(xr, 1),
            'floor_stop_y': round(ys, 1), 'floor_stop_top_z': round(top, 1),
            'floor_stop_height_mm': round(top - FLOOR_Z, 1), 'floor_z': round(FLOOR_Z, 1),
            'tether_length_note': f'the hip may rise {TETHER_RISE:.0f} mm above the stance: at the tether the boom rises '
                                  f'{TETHER_RISE * (ys - y_piv) / (0.0 - y_piv):.0f} mm'}
    return P, meta


# ------------------------------------------------------------------------------------------------- the foot


def foot(holes=None):
    """The BotWheel's stand-in: a fixed, spoked PLA disc of the tyre's radius on the wheel link's foot (the BotWheel's
    Ø50 boss and 4 x M6 on its 36 PCD, fivebar.wheel_link). M6 x 40 from inside the hub on the DIN 433 washers into
    M6 nylon-insert nuts in hex pockets. Its tread is 12 mm inboard of the tyre's mid-plane (y 92 against 104.8), so the
    leg's out-of-plane moment is less than the record's. Built in the wheel link's own frame at the axle (axis along y)."""
    w = fb.gmi.motor_interface(fb.WHEEL)
    bw = w['case']['bolts']
    y_face = fb.Y['wheel_link'][1]                                  # the link's outer face, where the BotWheel's flange sits
    y_out = y_face + 24.0
    boss = _ycyl(24.8, fb.Y['wheel_boss'] - fb.WHEEL_RECESS_PLAY + 0.4, y_face + 0.01)
    body = _ycyl(36.0, y_face, y_out).union(boss)
    rim = _ycyl(WHEEL_R, y_face, y_out).cut(_ycyl(WHEEL_R - 10.0, y_face - 1, y_out + 1))
    body = body.union(rim)
    for k in range(6):
        a = math.radians(30 + 60 * k)
        sp = _box(30.0, WHEEL_R - 6.0, y_face, y_out, -9.0, 9.0).rotate((0, 0, 0), (0, 1, 0), -math.degrees(a))
        body = body.union(sp)
    nut_seat = 84.5                                                  # M6 x 40 ends at y 92: 1.5 mm through a 6 mm nut
    for (x, z) in (holes or fb.gmi.circle_pts(bw['pcd'], bw['count'] or 4, 45.0)):
        body = body.cut(_ycyl(3.3, y_face - 10, y_out + 1, x, z))
        hexp = (cq.Workplane('XZ', origin=(0, y_out + 1, 0)).center(x, z).polygon(6, 10.4 / math.cos(math.pi / 6))
                .extrude(y_out + 1 - nut_seat))
        body = body.cut(hexp)
    body = body.cut(_ycyl(10.0, y_face - 10, y_out + 1))
    return body, {'y_face': y_face, 'y_out': y_out, 'tread_mid_y': (y_face + y_out) / 2, 'nut_seat_y': nut_seat,
                  'screw': 'screw_m6x40', 'nut': 'nut_m6_nyloc'}


def foot_print(f, meta):
    """The foot in print orientation: its outer face on z = 0, the boss up."""
    return f.rotate((0, 0, 0), (1, 0, 0), -90).translate((0, 0, meta['y_out']))


# ------------------------------------------------------------------------------------------------- slicing


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def slice_all():
    from cadagent import slicer
    from print_slicing import engine_identity
    exe = slicer.executable()
    if not exe:
        raise SystemExit('Bambu Studio is not installed (snap install bambu-studio)')
    ident = engine_identity(exe)
    old = _load(OUT / 'slices.json', {}).get('parts', {})
    rows = {}
    for key, f, qty, recipe, phase, _ in PRINTS:
        src = R / f
        sha = _sha(src)
        fil = TPU if recipe == 'tpu' else 'pla'
        if key in old and old[key].get('sha256') == sha and old[key].get('recipe') == recipe and old[key].get('ok'):
            rows[key] = old[key]
            continue
        r = slicer.slice_part(src, workdir=WORK / key, filament=fil, overrides=RECIPES[recipe])
        ok = bool(r.get('grams')) and r.get('exit_code') == 0 and math.isfinite(r.get('seconds') or float('nan'))
        rows[key] = {'file': f, 'sha256': sha, 'recipe': recipe, 'overrides': RECIPES[recipe], 'filament': r.get('filament'),
                     'printer': r.get('printer'), 'process': r.get('process'), 'grams': r.get('grams'),
                     'minutes': r.get('minutes'), 'filament_m': r.get('filament_m'), 'ok': ok,
                     'error': None if ok else (r.get('error') or 'no grams')}
        print(f"  {key:24} {recipe:16} {r.get('grams')} g  {r.get('minutes')} min  {'ok' if ok else 'FAILED'}", flush=True)
    if engine_identity(exe) != ident:
        raise SystemExit('the slicer changed during the run: slice again')
    doc = {'made_by': 'tools/motor_day.py --slice (cadagent.slicer on Bambu Studio)', 'engine': ident,
           'note': 'slicer estimates for planning; the 3MF and STL files carry geometry only: use the recipe in prints.csv',
           'parts': rows}
    (OUT / 'slices.json').write_text(json.dumps(doc, indent=1) + '\n')


# ------------------------------------------------------------------------------------------------- derating


def _load(p: Path, default=None):
    return json.loads(p.read_text()) if p.exists() else default


def record_loads() -> dict:
    """The loads the FEA record's cases were run at (cad/leg_studies.py cases(), from exports/leg/rig-results.json)."""
    rig = _load(R / 'exports/leg/rig-results.json')['scenarios']

    def peak(keys):
        return max(max(rig[n].get('peak_joint_force_n', {}).get(k, 0.0) for k in keys) for n in ('drop_150', 'jump'))
    S = _load(R / 'exports/leg/fea/summary.json')
    return {'knee_dyn_n': peak(('knee_f', 'knee_r')), 'hip_dyn_n': peak(('hip_f', 'hip_r')),
            'axle_full_n': rig['drop_150']['peak_axle_force_n'],
            'power_off_axle_n': S['cases']['R3']['Fw3'][2], 'stop_nm': S['cases']['R3']['stop_nm'], 'cap_nm': 60.0, 'peak_nm': 120.0}


def knee_of(run: dict) -> float:
    return max(run['peak_joint_force_n'].get('knee_f', 0), run['peak_joint_force_n'].get('knee_r', 0))


def hip_of(run: dict) -> float:
    return max(run['peak_joint_force_n'].get('hip_f', 0), run['peak_joint_force_n'].get('hip_r', 0))


KNEE_SIDE = {'upper_link', 'front_link', 'wheel_link'}           # the parts a knee pin loads
HIP_SIDE = {'hip_frame', 'output_adapter', 'upper_link'}           # the parts the hip joint and the motor's hub load


def _joints(part: str, run: dict, rec: dict, lf: float, hub: bool = False):
    """A landing case's row scaled by the worst of the joints its part carries: the knee's ratio to the record's landing
    for the links, the hip's for the hip side, and the hub torque's (the push's, or a power cut's backdriven one) to the
    60 N m cap the record's hub carries."""
    cand = []
    if part in KNEE_SIDE or part not in HIP_SIDE:
        cand.append((knee_of(run) * lf / rec['knee_dyn_n'], f"knee {knee_of(run) * lf:.0f} N against {rec['knee_dyn_n']:.0f} N"))
    if part in HIP_SIDE:
        cand.append((hip_of(run) * lf / rec['hip_dyn_n'], f"hip {hip_of(run) * lf:.0f} N against {rec['hip_dyn_n']:.0f} N"))
        if hub:
            g = run.get('peak_gearbox_nm') or 0.0
            cand.append((g / rec['cap_nm'], f"hub {g:.0f} N m against {rec['cap_nm']:.0f}"))
    return max(cand)


def scale_of(part: str, case: str, run: dict, rec: dict, cap: float, lf: float):
    """[(load ratio day-one / record, target, what it is)] for a FEA row's case under the powered runs (the jump at the
    cap: its landing and its push), or [] where they do not load it. lf scales the simulated forces to the stand's mass."""
    if case in ('R1', 'R1F'):
        f, txt = _joints(part, run, rec, lf, hub=True)
        return [(f, LANDING_TARGET, f'landing: {txt}')]
    if case in ('R1w',):
        ax = run['peak_axle_force_n'] * lf
        return [(ax / rec['axle_full_n'], LANDING_TARGET, f"landing on the wheel link: axle {ax:.0f} N against {rec['axle_full_n']:.0f} N")]
    if case in ('E2', 'E3', 'E3o', 'E3i'):
        return [(cap / rec['cap_nm'], 2.0, f'a motor at the {cap:.0f} N m cap (record {rec["cap_nm"]:.0f})')]
    if case == 'R2':
        return [(cap / rec['peak_nm'], 2.0, f'a motor stalled at the {cap:.0f} N m cap, every day on day one (record {rec["peak_nm"]:.0f})')]
    return []                         # E1 (a turn): no turns on the stand; R3* (a power cut): power_cut_rows()


def cut_scale(part: str, case: str, off: dict, rec: dict, lf: float):
    """The same for a power cut onto the floor stop (target 1: a fault). The backdriven hub torque enters the cases that
    carry a hub torque."""
    g = off.get('peak_gearbox_nm') or 0.0
    if case in ('R1', 'R1F'):
        f, txt = _joints(part, off, rec, lf, hub=True)
        return [(f, FAULT_TARGET, f'power cut: {txt}')]
    if case in ('R1w', 'R3K', 'R3KF'):
        ax = off['peak_axle_force_n'] * lf
        ref = rec['axle_full_n'] if case == 'R1w' else rec['power_off_axle_n']
        return [(ax / ref, FAULT_TARGET, f'power cut: axle {ax:.0f} N against {ref:.0f} N')]
    if case in ('R3', 'R3o'):          # the upper link's own stop face: only if the leg reaches its stops
        st = off.get('peak_stop_nm') or 0.0
        return [(st / rec['stop_nm'], FAULT_TARGET, f'power cut: stop {st:.0f} N m against {rec["stop_nm"]:.0f}')]
    if case in ('E2', 'E3', 'E3o', 'E3i'):
        return [(g / rec['cap_nm'], FAULT_TARGET, f'power cut: hub {g:.0f} N m against {rec["cap_nm"]:.0f}')]
    if case == 'R2':
        return [(g / rec['peak_nm'], FAULT_TARGET, f'power cut: hub {g:.0f} N m against {rec["peak_nm"]:.0f}')]
    return []


def _row(r: dict, f: float, target: float, why: str, pla, LC: dict) -> dict:
    """One FEA row at PLA strength (linear: the factor scales with the strength) and at the day-one load ratio f."""
    s_rec = r['material_data']['strength_mpa']
    gate = r['safety_factor'] * pla.strength_mpa / s_rec
    lc = LC.get((r['part'], r['case']))
    layer = None
    if lc and r['material_data'].get('strength_z_mpa'):
        # bond: S_z and S_s scale together (S_s = S_z / sqrt 3 for both); bulk: in-layer strength
        k_z = pla.strength_mpa / r['material_data']['strength_z_mpa']
        k_xy = pla.strength_mpa / r['material_data'].get('strength_xy_mpa', s_rec)
        layer = min(lc.get('safety_factor_bond', lc['safety_factor']) * k_z, lc.get('safety_factor_bulk', 99) * k_xy)
    base = min(gate, layer) if layer is not None else gate
    sf = base / f if f > 1e-9 else None
    return {'part': r['part'], 'case': r['case'], 'record_gate': r['safety_factor'],
            'record_layer': lc['safety_factor'] if lc else None, 'pla_gate_at_record_load': round(gate, 2),
            'pla_layer_at_record_load': round(layer, 2) if layer is not None else None, 'load_ratio': round(f, 3),
            'sf': round(sf, 2) if sf is not None else None, 'target': target, 'ok': sf is None or sf >= target,
            'governed_by': ('layer' if layer is not None and layer < gate else 'gate'), 'load': why}


def _verdict(rows: list) -> dict:
    worst = min((x for x in rows if x['sf'] is not None), key=lambda x: x['sf'] / x['target'])
    return {'all_ok': all(x['ok'] for x in rows), 'worst': f"{worst['part']} {worst['case']} {worst['sf']}",
            'margin': round(worst['sf'] / worst['target'], 3), 'rows': rows}


def derate(sim: dict, stand: dict) -> dict:
    """PLA factors for every FEA row of the leg under the stand's runs. The simulation carries one mass for weight and
    inertia; the stand's weight at the foot and its inertia differ, so the simulated forces are scaled up by the larger
    of the two over the simulated mass (forces in a landing go roughly with the mass)."""
    from cadagent.fea import MATERIALS
    pla = MATERIALS['pla']
    S = _load(R / 'exports/leg/fea/summary.json')
    LC = {(r['part'], r['case']): r['layer_check'] for r in
          _load(R / 'research/leg-preprint/evidence/leg-layer-check-print-ready.json')['rows'] if r.get('layer_check')}
    rec = record_loads()
    runs = {(r['test'], r['cap_nm']): r for r in sim['runs']}
    caps = sorted(c for (t, c) in runs if t == 'jump')
    m_sim = sim['mass_kg']
    m_stand = max(stand['scale_reads_kg'], stand['effective_mass_kg'])
    lf = max(1.0, m_stand / m_sim)
    fea = [r for r in S['results'] if r['part'] != 'leg']
    out = {'pla': {'name': pla.name, 'strength_mpa': pla.strength_mpa, 'E_mpa': pla.E_mpa, 'note': pla.note,
                   'from': 'cadagent.fea.MATERIALS["pla"]'},
           'record': {'file': 'exports/leg/fea/summary.json', 'layer_check': 'research/leg-preprint/evidence/leg-layer-check-print-ready.json',
                      'mesh_mm': S.get('mesh_mm'), 'loads': rec},
           'sim': {'file': 'exports/motor-day/sim.json', 'mass_kg': m_sim},
           'mass': {'sim_kg': m_sim, 'stand_scale_kg': stand['scale_reads_kg'], 'stand_effective_kg': stand['effective_mass_kg'],
                    'load_factor': round(lf, 3),
                    'note': 'simulated forces x load_factor = the larger of the stand\'s weight at the foot and its inertia over '
                            'the simulated mass (never below 1)'},
           'targets': {'landing': LANDING_TARGET, 'cap': 2.0, 'fault': FAULT_TARGET}, 'caps': {}, 'power_cut': {}}
    for cap in caps:
        run = runs[('jump', cap)]
        rows = [_row(r, f, t, why, pla, LC) for r in fea for f, t, why in scale_of(r['part'], r['case'], run, rec, cap, lf)]
        out['caps'][str(cap)] = {'jump_mm': run['jump_height_mm'], 'axle_n': run['peak_axle_force_n'], 'knee_n': knee_of(run),
                                 'hub_nm': run.get('peak_gearbox_nm'), **_verdict(rows)}
    ok = [c for c in caps if out['caps'][str(c)]['all_ok']]
    cap = out['pla_cap_nm'] = max(ok) if ok else None
    # the heaviest stand the cap still holds: the landing rows scale with the mass, the cap rows do not
    if cap:
        land = [r for r in out['caps'][str(cap)]['rows'] if r['case'] in ('R1', 'R1F', 'R1w') and r['sf']]
        out['mass']['max_stand_kg'] = round(m_sim * lf * min(r['sf'] / r['target'] for r in land), 2)
    for test in ('power_off', 'power_off_damped'):
        off = next((r for r in sim['runs'] if r['test'] == test), None)
        if off:
            rows = [_row(r, f, t, why, pla, LC) for r in fea for f, t, why in cut_scale(r['part'], r['case'], off, rec, lf)]
            out['power_cut'][test] = {'cap_nm': off['cap_nm'], 'axle_n': off['peak_axle_force_n'], 'knee_n': knee_of(off),
                                      'hip_n': hip_of(off), 'hub_nm': off.get('peak_gearbox_nm'), **_verdict(rows)}
    out['stand_cap_nm'] = max(r['cap_nm'] for r in sim['runs'] if r['test'] != 'jump')
    out['stand_runs'] = {r['test']: {'cap_nm': r['cap_nm'], 'peak_motor_nm': r['peak_motor_nm'], 'knee_n': knee_of(r),
                                     'hip_n': hip_of(r), 'axle_n': r['peak_axle_force_n'], 'hub_nm': r.get('peak_gearbox_nm')}
                         for r in sim['runs'] if r['test'] != 'jump'}
    if out['pla_cap_nm'] is None or out['stand_cap_nm'] > out['pla_cap_nm']:
        raise SystemExit(f"the stand-up, squat and power-cut runs are at {out['stand_cap_nm']:g} N m, above the PLA cap "
                         f"({out['pla_cap_nm']}): lower STAND_CAP in tools/motor_day_sim.py and rerun it")
    # the hub clamp in tapped PLA: the record's friction at its preload, at the PLA torque's preload (T = K F d, K 0.2)
    j = S['joints']['R1']['hub_rear']
    t_pla = 1.0
    pre = t_pla / (0.2 * 0.005)
    out['hub_clamp'] = {'torque_nm': t_pla, 'preload_n': round(pre), 'record_friction_nm': j['friction_nm'],
                        'record_preload_n': 1200, 'friction_nm': round(j['friction_nm'] * pre / 1200, 1),
                        'note': 'eight M5 x 40 into the PLA adapter\'s hand-tapped holes at 1.0 N m (K = 0.2): the clamp\'s friction against the hub torque; '
                                'the two dowels carry the rest. PLA creeps under a clamp: re-torque '
                                'before each session.'}
    return out


# ------------------------------------------------------------------------------------------------- BOM


SUBS = {   # what a builder may already have that does the same job (the CAD's numbers in brackets)
    'screw_m4x20': 'any M4 x 20 socket head, class 12.9 (10.9 at a pinch); length matters: the RS-04 has 5 mm of usable thread',
    'screw_m5x25': 'any M5 x 25 socket head, class 10.9 or 12.9',
    'screw_m5x30': 'any M5 x 30 socket head; check 10-11 mm reaches into the insert through your plywood',
    'screw_m5x40': 'any M5 x 40 socket head (partly threaded is fine)',
    'screw_m6x40': 'any M6 x 40 socket head',
    'nut_m6_nyloc': 'any M6 nylon-insert nut (10 mm across flats: the foot\'s pocket is 10.4)',
    'nut_m10_nyloc': 'any M10 x 1.5 nylon-insert nut',
    'washer_m5_large': 'any M5 fender washer, 15 mm OD or more',
    'washer_m12_thin': 'any M12 washer 20 mm OD or less (it must clear the knee boss)',
    'washer_m6_din433': 'any M6 washer of 11 mm OD or less (a DIN 125 at 12 mm touches the hub bore)',
    'dowel_5x16': 'any 5 mm h6/m6 steel dowel, 16 mm',
    'dowel_5x20': 'any 5 mm h6/m6 steel dowel, 20 mm',
    'insert_m5': 'any M5 heat-set insert for a 6.4 mm hole, about 8 mm long',
    'knee_spacer': '5/8 in (15.9 mm) aluminium or steel tube, cut to 24 mm',
    'stop_pin': 'a 16 mm steel rod or dowel, 40 mm long',
    'circlip_60': 'any DIN 471 external ring for a 60 mm shaft',
    'bearing_6301': 'any 6301-2RS (12 x 37 x 12), check C0 >= 4.15 kN',
    'bearing_61812': '6812-2RS or -2Z (60 x 78 x 10) from any bearing shop',
}

DAY_ONE_CHANGES = {   # leg BOM key -> (replacement key or None, why)
    'robstride-rs-04': (None, 'in hand (arrived: Phase 0 checks them)'),
    'odrive-botwheel': (None, 'later: the printed foot stands in on day one (other vendors)'),
    'screw_m6x30': ('screw_m6x40', 'the foot is 24 mm thick: M6 x 40 through it into a nylon-insert nut'),
}
EXTRA = [   # (key, qty, what for): parts day one adds
    ('nut_m6_nyloc', 4, 'the foot: in its hex pockets on the M6 x 40'),
    ('screw_m5x30', 6, 'the stand: the end plate to the hip frame\'s inserts (18.3 mm plywood + washer: 10.5 mm into the 11 mm pilot)'),
    ('washer_m5_large', 6, 'the stand: under the M5 x 30 heads on the plywood'),
]


def hardware_rows():
    bom = _load(R / 'exports/leg/bom.json')['per_leg']
    hw = {i['key']: i for i in _load(R / 'catalog/hardware.json')}
    rows, mc, other = [], [], []
    for b in bom:
        key, qty, why = b['key'], b['qty'], b['for']
        if key in DAY_ONE_CHANGES:
            new, note = DAY_ONE_CHANGES[key]
            if new is None:
                other.append({'key': key, 'qty': qty, 'name': b.get('name') or f"{b['vendor']} {b['part_number']}",
                              'vendor': b['vendor'], 'part_number': b['part_number'], 'price_usd_each': b.get('price_usd_each'),
                              'for': why, 'day_one': note})
                continue
            key, why = new, f'{why} ({note})'
        rows.append((key, qty, why))
    rows += EXTRA
    merged = {}
    for key, qty, why in rows:
        if key in merged:
            merged[key]['qty'] += qty
            merged[key]['for'] += '; ' + why
        else:
            merged[key] = {'key': key, 'qty': qty, 'for': why}
    for key, m in merged.items():
        h = hw[key]
        pn, url = h.get('model'), None
        for b in h.get('buy', []):
            if b.get('seller') == 'McMaster-Carr':
                url = b.get('url')
        if h['vendor'] != 'McMaster-Carr':          # a non-McMaster primary with a McMaster same-trade-number listing
            mcb = next((b for b in h.get('buy', []) if b.get('seller') == 'McMaster-Carr'), None)
            if mcb:
                pn = mcb['url'].rstrip('/').split('/')[-1]
        pack = h.get('pack_qty') or 1
        each = h.get('price_usd')
        pieces = PIECES_PER.get(key, 1)                   # a stock length that is cut into several parts
        packs = math.ceil(m['qty'] / pieces / pack)
        pack_price = h.get('pack_price_usd') or (each * pack if each else None)
        mc.append({**m, 'mcmaster': pn if (url or pn) else None, 'name': h['name'], 'url': url or (f'https://www.mcmaster.com/{pn}/' if pn else None),
                   'price_usd_each': each, 'pack_qty': pack, 'packs': packs,
                   'cost_usd': round(packs * pack_price, 2) if pack_price else None,
                   'price_checked': h.get('price_checked'), 'substitute': SUBS.get(key, ''),
                   'mass_g_each': (h.get('specs') or {}).get('mass_g'),
                   'note': (h.get('buy') and next((b.get('note') for b in h['buy'] if b.get('note')), None)) or ''})
    return mc, other


PIECES_PER = {'knee_spacer': 4}   # catalog/hardware.json: one 5/8 in tube length cuts four 24 mm spacers

ELEC_PHASE0 = ('usb_can_u2c', 'bench_supply_36v', 'resistor_120', 'xt30_male', 'wire_12awg', 'can_cable', 'gh_header_2p', 'heatshrink_kit')


def other_vendor_rows(other: list, slices: dict) -> list:
    rig = _load(R / 'catalog/rig.json')
    mats = _load(R / 'catalog/materials.json')
    out = []
    g = {'pla': 0.0, 'tpu': 0.0}
    for key, f, qty, recipe, phase, _ in PRINTS:
        s = slices.get(key) or {}
        if s.get('grams'):
            g['tpu' if recipe == 'tpu' else 'pla'] += s['grams'] * qty
    for k, name, mkey in (('pla', 'Bambu Lab PLA Basic, 1 kg spool', 'pla'), ('tpu', 'Bambu Lab TPU 95A HF, 1 kg spool', 'tpu95')):
        m = mats[mkey]
        need = g[k] * 1.1 / 1000                              # 10 % for purge, brim and supports
        n = max(1, math.ceil(need))
        out.append({'group': 'filament', 'item': name, 'qty': n, 'vendor': 'Bambu Lab', 'part_number': '',
                    'price_usd_each': m['price_usd_per_kg'], 'cost_usd': round(n * m['price_usd_per_kg'], 2),
                    'url': m['source'][-1], 'when': 'Phase 1', 'note': f'{g[k] / 1000:.2f} kg sliced + 10 %'})
    for o in other:
        out.append({'group': 'leg', 'item': o['name'], 'qty': o['qty'], 'vendor': o['vendor'], 'part_number': o['part_number'],
                    'price_usd_each': o['price_usd_each'], 'cost_usd': None, 'url': '', 'when': 'later', 'note': o['day_one']})
    out.append({'group': 'leg', 'item': 'Output adapter, machined 6061-T6 (exports/leg/cnc/output_adapter.step, README.md)', 'qty': 2,
                'vendor': 'JLCCNC (instant price on upload)', 'part_number': '', 'price_usd_each': None, 'cost_usd': None,
                'url': 'https://jlccnc.com/', 'when': 'order now (5-10 days)',
                'note': 'replaces the PLA stand-ins before any cap above the PLA cap'})
    out.append({'group': 'leg', 'item': 'Structural epoxy, two-part, metal to plastic (D74)', 'qty': 1, 'vendor': 'owner\'s choice',
                'part_number': '', 'price_usd_each': None, 'cost_usd': None, 'url': '', 'when': 'Phase 3',
                'note': 'the stop pins, the knee-eye sleeves, the RS-04 dowels; not an anaerobic retainer on plastic'})
    for i in rig:
        if i.get('group') != 'electronics':
            continue
        alt = (i.get('alternates') or [])
        us = next((a for a in alt if 'west3d' in (a.get('url') or '') or 'inno-maker' in (a.get('url') or '')), None)
        out.append({'group': 'electronics', 'item': i['name'], 'qty': i.get('qty') or 1, 'vendor': i['vendor'],
                    'part_number': i.get('model') or '', 'price_usd_each': i.get('price_usd'),
                    'cost_usd': round((i.get('pack_price_usd') or i.get('price_usd') or 0) * math.ceil((i.get('qty') or 1) / (i.get('pack_qty') or 1)), 2) or None,
                    'url': (i.get('buy') or [{}])[0].get('url', ''),
                    'when': 'Phase 0 (bench spin-up)' if i['key'] in ELEC_PHASE0 else 'Phase 4 (the pod: pendant, contactor, relay)',
                    'note': (f"US alternate: {us['supplier']} {us['part_number']} {us['price']}" if us and i['key'] == 'usb_can_u2c' else '')
                    + (' ships from China: order the US alternate for day one' if i['key'] == 'usb_can_u2c' else '')})
    for name, qty, note in (('2x4 lumber, 8 ft (the rails, cleats, uprights, braces, floor stop)', 4, 'straight and dry; spruce-pine-fir'),
                            ('Plywood 23/32 in, 2 x 4 ft (the end plate, the base, the stop board)', 1, 'catalog/rig.json plywood_18'),
                            ('Carriage bolt 1/2-13 x 5 in, 2 fender washers, 1 nylon-insert nut (the pivot, each side)', 2, ''),
                            ('Construction screws #10 x 3 in (rails to cleats, cleats through the plate, uprights, braces)', 40, ''),
                            ('Rope 6 mm (1/4 in), 3 m, and a screw eye (the tether)', 1, ''),
                            ('Sandbags or weight plates (on the stand\'s base)', 4, ''),
                            ('Bathroom scale (weigh the boom\'s end: the effective mass)', 1, 'in hand?'),
                            ('Rubber mat under the foot', 1, 'catalog/rig.json rubber_mat (Amazon)')):
        out.append({'group': 'stand (hardware store)', 'item': name, 'qty': qty, 'vendor': 'any hardware store', 'part_number': '',
                    'price_usd_each': None, 'cost_usd': None, 'url': '', 'when': 'Phase 2', 'note': note or 'price not checked'})
    return out


# ------------------------------------------------------------------------------------------------- items and CAD names

# the leg's CAD names (build_rig.leg_parts, prefix 'leg_') -> the BOM key each one is
CAD_ITEM = [
    ('leg_hip_frame', 'hip_frame'), ('leg_upper_link', 'upper_link'), ('leg_front_link', 'front_link'),
    ('leg_wheel_link', 'wheel_link'), ('leg_apex_spacer', 'apex_spacer'), ('leg_stop_sleeve', 'stop_sleeve'),
    ('leg_output_adapter', 'output_adapter_pla'), ('leg_motor', 'robstride-rs-04'), ('leg_bearing_61812', 'bearing_61812'),
    ('leg_apex_61812', 'bearing_61812'), ('leg_knee_bearing', 'bearing_6301'), ('leg_knee_pin', 'knee_pin'),
    ('leg_knee_nut_upper', 'nut_m10_nyloc'), ('leg_knee_washer', 'washer_m12_thin'), ('leg_knee_spacer', 'knee_spacer'),
    ('leg_eye_sleeve', 'eye_sleeve'), ('leg_apex_circlip', 'circlip_60'), ('leg_stop_posts', 'stop_pin'),
    ('leg_screws_lugs', 'screw_m4x20'), ('leg_screws_links', 'screw_m5x40'), ('leg_screws_outputs', 'screw_m5x25'),
    ('leg_screws_wheel', 'screw_m6x40'), ('leg_washers_wheel', 'washer_m6_din433'), ('foot', 'foot'),
    ('end_plate', 'end_plate'), ('cleat', 'cleat'), ('rail', 'rail'), ('cross_member', 'cross_member'), ('upright', 'upright'),
    ('brace', 'brace'), ('base', 'base'), ('pivot_bolt', 'pivot_bolt'), ('floor_stop', 'floor_stop'), ('stop_pad', 'stop_pad'),
    ('stop_board', 'stop_board'), ('tether', 'tether'), ('mat', 'mat'), ('frame_screws', 'screw_m5x30'),
]
STAND_ITEMS = {   # stand parts as BOM lines: key -> (name, qty, source)
    'end_plate': ('End plate, 300 x 260 plywood (drill through the template)', 1, 'plywood, cut'),
    'cleat': ('Cleat, 2x4 x 260', 2, 'lumber, cut'), 'rail': ('Boom rail, 2x4 x 1500', 2, 'lumber, cut'),
    'cross_member': ('Cross member, 2x4 between the rails\' far ends', 1, 'lumber, cut'),
    'upright': ('Upright, 2x4 (pivot post)', 2, 'lumber, cut'), 'brace': ('Brace, 2x4 at 45 deg', 2, 'lumber, cut'),
    'base': ('Base, plywood', 1, 'plywood, cut'), 'pivot_bolt': ('Pivot: 1/2-13 x 5 in carriage bolt, washers, nyloc', 2, 'hardware store'),
    'floor_stop': ('Floor stop, 2x4 offcuts stacked', 2, 'lumber, cut'), 'stop_pad': ('Rubber pad on the floor stop', 2, 'rubber mat offcut'),
    'stop_board': ('Stop board, plywood', 1, 'plywood, cut'), 'tether': ('Tether: rope and screw eye', 1, 'hardware store'),
    'mat': ('Rubber mat under the foot', 1, 'catalog/rig.json rubber_mat'),
}


def item_numbers(prints, mc, other_leg):
    """One number per BOM line, in build order: prints, then McMaster-Carr, the leg's other bought parts, the stand."""
    keys = [p['key'] for p in prints if not p['key'].startswith('coupon_')] + [m['key'] for m in mc] + [o['key'] for o in other_leg] \
        + list(STAND_ITEMS)
    return {k: i + 1 for i, k in enumerate(dict.fromkeys(keys))}


def item_of(name: str, items: dict):
    for pre, key in CAD_ITEM:
        if name == pre or name.startswith(pre + '_') or name.startswith(pre):
            return items.get(key)
    return None


# ------------------------------------------------------------------------------------------------- assembly

def scene():
    """Every part of the leg on the stand at the stance, the BotWheel swapped for the foot: name -> shape."""
    import build_rig as br
    P = {n: s for n, (s, _) in br.leg_parts(STANCE, 0.0, 0.0).items() if n not in ('leg_wheel_tyre', 'leg_wheel_hub')}
    sw = P['leg_screws_wheel']
    ax = sw.BoundingBox()
    cx, cz = (ax.xmin + ax.xmax) / 2, (ax.zmin + ax.zmax) / 2            # the axle: the four screws sit round it
    holes = [(c.x - cx, c.z - cz) for c in (so.Center() for so in sw.Solids())]
    f, fm = foot(holes)                                                  # the foot's holes where the wheel link's are
    P['foot'] = f.val().translate(cq.Vector(cx, 0, cz))
    st, meta = stand_parts()
    for n, s in st.items():
        P[n] = s.val() if hasattr(s, 'val') else s
    return P, meta, fm


STEPS = [   # (title, parts added (prefixes), lift (mm along x, y, z) per prefix, view, what to do)
    ('The stand: base, uprights, braces', ['base', 'upright', 'brace', 'stop_board', 'floor_stop', 'stop_pad', 'mat'],
     {'upright': (0, 0, 80), 'brace': (0, -60, 60), 'stop_pad': (0, 0, 40)}, (1.0, 0.8, 0.6),
     'Screw the uprights to the base (four #10 x 3 in each, from below), the braces between them and the base. Stack the '
     'floor stop under where the rails will be and top it with the rubber pad. Weight the base with sandbags.'),
    ('The boom', ['rail', 'cleat', 'cross_member', 'end_plate', 'pivot_bolt'],
     {'end_plate': (0, 60, 0), 'cleat': (0, 30, 0), 'pivot_bolt': (90, 0, 0)}, (1.0, 0.8, 0.6),
     'Drill the end plate through the printed template (six Ø5.5 and the two lead slots). Screw the cleats to the plate\'s '
     'back through its face, then the rails to the cleats\' outer faces (four screws each, glued). Join the rails\' far ends '
     'with the cross member. Hang the rails between the uprights on the two carriage bolts, a fender washer each side.'),
    ('Hip frame and motors (bench)', ['leg_hip_frame', 'leg_bearing_61812_front', 'leg_bearing_61812_rear', 'leg_motor',
                                      'leg_screws_lugs', 'leg_stop_posts'],
     {'leg_bearing_61812': (0, -25, 0), 'leg_motor': (0, -70, 0), 'leg_screws_lugs': (0, 40, 0), 'leg_stop_posts': (0, 40, 0)},
     (0.85, 1.0, 0.55),
     'Heat-set the six M5 inserts. Press the two 61812s in from the motor side onto their lip (the C1 coupon says how tight '
     'PLA comes out). Drill the four Ø5 dowel holes deeper with a 5.2 mm drill, its tip 14.5 mm in (the same tape mark '
     'as Phase 0.3), so a dowel stops 13 mm down. With the epoxy, '
     'bond the four stop pins, and the four Ø5 x 16 dowels pushed to the bottom; wipe the squeeze-out flush with the seat '
     'face, and hold each dowel square to the face (a small square against it) while the epoxy sets. After the cure, '
     'check each dowel stands 3.0 mm proud (2.0 to 3.5). Each motor on its two dowels (into the '
     'case\'s two locating holes) and ten M4 x 20, snug only: the lug torque is not established (#116).'),
    ('Upper links and adapters (bench)', ['leg_output_adapter', 'leg_screws_outputs', 'leg_eye_sleeve', 'leg_upper_link',
                                          'leg_screws_links'],
     {'leg_output_adapter': (0, 50, 0), 'leg_screws_outputs': (0, 80, 0), 'leg_eye_sleeve': (0, 70, 0),
      'leg_upper_link': (0, 110, 0), 'leg_screws_links': (0, 150, 0)}, (0.85, 1.0, 0.55),
     'Tap the PLA adapters\' eight M5 holes. Each adapter onto its motor\'s output: nine M5 x 25, heads in the pockets, '
     'snug (PLA: no 6 N m). The two DIN 179 sleeves bonded end to end into each link\'s knee eye. Each link on its adapter: '
     'two Ø5 x 20 dowels, eight M5 x 40 at 1.0 N m. Both links swing freely to their bare stop pins.'),
    ('Knees', ['leg_front_link', 'leg_wheel_link', 'leg_knee'], {'leg_front_link': (0, 70, 0), 'leg_wheel_link': (0, 110, 0),
                                                                  'leg_knee_pin': (0, 150, 0)}, (0.85, 1.0, 0.55),
     'Two 6301-2RS and the 24 mm spacer into each lower link\'s knee boss, a washer each side; the 12 x 90 shoulder screw '
     'from outside through the lower link and the eye sleeves; the M10 nyloc in the upper link\'s pocket (20 N m: steel on '
     'steel). The knees turn freely.'),
    ('Apex and foot', ['leg_apex_61812', 'leg_apex_spacer', 'leg_apex_circlip', 'foot', 'leg_screws_wheel', 'leg_washers_wheel'],
     {'leg_apex_61812': (0, 60, 0), 'leg_apex_spacer': (0, -40, 0), 'leg_apex_circlip': (0, -60, 0), 'foot': (0, 90, 0),
      'leg_screws_wheel': (0, -50, 0), 'leg_washers_wheel': (0, -40, 0)}, (0.85, 1.0, 0.55),
     'The two 61812s into the front link\'s apex eye, the wheel link\'s hub through them with the printed spacer, the '
     'circlip. The foot\'s boss into the wheel link\'s recess, four M6 nylon-insert nuts in its pockets, four M6 x 40 from '
     'inside the hub on the DIN 433 washers at 0.9 N m (the nuts bear on printed PLA: half the PA6-CF leg\'s torque). '
     'The leg folds and stretches by hand from stop to stop.'),
    ('Stop sleeves, then onto the boom', ['leg_stop_sleeve'], {'leg_stop_sleeve': (0, 50, 0)}, (1.0, 0.8, 0.6),
     'The TPU sleeves over the stop pins. The leg onto the end plate: six M5 x 30 with fender washers from the plate\'s '
     'back into the hip frame\'s inserts (1.5 N m), each motor\'s lead through its slot. Tie the tether. Put the leg\'s '
     'foot on the bathroom scale with the motors unpowered, the boom resting on it, and write the reading down: it is '
     '`--half-mass` in the ladder. No ballast.'),
]


def render_steps(P, items):
    from cadagent.render import Renderer
    import build_rig as br
    d = OUT / 'steps'
    d.mkdir(parents=True, exist_ok=True)
    r = Renderer(d, size=(1400, 1000), subtitle='GYROPUP MOTOR DAY | THE PLA LEG ON THE BOOM STAND')
    grey, done, rows = (0.80, 0.81, 0.83), [], []
    wood, ply = (0.80, 0.66, 0.45), (0.86, 0.75, 0.56)

    def col(n):
        if n.startswith(('rail', 'cleat', 'cross', 'upright', 'brace', 'floor_stop')):
            return wood
        if n.startswith(('end_plate', 'base', 'stop_board')):
            return ply
        if n == 'foot':
            return (0.96, 0.72, 0.16)
        if n in ('mat', 'stop_pad'):
            return (0.18, 0.19, 0.21)
        return br.colour(n)
    leg_only = lambda n: n.startswith('leg_') or n == 'foot'  # noqa: E731
    for k, (title, add0, lift0, view, how) in enumerate(STEPS, 1):
        on_leg = add0[0].startswith('leg_') and k < len(STEPS)
        add = [n for n in P if any(n == a or n.startswith(a) for a in add0)]
        shapes = []
        for n in done:
            if n in add or (on_leg and not leg_only(n)):
                continue
            shapes.append((P[n], grey))
        for n in add:
            off = next((v for a, v in lift0.items() if n.startswith(a)), (0, 0, 0))
            shapes.append((P[n], col(n), off))
        labels, seen = [], set()
        for j, n in enumerate(add):
            it = item_of(n, items)
            if it is None or it in seen:
                continue
            seen.add(it)
            bb = P[n].BoundingBox()
            off = next((v for a, v in lift0.items() if n.startswith(a)), (0, 0, 0))
            c = ((bb.xmin + bb.xmax) / 2 + off[0], (bb.ymin + bb.ymax) / 2 + off[1], (bb.zmin + bb.zmax) / 2 + off[2])
            m = len(seen) - 1
            tx = 40 if m % 2 == 0 else 1110
            labels.append((str(it), _short(n), c, (tx, 150 + (m // 2) * 62)))
        f = f'step-{k:02d}.png'
        r.render(f, shapes=shapes, view=view, caption=f'{k}. {title}', note=how.split('. ')[0][:118], labels=labels, zoom=0.86)
        rows.append({'step': k, 'title': title, 'adds': add, 'items': sorted(seen), 'how': how, 'picture': f'exports/motor-day/steps/{f}'})
        done += [n for n in add if n not in done]
    return rows


def _short(n: str) -> str:
    for pre, key in CAD_ITEM:
        if n.startswith(pre):
            return key.replace('_', ' ')
    return n


# ------------------------------------------------------------------------------------------------- drawings

def drawings(P, items, names, rev, meta, fm):
    from matplotlib.backends.backend_pdf import PdfPages
    import drawing_sheet as ds
    d = OUT / 'drawings'
    d.mkdir(parents=True, exist_ok=True)

    def parts(prefixes):
        groups = {}
        for n in P:
            if any(n == p or n.startswith(p) for p in prefixes):
                it = item_of(n, items)
                groups.setdefault((it, n if it is None else it), []).append(P[n])
        return [ds.Part(v, k[0]) for k, v in groups.items()]

    def rows_for(prts, extra=()):
        """The sheet's parts list: what it draws (ballooned) and the extras it names but has no model of."""
        drawn = {p.item for p in prts if p.item}
        out = []
        for it in sorted(drawn | {items[k] for k in extra if k in items}):
            key = next(k for k, v in items.items() if v == it)
            nm, qty, src = names.get(key, (key, '', ''))
            out.append((it, qty, nm if it in drawn else f'[not drawn] {nm}', src))
        return out
    y0, y1 = meta['plate_y']
    sheets = []
    # MD-01: the hip module
    hip = ['leg_hip_frame', 'leg_bearing_61812_front', 'leg_bearing_61812_rear', 'leg_motor', 'leg_screws_lugs', 'leg_stop_posts',
           'leg_stop_sleeve']
    s = ds.Sheet('Hip module', 'MD-01', rev, 'the hip frame, the two RS-04s, the support bearings, the stop pins',
                 notes=['Inserts: six M5 heat-set in the flange ends (item list). Lug screws snug only: the torque is not '
                        'established (#116). Stop pins bonded with structural epoxy (D74).'])
    pr = parts(hip)
    s.view('front (leg side)', pr, direction=(0, 1, 0), up=(0, 0, 1), box=(0.0, 0.42, 0.62, 0.58), hidden=False)
    s.view('top', pr, direction=(0, 0, -1), up=(0, 1, 0), box=(0.0, 0.0, 0.62, 0.42), hidden=False, balloons=False)
    s.view('iso', pr, direction=(-0.8, 1.0, -0.6), up=(0, 0, 1), box=(0.62, 0.2, 0.38, 0.6), hidden=False)
    mounts = fb.frame_mounts()['inserts_xz']
    s.dim('front (leg side)', (mounts[0][0], 0, mounts[0][1]), (mounts[2][0], 0, mounts[2][1]), offset=22)
    s.dim('front (leg side)', (mounts[2][0], 0, mounts[3][1]), (mounts[2][0], 0, mounts[2][1]), offset=-30)
    s.dim('front (leg side)', (-75, 0, -60), (75, 0, -60), offset=-36, text='150 (motor axes)')
    s.parts_list(rows_for(pr, ('insert_m5', 'dowel_5x16')))
    sheets.append(s)
    # MD-02: an upper link on its adapter
    ul = ['leg_upper_link_front', 'leg_output_adapter_front', 'leg_eye_sleeve_front', 'leg_screws_links', 'leg_screws_outputs']
    s = ds.Sheet('Upper link and adapter', 'MD-02', rev, 'the front side; the rear is its mirror about x = 0',
                 notes=['PLA adapter (day one): tap the eight M5 holes by hand; M5 x 40 at 1.0 N m. Replace with the machined '
                        '6061 adapter before any run above the PLA cap.'])
    # the front side only, solid by solid (a part's model may hold both sides in one compound)
    pr = [ds.Part([so for sh in p.shapes for so in (sh.Solids() or [sh]) if _cx(so) > 0], p.item) for p in parts(ul)]
    pr = [p for p in pr if p.shapes]
    s.view('side', pr, direction=(0, 1, 0), up=(0, 0, 1), box=(0.0, 0.35, 0.62, 0.65), hidden=False)
    s.view('top', pr, direction=(0, 0, -1), up=(0, 1, 0), box=(0.0, 0.0, 0.62, 0.35), hidden=False, balloons=False)
    s.view('iso', pr, direction=(-0.8, 1.0, -0.6), up=(0, 0, 1), box=(0.62, 0.2, 0.38, 0.6), hidden=False)
    bh, bk = P['leg_output_adapter_front'].BoundingBox(), P['leg_eye_sleeve_front'].BoundingBox()
    hip_c = ((bh.xmin + bh.xmax) / 2, 0, (bh.zmin + bh.zmax) / 2)
    knee_c = ((bk.xmin + bk.xmax) / 2, 0, (bk.zmin + bk.zmax) / 2)
    s.dim('side', hip_c, knee_c, offset=-45, text=f'{math.dist(hip_c, knee_c):.1f} hip to knee')
    s.dim('side', (bh.xmin, 0, hip_c[2]), (bh.xmax, 0, hip_c[2]), offset=bh.zlen / 2 + 18, text=f'Ø{bh.xlen:.0f} adapter')
    s.parts_list(rows_for(pr, ('dowel_5x20',)))
    sheets.append(s)
    # MD-03: the knees, the apex and the foot
    lw = ['leg_front_link', 'leg_wheel_link', 'leg_knee', 'leg_apex', 'foot', 'leg_screws_wheel', 'leg_washers_wheel']
    s = ds.Sheet('Lower links, knees, apex and foot', 'MD-03', rev, 'the five-bar\'s lower half at the 300 mm stance',
                 notes=['Knee nuts 20 N m (steel on steel). Foot: M6 x 40 on DIN 433 washers into nyloc nuts in its pockets, '
                        '0.9 N m (PLA under the nuts: re-torque before each session). The foot does not turn: it stands in for the '
                        'BotWheel at the tyre\'s radius.'])
    pr = parts(lw)
    s.view('side', pr, direction=(0, 1, 0), up=(0, 0, 1), box=(0.0, 0.3, 0.6, 0.7), hidden=False)
    s.view('front', pr, direction=(-1, 0, 0), up=(0, 0, 1), box=(0.6, 0.3, 0.4, 0.7), hidden=False, balloons=False)
    ax = P['foot'].BoundingBox()
    zc = (ax.zmin + ax.zmax) / 2
    s.dim('side', (-WHEEL_R, 0, zc), (WHEEL_R, 0, zc), offset=-(WHEEL_R + 20), text=f'Ø{2 * WHEEL_R:.1f} (the tyre\'s)')
    s.dim('side', (220, 0, 0), (220, 0, zc - WHEEL_R), offset=-25, text=f'{STANCE + WHEEL_R:.0f} hip to floor')
    s.parts_list(rows_for(pr, ('nut_m6_nyloc',)))
    sheets.append(s)
    # MD-04: the foot itself
    f, _ = foot()
    s = ds.Sheet('Foot (BotWheel stand-in)', 'MD-04', rev, 'printed PLA, 4 walls, 30 % gyroid; the outer face on the bed',
                 notes=['Glue a strip of rubber (a bike inner tube) round the rim for grip.', 'Not in the FEA record: '
                        'inspect it after every rung.'])
    pr = [ds.Part([f], items.get('foot'))]
    s.view('face', pr, direction=(0, 1, 0), up=(0, 0, 1), box=(0.0, 0.3, 0.55, 0.7))
    s.view('side', pr, direction=(-1, 0, 0), up=(0, 0, 1), box=(0.55, 0.3, 0.2, 0.7), balloons=False)
    s.view('iso', pr, direction=(-0.8, 1.0, -0.6), up=(0, 0, 1), box=(0.75, 0.3, 0.25, 0.7), hidden=False, balloons=False)
    s.dim('face', (-WHEEL_R, 0, 0), (WHEEL_R, 0, 0), offset=-(WHEEL_R + 14))
    s.dim('face', (-WHEEL_R + 10, 0, 0), (WHEEL_R - 10, 0, 0), offset=WHEEL_R + 10)
    s.dim('side', (0, fm['y_face'], -WHEEL_R), (0, fm['y_out'], -WHEEL_R), offset=-14)
    s.dim('face', (-12.73, 0, -12.73), (12.73, 0, 12.73), offset=30, text='36 PCD, 4 x Ø6.6, hex 10.4 AF')
    s.dim('face', (-24.8, 0, 0), (24.8, 0, 0), offset=-48, text='Ø49.6 boss x 4.8')
    s.parts_list([(items.get('foot'), 1, 'Foot, PLA', 'print: foot.stl / .3mf')])
    sheets.append(s)
    # MD-05: the stand
    st = ['end_plate', 'cleat', 'rail', 'cross_member', 'upright', 'brace', 'base', 'pivot_bolt', 'floor_stop', 'stop_pad',
          'stop_board', 'tether']
    ctx = ['leg_hip_frame', 'leg_motor', 'leg_upper_link', 'leg_front_link', 'leg_wheel_link', 'foot']
    s = ds.Sheet('Boom stand', 'MD-05', rev, 'the leg on the end of a pivoting 2x4 boom; the floor stop catches it at a '
                 f'{FLOOR_STOP_LEG:.0f} mm leg', notes=[
                     f"Floor stop {meta['floor_stop_height_mm']:.0f} mm tall (rubber pad included): set it so the rails land on "
                     f"it with the leg at {FLOOR_STOP_LEG:.0f} mm, before the leg reaches its own stops.",
                     f"Tether: {meta['tether_length_note']}.", 'Lumber and plywood densities are estimates: weigh the boom\'s '
                     'end on a scale (Phase 3, last step).'])
    pr = parts(st) + [ds.Part(p.shapes, None) for p in parts(ctx)]
    s.view('side', pr, direction=(-1, 0, 0), up=(0, 0, 1), box=(0.0, 0.40, 1.0, 0.60), hidden=False, deflection=1.0)
    s.view('top', pr, direction=(0, 0, -1), up=(1, 0, 0), box=(0.0, 0.0, 0.62, 0.40), hidden=False, deflection=1.0, balloons=False)
    s.view('leg end', pr, direction=(0, -1, 0), up=(0, 0, 1), box=(0.62, 0.0, 0.38, 0.40), hidden=False, deflection=1.0, balloons=False)
    s.dim('side', (0, meta['pivot_y'], 0), (0, 0, 0), offset=110, text=f"{-meta['pivot_y']:.0f} pivot to hip")
    s.dim('side', (0, 0, FLOOR_Z), (0, 0, 0), offset=-(fm['tread_mid_y'] + 60), text=f'{-FLOOR_Z:.0f}')
    s.dim('side', (0, meta['floor_stop_y'], FLOOR_Z), (0, meta['floor_stop_y'], meta['floor_stop_top_z']), offset=60)
    s.parts_list(rows_for(pr, ('screw_m5x30', 'washer_m5_large')))
    sheets.append(s)
    pdf_path = d / 'motor-day-drawings.pdf'
    out = []
    with PdfPages(pdf_path) as pdf:
        for sh in sheets:
            png = d / f'{sh.number}.png'
            sh.save(pdf, png)
            out.append({'number': sh.number, 'title': sh.title, 'png': f'exports/motor-day/drawings/{png.name}'})
            print(f'  {sh.number} {sh.title}', flush=True)
    return out


def _cx(sh):
    bb = sh.BoundingBox()
    return (bb.xmin + bb.xmax) / 2


# ------------------------------------------------------------------------------------------------- stand masses

def stand_masses(P, slices, mc, meta, fm) -> dict:
    """The boom's effective mass at the foot: sum m r^2 / R^2 about the pivot (what the leg accelerates), and sum m r / R
    (what a scale under the foot reads with the boom resting on it). Printed parts at their slicer grams, bought parts
    at their catalogue masses, lumber at an estimated density."""
    yp = meta['pivot_y']
    Rf = 0.0 - yp
    rows = []

    def add(name, m_g, y):
        rows.append((name, m_g, y - yp))
    lp = _load(R / 'catalog/leg_actuators.json')[0]['specs']['mass_g']
    leg_prints = {k: (slices.get(k) or {}).get('grams') for k, *_ in PRINTS}
    for n, sh in P.items():
        bb = sh.BoundingBox()
        yc = (bb.ymin + bb.ymax) / 2
        if n.startswith(('base', 'upright', 'brace', 'floor_stop', 'stop_pad', 'stop_board', 'mat', 'pivot', 'tether')):
            continue                                          # on the floor: does not move
        if n.startswith(('rail', 'cleat', 'cross_member')):
            add(n, sh.Volume() / 1000 * WOOD['spf'], yc)
        elif n == 'end_plate':
            add(n, sh.Volume() / 1000 * WOOD['plywood'], yc)
        elif n.startswith('leg_motor'):
            add(n, lp, yc)
    for k, g in leg_prints.items():
        if k.startswith('coupon') or k == 'drill_template' or not g:
            continue
        q = next(q for kk, _, q, *_ in PRINTS if kk == k)
        add(k, g * q, 0.0 if k != 'foot' else fm['tread_mid_y'])
    hw = sum((m.get('mass_g_each') or 0) * m['qty'] for m in mc)
    add('bought hardware', hw, 0.0)
    m_in = sum(m * r * r for _, m, r in rows) / Rf ** 2 / 1000
    m_st = sum(m * r for _, m, r in rows) / Rf / 1000
    return {'pivot_to_hip_mm': round(Rf, 1), 'effective_mass_kg': round(m_in, 2), 'scale_reads_kg': round(m_st, 2),
            'moving_kg': round(sum(m for _, m, _ in rows) / 1000, 2),
            'rows': [{'part': n, 'g': round(m), 'r_mm': round(r)} for n, m, r in rows],
            'note': 'lumber at 0.45 g/cm3 and plywood at 0.60 (estimates); printed parts at their sliced grams'}


# ------------------------------------------------------------------------------------------------- the page

def _fill(doc: str, tag: str, body: str) -> str:
    a, b = f'<!-- gen:{tag} -->', f'<!-- /gen:{tag} -->'
    i, j = doc.index(a), doc.index(b)
    return doc[:i + len(a)] + '\n' + body.strip() + '\n' + doc[j:]


def _h(minutes):
    return f'{minutes / 60:.1f} h' if minutes else '-'


def _money(v):
    return f'${v:,.2f}' if v else '-'


def _and(words: list) -> str:
    return ', '.join(words[:-1]) + (' and ' if len(words) > 1 else '') + (words[-1] if words else '')


def write_doc(ctx):
    doc = DOC.read_text()
    slices, der, stand, steps, sheets, mc, other = (ctx[k] for k in ('slices', 'der', 'stand', 'steps', 'sheets', 'mc', 'other'))
    meta, items = ctx['meta'], ctx['items']
    cap = der['pla_cap_nm']
    # ---- the stand
    giv = ['| The rig has | The boom stand |', '|---|---|',
           '| Vertical rails: the hip goes straight up | An arc about the pivot: over a 150 mm rise the foot moves '
           f"{150 ** 2 / (2 * stand['pivot_to_hip_mm']):.0f} mm along the boom (the wheel's axle direction) |",
           '| 14.75 kg of ballast, the robot\'s half | no ballast: the boom\'s own weight at the foot (below), lighter, so gentler landings |',
           '| ToF height sensor, load plate | none: the motors\' encoders give the leg\'s length; film the jump against a tape |',
           '| Bumpers and a top stop | the floor stop and the tether |',
           '| The rig\'s numbers (S1-S6) compare with the simulation | rough: the arc and the boom\'s inertia are not in the model |']
        # the stand table
    body = [f"![The PLA leg on the boom stand](../exports/motor-day/steps/step-{len(steps):02d}.png)", '',
            f"The boom is two 2x4 rails, {stand['pivot_to_hip_mm'] / 1000:.2f} m from the pivot to the hip. Its parts and "
            f"dimensions are on drawing MD-05 below. What it gives up:", ''] + giv + ['',
            f"**Weight, not ballast.** The simulation carries one mass, {der['sim']['mass_kg']:.1f} kg, for both the weight "
            f"the leg holds and the inertia it accelerates. The stand already weighs about **{stand['scale_reads_kg']:.1f} kg** "
            f"at the foot (a scale under it, the boom resting on it) while its inertia there is about "
            f"{stand['effective_mass_kg']:.1f} kg ({stand['moving_kg']:.1f} kg moving, lumber at estimated densities). Ballast on "
            f"the plate would add to both, so add none. Weigh it with the motors unpowered: the reading is `--half-mass` in the "
            f"ladder. The derating scales the simulated forces by the larger mass; **above {der['mass'].get('max_stand_kg', 0):.1f} kg "
            f"the PLA cap no longer holds**: lighten the boom (a thinner end plate, shorter rails) before running."]
    doc = _fill(doc, 'stand', '\n'.join(body))
    # ---- prints
    ph = {'0': 'Phase 0', '1a': 'Coupons', '1b': 'Leg and stand'}
    tot = {'pla_g': 0, 'tpu_g': 0, 'min': 0}
    by_phase = {p: 0 for p in ph}
    L = ['Sliced in Bambu Studio for a P1S, 0.4 mm nozzle, 0.20 mm layers, Bambu PLA Basic (TPU 95A HF for the sleeves). '
         '"Solid" is what the FEA assumes: 4 walls and 100 % infill. Times are the slicer\'s estimates. **Print them in '
         'this order**, top to bottom; "Item" is the BOM number the drawings and assembly steps use.', '',
         '| Print | Part | Qty | Item | File | Settings | Time | Filament | Bed face, what to watch |',
         '|---|---|---|---|---|---|---|---|---|']
    c1 = {'min': 0, 'g': 0, 'n': 0}
    queue = ctx['queue']
    for r in queue:
        key, qty, recipe, phase, f = r['key'], r['qty'], r['recipe'], r['phase'], r['file']
        s = slices.get(key) or {}
        mins, g = (s.get('minutes') or 0) * qty, (s.get('grams') or 0) * qty
        tot['min'] += mins
        by_phase[phase] += mins
        tot['tpu_g' if recipe == 'tpu' else 'pla_g'] += g
        if key in C1:
            c1['min'] += mins
            c1['g'] += g
            c1['n'] += qty
            if c1['n'] == 1:
                L.append(f"| **{r['order']}** | **C1 bore coupons** ({ph[phase]}) | C1N | | "
                         '`exports/rig/bench/coupon_*_m01/nom/p01.stl` | solid | C1MIN | C1G | the leg\'s press-fit bores at '
                         '-0.1 / 0 / +0.1 mm: print them as one batch and pick the offset that fits '
                         '([sheets](../research/leg-preprint/sheets/)). If a coupon other than `nom` fits, change the CAD '
                         'before print 4: `PRINT_HOLE_COMP` for the sleeve holes (the RS-04 dowel holes are drilled out: Phase 0.3); `KC`, `AC` and `STOP_HOLE_PLAY` '
                         'for the bearing seats and stop-pin holes (`cad/fivebar.py`; the [print package](leg-print-package.md) '
                         'C1 row). Then regenerate the leg\'s files (`cad/build_leg.py`, then `tools/motor_day.py --slice` '
                         'for the times and grams) |')
            continue
        name = key.replace('_', ' ').replace(' pla', ' (PLA)')
        L.append(f"| **{r['order']}** | **{name}** ({ph[phase]}) | {qty} | {items.get(key, '')} | [{Path(f).name}](../{f}) | "
                 f"{recipe} | {_h(mins)} | {g:.0f} g{' TPU' if recipe == 'tpu' else ''} | {r['how']} |")
    doc_t = '\n'.join(L).replace('C1N', str(c1['n'])).replace('C1MIN', _h(c1['min'])).replace('C1G', f"{c1['g']:.0f} g")
    first = next(r for r in queue if r['key'] == 'hip_frame')['order']
    before = sum(((slices.get(r['key']) or {}).get('minutes') or 0) * r['qty'] for r in queue if r['order'] < first)
    hip = (slices.get('hip_frame') or {}).get('minutes') or 0
    doc_t += (f"\n\n**Total:** {_h(tot['min'])} of printing, {tot['pla_g'] / 1000:.2f} kg of PLA and {tot['tpu_g']:.0f} g of TPU: "
              f"the two Phase 0 fit checks {_h(by_phase['0'])}, the coupons {_h(by_phase['1a'])}, the leg and stand "
              f"{_h(by_phase['1b'])}. Every file, with these settings and this order in `prints.csv`, is in the bundle.\n\n"
              '**On one printer, print in the order above.** Prints 1 and 2 are the two fit checks (Phase 0.3 and 0.4). '
              'Fit each to a motor as it comes off the bed. The coupon is cut from the hip frame round one motor, and the '
              f"first adapter is the same file as the second. So a misfit shows up before the hip frame ({_h(hip)}) and the "
              "second adapter are printed. Print 3, the coupons, shows how the leg's bores come out in PLA. "
              f"Start the hip frame {_h(before)} in, once both fits have passed and the coupon offsets are picked. It is the "
              'longest print, and the motors go on it first. The drill template is last only because the leg does not need '
              'it. Print it sooner if you want to build the boom (assembly steps 1 and 2) while the leg prints.\n\n'
              '**PLA limits on the bench.** PLA softens at about 55 °C and the RS-04s bolt straight to the hip frame: '
              'feel the motor cases, and stop above 40 °C. PLA creeps under a clamp: re-torque the M5s before each session.')
    doc = _fill(doc, 'prints', doc_t)
    # ---- orders
    tot_mc = sum(m['cost_usd'] or 0 for m in mc)
    L = [f"### McMaster-Carr ({len(mc)} lines, {_money(tot_mc)} in packs)", '',
         'Part numbers from `catalog/hardware.json` (picked and read with the mcmaster-parts tooling). Prices as read on the '
         'date given; McMaster sells most screws in packs, so the cost is the packs\'. Already have it? The last column '
         'says what will do.', '',
         '| Item | McMaster | Part | Qty | Packs | Cost | Already have? |', '|---|---|---|---|---|---|---|']
    for m in mc:
        pn = f"[{m['mcmaster']}]({m['url']})" if m['mcmaster'] else '**to confirm**'
        L.append(f"| {items.get(m['key'], '')} | {pn} | {m['name']} | {m['qty']} | {m['packs']} x {m['pack_qty']} | "
                 f"{_money(m['cost_usd'])} | {m['substitute']} |")
    L += ['', '### Other vendors', '', '| Group | Item | Qty | Vendor | Each | When | Note |', '|---|---|---|---|---|---|---|']
    for o in other:
        it = f"[{o['item']}]({o['url']})" if o.get('url') else o['item']
        L.append(f"| {o['group']} | {it} | {o['qty']} | {o['vendor']} | {_money(o['price_usd_each'])} | {o['when']} | {o['note']} |")
    doc = _fill(doc, 'orders', '\n'.join(L))
    # ---- assembly
    L = ['Each step\'s new parts in colour, lifted along the way they go in; the numbers are the BOM items '
         '(`bom.csv`). Torques for PLA are lower than the PA6-CF leg\'s.', '']
    for r in steps:
        L += [f"#### {r['step']}. {r['title']}", '', f"![step {r['step']}](../{r['picture']})", '', r['how'], '']
    L += ['### Drawings', '', 'Generated from the same CAD with hidden-line views, balloons keyed to the BOM items and the '
          'parts list on each sheet. All five are in [motor-day-drawings.pdf](../exports/motor-day/drawings/motor-day-drawings.pdf).', '']
    for sh in sheets:
        L += [f"**{sh['number']} {sh['title']}**", '', f"![{sh['number']}](../{sh['png']})", '']
    doc = _fill(doc, 'assembly', '\n'.join(L))
    # ---- derating
    caps = sorted(der['caps'], key=float)
    ms = der['mass']
    L = [f"Every day-one run lands, so the landings are held to the everyday target ({LANDING_TARGET:g}), not the rare-event "
         f"1.2 the robot's record uses. A power cut is a fault: target {FAULT_TARGET:g}. How the numbers are made:", '',
         f"- **Material:** cad-agent's PLA row ({der['pla']['strength_mpa']} MPa, \"{der['pla']['note']}\") against each "
         'row\'s humid PA6-CF strength (40.8 MPa in the layers, 18.1 across) or 6061 for the adapter. The FEA is linear, so '
         'a row\'s factor scales with the strength.',
         f"- **Loads:** the rig's controller and MuJoCo model at each cap, at {ms['sim_kg']:.1f} kg "
         f"(`tools/motor_day_sim.py`), against the loads the record's cases were run at (knee {der['record']['loads']['knee_dyn_n']:.0f} N "
         f"and hip {der['record']['loads']['hip_dyn_n']:.0f} N in a landing, axle {der['record']['loads']['axle_full_n']:.0f} N on the "
         "wheel link, the motors' 60 and 120 N m). A landing case takes its worst joint; a power cut also its backdriven hub torque.",
         f"- **Mass:** the simulation has one mass; the stand weighs about {ms['stand_scale_kg']:.1f} kg at the foot and its inertia "
         f"is about {ms['stand_effective_kg']:.1f} kg there. The simulated forces are scaled by the larger over the simulated mass "
         f"(x {ms['load_factor']:.2f}).",
         '- **Not in it:** PLA is brittle (it cracks without warning, where PA6-CF whitens first), creeps, and softens at '
         '55 °C. No margin is added for these: the ladder adds them by stepping up slowly and inspecting after each rung.', '',
         '| Cap at the motors | Jump (sim) | Axle peak | Knee peak | Hub peak | Weakest row | All rows at target |',
         '|---|---|---|---|---|---|---|']
    for c in caps:
        x = der['caps'][c]
        L.append(f"| {float(c):.0f} N m | {x['jump_mm']:.0f} mm | {x['axle_n']:.0f} N | {x['knee_n']:.0f} N | {x['hub_nm']:.0f} N m | "
                 f"{x['worst']} | {'yes' if x['all_ok'] else '**no**'} |")
    L += ['', f"**The PLA cap is {cap:.0f} N m**" if cap else '**No simulated cap keeps every row at target.**']
    if cap:
        x = der['caps'][str(cap)]
        L[-1] += f": a {x['jump_mm']:.0f} mm hop in the model (expect less: the stand's weight at the foot is more than its inertia there)."
        nxt = [c for c in caps if float(c) > cap]
        if nxt:
            y = der['caps'][nxt[0]]
            bad = min((r for r in y['rows'] if not r['ok']), key=lambda r: r['sf'] / r['target'])
            L[-1] += (f" At {float(nxt[0]):.0f} N m {bad['part']} {bad['case']} falls to {bad['sf']}, under its target of "
                      f"{bad['target']:g}.")
        if ms.get('max_stand_kg'):
            L[-1] += f" The cap holds for a stand up to **{ms['max_stand_kg']:.1f} kg** at the foot (the landings scale with it)."
        rows = sorted((r for r in x['rows'] if r['sf'] is not None), key=lambda r: r['sf'] / r['target'])
        L += ['', f'Where PLA fails first, at {cap:.0f} N m (the weakest rows):', '',
              '| Part | Case | PLA factor | Target | Governed by | Load |', '|---|---|---|---|---|---|']
        for r in rows[:5]:
            L.append(f"| {r['part']} | {r['case']} | {r['sf']} | {r['target']:g} | {r['governed_by']} | {r['load']} |")
    pc = der['power_cut']
    names = {'power_off': 'undamped (the worst case)', 'power_off_damped': 'with the RS-04\'s power-off damping (assumed: B1 measures it)'}
    L += ['', f"**A power cut onto the floor stop** (the pendant let go, on purpose or not, at the {der['stand_cap_nm']:.0f} N m stand):", '',
          '| Motors | Knee | Hip | Hub | Axle | Weakest rows | All rows at 1 |', '|---|---|---|---|---|---|---|']
    for t, x in pc.items():
        w = sorted((r for r in x['rows'] if r['sf'] is not None), key=lambda r: r['sf'] / r['target'])[:2]
        L.append(f"| {names.get(t, t)} | {x['knee_n']:.0f} N | {x['hip_n']:.0f} N | {x['hub_nm']:.0f} N m | {x['axle_n']:.0f} N | "
                 + '; '.join(f"{r['part']} {r['case']} {r['sf']} ({r['load'].split(': ', 1)[-1]})" for r in w)
                 + f" | {'yes' if x['all_ok'] else '**no**'} |")
    hc = der['hub_clamp']
    hop = der['caps'][str(cap)]['hub_nm'] if cap else None
    cut_hub = max((x['hub_nm'] for x in pc.values()), default=None)
    L += ['', f"The hub clamp in the PLA adapter: {hc['preload_n']} N a screw at {hc['torque_nm']} N m gives about "
          f"{hc['friction_nm']} N m of friction. The hub sees about {hop:.0f} N m in the hop" + (
              f" and up to {cut_hub:.0f} N m in a power cut" if cut_hub else '') + ': above the friction the two dowels carry it. '
          f"{hc['note'].split(': ')[-1].split('; ')[-1][:1].upper()}{hc['note'].split(': ')[-1].split('; ')[-1][1:]}",
          '', 'Full table: [derating.json](../exports/motor-day/derating.json).']
    doc = _fill(doc, 'derating', '\n'.join(L))
    # ---- the ladder
    sc = der['stand_cap_nm']
    hm = '--damper 0 --half-mass KG'
    gb = {t: x['peak_motor_nm'] for t, x in der['stand_runs'].items()}
    lad = [
        ('L0', 'Unpowered', '-', 'Fold and stretch the leg by hand from stop to stop; the boom swings freely; the foot lands '
         'on the mat at the stance with the boom level.', 'no rub; no part touches another'),
        ('L1', 'Commission each motor', '2 A bench limit', 'Phase 0.5 (C1-C5) on all four motors, then C6: ids 1 front, 2 rear on this leg. '
         'C4 saves the rig\'s 60 N m; then `python -m rig.rs04 --id N param limit_torque 10` and `--id N save`, so a motor '
         'powers up at 10.', 'the motor reads back 10 after a power cycle'),
        ('L2', 'Zero on the bare stops', '10 N m', 'The boom propped on the floor stop, the foot in the air. '
         '`python -m rig.calibrate`, one link at a time onto its stop pins by hand.', 'the 142 deg between the posts; no creak at the stop pins'),
        ('L3', 'In-air sweeps', '10 N m', f'`python -m rig.run --backend can --test squat --cap 10 {hm} --rate-limit 5` '
         'with the foot in the air (boom propped).', 'smooth; the knees and the adapters do not click; motor cases under 40 °C'),
        ('L4', 'Stand up', f'{sc:.0f} N m', f'`--test stand_up --cap {sc:.0f} {hm}`, the foot on the mat.',
         f"holds 300 mm; peak motor torque about {gb['stand_up']:.0f} N m (sim)"),
        ('L5', 'Squat x 3', f'{sc:.0f} N m', f'`--test squat --cap {sc:.0f} {hm}`.', 're-check every screw\'s paint mark after'),
    ]
    und, dmp = pc.get('power_off', {}), pc.get('power_off_damped', {})
    if und.get('all_ok'):
        lad.append(('L6', 'Power cut onto the floor stop', f'{sc:.0f} N m', f'`--test power_off --cap {sc:.0f} {hm}`: let go of the pendant.',
                    'the boom lands on the floor stop, not the leg on its own stops'))
    elif dmp.get('all_ok'):
        lad.append(('L6', 'Damped power cut (skip until B1)', f'{sc:.0f} N m',
                    f'Only once B1 has measured the RS-04\'s power-off damping at or above the model\'s: '
                    f'`--test power_off_damped --cap {sc:.0f} {hm}`, let go of the pendant.',
                    'the boom lands on the floor stop, not the leg on its own stops'))
    jc = [c for c in caps if (not cap) or float(c) <= cap]
    for k, c in enumerate(jc):
        x = der['caps'][c]
        lad.append((f'L{len(lad)}', 'Hop' if k == 0 else 'Higher hop', f'{float(c):.0f} N m', f"`--test jump --cap {float(c):.0f} {hm}`.",
                    f"a hop of up to about {x['jump_mm']:.0f} mm; inspect the weakest rows' corners (above) with a lamp"))
    L = ['Each rung runs only after the one before it passed and the leg was inspected. In every `rig.run` command:', '',
         '- `--cap` is the cap in both places: `rig.run` writes it to both motors\' `limit_torque` at start-up, reads it back '
         '(it stops if a motor does not take it) and clips its own commands to it. **Without `--cap` the rig runs at 60 N m: '
         'never on the PLA leg.**',
         '- `--damper 0` keeps the RS-04\'s power-off anti-backdrive protection on (the factory default), so a power cut is '
         'damped.',
         f"- `--half-mass KG`: KG is the scale's reading under the foot from assembly step 7 (about {ms['stand_scale_kg']:.1f}). "
         'It sets the gravity feed-forward.', '',
         'The safety rules of [leg-rig-safety.md](leg-rig-safety.md) apply unchanged (one operator, the pendant, the clear '
         'zone, eye protection).', '',
         '```mermaid', 'flowchart LR'] + [f'  {a}["{a}<br/>{b}<br/>{c}"]' + (f' --> {lad[i + 1][0]}' if i + 1 < len(lad) else '')
                                         for i, (a, b, c, _, _) in enumerate(lad)] + ['```', '',
         '| Rung | What | Cap | How | Pass when |', '|---|---|---|---|---|']
    for a, b, c, d, e in lad:
        L.append(f'| {a} | {b} | {c} | {d} | {e} |')
    if not und.get('all_ok'):
        w = min((r for r in und['rows'] if r['sf'] is not None), key=lambda r: r['sf'] / r['target'])
        L += ['', f"**No deliberate undamped power cut on PLA.** Undamped, {w['part']} {w['case']} comes to {w['sf']} against "
              f"{w['target']:g} ({w['load']}). " + (
                  'With the modelled damping every row holds, so the damped cut waits for B1 to measure it. '
                  if dmp.get('all_ok') else 'Even with the modelled damping a row falls short, so no power cut is on the ladder. ')
              + 'A pendant let go by accident is the same event, damped by the protection `--damper 0` keeps on, but by how '
              'much only B1 says (it needs the dyno, an archived fixture: [bench tests](leg-bench-tests.md#b1-the-power-off-'
              f"damping-decides-d39)). **Until then the accidental cut is the residual risk**: at worst {w['part'].replace('_', ' ')} "
              f"at a factor of {w['sf']} (under 1: it may break). Keep spare printed "
              + _and(sorted({r['part'].replace('_', ' ') + 's' for r in und['rows'] if r['sf'] is not None and r['sf'] < 1.2 * r['target']}))
              + ' on hand, keep the clear zone, set the floor stop before every session, and inspect the parts above after any cut.']
    L += ['', '**Stop the ladder** at any crack, whitening, click or creak, a screw\'s paint mark broken, a motor case over '
          '40 °C, or a fault. Photograph it, write it on #156. **Look first** at: the wheel link\'s hub root (where the hub '
          'leaves the link, inside the apex), the front link\'s apex ring, the upper links\' knee-eye stubs, the PLA adapters '
          'round their dowels and screws, and the foot\'s spokes.', '',
          f"Above {cap:.0f} N m the leg needs the machined adapters and PA6-CF (the [print package](leg-print-package.md))."
          if cap else '']
    doc = _fill(doc, 'ladder', '\n'.join(L))
    DOC.write_text(doc)


# ------------------------------------------------------------------------------------------------- CSV and the bundle

def write_csv(path: Path, rows: list, cols: list):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow(r)


def bundle(files: list):
    z = OUT / 'motor-day-package.zip'
    readme = ('Gyropup motor day: the first leg in PLA on a boom stand.\n'
              'Read docs/motor-day.md (https://gyropup.com) first. Not a release: nothing here has been printed, bought or '
              'run.\nbom.csv: every line with its item number (the balloons on the drawings). prints.csv: each print with '
              'its slicer settings (the 3MF and STL files carry geometry only). mcmaster.csv and other-vendors.csv: the '
              'orders. drawings/: MD-01..05 as PNG and one PDF. steps/: the exploded assembly steps.\n'
              'Generated by tools/motor_day.py.\n')
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        zi = zipfile.ZipInfo('motor-day/README.txt', date_time=(2026, 11, 2, 0, 0, 0))
        zf.writestr(zi, readme)
        for src, arc in files:
            zi = zipfile.ZipInfo(f'motor-day/{arc}', date_time=(2026, 11, 2, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(zi, src if isinstance(src, bytes) else (R / src).read_bytes())
    return z


SITE = 'https://gyropup.com'
REPO = 'https://github.com/Valpatel/gyropup/blob/main'


def zip_markdown(text: str, files: list) -> str:
    """docs/motor-day.md for the bundle: a link to a file in the bundle points inside it, a link to another page goes to
    the site (docs/<name>.md -> its page), anything else to the repository on GitHub."""
    import re
    inside = {('../' + src) if not src.startswith('docs/') else src[len('docs/'):]: arc for src, arc in files
              if isinstance(src, str)}

    def fix(m):
        url = m.group(1)
        if re.match(r'^[a-z]+:', url) or url.startswith('#'):
            return m.group(0)
        path, _, frag = url.partition('#')
        if path in inside:
            new = inside[path]
        elif path.endswith('.md') and '/' not in path:
            new = f"{SITE}/site/pages/docs-{path[:-3]}-md.html"
        else:
            new = f"{REPO}/{(Path('docs') / path).as_posix().replace('docs/../', '')}"
        return f"]({new}{'#' + frag if frag else ''})"
    return re.sub(r'\]\(([^)\s]+)\)', fix, text)


def _rev() -> str:
    try:
        return subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=R, capture_output=True, text=True).stdout.strip() or 'local'
    except Exception:
        return 'local'


def export_parts(fm):
    d = OUT / 'parts'
    d.mkdir(parents=True, exist_ok=True)
    f, _ = foot()
    fp = foot_print(f, fm)
    t = drill_template()
    ep = end_plate()
    for name, shp in (('foot', fp), ('drill_template', t)):
        cq.exporters.export(shp, str(d / f'{name}.step'))
        cq.exporters.export(shp, str(d / f'{name}.stl'), tolerance=0.05, angularTolerance=0.2)
        try:
            cq.exporters.export(shp, str(d / f'{name}.3mf'), tolerance=0.05, angularTolerance=0.2)
        except Exception:
            pass
    cq.exporters.export(ep, str(d / 'end_plate.step'))
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--slice', action='store_true', help='slice every print with Bambu Studio first (slices.json)')
    ap.add_argument('--no-render', action='store_true', help='skip the step pictures and the drawings')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    f, fm = foot()
    export_parts(fm)
    if a.slice:
        slice_all()
    sim = _load(OUT / 'sim.json')
    if not sim:
        raise SystemExit('exports/motor-day/sim.json is missing: run tools/motor_day_sim.py first')
    slices = (_load(OUT / 'slices.json', {}) or {}).get('parts', {})
    bad = [k for k, s in slices.items() if not s.get('ok')]
    if bad:
        raise SystemExit(f'failed slices: {bad}')
    mc, other_leg = hardware_rows()
    P, meta, fm = scene()
    stand = stand_masses(P, slices, mc, meta, fm)
    der = derate(sim, stand)
    (OUT / 'derating.json').write_text(json.dumps(der, indent=1) + '\n')
    other = other_vendor_rows(other_leg, slices)
    prints = []
    for key, fpath, qty, recipe, phase, how in PRINTS:
        s = slices.get(key) or {}
        prints.append({'key': key, 'file': fpath, 'qty': qty, 'phase': phase, 'recipe': recipe,
                       'settings': '; '.join(f'{k}={v}' for k, v in RECIPES[recipe].items()),
                       'filament': s.get('filament') or ('TPU 95A' if recipe == 'tpu' else 'PLA'),
                       'minutes_each': s.get('minutes'), 'grams_each': s.get('grams'), 'how': how})
    items = item_numbers(prints, mc, other_leg)
    names = {p['key']: (p['key'].replace('_', ' ') + (' (PLA)' if p['recipe'] != 'tpu' else ' (TPU)'), p['qty'], 'print: ' + Path(p['file']).name)
             for p in prints}
    names.update({m['key']: (m['name'], m['qty'], f"McMaster {m['mcmaster'] or '(to confirm)'}") for m in mc})
    names.update({o['key']: (o['name'], o['qty'], o['day_one']) for o in other_leg})
    names.update({k: (v[0], v[1], v[2]) for k, v in STAND_ITEMS.items()})
    names['screw_m5x30'] = (names['screw_m5x30'][0], names['screw_m5x30'][1], names['screw_m5x30'][2])
    if a.no_render:                             # keep the pictures already rendered: only if no item number has moved
        steps, rendered = _load(OUT / 'steps' / 'steps.json', []), _load(OUT / 'drawings' / 'sheets.json', {})
        sheets = rendered.get('sheets') or []
        if not steps or not sheets:
            raise SystemExit('--no-render needs the rendered steps and drawings (steps/steps.json, drawings/sheets.json)')
        if rendered.get('items') != items:
            moved = sorted(k for k in set(items) | set(rendered.get('items') or {}) if items.get(k) != (rendered.get('items') or {}).get(k))
            raise SystemExit(f'the BOM item numbers changed since the steps and drawings were rendered ({moved}): render again')
        if len(steps) != len(STEPS) or rendered.get('step_parts') != [list(st[1]) for st in STEPS]:
            raise SystemExit('the assembly steps or their parts changed since they were rendered: render again')
        for r, (title, *_, how) in zip(steps, STEPS):     # only the words may change without a new picture
            r['title'], r['how'] = title, how
    bom = [{'item': items[k], 'key': k, 'qty': v[1], 'part': v[0], 'source': v[2]} for k, v in names.items() if k in items]
    bom.sort(key=lambda r: r['item'])
    write_csv(OUT / 'bom.csv', bom, ['item', 'key', 'qty', 'part', 'source'])
    by_key = {p['key']: p for p in prints}
    queue = print_queue()
    write_csv(OUT / 'prints.csv', [{**by_key[q['key']], **q, 'item': items.get(q['key'], '')} for q in queue],
              ['order', 'item', 'key', 'qty', 'phase', 'file', 'recipe', 'filament', 'settings', 'minutes_each', 'grams_each', 'how'])
    write_csv(OUT / 'mcmaster.csv', [{**m, 'item': items.get(m['key'])} for m in mc],
              ['item', 'key', 'mcmaster', 'name', 'qty', 'pack_qty', 'packs', 'price_usd_each', 'cost_usd', 'price_checked', 'url',
               'substitute', 'for'])
    write_csv(OUT / 'other-vendors.csv', other, ['group', 'item', 'qty', 'vendor', 'part_number', 'price_usd_each', 'cost_usd',
                                                'when', 'url', 'note'])
    (OUT / 'stand.json').write_text(json.dumps({'geometry': meta, 'foot': fm, 'masses': stand}, indent=1) + '\n')
    if not a.no_render:
        steps = render_steps(P, items)
        sheets = drawings(P, items, names, _rev(), meta, fm)
        (OUT / 'drawings' / 'sheets.json').write_text(json.dumps({'items': items, 'step_parts': [list(st[1]) for st in STEPS],
                                                                  'sheets': sheets}, indent=1) + '\n')
    (OUT / 'steps' / 'steps.json').write_text(json.dumps(steps, indent=1) + '\n')
    write_doc({'slices': slices, 'der': der, 'stand': stand, 'steps': steps, 'sheets': sheets, 'mc': mc, 'other': other,
               'meta': meta, 'items': items, 'queue': queue})
    files = [(f'exports/motor-day/{n}', n) for n in ('bom.csv', 'prints.csv', 'mcmaster.csv', 'other-vendors.csv',
                                                    'derating.json', 'stand.json', 'sim.json', 'slices.json')]
    for key, fpath, *_ in PRINTS:
        files.append((fpath, f'print/{Path(fpath).name}'))
        alt = Path(fpath).with_suffix('.stl' if fpath.endswith('.3mf') else '.3mf')
        if (R / alt).exists():
            files.append((str(alt), f'print/{alt.name}'))
    files.append(('exports/motor-day/parts/end_plate.step', 'stand/end_plate.step'))
    for sh in sheets:
        files.append((sh['png'], f"drawings/{Path(sh['png']).name}"))
    if sheets:
        files.append(('exports/motor-day/drawings/motor-day-drawings.pdf', 'drawings/motor-day-drawings.pdf'))
    for r in steps:
        files.append((r['picture'], f"steps/{Path(r['picture']).name}"))
    files.append((zip_markdown((R / 'docs/motor-day.md').read_text(), files).encode(), 'motor-day.md'))
    z = bundle(files)
    print(f'-> {z.relative_to(R)} ({z.stat().st_size / 1e6:.1f} MB), docs/motor-day.md; PLA cap {der["pla_cap_nm"]} N m')


if __name__ == '__main__':
    main()
