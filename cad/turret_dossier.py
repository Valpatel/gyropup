"""The turret's geometry for its design dossier (cad-agent's process: dossier/, `cad-agent gates`, `cad-agent check`).

Declares, on cadagent.dossier's registry, everything the gates read and the YAML dossier (dossier/project.yaml,
dossier/sections/*.yaml) is joined to by id:

  parts       every part of cad/turret.py (made and bought) placed at home (pan 0, tilt 0, the dial parked) in the T
              frame (mm, the TM mounting face at z = 0, robot=False), the mirrored flywheel pair (flywheel_m,
              flywheel_tyre_m), the rotor's leads merged into the rotor (turret_gates.MERGED); the 30 balls of the
              physics-settled pile (exports/turret/feed/pile.json) as one free part `ball`; the stand (cad/turret_stand.py)
              under the compute plinth (D66: the turret on its own, as it is built and tested first)
  cavity      hopper_cavity on the hopper (turret_gates.hopper_cavity: the dial wall's cylinder from the floor to the lid,
              less every tilt-frame solid, the dial parked)
  joints      the aim (I-pan carrying I-tilt), the mechanisms on the cartridge (I-feed, I-wheel-l, I-wheel-r, I-flap), the
              pinion (I-pan-drive), and the fixed joints that make each moving body (a part rides with a body only through
              a declared fixed joint or fastener: cadagent.gates.relations.moving_bodies)
  fasteners   cad/turret.py GATED_SCREWS: the laser holder's and the hopper's M3 socket heads into modelled inserts
  assembly    the build order, with the direction each part moves to its seat

The chain rule. cadagent puts a part in a moving body only by growing from the joint's moving part across fixed joints and
fasteners, and stops at every non-fixed joint's fixed part. So in a chain each child joint must name the parent's moving
part itself as its fixed part (docs/gates.md, "What moves"): the tilt joint hangs on pan_ring (I-pan's moving part), and the
feed, the flywheels and the flap hang on cartridge_body (I-tilt's moving part). Their measured gaps are then from those
parts, not from the bearings that carry them, so those interfaces declare a clearance that covers the gap (dossier/
project.yaml says which; reported on Valpatel/cad-agent#39). The real bearing pairs are the joints' intended contacts.

    .venv/bin/cad-agent gates --build          # builds this (cad: gates: build:) and runs every gate and the lint
    .venv/bin/python cad/turret_dossier.py     # just the geometry record: exports/dossier-geometry.json
"""
from __future__ import annotations

import sys
from pathlib import Path

import cadquery as cq

from cadagent import dossier as cd
from cadagent.dossier import Axis
from cadagent.fasteners import socket_head_envelope

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import turret as tu            # noqa: E402
import turret_gates as tg      # noqa: E402
import turret_stand as ts      # noqa: E402

LAYOUT = {'bodyTop': 100.0}

# section of every registered part (dossier/sections/<id>.yaml; docs/turret-sections.md 1-8)
SECTIONS = {
    'S1-base': ['pan_base', 'pan_clamp', 'pan_bearing', 'pan_bearing_inner', 'pan_ring', 'pan_spacer', 'circlip_50',
                'pan_pinion', 'pan_servo', 'bumper_ring', 'index_magnet', 'hall_switch'],
    'S2-tilt': ['tilt_yoke', 'cradle', 'cradle_plate_l', 'cradle_plate_r', 'stop_lug', 'horn_boss', 'pivot_spacer',
                'tilt_servo', 'tilt_bearing', 'tilt_bearing_inner', 'shoulder_screw', 'ct_thumbscrew'],
    'S3-feed': ['dial', 'hopper', 'hopper_lid', 'hopper_flap', 'feed_motor', 'hopper_inserts', 'ball'],
    'S4-launcher': ['cartridge_body', 'flywheel', 'flywheel_m', 'flywheel_tyre', 'flywheel_tyre_m', 'flywheel_motor_l',
                    'flywheel_motor_r', 'esc_l', 'esc_r', 'cartridge_board'],
    'S5-barrel': ['barrel', 'laser_mount', 'laser', 'laser_screws', 'laser_inserts'],
    'S6-wiring': ['slip_ring', 'slip_ring_rotor', 'ring_carrier', 'ring_driver', 'ring_coupling', 'board_bay',
                  'board_bay_lid', 'turret_board', 'base_board', 'dt_receptacle', 'dt_plug'],
    'S7-compute': ['compute_tray', 'compute_shell', 'compute', 'eth_jack', 'xt30_input', 'input_fuses'],
    'S8-stand': ['stand_box', 'stand_bottom', 'stand_foot', 'dock', 'pack', 'terminal_board', 'usb_can',
                 'panel_switch', 'panel_pendant'],
}
SECTION_OF = {p: s for s, ps in SECTIONS.items() for p in ps}
GROUNDED = 'compute_tray'          # the plinth's floor: bolted to the head's TM face, or to the stand's top
FREE = {'ball': 'a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper\'s cavity',
        'dt_plug': 'the robot harness\'s plug, a separate cable plugged into the receptacle (absent on the stand)'}

