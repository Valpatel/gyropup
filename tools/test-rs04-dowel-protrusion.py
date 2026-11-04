#!/usr/bin/env python3
"""The RS-04 case's two Ø5 locating holes against the steel dowels that stand out of the hip frame into them.

The case has two Ø5 locating holes on its Ø106 lug circle and no pins of its own (owner, 2026-11-03; the vendor STEP has
them 4.5 deep: catalog/interfaces.json). A Ø5 x 16 dowel (catalog/hardware.json dowel_5x16) bonded to the bottom of the
frame's hole stands its length less the hole's depth proud of the seat face. It must stay more than 0.5 mm short of the
case hole's floor, or the case can sit on the dowels and not on its face.

The hole depths are read from the exported STEP files' own B-rep (plain text, no CAD kernel), so this runs anywhere:
    python3 tools/test-rs04-dowel-protrusion.py
"""
from __future__ import annotations

import json
import math
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLEARANCE = 0.5                 # mm the dowel must stay short of the case hole's floor
HOLE_R = (2.45, 2.70)           # mm: the frame's printed Ø5 dowel hole (2.5 + PRINT_HOLE_COMP / 2 + 0.015 = 2.5775 today),
                                # between the M4 clearance (2.25) and an M5 clearance (2.75)
# The parts the motor's case seats on, each with its two dowel holes per motor
SEATS = {'exports/leg/hip_frame.step': 4, 'exports/leg/rs04-mounting-fit/hip_frame.step': 4,
         'exports/rig/bench/coupon_frame_ring_nom.step': 2, 'exports/leg/rs04-mounting-fit/coupon_frame_ring_nom.step': 2}
DRILL_OUT = 13.0                # mm, full diameter: docs/motor-day.md Phase 0.3 has the 12 mm holes drilled to this by hand
PROUD_BAND = (2.5, 3.5)         # mm the page accepts, after the drill-out
DOC = ROOT / 'docs/motor-day.md'


def step_entities(path: Path) -> dict:
    text = path.read_text(errors='replace')
    data = text[text.index('DATA;') + 5:]
    out = {}
    for m in re.finditer(r'#(\d+)\s*=\s*([A-Z0-9_]+)\s*\((.*?)\)\s*;', data, re.S):
        out[int(m.group(1))] = (m.group(2), m.group(3))
    return out


def refs(args: str) -> list:
    return [int(r) for r in re.findall(r'#(\d+)', args)]


def numbers(args: str) -> list:
    return [float(v) for v in re.findall(r'[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?', args.split(',', 1)[1])]


def dowel_holes(path: Path) -> list:
    """Each cylindrical face of the dowel hole's radius: (axis point, axis direction, extent along the axis)."""
    E = step_entities(path)

    def point(i):
        return numbers(E[i][1])[:3]
    holes = []
    for name, args in E.values():
        if name != 'ADVANCED_FACE':
            continue
        r = refs(args)
        bounds, surf = r[:-1], r[-1]
        if surf not in E:                                  # a complex entity, which the regex does not read
            raise AssertionError(f'{path.name}: face surface #{surf} is not a simple entity: extend the parser')
        if E[surf][0] != 'CYLINDRICAL_SURFACE':
            continue
        place, radius = refs(E[surf][1])[0], numbers(E[surf][1])[-1]
        if not HOLE_R[0] <= radius <= HOLE_R[1]:
            continue
        loc_i, dir_i = refs(E[place][1])[:2]
        loc, d = point(loc_i), point(dir_i)
        n = math.sqrt(sum(c * c for c in d))
        d = [c / n for c in d]
        ts = []
        for b in bounds:                                   # FACE_BOUND -> EDGE_LOOP -> ORIENTED_EDGE -> EDGE_CURVE -> VERTEX
            for oe in refs(E[refs(E[b][1])[0]][1]):
                ec = refs(E[oe][1])[-1]
                for v in refs(E[ec][1])[:2]:
                    p = point(refs(E[v][1])[0])
                    ts.append(sum((p[k] - loc[k]) * d[k] for k in range(3)))
        holes.append((loc, d, min(ts), max(ts)))
    # one hole may be split into several faces: merge those on the same axis
    merged = []
    for loc, d, t0, t1 in holes:
        for h in merged:
            off = [loc[k] - h['loc'][k] for k in range(3)]
            along = sum(off[k] * h['d'][k] for k in range(3))
            if math.sqrt(max(0.0, sum(c * c for c in off) - along * along)) < 0.05:
                if sum(d[k] * h['d'][k] for k in range(3)) < 0:            # the same axis, the other way round
                    t0, t1 = -t1, -t0
                h['t0'], h['t1'] = min(h['t0'], t0 + along), max(h['t1'], t1 + along)
                break
        else:
            merged.append({'loc': loc, 'd': d, 't0': t0, 't1': t1})
    return [h['t1'] - h['t0'] for h in merged]


