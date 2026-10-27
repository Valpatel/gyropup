"""Gyropup mechanical interfaces (GMI v0.3, printed): the standard faces and the parts that put each motor onto them.

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
import os
from pathlib import Path

import cadquery as cq

R = Path(__file__).resolve().parents[1]
STD = json.loads((R / 'cad/interfaces.json').read_text())
FAST = STD['fasteners']
# Printed parts (D33): sizes the optimiser may vary, overridden like leg.PARAMS by GYROPUP_CAD_PARAMS
PRINT = dict(STD['print']['defaults'])
if os.environ.get('GYROPUP_CAD_PARAMS'):
    PRINT.update({k: v for k, v in json.loads(Path(os.environ['GYROPUP_CAD_PARAMS']).read_text()).items() if k in PRINT})
CAT = json.loads((R / 'catalog/interfaces.json').read_text()) if (R / 'catalog/interfaces.json').exists() else {}


BRACKET_DROP = 10.0          # the yoke screws sit this far below the tab's top edge (the tab reaches 4 mm above tab_top)


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
            # dowels: holes in the motor (we press pins in) or pins the motor already has (we drill sockets for them)
            'dowels': ({'count': dw.get('count'), 'd': dw.get('diameter'), 'pcd': dw.get('pcd'),
                        'angles': dw.get('angles_deg') or [360.0 * k / dw['count'] + (dw.get('start_deg') or 0.0) for k in range(dw['count'])],
                        'installed': bool(out.get('dowel_pins')), 'protrusion': dw.get('protrusion')}
                       if (dw := out.get('dowel_holes') or out.get('dowel_pins')) else None),
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

def ao_bolt_deg(s) -> list:
    """The standard face's bolt angles (deg, motor frame): the standard's bolt_deg, else evenly spaced from half a
    pitch."""
    return s.get('bolt_deg') or [360.0 / s['bolts'] * (k + 0.5) for k in range(s['bolts'])]


def _arc_slot(r, w, a0, a1, z0, z1):
    """A pocket of width w along the arc of radius r from a0 to a1 (deg), round-ended, from z0 to z1."""
    ri, ro = r - w / 2, r + w / 2
    p = lambda rr, a: (rr * math.cos(math.radians(a)), rr * math.sin(math.radians(a)))
    am = (a0 + a1) / 2
    sector = (cq.Workplane('XY').workplane(offset=z0).moveTo(*p(ri, a0)).lineTo(*p(ro, a0)).threePointArc(p(ro, am), p(ro, a1))
              .lineTo(*p(ri, a1)).threePointArc(p(ri, am), p(ri, a0)).close().extrude(z1 - z0))
    return sector.union(_cyl(w / 2, z0, z1, *p(r, a0))).union(_cyl(w / 2, z0, z1, *p(r, a1)))


def output_adapter(part_id: str, size: str = 'L'):
    """Output adapter, motor frame (output face z = 0). Returns (solid, info with the axial positions).

    The standard's 'made' says how it is made: 'cnc' (6061-T6 from an instant-price CNC service: the face's holes
    tapped, a blind bore from the motor side for mass) or printed (PA6-CF, heat-set inserts in the face). Either way the
    motor's screws sit in pockets with their heads below the face, where the link sits (the standard's 'head'); where
    two pockets would leave a sliver of the spigot between them, the spigot is cut away between them."""
    mi, s = motor_interface(part_id), STD[f'AO-{size}']
    cnc = s.get('made') == 'cnc'
    o = mi['output']
    relief = s['relief']
    z_sh0 = relief
    z_face = z_sh0 + s['shoulder_len'] + s['journal_len'] + PRINT['journal_extra']   # longer: room for a thicker printed plate
    z_top = z_face + s['spigot_h']
    bw = STD[f'AC-{size}']['bearing_w']
    z_j0 = z_face - 1.0 - STD[f'AC-{size}']['seat_lip'] - bw   # the bearing sits under the plate's lip at its leg-side face
    body = (_cyl(o['flange_d'] / 2 - 0.5, 0, relief + 0.01)                                # contact boss on the flange only
            .union(_cyl(s['shoulder_d'] / 2, z_sh0, z_j0))                                  # shoulder: seats the inner ring
            .union(_cyl(s['journal_d'] / 2, z_j0, z_face))                                  # bearing journal
            .union(_cyl(s['spigot_d'] / 2, z_face, z_top)))                                 # standard spigot
    # the motor's screws: clearance through, heads in pockets in the spigot
    b = o['bolts']
    hd = s.get('head') or {'kind': 'socket head', 'd': 8.5, 'h': 5.0, 'pocket_d': 10.0, 'below_face': 0.6}
    pr = hd['pocket_d'] / 2
    z_pk = z_face - hd['below_face'] - hd['h']                                              # the pockets' floor: the heads' seat
    for (x, y) in circle_pts(b['pcd'], angles=b['angles']):
        body = body.cut(_cyl(clear(b['thread']) / 2, -1, z_top + 1, x, y))
        body = body.cut(_cyl(pr, z_pk, z_top + 1, x, y))
    angs = sorted(b['angles'])
    for a0, a1 in zip(angs, angs[1:] + [angs[0] + 360.0]):
        if b['pcd'] * math.sin(math.radians(a1 - a0) / 2) < 2 * pr + 3.0:                 # under 3 mm of spigot between them
            body = body.cut(_arc_slot(b['pcd'] / 2, 2 * pr, a0, a1, z_face, z_top + 1))     # (the spigot only: the face's holes are below it)
    if o['dowels']:
        dw = o['dowels']
        for (x, y) in circle_pts(dw['pcd'], angles=dw['angles']):
            if dw['installed']:                                                             # the motor's own pins: sockets
                body = body.cut(_cyl(dw['d'] / 2 + (0.0 if cnc else 0.03), -1, (dw['protrusion'] or 3.0) + 0.5, x, y))
            else:                                                                           # steel pins pressed in, into the motor
                body = body.cut(_cyl(dw['d'] / 2 - 0.05, -1, 16, x, y))                     # 16 mm in the plastic: low bearing stress
    if o['pilot_d']:                                                                        # locating boss into the motor's recess
        body = body.union(_cyl(o['pilot_d'] / 2 - 0.05, -2.0, 0.01))
    # the standard face: tapped (cnc) or heat-set inserts (printed) on the PCD, dowel holes
    c = s.get('cnc', {})
    for (x, y) in circle_pts(s['pcd'], angles=ao_bolt_deg(s)):
        if cnc:
            body = body.cut(_cyl(FAST[s['thread']]['tap'] / 2, z_face - c['drill_depth'], z_face + 0.01, x, y))
        else:
            body = body.cut(_cyl(FAST[s['thread']]['insert_pilot'] / 2, z_face - PRINT['insert_depth_ao'], z_face + 0.01, x, y))
    for (x, y) in circle_pts(s['pcd'], angles=s['dowel_deg']):
        body = body.cut(_cyl(s['dowel_d'] / 2, z_face - 8, z_face + 0.01, x, y))
    if cnc and c.get('bore_d'):                                                             # mass: a blind bore from the motor side
        body = body.cut(_cyl(c['bore_d'] / 2, -1, c['bore_depth']))
    if cnc:                                                                                  # a 0.5 x 45 lead-in on the journal's face end
        r = s['journal_d'] / 2
        ring = (cq.Workplane('XZ').polyline([(r - 0.5, z_face + 0.01), (r + 1.0, z_face + 0.01), (r + 1.0, z_face - 1.0), (r, z_face - 0.5)])
                .close().revolve(360, (0, 0, 0), (0, 1, 0)))
        body = body.cut(ring)
    pins = (f"sockets for the motor's {o['dowels']['count']} x Ø{o['dowels']['d']:g} pins" + (' (H7)' if cnc else '') if o['dowels'] and o['dowels']['installed']
            else f"{o['dowels']['count']} x Ø{o['dowels']['d']:g} x 20 steel dowels into the motor" if o['dowels'] else 'no dowels: torque by clamp')
    screws = f"{b['count']} x {b['thread']} x {hd.get('length', 25):g} {hd['kind']}s into the motor, heads in pockets {hd['below_face']:g} mm below the face"
    if cnc:
        note = (f"CNC {c['material']} (instant price: JLCCNC, backup Xometry; exports/leg/cnc/); {s['bolts']} x {s['thread']} tapped "
                f"{c['thread_depth']:g} deep and {s['dowels']} x Ø{s['dowel_d']:g} {c['dowel_fit']} dowel holes in the face; {pins}; {screws}; "
                f"Ø{s['journal_d']:g} {c['journal_fit']} journal for the support bearing; a Ø{c['bore_d']:g} x {c['bore_depth']:g} blind bore from the motor side")
    else:
        note = f"printed PA6-CF, 100 % solid; {s['bolts']} x {s['thread']} heat-set inserts in the face; {pins}; {screws}"
    deg = lambda angs: ', '.join(f'{a:g}' for a in angs)
    spec = None
    if cnc:                     # the callouts a CNC order needs beyond the STEP (motor frame: the motor face at z = 0, +z to the link)
        spec = [f"Material {c['material']}; {c['finish']}; general tolerance {c['general']}; threads 6H",
                f"Datums: A = the Ø{s['journal_d']:g} journal's axis; the contact face (z 0) square to A within 0.02; the standard face "
                f"(z {z_face:g}) parallel to the contact face within 0.02; the dowel holes and the motor's pin sockets at position Ø0.05 to A",
                f"Ø{s['journal_d']:g} {c['journal_fit']} journal, z {z_j0:g} to {z_face:g}, with a 0.5 x 45 deg lead-in at the face end: the "
                f"support bearing's inner ring (61812), fitted with retaining compound",
                f"Ø{s['shoulder_d']:g} shoulder, its face at z {z_j0:g} square to the axis within 0.02: seats the bearing's inner ring",
                f"Contact face at z 0 (Ø{o['flange_d'] - 1:g}) flat within 0.02; {relief:g} mm relief outside it",
                f"{s['bolts']} x {s['thread']} tapped {c['thread_depth']:g} deep (drill Ø{FAST[s['thread']]['tap']:g} x {c['drill_depth']:g}) from the face (z {z_face:g}), "
                f"PCD {s['pcd']:g} at {deg(ao_bolt_deg(s))} deg",
                f"{s['dowels']} x Ø{s['dowel_d']:g} {c['dowel_fit']} x 8 deep from the face, PCD {s['pcd']:g} at {deg(s['dowel_deg'])} deg (Ø{s['dowel_d']:g} m6 dowel pins pressed in)",
                f"{b['count']} x Ø{clear(b['thread']):g} through, PCD {b['pcd']:g} at {deg(b['angles'])} deg, each with a Ø{hd['pocket_d']:g} counterbore from the top "
                f"to z {z_pk:g} ({z_face - z_pk:g} below the face); the spigot is cut away between counterbores closer than 3 mm",
                *([f"{o['dowels']['count']} x Ø{o['dowels']['d']:g} H7 x {(o['dowels']['protrusion'] or 3.0) + 0.5:g} deep from the motor face, PCD {o['dowels']['pcd']:g} "
                   f"at {deg(o['dowels']['angles'])} deg (the motor's own pins)"] if o['dowels'] and o['dowels']['installed'] else []),
                f"Ø{c['bore_d']:g} x {c['bore_depth']:g} blind bore from the motor face (mass)",
                f"Ø{s['spigot_d']:g} spigot, {s['spigot_h']:g} tall (general tolerance: the dowels locate the link; the spigot is three lobes "
                f"between the counterbores and a lead into the link's recess)",
                "Walls of 1.4 mm (1.0 mm to the thread's major diameter) between the counterbores and the face's tapped and dowel holes, "
                "15 deg apart: intended, fine in 6061"]
    return body, {'part': part_id, 'z_face': z_face, 'z_journal': (z_j0, z_face), 'z_head_seat': z_pk, 'head': hd,
                  'material': 'al6061' if cnc else 'pa6-cf', 'made': 'cnc' if cnc else 'print', 'note': note, 'spec': spec, 'assumed': mi['assumed']}


def std_face_mate(size: str = 'L', depth: float = 12.0):
    """What a link cuts to sit on the AO face (z = 0 is the face; the link is on +z): spigot recess, bolt
    clearances, dowel holes."""
    s = STD[f'AO-{size}']
    c = _cyl(s['spigot_d'] / 2 + 0.05, -0.01, s['spigot_h'] + 0.3)
    for (x, y) in circle_pts(s['pcd'], angles=ao_bolt_deg(s)):
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
    if z_top < z_bear1 + s['seat_lip'] - 1e-6:
        raise ValueError('journal shorter than the bearing and its lip')
    b = c['bolts']
    ring_r = max(b['pcd'] / 2 + clear(b['thread']) + 4.5, s['bearing_od'] / 2 + 6)
    t_arm = z_top - lug_z                                                                   # printed: arms the plate's full thickness
    arm_z0 = z_top - t_arm
    p = _cyl(ring_r, lug_z, z_top)
    # three arms to the spacer posts, and a tab on top for the hip bracket
    for ang in s['post_deg']:
        x, y = s['post_r'] * math.cos(math.radians(ang)), s['post_r'] * math.sin(math.radians(ang))
        arm = (cq.Workplane('XY').workplane(offset=arm_z0).center(x / 2, y / 2).rect(math.hypot(x, y), PRINT['plate_arm_w'])
               .extrude(t_arm).rotate((x / 2, y / 2, 0), (x / 2, y / 2, 1), math.degrees(math.atan2(y, x))))
        p = p.union(arm).union(_cyl(s['post_d'] / 2 + 6, lug_z, z_top, x, y))
        p = p.cut(_cyl(clear(s['post_thread']) / 2, lug_z - 1, z_top + 1, x, y))
    tab_top = s['plate_r'] + s['top_ext'] + PRINT['tab_extra']        # printed: a taller tab, the yoke screws clear of every edge
    # the tab carries the whole leg into the yoke: full plate thickness, widening into the ring (no thin neck)
    # printed: the tab's shoulders run out to the side posts' bosses, so there is no notch between tab and arms
    sx, sy = s['post_r'] * math.cos(math.radians(min(s['post_deg']))), s['post_r'] * math.sin(math.radians(min(s['post_deg'])))
    tab = (cq.Workplane('XY').workplane(offset=lug_z).polyline([(-s['plate_r'] * 0.55, tab_top + 4), (s['plate_r'] * 0.55, tab_top + 4),
                                                               (sx + 2, sy + 4), (sx - 4, sy - 16), (ring_r, 0.0),
                                                               (-ring_r, 0.0), (-sx + 4, sy - 16), (-sx - 2, sy + 4)]).close()
           .extrude(z_top - lug_z))
    p = p.union(tab)
    win_z0, win_z1 = ring_r + 12.0, tab_top - 22.0                        # a window in the tab, a 14 mm frame left round it
    if PRINT['plate_tab_window'] and win_z1 - win_z0 > 8:
        p = p.cut(cq.Workplane('XY').workplane(offset=lug_z - 1).center(0, (win_z0 + win_z1) / 2)
                  .rect(2 * (s['plate_r'] * 0.55 - 12), win_z1 - win_z0).extrude(z_top - lug_z + 2))
    for k in range(s['bracket_bolts']):
        x = (k - (s['bracket_bolts'] - 1) / 2) * s['plate_r'] * 0.4
        p = p.cut(_cyl(FAST[s['bracket_thread']]['insert_pilot'] / 2, lug_z - 1, lug_z + 10, x, tab_top - BRACKET_DROP))   # inserts from the motor side, where the yoke is
    # motor side: the spigot recess (if the motor has a male spigot) and the lug screws (counterbored from the leg side)
    if c['spigot_d']:
        p = p.cut(_cyl(c['spigot_d'] / 2 + 0.03, lug_z - 0.01, lug_z + c['spigot_h'] + 0.1))
    for (x, y) in circle_pts(b['pcd'], angles=b['angles']):
        p = p.cut(_cyl(clear(b['thread']) / 2, lug_z - 1, z_top + 1, x, y))
        p = p.cut(_cyl(clear(b['thread']) * 0.95, z_top - PRINT['lug_counterbore'], z_top + 1, x, y))   # deep: a stocked length engages
    # the bore: the bearing goes in from the motor side and stops on a lip at the leg-side face. Its outer ring only ever
    # takes outward thrust (the adapter's shoulder lifts the inner ring; nothing pushes the inner ring in), which the lip
    # carries, so no retainers: the leg-side face stays flat, 1 mm from the link
    p = p.cut(_cyl(s['bearing_od'] / 2 + 0.3, lug_z - 1, z_bear0))                        # a clearance lead-in from the motor side,
    p = p.cut(_cyl(s['bearing_od'] / 2, z_bear0 - 0.01, z_bear1))                         # then the seat: line-to-line, sanded to fit
    p = p.cut(_cyl(s['lip_d'] / 2, z_bear1 - 0.01, z_top + 1))
    # lightening pockets in the ring between the lug screws, from the motor side, 6 mm deep (the lug faces, the bearing
    # seat and the leg-side face stay whole)
    r_in, r_out = s['bearing_od'] / 2 + 3.0, ring_r - 3.0
    if PRINT['plate_pockets'] and r_out - r_in > 6:                      # (printed: no pockets, their thin walls crack)
        angs = sorted(b['angles'])
        for k, a0 in enumerate(angs):
            a1 = angs[(k + 1) % len(angs)] + (360 if k == len(angs) - 1 else 0)
            mid, span = (a0 + a1) / 2, (a1 - a0)
            half = max(0.0, span / 2 - math.degrees((clear(b['thread']) * 0.95 + 3.0) / (b['pcd'] / 2)))
            if half < 4:
                continue
            sector = (cq.Workplane('XY').workplane(offset=lug_z - 0.01)
                      .moveTo(r_in * math.cos(math.radians(mid - half)), r_in * math.sin(math.radians(mid - half)))
                      .lineTo(r_out * math.cos(math.radians(mid - half)), r_out * math.sin(math.radians(mid - half)))
                      .threePointArc((r_out * math.cos(math.radians(mid)), r_out * math.sin(math.radians(mid))),
                                     (r_out * math.cos(math.radians(mid + half)), r_out * math.sin(math.radians(mid + half))))
                      .lineTo(r_in * math.cos(math.radians(mid + half)), r_in * math.sin(math.radians(mid + half)))
                      .threePointArc((r_in * math.cos(math.radians(mid)), r_in * math.sin(math.radians(mid))),
                                     (r_in * math.cos(math.radians(mid - half)), r_in * math.sin(math.radians(mid - half))))
                      .close().extrude(min(6.0, z_bear0 - lug_z + 4.0)))
            p = p.cut(sector)
    return p, {'part': part_id, 'z': (lug_z, z_top), 'bearing_z': (z_bear0, z_bear1), 'tab_z': (lug_z, z_top), 'tab_top': tab_top, 'ring_r': ring_r, 'material': 'pa6-cf',
               'note': f"printed PA6-CF, 100 % solid, flat; {s['bearing']} support bearing pressed in from the motor side against a {s['seat_lip']:g} mm lip; "
                       f"{s['bracket_bolts']} x {s['bracket_thread']} inserts for the yoke", 'assumed': mi['assumed']}


# vendor STEP files (kept local, see references/vendor/*/SOURCE.txt): where each one's output face is
STEP_FRAMES = {
               'robstride-rs-04': {'file': 'RS04.stp', 'axis': 'z', 'output_z': 25.5}}     # case face 25.0, output 0.5 proud


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