# the moving joints. clearance: a declared gap (dossier interface) where the chain rule measures the hold from a part that
# is not the bearing (see the module docstring); the toolkit's 1 mm otherwise
SAMPLES = {'I-pan': 35, 'I-tilt': 6, 'I-feed': 16, 'I-wheel-l': 13, 'I-wheel-r': 13, 'I-flap': 6, 'I-pan-drive': 13}
FLAP_RANGE = (-50, 0)      # its knuckle meets the lid at 51 deg (turret/program 8016d3e, the motion gate's onset): the stop

# fixed joints: (interface id, part, carrier): the part rides with its carrier's body. Every one is a mounting interface
# of cad/turret.py's part notes; the interface's kind and datum are in the dossier.
FIXED = [
    # the pan body (seed pan_ring, I-pan's moving part)
    ('I-turntable', 'pan_bearing_inner', 'pan_ring'), ('I-spacer', 'pan_spacer', 'pan_bearing_inner'),
    ('I-circlip', 'circlip_50', 'pan_ring'), ('I-yoke', 'tilt_yoke', 'pan_ring'), ('I-driver', 'ring_driver', 'pan_ring'),
    ('I-coupling', 'ring_coupling', 'ring_driver'), ('I-rotor', 'slip_ring_rotor', 'ring_coupling'),
    ('I-hall', 'hall_switch', 'pan_ring'), ('I-bay', 'board_bay', 'tilt_yoke'), ('I-bay-lid', 'board_bay_lid', 'board_bay'),
    ('I-boards', 'turret_board', 'board_bay'), ('I-tilt-servo', 'tilt_servo', 'tilt_yoke'),
    ('I-tilt-outer', 'tilt_bearing', 'tilt_yoke'),
    # the tilt body (seed cartridge_body, I-tilt's moving part)
    ('I-ct', 'cradle', 'cartridge_body'), ('I-plate-l', 'cradle_plate_l', 'cradle'), ('I-plate-r', 'cradle_plate_r', 'cradle'),
    ('I-horn-boss', 'horn_boss', 'cradle_plate_l'), ('I-pivot-spacer', 'pivot_spacer', 'cradle_plate_r'),
    ('I-shoulder', 'shoulder_screw', 'cradle_plate_r'), ('I-tilt-inner', 'tilt_bearing_inner', 'shoulder_screw'),
    ('I-stop-lug', 'stop_lug', 'cradle_plate_r'), ('I-thumbscrew', 'ct_thumbscrew', 'cradle'),
    ('I-hopper-inserts', 'hopper_inserts', 'cartridge_body'), ('I-lid', 'hopper_lid', 'hopper'),
    ('I-barrel', 'barrel', 'cartridge_body'), ('I-laser-inserts', 'laser_inserts', 'cartridge_body'),
    ('I-set-screws', 'laser_screws', 'laser_mount'), ('I-laser', 'laser', 'laser_screws'),
    ('I-feed-servo', 'feed_motor', 'cartridge_body'), ('I-motor-l', 'flywheel_motor_l', 'cartridge_body'),
    ('I-motor-r', 'flywheel_motor_r', 'cartridge_body'), ('I-esc-l', 'esc_l', 'cartridge_body'),
    ('I-esc-r', 'esc_r', 'cartridge_body'), ('I-cart-board', 'cartridge_board', 'cartridge_body'),
    ('I-pile', 'ball', 'hopper'),
    # each flywheel body (seed the hub)
    ('I-tyre-l', 'flywheel_tyre', 'flywheel'), ('I-tyre-r', 'flywheel_tyre_m', 'flywheel_m'),
]

