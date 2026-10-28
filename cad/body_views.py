"""Section and exploded views of the body (milestone M5; the user's review of the design by sections), headless.

    .venv/bin/python cad/body_views.py        # -> exports/body/views/*.png (heavy: run it on a GB10 with gp-remote)

Solid views are cad/build_body.py's (body-p1-*, body-p3-*). These add:
  section-side-y0      the P3 robot cut at y = 0, seen from the left: the spine's gap, the tray's stack, the bay's packs
  section-front-fan    cut at x = -60 (the J501 fan's axis), seen from the front: cooler, duct, turret plate, riser
  section-front-plate  cut at x = 80, seen from the front: the power plate, its VESCs and converter, the bay
  section-top-tray     cut at z = 150, seen from above: what stands on the tray
  exploded             the P3 parts pulled apart by section (shell out, head up, power up, bay down, packs out)
  exploded-bay         the battery bay alone, the packs sliding out of their doors
"""
from __future__ import annotations

import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import body_frame as bf  # noqa: E402

OUT = R / 'exports' / 'body' / 'views'
BIG = 2000.0


def _v(s):
    return s.val() if hasattr(s, 'val') else s


def _keep(shape, x=None, y=None, z=None):
    """The part of a shape on the kept side of a plane: x=(value, sign) keeps sign*(X - value) >= 0."""
    lo, hi = [-BIG] * 3, [BIG] * 3
    for i, c in enumerate((x, y, z)):
        if c is None:
            continue
        v, sg = c
        if sg > 0:
            lo[i] = v
        else:
            hi[i] = v
    try:
        out = _v(shape).intersect(_v(bf.box(lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])))
        return out if out.Volume() > 1e-3 else None
    except Exception:
        return None


GROUP_OFFSET = [                                  # (name prefixes, (dx, dy, dz)) for the exploded view, first match wins
    (('item.battery_front',), (260.0, 0.0, -260.0)), (('item.battery_rear',), (-260.0, 0.0, -260.0)),
    (('bay_door_front',), (120.0, 0.0, -200.0)), (('bay_door_rear',), (-120.0, 0.0, -200.0)),
    (('bay_', 'item.battery_adapter', 'adapter_plate'), (0.0, 0.0, -180.0)),
    (('belly_plate',), (0.0, 0.0, -90.0)),
    (('shell_side_l', 'ear_bracket_l', 'ear_pod_l'), (0.0, 170.0, 0.0)), (('shell_side_r', 'ear_bracket_r', 'ear_pod_r'), (0.0, -170.0, 0.0)),
    (('shell_door',), (0.0, 230.0, 0.0)), (('shell_hatch',), (0.0, 230.0, 0.0)),
    (('shell_front', 'd435_cradle_front', 'item.d435_front', 'd435_front', 'eyes_'), (200.0, 0.0, 0.0)),
    (('shell_rear', 'd435_cradle_rear', 'd435_rear'), (-200.0, 0.0, 0.0)),
    (('item.turret',), (0.0, 0.0, 420.0)), (('riser',), (0.0, 0.0, 330.0)), (('item.vlp16',), (0.0, 0.0, 330.0)),
    (('deck', 'item.lidar_'), (0.0, 0.0, 260.0)), (('turret_plate', 'fan_duct'), (0.0, 0.0, 200.0)), (('post_',), (0.0, 0.0, 120.0)),
    (('power_plate', 'plate_post', 'bus_', 'dcdc_bracket', 'item.plate_', 'item.power_dcdc'), (0.0, 0.0, 130.0)),
    (('compute_pallet', 'isolator_', 'item.j501', 'item.agx'), (0.0, 0.0, 60.0)),
]


def offset(n):
    for pre, d in GROUP_OFFSET:
        if n.startswith(pre):
            return d
    return (0.0, 0.0, 0.0)


def main():
    from cadagent.render import Renderer
    import build_body as bb
    OUT.mkdir(parents=True, exist_ok=True)
    L = bb._layout()
    parts = {n: p for n, p in bf.all_parts(L['mounts']).items() if p.shape is not None and bf.on_robot(p, 'P3')}
    shapes = {n: (_v(p.shape), p.colour if p.colour else bb.colour(n)) for n, p in parts.items()}
    for it in L['items']:
        shapes[f'item.{it["name"]}'] = (_v(it['shape']), it.get('rgb', (0.5, 0.55, 0.6)))
    legs = {n: (_v(s), bb.colour(n)) for n, s in bf.legs(300.0).items()}
    r = Renderer(OUT, subtitle='GYROPUP BODY | D65 (two DCB609), P3')
    made = []
    cuts = [('section-side-y0', dict(y=(0.0, 1)), (0.0, -1.0, 0.04), 'cut at y = 0, from the left: the spine, the tray\'s stack, the bay\'s two packs'),
            ('section-front-fan', dict(x=(-60.0, -1)), (1.0, 0.0, 0.05), 'cut at x = -60 (the J501 fan), from the front: cooler, duct, turret plate, riser'),
            ('section-front-plate', dict(x=(80.0, -1)), (1.0, 0.0, 0.05), 'cut at x = 80, from the front: the power plate, VESCs, converter, the bay'),
            ('section-top-tray', dict(z=(150.0, -1)), (0.0, 0.0, 1.0), 'cut at z = 150, from above: what stands on the tray')]
    for name, cut, view, cap in cuts:
        sh = []
        for n, (s, c) in list(shapes.items()) + list(legs.items()):
            k = _keep(s, **cut)
            if k is not None:
                sh.append((k, c))
        r.render(f'{name}.png', shapes=sh, view=view, caption=cap)
        made.append(f'{name}.png')
    ex = []
    for n, (s, c) in shapes.items():
        dx, dy, dz = offset(n)
        ex.append((s.translate((dx, dy, dz)) if (dx, dy, dz) != (0, 0, 0) else s, c))
    r.render('exploded.png', shapes=ex, view=(1.0, -1.1, 0.75), caption='exploded by section: shell out, head up, power up, bay down, packs out')
    made.append('exploded.png')
    bay = [(s.translate((offset(n)[0] * 0.8, 0.0, 0.0)) if n.startswith(('item.battery_front', 'item.battery_rear', 'bay_door')) else s, c)
           for n, (s, c) in shapes.items() if n.startswith(('bay_', 'adapter_plate', 'item.battery', 'belly_plate'))]
    r.render('exploded-bay.png', shapes=bay, view=(1.0, -1.2, 0.5), caption='the battery bay: the packs slide out of their doors on their adapters\' rails')
    made.append('exploded-bay.png')
    print('\n'.join(str(OUT / m) for m in made))


if __name__ == '__main__':
    main()
