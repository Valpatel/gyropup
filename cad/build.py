"""Gyropup's parts in CadQuery, from a design file: the chassis, the two leg modules, the head, face and sensor mounts.

    python cad/build.py [designs/default.json]

The leg modules are built on the mechanical interface standard (docs/mechanical-interfaces.md, cad/gmi.py, cad/leg.py)
from the motors' real drawings (catalog/interfaces.json). Link lengths, wheel size and the body size come from the
designer's layout (tools/derive.mjs), so every design gets parts that fit it.

Frame: x forward, y left, z up, origin on the hip axis (the same as the physics model). STEP files are in that frame
(legs at the zero pose); STL files are in print orientation on z = 0 for printed parts. The assembly (exports/asm_*.step)
is posed standing. Writes exports/<part>.step/.stl, exports/geometry-checks.json (the cad-agent parts file),
exports/mass-properties.json (CAD masses for sim/model.py), exports/mech-layout.json (the real stack and track for the
physics model) and exports/bom-mechanical.json (every part with its material and how it is made).

Made parts (qty):
  chassis (1)            3 mm 6061, bent (SendCutSend): floor, side walls with the HM pattern for the legs, front and
                         rear walls for the face and cameras, top flanges with the J501 box's M3 standoffs
  battery_cradle (1)     printed: rails and strap slots for the FLEXVOLT pack inside the chassis
  per leg, x2: yoke_bracket (PA6-CF), hip/knee motor plates and output adapters (CNC 6061), thigh and shin (6061 box),
                         knee crank (6061), wheel adapter (6061); bought: 61812 x2, 6001 x2, two M6 rod ends and a tube,
                         three spacer posts
  head_saddle, face, camera_cradle (2), lidar_hanger
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import cadquery as cq

from cadagent.geometry import export_print_stl
from cadagent.robot import printed_part_body

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
sys.path.insert(0, str(R))
import gmi  # noqa: E402
import leg  # noqa: E402

P = json.loads((R / 'cad/parameters.json').read_text())
OUT = R / 'exports'
SHEET = 3.0          # chassis sheet thickness (6061)


def derive(design_path: Path) -> dict:
    out = subprocess.run(['node', str(R / 'tools/derive.mjs'), str(design_path)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def chassis(L, S):
    """A 3 mm 6061 box: floor, two side walls carrying the legs (HM pattern: 6 x M6 tapped + 2 dowel holes each side,
    and the cable pass), front and rear walls (face and cameras), and inward top flanges where the J501 box stands on
    its four M3 standoffs. Bent from sheet by SendCutSend (floor + sides), front/rear plates riveted on."""
    T = L['tray']
    W, D = T['width'], T['depth']
    z0, z1 = L['trayBottom'], L['bodyBottom']
    H = z1 - z0
    box = cq.Workplane('XY').box(D, W, H).translate((0, 0, z0 + H / 2))
    inner = cq.Workplane('XY').box(D - 2 * SHEET, W - 2 * SHEET, H).translate((0, 0, z0 + SHEET + H / 2))
    c = box.cut(inner)
    # top flanges (12 mm inward) along the sides, for the J501 standoffs
    for s in (1, -1):
        c = c.union(cq.Workplane('XY').box(D, 12, SHEET).translate((0, s * (W / 2 - 6), z1 - SHEET / 2)))
    jb = P['j501_box']
    for (jx, jy) in jb['standoff_centers']:
        x, y = jb['depth'] / 2 - jy, jx - jb['width'] / 2
        c = c.cut(cq.Workplane('XY').circle(1.7).extrude(10).translate((x, y, z1 - 5)))
    # legs: HM pattern and cable passes on both sides
    for s in (1, -1):
        yw = s * W / 2
        for (x, z) in leg.hm_holes():
            c = c.cut(cq.Workplane('XZ', origin=(0, yw + s, 0)).center(x, z).circle(gmi.tap('M6') / 2).extrude(s * (SHEET + 2)))
        for (x, z) in leg.hm_dowels():
            c = c.cut(cq.Workplane('XZ', origin=(0, yw + s, 0)).center(x, z).circle(leg.STD['HM']['dowel_d'] / 2).extrude(s * (SHEET + 2)))
        for (x, z) in leg.CABLE_PASSES:
            c = c.cut(cq.Workplane('XZ', origin=(0, yw + s, 0)).center(x, z).circle(leg.STD['CP']['grommet_hole'] / 2).extrude(s * (SHEET + 2)))
    # front and rear: face, camera cradles (M4 tapped) and a window behind the face for the eyes and lights
    for xs, pts in ((D / 2, [(-45, 20), (45, 20), (-45, 60), (45, 60)]), (-D / 2, [(-20, 12), (20, 12)])):
        for (y, z) in pts:
            c = c.cut(cq.Workplane('YZ', origin=(xs + math.copysign(1, xs), 0, 0)).center(y, z0 + z).circle(gmi.tap('M4') / 2).extrude(-math.copysign(SHEET + 2, xs)))
    c = c.cut(cq.Workplane('YZ', origin=(D / 2 + 1, 0, 0)).center(0, z0 + 40).rect(70, 36).extrude(-(SHEET + 2)))
    # floor: lidar hanger (M4), lidar cable, drain/vent slots under the battery
    for (x, y) in [(-30, -30), (30, -30), (-30, 30), (30, 30)]:
        c = c.cut(cq.Workplane('XY').circle(gmi.tap('M4') / 2).extrude(10).translate((x, y, z0 - 1)))
    c = c.cut(cq.Workplane('XY').circle(8).extrude(10).translate((0, 0, z0 - 1)))
    for x in (-D / 4, D / 4):
        c = c.cut(cq.Workplane('XY').box(40, 8, 10).translate((x, 0, z0)))
    return c


def battery_cradle(L):
    """Printed rails on the chassis floor that locate the FLEXVOLT pack(s) in their adapters, with strap slots."""
    T = L['tray']
    W, D = T['width'], T['depth']
    z0 = L['trayBottom'] + SHEET
    n = (L.get('battery') or {}).get('packs', 1)
    bl, bw, bh = (L.get('battery') or {}).get('dims', (157, 92, 110))
    rails = None
    for k in range(n):
        yc = (k + 0.5) * (W - 2 * SHEET) / n - (W - 2 * SHEET) / 2
        for s in (1, -1):
            r = cq.Workplane('XY').box(bl, 6, 18).translate((0, yc + s * (bw / 2 + 3.2), z0 + 9))
            rails = r if rails is None else rails.union(r)
        stop = cq.Workplane('XY').box(6, bw + 12.4, 18).translate((-bl / 2 - 3, yc, z0 + 9))
        rails = rails.union(stop)
    for x in (-D / 4, D / 4):
        rails = rails.cut(cq.Workplane('XY').box(30, W, 4).translate((x, 0, z0 + 2)))       # strap channels
    return rails


def head_saddle(L):
    """Open frame on the J501 lid screws; turret ring raised 20 mm so the cooler grille keeps breathing."""
    jb = P['j501_box']
    top = L['bodyTop']
    t = 6.0
    ring_z = top + 20
    rails = cq.Workplane('XY')
    pts = [((jb['depth'] / 2 - jy), (jx - jb['width'] / 2)) for jx, jy in jb['standoff_centers']]
    frame = None
    for (x, y) in pts:
        dist, ang = math.hypot(x, y), math.degrees(math.atan2(y, x))
        arm = cq.Workplane('XY').box(dist, 14, t).translate((dist / 2, 0, t / 2)).rotate((0, 0, 0), (0, 0, 1), ang).translate((0, 0, top))
        foot = cq.Workplane('XY').circle(9).extrude(t).translate((x, y, top))
        frame = arm.union(foot) if frame is None else frame.union(arm).union(foot)
    ring = cq.Workplane('XY').circle(57).circle(30).extrude(t).translate((0, 0, ring_z))
    legs = None
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        leg = cq.Workplane('XY').circle(6).extrude(ring_z - top).translate((44 * math.cos(a), 44 * math.sin(a), top))
        legs = leg if legs is None else legs.union(leg)
    s = frame.union(legs).union(ring)
    for (x, y) in pts:
        s = s.cut(cq.Workplane('XY').circle(1.7).extrude(30).translate((x, y, top - 5)))
    for (x, y) in [(40, 40), (40, -40), (-40, 40), (-40, -40)]:
        s = s.cut(cq.Workplane('XY').circle(P['print']['insert_m4_pilot'] / 2).extrude(t + 2).translate((x * 0.71, y * 0.71, ring_z - 1)))
    return s


def face(L):
    """Eye window and headlight bosses, bolted to the tray front."""
    D = L['tray']['depth']
    z0 = L['trayBottom']
    plate = cq.Workplane('YZ').center(0, z0 + 40).rect(140, 76).extrude(5).translate((D / 2, 0, 0)).edges('|X').fillet(8)
    plate = plate.cut(cq.Workplane('YZ').center(0, z0 + 60).rect(53, 22).extrude(10).translate((D / 2 - 1, 0, 0)))         # DualEye
    for y in (-50, 50):
        boss = cq.Workplane('YZ').center(y, z0 + 30).circle(14).extrude(14).translate((D / 2, 0, 0))
        plate = plate.union(boss).cut(cq.Workplane('YZ').center(y, z0 + 30).circle(4.2).extrude(30).translate((D / 2 - 1, 0, 0)))  # M8 pod bolt
    for (y, z) in [(-45, 20), (45, 20), (-45, 60), (45, 60)]:
        plate = plate.cut(cq.Workplane('YZ').center(y, z0 + z).circle(2.25).extrude(20).translate((D / 2 - 1, 0, 0)))
    return plate


def camera_cradle(L, front=True):
    D = L['tray']['depth']
    z0 = L['trayBottom']
    sgn = 1 if front else -1
    w, h, d = P['camera']['d435']
    base = cq.Workplane('XY').box(30, w + 16, 5).translate((sgn * (D / 2 + 17), 0, z0 + 2.5))
    back = cq.Workplane('XY').box(5, 60, 30).translate((sgn * (D / 2 + 2.5), 0, z0 + 15))
    lip = cq.Workplane('XY').box(4, w + 16, 12).translate((sgn * (D / 2 + 33), 0, z0 + 6))
    c = base.union(back).union(lip)
    c = c.cut(cq.Workplane('XY').circle(3.4).extrude(10).translate((sgn * (D / 2 + 17), 0, z0 - 1)))      # 1/4-20
    for y in (-20, 20):
        c = c.cut(cq.Workplane('YZ').center(y, z0 + 12).circle(2.25).extrude(20).translate((sgn * (D / 2 - 5), 0, 0)))
    return c


def lidar_hanger(L):
    z0 = L['trayBottom']
    lp = P['lidar']
    disc = cq.Workplane('XY').circle(52).extrude(8).translate((0, 0, z0 - 8))
    disc = disc.cut(cq.Workplane('XY').circle(3.4).extrude(20).translate((0, 0, z0 - 15)))
    for x in (-lp['pin_spacing'] / 2, lp['pin_spacing'] / 2):
        disc = disc.cut(cq.Workplane('XY').circle(lp['pin_d'] / 2).extrude(5).translate((x, 12, z0 - 8.5)))
    for (x, y) in [(-30, -30), (30, -30), (-30, 30), (30, 30)]:
        disc = disc.cut(cq.Workplane('XY').circle(2.25).extrude(20).translate((x, y, z0 - 15)))
    disc = disc.cut(cq.Workplane('XY').rect(10, 40).extrude(20).translate((0, -32, z0 - 15)))             # cable notch
    return disc


# --------------------------------------------------------------------------- assembly and export



def build(design_path: Path):
    ev = derive(design_path)
    L = ev['layout']
    d = json.loads(Path(design_path).read_text())
    hip_id = d['parts']['leg_actuator']
    lparts, lmeta, lbought, S, assumed = leg.leg_parts(L, hip_id, hip_id, d['parts']['wheel_motor'])
    a, b = L['thigh'], L['shin']
    cr = leg.STD['PR']['crank_r']
    # standing pose for the assembly (60 % height), from the controller's own leg geometry
    from sim.controller import hip_for, knee_for
    am, bm = a / 1000, b / 1000
    lo, hi = math.radians(L['kneeMinDeg']), math.radians(L['kneeMaxDeg'])
    hmin, hmax = (math.sqrt(am * am + bm * bm - 2 * am * bm * math.cos(g)) for g in (lo, hi))
    hh = hmin + 0.6 * (hmax - hmin)
    hip_q, knee_q = hip_for(am, bm, hh), knee_for(am, bm, hh) - math.pi

    parts, meta, placed = {}, {}, {}

    def add(name, shape, material, qty, how, place=True):
        parts[name], meta[name] = shape, {'material': material, 'qty': qty, 'how': how}
        if place:
            placed[name] = shape

    add('chassis', chassis(L, S), 'al6061', 1, '3 mm 6061, laser cut and bent (SendCutSend); tapped M6/M5/M4/M3')
    add('battery_cradle', battery_cradle(L), 'pla', 1, 'printed PLA')
    add('head_saddle', head_saddle(L), 'pla', 1, 'printed PLA')
    add('face', face(L), 'pla', 1, 'printed PLA')
    add('camera_cradle', camera_cradle(L, True), 'pla', 2, 'printed PLA')
    placed['camera_cradle_rear'] = camera_cradle(L, False)
    add('lidar_hanger', lidar_hanger(L), 'pla', 1, 'printed PLA')
    # the legs: left as built, right mirrored; each part turned to the standing pose
    for name, shape in lparts.items():
        m = lmeta[name]
        add(name, shape, m['material'], 2, m['note'], place=False)
        posed = leg.pose(shape, name, hip_q, knee_q, a, cr)
        placed[f'{name}_l'] = posed
        placed[f'{name}_r'] = posed.mirror('XZ')

    rot = {'face': ((0, 1, 0), 90), 'head_saddle': ((1, 0, 0), 180), 'lidar_hanger': ((1, 0, 0), 180), 'camera_cradle': None,
           'yoke_bracket': ((1, 0, 0), -90), 'battery_cradle': None}
    materials = json.loads((R / 'catalog/materials.json').read_text())
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob('asm_*.step'):          # parts from an earlier build must not linger
        old.unlink()
    for old in OUT.glob('*.stl'):
        old.unlink()
    report, mass = {}, {}
    METAL_DENSITY = {'al6061': 2.70}
    for name, shape in parts.items():
        solid = shape.val() if hasattr(shape, 'val') else shape
        cq.exporters.export(solid, str(OUT / f'{name}.step'))
        mat = meta[name]['material']
        if mat in METAL_DENSITY:                # machined or cut: solid metal, no STL to print
            body, mrep = printed_part_body(solid, METAL_DENSITY[mat], wall_mm=500.0, infill=1.0, name=name)
            report[name] = {'cad_valid': solid.isValid(), 'solid_count': len(solid.Solids()), 'made': meta[name]['how'], 'qty': meta[name]['qty'], 'print': False}
        else:
            rep = export_print_stl(solid, OUT / f'{name}.stl', rotation=rot.get(name))
            rep.update(qty=meta[name]['qty'], made=meta[name]['how'], print=True)
            report[name] = rep
            body, mrep = printed_part_body(solid, materials[{'pa_cf': 'pa6-cf'}.get(mat, mat)]['density_g_cm3'], wall_mm=2.0, infill=0.4, name=name)
        mass[name] = {**mrep, 'material': mat, 'qty': meta[name]['qty'], 'com_m': list(body.com)}
    # bought parts at their real positions (envelopes; vendor STEP files stay local and are not exported)
    T, B = L['tray'], L['body']
    bought = {}
    bought['j501_box'] = cq.Workplane('XY').box(B['depth'], B['width'], B['height']).edges().fillet(6).translate((0, 0, L['bodyBottom'] + B['height'] / 2))
    if L.get('battery'):
        n, (bl, bw, bh) = L['battery']['packs'], L['battery']['dims']
        for i in range(n):
            y = (i + 0.5) * T['width'] / n - T['width'] / 2
            bought[f'battery_{i + 1}'] = cq.Workplane('XY').box(bl, bw, bh).edges('|X').fillet(8).translate((0, y, L['trayBottom'] + SHEET + 18 + bh / 2 - 12))
    env = {'hip_motor': gmi.place(_envelope(hip_id), (0, S.y['hip_out'], 0), (0, 1, 0)),
           'knee_motor': gmi.place(_envelope(hip_id), (0, S.y['knee_out'], 0), (0, -1, 0)),
           'posts': lbought['posts'], 'pushrod': lbought['pushrod'], 'wheel': lbought['wheel']}
    for name, shape in env.items():
        posed = leg.pose(shape, name, hip_q, knee_q, a, cr)
        bought[f'{name}_l'], bought[f'{name}_r'] = posed, posed.mirror('XZ')
    lz = L['trayBottom'] - 8 - 36
    bought['lidar'] = cq.Workplane('XY').circle(51.65).extrude(71.7).translate((0, 0, lz - 36))
    for name, x in (('camera_front', T['depth'] / 2 + 17), ('camera_rear', -(T['depth'] / 2 + 17))):
        bought[name] = cq.Workplane('XY').box(25, 90, 25).translate((x, 0, L['trayBottom'] + 5 + 12.5))
    for name, shape in bought.items():
        cq.exporters.export(shape.val(), str(OUT / f'asm_{name}.step'))
    for name, shape in placed.items():
        cq.exporters.export(shape.val() if hasattr(shape, 'val') else shape, str(OUT / f'asm_{name}.step'))

    export_link_meshes(design_path, L, S, parts, lparts, lbought, bought, placed, hip_id)
    (OUT / 'geometry-checks.json').write_text(json.dumps({k: v for k, v in report.items() if v.get('print')}, indent=1) + '\n')
    total = sum(m['mass_g'] * m['qty'] for m in mass.values())
    (OUT / 'mass-properties.json').write_text(json.dumps({'design': str(Path(design_path).resolve().relative_to(R)), 'parts': mass,
                                                          'made_total_g': round(total, 1), 'estimate': True,
                                                          'note': 'printed parts at 2 mm walls and 40 % infill; metal parts solid; weigh the real parts'}, indent=1) + '\n')
    (OUT / 'mech-layout.json').write_text(json.dumps({'design': str(Path(design_path).resolve().relative_to(R)), 'stack_mm': S.y, 'track_mm': S.track,
                                                      'notes': S.notes, 'assumed_interfaces': assumed,
                                                      'hip_y_mm': sum(S.y['thigh']) / 2, 'wheel_y_mm': S.y['wheel_centre'],
                                                      'min_knee_deg': S.y.get('min_knee_deg')}, indent=1) + '\n')
    (OUT / 'bom-mechanical.json').write_text(json.dumps({n: {**meta[n], 'mass_g_each': round(mass[n]['mass_g'], 1)} for n in parts}, indent=1) + '\n')
    print(f"{len(parts)} part types, {sum(m['qty'] for m in meta.values())} parts, {total / 1000:.2f} kg made (estimate); track {S.track:.0f} mm")
    for n in S.notes:
        print('  note:', n)
    for name, rep in report.items():
        print(f"  {name:20} x{rep['qty']}  {meta[name]['material']:7} valid={rep['cad_valid']} solids={rep['solid_count']}  {meta[name]['how']}")
    return report


# Which link each leg part moves with (left leg, zero pose); everything else is fixed to the body.
LEG_LINK = {'thigh': 'thigh', 'hip_output_adapter': 'thigh', 'shin': 'shin', 'wheel_adapter': 'shin',
            'knee_crank': 'crank', 'knee_output_adapter': 'crank', 'pushrod': 'rod', 'wheel': 'wheel'}
VIEW_SKIP = {'j501_box', 'lidar', 'camera_front', 'camera_rear'}       # the 3D page draws these itself (FOV, eyes)


def export_link_meshes(design_path, L, S, parts, lparts, lbought, bought, placed, hip_id):
    """Meshes of every part grouped by the link it moves with, for the 3D simulator: exports/links/*.stl (robot frame,
    millimetres, legs at the zero pose, left leg only: the page mirrors it) and exports/links/manifest.json. The page
    turns the thigh by the hip angle, the shin by the knee angle about the knee pin, the wheel by its spin, the crank
    by hip + knee, and keeps the push-rod parallel to the thigh, from the physics run's joint angles."""
    import re
    colors = {}
    try:
        import yaml
        colors = ((yaml.safe_load((R / 'cad-agent.yaml').read_text()).get('cad') or {}).get('view') or {}).get('colors', {})
    except Exception:
        pass
    col = lambda n: colors.get(n) or colors.get(re.sub(r'_(l|r|\d+)$', '', n)) or colors.get(n.split('_')[0]) or '#9aa3ad'
    d = OUT / 'links'
    d.mkdir(exist_ok=True)
    for old in d.glob('*.stl'):
        old.unlink()
    links = {k: [] for k in ('body', 'thigh', 'shin', 'wheel', 'crank', 'rod')}

    def put(link, name, shape, side):
        f = f'{name}.stl'
        cq.exporters.export(shape.val() if hasattr(shape, 'val') else shape, str(d / f), tolerance=0.4, angularTolerance=0.3)
        links[link].append({'file': f, 'name': name, 'color': col(name), 'side': side})

    for name, shape in lparts.items():                         # left leg, zero pose
        put(LEG_LINK.get(name, 'body'), name, shape, 'l')
    for name in ('posts', 'pushrod', 'wheel'):
        put(LEG_LINK.get(name, 'body'), name, lbought[name], 'l')
    env = {'hip_motor': gmi.place(_envelope(hip_id), (0, S.y['hip_out'], 0), (0, 1, 0)),
           'knee_motor': gmi.place(_envelope(hip_id), (0, S.y['knee_out'], 0), (0, -1, 0))}
    for name, shape in env.items():
        put('body', name, shape, 'l')
    for name in ('chassis', 'battery_cradle', 'face', 'lidar_hanger', 'head_saddle'):
        put('body', name, parts[name], None)
    put('body', 'camera_cradle_front', parts['camera_cradle'], None)
    put('body', 'camera_cradle_rear', placed['camera_cradle_rear'], None)
    for name, shape in bought.items():
        if name.startswith('battery'):
            put('body', name, shape, None)
    (d / 'manifest.json').write_text(json.dumps({
        'design': str(Path(design_path).resolve().relative_to(R)), 'units': 'mm',
        'frame': 'robot: x forward, y left, z up, origin on the hip axis; legs at the zero pose (hanging straight down)',
        'thigh_mm': L['thigh'], 'shin_mm': L['shin'], 'crank_r_mm': leg.STD['PR']['crank_r'], 'mirror': 'side l parts are mirrored (y -> -y) for the right leg',
        'links': links}, indent=1) + '\n')


def _envelope(part_id):
    """A motor's stepped envelope (never the vendor STEP, which stays local)."""
    mi = gmi.motor_interface(part_id)
    od, Lm = mi['od'] or 100.0, mi['length'] or 50.0
    off = mi['output']['face_offset'] if mi['output'] else 0.0
    front = mi['case']['spigot_d'] or od * 0.7
    return gmi._cyl(od / 2, -Lm, -off).union(gmi._cyl(front / 2, -off, 0.0))


if __name__ == '__main__':
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else R / 'designs/default.json')
