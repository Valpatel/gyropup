"""WIP construction operations tied to named CAD ownership, not display colours.

No CAD imports. Archived rig tightening/fit instructions are deliberately not
republished. Grouped source screw envelopes remain grouped source identities.
"""
from __future__ import annotations
import math

BODY = 'hardware/cad/body/body_frame.py'
LEG = 'hardware/cad/legs/fivebar.py'
COLLECTOR = 'tools/engineering/robot/robot_view.py'
WARNING = ('WIP CAD assembly study. The order explains named construction relationships; '
           'it is not a qualified fastening, fit, wiring or powered-operation procedure.')


def operation(key, title, parts, source, text, chapter, direction=(1, -1, .7), offset=(0, 0, 50), offsets=None):
    return dict(id=key, title=title, additions=parts, source_operation=source,
                text=text, subassembly=chapter, camera=dict(direction=list(direction)), offset=list(offset),
                offsets=dict(offsets or {}))


def body_operations():
    """Named frame/layout construction records, with closures deliberately last."""
    return [
        operation('body-spine', 'Body spine and hip mounting faces',
                  ['cheek_left', 'cheek_right', 'spacers', 'spacer_screws'],
                  BODY+'::frame_parts / place_cheek',
                  'Locate the two physical cheek faces and their connecting spacer envelopes. '
                  'Their CAD mounting holes establish the left/right hip-module datums.', 'body'),
        operation('body-trays', 'Floor tray above the spine', ['floor_tray'], BODY+'::frame_parts',
                  'The floor tray approaches the top of the spine. Its rendering does not qualify the fasteners.', 'body'),
        operation('body-belly', 'Belly plate below the spine', ['belly_plate'], BODY+'::frame_parts',
                  'The belly plate approaches from below; the printed leg interfaces remain unchanged.', 'body', offset=(0, 0, -188)),
        operation('body-end-supports', 'Conditional end-pack holders and rigid sit feet',
                  ['end_pack_holder_front', 'end_pack_holder_rear', 'end_foot_front', 'end_foot_rear'],
                  'hardware/cad/body/body_battery.py::end_parts',
                  'These body-side supports approach from below. Purchased adapter mounting, loads and drop/retention qualification remain unresolved.',
                  'body', offset=(0, 0, -188)),
        operation('body-platforms', 'Compute and power support platforms',
                  [*[f'post_{i}' for i in range(1, 5)], *[f'isolator_{i}' for i in range(1, 5)],
                   'compute_pallet', *[f'plate_post_{i}' for i in range(1, 5)], 'power_plate', 'dcdc_bracket',
                   'bus_insulator_1', 'bus_insulator_2', 'bus_bar_1', 'bus_bar_2'],
                  BODY+'::frame_parts / place_plate',
                  'Identify the support posts, isolated compute pallet and separate power platform. '
                  'Bus insulators and conductors remain individually identified; this is not electrical approval.', 'body'),
    ]