SCREW = {'d': 3.0, 'head_d': 5.5, 'head_h': 3.0, 'pitch': 0.5}       # ISO 4762 M3 socket heads (the gated screws)
FASTENER_VIA = {'laser_foot_screws': 'I-laser-foot', 'hopper_screws': 'I-hopper-lugs'}


def tilt_home(G):
    """The tilt frame's home translation in T: the C origin at (-tilt_x, 0, path_t)."""
    return (-G.tilt_x, 0.0, G.path_t)


def c_to_t(G, p):
    h = tilt_home(G)
    return (p[0] + h[0], p[1] + h[1], p[2] + h[2])


def _shape(s):
    return s.val() if hasattr(s, 'val') else s


def register(reg, T, pile):
    """Declare the turret on registry `reg`: T a tu.Turret, pile the settled load (turret_gates.load_pile)."""
    G = T.G
    park = pile['park_deg']
    home = tilt_home(G)

    # parts at home: the tilt frame placed by a translation (so the cavity follows the hopper)
    for name, (s, frame) in tg.parts_local(T, park).items():
        reg.add_part(name, _shape(s), section=SECTION_OF[name], place=home if frame == 'tilt' else None,
                     grounded=name == GROUNDED, free=name in FREE, reason=FREE.get(name, ''))
    r = G.ball / 2
    reg.add_part('ball', tg.sphere(r), section=SECTION_OF['ball'], place=[c_to_t(G, c) for c in tg.hopper_balls(pile)],
                 free=True, reason=FREE['ball'])
    reg.add_cavity('hopper', 'hopper_cavity', tg.hopper_cavity(T, park))

    # the stand under the plinth: its top (z 0 in turret_stand) carries the plinth's floor (D66)
    down = (0.0, 0.0, -tu.PLINTH['h'])
    for name, s in ts.parts().items():
        reg.add_part(name, _shape(s), section='S8-stand', place=down)
    bought = ts.bought()
    reg.add_part('stand_foot', [_shape(bought.pop(f'foot_{k}')[0]) for k in (1, 2, 3, 4)], section='S8-stand', place=down)
    for name, (s, _m, _n) in bought.items():
        reg.add_part(name, _shape(s), section='S8-stand', place=down)

    # the aim: pan carries tilt (the tilt joint hangs on pan_ring, I-pan's moving part)
    reg.joint('I-pan', 'revolute', parts=('pan_ring', 'pan_bearing'), axis=((0, 0, 0), (0, 0, 1)), range_deg=(-170, 170),
              samples=SAMPLES['I-pan'],
              intended_contacts=[('pan_bearing_inner', 'pan_bearing'), ('slip_ring_rotor', 'slip_ring'),
                                 ('pan_spacer', 'pan_bearing'), ('ring_coupling', 'slip_ring')])
    # tilt 0 to -25 deg (muzzle down) = a turn of 0..25 deg about +y at the tilt axis
    reg.joint('I-tilt', 'revolute', parts=('cartridge_body', 'pan_ring'), axis=((0, 0, G.tilt_t), (0, 1, 0)),
              range_deg=(0, -G.tilt_min), samples=SAMPLES['I-tilt'],
              intended_contacts=[('horn_boss', 'tilt_servo'), ('stop_lug', 'tilt_yoke'), ('shoulder_screw', 'tilt_yoke'),
                                 ('tilt_bearing_inner', 'tilt_bearing'), ('shoulder_screw', 'tilt_bearing'),
                                 ('pivot_spacer', 'tilt_bearing'), ('pivot_spacer', 'tilt_yoke')])
    # the mechanisms on the cartridge (each hangs on cartridge_body, I-tilt's moving part)
    reg.joint('I-feed', 'revolute', parts=('dial', 'cartridge_body'), axis=(c_to_t(G, (0, 0, 0)), (0, 0, 1)),
              range_deg=(0, 90), samples=SAMPLES['I-feed'], intended_contacts=[('dial', 'feed_motor')])
    for jid, hub, motor, sgn in (('I-wheel-l', 'flywheel', 'flywheel_motor_l', 1), ('I-wheel-r', 'flywheel_m', 'flywheel_motor_r', -1)):
        reg.joint(jid, 'revolute', parts=(hub, 'cartridge_body'), axis=(c_to_t(G, (G.wheel_x, sgn * G.wheel_y, 0)), (0, 0, 1)),
                  range_deg=(0, 360), samples=SAMPLES[jid], intended_contacts=[(hub, motor)])
    reg.joint('I-flap', 'revolute', parts=('hopper_flap', 'cartridge_body'),
              axis=(c_to_t(G, (tu.FILL_PORT[0] - 19, 0, G.hopper_top + 6)), (0, 1, 0)), range_deg=FLAP_RANGE,
              samples=SAMPLES['I-flap'], intended_contacts=[('hopper_flap', 'hopper_lid')])
    sx, sy = G.servo_pan_xy
    reg.joint('I-pan-drive', 'revolute', parts=('pan_pinion', 'pan_servo'), axis=((sx, sy, 0), (0, 0, 1)),
              range_deg=(0, 360), samples=SAMPLES['I-pan-drive'], intended_contacts=[('pan_pinion', 'pan_servo')])
    # the rigid mounts that make the moving bodies
    for jid, part, carrier in FIXED:
        reg.joint(jid, 'fixed', parts=(part, carrier), axis=((0, 0, 0), (0, 0, 1)))

    # the gated screws (turret.GATED_SCREWS) with their modelled inserts
    for name, spec in tg.fastener_specs(T).items():
        reg.fastener(spec.key, clamps=spec.clamps, into=spec.into, name=name, via=FASTENER_VIA[name], tool='hex 2.5',
                     at=[Axis(o, d) for o, d in spec.axes], length_mm=spec.length_mm, diameter_mm=SCREW['d'],
                     thread_start_mm=spec.thread_start_mm, thread_depth_mm=tu.INSERT_M3['l'],
                     shape=socket_head_envelope(SCREW['d'], spec.length_mm, SCREW['head_d'], SCREW['head_h']))

    for order, (fit, onto, direction, extra) in enumerate(ASSEMBLY, start=1):
        reg.assembly.step(order, fit, onto, direction=direction, **extra)


