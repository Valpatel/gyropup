"""Build the foam-ball turret on the Orin AGX compute box (cad/turret_box.py): the adapter's parts and print plan, the
clearance and airflow checks, and the 3D game page's scene (designer/sim.html, design "Turret on the Orin AGX box").

    .venv/bin/python cad/build_turret_box.py [--no-j501] [--out DIR --scene DIR]

Writes exports/turret/box/ (the adapter's STEP and print-ready STL, print-plan.json, bom.json, box.json with the checks,
the mechanism's numbers and the J501 revision it was built on) and exports/sim/turret_box/ (gitignored: every turret,
adapter and J501 part as an STL in its moving group's frame, and manifest.json: the pivots, the ball path, the callouts,
the ball's journey, the numbers). The turret is cad/turret.py's and the box is the J501 repo's own export: its
exports/view/*.stl when they match its parameters (the lid's top at the roof's height), else its exports/*.step (the
view meshes lag a revision change), so rebuilding after either project changes picks the change up. The J501 is
Rev 0.9 (the tower cooler: the Seeed reComputer mini J501 heatsink, its 9215 fan under a flush grille); the build
prints a warning when its parameters hold another revision than the adapter was drawn for (turret_box.BUILT_FOR) or
are not committed there. --out / --scene write elsewhere (a check of another J501 tree: J501_DIR=... --out /tmp/x).
Frames: the box frame of cad/turret_box.py (mm, x forward, y left, z up).
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import time
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import cadquery as cq  # noqa: E402

import printplan  # noqa: E402
import turret as tu  # noqa: E402
import turret_box as tb  # noqa: E402
from cadagent.geometry import export_print_stl  # noqa: E402
from cadagent.robot import Body, combine, printed_part_body, solid_mass_properties  # noqa: E402

OUT = R / 'exports' / 'turret' / 'box'
SCENE = R / 'exports' / 'sim' / 'turret_box'
MATERIALS = json.loads((R / 'catalog/materials.json').read_text())
CAT = {i['id']: i for i in json.loads((R / 'catalog/turret.json').read_text())}


def _catalogue():
    """Every catalogue item by id and by key (catalog/index.json's files and catalog/sourcing.json's parts), as the
    bench's parts list (cad/build_turret.py) reads them."""
    out = {}
    for f in dict.fromkeys(['hardware.json', *json.loads((R / 'catalog/index.json').read_text())['files']]):
        for it in json.loads((R / 'catalog' / f).read_text()):
            for k in (it.get('id'), it.get('key')):
                if k:
                    out.setdefault(k, it)
    for it in json.loads((R / 'catalog/sourcing.json').read_text()).get('parts', []):
        for k in (it.get('id'), it.get('key')):
            if k:
                out.setdefault(k, it)
    return out


# what to buy for the adapter, by catalogue key: [(key, qty, what for)]. The pod's panel parts are the bench stand's
# (D42, D47); the pendant itself, its plug and the 24 V supply are the stand's, moved over (SHARED)
BOX_BOUGHT = [('amass-xt60e-m', 1, 'pod: 24 V in'), ('turret_screw_m2_5x8', 2, 'pod: the XT60E-M\'s two screws'),
              ('turret_nut_m2_5', 2, 'pod: their nuts'), ('bulgin-r13244aaaa', 1, 'pod: turret power'),
              ('fuse-holder-5x20-panel', 1, 'pod: the fuse'), ('littelfuse-0477005-mxp', 2, 'pod: 5 A time-lag, one spare'),
              ('switchcraft-tb3m', 1, 'pod: the hold-to-run pendant\'s socket'), ('usb-can-canable2', 1, 'pod: CAN to the turret, USB to the J501'),
              ('wago-221-413', 4, 'pod: +24 V and 0 V to the DT12\'s power pins, the pendant loop to its safety pins'),
              ('turret_screw_m3x40', 4, 'the lid screws through the legs, in place of the J501\'s M3 x 16'),
              ('insert_m5', 4, 'deck: the TM face, wholly in the 8 mm deck'), ('screw_m5x12_button', 4, 'the turret onto the deck (the stand keeps its M5 x 16)'),
              ('turret_dowel_5x10', 2, 'deck: the TM face\'s dowels'),
              ('turret_insert_m3_short', 6, 'deck: the shroud\'s tabs'), ('turret_screw_m3x10', 6, 'shroud: its tabs up into the deck'),
              ('insert_m3', 4, 'deck: the pod cover'), ('turret_screw_m3x6_flat', 4, 'pod cover'),
              ('preson-p8106ul-3-8in', 1, 'shroud: a 3 mm strip cut from the roll, the ring under the floor\'s lip on the J501 roof\'s solid band')]
SHARED = [('pendant-hold-to-run', 'the bench stand\'s pendant, plugged into the pod instead'),
          ('switchcraft-ta3flx', 'on the pendant\'s lead'), ('meanwell-lrs-350-24', 'the bench supply: 24 V for the J501 and the turret')]
J501_VIEW = tb.J501_DIR / 'exports' / 'view'
_LID = ('J501 lid (P2, Rev {rev}): the flush grille over the 9215 fan is its intake, the hex cells round it let the exhaust out'
        if tb.J['intake']['kind'] == 'grille' else
        'J501 lid (P2, Rev {rev}): hex cells inside the Ø80 ring feed the fan, the cells round it let the exhaust out')
J501_PARTS = {'base': ('#2f343c', 'J501 base (P1): the floor, the walls, the board and cooler columns'),
              'cover': ('#3b3f46', _LID.format(rev=tb.J['revision'])),
              'front_no_gmsl': ('#8a9099', 'J501 front plate (P4)'), 'rear_io': ('#8a9099', 'J501 rear plate (P5): DC in, Ethernet, USB'),
              'side_hatch': ('#8a9099', 'J501 side hatch (P10)')}
M = 1e-3
G0 = 9.81

# ------------------------------------------------------------------------------------------- what each part does

