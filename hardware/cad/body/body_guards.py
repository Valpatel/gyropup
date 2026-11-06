"""The legs' pinch points as the body's hazard table sees them (B6; docs/body-safety.md rows 3-4): what a guard must do
at the knee scissor and the lower-link V, measured from cad/fivebar.py over the leg's whole range (read only).

    .venv/bin/python cad/body_guards.py      # -> exports/body/shell/guards.json

ISO 13854: a gap that closes is safe for fingers at >= 25 mm; ISO 13857: an opening <= 4 mm admits none. For a V of
angle theta closing at its vertex, the opening at a distance r from the vertex is 2 r sin(theta / 2): a guard that
fills the V out to r25 = 25 / (2 sin(theta_min / 2)) keeps the rest of the V >= 25 mm, and the V is finger-proof up to
r4 = 4 / (2 sin(theta_max / 2)) from the vertex at every stance.

What this finds (2026-10-27, main's leg, inside the stops): the knees close no tighter than 24.9 deg (at a 106.5 mm
leg), so a TPU 95A knee wedge 58 mm long on the upper link's inner edge keeps the rest of the scissor >= 25 mm; the
lower-link V at the apex closes to 29.1 deg at full height, so an apex fillet 50 mm long on the wheel link does the
same. Both ride on the leg's links: their envelopes are drawn here (module frame, the reference stance) for the leg
workstream to fit to its links when its stop redesign merges (leg/stops gives the upper links stop faces: D53); the
stops' fairings wait for that merge (docs/body-next-plan.md 5.1 item 6). People-near mode stays the first measure.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import body_params as bp  # noqa: E402

OUT = R / 'exports' / 'body' / 'shell'
SAFE, NO_FINGER = 25.0, 4.0


def _angle(a, b, c):
    v1, v2 = (a[0] - b[0], a[1] - b[1]), (c[0] - b[0], c[1] - b[1])
    return math.degrees(math.acos(max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (math.hypot(*v1) * math.hypot(*v2))))))


def sweep(step=5.0):
    """The knee and apex angles at every reachable stance (leg length, lean) inside the stops."""
    fb = bp._fivebar()
    fo, fi, ro, ri = fb.stop_angles()
    A, B = (fb.P['D'] / 2, 0.0), (-fb.P['D'] / 2, 0.0)
    rows = []
    h = bp.LEG_RANGE[0]
    while h <= bp.LEG_RANGE[1] + 1e-9:
        for lean in (-20.0, -10.0, 0.0, 10.0, 20.0):
            phi = fb.stance(h, lean)
            if phi is None or not (fi - 1e-6 <= phi[0] <= fo + 1e-6 and ro - 1e-6 <= phi[1] <= ri + 1e-6):
                continue
            j = fb.fk(*phi)
            rows.append({'h': round(h, 1), 'lean': lean, 'knee_front': _angle(A, j['C'], j['E']), 'knee_rear': _angle(B, j['D'], j['E']),
                         'apex': _angle(j['C'], j['E'], j['D'])})
        h += step
    return rows


def requirements():
    fb = bp._fivebar()
    rows = sweep()
    out = {}
    for key, link in (('knee_front', fb.P['l1']), ('knee_rear', fb.P['l1']), ('apex', fb.P['l2'])):
        lo = min(rows, key=lambda r: r[key])
        hi = max(rows, key=lambda r: r[key])
        r25 = SAFE / (2 * math.sin(math.radians(lo[key]) / 2))
        r4 = NO_FINGER / (2 * math.sin(math.radians(hi[key]) / 2))
        out[key] = {'min_deg': round(lo[key], 1), 'at_min': [lo['h'], lo['lean']], 'max_deg': round(hi[key], 1),
                    'guard_length_for_25_mm': round(r25, 1), 'link_mm': link, 'finger_proof_within_mm': round(r4, 1),
                    'a_body_guard_can': r25 < 0.6 * link}
    return {'stances': len(rows), 'rule': 'ISO 13854 25 mm (fingers), ISO 13857 4 mm', 'requirements': out,
            'knee': f"a TPU 95A wedge on each upper link's inner edge at the knee, {out['knee_front']['guard_length_for_25_mm']:.0f} mm long "
                    '(its envelope below; fitted to the link by the leg workstream after leg/stops merges)',
            'apex': f"a TPU 95A fillet on the wheel link at the axle, {out['apex']['guard_length_for_25_mm']:.0f} mm long (its envelope below)",
            'stop_fairings': 'blocked on leg/stops (the posts move: D53)'}


def apex_fillet(length=None):
    """The apex fillet's envelope in the leg's module frame at the reference stance (300 mm): a TPU wedge filling the
    lower-link V from the axle out to the guard length, the wheel link's layer (it rides on the wheel link)."""
    import cadquery as cq
    fb = bp._fivebar()
    req = requirements()['requirements']['apex']
    L = length or req['guard_length_for_25_mm']
    j = fb.fk(*fb.stance(300.0))
    E, C, D = j['E'], j['C'], j['D']
    u1 = ((C[0] - E[0]) / math.dist(C, E), (C[1] - E[1]) / math.dist(C, E))
    u2 = ((D[0] - E[0]) / math.dist(D, E), (D[1] - E[1]) / math.dist(D, E))
    pts = [(E[0], E[1]), (E[0] + L * u1[0], E[1] + L * u1[1]), (E[0] + L * u2[0], E[1] + L * u2[1])]
    y0, y1 = fb.Y['wheel_link']
    return cq.Workplane('XZ', origin=(0, y1, 0)).polyline(pts).close().extrude(y1 - y0)


def knee_wedge(front=True, length=None):
    """The knee wedge's envelope (module frame, the reference stance): it fills the scissor between the upper link and
    its lower link from the knee out to the guard length, on the upper link's layer."""
    import cadquery as cq
    fb = bp._fivebar()
    L = length or requirements()['requirements']['knee_front']['guard_length_for_25_mm']
    j = fb.fk(*fb.stance(300.0))
    K, M, E = (j['C'], (fb.P['D'] / 2, 0.0), j['E']) if front else (j['D'], (-fb.P['D'] / 2, 0.0), j['E'])
    u1 = ((M[0] - K[0]) / math.dist(M, K), (M[1] - K[1]) / math.dist(M, K))
    u2 = ((E[0] - K[0]) / math.dist(E, K), (E[1] - K[1]) / math.dist(E, K))
    pts = [K, (K[0] + L * u1[0], K[1] + L * u1[1]), (K[0] + L * u2[0], K[1] + L * u2[1])]
    y0, y1 = fb.Y['upper']
    return cq.Workplane('XZ', origin=(0, y1, 0)).polyline(pts).close().extrude(y1 - y0)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    r = requirements()
    (OUT / 'guards.json').write_text(json.dumps(r, indent=1) + '\n')
    import cadquery as cq
    for name, sh in (('knee_wedge_front', knee_wedge(True)), ('knee_wedge_rear', knee_wedge(False)), ('apex_fillet', apex_fillet())):
        cq.exporters.export(sh.val(), str(OUT / f'{name}_envelope.step'))
    for k, v in r['requirements'].items():
        print(f"{k:11} closes to {v['min_deg']} deg at {v['at_min']}: a guard {v['guard_length_for_25_mm']} mm long keeps 25 mm "
              f"(link {v['link_mm']}; a body guard can: {v['a_body_guard_can']})")


if __name__ == '__main__':
    main()