def leg_operations(side):
    if side not in ('L', 'R'):
        raise ValueError('Unknown physical leg side')
    label = 'Left' if side == 'L' else 'Right'
    chapter = side.lower()+'-leg'
    def names(*items): return [side+'.'+n for n in items]
    def add(key, title, parts, function, text, offsets=None):
        return operation(side.lower()+'-'+key, label+' '+title, parts, LEG+'::'+function,
                         text, chapter, direction=(1, 1 if side == 'L' else -1, .45),
                         offset=(0, 60 if side == 'L' else -60, 0), offsets=offsets)
    return [
        add('motors', 'stationary motor cases',
            names('motor_front', 'motor_rear'), 'bought_parts',
            'Present the two motor cases before the hip support closes around them. '
            'Their outward arrival avoids passing the cases through the already-installed hip web; '
            'the cases still need temporary support. This is a WIP presentation dependency, not a fixture procedure.'),
        add('hip', 'hip frame, support bearings and lug screw group',
            names('hip_frame', 'bearing_61812_front', 'bearing_61812_rear')+
            ['frame_screws_'+('left' if side == 'L' else 'right'), 'cheek_nuts_'+('left' if side == 'L' else 'right')]+
            names('screws_lugs'),
            'assembly / bought_parts / screw_groups; '+BODY+'::frame_parts / legs',
            'Locate the hip frame around the motor cases, then show its support bearings and retained screw groups. '
            'Lug screws follow the support and precede the upper links. The source flange screw group remains a group; '
            'bearing fits, driver access, temporary support and insert retention are unverified. No torque is specified.'),
        add('upper', 'output adapters and upper links',
            names('output_adapter_front', 'output_adapter_rear', 'screws_outputs', 'upper_link_front', 'upper_link_rear', 'screws_links'),
            'assembly / link_frames / screw_groups',
            'Each output adapter and its upper link share the authored rotating-link frame. '
            'The output screw group precedes the upper links so it does not arrive through their hubs. '
            'The front and rear instances are distinct; source screw groups are not individual manufactured screw models.'),
        add('front-knee', 'front knee and lower link',
            names('front_link', 'knee_bearing_front_in', 'knee_bearing_front_out', 'knee_spacer_front',
                  'eye_sleeve_front', 'knee_washer_front', 'knee_pin_front', 'knee_nut_upper_front'),
            'assembly / bought_parts / link_frames',
            'The current source uses the 6301 knee cartridge in the front lower link, with separate spacer, '
            'eye sleeve, washer, shoulder-pin and nut identities. The pin connects the upper eye and lower knee; '
            'the archived 6201-era display is not substituted for this geometry. The inboard bearing is blocked by '
            'the lower-link shoulder from outside and the upper eye from inside; this arrival remains illustrative pending subassembly validation.'),
        add('rear-knee', 'rear knee and wheel-carrying lower link',
            names('wheel_link', 'knee_bearing_rear_in', 'knee_bearing_rear_out', 'knee_spacer_rear',
                  'eye_sleeve_rear', 'knee_washer_rear', 'knee_pin_rear', 'knee_nut_upper_rear'),
            'assembly / bought_parts / link_frames',
            'Identify the second knee cartridge and the separate wheel-carrying lower link. '
            'Its parent/axis comes from the rear upper-link endpoint; it is not attached to the front knee.'),
        add('apex', 'apex connection and loop closure',
            names('apex_spacer', 'apex_61812', 'apex_circlip'), 'assembly / bought_parts / link_frames',
            'The two lower links meet at the source five-bar apex. The spacer, paired-bearing envelope '
            'and circlip remain separate CAD identities. The rigid circlip envelope overlaps its final groove; '
            'its illustrated arrival does not model circlip expansion. This closure does not prove physical fit or free motion.'),
        add('wheel', 'wheel hub, tyre and retained screw groups',
            names('wheel_hub', 'wheel_tyre', 'washers_wheel', 'screws_wheel'), 'bought_parts / screw_groups; hardware/cad/body/body_params.py::_fivebar (D69 override)',
            'The collected wheel hub and tyre share the authored apex/wheel datum. The D69 body collection uses '
            'a 254 mm diameter, 64 mm wide envelope; its ordered SKU and physical dimensions remain unverified. '
            'Keep the wheel-fastener and washer '
            'source groups visible as groups. Washers precede screws, arriving from the inboard side of the hub as in '
            'the source screw stack. Thread engagement, wiring and tightening remain unqualified.',
            offsets={side+'.'+n: [0, -60 if side == 'L' else 60, 0] for n in ('washers_wheel', 'screws_wheel')}),
        add('stops', 'stop posts and four sleeves',
            names('stop_posts', *[f'stop_sleeve_{i}' for i in range(1, 5)]), 'assembly / bought_parts / stop_posts',
            'Show the fixed stop-post group and four separate sleeve instances after the motor-access stages. '
            'Their CAD position is not a release to bond, preload or power the mechanism.'),
    ]