ROLE = {
    'pan_base': 'The fixed base: bolts to the TM face (4 x M5, 2 dowels) and holds the pan bearing, the pan servo, the DT12 socket and the pan stop post.',
    'pan_clamp': 'Aluminium ring (SendCutSend, 3.2 mm 6061-T6): clamps the pan bearing\'s outer race into the base (5 x M3).',
    'pan_ring': 'The turntable: a 63-tooth gear on the bearing\'s inner race; the yoke bolts on top. It turns without a stop: power and signals cross on the slip ring.',
    'pan_pinion': '21-tooth pinion on the pan servo\'s horn. 63 / 21 = 3, so the servo turns three times for every turn of the turret.',
    'tilt_yoke': 'Two arms up to the tilt axis: the tilt servo on the left, a bearing on the right, hard stops at 0 and -25 deg (it cannot point above level).',
    'cradle': 'Swings on the tilt axis. Its two rails carry the ball cartridge (2 dowels + a thumbscrew) and the laser.',
    'cartridge_body': 'One printed block: the dial housing, the drop chute, the flywheel cage and the barrel socket. It lifts off the cradle as a unit.',
    'flywheel': 'Flywheel hub on the X2216\'s prop adapter (a washer and an M5 nut). Two of them spin opposite ways.',
    'flywheel_tyre': 'TPU tyre: the 22.7 mm ball is squeezed between two of them and leaves at nearly their surface speed.',
    'dial': 'The feed dial: 8 pockets on the feed servo\'s horn. Each 45 deg step drops one ball through the exit hole; parked, a spoke covers the hole.',
    'hopper': 'Clear tube over the dial: 30 balls fall into the pockets by gravity; the cone on the dial stirs them.',
    'hopper_lid': 'The hopper lid, with the fill port for the dock\'s spout.',
    'hopper_flap': 'Sprung flap over the fill port: the dock\'s spout pushes it open.',
    'barrel': '100 mm barrel, bore 2 mm over the ball after the wheels: it only guides. Two IR gates 60 mm apart time every shot. Blaze-orange tip.',
    'laser_mount': 'Holds the aiming laser parallel to the barrel (three boresight screws). It stays on the cradle when the cartridge comes off.',
    'bumper_ring': 'TPU ring round the base: it takes the knocks.',
    'pan_servo': 'Feetech STS3215 (12 V serial bus, 2.94 N.m stall, 45 rpm, 12-bit encoder): drives the pinion.',
    'pan_bearing': '61810-2RS thin-section bearing (50 x 65 x 7): the whole upper turret turns on it, with a 40 mm open centre.',
    'dt_receptacle': 'Deutsch DT 12-way socket: 24 V, CAN, the safety line and an ID pin between the turret and its host.',
    'dt_plug': 'The host\'s DT12 plug (a 90 deg boot turns the harness down).',
    'tilt_servo': 'STS3215 on the yoke\'s left arm: tilts the cradle directly.',
    'tilt_bearing': 'MR126 bearing round the M5 shoulder screw: the cradle\'s second pivot.',
    'flywheel_motor_l': 'SunnySky X2216 (880 rpm/V) on the fixed 12 V rail: 10,560 rpm at most, which caps the ball speed. Hangs under the cage plate.',
    'flywheel_motor_r': 'SunnySky X2216, spinning the other way.',
    'esc_l': 'AM32 35 A ESC for the left flywheel motor, on the cartridge board.',
    'esc_r': 'AM32 35 A ESC for the right flywheel motor, on the cartridge board.',
    'cartridge_board': 'The cartridge board: six FETs that short the motors\' phases about 8 ms after the safety line drops (the brake), their driver and the gates\' comparator; the two ESCs lie under it on the cage plate.',
    'feed_motor': 'Feetech STS3215 servo (bus ID 3) under the dial floor: steps the dial 45 deg per ball and feels a jam in its load reading.',
    'laser': 'Quarton 650 nm Class 2 red laser (under 1 mW): the aiming dot, parallel to the barrel.',
    'box_deck': f'The adapter: carries the TM face {tb.Z_TM - tb.ROOF:.0f} mm above the J501\'s roof on four legs at the lid\'s screw '
                f'corners; the control pod hangs at the back.',
    'intake_shroud': (f'Keeps the J501 fan\'s intake apart from its exhaust: a Ø{2 * tb.COLLAR_R:.0f} collar round the flush grille over '
                      f'the 9215 fan, sealed on the roof by a foam ring, fed by a duct from the front grille; the fan breathes room air, '
                      f'not its own hot exhaust.' if tb.J['intake']['kind'] == 'grille' else
                      'Keeps the J501 fan\'s intake apart from its exhaust: the fan breathes through the front grille, not its own hot air.'),
    'pod_cover': 'Closes the control pod from below.',
    'pod_xt60': 'XT60 socket: 24 V in. The J501 takes 12-36 V, so one 24 V supply can run both.',
    'pod_switch': 'DC rocker switch (Bulgin R13244AAAA, Ø20.2, keyed): turret power.',
    'pod_fuse': '5 A time-lag fuse (DC-rated) in a panel holder.',
    'pod_pendant': ('Mini-XLR socket (Switchcraft TB3M) for the hold-to-run pendant: the safety line. Nothing spins or feeds unless it '
                    'is held; it is keyed, so no headphone plug can close the loop.'),
    'pod_usb': 'USB-CAN adapter: the J501 talks CAN to the turret\'s MCU through it.',
    'pod_wago': 'WAGO lever connectors: 24 V to the DT12 power pins, the pendant loop to its safety pins.',
}
TITLE = {'pan_base': 'Pan base', 'pan_clamp': 'Bearing clamp', 'pan_ring': 'Pan ring (63 T)', 'pan_pinion': 'Pan pinion (21 T)',
         'tilt_yoke': 'Tilt yoke', 'cradle': 'Cradle', 'cartridge_body': 'Ball cartridge', 'flywheel': 'Flywheel hub', 'flywheel_tyre': 'Flywheel tyre',
         'dial': 'Feed dial', 'hopper': 'Hopper', 'hopper_lid': 'Hopper lid', 'hopper_flap': 'Fill flap', 'barrel': 'Barrel',
         'laser_mount': 'Laser mount', 'bumper_ring': 'Bumper ring', 'pan_servo': 'Pan servo', 'pan_bearing': 'Pan bearing',
         'dt_receptacle': 'DT12 socket', 'dt_plug': 'DT12 plug', 'tilt_servo': 'Tilt servo', 'tilt_bearing': 'Tilt bearing',
         'flywheel_motor_l': 'Flywheel motor L', 'flywheel_motor_r': 'Flywheel motor R', 'esc_l': 'ESC L', 'esc_r': 'ESC R',
         'feed_motor': 'Feed servo (STS3215)', 'cartridge_board': 'Cartridge board', 'laser': 'Aiming laser', 'box_deck': 'Box adapter',
         'intake_shroud': 'Intake shroud', 'pod_cover': 'Pod cover', 'pod_xt60': '24 V in (XT60)', 'pod_switch': 'Power switch',
         'pod_fuse': 'Fuse', 'pod_pendant': 'Pendant socket', 'pod_usb': 'USB-CAN', 'pod_wago': 'Wiring', 'base': 'J501 base',
         'cover': 'J501 lid', 'front_no_gmsl': 'J501 front plate', 'rear_io': 'J501 rear plate', 'side_hatch': 'J501 side hatch'}
# the parts the callouts name (the rest are listed when clicked)
CALLOUTS = ['hopper', 'dial', 'feed_motor', 'cartridge_body', 'flywheel_tyre', 'barrel', 'laser', 'cradle', 'tilt_servo', 'tilt_yoke',
            'pan_ring', 'pan_pinion', 'pan_servo', 'pan_bearing', 'pan_base', 'dt_receptacle', 'box_deck', 'intake_shroud', 'pod_pendant', 'cover']
# exploded view: how far each part moves (box frame at pan = tilt = 0, mm)
EXPLODE = {'box_deck': (0, 0, 60), 'intake_shroud': (0, 0, 28), 'pod_cover': (0, 0, 48), 'lid_screw': (0, 0, 120), 'pod_': (0, 0, 60),
           'bumper_ring': (0, 0, 75), 'pan_base': (0, 0, 95), 'pan_servo': (0, 0, 95), 'dt_receptacle': (0, -30, 95), 'dt_plug': (0, -75, 95),
           'pan_bearing': (0, 0, 125), 'pan_clamp': (0, 0, 145), 'pan_pinion': (0, 0, 120), 'pan_ring': (0, 0, 165), 'tilt_yoke': (0, 0, 195),
           'tilt_servo': (0, 45, 195), 'tilt_bearing': (0, -30, 195), 'cradle': (0, 0, 215), 'cartridge_body': (0, 0, 250),
           'flywheel': (0, 0, 250), 'flywheel_tyre': (0, 0, 250), 'flywheel_motor': (0, 0, 290), 'esc_': (0, 0, 320), 'feed_motor': (0, 0, 210),
           'cartridge_board': (0, 0, 330), 'dial': (0, 0, 300), 'hopper': (0, 0, 350), 'hopper_lid': (0, 0, 390), 'hopper_flap': (0, 0, 400),
           'barrel': (70, 0, 250), 'laser_mount': (25, -35, 230), 'laser': (25, -35, 230)}


def explode_of(name):
    for k in sorted(EXPLODE, key=len, reverse=True):
        if name == k or (k.endswith('_') and name.startswith(k)) or name.startswith(k + '_') or name == k.rstrip('_'):
            return list(EXPLODE[k])
    return [0, 0, 0]


def hexcol(c):
    return '#' + ''.join(f'{int(round(255 * max(0.0, min(1.0, v)))):02x}' for v in c[:3])


# ------------------------------------------------------------------------------------------- meshes

_STL = np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])


def read_stl(path):
    b = Path(path).read_bytes()
    n = struct.unpack('<I', b[80:84])[0]
    if len(b) == 84 + 50 * n:
        return np.frombuffer(b[84:], dtype=_STL)['v'].astype(float)
    vs = [list(map(float, ln.split()[1:4])) for ln in b.decode(errors='ignore').splitlines() if ln.strip().startswith('vertex')]
    return np.array(vs, float).reshape(-1, 3, 3)


def write_stl(path, tris):
    tris = np.asarray(tris, np.float32)
    nrm = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm = np.divide(nrm, ln, out=np.zeros_like(nrm), where=ln > 0)
    a = np.zeros(len(tris), dtype=_STL)
    a['n'], a['v'] = nrm, tris
    with open(path, 'wb') as f:
        f.write(b'gyropup turret_box'.ljust(80, b' '))
        f.write(struct.pack('<I', len(tris)))
        f.write(a.tobytes())


def shape_tris(shape, tol=0.2, ang=0.3):
    s = shape.val() if hasattr(shape, 'val') else shape
    verts, faces = s.tessellate(tol, ang)
    v = np.array([(p.x, p.y, p.z) for p in verts], float)
    return v[np.array(faces, int)] if len(faces) else np.zeros((0, 3, 3))


def decimate(tris, keep):
    """Fewer triangles for the page: quadric decimation (VTK, through pyvista) of the welded mesh."""
    try:
        import pyvista as pv
    except ImportError:
        return tris
    pts, inv = np.unique(np.round(tris.reshape(-1, 3), 4), axis=0, return_inverse=True)
    f = inv.reshape(-1, 3)
    f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])]
    m = pv.PolyData(pts, np.hstack([np.full((len(f), 1), 3), f]).ravel()).decimate(1.0 - keep, volume_preservation=True)
    return np.asarray(m.points)[m.faces.reshape(-1, 4)[:, 1:]]


