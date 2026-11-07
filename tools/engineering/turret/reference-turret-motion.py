#!/usr/bin/env python3
"""Generate the independent turret reference from an immutable, reviewed full scene.

Mechanical datums and ownership below are audited against CAD source, not inferred
from the display manifest. Pan +/-170 is bounded viewer coverage, not a hard stop.
Requires the existing pinned cad-agent motion_trace only when generating poses.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[3]
PREFIX = 'hardware/exports/sim/turret_box/'
FRAME = ('box: x forward (pan 0), y left, z up; origin on the desk under the pan axis. Each part is in its '
         "group's frame (pivots); journey focus points and the ball path are in the tilt frame (origin on the tilt axis)")

# Independent source audit: turret.py MADE/bought_parts; turret_box.py PARTS/bought;
# rotor ownership follows the actual shafts, while whole motor envelopes stay fixed
# on their supporting group. These are explicit names, not display-derived owners.
OWNERSHIP = {
    'base': 'pan_base base_board_carrier bumper_ring ring_carrier pan_servo pan_bearing pan_clamp slip_ring '
            'base_board base_board_inserts base_board_screws base_carrier_inserts base_carrier_screws '
            'index_magnet dt_receptacle dt_plug'.split(),
    'pan': 'pan_ring pan_spacer tilt_yoke ring_driver board_bay board_bay_lid pan_bearing_inner circlip_50 '
           'slip_ring_rotor ring_coupling ring_leads_rotor turret_board hall_switch tilt_servo tilt_bearing'.split(),
    'tilt': 'cradle horn_boss pivot_spacer cartridge_body hopper hopper_lid barrel laser_mount '
            'cradle_plate_l cradle_plate_r stop_lug shoulder_screw flywheel_motor_l flywheel_motor_r '
            'cartridge_board esc_l esc_r feed_motor ct_thumbscrew laser laser_screws laser_inserts '
            'hopper_inserts tilt_bearing_inner'.split(),
    'wheel_l': ['flywheel', 'flywheel_tyre'],
    'wheel_r': ['flywheel_m', 'flywheel_tyre_m'],
    'dial': ['dial'], 'flap': ['hopper_flap'], 'pinion': ['pan_pinion'],
    'adapter': 'box_deck intake_shroud pod_cover pod_xt60 pod_switch pod_fuse pod_pendant pod_usb pod_wago '
               'lid_screw_1 lid_screw_2 lid_screw_3 lid_screw_4'.split(),
    'j501': 'j501_base j501_cover j501_front_no_gmsl j501_rear_io j501_side_hatch'.split(),
}
OWNERS = {name: group for group, names in OWNERSHIP.items() for name in names}
assert len(OWNERS) == sum(map(len, OWNERSHIP.values())) == 80


def joint(parent, pivot, axis, span):
    return dict(parent=parent, pivot=pivot, axis=axis, range_deg=span)


# J501 roof97 + GAP40 + DECK_T8 = TM145; Geo.path_t125 + tilt_c15 =140.
# Wheel_x73 - tilt_x48 =25; wheel_y=51.62/2. FILL_PORT.x-19-tilt_x=-87.
# Source audit and sign/basis proof: docs/validation/turret-motion.md.
JOINTS = dict(
    pan=joint(None, [0, 0, 145], [0, 0, 1], [-170, 170]),
    tilt=joint('pan', [0, 0, 285], [0, -1, 0], [-25, 12]),
    pinion=joint(None, [-52.65, 0, 145], [0, 0, 1], [-510, 510]),
    dial=joint('tilt', [-48, 0, 285], [0, 0, 1], [0, 360]),
    wheel_l=joint('tilt', [25, 25.81, 285], [0, 0, 1], [0, 360]),
    wheel_r=joint('tilt', [25, -25.81, 285], [0, 0, -1], [0, 360]),
    flap=joint('tilt', [-87, 0, 376], [0, -1, 0], [0, 110]),
)
PIVOTS = dict(pan=[0, 0, 145], tilt=[0, 0, 140], pinion=[-52.65, 0, 145], pinion_ratio=-3,
              dial=[-48, 0, 0], wheel_l=[25, 25.81, 0], wheel_r=[25, -25.81, 0], flap=[-87, 0, 91])


def manifest_parts(manifest):
    if manifest.get('units') != 'mm' or manifest.get('frame') != FRAME or manifest.get('scene_frame_version') != 2:
        raise ValueError('Unsupported scene units/frame')
    parts = manifest['parts']
    names = [p['name'] for p in parts]
    if len(names) != 80 or len(set(names)) != 80 or set(names) != set(OWNERS):
        raise ValueError('Unknown, missing or duplicate independently audited components')
    for value in manifest['pivots'].values():
        numbers = value if isinstance(value, list) else [value]
        if not all(type(n) in (int, float) and math.isfinite(n) for n in numbers):
            raise ValueError('Nonfinite or nonnumeric display pivot')
    if manifest['pivots'] != PIVOTS:
        raise ValueError('Display pivots disagree with independently audited CAD datums')
    if manifest['limits']['tilt_deg'] != [-25, 12] or manifest['limits']['fire_tilt_max_deg'] != 10:
        raise ValueError('Reference requires the recovered mechanical and separate firing bounds')
    for part in parts:
        if part['group'] != OWNERS[part['name']] or part['file'] != part['name'] + '.stl':
            raise ValueError('Display file/ownership disagrees with independent CAD ownership: ' + part['name'])
    return {p['name']: p for p in parts}


def vertices(data):
    if len(data) < 84:
        raise ValueError('Incomplete binary STL')
    count = struct.unpack_from('<I', data, 80)[0]
    if not count or len(data) != 84 + 50 * count:
        raise ValueError('Binary STL length/count mismatch')
    points = []
    for row in struct.iter_unpack('<12fH', data[84:]):
        if not all(math.isfinite(v) for v in row[:12]):
            raise ValueError('Nonfinite STL normal/vertex')
        points.extend([list(row[i:i+3]) for i in (3, 6, 9)])
    return points


def sub(a, b): return [a[i] - b[i] for i in range(3)]
def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def dot(a, b): return sum(x*y for x, y in zip(a, b))


def landmarks(points):
    i0 = 0
    i1 = max(range(len(points)), key=lambda i: dot(sub(points[i], points[i0]), sub(points[i], points[i0])))
    u = sub(points[i1], points[i0])
    i2 = max(range(len(points)), key=lambda i: dot(cross(u, sub(points[i], points[i0])), cross(u, sub(points[i], points[i0]))))
    normal = cross(u, sub(points[i2], points[i0]))
    i3 = max(range(len(points)), key=lambda i: abs(dot(normal, sub(points[i], points[i0]))))
    if abs(dot(normal, sub(points[i3], points[i0]))) <= 1e-6:
        raise ValueError('Four affinely independent actual STL landmarks required')
    return [i0, i1, i2, i3]


def generate(revision):
    actual = subprocess.check_output(['git', 'rev-parse', revision + '^{commit}'], cwd=ROOT, text=True).strip()
    if actual != revision:
        raise ValueError('Use a full immutable reviewed commit identity')
    def blob(name): return subprocess.check_output(['git', 'show', revision + ':' + name], cwd=ROOT)
    if blob('tools/engineering/turret/reference-turret-motion.py') != Path(__file__).read_bytes():
        raise ValueError('Reference producer must match its immutable source revision')
    raw = blob(PREFIX + 'manifest.json')
    manifest = json.loads(raw)
    parts = manifest_parts(manifest)
    contract = dict(schema_version=1, length_unit='mm', frame='assembly-home',
                    reference='Independently audited hardware/cad/turret/turret.py and turret_box.py datums/ownership; '
                              'actual immutable rest STL at ' + revision + '; bounded sampled viewer coverage, not physical qualification.',
                    joints=JOINTS, components={})
    indices, bindings = {}, {}
    for name in sorted(OWNERS):
        part = parts[name]
        data = blob(PREFIX + part['file'])
        digest = hashlib.sha256(data).hexdigest()
        if digest != part['sha256']:
            raise ValueError('Immutable STL does not match manifest: ' + name)
        points = vertices(data)
        chosen = landmarks(points)
        group = OWNERS[name]
        # Pinion is the legacy root mesh in box coordinates. All other articulated
        # exports are local to their independently audited assembly-home pivot.
        origin = JOINTS[group]['pivot'] if group in ('pan', 'tilt', 'dial', 'wheel_l', 'wheel_r', 'flap') else [0, 0, 0]
        indices[name] = chosen
        contract['components'][name] = dict(joint=group if group in JOINTS else None,
                                            points=[[a+b for a, b in zip(points[i], origin)] for i in chosen])
        bindings[name] = dict(file=part['file'], group=group, sha256=digest)
    from cadagent.motion_trace import required_poses
    return dict(contract=contract, vertex_indices=indices, poses=required_poses(contract),
                source=dict(revision=revision, manifest_sha256=hashlib.sha256(raw).hexdigest(), parts=bindings,
                            cad_source_sha256={name: hashlib.sha256(blob(name)).hexdigest() for name in (
                                'hardware/cad/turret/turret.py', 'hardware/cad/turret/turret_box.py',
                                'hardware/cad/builders/build_turret_box.py')}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--out', type=Path, default=ROOT/'tests/fixtures/turret-motion-reference.json')
    args = parser.parse_args()
    fixture = generate(args.revision)
    args.out.write_text(json.dumps(fixture, indent=2) + '\n')
    print('reference:', len(fixture['vertex_indices']), 'components;', len(fixture['poses']), 'poses')


if __name__ == '__main__':
    main()
