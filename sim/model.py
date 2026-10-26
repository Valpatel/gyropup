"""Design → robot model: MuJoCo (MJCF) and URDF, with masses, inertias and actuator limits from the design's parts.

    python -m sim.model designs/default.json      # writes build/sim/<design>/robot.xml, robot.urdf, model.json

The design is evaluated with the designer's own model (tools/derive.mjs), so masses, the layout and the parts list are
exactly what the designer shows. Every BOM line becomes mass on a link:

- base (hip-axis frame): compute box, battery, sensors, electronics, the four leg actuators stacked at the hips, the
  body's printed parts and the hardware allowance;
- thigh and shin (each side): printed links, wheel mounts, and the stator half of the hub motor;
- wheel (each side): the spinning half of the hub motor (rotor and tyre) and any printed hub and tyre.

URDF frame: x forward, y left, z up, origin on the hip axis. The four-bar knee drive is modelled as its equivalent
serial chain (DDT models the Diablo the same way). Numbers marked "estimate" in model.json need a real part to check.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

from cadagent import robot as rb

R = Path(__file__).resolve().parents[1]
G = 9.81
M = 0.001
ROTOR_SHARE = 0.6        # estimate: share of a hub motor's mass that spins (outer rotor + tyre)
LEG_HARDWARE_SHARE = 0.2  # estimate: share of the hardware allowance carried by the legs (bearings, pins)


def derive(design_path: Path) -> dict:
    out = subprocess.run(['node', str(R / 'tools/derive.mjs'), str(design_path)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def load_catalog() -> dict:
    idx = json.loads((R / 'catalog/index.json').read_text())
    cat = {}
    for f in idx['files']:
        for it in json.loads((R / 'catalog' / f).read_text()):
            cat[it['id']] = it
    return cat


def part(design: dict, catalog: dict, slot: str):
    ref = design['parts'].get(slot)
    if isinstance(ref, dict):
        return ref
    return catalog.get(ref) if ref else None


def actuator_limits(item: dict, bus_v: float, kind: str) -> dict:
    """Peak torque, speed limit (rad/s at the bus voltage), and reflected rotor inertia (estimate)."""
    s = item.get('specs', {})
    peak = s.get('peak_torque_nm') or s.get('rated_torque_nm') or 1.0
    rated = s.get('rated_torque_nm') or peak / 3
    rpm = s.get('no_load_speed_rpm')
    vnom = s.get('voltage_nominal_v')
    if rpm and vnom and bus_v:
        rpm = rpm * bus_v / vnom
    omega = (rpm or 300) * 2 * math.pi / 60
    est = {}
    if kind == 'leg':
        gear = s.get('gear_ratio') or 9
        mass = (s.get('mass_g') or 800) * M
        d = (s.get('diameter_mm') or 100) * M
        rotor = 0.5 * (0.35 * mass) * (0.35 * d) ** 2          # rotor ~35 % of mass at ~35 % of the case diameter
        armature = s.get('rotor_inertia_kg_m2', rotor) * gear ** 2
        est['armature'] = 'rotor_inertia_kg_m2' not in s
    else:
        armature = 0.0                                          # a hub motor's rotor is part of the wheel link
    return {'peak_nm': peak, 'rated_nm': rated, 'omega_max': omega, 'rpm_at_bus': rpm, 'armature': armature, 'estimates': est}


def cad_masses(design_path: Path):
    """Printed part masses from the CAD (exports/mass-properties.json, written by cad/build.py) when they were built
    from this design; None otherwise. {part: (kg each, qty)}."""
    f = R / 'exports' / 'mass-properties.json'
    if not f.exists():
        return None
    mp = json.loads(f.read_text())
    if (R / mp.get('design', '')).resolve() != Path(design_path).resolve():
        return None
    return {n: (v['mass_g'] / 1000, v['qty']) for n, v in mp['parts'].items()}


def build(design_path: Path, out_dir: Path | None = None) -> dict:
    design_path = Path(design_path).resolve()
    design = json.loads(design_path.read_text())
    ev = derive(design_path)
    catalog = load_catalog()
    L = ev['layout']
    out_dir = Path(out_dir or R / 'build' / 'sim' / design_path.stem)
    out_dir.mkdir(parents=True, exist_ok=True)

    hipY, wheelY = L['hipX'] * M, L['wheelX'] * M
    a, b, r = L['thigh'] * M, L['shin'] * M, L['wheelR'] * M
    Bd, Bw, Bh = L['body']['depth'] * M, L['body']['width'] * M, L['body']['height'] * M
    trayZ = (L['trayBottom'] + L['trayH'] / 2) * M
    bodyZ = (L['bodyBottom'] + L['body']['height'] / 2) * M
    top = L['bodyTop'] * M

    base, thigh, shin, wheel = [], [], [], []
    tail_link1, tail_arm = [], []          # the tail: wag-motor link at the pivot, and the arm with its shoe
    T = L.get('tail')
    if T:
        tpx, tpz, tlen = T['pivotX'] * M, T['pivotZ'] * M, T['length'] * M
        yoff = T['yawOffset'] * M          # pitch axis to the wag axis
        arm = tlen - yoff                  # wag axis to the shoe's far end
        dz = T['tubeDrop'] * M             # the tube runs this far below the pitch axis (clamped under the wag motor)
    turret_mass = 0.0
    notes = []
    bus_v = ev['power'].get('bus_v', [None, None])
    bus_nom = part(design, catalog, 'battery')['specs'].get('voltage_nominal_v') if part(design, catalog, 'battery') else None

    def add_tail_print(pid, kg):
        if pid == 'tail_mount':
            base.append(rb.box_body(kg, (0.1, 0.07, 0.1), center=(tpx, 0, tpz), name=pid))
        elif pid == 'tail_yoke':
            tail_link1.append(rb.box_body(kg, (yoff, 0.06, 0.04), center=(-yoff / 2, 0, 0.02), name=pid))
        elif pid == 'tail_clamp':
            tail_arm.append(rb.box_body(kg, (0.05, 0.04, 0.04), center=(-0.03, 0, -dz), name=pid))
        else:
            tail_arm.append(rb.point_body(kg, (-arm + T['shoeR'] * M, 0, -dz), name=pid))

    for line in ev['lines']:
        g = (line.get('mass_g') or 0) * line['qty'] * M
        if g <= 0:
            continue
        slot = line['slot']
        item = part(design, catalog, slot) if slot not in ('printed', 'hardware') else None
        dims = (item or {}).get('specs', {}).get('dimensions_mm')
        if slot == 'leg_actuator':
            each = g / line['qty']
            for side in (1, -1):
                for k in (0, 1):
                    y = side * (Bw / 2 + L['motorL'] * M * (0.25 + 0.5 * k))
                    base.append(rb.cylinder_body(each, L['motorD'] * M / 2, L['motorL'] * M / 2, axis='y', center=(0, y, 0), name='leg actuator'))
        elif slot == 'wheel_motor':
            each = g / 2
            for side in (1, -1):
                wheel.append((side, rb.cylinder_body(each * ROTOR_SHARE, r, L['wheelW'] * M, axis='y', hollow_radius=0.6 * r, name='hub rotor + tyre')))
                shin.append((side, rb.cylinder_body(each * (1 - ROTOR_SHARE), 0.5 * r, L['wheelW'] * M, axis='y',
                                                    center=(0, side * (wheelY - hipY), -b), name='hub stator')))
            notes.append(f'hub motor split {ROTOR_SHARE:.0%} spinning / {1 - ROTOR_SHARE:.0%} stator (estimate)')
        elif slot == 'compute':
            base.append(rb.box_body(g, (Bd, Bw, Bh), center=(0, 0, bodyZ), name='compute box'))
        elif slot == 'battery':
            s = item['specs']
            size = tuple((s.get(k) or d) * M for k, d in (('length_mm', L['body']['depth']), ('width_mm', L['body']['width'] * 0.6), ('height_mm', L['trayH'] * 0.8)))
            base.append(rb.box_body(g, size, center=(0, 0, trayZ), name='battery'))
        elif slot == 'lidar':
            mount = L['lidarMount']
            z = (top + 0.008 + 0.036) if mount == 'top' else (top + 0.05 + 0.036) if mount == 'mast' else (L['trayBottom'] * M - 0.004 - 0.036)
            base.append(rb.cylinder_body(g, 0.0515, 0.0717, axis='z', center=(0, 0, z), name='lidar'))
        elif slot in ('depth_front', 'depth_rear'):
            x = (Bd / 2 + 0.013) * (1 if slot == 'depth_front' else -1)
            base.append(rb.box_body(g, (0.025, 0.09, 0.025), center=(x, 0, (L['bodyBottom'] + 14) * M), name=slot))
        elif slot == 'printed' and cad_masses(design_path):
            # the real printed parts: legs from the CAD links, everything else on the body
            for name, (kg, qty) in cad_masses(design_path).items():
                if name == 'thigh':
                    for side in (1, -1):
                        thigh.append((side, rb.box_body(kg, (L['linkD'] * M, L['linkW'] * M, a), center=(0, 0, -a / 2), name='thigh (CAD)')))
                elif name == 'shin':
                    for side in (1, -1):
                        shin.append((side, rb.box_body(kg, (L['linkD'] * M, L['linkW'] * M, b), center=(0, 0, -b / 2), name='shin (CAD)')))
                elif name == 'pushrod':          # half rides with each link it joins
                    for side in (1, -1):
                        thigh.append((side, rb.point_body(kg / 2, (0, 0, -a / 2), name='pushrod (CAD)')))
                        shin.append((side, rb.point_body(kg / 2, (0, 0, 0), name='pushrod (CAD)')))
                elif name.startswith('tail_') and T:
                    add_tail_print(name, kg * qty)
                elif name == 'knee_crank':       # on the knee motor's output, at the hip axis
                    for side in (1, -1):
                        thigh.append((side, rb.point_body(kg, (0, 0, 0), name='knee crank (CAD)')))
                else:
                    base.append(rb.box_body(kg * qty, (Bd, Bw, 0.02), center=(0, 0, trayZ), name=f'{name} (CAD)'))
            for p in ev['parts']:                # printed wheel and tail parts are not in the CAD yet
                if p['id'].startswith('tail_') and p['id'] not in cad_masses(design_path):
                    add_tail_print(p['id'], p['mass_g'] * p['qty'] * M)
                if p['id'] in ('wheel_hub', 'tyre'):
                    pg = p['mass_g'] * p['qty'] * M
                    for side in (1, -1):
                        wheel.append((side, rb.cylinder_body(pg / 2, r, L['wheelW'] * M, axis='y', hollow_radius=0.5 * r, name=p['id'])))
            notes.append('printed part masses from the CAD (exports/mass-properties.json)')
        elif slot == 'printed':
            for p in ev['parts']:
                pg = p['mass_g'] * p['qty'] * M
                if p['id'] == 'thigh':
                    for side in (1, -1):
                        thigh.append((side, rb.box_body(pg / 2, (L['linkD'] * M, L['linkW'] * M, a), center=(0, 0, -a / 2), name='thigh')))
                elif p['id'] in ('shin', 'wheel_mount'):
                    for side in (1, -1):
                        z = -b / 2 if p['id'] == 'shin' else -b
                        shin.append((side, rb.box_body(pg / 2, (L['linkD'] * M, L['linkW'] * M, b if p['id'] == 'shin' else 0.03), center=(0, 0, z), name=p['id'])))
                elif p['id'] in ('wheel_hub', 'tyre'):
                    for side in (1, -1):
                        wheel.append((side, rb.cylinder_body(pg / 2, r, L['wheelW'] * M, axis='y', hollow_radius=0.5 * r, name=p['id'])))
                elif p['id'].startswith('tail_'):
                    add_tail_print(p['id'], pg)
                elif p['id'] == 'lidar_crown':
                    base.append(rb.cylinder_body(pg, 0.066, 0.05, axis='z', center=(0, 0, top + 0.03), hollow_radius=0.06, name='crown'))
                else:
                    base.append(rb.box_body(pg, (Bd, Bw, 0.02), center=(0, 0, bodyZ - Bh / 2), name=p['id']))
        elif slot in ('tail_pitch', 'tail_lock') and T:     # on the body, at the tail pivot
            base.append(rb.cylinder_body(g, T['pitchD'] * M / 2, T['pitchL'] * M, axis='y', center=(tpx, 0, tpz), name=slot))
        elif slot == 'tail_yaw' and T:                         # rides on the pitch output, at the pivot
            tail_link1.append(rb.cylinder_body(g, T['yawD'] * M / 2, T['yawL'] * M, axis='z', center=(-yoff, 0, 0), name=slot))
        elif slot == 'tail_tube' and T:
            tail_arm.append(rb.cylinder_body(g, T['tubeD'] * M / 2, arm - 0.04, axis='x', center=(-arm / 2, 0, -dz), hollow_radius=T['tubeD'] * M / 2 - 0.001, name='tail tube'))
        elif slot == 'head_payload':
            turret_mass = g          # becomes the turret's pan and tilt links below
        elif slot == 'hardware':
            legs = g * LEG_HARDWARE_SHARE
            base.append(rb.point_body(g - legs, (0, 0, trayZ), name='hardware'))
            for side in (1, -1):
                thigh.append((side, rb.point_body(legs / 4, (0, 0, -a / 2), name='hardware')))
                shin.append((side, rb.point_body(legs / 4, (0, 0, -b / 2), name='hardware')))
        else:
            size = tuple(v * M for v in dims) if dims and all(dims) else None
            base.append(rb.box_body(g, size, center=(0, 0, trayZ), name=slot) if size else rb.point_body(g, (0, 0, trayZ), name=slot))

    leg_act = part(design, catalog, 'leg_actuator')
    wheel_act = part(design, catalog, 'wheel_motor')
    legl = actuator_limits(leg_act, bus_nom, 'leg')
    wl = actuator_limits(wheel_act, bus_nom, 'wheel')

    # visuals: simple coloured shapes until the CAD meshes exist
    hexc = (design.get('character') or {}).get('color', '#f5b82e').lstrip('#')
    body_rgba = tuple(int(hexc[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (1.0,)
    leg_rgba = tuple(c * 0.85 for c in body_rgba[:3]) + (1.0,)
    DARK, STEEL, TYRE, LENS = (0.18, 0.2, 0.24, 1), (0.55, 0.57, 0.6, 1), (0.1, 0.1, 0.12, 1), (0.33, 0.9, 1.0, 1)
    V = rb.Visual
    base_vis = [V(kind='box', size=(Bd - 0.004, Bw - 0.004, (L['trayH'] - 1) * M), xyz=(0, 0, trayZ - 0.0005), rgba=DARK),
                V(kind='box', size=(Bd, Bw, Bh), xyz=(0, 0, bodyZ), rgba=body_rgba)]
    for side in (1, -1):
        base_vis.append(V(kind='cylinder', size=(L['motorD'] * M / 2, L['motorL'] * M - 0.003), xyz=(0, side * (Bw / 2 + 0.003 + L['motorL'] * M / 2), 0),
                          rpy=(math.pi / 2, 0, 0), rgba=STEEL))
    if part(design, catalog, 'lidar'):
        mount = L['lidarMount']
        z = (top + 0.044) if mount == 'top' else (top + 0.086) if mount == 'mast' else (L['trayBottom'] * M - 0.04)
        base_vis.append(V(kind='cylinder', size=(0.0515, 0.0717), xyz=(0, 0, z), rgba=DARK))
    for slot, sign in (('depth_front', 1), ('depth_rear', -1)):
        if part(design, catalog, slot):
            base_vis.append(V(kind='box', size=(0.025, 0.09, 0.025), xyz=(sign * (Bd / 2 + 0.013), 0, (L['bodyBottom'] + 14) * M), rgba=DARK))
    base_vis.append(V(kind='box', size=(0.11, 0.11, 0.006), xyz=(0, 0, top + 0.003), rgba=DARK))   # head plate
    if part(design, catalog, 'eyes'):
        for s_ in (1, -1):
            base_vis.append(V(kind='cylinder', size=(0.0095, 0.004), xyz=(Bd / 2 + 0.002, s_ * 0.0155, (L['bodyBottom'] + 0.62 * L['body']['height']) * M),
                              rpy=(0, math.pi / 2, 0), rgba=LENS))

    knee_lo = math.radians(L['kneeMinDeg']) - math.pi
    knee_hi = math.radians(L['kneeMaxDeg']) - math.pi
    links = [rb.Link('base', rb.combine(base, 'base'), base_vis, [
        rb.Collision('box', (Bd, Bw, (L['bodyTop'] - L['trayBottom']) * M), xyz=(0, 0, (L['bodyTop'] + L['trayBottom']) / 2 * M), contype=2, conaffinity=1),
    ])]
    if part(design, catalog, 'lidar') and L['lidarMount'] != 'under':
        links[0].collisions.append(rb.Collision('cylinder', (0.068, 0.09), xyz=(0, 0, top + 0.05), contype=2, conaffinity=1))
    joints, motors = [], []
    for side, tag in ((1, 'l'), (-1, 'r')):
        th = rb.combine([bd for s, bd in thigh if s == side], f'thigh_{tag}')
        sh = rb.combine([bd for s, bd in shin if s == side], f'shin_{tag}')
        wh = rb.combine([bd for s, bd in wheel if s == side], f'wheel_{tag}')
        links += [
            rb.Link(f'thigh_{tag}', th, [V(kind='box', size=(L['linkD'] * M, L['linkW'] * M, a), xyz=(0, 0, -a / 2), rgba=leg_rgba)], [rb.Collision('box', (L['linkD'] * M, L['linkW'] * M, a), xyz=(0, 0, -a / 2), contype=4, conaffinity=1)]),
            rb.Link(f'shin_{tag}', sh, [V(kind='box', size=(L['linkD'] * M, L['linkW'] * M, b), xyz=(0, 0, -b / 2), rgba=leg_rgba)], [rb.Collision('box', (L['linkD'] * M, L['linkW'] * M, b), xyz=(0, 0, -b / 2), contype=4, conaffinity=1)]),
            rb.Link(f'wheel_{tag}', wh, [V(kind='cylinder', size=(r, L['wheelW'] * M), rpy=(math.pi / 2, 0, 0), rgba=TYRE),
                                         V(kind='cylinder', size=(0.62 * r, L['wheelW'] * M + 0.008), rpy=(math.pi / 2, 0, 0), rgba=STEEL),
                                         V(kind='box', size=(1.1 * r, L['wheelW'] * M + 0.016, 0.012), rgba=DARK)], [rb.Collision('cylinder', (r, L['wheelW'] * M), rpy=(math.pi / 2, 0, 0), contype=4, conaffinity=1, friction=(1.0, 0.02, 0.001))]),
        ]
        joints += [
            rb.Joint(f'hip_{tag}', 'revolute', 'base', f'thigh_{tag}', xyz=(0, side * hipY, 0), axis=(0, 1, 0), lower=-0.6, upper=2.2,
                     effort=legl['peak_nm'], velocity=legl['omega_max'], damping=0.05, friction=0.05, armature=legl['armature']),
            rb.Joint(f'knee_{tag}', 'revolute', f'thigh_{tag}', f'shin_{tag}', xyz=(0, 0, -a), axis=(0, 1, 0), lower=knee_lo, upper=knee_hi,
                     effort=legl['peak_nm'], velocity=legl['omega_max'], damping=0.05, friction=0.05, armature=legl['armature']),
            rb.Joint(f'wheel_{tag}', 'continuous', f'shin_{tag}', f'wheel_{tag}', xyz=(0, side * (wheelY - hipY), -b), axis=(0, 1, 0),
                     effort=wl['peak_nm'], velocity=wl['omega_max'], damping=0.01, friction=0.02),
        ]
        motors += [rb.Motor(f'hip_{tag}', legl['peak_nm']), rb.Motor(f'knee_{tag}', legl['peak_nm']), rb.Motor(f'wheel_{tag}', wl['peak_nm'])]

    # the turret (head payload): a pan ring and a tilting launcher with a muzzle, each on a servo-class motor
    turret = None
    if turret_mass > 0:
        hp = design.get('head_payload', {})
        pan_m, tilt_m = 0.4 * turret_mass, 0.6 * turret_mass
        pan_link = rb.Link('turret_pan', rb.cylinder_body(pan_m, 0.05, 0.03, axis='z', center=(0, 0, 0.015)),
                           [V(kind='cylinder', size=(0.05, 0.03), xyz=(0, 0, 0.015), rgba=DARK),
                            V(kind='box', size=(0.04, 0.008, 0.06), xyz=(0, 0.052, 0.045), rgba=body_rgba),
                            V(kind='box', size=(0.04, 0.008, 0.06), xyz=(0, -0.052, 0.045), rgba=body_rgba)], [])
        tilt_link = rb.Link('turret_tilt', rb.box_body(tilt_m, (0.15, 0.09, 0.06), center=(0.02, 0, 0)),
                            [V(kind='box', size=(0.15, 0.092, 0.056), xyz=(0.02, 0, 0), rgba=body_rgba),
                             V(kind='cylinder', size=(0.009, 0.08), xyz=(0.115, 0, 0), rpy=(0, math.pi / 2, 0), rgba=STEEL),
                             V(kind='cylinder', size=(0.011, 0.012), xyz=(0.152, 0, 0), rpy=(0, math.pi / 2, 0), rgba=(1, 0.16, 0.43, 1)),
                             V(kind='cylinder', size=(0.042, 0.034), xyz=(-0.025, 0, 0.046), rgba=(0.23, 0.25, 0.28, 1))],
                            [rb.Collision('box', (0.15, 0.09, 0.06), xyz=(0.02, 0, 0), contype=2, conaffinity=1)],
                            sites=[('muzzle', (0.165, 0, 0))])
        links += [pan_link, tilt_link]
        joints += [
            rb.Joint('turret_pan', 'revolute', 'base', 'turret_pan', xyz=(0, 0, top + 0.006), axis=(0, 0, 1), lower=-3.1, upper=3.1,
                     effort=5.0, velocity=10.0, damping=0.05, friction=0.02, armature=0.002),
            rb.Joint('turret_tilt', 'revolute', 'turret_pan', 'turret_tilt', xyz=(0, 0, 0.058), axis=(0, 1, 0), lower=-0.05, upper=0.45,
                     effort=3.0, velocity=6.0, damping=0.05, friction=0.02, armature=0.001),
        ]
        motors += [rb.Motor('turret_pan', 5.0), rb.Motor('turret_tilt', 3.0)]
        turret = {'pan_effort_nm': 5.0, 'tilt_effort_nm': 3.0, 'magazine': hp.get('magazine_shots', 24), 'dart_speed_mps': 24.0,
                  'dart_mass_kg': 0.001, 'tilt_positive': 'barrel down', 'estimates': 'pan/tilt torques and the 40/60 mass split'}

    # the tail: pitch (RS-06 class) at the back of the tray, wag (yaw) right after it, a carbon arm and a skid shoe.
    # Positive pitch raises the tail; the arm points backwards (-x) at zero.
    tail = None
    if T:
        tpitch, tyaw = part(design, catalog, 'tail_pitch'), part(design, catalog, 'tail_yaw')
        lp, ly = actuator_limits(tpitch, bus_nom or 48, 'leg'), actuator_limits(tyaw, bus_nom or 48, 'leg')
        lock = part(design, catalog, 'tail_lock')
        shoe_r = T['shoeR'] * M
        links += [
            rb.Link('tail_pitch', rb.combine(tail_link1, 'tail_pitch') if tail_link1 else rb.point_body(0.05),
                    [V(kind='cylinder', size=(T['yawD'] * M / 2, T['yawL'] * M), xyz=(-yoff, 0, 0), rgba=STEEL),
                     V(kind='box', size=(yoff, 0.04, 0.006), xyz=(-yoff / 2, 0, T['yawL'] * M / 2 + 0.003), rgba=STEEL)], []),
            rb.Link('tail', rb.combine(tail_arm, 'tail'),
                    [V(kind='cylinder', size=(T['tubeD'] * M / 2, arm - shoe_r), xyz=(-(arm - shoe_r) / 2, 0, -dz), rpy=(0, math.pi / 2, 0), rgba=DARK),
                     V(kind='box', size=(0.04, 0.034, dz), xyz=(0, 0, -dz / 2), rgba=leg_rgba),
                     V(kind='sphere', size=(shoe_r,), xyz=(-arm + shoe_r, 0, -dz), rgba=leg_rgba)],
                    [rb.Collision('cylinder', (T['tubeD'] * M / 2 + 0.002, arm - 0.06), xyz=(-(arm - 0.06) / 2 - 0.03, 0, -dz), rpy=(0, math.pi / 2, 0), contype=4, conaffinity=1),
                     rb.Collision('sphere', (shoe_r,), xyz=(-arm + shoe_r, 0, -dz), contype=4, conaffinity=1, friction=(0.7, 0.02, 0.001))],
                    sites=[('tail_tip', (-arm + shoe_r, 0, -dz))]),
        ]
        joints += [
            rb.Joint('tail_pitch', 'revolute', 'base', 'tail_pitch', xyz=(tpx, 0, tpz), axis=(0, 1, 0), lower=-1.75, upper=0.95,
                     effort=lp['peak_nm'], velocity=lp['omega_max'], damping=0.05, friction=0.05, armature=lp['armature']),
            rb.Joint('tail_yaw', 'revolute', 'tail_pitch', 'tail', xyz=(-yoff, 0, 0), axis=(0, 0, 1), lower=-0.7, upper=0.7,
                     effort=ly['peak_nm'], velocity=ly['omega_max'], damping=0.03, friction=0.03, armature=ly['armature']),
        ]
        motors += [rb.Motor('tail_pitch', lp['peak_nm']), rb.Motor('tail_yaw', ly['peak_nm'])]
        tail = {'pitch': {k: v for k, v in lp.items()}, 'yaw': {k: v for k, v in ly.items()}, 'length_m': tlen, 'shoe_r_m': shoe_r,
                'reach_m': tlen - shoe_r, 'yaw_offset_m': yoff, 'drop_m': dz,
                'pivot_m': [tpx, 0, tpz], 'lock_hold_nm': (lock or {}).get('specs', {}).get('hold_torque_nm'),
                'lock_tooth_rad': math.radians((lock or {}).get('specs', {}).get('tooth_deg', 4)),
                'positive': 'tail up', 'parts': {'pitch': tpitch['id'], 'yaw': tyaw['id'], 'lock': (lock or {}).get('id')}}

    name = design.get('name', 'gyropup')
    rb.write_mjcf(out_dir / 'robot.xml', 'gyropup', links, joints, motors, floating=True, floor=True, timestep=0.001,
                  imu_link='base', comment=f'{name}: generated by sim/model.py from {design_path.name}')
    rb.write_urdf(out_dir / 'robot.urdf', 'gyropup', links, joints, comment=f'{name}: generated by sim/model.py from {design_path.name}')
    urdf_check = rb.check_urdf(out_dir / 'robot.urdf')
    total = sum(l.body.mass for l in links)
    cad = cad_masses(design_path)
    est_printed = sum(p['mass_g'] * p['qty'] for p in ev['parts']          # the estimates the CAD replaced
                      if p['id'] not in ('wheel_hub', 'tyre') and (not p['id'].startswith('tail_') or p['id'] in (cad or {}))) * M
    cad_delta = (sum(kg * q for kg, q in cad.values()) - est_printed) if cad else 0.0   # CAD replaces the estimate
    info = {
        'design': str(design_path.relative_to(R)), 'name': name, 'total_mass_kg': total,
        'designer_mass_kg': ev['mass']['total_kg'], 'printed_cad_delta_kg': round(cad_delta, 3),
        'mass_reconciles': abs(total - ev['mass']['total_kg'] - cad_delta) < 0.01 * ev['mass']['total_kg'],
        'links': {l.name: l.body.as_dict() for l in links},
        'leg_actuator': {k: v for k, v in legl.items()}, 'wheel_motor': {k: v for k, v in wl.items()},
        'head_payload': design.get('head_payload'), 'body_top_m': top, 'turret': turret, 'tail': tail,
        'bus_v_nominal': bus_nom, 'bus_v_range': bus_v, 'layout_mm': L, 'urdf_check': urdf_check, 'notes': notes,
        'estimates': ['hub motor rotor/stator split', 'leg actuator rotor inertia (armature)' if legl['estimates'].get('armature') else None,
                      'printed part masses (CAD at 2 mm walls, 40 % infill)' if cad_masses(design_path) else 'printed part masses (designer estimate until CAD)',
                      'joint damping and friction'],
    }
    info['estimates'] = [e for e in info['estimates'] if e]
    (out_dir / 'model.json').write_text(json.dumps(info, indent=1) + '\n')
    return info


if __name__ == '__main__':
    info = build(Path(sys.argv[1] if len(sys.argv) > 1 else R / 'designs/default.json'))
    print(f"{info['name']}: {info['total_mass_kg']:.2f} kg in the model, {info['designer_mass_kg']:.2f} kg in the designer"
          f"{f' {info["printed_cad_delta_kg"]:+.2f} kg printed parts from the CAD' if info['printed_cad_delta_kg'] else ''} "
          f"({'reconciles' if info['mass_reconciles'] else 'DOES NOT reconcile'}); URDF check {'pass' if info['urdf_check']['pass'] else info['urdf_check']['problems']}")
