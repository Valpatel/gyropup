"""Gyropup mechanical interfaces (GMI v0.2): the standard faces and the parts that put each motor onto them.

docs/mechanical-interfaces.md explains the standard; cad/interfaces.json holds its numbers. Each motor's own patterns
come from catalog/interfaces.json, taken from the vendor drawings and checked against their STEP files
(research/actuator-interfaces.md).

For each joint motor there are two motor-specific parts, and everything else only sees standard faces:
  output adapter (AO)  sits on the motor's output: a contact boss the size of the output flange (with a relief
                       elsewhere, because RobStride outputs are flush with a stationary ring), dowels into the
                       motor's dowel holes, a Ø70 journal for the support bearing, and the standard face for the link
  motor plate (AC)     bolts to the motor's mounting lugs, locates its spigot, and holds the support bearing (61814)
                       around the adapter's journal, so bending from the leg goes into the structure, not into the
                       motor's thin output bearing; standard holes for the yoke posts and the hip bracket

Local frame of a motor: axis +z, the OUTPUT FACE at z = 0, the motor body at z < 0, the leg side at z > 0.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cadquery as cq

R = Path(__file__).resolve().parents[1]
STD = json.loads((R / 'cad/interfaces.json').read_text())
FAST = STD['fasteners']
CAT = json.loads((R / 'catalog/interfaces.json').read_text()) if (R / 'catalog/interfaces.json').exists() else {}


def motor_interface(part_id: str) -> dict:
    """Envelope and patterns of a motor (catalog/interfaces.json), normalised. 'assumed' is True unless the data came
    from a drawing; 'missing' lists what the build had to guess."""
    m = CAT.get(part_id)
    if not m:
        raise KeyError(f'{part_id}: no interface data in catalog/interfaces.json')
    env, out, case = m.get('envelope') or {}, m.get('output') or {}, m.get('case') or {}
    missing = []

    def pat(p, name):
        if not p:
            missing.append(name)
            return None
        return {'count': p.get('count'), 'thread': (p.get('thread') or '').split('-')[0] or None, 'pcd': p.get('pcd'),
                'angles': p.get('angles_deg') or [360.0 * k / (p.get('count') or 1) for k in range(p.get('count') or 0)],
                'depth': p.get('depth')}
    sp = case.get('spigot') or {}
    info = {
        'id': part_id,
        'od': env.get('outer_diameter'),
        'length': env.get('length_total_step') or env.get('length_total'),
        'output': {
            'flange_d': out.get('flange_diameter'),
            'face_offset': out.get('face_offset_from_case_face') or 0.0,
            'bolts': pat(out.get('bolts'), 'output bolts'),
            'dowels': ({'count': out['dowel_holes'].get('count'), 'd': out['dowel_holes'].get('diameter'), 'pcd': out['dowel_holes'].get('pcd'),
                        'angles': out['dowel_holes'].get('angles_deg') or [360.0 * k / out['dowel_holes']['count'] for k in range(out['dowel_holes']['count'])]}
                       if out.get('dowel_holes') else None),
            'pilot_d': (out.get('pilot') or {}).get('diameter'),
        } if out.get('bolts') else None,
        'case': {
            'face': case.get('mount_face'),
            'bolts': pat(case.get('bolts'), 'case bolts'),
            'spigot_d': sp.get('diameter') if (sp.get('type') or '').startswith('male') else None,
            'spigot_h': sp.get('height') or 0.0,
            'boss_d': sp.get('diameter'),
        },
        'confidence': m.get('confidence'),
    }
    if info['output'] and not info['output']['flange_d']:
        missing.append('output flange diameter')
        info['output']['flange_d'] = (info['output']['bolts']['pcd'] or 30) + 10
    info['assumed'] = m.get('confidence') not in ('drawing',) or bool(missing)
    info['missing'] = missing
    return info


def circle_pts(pcd: float, n: int = None, start_deg: float = 0.0, angles=None):
    angs = angles if angles is not None else [start_deg + 360.0 * k / n for k in range(n)]
    return [(pcd / 2 * math.cos(math.radians(a)), pcd / 2 * math.sin(math.radians(a))) for a in angs]


def clear(thread: str) -> float:
    return FAST[thread]['clear']


def tap(thread: str) -> float:
    return FAST[thread]['tap']


def _cyl(r, z0, z1, x=0.0, y=0.0):
    return cq.Workplane('XY').workplane(offset=z0).center(x, y).circle(r).extrude(z1 - z0)


# ----------------------------------------------------------------------------------- the output adapter (AO)

def output_adapter(part_id: str, size: str = 'L'):
    """Output adapter, motor frame (output face z = 0). Returns (solid, info with the axial positions)."""
    mi, s = motor_interface(part_id), STD[f'AO-{size}']
    o = mi['output']
    relief = s['relief']
    z_sh0 = relief
    z_j0 = z_sh0 + s['shoulder_len']
    z_face = z_j0 + s['journal_len']
    body = (_cyl(o['flange_d'] / 2 - 0.5, 0, relief + 0.01)                                # contact boss on the flange only
            .union(_cyl(s['shoulder_d'] / 2, z_sh0, z_j0))                                  # bearing shoulder
            .union(_cyl(s['journal_d'] / 2, z_j0, z_face))                                  # bearing journal
            .union(_cyl(s['spigot_d'] / 2, z_face, z_face + s['spigot_h'])))                 # standard spigot
    # the motor's screws: clearance through, heads in counterbores under the spigot face
    b = o['bolts']
    for (x, y) in circle_pts(b['pcd'], angles=b['angles']):
        d = clear(b['thread'])
        body = body.cut(_cyl(d / 2, -1, z_face + s['spigot_h'] + 1, x, y))
        body = body.cut(_cyl(d * 0.92, z_face + s['spigot_h'] - 4.5, z_face + s['spigot_h'] + 1, x, y))
    if o['dowels']:                                                                         # pins pressed in, into the motor
        dw = o['dowels']
        for (x, y) in circle_pts(dw['pcd'], angles=dw['angles']):
            body = body.cut(_cyl(dw['d'] / 2 - 0.01, -1, 6, x, y))
    if o['pilot_d']:                                                                        # locating boss into the motor's recess
        body = body.union(_cyl(o['pilot_d'] / 2 - 0.05, -2.0, 0.01))
    # the standard face: tapped holes (helicoils) on the PCD, dowel holes, all clear of the motor screw counterbores
    for (x, y) in circle_pts(s['pcd'], s['bolts'], 360.0 / s['bolts'] / 2):
        body = body.cut(_cyl(tap(s['thread']) / 2, z_face - 9, z_face + 0.01, x, y))
    for a in s['dowel_deg']:
        x, y = s['pcd'] / 2 * math.cos(math.radians(a)), s['pcd'] / 2 * math.sin(math.radians(a))
        body = body.cut(_cyl(s['dowel_d'] / 2, z_face - 8, z_face + 0.01, x, y))
    return body, {'part': part_id, 'z_face': z_face, 'z_journal': (z_j0, z_face), 'material': 'al6061',
                  'note': 'CNC 6061-T6; standard-face holes take M5 helicoils; motor dowels pressed in', 'assumed': mi['assumed']}


def std_face_mate(size: str = 'L', depth: float = 12.0):
    """What a link cuts to sit on the AO face (z = 0 is the face; the link is on +z): spigot recess, bolt
    clearances, dowel holes."""
    s = STD[f'AO-{size}']
    c = _cyl(s['spigot_d'] / 2 + 0.05, -0.01, s['spigot_h'] + 0.3)
    for (x, y) in circle_pts(s['pcd'], s['bolts'], 360.0 / s['bolts'] / 2):
        c = c.union(_cyl(clear(s['thread']) / 2, -0.01, depth, x, y))
    for a in s['dowel_deg']:
        x, y = s['pcd'] / 2 * math.cos(math.radians(a)), s['pcd'] / 2 * math.sin(math.radians(a))
        c = c.union(_cyl(s['dowel_d'] / 2 + 0.02, -0.01, depth, x, y))
    return c


# ----------------------------------------------------------------------------------- the motor plate (AC)

def motor_plate(part_id: str, size: str = 'L', thick_extra: float = 1.0):
    """Motor plate, motor frame. It sits on the motor's mounting lugs (output side), holds the support bearing around
    the adapter's journal, and offers the standard post and bracket holes. Returns (solid, info)."""
    mi, s, a = motor_interface(part_id), STD[f'AC-{size}'], STD[f'AO-{size}']
    c = mi['case']
    lug_z = -(mi['output']['face_offset'] if mi['output'] else 0.0)                     # lug face, behind the output face
    _, ad = output_adapter(part_id, size)
    j0, j1 = ad['z_journal']
    z_bear0 = j0
    z_bear1 = j0 + s['bearing_w']
    z_top = j1 - 1.0                                                                       # 1 mm short of the AO face: the link clears it
    if z_top < z_bear1:
        raise ValueError('journal shorter than the bearing')
    b = c['bolts']
    ring_r = max(b['pcd'] / 2 + clear(b['thread']) + 4.5, s['bearing_od'] / 2 + 6)
    t_arm = min(8.0, z_top - lug_z)
    arm_z0 = z_top - t_arm                                                                  # arms flush with the leg-side face
    p = _cyl(ring_r, lug_z, z_top)
    # three arms to the spacer posts, and a tab on top for the hip bracket
    for ang in s['post_deg']:
        x, y = s['post_r'] * math.cos(math.radians(ang)), s['post_r'] * math.sin(math.radians(ang))
        arm = (cq.Workplane('XY').workplane(offset=arm_z0).center(x / 2, y / 2).rect(math.hypot(x, y), 16)
               .extrude(t_arm).rotate((x / 2, y / 2, 0), (x / 2, y / 2, 1), math.degrees(math.atan2(y, x))))
        p = p.union(arm).union(_cyl(s['post_d'] / 2 + 4, lug_z, z_top, x, y))
        p = p.cut(_cyl(clear(s['post_thread']) / 2, lug_z - 1, z_top + 1, x, y))
    tab_top = s['plate_r'] + s['top_ext']
    # the tab carries the whole leg into the yoke: full plate thickness, widening into the ring (no thin neck)
    tab = (cq.Workplane('XY').workplane(offset=lug_z).polyline([(-s['plate_r'] * 0.55, tab_top + 4), (s['plate_r'] * 0.55, tab_top + 4),
                                                               (ring_r * 0.95, ring_r * 0.35), (-ring_r * 0.95, ring_r * 0.35)]).close()
           .extrude(min(10.0, z_top - lug_z)).translate((0, 0, max(0.0, z_top - lug_z - 10.0))))
    p = p.union(tab)
    for k in range(s['bracket_bolts']):
        x = (k - (s['bracket_bolts'] - 1) / 2) * s['plate_r'] * 0.4
        p = p.cut(_cyl(tap(s['bracket_thread']) / 2, lug_z - 1, z_top + 1, x, tab_top - 8))
    # motor side: the spigot recess (if the motor has a male spigot) and the lug screws (counterbored from the leg side)
    if c['spigot_d']:
        p = p.cut(_cyl(c['spigot_d'] / 2 + 0.03, lug_z - 0.01, lug_z + c['spigot_h'] + 0.1))
    for (x, y) in circle_pts(b['pcd'], angles=b['angles']):
        p = p.cut(_cyl(clear(b['thread']) / 2, lug_z - 1, z_top + 1, x, y))
        p = p.cut(_cyl(clear(b['thread']) * 0.95, z_top - 4.5, z_top + 1, x, y))
    # the bore: clears the rotating shoulder (lip), then the bearing seat
    p = p.cut(_cyl(s['lip_d'] / 2, lug_z - 1, z_top + 1))
    p = p.cut(_cyl(s['bearing_od'] / 2 + 0.01, z_bear0, z_top + 1))
    return p, {'part': part_id, 'z': (lug_z, z_top), 'bearing_z': (z_bear0, z_bear1), 'tab_z': (max(lug_z, z_top - 10.0), z_top), 'tab_top': tab_top, 'material': 'al6061',
               'note': f"CNC 6061-T6; {s['bearing']} support bearing, circlips DIN 472/471", 'assumed': mi['assumed']}