def case_hole_depth() -> float:
    loc = json.loads((ROOT / 'catalog/interfaces.json').read_text())['robstride-rs-04']['case']['locating']
    m = re.search(r'([\d.]+)\s*(?:mm\s*)?deep', loc['note'])
    if not m:
        raise AssertionError(f'no locating-hole depth in catalog/interfaces.json: {loc}')
    return float(m.group(1))


def dowel_length() -> float:
    row = next(r for r in json.loads((ROOT / 'catalog/hardware.json').read_text()) if r['key'] == 'dowel_5x16')
    return float(row['specs']['length_mm'])


class DowelProtrusion(unittest.TestCase):
    def setUp(self):
        self.case, self.dowel = case_hole_depth(), dowel_length()
        self.limit = self.case - CLEARANCE

    def test_holes_found(self):
        for f, n in SEATS.items():
            depths = dowel_holes(ROOT / f)
            self.assertEqual(len(depths), n, f'{f}: {len(depths)} dowel holes of radius {HOLE_R[0]}-{HOLE_R[1]} mm, expected '
                             f'{n}: has the printed hole size moved out of HOLE_R?')

    @unittest.expectedFailure
    def test_cad_holes_leave_clearance(self):
        """Fails today: the CAD's 12 mm holes leave a 16 mm dowel 4.0 proud, 0.5 short of the 4.5 mm case hole: no margin.
        The fix is in the CAD (cad/fivebar.py hip_frame: the dowel hole 13 deep). When it lands, this passes, the
        unexpected success fails the run, and this marker goes."""
        for f in SEATS:
            for depth in dowel_holes(ROOT / f):
                proud = round(self.dowel - depth, 2)            # the export's float noise is not margin
                self.assertLess(proud, self.limit, f'{f}: a {self.dowel:g} mm dowel in a {depth:.2f} mm hole stands '
                                f'{proud:.2f} proud; the case hole is {self.case:g} deep')

    def test_motor_day_build_leaves_clearance(self):
        """The motor-day build drills the holes to DRILL_OUT first (Phase 0.3, assembly step 3)."""
        text = DOC.read_text()
        phase0 = text.split('## Phase 0', 1)[1].split('## Phase 1', 1)[0]
        step3 = text.split('#### 3. ', 1)[1].split('#### 4. ', 1)[0]           # generated from tools/motor_day.py STEPS
        nominal = f'{self.dowel - DRILL_OUT:.1f} mm proud ({PROUD_BAND[0]:g} to {PROUD_BAND[1]:g}'
        for name, sec in (('Phase 0.3', phase0), ('assembly step 3', step3)):
            self.assertTrue(f'to {DRILL_OUT:g} mm deep' in sec, f'{name} no longer drills the dowel holes to {DRILL_OUT:g} mm')
            self.assertTrue(nominal in sec, f'{name} does not ask for "{nominal}"')
        self.assertLess(PROUD_BAND[1], self.limit)
        for f in SEATS:
            for depth in dowel_holes(ROOT / f):
                proud = round(self.dowel - max(depth, DRILL_OUT), 2)
                self.assertLess(proud, self.limit, f'{f}: drilled to {max(depth, DRILL_OUT):.2f}, the dowel stands {proud:.2f}')
                self.assertGreater(proud, 2.0, f'{f}: only {proud:.2f} of the dowel in the case hole')


if __name__ == '__main__':
    unittest.main(verbosity=2)
