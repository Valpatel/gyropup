"""Conditional front/rear DeWalt packs through the existing body CAD owner (#193).

Overall pack/adapter outlines are planning envelopes. The selected Azocek
interface, latch, mounting holes and electrical ratings are unmeasured. These
parts are WIP geometry, not a manufacturing or physical retention release.
The old belly bay and its pad studies remain historical, source-pinned evidence.
"""
from __future__ import annotations

if __package__ in (None, ''):
    import sys as _checkout_sys
    from pathlib import Path as _CheckoutPath
    _checkout_sys.path.insert(0, str(_CheckoutPath(__file__).resolve().parents[3]))

import math
from collections.abc import Mapping
import cadquery as cq
import hardware.cad.body.body_params as bp

# Issue #193 planning inputs. These are overall outlines, not mating-interface CAD.
# AMKUS LAI-002 Rev05 (2021-11-15), p8, identifies DCB609 as 137 x 97 x 91 mm,
# 1.45 kg, and DCB606 as 124 x 84 x 91 mm, 1.0 kg. The existing DCB547-derived
# 138 x 87 x 97 outline is retained as a conflicting reference, not relabelled.
PACK_OUTLINE_SOURCE = ('https://device.report/m/'
    'ece13665cf944f3420373a08d01f8946493f8ec6b33ccaa41fbd18d8d414dc6d.pdf#page=8')
PACK_PROFILES = {
    'DCB609': {'name': 'DeWalt DCB609 FLEXVOLT 20V/60V MAX 9.0 Ah',
               'L': 137.0, 'W': 97.0, 'H': 91.0, 'mass_g': 1565.0,
               'published_mass_g': 1450.0, 'ah': 9.0, 'wh_rated': 180.0},
    'DCB606': {'name': 'DeWalt DCB606 FLEXVOLT 20V/60V MAX 6.0 Ah',
               'L': 124.0, 'W': 84.0, 'H': 91.0, 'mass_g': 1000.0,
               'published_mass_g': 1000.0, 'ah': 6.0, 'wh_rated': 120.0},
}
SUPPORTED_OUTLINE_MM = (138.0, 97.0, 97.0)  # union of dated references, NOT a measured pack
END_PACK = {'shell_allowance_mm': 2.6, 'wall_gap_mm': 5.0,
            'support_stock': '5052-0.125', 'bottom_margin_mm': 5.0,
            'hand_clearance_mm': 50.0}
SELECTED_ADAPTER = {'name': 'Azocek DeWalt 20V adapter', 'asin': 'B0CDGR4Y8K',
                    'source': 'https://www.amazon.com/dp/B0CDGR4Y8K',
                    'interface_measured': False, 'mount_holes': None, 'rail': None,
                    'latch': None, 'electrical_ratings_verified': False,
                    'planning_outline_mm': (100.0, 72.0, 25.0),
                    'basis': 'CONDITIONAL planning reservation only; selected Azocek is not the old Terrafirma adapter'}


def pack_profile(profile='DCB609'):
    """A dated nominal outline or an explicitly supplied smaller planning envelope.

    Bounds are checked against the reference union; choosing a smaller envelope
    never rescales the adapter, rail or mounting datum. Electrical/interface fit
    is not inferred from an outline. Custom mass must be provided independently.
    """
    if isinstance(profile, str):
        if profile not in PACK_PROFILES:
            raise ValueError(f'Unknown pack profile: {profile}')
        out = dict(PACK_PROFILES[profile], profile=profile, source=PACK_OUTLINE_SOURCE)
    elif isinstance(profile, Mapping):
        if set(profile) - {'name', 'source', 'L', 'W', 'H', 'mass_g'}:
            raise ValueError('Custom pack accepts only overall dimensions, mass, name and source; no inferred interface or electrical specification')
        out = dict(profile)
        out.setdefault('name', 'Smaller conditional pack envelope')
        out['profile'] = 'custom'
        out.setdefault('source', 'User-supplied planning envelope; not a measured mating interface')
    else:
        raise ValueError('Pack profile must name a supported pack or supply an explicit envelope')
    if any(not isinstance(out.get(key), str) or not out[key].strip() for key in ('name', 'source')):
        raise ValueError('Pack name and source must be nonempty text')
    for key in ('L', 'W', 'H', 'mass_g'):
        value = out.get(key)
        try:
            number = float(value) if not isinstance(value, bool) and isinstance(value, (int, float)) else math.nan
        except (OverflowError, ValueError):
            number = math.nan
        if not math.isfinite(number) or number <= 0:
            raise ValueError(f'Pack {key} must be finite and positive')
        out[key] = number
    if not math.isfinite(2.0 * out['mass_g']):
        raise ValueError('Combined pack mass must remain finite')
    if any(out[key] > cap for key, cap in zip(('L', 'W', 'H'), SUPPORTED_OUTLINE_MM)):
        raise ValueError('Pack exceeds the supported reference envelope; recheck the holder and all clearances')
    out.update(envelope=True, interface_measured=False, physical_fit_verified=False,
               blocked_by='issue #20 / #193: actual pack and Azocek rail, latch, terminals and mounting-hole measurements')
    if out['profile'] == 'DCB609':
        out['mass_basis'] = '1.565 kg retained conservative planning mass; AMKUS lists 1.45 kg; actual pack unweighed'
    else:
        out['mass_basis'] = 'AMKUS published mass' if out['profile'] == 'DCB606' else 'User-supplied planning mass'
    return out