def surface_points(tris, per_mm2=0.12, rng=np.random.default_rng(1)):
    """Points on a mesh: every vertex and about per_mm2 random points per mm2 of its faces."""
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    n = rng.poisson(area * per_mm2)
    idx = np.repeat(np.arange(len(tris)), n)
    u, v = rng.random(len(idx)), rng.random(len(idx))
    flip = u + v > 1
    u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    pts = a[idx] + u[:, None] * (b[idx] - a[idx]) + v[:, None] * (c[idx] - a[idx])
    return np.concatenate([tris.reshape(-1, 3), pts])


def rot_z(p, ang):
    c, s = math.cos(ang), math.sin(ang)
    return np.stack([p[:, 0] * c - p[:, 1] * s, p[:, 0] * s + p[:, 1] * c, p[:, 2]], axis=1)


def rot_y(p, ang):
    """About +y by ang (rad): turret.py's tilt turns the tilt group by -tilt about +y (negative tilt = muzzle down)."""
    c, s = math.cos(ang), math.sin(ang)
    return np.stack([p[:, 0] * c + p[:, 2] * s, p[:, 1], -p[:, 0] * s + p[:, 2] * c], axis=1)


J501_KEEP = {'base': 24000, 'cover': 24000}                     # triangles for the page (phones); the plates 8000


def j501_meshes():
    """({name: (triangles in the J501 frame, source)}, the view export used): the J501 repo's exports/view/*.stl when they
    match its parameters (the lid's top at the roof's height), else its exports/*.step, tessellated."""
    cover = J501_VIEW / 'cover.stl'
    view = cover.exists() and abs(float(read_stl(cover)[..., 2].max()) - tb.ROOF) < 0.05
    out = {}
    for name in J501_PARTS:
        src = (J501_VIEW / f'{name}.stl') if view else (tb.J501_DIR / 'exports' / f'{name}.step')
        if src.exists():
            out[name] = (read_stl(src) if src.suffix == '.stl' else shape_tris(cq.importers.importStep(str(src)), 0.25, 0.4), src)
    return out, view


# ------------------------------------------------------------------------------------------- the mechanism's numbers

def flight(v0=21.3, z0=0.55, pitch_deg=0.0, cd=0.5, d=0.0227, m=0.00183, dt=2e-4, x_max=12.0):
    """A ball's flight with drag and gravity (as designer/turret3d.js flies it): rows [x m, t s, drop mm, v m/s]."""
    k = 0.5 * 1.2 * cd * math.pi * (d / 2) ** 2 / m
    a = math.radians(pitch_deg)
    x, z, vx, vz, t = 0.0, z0, v0 * math.cos(a), v0 * math.sin(a), 0.0
    rows, nxt = [], 1.0
    while x < x_max and z > 0:
        v = math.hypot(vx, vz)
        vx -= k * v * vx * dt
        vz -= (G0 + k * v * vz) * dt
        x += vx * dt
        z += vz * dt
        t += dt
        if x >= nxt:
            if nxt <= 6.0:
                rows.append([round(nxt, 1), round(t, 3), round((z0 - z) * 1000), round(math.hypot(vx, vz), 1)])
            nxt += 1.0
    return rows, round(x, 2)


def mechanics(T, rows, groups):
    G = T.G
    sn, sv = CAT['sunnysky-x2216-880kv-v3']['specs'], CAT['feetech-sts3215-c018-12v']['specs']
    l3 = json.loads((R / 'exports/turret/launch/launch3d.json').read_text())['design']          # the physics' set speed (sim/turret_launch3d.py)
    ball = {'d_mm': G.ball, 'mass_g': 1.83, 'speed_mps': round(l3['set_fps_nominal'] * 0.3048, 2), 'fps': l3['set_fps_nominal'], 'bore_mm': G.bore_out,
            'cap_fps': 70}
    ball['energy_j'] = round(0.5 * ball['mass_g'] * M * ball['speed_mps'] ** 2, 3)
    # flywheels: hub + tyre from the CAD (about the wheel's axis), the X2216's rotor from the catalogue (est)
    hub = solid_mass_properties(T.local['flywheel'].val(), tu.DENS['pa6-cf'], 1.0)
    tyre = solid_mass_properties(T.local['flywheel_tyre'].val(), tu.DENS['tpu95'], 1.0)
    i_wheel = (hub.inertia[2][2] + tyre.inertia[2][2]) * 1e6 + sn['rotor_inertia_kg_mm2']           # kg mm2
    wheel_d = tu.TYRE_SET[0]                                       # the v0 tyre (Ø34: D42)
    rpm = float(l3['set_rpm'])                                     # the ESC set speed for the nominal ball (launch3d.json)
    eta = round(ball['speed_mps'] / (rpm / 60 * math.pi * wheel_d * M), 3)   # exit speed / tyre surface speed at that speed
    w = rpm * 2 * math.pi / 60
    e_wheel = 0.5 * i_wheel * 1e-6 * w ** 2
    loss = 0.3                                                     # foam hysteresis per shot, share of the ball's energy (assumed)
    de = ball['energy_j'] * (1 + loss) / 2                          # per wheel
    drop = 100 * (1 - math.sqrt(max(0.0, 1 - de / e_wheel)))
    i_lim = 20.0                                                   # AM32 current limit set for the flywheels (A, a choice)
    torque = sn['kt_nm_per_a'] * i_lim
    recover_ms = 1000 * i_wheel * 1e-6 * (w * drop / 100) / torque
    spin_ms = 1000 * i_wheel * 1e-6 * w / torque
    coast_s = i_wheel * 1e-6 * w / (sn['kt_nm_per_a'] * sn['no_load_current_a'])
    crush = G.ball + wheel_d - G.wheel_c
    fly = {'d_mm': wheel_d, 'centres_mm': round(G.wheel_c, 2), 'crush_mm': round(crush, 2), 'crush_pct': round(100 * crush / G.ball, 1),
           'rpm': round(rpm, -1), 'surface_mps': round(rpm / 60 * math.pi * wheel_d * M, 1), 'efficiency_assumed': eta,
           'throttle_pct': round(100 * rpm / sn['no_load_speed_rpm']), 'motor_kv': sn['kv_rpm_per_v'], 'no_load_rpm': sn['no_load_speed_rpm'],
           'inertia_kg_mm2': round(i_wheel, 2), 'energy_j_each': round(e_wheel, 2), 'speed_drop_per_shot_pct': round(drop, 1),
           'recovery_ms': round(recover_ms, 1), 'spin_up_ms_motor_limit': round(spin_ms), 'coast_down_s': round(coast_s, 1),
           'current_limit_a': i_lim, 'note': 'the set speed for the nominal ball at the physics\' set fps (sim/turret_launch3d.py); foam loss 30 % '
                                            '(assumed); the chronograph gates in the barrel measure the real speed'}
    # feed: one ball per 45 deg of the dial, stepped by the STS3215 (45 rpm at 12 V with no load: 167 ms per step at full
    # speed, ~200-250 ms settled with its ramps, est until bench test 3.9 measures it)
    step_ms = 235.0                                                # exports/turret/feed/feed_dyn.json: settled in 232-246 ms
    feed = {'pockets': G.n_pockets, 'motor': 'Feetech STS3215 serial bus servo (ID 3)', 'ratio': 345, 'no_load_rpm': sv['no_load_speed_rpm'],
            'step_deg': 360 / G.n_pockets, 'step_ms_est': step_ms, 'rate_per_s': 3, 'max_rate_per_s': 3,
            'pitch_radius_mm': G.rp, 'exit_x_mm': G.exit_x, 'park_deg': 360 / G.n_pockets / 2}
    # the drop from the pocket through the chute to the nip: gravity along the bend (radius chute_r), from rest
    t, s, v, dt = 0.0, 0.0, 0.0, 1e-5
    arc = math.pi / 2 * G.chute_r * M
    while s < arc:
        ang = s / (G.chute_r * M)                                 # 0 = falling straight down, pi/2 = moving forward
        v += G0 * math.cos(ang) * dt
        s += v * dt
        t += dt
    chute_ms, v_nip = 1000 * t, v
    run_ms = 1000 * ((G.wheel_x - 7.25 - G.chute_cx) * M) / max(v_nip, 0.1)
    barrel_ms = 1000 * (G.barrel_x1 - G.wheel_x) * M / ball['speed_mps']
    timing = {'dial_to_exit_ms': round(step_ms), 'chute_ms': round(chute_ms), 'to_nip_ms': round(run_ms),
              'nip_to_muzzle_ms': round(barrel_ms, 1), 'speed_into_nip_mps': round(v_nip, 2)}
    timing['trigger_to_muzzle_ms'] = round(timing['dial_to_exit_ms'] + chute_ms + run_ms + barrel_ms)
    # pan and tilt
    gr = G.gear
    pan = {'pinion_teeth': gr['z_pinion'], 'ring_teeth': gr['z_ring'], 'ratio': gr['z_ring'] / gr['z_pinion'], 'module_mm': gr['m'],
           'servo_stall_nm': sv['stall_torque_nm'], 'ring_stall_nm': round(sv['stall_torque_nm'] * gr['z_ring'] / gr['z_pinion'], 2),
           'firmware_cap_pct': 50, 'max_deg_s': round(sv['no_load_speed_deg_per_s'] / (gr['z_ring'] / gr['z_pinion'])),
           'range_deg': [-170, 170], 'hard_stop_deg': 173.5, 'encoder_counts_per_turret_deg': round(4096 / 360 * gr['z_ring'] / gr['z_pinion'], 1)}
    tg = groups['tilt']
    tilt_axis_x = 0.0
    hold = tg.mass * G0 * (tg.com[0] - tilt_axis_x)
    tilt = {'servo_stall_nm': sv['stall_torque_nm'], 'max_deg_s': sv['no_load_speed_deg_per_s'], 'range_deg': [G.tilt_min, 0.0],
            'group_mass_g': round(tg.mass * 1000), 'com_ahead_mm': round(tg.com[0] * 1000, 1), 'holding_nm': round(hold, 2),
            'margin': round(sv['stall_torque_nm'] / max(abs(hold), 1e-6), 1)}
    # the pan group's inertia about the pan axis (with the tilt group at tilt 0), and the torque to reach full slew fast
    pz = 0.0
    for b in (groups['pan'], groups['tilt']):
        pz += b.inertia[2][2] + b.mass * (b.com[0] ** 2 + b.com[1] ** 2)
    pan['inertia_kg_m2'] = round(pz, 5)
    pan['accel_at_cap_deg_s2'] = round(math.degrees(pan['ring_stall_nm'] * 0.5 / pz))
    pan['time_to_full_slew_ms'] = round(1000 * math.radians(pan['max_deg_s']) / math.radians(pan['accel_at_cap_deg_s2']), 1)
    level, x_ground = flight(z0=(tb.Z_TM + G.path_t) * M + 0.3)
    return {'ball': ball, 'flywheel': fly, 'feed': feed, 'timing': timing, 'pan': pan, 'tilt': tilt,
            'flight_level': {'rows': level, 'from_height_m': round((tb.Z_TM + G.path_t) * M + 0.3, 3), 'lands_m': x_ground,
                             'note': 'a level shot from the bench (the box on a 0.3 m crate): [range m, time s, drop mm, speed m/s]; '
                                     'drag as a sphere, Cd 0.5'}}