def finishing_operations():
    return [
        operation('body-compute', 'Compute stack and sensor envelopes',
                  ['item.j501_carrier', 'item.agx_module', 'item.agx_spreader', 'item.agx_cooler',
                   'item.j501_standoff_15_16.5', 'item.j501_standoff_165_16.5', 'item.j501_standoff_15_146.5', 'item.j501_standoff_165_146.5',
                   'item.lidar_box', 'item.lidar_coil', 'd435_cradle_front', 'd435_cradle_rear', 'd435_front', 'd435_rear',
                   'eyes_board', 'eyes_clip', 'ear_bracket_l', 'ear_bracket_r', 'ear_pod_l', 'ear_pod_r', 'item.vn100'],
                  'hardware/cad/builders/build_body.py::_layout; hardware/cad/body/body_shell.py::shell_parts',
                  'Locate the tracked J501/AGX assembly and the individually named sensor mounts/envelopes. '
                  'The robot model uses the tracked parameter snapshot; supplier dimensions and cable access are separate checks.', 'body'),
        operation('body-power', 'Power electronics envelopes',
                  ['item.plate_vesc_r', 'item.plate_vesc_l', 'item.plate_main_switch', 'item.plate_shunt',
                   'item.power_dcdc', 'item.plate_mrbf_block', 'item.plate_fuses', 'item.plate_mcu_board', 'item.plate_buck_5v'],
                  'hardware/cad/builders/build_body.py::_layout; hardware/cad/body/body_layout.py::layout',
                  'These are source layout envelopes on the power platform and the conditional front/rear drop-in mounts. '
                  'No adapter purchase/fit, series wiring, charging or hot-swap architecture is selected by this view.', 'body'),
        *[operation(f'body-adapter-{end}', f'{end.title()} Azocek adapter reservation', [f'item.battery_adapter_{end}'],
                    'hardware/cad/body/body_battery.py::adapter_boxes',
                    'Conditional unmeasured outline only. Mounting holes, rail, latch, ratings and positive retention remain unresolved.',
                    'body', offset=(sign*80, 0, 0)) for end, sign in [('front', 1), ('rear', -1)]],
        operation('body-packs', 'Front/rear vertical drop-in pack envelopes', ['item.battery_front', 'item.battery_rear'],
                  'hardware/cad/body/body_battery.py::pack_boxes',
                  'Both packs approach down from the +188 mm reservation and remove upward. This does not establish actual rail or latch travel.',
                  'body', offset=(0, 0, 188)),
        operation('body-deck', 'Deck, turret plate and lidar mounting datum',
                  ['deck', 'turret_plate', 'turret_plate_nuts', 'riser', 'item.vlp16_window', 'item.vlp16_housing'],
                  BODY+'::frame_parts; '+COLLECTOR+'::lidar_shapes',
                  'Locate the deck, source turret support plate/riser and lidar geometry. '
                  'The TM mounting face and pan-axis X coordinate are recorded from body_params.tm(), not the archived playground.', 'body'),
        operation('body-covers', 'Enclosure reference',
                  ['shell_side_l_front', 'shell_side_l_rear', 'shell_side_r_front',
                   'shell_side_r_rear', 'shell_front', 'shell_rear', 'shell_door', 'shell_hatch', 'fan_duct'],
                  BODY+'::all_parts; hardware/cad/body/body_shell.py::shell_parts',
                  'The final reference includes the modeled doors and shell panels. Explanatory explosion is not '
                  'a validated insertion path; keep access and fastening work unresolved.', 'body'),
    ]


def robot_operations():
    return body_operations()+leg_operations('L')+leg_operations('R')+finishing_operations()


def validate_operations(operations, available):
    """Reject silent omissions and double-assignment before guide generation."""
    available = set(available)
    seen = set()
    for op in operations:
        names = op['additions']
        if not names or len(names) != len(set(names)) or set(names)-available or seen.intersection(names):
            raise ValueError('Unknown, duplicate or multiply assigned operation parts: '+op['id'])
        overrides = op.get('offsets', {})
        if (set(overrides)-set(names) or any(not isinstance(v, (list, tuple)) or len(v) != 3
                or any(not isinstance(n, (int, float)) or not math.isfinite(n) for n in v)
                for v in [op['offset'], *overrides.values()])):
            raise ValueError('Unknown or invalid operation offset: '+op['id'])
        seen.update(names)
    if seen != available:
        raise ValueError('Unassigned robot parts: '+', '.join(sorted(available-seen)))
    return seen