def _placed_bounds(box, matrix):
    """Bounds of eight independently transformed corners; no CAD or interface scaling."""
    points = [tuple(sum(matrix[4 * row + col] * p[col] for col in range(3)) + matrix[4 * row + 3]
                    for row in range(3))
              for p in ((x, y, z) for x in box[:2] for y in box[2:4] for z in box[4:6])]
    return tuple(value for axis in range(3) for value in (min(p[axis] for p in points), max(p[axis] for p in points)))


def end_pack_geometry(profile='DCB609', *, belly_z=None, body_x=None, support_t=None):
    """Conditional vertical end packs in the existing robot frame (mm, z up).

    Local X is the upward rail axis, Y is lateral, and +Z points into the adapter.
    The top/mating reference is fixed by the maximum reference outline, not by a
    variant's dimensions. Its actual relationship to a purchased latch is unknown.
    """
    spec = pack_profile(profile)
    belly_z = z_belly() if belly_z is None else belly_z
    body_x = bp.BODY_X if body_x is None else body_x
    support_t = bp.STOCK[END_PACK['support_stock']]['t'] if support_t is None else support_t
    try:
        valid_frame = (isinstance(body_x, (list, tuple)) and len(body_x) == 2 and
            all(not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v)
                for v in (*body_x, belly_z, support_t)) and body_x[0] < body_x[1] and support_t > 0)
    except (OverflowError, TypeError, ValueError):
        valid_frame = False
    if not valid_frame:
        raise ValueError('End-pack frame needs finite ordered body ends, belly height and positive support thickness')
    al, aw, ah = SELECTED_ADAPTER['planning_outline_mm']
    cap_l, cap_w, cap_h = SUPPORTED_OUTLINE_MM
    top_z = belly_z + cap_l + END_PACK['bottom_margin_mm']
    travel = cap_l + END_PACK['hand_clearance_mm']
    local = (-spec['L'], 0.0, -spec['W'] / 2, spec['W'] / 2, -spec['H'], 0.0)
    conservative = (-cap_l, 0.0, -cap_w / 2, cap_w / 2, -cap_h, 0.0)
    adapter = (-al, 0.0, -aw / 2, aw / 2, 0.0, ah)
    out = {'profile': spec, 'reference_union_mm': list(SUPPORTED_OUTLINE_MM),
           'reference_union_measured': False, 'z_belly': float(belly_z), 'support_t': float(support_t),
           'removal_offset_mm': (0.0, 0.0, travel), 'insertion_direction': (0.0, 0.0, -1.0),
           'transforms': {}, 'packs': {}, 'adapters': {}, 'clearance_packs': {}, 'removal_volumes': {}}
    for end, sign, body_end in (('front', 1.0, body_x[1]), ('rear', -1.0, body_x[0])):
        datum_x = body_end + sign * (END_PACK['shell_allowance_mm'] + END_PACK['wall_gap_mm'] + support_t + ah)
        # Front: RY(-90). Rear: RZ(180)*front. Both have determinant +1,
        # local +X -> world +Z and mating +Z -> inward; neither reflects a mesh.
        matrix = (0.0, 0.0, -sign, datum_x, 0.0, sign, 0.0, 0.0, 1.0, 0.0, 0.0, top_z)
        out['transforms'][end] = matrix
        out['packs'][end] = _placed_bounds(local, matrix)
        out['adapters'][end] = _placed_bounds(adapter, matrix)
        b = _placed_bounds(conservative, matrix)
        out['clearance_packs'][end] = b
        out['removal_volumes'][end] = (*b[:5], b[5] + travel)
    return out