# ------------------------------------------------------------------------------------------- clearance

def sweep(T, pts_pan, pts_tilt, pans=np.arange(-170, 171, 5.0), tilts=np.arange(0.0, -25.01, -2.5)):
    """The moving parts against the deck (outside the turret's own base) and against upright antennas on the J501's
    bulkheads, over pan x tilt. Points are in their groups' frames (mm)."""
    G = T.G
    ants = tb.antennas()
    deck_gap, worst = 1e9, None
    ant_min = {a[0]: 1e9 for a in ants}
    blocked = {}                                     # pan -> the deepest tilt that clears every antenna by 3 mm
    for pan in pans:
        ok_tilt, still_clear = None, True
        p_pan = rot_z(pts_pan, math.radians(pan)) + [0, 0, tb.Z_TM]
        for tilt in tilts:
            p_t = rot_y(pts_tilt, math.radians(-tilt)) + [0, 0, G.tilt_t]
            p_t = rot_z(p_t, math.radians(pan)) + [0, 0, tb.Z_TM]
            p = np.concatenate([p_pan, p_t])
            r = np.hypot(p[:, 0], p[:, 1])
            over = (r > G.base_r) & (p[:, 0] > tb.DECK_X[0]) & (p[:, 0] < tb.DECK_X[1]) & (np.abs(p[:, 1]) < tb.SIDE_Y)
            if over.any():
                g = float((p[over, 2] - tb.Z_TM).min())
                if g < deck_gap:
                    deck_gap, worst = g, (float(pan), float(tilt))
            clear = True
            for name, b, t, d in ants:
                q = p[(p[:, 2] > b[2]) & (p[:, 2] < t[2] + d)]
                dist = float(np.hypot(q[:, 0] - b[0], q[:, 1] - b[1]).min()) - d / 2 if len(q) else 1e9
                ant_min[name] = min(ant_min[name], dist)
                if dist < 3.0:
                    clear = False
            if clear and still_clear:
                ok_tilt = tilt
            still_clear = still_clear and clear
        blocked[float(pan)] = ok_tilt if ok_tilt is not None else 0.0
    table = [[p, -float(v)] for p, v in blocked.items()]          # [pan deg, most depression allowed deg] with antennas up
    lim = [p for p, v in table if v < -G.tilt_min - 0.01]
    sectors = []                                                  # the pan sectors where the antennas limit the tilt
    for pan in lim:
        if sectors and pan - sectors[-1][1] <= 5.0 + 1e-6:
            sectors[-1][1] = pan
        else:
            sectors.append([pan, pan])
    return {'deck_min_gap_mm': round(deck_gap, 1), 'deck_worst_pose_deg': worst,
            'antenna_min_gap_mm': {k: round(v, 1) for k, v in ant_min.items()},
            'antenna_tilt_max_deg': table,
            'antenna_limited_pans_deg': sectors,
            'note': 'antennas: upright swivel dipoles on all four RP-SMA bulkheads (none chosen yet: ' + tb.ANTENNA['note'] + ')'}


def ball_clear(T, pans=np.arange(-170, 171, 5.0), tilt=-25.0):
    """At the deepest tilt, how far outside the deck's outline the muzzle is (mm, the least over pan): a ball leaving it
    can only go down past the deck and the box, never into them."""
    G = T.G
    worst = 1e9
    for pan in pans:
        x, y, _ = T.point((G.barrel_x1, 0, 0), 'tilt', pan, tilt)
        dx = max(tb.DECK_X[0] - x, x - tb.DECK_X[1], 0.0)
        dy = max(abs(y) - tb.SIDE_Y, 0.0)
        out = math.hypot(dx, dy) if (dx or dy) else -min(x - tb.DECK_X[0], tb.DECK_X[1] - x, tb.SIDE_Y - abs(y))
        worst = min(worst, out - G.br)
    return round(worst, 1)


def ball_path_check():
    """The 3D check of the ball's way out, cad/turret_lidar.py --scene box (every moving part and the ball's path, a
    Ø22.8 ball 2 deg low at the slowest stray speed, against the deck, the box and upright antennas, at every pan and
    tilt, 10 mm margin), when its result is for this TM height; None when it has not been run."""
    f = R / 'exports' / 'turret' / 'lidar' / 'box.json'
    if not f.exists():
        return None
    d = json.loads(f.read_text())
    deck = next((o for o in d.get('obstacles', []) if o.get('name') == 'deck and box'), None)
    current = deck is not None and abs(deck['lo'][2] + tb.Z_TM) < 0.01
    ko = [abs(p) for p in d.get('keep_out_fire_pan_deg') or []]
    return {'file': 'exports/turret/lidar/box.json', 'current': current, 'margin_mm': d.get('margin_mm'),
            'limited_pan_window_deg': d.get('limited_pan_window_deg'), 'clear': current and d.get('limited_pan_window_deg') is None,
            'no_fire_from_pan_deg': min(ko) if ko else None,
            'note': ('every pan and tilt clear of the deck, the box and upright antennas by the margin; no firing within '
                     f'{180 - min(ko):.0f} deg of straight back (the operator\'s side)' if ko else '') if current else
                    'stale: rerun .venv/bin/python cad/turret_lidar.py --scene box, then this build'}


def adapter_clearance(adapter):
    """The shroud against the deck's legs and TM insert bosses (task N4 asks 3 mm or more), measured between the solids, and
    the shroud's lowest point over the J501's roof (mm)."""
    deck, shroud = adapter['box_deck'], adapter['intake_shroud'].val()
    legs, bosses = {}, {}
    for k, (x, y) in enumerate(tb.LEGS):
        leg = deck.intersect(tb._cyl_z(tb.LEG_OD / 2 + 1.0, tb.ROOF - tb.SPIGOT_L - 2.0, tb.DECK_Z0 - 0.01, x, y)).val()
        legs[f'leg_{k + 1}'] = round(shroud.distance(leg), 2)
    for k, (x, y) in enumerate(tu.TM_BOLTS):              # the TM inserts are wholly in the deck plate: anything below it?
        below = deck.intersect(tb._box(x - 9.0, x + 9.0, y - 9.0, y + 9.0, tb.ROOF, tb.DECK_Z0 - 0.01))
        bosses[f'tm_boss_{k + 1}'] = round(shroud.distance(below.val()), 2) if below.solids().size() else None
    least = min([*legs.values(), *[b for b in bosses.values() if b is not None]])
    return {'legs_mm': legs, 'tm_bosses_mm': bosses, 'least_mm': least, 'required_mm': 3.0, 'ok': least >= 3.0,
            'shroud_over_the_roof_mm': round(min(v.Z for v in shroud.Vertices()) - tb.ROOF, 2),
            'how': 'the BRepExtrema distance between the intake shroud and each leg (the deck cut round it, under the deck plate) and '
                   'anything of the deck below its plate at each TM insert (none: the inserts are wholly in the 8 mm deck)'}


