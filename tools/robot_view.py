"""The whole robot as it is drawn today, for the 3D view and the README's pictures: the P3 body (cad/build_body.py's
frame, shell and layout items), both five-bar legs at the 300 mm stance (cad/body_frame.legs, the RS-04s as envelopes)
and the turret (cad/turret.py) on its riser, placed as sim/robot_v2.py places it.

    .venv/bin/python tools/robot_view.py          # exports/robot/*.step + robot.json, cad/assembly.png, cad/exploded.png
    .venv/bin/python tools/robot_view.py --no-render

`cad-agent view` reads exports/robot/*.step (cad-agent.yaml, cad.view), and so does the cad-agent site's Gyropup model.
Parts are merged into about forty groups (a STEP each) so the web model stays light: fasteners, bearings and pins go in
one hardware group per leg. Bought parts are envelopes (the vendors' STEP files are not redistributed). This replaces
the serial-leg assembly that cad/build.py exported as exports/asm_*.step (rev 0.1, historical). It lives in tools/, not
cad/: it draws nothing new, and receipts pin cad/'s sources (tools/test-rs04-lug-stacks.py and the carrier checks).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cadquery as cq

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
sys.path.insert(0, str(R))
import body_frame as bf  # noqa: E402

OUT = R / 'exports' / 'robot'
PICTURES = R / 'cad'
STANCE_MM = 300.0

# group: (colour, name prefixes it takes, first match wins). Body parts are matched by their cad/body_*.py names, the
# layout's items as 'item.<name>'.
BODY_GROUPS = [
    ('shell', '#cdd1db', ('shell_', 'fan_duct', 'eyes_clip')),
    ('deck', '#33383f', ('deck',)),
    ('bay_doors', '#d98c26', ('bay_door_',)),
    ('bus_bars', '#c8743a', ('bus_bar_', 'bus_insulator_')),
    ('ear_pods', '#3b4049', ('ear_pod_',)),
    ('cameras', '#2a2d33', ('d435_front', 'd435_rear', 'eyes_board')),
    ('hardware', '#26282c', ('spacer', 'frame_screws_', 'cheek_nuts_', 'turret_plate_nuts', 'isolator_', 'bay_skid_')),
    ('brackets', '#454a52', ('post_', 'riser', 'plate_post_', 'dcdc_bracket', 'bay_rail_', 'adapter_plate_', 'ear_bracket_',
                             'd435_cradle_')),
    ('frame', '#b4bac4', ('cheek_', 'floor_tray', 'belly_plate', 'compute_pallet', 'power_plate', 'turret_plate', 'bay_')),
    ('battery', '#fdb913', ('item.battery_front', 'item.battery_rear')),
    ('compute', '#5a6b7c', ('item.j501', 'item.agx', 'item.lidar_')),
    ('electronics', '#2b6cb0', ('item.plate_', 'item.power_', 'item.vn100', 'item.battery_adapter')),
]
LEG_GROUPS = [                                   # per leg: <group>_l, <group>_r
    ('hip_frame', '#5f6670', ('hip_frame',)),
    ('motors', '#2a2d33', ('motor_',)),
    ('output_adapters', '#c9ced6', ('output_adapter_',)),
    ('upper_links', '#f5b82e', ('upper_link_',)),
    ('front_link', '#f5b82e', ('front_link',)),
    ('wheel_link', '#e9a21f', ('wheel_link',)),
    ('stops', '#c8382f', ('stop_sleeve_',)),
    ('tyre', '#1b1d21', ('wheel_tyre',)),
    ('hub', '#4a5058', ('wheel_hub',)),
    ('leg_hardware', '#8f969f', ('',)),          # bearings, pins, washers, spacers, nuts, sleeves, circlip, screws, stop posts
]
# the turret's parts by colour: turret_<group>; its printed parts not listed are turret_frame, its bought parts turret_bought
TURRET_GROUPS = {'barrel': ('#e8892b', ('barrel', 'hopper_flap')), 'hopper': ('#9cc9e8', ('hopper', 'hopper_lid')),
                 'dark': ('#3b3f46', ('flywheel_tyre', 'bumper_ring', 'pan_clamp', 'dial'))}
TURRET_FRAME, TURRET_BOUGHT = ('frame', '#b8bec7'), ('bought', '#3a3f47')
# The layout's envelopes for the turret (a Ø172 can the turret's mass, cad/body_layout.py) and the VLP-16 (a plain
# cylinder) stay in the layout for the mass ledger, keep-outs and checks; the pictures draw the turret's CAD and a
# VLP-16 shaped like one instead.
SKIP_ITEMS = ('turret', 'vlp16')
LIDAR = {'window': ('lidar', '#15171b'), 'housing': ('lidar_housing', '#9aa1aa'), 'window_half_h': 14.0, 'gland_r': 8.0,
         'gland_z': 12.7}

# the exploded picture: each leg straight out along y (+ left, - right), its wheel further; the turret up with the head
LEG_OUT = {'tyre': 330, 'hub': 330}
LEG_OUT_REST = 210
TURRET_UP = 420.0


def _v(s):
    return s.val() if hasattr(s, 'val') else s


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))


def _group(name, groups):
    for g, colour, prefixes in groups:
        if name.startswith(prefixes):
            return g, colour
    raise KeyError(f'{name}: no group takes it (add it to tools/robot_view.py)')


def _turret_group(name):
    for g, (colour, names) in TURRET_GROUPS.items():
        if name in names:
            return g, colour
    return TURRET_FRAME


def turret_shapes(face_z, pan_x):
    """The turret's parts and bought envelopes in the robot frame, at pan 0 and tilt 0: [(group, colour, name, shape)]. Placed as
    sim/robot_v2.py places it: its TM face on the riser (body_params.tm()['face_z']), its pan axis at pan_x."""
    import turret as tu
    T = tu.Turret({'bodyTop': face_z - 20.0 - tu.SADDLE_T})
    out = []
    for name, m in T.meta.items():
        for k in range(m['qty']):
            local = T.local[name] if k == 0 else T.local[name].mirror('XZ')
            sh = _v(T.pose_shape(local, T.frame[name], 0.0, 0.0, robot=True)).translate(cq.Vector(pan_x, 0, 0))
            out.append((*_turret_group(name), name if k == 0 else f'{name}_{k + 1}', sh))
    for name, (shape, frame, _, _) in T.bought.items():
        out.append((*TURRET_BOUGHT, name, _v(T.pose_shape(shape, frame, 0.0, 0.0, robot=True)).translate(cq.Vector(pan_x, 0, 0))))
    return out


def _vlp16_spec():
    cat = json.loads((R / 'catalog/sensors_compute.json').read_text())
    return next(c for c in cat if c['id'] == 'velodyne-vlp-16')['specs']


def lidar_shapes(envelope):
    """The VLP-16 in the layout's envelope (its cylinder on the deck), drawn as it looks: an aluminium base and cap and,
    between them, the dark window band round its optical centre (catalog/sensors_compute.json), with the cable gland out
    to +y as sim/robot_v2.py draws it. [(group, colour, name, shape)]."""
    b = _v(envelope).BoundingBox()
    x, y, r, z0, h = (b.xmin + b.xmax) / 2, (b.ymin + b.ymax) / 2, b.xlen / 2, b.zmin, b.zlen
    oc = _vlp16_spec()['optical_center_above_base_mm']
    w0, w1 = z0 + oc - LIDAR['window_half_h'], z0 + oc + LIDAR['window_half_h']
    cyl = lambda rr, za, zb: cq.Workplane('XY').workplane(offset=za).center(x, y).circle(rr).extrude(zb - za).val()
    groove = lambda zc: cq.Workplane('XY').workplane(offset=zc - 0.6).center(x, y).circle(r + 1).circle(r - 1.2).extrude(1.2).val()
    housing = cyl(r, z0, w0).fuse(cyl(r, w1, z0 + h))
    for k in range(3):                                   # the cap's cooling grooves
        housing = housing.cut(groove(z0 + h - 5.0 - 4.0 * k))
    gland = (cq.Workplane('XZ').workplane(offset=-(y + r - 2.0)).center(x, z0 + LIDAR['gland_z'])
             .circle(LIDAR['gland_r']).extrude(-(LIDAR['gland_z'] + 2.0)).val())
    window = cyl(r - 1.5, w0, w1)
    return [(*LIDAR['housing'], 'vlp16_housing', housing.fuse(gland)), (*LIDAR['window'], 'vlp16_window', window)]


def visual_items(items, tm):
    """The layout's items for a picture: the turret and VLP-16 envelopes replaced by their drawn shapes, one item per
    colour group ({'name', 'shape', 'rgb'}), named turret_<group> and vlp16_<part> (cad/body_views.py's exploded offsets
    match them by those prefixes)."""
    out = []
    for it in items:
        if it['name'] == 'turret':
            groups = {}
            for g, c, n, s in turret_shapes(tm['face_z'], tm['pan_x']):
                groups.setdefault((g, c), []).append(s)
            out += [{'name': f'turret_{g}', 'shape': cq.Compound.makeCompound(ss), 'rgb': _rgb(c)} for (g, c), ss in groups.items()]
        elif it['name'] == 'vlp16':
            out += [{'name': n, 'shape': s, 'rgb': _rgb(c)} for _, c, n, s in lidar_shapes(it['shape'])]
        else:
            out.append(it)
    return out


def collect():
    """Every part of the robot: [(group, colour, source name, shape, exploded offset (mm))]."""
    import body_params as bp
    import body_views as bv
    import build_body as bb
    L = bb._layout()
    rows = []
    for n, p in bf.all_parts(L['mounts']).items():
        if p.shape is None or not bf.on_robot(p, 'P3'):
            continue
        g, c = _group(n, BODY_GROUPS)
        rows.append((g, c, n, _v(p.shape), bv.offset(n)))
    for it in L['items']:
        if it['name'] in SKIP_ITEMS or it.get('shape') is None:
            continue
        n = f"item.{it['name']}"
        g, c = _group(n, BODY_GROUPS)
        rows.append((g, c, n, _v(it['shape']), bv.offset(n)))
    for n, s in bf.legs(STANCE_MM).items():
        side, part = n.split('.', 1)
        g, c = _group(part, LEG_GROUPS)
        sign = 1.0 if side == 'L' else -1.0
        rows.append((f'{g}_{side.lower()}', c, n, _v(s), (0.0, sign * LEG_OUT.get(g, LEG_OUT_REST), 0.0)))
    vlp16 = next(it for it in L['items'] if it['name'] == 'vlp16')
    for g, c, n, s in lidar_shapes(vlp16['shape']):
        rows.append((g, c, f'item.{n}', s, bv.offset('item.vlp16')))
    tm = bp.tm()
    for g, c, n, s in turret_shapes(tm['face_z'], tm['pan_x']):
        rows.append((f'turret_{g}', c, f'turret.{n}', s, (0.0, 0.0, TURRET_UP)))
    return rows


def export(rows):
    """One STEP per group in exports/robot/ (old files removed first) and robot.json: each group's colour and members."""
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob('*.step'):
        f.unlink()
    groups = {}
    for g, c, n, s, _ in rows:
        groups.setdefault(g, {'color': c, 'members': [], 'shapes': []})
        groups[g]['members'].append(n)
        groups[g]['shapes'].append(s)
    for g, d in groups.items():
        shape = d['shapes'][0] if len(d['shapes']) == 1 else cq.Compound.makeCompound(d['shapes'])
        cq.exporters.export(shape, str(OUT / f'{g}.step'))
    record = {'what': 'Gyropup as drawn today: the P3 body, both five-bar legs at the 300 mm stance, the turret at pan 0, '
                      'tilt 0. Bought parts are envelopes.',
              'frame': 'robot: x forward, y left, z up (mm), origin on the hip axis between the legs',
              'stance_mm': STANCE_MM, 'regenerate': '.venv/bin/python tools/robot_view.py',
              'groups': {g: {'color': d['color'], 'members': d['members']} for g, d in sorted(groups.items())}}
    (OUT / 'robot.json').write_text(json.dumps(record, indent=1) + '\n')
    return groups


def render(rows):
    from cadagent.render import Renderer
    r = Renderer(PICTURES, size=(900, 720), subtitle='GYROPUP | P3 BODY, FIVE-BAR LEGS (LEG V2), TURRET')
    asm = [(s, _rgb(c)) for _, c, _, s, _ in rows]
    r.render('assembly.png', shapes=asm, view=(1.0, -1.05, 0.55),
             caption=f'Gyropup assembled from the current CAD, legs at {STANCE_MM:.0f} mm')
    ex = [(s.translate(cq.Vector(*o)) if any(o) else s, _rgb(c)) for _, c, _, s, o in rows]
    r.render('exploded.png', shapes=ex, view=(1.0, -1.1, 0.75),
             caption='Exploded: shell out, head up, bay down, legs out')
    return ['assembly.png', 'exploded.png']


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--no-render', action='store_true', help='only the STEP files and robot.json')
    a = ap.parse_args(argv)
    rows = collect()
    groups = export(rows)
    print(f'exports/robot: {len(groups)} groups from {len(rows)} parts')
    if not a.no_render:
        for m in render(rows):
            print(f'cad/{m}')


if __name__ == '__main__':
    main()