# vendor STEP files (kept local, see references/vendor/*/SOURCE.txt): where each one's output face is
STEP_FRAMES = {'robstride-rs-03': {'file': 'RS03.stp', 'axis': 'z', 'output_z': 37.5}}


def motor_body(part_id: str):
    """The motor itself, in the motor frame (output face z = 0, body towards -z): the vendor STEP when it is on this
    machine, else a stepped envelope from the drawing numbers. Returns (shape, 'step'|'envelope')."""
    f = STEP_FRAMES.get(part_id)
    if f and (R / 'references/vendor' / part_id / f['file']).exists():
        shape = cq.importers.importStep(str(R / 'references/vendor' / part_id / f['file']))
        return shape.translate((0, 0, -f['output_z'])), 'step'
    mi = motor_interface(part_id)
    od, L = mi['od'] or 100.0, mi['length'] or 50.0
    off = mi['output']['face_offset'] if mi['output'] else 0.0
    body = _cyl(od / 2, -L, -off)
    front = mi['case']['spigot_d'] or (mi['output']['flange_d'] + 10 if mi['output'] else od * 0.7)
    body = body.union(_cyl(front / 2, -off, 0.0))
    if mi['output'] and mi['output']['pilot_d']:
        body = body.cut(_cyl(mi['output']['pilot_d'] / 2, -2.5, 0.01))
    return body, 'envelope'


def place(shape, origin=(0, 0, 0), axis=(0, 0, 1)):
    """Move a part built in a motor frame (axis +z) so its +z points along `axis` from `origin` (robot frame)."""
    ax = tuple(float(v) for v in axis)
    rot = {(0.0, 1.0, 0.0): ((1, 0, 0), -90), (0.0, -1.0, 0.0): ((1, 0, 0), 90), (1.0, 0.0, 0.0): ((0, 1, 0), 90),
           (-1.0, 0.0, 0.0): ((0, 1, 0), -90), (0.0, 0.0, -1.0): ((1, 0, 0), 180)}.get(ax)
    out = shape.rotate((0, 0, 0), rot[0], rot[1]) if rot else shape
    return out.translate(tuple(origin))