# ------------------------------------------------------------------------------------------- main

def main():
    global OUT, SCENE
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-j501', action='store_true', help='skip the J501 meshes (the page then shows a plain box)')
    ap.add_argument('--out', type=Path, default=OUT, help='where the adapter\'s files go (default exports/turret/box)')
    ap.add_argument('--scene', type=Path, default=SCENE, help='where the 3D page\'s scene goes (default exports/sim/turret_box)')
    a = ap.parse_args()
    OUT, SCENE = a.out.resolve(), a.scene.resolve()
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    SCENE.mkdir(parents=True, exist_ok=True)
    for f in SCENE.glob('*.stl'):
        f.unlink()
    T = tu.Turret({'bodyTop': tb.Z_TM - 20.0 - tu.SADDLE_T})        # its TM face on the deck
    G = T.G
    g = tb.J.get('git') or {}
    print(f'turret on the box: TM face {tb.Z_TM:.0f} mm above the desk ({tb.GAP:.0f} mm gap + {tb.DECK_T:.0f} mm deck over the J501 '
          f'Rev {tb.J["revision"]} roof), pan axis over the box middle; J501 parameters from {tb.J["source"] or "the built-in fallback"}'
          + (f' ({g["state"]}, J501 HEAD {g["head"][:7]})' if g.get('head') else ''))
    warn = tb.revision_warning()
    if warn:
        print('\n  ' + '!' * 100 + f'\n  WARNING: {warn}\n  ' + '!' * 100 + '\n')

    # ---- the adapter: STEP, print STL, print plan
    adapter = tb.parts()
    plan, masses = {}, {}
    for name, shape in adapter.items():
        mat, qty, how, rot = tb.PARTS[name]
        v = shape.val()
        if not v.isValid() or len(v.Solids()) != 1:                 # a failed boolean leaves pieces: never export them
            raise SystemExit(f'{name}: not one valid solid ({len(v.Solids())} solids, valid {v.isValid()}) on the J501 Rev {tb.J["revision"]}')
        cq.exporters.export(v, str(OUT / f'{name}.step'))
        export_print_stl(v, OUT / f'{name}.stl', rotation=rot)
        g = solid_mass_properties(v, MATERIALS[mat]['density_g_cm3'], 0.45, name).mass * 1000
        masses[name] = g
        plan[name] = printplan.row(v, rot, mat, qty, g, False, how)
    too_big = printplan.write(OUT / 'print-plan.json', plan, note='the turret\'s adapter on the J501 compute box; hours are rough')

    # ---- the turret's parts, posed in the box frame, by moving group
    rows, tot, com = tu.mass_properties(T, 0.0)
    parts = []                                         # manifest entries

    def add(name, group, shape, color, opacity=1.0, kind='made', mirror=False, offset=(0, 0, 0), extra=None, tol=0.2):
        tris = shape_tris(shape, tol) - np.asarray(offset, float)
        f = f'{name}{"_m" if mirror else ""}.stl'
        write_stl(SCENE / f, tris)
        lo, hi = tris.reshape(-1, 3).min(axis=0), tris.reshape(-1, 3).max(axis=0)
        e = {'name': name + ('_m' if mirror else ''), 'part': name, 'group': group, 'file': f, 'color': color, 'opacity': opacity, 'kind': kind,
             'bbox': [round(float(x), 1) for x in (*lo, *hi)], 'title': TITLE.get(name, name.replace('_', ' ')),
             'role': ROLE.get(name, ''), 'explode': explode_of(name)}
        if extra:
            e.update(extra)
        parts.append(e)
        return tris

    tz = tb.Z_TM + G.tilt_t
    pan_o, tilt_o = (0.0, 0.0, tb.Z_TM), (0.0, 0.0, tz)
    flap_hinge = (tu.FILL_PORT[0] - 19.0, 0.0, G.hopper_top + 6.0 - G.tilt_c)      # tilt frame
    wheel = {'wheel_l': (G.wheel_x, G.wheel_y, 0.0), 'wheel_r': (G.wheel_x, -G.wheel_y, 0.0)}
    group_pts = {'pan': [], 'tilt': []}
    for name, m in T.meta.items():
        fr = T.frame[name]
        posed = T.pose_shape(T.local[name], fr, 0.0, 0.0, robot=True)
        row = rows.get(name, {})
        info = {'material': m['material'], 'mass_g': round(row.get('mass_g', 0.0), 1), 'qty': m['qty'], 'how': m['note'], 'doc': m['doc'],
                'print_h': round(row.get('mass_g', 0.0) * m['qty'] / tu.DENS[m['material']] / tu.PRINT_RATE_CM3_H[m['material']], 1)}
        col = tu.COL.get(name, (0.6, 0.6, 0.62))
        op = col[3] if len(col) > 3 else 1.0
        if fr in ('base', 'pinion'):
            add(name, fr, posed, hexcol(col), op, extra=info)
        elif fr == 'pan':
            tris = add(name, 'pan', posed, hexcol(col), op, offset=pan_o, extra=info)
            group_pts['pan'].append(tris)
        else:
            if name in ('flywheel', 'flywheel_tyre'):
                for side, mir in (('wheel_l', False), ('wheel_r', True)):
                    sh = T.pose_shape(T.local[name].mirror('XZ'), fr, 0.0, 0.0, robot=True) if mir else posed
                    wx, wy, _ = wheel[side]
                    tris = add(name, side, sh, hexcol(col), op, mirror=mir, offset=(wx, wy, tz), extra=info)
                    group_pts['tilt'].append(tris + [wx, wy, 0.0])
            elif name == 'dial':
                tris = add(name, 'dial', posed, hexcol(col), op, offset=tilt_o, extra=info)
                group_pts['tilt'].append(tris)
            elif name == 'hopper_flap':
                tris = add(name, 'flap', posed, hexcol(col), op, offset=(flap_hinge[0], 0.0, tz + flap_hinge[2]), extra=info)
                group_pts['tilt'].append(tris + [flap_hinge[0], 0.0, flap_hinge[2]])
            else:
                tris = add(name, 'tilt', posed, hexcol(col), op, offset=tilt_o, extra=info)
                group_pts['tilt'].append(tris)
    for name, (shape, fr, mass, note) in T.bought.items():
        posed = T.pose_shape(shape, fr, 0.0, 0.0, robot=True)
        col = tu.COL.get(name, (0.2, 0.2, 0.22))
        op = col[3] if len(col) > 3 else 1.0
        info = {'mass_g': mass, 'note': note}
        if fr == 'base':
            add(name, 'base', posed, hexcol(col), op, kind='bought', extra=info)
        elif fr == 'pan':
            group_pts['pan'].append(add(name, 'pan', posed, hexcol(col), op, kind='bought', offset=pan_o, extra=info))
        else:
            group_pts['tilt'].append(add(name, 'tilt', posed, hexcol(col), op, kind='bought', offset=tilt_o, extra=info))

    # ---- the adapter and what is in it (box frame)
    acol = {'box_deck': '#3d4552', 'intake_shroud': '#5aa9e6', 'pod_cover': '#3d4552'}
    for name, shape in adapter.items():
        mat, qty, how, rot = tb.PARTS[name]
        add(name, 'adapter', shape, acol[name], kind='adapter', extra={'material': mat, 'mass_g': round(masses[name], 1), 'qty': qty, 'how': how,
                                                                       'print_h': plan[name]['hours']})
    for name, (shape, mass, note) in tb.bought().items():
        base = 'lid_screw' if name.startswith('lid_screw') else name
        add(name, 'adapter', shape, '#c9ccd2' if base == 'lid_screw' else '#1d2027', kind='bought', extra={'mass_g': mass, 'note': note,
                                                                                                          'title': TITLE.get(base, 'Lid screw')})
        if base == 'lid_screw':
            parts[-1]['title'] = f'Lid screw (M3 x {tb.LID_SCREW_LEN:.0f})'
            parts[-1]['role'] = f'Clamps leg, lid and base into the J501\'s own lid insert: the J501\'s M3 x {tb.J["lid_screw_len"]:.0f} swapped for M3 x {tb.LID_SCREW_LEN:.0f}.'

    # ---- the J501 itself, from its repo's export (box frame), decimated for phones
    j501, j501_src = [], None
    Mj = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    tj = np.array([tb.TC[1], -tb.TC[0], 0.0])
    if not a.no_j501:
        meshes, view = j501_meshes()
        j501_src = 'exports/view (its view meshes)' if view else 'exports/*.step (its view meshes do not match its parameters yet)'
        print(f'  J501 meshes: {j501_src}')
        for name, (col, role) in J501_PARTS.items():
            if name not in meshes:
                print(f'  (no J501 {name}: skipped)')
                continue
            tris, src = meshes[name]
            tris = tris @ Mj.T + tj
            n0 = len(tris)
            tris = decimate(tris, min(1.0, J501_KEEP.get(name, 8000) / n0))
            write_stl(SCENE / f'j501_{name}.stl', tris)
            lo, hi = tris.reshape(-1, 3).min(axis=0), tris.reshape(-1, 3).max(axis=0)
            parts.append({'name': f'j501_{name}', 'part': name, 'group': 'j501', 'file': f'j501_{name}.stl', 'color': col, 'opacity': 1.0,
                          'kind': 'j501', 'bbox': [round(float(x), 1) for x in (*lo, *hi)], 'title': TITLE.get(name, name), 'role': role,
                          'explode': [0, 0, 0], 'triangles': [n0, len(tris)], 'source': str(src)})
            j501.append(name)

    # ---- mass properties of the moving groups (for the tilt holding torque and the pan's inertia)
    def group_body(gname):
        bodies = []
        for name, m in T.meta.items():
            fr = T.frame[name]
            if (gname == 'tilt') != (fr == 'tilt') or (gname == 'pan' and fr != 'pan'):
                continue
            wall, infill = (500.0, 1.0) if m['solid'] else (2.0, 0.4)
            for k in range(m['qty']):
                sh = T.local[name] if k == 0 else T.local[name].mirror('XZ')
                v = T.pose_shape(sh, fr, 0.0, 0.0, robot=False).val()
                if gname == 'tilt':
                    v = v.translate(cq.Vector(0, 0, -G.tilt_t))
                bodies.append(printed_part_body(v, tu.DENS[m['material']], wall_mm=wall, infill=infill, name=name)[0])
        for name, (shape, fr, mass, note) in T.bought.items():
            if fr != gname or mass <= 0:
                continue
            v = T.pose_shape(shape, fr, 0.0, 0.0, robot=False).val()
            if gname == 'tilt':
                v = v.translate(cq.Vector(0, 0, -G.tilt_t))
            bodies.append(solid_mass_properties(v, mass / (v.Volume() / 1000.0), 1.0, name))
        if gname == 'tilt':
            bodies.append(Body(30 * 0.00183, (0.0, 0.0, (G.path_t + (G.dial_z0 + G.hopper_top) / 2 - 8 - G.tilt_t) * M), name='30 balls'))
        return combine(bodies, gname)
    groups = {g: group_body(g) for g in ('pan', 'tilt')}
    mech = mechanics(T, rows, groups)

    # ---- checks: the sweep, the ball's way out, the airflow, tipping
    pts_pan = surface_points(np.concatenate(group_pts['pan']), 0.05)
    pts_tilt = surface_points(np.concatenate(group_pts['tilt']), 0.05)
    sw = sweep(T, pts_pan, pts_tilt)
    air = tb.airflow_estimate()
    seal = tb.intake_seal()
    fit = adapter_clearance(adapter)
    path_out = ball_path_check()
    j501_printed = 368.2                                         # g, the J501 slice report (PLA, Rev 0.8: not re-sliced for 0.9)
    j501_inside = 1000.0                                         # g, the Orin module + carrier + cooler (est; the Rev 0.9 tower
    #                                                              cooler is heavier, so the tipping push below is on the low side)
    turret_g = tot
    adapter_g = sum(masses.values()) + sum(m for _, m, _ in tb.bought().values())
    zc = (j501_printed * 46 + j501_inside * 40 + adapter_g * (tb.ROOF + 25) + turret_g * (tb.Z_TM + com[2])) / (j501_printed + j501_inside + adapter_g + turret_g)
    total = (j501_printed + j501_inside + adapter_g + turret_g) / 1000
    half = min(-tb.REAR_X, tb.FRONT_X, tb.SIDE_Y)
    push_h = tb.Z_TM + G.tilt_t
    tip = {'total_kg': round(total, 2), 'com_height_mm': round(zc), 'tip_angle_deg': round(math.degrees(math.atan2(half, zc))),
           'push_to_tip_n': round(total * G0 * half / push_h, 1), 'push_height_mm': round(push_h),
           'note': 'J501: 368 g printed (its slice report) + 1.0 kg Orin, carrier and cooler (est); a sideways push at the tilt axis that '
                   'lifts the box off its narrow edge'}
    fl = mech['flywheel']
    vmax = fl['no_load_rpm'] / 60 * math.pi * fl['d_mm'] * M * fl['efficiency_assumed']
    # the physics' ceiling (sim/turret_launch3d.py: the fastest swept ball at 100 % throttle, +5 % KV, +4 % rail, runout, tyre growth)
    l3 = json.loads((R / 'exports/turret/launch/launch3d.json').read_text())
    ceil = next((c for c in l3.get('ceiling_map', []) if c['rail_v'] == 12.0 and abs(c['wheel_d_mm'] - fl['d_mm']) < 0.1), None)
    ceil_txt = (f'{ceil["ceiling_fps"]} fps on Ø{fl["d_mm"]:.0f} tyres, docs/turret-physics.md section 4' if ceil else
                'docs/turret-physics.md section 4')
    overspeed = {'max_exit_mps': round(vmax, 1), 'max_fps': round(vmax / 0.3048), 'cap_mps': round(mech['ball']['cap_fps'] * 0.3048, 2),
                 'physics_ceiling_fps': ceil['ceiling_fps'] if ceil else None,
                 'note': f'the fixed 12 V flywheel rail is the ceiling: at the X2216s\' full no-load speed on it ({fl["no_load_rpm"]} rpm) a ball '
                         f'leaves at about {vmax:.0f} m/s by this page\'s rough model (the physics\' fastest ball at 100 % throttle on a fast '
                         f'motor and a high rail: {ceil_txt}), under the {mech["ball"]["cap_fps"]} fps cap; the barrel\'s two gates trip the '
                         f'safety line on any ball over 66 fps, and 24 V must never reach the ESCs'}
    tmg = mech['timing']
    rel = l3.get('release_phase_short') or {}
    b5 = round(rel.get('speed_5pct_at_ms') or 48)
    release = {'after_drop_ms': round(tmg['trigger_to_muzzle_ms'] - tmg['dial_to_exit_ms']), 'coast_s': fl['coast_down_s'],
               'note': f'a ball that has already dropped still fires up to {tmg["trigger_to_muzzle_ms"] - tmg["dial_to_exit_ms"]:.0f} ms after ARM '
                       f'is released; the phase-short brake (six FETs on the cartridge board, 5-14 ms after the line drops) stops the wheels to 5 % '
                       f'about {b5} ms after release (docs/turret-physics.md section 5), where unbraked they would coast {fl["coast_down_s"]} s',
               'brake_to_5pct_ms': b5, 'brake_tau_ms': rel.get('tau_ms_model')}
    checks = {'clearance': sw, 'muzzle_outside_deck_mm': ball_clear(T), 'ball_path': path_out, 'airflow': air, 'intake_seal': seal,
              'shroud_fit': fit, 'tipping': tip, 'overspeed': overspeed, 'release': release,
              'lid_screw': f'M3 x {tb.LID_SCREW_LEN:.0f} ISO 4762, tip at z {tb.LID_SCREW_TIP:.0f} (as the J501\'s own M3 x {tb.J["lid_screw_len"]:.0f})',
              'heights_mm': {'roof': tb.ROOF, 'deck_underside': tb.DECK_Z0, 'tm_face': tb.Z_TM,
                             'antenna_tops_over_tm_face': round(tb.antennas()[0][2][2] - tb.Z_TM, 1) if tb.antennas() else None},
              'too_big': too_big}
    print(f'  deck: min gap under the moving turret {sw["deck_min_gap_mm"]} mm (pan, tilt {sw["deck_worst_pose_deg"]}); at -25 deg the '
          f'ball leaves {checks["muzzle_outside_deck_mm"]} mm or more outside the deck\'s outline'
          + (f'; its 3D path clear at every pan and tilt ({path_out["file"]})' if path_out and path_out['clear'] else
             f'; the 3D ball path: {path_out["note"] if path_out else "not run (cad/turret_lidar.py --scene box)"}'))
    print(f'  antennas upright: closest {min(sw["antenna_min_gap_mm"].values())} mm; depression limited at pans {sw["antenna_limited_pans_deg"]}')
    print(f'  airflow: {air["loss_pa"]} Pa through the shroud, J501 fan flow -{air["flow_drop_pct"]} % (est, limit {air["limit_pct"]:.0f} %; '
          f'sensitivity {", ".join(f"{v} %" for v in air["sensitivity_flow_drop_pct"].values())})')
    print(f'  shroud: Ø{seal["collar_d_mm"]} collar, foam ring r {seal["tape_r_mm"][0]}-{seal["tape_r_mm"][1]}'
          + (f' (the grille\'s openings {seal["tape_margin_mm"]["to_the_grille_openings"]} mm inside it, the first open cell '
             f'{seal["tape_margin_mm"]["to_the_first_open_cell"]} mm outside)' if 'tape_margin_mm' in seal else '')
          + f'; clear of the legs and TM bosses by {fit["least_mm"]} mm (3 needed)')
    print(f'  tipping: {tip["total_kg"]} kg, centre of mass {tip["com_height_mm"]} mm up, a {tip["push_to_tip_n"]} N push at the tilt axis tips it')
    print(f'  flywheels {mech["flywheel"]["rpm"]:.0f} rpm, {mech["flywheel"]["energy_j_each"]} J each, -{mech["flywheel"]["speed_drop_per_shot_pct"]} % a shot, '
          f'back in {mech["flywheel"]["recovery_ms"]} ms; trigger to muzzle {mech["timing"]["trigger_to_muzzle_ms"]} ms; tilt hold '
          f'{mech["tilt"]["holding_nm"]} N.m ({mech["tilt"]["margin"]}x)')

    # ---- the ball's way through the turret (tilt frame, mm) and the balls in a full hopper
    tc = G.tilt_c
    path = [[round(G.exit_x, 2), 0.0, round(G.ball_z_dial - tc, 2)]]
    for k in range(1, 13):
        th = math.pi + k * (math.pi / 2) / 12
        path.append([round(G.chute_cx + G.chute_r * math.cos(th), 2), 0.0, round(G.chute_r + G.chute_r * math.sin(th) - tc, 2)])
    for x in (G.wheel_x - 7.25, G.wheel_x, G.wheel_x + 7.25, G.socket_x0, G.barrel_x0 + 30, G.barrel_x0 + 80, G.barrel_x1):
        path.append([round(x, 2), 0.0, round(-tc, 2)])
    rb = G.ball / 2
    pockets = [[round(G.rp * math.cos(math.radians(45 * k)), 2), round(G.rp * math.sin(math.radians(45 * k)), 2), round(G.ball_z_dial - tc, 2)]
               for k in range(G.n_pockets)]                                    # dial frame: pocket k at 45k deg
    pile = []
    z1 = G.dial_z0 + G.dial_h + rb + 0.5
    for z, rings in ((z1, ((13.0, 3, 0.0), (36.5, 9, 0.0))), (z1 + 17.0, ((0.0, 1, 0.0), (26.0, 7, 0.3), (37.0, 3, 0.9)))):
        for rr, n, a0 in rings:
            for k in range(n):
                ang = a0 + 2 * math.pi * k / n
                pile.append([round(rr * math.cos(ang), 2), round(rr * math.sin(ang), 2), round(z - tc, 2)])
    pile = pile[:30 - (G.n_pockets - 1)]

    # ---- callout anchors (in each part's group frame) and the ball's journey
    by = {p['name']: p for p in parts}

    def top_of(name, dx=0.0, dy=0.0, dz=0.0, side=None):
        b = by[name]['bbox']
        x, y = (b[0] + b[3]) / 2 + dx, (b[1] + b[4]) / 2 + dy
        if side == '-y':
            y = b[1] + dy
        return [round(x, 1), round(y, 1), round(b[5] + dz, 1)]
    anchors = {'hopper': top_of('hopper', -30, 0, -20, '-y'), 'dial': [-G.rp, -6.0, round(G.dial_z0 + 15 - tc, 1)],
               'feed_motor': [0.0, -12.0, round(G.floor_z - G.floor_t - 25 - tc, 1)], 'cartridge_body': [round(G.wheel_x, 1), round(-G.cage_y, 1), round(10 - tc, 1)],
               'flywheel_tyre': [0.0, 20.0, 0.0], 'barrel': [round(G.barrel_x1 - 20, 1), -15.0, round(-tc, 1)],
               'laser': [round(tu.LASER_X[1] + 12, 1), round(tu.LASER_Y, 1), round(-tc, 1)], 'cradle': [40.0, round(-G.cheek_y[1], 1), round(G.rail_z[0] + 2 - tc, 1)],
               'tilt_servo': [0.0, round(G.arm_y[1] + 15, 1), round(G.tilt_t, 1)], 'tilt_yoke': [0.0, round(-G.arm_y[1], 1), round(G.tilt_t - 40, 1)],
               'pan_ring': [0.0, -40.0, round(G.turntable_z[1] - 6, 1)], 'pan_pinion': [round(G.servo_pan_xy[0], 1), -14.0, round(G.turntable_z[1] - 4 + tb.Z_TM, 1)],
               'pan_servo': [round(G.servo_pan_xy[0], 1), 25.0, round(tb.Z_TM + 20, 1)], 'pan_bearing': [0.0, -32.0, round(tb.Z_TM + G.brg_z + 3, 1)],
               'pan_base': [30.0, -64.0, round(tb.Z_TM + 12, 1)], 'dt_receptacle': [0.0, round(-G.dt_y - 20, 1), round(tb.Z_TM + tu.DT_Z, 1)],
               'box_deck': [70.0, -100.0, round(tb.Z_TM - 4, 1)], 'intake_shroud': [round(tb.FRONT_X - 2, 1), 30.0, round(tb.ROOF + 18, 1)],
               'pod_pendant': [round(tb.POD_X[0] - 2, 1), next(y for n, y, *_ in tb.PANEL if n == 'pendant'), round(tb.POD_ZC, 1)],
               'cover': [0.0, -80.0, round(tb.ROOF, 1)]}
    for p in parts:
        if p['part'] in anchors and not p['name'].endswith('_m'):
            p['anchor'] = anchors[p['part']]
            p['callout'] = p['part'] in CALLOUTS
        if p['part'] == 'cover' and p['group'] == 'j501':
            p['anchor'], p['callout'] = anchors['cover'], True
    fl, fd, tm = mech['flywheel'], mech['feed'], mech['timing']
    fl_rows = mech['flight_level']['rows']
    at3 = next((r for r in fl_rows if r[0] == 3.0), fl_rows[-1])
    journey = [
        {'id': 'hopper', 'title': '1  Hopper', 'parts': ['hopper', 'hopper_lid', 'hopper_flap'], 'focus': [0.0, 0.0, round((G.dial_z0 + G.hopper_top) / 2 - tc, 1)],
         'text': f'Thirty balls (Ø{G.ball}, 1.83 g) wait in the clear hopper. Gravity drops them into the dial\'s pockets; the cone on top of the dial stirs the pile so they cannot bridge.'},
        {'id': 'dial', 'title': '2  Feed dial', 'parts': ['dial', 'feed_motor'], 'focus': [0.0, 0.0, round(G.ball_z_dial - tc, 1)],
         'text': f'A servo under the dial (the same STS3215 as pan and tilt) steps it 45 deg per ball in about {fd["step_ms_est"]:.0f} ms: '
                 f'{fd["rate_per_s"]} balls/s, {fd["max_rate_per_s"]} at most. It reads its own load, so it feels a jam and backs off. Parked, a spoke sits '
                 f'over the exit hole, so no ball can reach the wheels, powered or not.'},
        {'id': 'exit', 'title': '3  Exit hole', 'parts': ['cartridge_body', 'dial'], 'focus': [round(G.exit_x, 1), 0.0, round(G.ball_z_dial - tc, 1)],
         'text': f'At the front of the housing ({G.exit_x:.0f} mm ahead of the dial axis) a pocket passes over a hole in the floor and its ball drops out. '
                 f'About {tm["dial_to_exit_ms"]} ms from the command (the servo\'s step).'},
        {'id': 'chute', 'title': '4  Chute', 'parts': ['cartridge_body'], 'focus': [round(G.chute_cx - 8, 1), 0.0, round(G.chute_r / 2 - tc, 1)],
         'text': f'A quarter bend of radius {G.chute_r:.1f} mm turns the falling ball forward onto the path, {G.tilt_c:.0f} mm under the tilt axis. '
                 f'It takes about {tm["chute_ms"]} ms and reaches the wheels at {tm["speed_into_nip_mps"]} m/s.'},
        {'id': 'nip', 'title': '5  Flywheels', 'parts': ['flywheel', 'flywheel_tyre', 'flywheel_motor_l', 'flywheel_motor_r', 'esc_l', 'esc_r', 'cartridge_board'],
         'focus': [round(G.wheel_x, 1), 0.0, round(-tc, 1)],
         'text': f'Two Ø{G.wheel_d:.0f} wheels {fl["centres_mm"]:.0f} mm apart spin opposite ways at about {fl["rpm"]:,.0f} rpm ({fl["throttle_pct"]} % of the '
                 f'X2216\'s no-load speed on the 12 V rail). The gap is {fl["crush_mm"]} mm narrower than the ball ({fl["crush_pct"]} % squeeze), so it leaves at the tyres\' '
                 f'surface speed. Each wheel stores {fl["energy_j_each"]} J; a shot costs about {fl["speed_drop_per_shot_pct"]} % of its speed, back in '
                 f'{fl["recovery_ms"]} ms at a {fl["current_limit_a"]:.0f} A current limit.'},
        {'id': 'barrel', 'title': '6  Barrel', 'parts': ['barrel'], 'focus': [round(G.barrel_x0 + 50, 1), 0.0, round(-tc, 1)],
         'text': f'{G.barrel_len:.0f} mm long, bore Ø{G.bore_out:.1f}: 2 mm over the ball, so it only guides. Two IR gates 60 mm apart time every ball '
                 f'(a built-in chronograph); {tm["nip_to_muzzle_ms"]} ms from the nip to the muzzle.'},
        {'id': 'muzzle', 'title': '7  Muzzle', 'parts': ['barrel', 'laser', 'laser_mount'], 'focus': [round(G.barrel_x1, 1), 0.0, round(-tc, 1)],
         'text': f'{mech["ball"]["speed_mps"]} m/s ({mech["ball"]["fps"]} fps nominal; the kid-safety cap is {mech["ball"]["cap_fps"]}), {mech["ball"]["energy_j"]} J. The barrel can never point above '
                 f'level: hard stops at 0 and {G.tilt_min:.0f} deg in the yoke. About {tm["trigger_to_muzzle_ms"]} ms from the command to here.'},
        {'id': 'flight', 'title': '8  Flight', 'parts': [], 'focus': None,
         'text': f'Air drag and gravity: a level shot from the bench has dropped {at3[2]} mm at {at3[0]:.0f} m and slowed to {at3[3]} m/s. The laser is parallel to '
                 f'the barrel, so at range the ball lands under the dot.'},
    ]

    # ---- the manifest
    j501_info = {'revision': tb.J['revision'], 'built_for': tb.BUILT_FOR, 'source': tb.J['source'], 'parameters_git': tb.J.get('git'),
                 'warning': warn, 'cooler': tb.J['cooler'], 'fan': tb.J['fan_model'], 'fan_xy_box_mm': list(tb.FAN), 'roof_z_mm': tb.ROOF,
                 'intake': tb.J['intake'], 'meshes': j501_src}
    man = {'units': 'mm', 'frame': 'box: x forward (pan 0), y left, z up; origin on the desk under the pan axis. Each part is in its '
                    'group\'s frame (pivots); journey focus points and the ball path are in the tilt frame (origin on the tilt axis)',
           'built': time.strftime('%Y-%m-%d %H:%M'), 'z_tm': tb.Z_TM, 'roof_z': tb.ROOF,
           'box': {'x': [tb.REAR_X, tb.FRONT_X], 'y': [-tb.SIDE_Y, tb.SIDE_Y], 'z': [0.0, tb.ROOF], 'revision': tb.J['revision'], 'parts': j501,
                   'cooler': tb.J['cooler']},
           'j501': j501_info,
           'deck': {'x': list(tb.DECK_X), 'y': [-tb.SIDE_Y, tb.SIDE_Y], 'z': [tb.DECK_Z0, tb.Z_TM]},
           'fan': {'xy': list(tb.FAN), 'z': tb.ROOF, 'r': tb.COLLAR_R, 'collar_r': tb.COLLAR_R, 'hole_r': tb.HOLE_R, 'intake': tb.J['intake']['kind'],
                   'grille_x': tb.FRONT_X, 'mouth_half': tb.MOUTH_HALF, 'duct_z': [tb.SH_Z0 + tb.SH_FLOOR_T, tb.DECK_Z0], 'model': tb.J['fan_model']},
           'pivots': {'pan': list(pan_o), 'tilt': [0.0, 0.0, G.tilt_t], 'pinion': [G.servo_pan_xy[0], G.servo_pan_xy[1], tb.Z_TM],
                      'pinion_ratio': -G.gear['z_ring'] / G.gear['z_pinion'], 'dial': [0.0, 0.0, 0.0], 'wheel_l': list(wheel['wheel_l']),
                      'wheel_r': list(wheel['wheel_r']), 'flap': list(flap_hinge)},
           'limits': {'pan_deg': [-170.0, 170.0], 'tilt_deg': [G.tilt_min, 0.0], 'pan_rate_deg_s': mech['pan']['max_deg_s'],
                      'tilt_rate_deg_s': mech['tilt']['max_deg_s']},
           'muzzle': [G.barrel_x1, 0.0, -tc], 'laser': [tu.LASER_X[0] - 2 + tu.LASER['L'], tu.LASER_Y, -tc],
           'ball_path': path, 'pockets': pockets, 'pile': pile, 'ball_r': rb, 'dial_park_deg': fd['park_deg'],
           'antennas': [{'name': n, 'base': list(b), 'top': list(t), 'd': d} for n, b, t, d in tb.antennas()],
           'parts': parts, 'journey': journey, 'mechanics': mech, 'checks': checks,
           'masses_g': {'turret_with_balls': round(tot), 'adapter': round(adapter_g), 'j501_printed': j501_printed, 'j501_inside_est': j501_inside}}
    (SCENE / 'manifest.json').write_text(json.dumps(man, indent=1, default=float) + '\n')
    (OUT / 'box.json').write_text(json.dumps({'checks': checks, 'mechanics': mech, 'masses_g': man['masses_g'], 'z_tm_mm': tb.Z_TM,
                                              'j501': j501_info}, indent=1, default=float) + '\n')
    # ---- the parts list: every line a catalogue key with its price (D40), as the bench's (cad/build_turret.py)
    cat = _catalogue()

    def line(key, qty, use):
        it = cat.get(key) or {}
        buys = it.get('buy') or [{}]
        return {'item': it.get('name') or it.get('model') or key, 'key': key, 'qty': qty, 'for': use, 'part_number': it.get('model'),
                'vendor': it.get('vendor'), 'url': buys[0].get('url'), 'price_usd_each': it.get('price_usd'), 'pack_qty': it.get('pack_qty'),
                'sellers': [{k: b.get(k) for k in ('seller', 'url', 'price_usd', 'pack_qty', 'in_stock')} for b in buys if b.get('url')]}
    rows = [line(k, q, u) for k, q, u in BOX_BOUGHT]
    shared = [dict(line(k, 0, u), note='not bought again') for k, u in SHARED]
    keyed = {n: tb.POD_PARTS[n.removeprefix('pod_')][0] for n in tb.bought() if n.removeprefix('pod_') in tb.POD_PARTS}
    envelopes = [{'item': n, 'key': keyed.get(n, 'wago-221-413' if n == 'pod_wago' else 'turret_screw_m3x40' if n.startswith('lid_screw') else None),
                  'note': note, 'mass_g': m} for n, (_, m, note) in tb.bought().items()]
    (OUT / 'bom.json').write_text(json.dumps({
        'adapter': rows, 'shared_with_the_bench_stand': shared,
        'price_usd_known': round(sum((r['price_usd_each'] or 0) * r['qty'] for r in rows), 2),
        'not_in_a_catalogue': sorted({r['key'] for r in rows if r['key'] not in cat}),
        'no_listed_price': sorted({r['key'] for r in rows if r['key'] in cat and r['price_usd_each'] is None}),
        'modelled': envelopes,
        'note': 'what to buy for the box adapter (cad/turret_box.py): every line a catalogue key (catalog/turret.json, hardware.json, '
                'sourcing.json) with a listed price (D40); qty per adapter, packs bought whole; modelled: the envelopes the 3D page '
                'shows; the turret\'s own parts: exports/turret/bench/bom.json'}, indent=1) + '\n')
    size = sum(f.stat().st_size for f in SCENE.glob('*.stl'))
    print(f'adapter {sum(masses.values()):.0f} g PETG, {sum(p["hours"] for p in plan.values()):.1f} h; scene {len(parts)} meshes, '
          f'{size / 1e6:.1f} MB -> {SCENE}; {time.time() - t0:.0f} s')
    if warn:
        print(f'WARNING: {warn}')


if __name__ == '__main__':
    main()