# The build order, read from the top: the cartridge is built on the bench first; then each group below it meets it from
# below (+Z), which for cadagent's straight-line check is the same relative motion as lowering the upper group onto it
# (the cartridge onto the cradle's rails, the cradle into the yoke, the yoke onto the turntable, the turntable into the
# base, the base onto the plinth, the plinth onto the stand). Each step: (part, onto, the direction it moves to its
# seat, {tool, fasteners}). cadagent fits one part at a time along a straight line, so a part fitted inside a group
# before the group meets the next (the tilt bearing, pressed into the arm before the cradle goes in), a cable (the rotor's
# leads) and the poured load are not straight insertions here: their steps fail, and docs/turret-sections.md says why.
SCREWS = {'tool': 'hex 2.5'}
ASSEMBLY = [
    # the cartridge, on the bench
    ('cartridge_body', None, '-Z', {}),
    ('feed_motor', 'cartridge_body', '+Z', {}),
    ('flywheel_motor_l', 'cartridge_body', '+Z', {}),
    ('flywheel_motor_r', 'cartridge_body', '+Z', {}),
    ('flywheel', 'flywheel_motor_l', '+Z', {}),
    ('flywheel_tyre', 'flywheel', '+Z', {}),
    ('flywheel_m', 'flywheel_motor_r', '+Z', {}),
    ('flywheel_tyre_m', 'flywheel_m', '+Z', {}),
    ('dial', 'feed_motor', '-Z', {}),
    ('hopper_inserts', 'cartridge_body', '-Z', {}),
    ('hopper', 'cartridge_body', '-Z', {**SCREWS, 'fasteners': ['hopper_screws']}),
    ('ball', 'dial', '-Z', {}),
    ('hopper_lid', 'hopper', '-Z', {}),
    ('hopper_flap', 'hopper_lid', '-Z', {}),
    ('barrel', 'cartridge_body', '-X', {}),
    ('laser_inserts', 'cartridge_body', '-Z', {}),
    ('laser_mount', 'cartridge_body', '-Z', {**SCREWS, 'fasteners': ['laser_foot_screws']}),
    ('laser_screws', 'laser_mount', '-Z', {}),
    ('laser', 'laser_mount', '-X', {}),
    ('esc_l', 'cartridge_body', '-Z', {}),
    ('esc_r', 'cartridge_body', '-Z', {}),
    ('cartridge_board', 'cartridge_body', '-Z', {}),
    # the cradle under it (the cartridge onto the rails), then the yoke round the cradle
    ('cradle', 'cartridge_body', '+Z', {}),
    ('ct_thumbscrew', 'cradle', '+Z', {}),
    ('cradle_plate_l', 'cradle', '-Y', {}),
    ('horn_boss', 'cradle_plate_l', '-Y', {}),
    ('cradle_plate_r', 'cradle', '+Y', {}),
    ('stop_lug', 'cradle_plate_r', '+Y', {}),     # screwed to the plate before the cradle is hung in the yoke
    ('tilt_yoke', 'cradle', '+Z', {}),
    ('tilt_servo', 'tilt_yoke', '-Y', {}),
    ('tilt_bearing', 'tilt_yoke', '+Y', {}),
    ('tilt_bearing_inner', 'tilt_bearing', '+Y', {}),
    ('pivot_spacer', 'cradle_plate_r', '-Z', {}),
    ('shoulder_screw', 'cradle_plate_r', '+Y', {}),
    ('board_bay', 'tilt_yoke', '+Y', {}),
    ('turret_board', 'board_bay', '+Y', {}),
    ('board_bay_lid', 'board_bay', '+Y', {}),
    # the turntable under the yoke, its bearing, then the base round it
    ('pan_ring', 'tilt_yoke', '+Z', {}),
    ('ring_driver', 'pan_ring', '+Z', {}),
    ('ring_coupling', 'ring_driver', '+Z', {}),
    ('hall_switch', 'pan_ring', '+Z', {}),
    ('pan_bearing_inner', 'pan_ring', '+Z', {}),
    ('pan_clamp', 'pan_ring', '+Z', {}),
    ('pan_bearing', 'pan_bearing_inner', '+Z', {}),
    ('index_magnet', 'pan_clamp', '+Z', {}),
    ('pan_spacer', 'pan_bearing_inner', '+Z', {}),
    ('circlip_50', 'pan_ring', '+Z', {}),
    ('pan_pinion', 'pan_ring', '+Z', {}),
    ('pan_servo', 'pan_pinion', '+Z', {}),
    ('slip_ring_rotor', 'ring_coupling', '+Z', {}),
    ('slip_ring', 'slip_ring_rotor', '+Z', {}),
    ('base_board', 'pan_bearing', '+Z', {}),
    ('pan_base', 'pan_bearing', '+Z', {}),
    ('ring_carrier', 'pan_base', '+Z', {}),
    ('bumper_ring', 'pan_base', '+Z', {}),
    ('dt_receptacle', 'pan_base', '+Y', {}),
    # the plinth under the base, then the stand under the plinth
    ('compute_shell', 'pan_base', '+Z', {}),
    ('compute', 'compute_shell', '+Z', {}),
    ('input_fuses', 'compute_shell', '+Z', {}),
    ('eth_jack', 'compute_shell', '+X', {}),
    ('xt30_input', 'compute_shell', '+X', {}),
    ('compute_tray', 'compute_shell', '+Z', {}),
    ('stand_box', 'compute_tray', '+Z', {}),
    ('dock', 'stand_box', '+Z', {}),
    ('terminal_board', 'stand_box', '+Z', {}),
    ('usb_can', 'stand_box', '+Z', {}),
    ('panel_switch', 'stand_box', '-X', {}),
    ('panel_pendant', 'stand_box', '-X', {}),
    ('stand_bottom', 'stand_box', '+Z', {}),
    ('stand_foot', 'stand_bottom', '+Z', {}),
    ('pack', 'stand_bottom', '+X', {}),
    ('dt_plug', 'dt_receptacle', '+Y', {}),
]
assert len(ASSEMBLY) == 72, len(ASSEMBLY)


def turret():
    return tu.Turret(LAYOUT)


T = turret()
register(cd.current_registry(), T, tg.load_pile(T.G))

if __name__ == '__main__':
    res = cd.build()
    print(f'{len(res.geometry["parts"])} parts, {len(res.geometry["joints"])} joints, '
          f'{len(res.geometry["fasteners"])} fastener groups, {len(res.geometry["assembly"]["steps"])} steps -> {res.path}')