PACK = pack_profile()
PACK.update(series=5, source='ENVELOPE: dated nominal outline, not mating CAD; ' + PACK_OUTLINE_SOURCE)
ADAPTER = dict(SELECTED_ADAPTER, L=100.0, W=72.0, H=25.0, mass_g=150.0, envelope=True,
               basis='ENVELOPE: unmeasured Azocek B0CDGR4Y8K; 100x72x25 mm reservation and 150 g assumed mass, not a specification',
               blocked_by='issue #20 / #193: measure and weigh selected Azocek adapter')
SERIES = 2 * PACK['series']
V_FULL, V_NOM, V_EMPTY = 4.1 * SERIES, 3.6 * SERIES, 3.0 * SERIES
R_PACK_OHM = 0.10  # existing electrical model; this placement change does not qualify a new supply
LEADS_SLOT = (-30.0, 24.0)  # retained spine-gap harness opening, not a selected electrical topology
PAD = {'lowest_leg_mm': 185.0, 'wheel_r': 127.0,
       'basis': 'Existing controller/firmware limits retained; historical bay-pad law is NOT adopted for end feet'}
END_FOOT = {'sit_leg_mm': 101.5, 'flange_t': 4.0, 'counterbore_depth': 1.5,
            'sole_t': 8.0, 'rib_t': 10.0, 'material': 'pa6-cf',
            'compliance_qualified': False, 'force_curve': None,
            'basis': 'Rigid WIP sit support at the existing mechanical leg-stop reference; no inherited crush-pad/drop acceptance'}


def z_belly():
    """Existing belly underside; the protected hip/leg datums do not move."""
    return -bp.z_spine_top() - bp.STOCK[bp.BELLY]['t']


def geometry(profile='DCB609'):
    """The canonical current end-pack placement, shared by CAD/layout/reports."""
    g = end_pack_geometry(profile)
    g['layout'] = 'front-rear-vertical-drop-in'
    g['foot_bottom_z'] = -END_FOOT['sit_leg_mm'] - PAD['wheel_r']
    g['holder_half_y'] = SUPPORTED_OUTLINE_MM[1] / 2 + 6.0
    g['base_top_z'] = g['z_belly']
    g['base_bottom_z'] = g['z_belly'] - g['support_t']
    return g


def foot_collision_boxes(end='front', g=None):
    """Conservative stock boxes for conditional rigid-foot simulation.

    Screw/tool holes are omitted from these boxes. This is not exact native
    contact geometry and carries no inherited drop/compliance qualification.
    """
    if end not in ('front', 'rear'):
        raise ValueError('Unknown end-pack holder')
    g = geometry() if g is None else g
    x1, hy = g['adapters']['front'][0], g['holder_half_y']
    top, bottom = g['base_bottom_z'], g['foot_bottom_z']
    ft, st, rt = END_FOOT['flange_t'], END_FOOT['sole_t'], END_FOOT['rib_t']
    boxes = [(94.0, x1, -hy, hy, top-ft, top), (120.0, x1, -hy, hy, bottom, bottom+st),
             (130.0, 160.0, -hy, -hy+rt, bottom+st, top-ft),
             (130.0, 160.0, hy-rt, hy, bottom+st, top-ft)]
    return boxes if end == 'front' else [(-b[1], -b[0], -b[3], -b[2], b[4], b[5]) for b in boxes]


def pack_boxes(profile='DCB609'):
    return geometry(profile)['packs']


def adapter_boxes():
    return geometry()['adapters']


def plate_holes(end):
    """Retain the existing known belly end lands; never invent Azocek holes."""
    if end not in ('front', 'rear'):
        raise ValueError('Unknown end-pack holder')
    sign = 1.0 if end == 'front' else -1.0
    return [(sign * x, y) for x in (102.0, 150.0) for y in (-30.0, 30.0)]


def summary():
    g = geometry()
    lowest = g['foot_bottom_z']
    return {'layout': 'front-rear-vertical-drop-in', 'pack': PACK['name'], 'profile': g['profile'],
            'reference_union_mm': g['reference_union_mm'], 'reference_union_measured': False,
            'config': f'{SERIES}S; existing electrical model unchanged',
            'v_full': round(V_FULL, 1), 'v_nominal': V_NOM, 'v_empty': V_EMPTY,
            'wh_rated': 2 * PACK['wh_rated'], 'packs_kg': 2 * PACK['mass_g'] / 1000,
            'pack_boxes_mm': g['packs'], 'adapter_boxes_mm': g['adapters'],
            'removal_offset_mm': g['removal_offset_mm'], 'removal_volumes_mm': g['removal_volumes'],
            'belly_z_mm': g['z_belly'], 'foot_bottom_z_mm': lowest,
            'sits_at_leg_mm': END_FOOT['sit_leg_mm'],
            'clearance_at_lowest_leg_mm': PAD['lowest_leg_mm'] + PAD['wheel_r'] + lowest,
            'clearance_at_300_mm': 300.0 + PAD['wheel_r'] + lowest,
            'adapter': dict(SELECTED_ADAPTER), 'support': dict(END_FOOT),
            'limits': ['Pack/adapter fit, latch and retention unmeasured',
                       'New support/camera/leg/removal clearances need native checks',
                       'Old belly-pad fall results do not qualify these rigid end feet']}


def _box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane('XY').box(x1-x0, y1-y0, z1-z0, centered=False).translate((x0, y0, z0))


def holder_part():
    """One-bend body-owned backing bracket, reused at the rear by a rigid rotation.

    Its base uses known belly PEM lands. The vertical face has no guessed bought
    adapter holes: that mounting interface remains explicitly unresolved.
    """
    from hardware.cad.body import body_sheet as sheet
    g = geometry()
    x0 = 94.0
    outer_x = g['adapters']['front'][0]
    width = 2 * g['holder_half_y']
    height = g['transforms']['front'][11] - g['base_bottom_z']
    features = [sheet.Feature('hole', 'base', (x-x0, y+width/2), 4.5,
                              note='M4 existing belly end lands; no bought-adapter pattern')
                for x, y in plate_holes('front')]
    return sheet.SheetPart('end_pack_holder', END_PACK['support_stock'], outer_x-x0, width,
                           flanges=[sheet.Flange('E', height)], features=features, qty=2,
                           note='Conditional WIP one-bend support; Azocek mounting/retention unresolved; verify loads and all clearances')


def place_holder(shape, end='front'):
    if end not in ('front', 'rear'):
        raise ValueError('Unknown end-pack holder')
    g = geometry()
    s = shape.translate((94.0, -g['holder_half_y'], g['base_bottom_z']))
    return s if end == 'front' else s.rotate((0, 0, 0), (0, 0, 1), 180)


def end_foot(end='front'):
    """Rigid WIP sit frame with a real load path and open middle, not old pad geometry.

    Counterbored top seats reuse the current M4x12 family. Bottom access holes
    leave the same bolt axes open for a tool; contact/drop strength is unverified.
    """
    if end not in ('front', 'rear'):
        raise ValueError('Unknown end-pack holder')
    g = geometry()
    x1, hy = g['adapters']['front'][0], g['holder_half_y']
    top, bottom = g['base_bottom_z'], g['foot_bottom_z']
    flange_t, sole_t = END_FOOT['flange_t'], END_FOOT['sole_t']
    s = _box(94.0, x1, -hy, hy, top-flange_t, top)
    s = s.union(_box(120.0, x1, -hy, hy, bottom, bottom+sole_t))
    for y0, y1 in [(-hy, -hy+END_FOOT['rib_t']), (hy-END_FOOT['rib_t'], hy)]:
        s = s.union(_box(130.0, 160.0, y0, y1, bottom+sole_t, top-flange_t))
    for x, y in plate_holes('front'):
        s = s.cut(cq.Workplane('XY', origin=(x, y, top-flange_t-1)).circle(2.25).extrude(flange_t+2))
        s = s.cut(cq.Workplane('XY', origin=(x, y, top-flange_t-1)).circle(4.0).extrude(END_FOOT['counterbore_depth']+1))
        if x >= 120.0:
            s = s.cut(cq.Workplane('XY', origin=(x, y, bottom-1)).circle(4.0).extrude(sole_t+2))
    return s if end == 'front' else s.rotate((0, 0, 0), (0, 0, 1), 180)


def end_parts():
    """Current structural candidates only; no old bay floor, doors or crush pads."""
    from hardware.cad.body.body_frame import Part
    sheet = holder_part()
    local = sheet.solid()
    out = {}
    for end in ('front', 'rear'):
        name = f'end_pack_holder_{end}'
        out[name] = Part(name, 'sheet', place_holder(local, end), sheet=sheet if end == 'front' else None,
                         local=local, material=sheet.s['material'], colour=(.66, .70, .75), note=sheet.note)
        name = f'end_foot_{end}'
        out[name] = Part(name, 'printed', end_foot(end), material=END_FOOT['material'], colour=(.22, .24, .27),
                         print_rotation=((0, 1, 0), 90),
                         note='Conditional rigid sit support; no compliance/drop or manufacturing qualification')
    return out
