"""The leg rig's assembly, step by step, with a picture of each step from the CAD (docs/leg-prototype-plan.md section
6.4 and task T13; the turret's cad/turret_assembly.py pattern).

    .venv/bin/python cad/rig_assembly.py

Each step adds parts to what is already built: the new parts in colour, lifted along the way they go in, what is already
fitted in grey. Writes exports/rig/assembly/step-NN.png, steps.json and docs/leg-rig-assembly.md (the written order;
every part number is in docs/leg-rig-orders.md, the torques in the step text).

The order: the rig's frame (it needs only bought parts and a few prints), the leg's upper half on the bench, that half
onto the carriage, the electrics and the zeroing of the motors with each upper link on its bare steel stop post, then
the knees, the apex, the wheel, the TPU sleeves, the ballast and the tethers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cadquery as cq

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import build_rig as br  # noqa: E402
import fivebar as fb  # noqa: E402
import rig_parts as rp  # noqa: E402

OUT = R / 'exports' / 'rig' / 'assembly'
GREY = (0.78, 0.79, 0.81)
ZH = br.zh_on_deck(300.0)
LEG_VIEW = (0.85, 1.0, 0.55)


def _bare_travel() -> float:
    import math
    sys.path.insert(0, str(R))
    from rig.calibrate import bare_stop_angles
    fo, fi, _, _ = bare_stop_angles()
    return abs(math.degrees(fi - fo))


BARE_TRAVEL = _bare_travel()
RIG_VIEW = (1.0, 0.85, 0.45)
BACK_VIEW = (-0.6, -1.0, 0.45)

# (title, parts added, lift per part (mm along z, or a vector), view, where ('leg': the leg alone, its module frame;
#  'rig': the rig, the carriage at ZH), what to do)
STEPS = [
    ('The base frame', ['side_left', 'side_right', 'front_member', 'wheel_member', 'bumper_member', 'post_member', 'rear_member'],
     {}, RIG_VIEW, 'rig',
     'On the rubber mat: the two 900 mm sides, the four 620 mm cross members (front; the wheel member at y +104.6, under '
     'where the tyre lands; the bumper member against the post member; the rear) and the 4080 lying flat as the post\'s '
     'member. Two corner brackets per joint on the vertical faces (MISUMI HBLTS8, their own screws and drop-in nuts), '
     'square by the diagonals (equal to 1 mm), every screw 20 N m.'),
    ('The post and the brace', ['post', 'brace', 'brace_hinges'], {'post': 60, 'brace': (0, -60, 60), 'brace_hinges': (0, -60, 60)},
     RIG_VIEW, 'rig',
     'The 8080 on its member, square to it (a machinist\'s square both ways), four corner brackets at its foot, two on each '
     'side face. The 720 mm brace from the post\'s back face 668 mm above the deck\'s top (686 above the frame) to the rear '
     'member\'s top, a free-angle bracket at each end on both side faces (four in all). Tighten the brace last, with the '
     'post plumb.'),
    ('The rails', ['rails'], {'rails': 80}, RIG_VIEW, 'rig',
     'Both HGR15 rails on the post\'s front slots (x = +-20), M4 x 16 into drop-in nuts at every hole, their bottom ends '
     '1 mm above where the deck\'s top will be (a 19 mm block on the frame while tightening). Snug them, run a block along '
     'both by hand, then tighten from the middle outwards (4 N m) while a second block rides the other rail: the carriage '
     'must slide its whole travel with no tight spot.'),
    ('The deck and the ToF sensor', ['deck', 'tof_mount'], {'deck': 40, 'tof_mount': 30}, RIG_VIEW, 'rig',
     'The 600 x 400 plywood from the post\'s front face forwards on the bumper, wheel and front members: 8 x M6 x 30 with '
     'oversized washers into drop-in nuts, none under the tyre\'s landing (x within +-130 at y 60-150). The VL53L1X in its '
     'mount, facing up, at x -212 under the carriage\'s target: two wood screws; its STEMMA QT lead to the pod.'),
    ('The carriage', ['carriage_plate', 'blocks', 'ballast_posts', 'tof_arm'], {'carriage_plate': (0, 60, 0), 'blocks': (0, 30, 0),
                                                                                 'ballast_posts': (0, -40, 0), 'tof_arm': (0, 60, 0)},
     RIG_VIEW, 'rig',
     'Off the rig: the four HGH15CA blocks onto the plate\'s back (16 x M4 x 10, no washers: 3.65 mm into their 5 mm '
     'threads; 3 N m); the two ballast posts (3/8-16 x 1 in and a washer from the front, 25 N m); the ToF target arm '
     '(2 x M4 x 10). Then slide the blocks onto the rails from the top (their plastic retainers stay in until the block '
     'meets the rail) and fit the rails\' end caps.'),
    ('The bumpers and the top stop', ['bumper_base_left', 'bumper_base_right', 'bumper_tpu_left', 'bumper_tpu_right', 'bumper_cap_left',
                                      'bumper_cap_right', 'top_stop_bracket', 'top_tpu_left', 'top_tpu_right'],
     {'bumper_base_left': 40, 'bumper_base_right': 40, 'bumper_tpu_left': 70, 'bumper_tpu_right': 70, 'bumper_cap_left': 100,
      'bumper_cap_right': 100, 'top_stop_bracket': (0, 50, 0), 'top_tpu_left': (0, 50, -40), 'top_tpu_right': (0, 50, -40)},
     RIG_VIEW, 'rig',
     'The bases on the deck at x = +-75 under the plate\'s bottom edge: 2 x M6 x 35 each through the deck into drop-in nuts '
     'in the bumper member; a TPU block in each pocket, a cap on each (R0 in docs/leg-bench-tests.md picks the infill first). '
     'The top stop on the post\'s front above the rails\' ends: 4 x M8 x 16 into drop-in nuts, its two TPU blocks in its cups. '
     'Lower the carriage onto the bumpers: the plate\'s edge lands on both caps at once (shim a base if not).'),
    ('The pod', ['pod', 'pod_lid', 'pendant_clip'], {'pod': (0, -60, 0), 'pod_lid': (-50, 0, 0), 'pendant_clip': (40, 0, 0)}, BACK_VIEW, 'rig',
     'Wired on the bench first (docs/leg-rig-wiring.md): the contactor on its two M4 inserts (2.3 N m), the relay on its '
     'one, the Class CC fuse holder and the 12 V converter on the printed rail, the U2C in its pocket, the Feather on its '
     'FeatherWing on the -y wall; the panel\'s XT60s, jack and fuse holder. Then on the post\'s back face: 4 x M8 x 16 '
     'into drop-in nuts. The pendant\'s clip on its side.'),
    ('The hip frame and the motors (bench)', ['leg_hip_frame', 'leg_bearing_61812_front', 'leg_bearing_61812_rear', 'leg_motor_front',
                                              'leg_motor_rear', 'leg_screws_lugs', 'leg_stop_posts'],
     {'leg_hip_frame': 0, 'leg_bearing_61812_front': (0, -25, 0), 'leg_bearing_61812_rear': (0, -25, 0), 'leg_motor_front': (0, -70, 0),
      'leg_motor_rear': (0, -70, 0), 'leg_screws_lugs': (0, 40, 0), 'leg_stop_posts': (0, 40, 0)}, LEG_VIEW, 'leg',
     'The frame\'s inserts at the coupon-proven temperature: 6 x M5 in the flange ends, 4 x M8 for the stop posts. The two '
     '61812s pressed in from the motor side onto the lip (the fit the frame coupon proved; Loctite 641 if it was a slip '
     'fit). The motors (each with its machined adapter already on, D46: 9 x M5 x 25, no washers, threadlocker, the '
     'adapter\'s journal into the 61812 with Loctite 641) onto their two Ø5 dowels, 10 x M4 x 20 each (heads 10 mm down in '
     'the counterbores; 2.5 N m). The four stop posts BARE (no TPU sleeves yet): the zero is set against the steel.'),
    ('The upper links (bench)', ['leg_eye_sleeve_front', 'leg_eye_sleeve_rear', 'leg_upper_link_front', 'leg_upper_link_rear', 'leg_screws_links'],
     {'leg_eye_sleeve_front': (0, 60, 0), 'leg_eye_sleeve_rear': (0, 60, 0), 'leg_upper_link_front': (0, 40, 0),
      'leg_upper_link_rear': (0, 40, 0), 'leg_screws_links': (0, 70, 0)}, LEG_VIEW, 'leg',
     'Two DIN 179 sleeves pressed end to end into each link\'s knee eye from the outer face (the eye coupon\'s fit). Each '
     'link onto its adapter\'s face: the two Ø5 dowels, 8 x M5 x 40 into the adapter\'s threads (D46: tapped aluminium), '
     'at the B4 torque (1.5 N m until B4 has run: the printed link under the heads sets it, for the 1,200 N per screw '
     'cad/leg_studies.py assumes). Both links swing freely to their bare posts.'),
    ('The leg\'s upper half onto the carriage', ['leg_hip_frame', 'leg_motor_front', 'leg_motor_rear', 'leg_upper_link_front',
                                                 'leg_upper_link_rear', 'leg_output_adapter_front', 'leg_output_adapter_rear'],
     {k: (0, 50, 0) for k in ('leg_hip_frame', 'leg_motor_front', 'leg_motor_rear', 'leg_upper_link_front', 'leg_upper_link_rear',
                               'leg_output_adapter_front', 'leg_output_adapter_rear')}, RIG_VIEW, 'rig',
     'The carriage resting on its bumpers. Each motor\'s lead through its slot in the plate first (XT30 and GH plug '
     'together), then the frame\'s flange ends onto the plate\'s front: 6 x M5 x 16 with washers into the inserts (the B4 '
     'torque). On the plate\'s back: the two XT30s into the Y-splice, the two GH plugs into the CAN junction, the service '
     'loop up to the post\'s top (cable-tied to the plate\'s top edge).'),
    ('Zero the motors', [], {}, RIG_VIEW, 'rig',
     'The bench supply (48 V; docs/leg-bench-tests.md, commissioning C1-C5): set each motor\'s id (127 -> 1 front, '
     '2 rear), `python -m rig.rs04 --id N setup`, save. Then python -m rig.calibrate: hold each upper link on its bare '
     f'knee-out post, it zeroes the motor there, you swing the link to the knee-in post, it checks the {BARE_TRAVEL:.0f} deg '
     'between the bare posts and the direction and writes rig/calibration.json. Power off.'),
    ('The knees', ['leg_front_link', 'leg_wheel_link', 'leg_knee_6201_front_in', 'leg_knee_6201_front_out', 'leg_knee_6201_rear_in',
                   'leg_knee_6201_rear_out', 'leg_knee_spacer_front', 'leg_knee_spacer_rear', 'leg_knee_washer_front', 'leg_knee_washer_rear',
                   'leg_knee_pin_front', 'leg_knee_pin_rear', 'leg_knee_nut_upper_front', 'leg_knee_nut_upper_rear'],
     {'leg_front_link': (0, 70, 0), 'leg_wheel_link': (0, 110, 0), 'leg_knee_pin_front': (0, 150, 0), 'leg_knee_pin_rear': (0, 150, 0)},
     RIG_VIEW, 'rig',
     'Two 6201s and the 28 mm spacer tube into each lower link\'s knee boss (the boss coupon\'s fit), a DIN 433 washer each '
     'side; the 12 x 90 shoulder screw from the outer side through the lower link, the washers and the eye sleeves; the '
     'M10 nyloc in the upper link\'s pocket onto the sleeves (20 N m: steel on steel). The knees turn freely.'),
    ('The apex', ['leg_apex_61812', 'leg_apex_spacer', 'leg_apex_circlip'], {'leg_apex_61812': (0, 60, 0), 'leg_apex_spacer': (0, -40, 0),
                                                                            'leg_apex_circlip': (0, -60, 0)}, RIG_VIEW, 'rig',
     'The inner 61812 into the front link\'s apex eye from the inside, the outer from the outside (the apex coupon\'s fit); '
     'the wheel link\'s hub through both from the outside with the printed spacer between the inner races; the DIN 471-60 '
     'circlip in its groove (circlip pliers). The loop now closes: the leg folds and stretches by hand from stop to stop.'),
    ('The wheel', ['leg_wheel_tyre', 'leg_wheel_hub', 'leg_screws_wheel'], {'leg_wheel_tyre': (0, 60, 0), 'leg_wheel_hub': (0, 60, 0),
                                                                           'leg_screws_wheel': (0, -50, 0)}, RIG_VIEW, 'rig',
     'Measure the BotWheel\'s flange threads first (bom.json\'s note: M6 x 30 for a 15 mm thread). Its boss into the wheel '
     'link\'s recess, 4 x M6 x 30 from inside the hub (8 N m, threadlocker). Its phase and hall leads taped along the wheel '
     'link and the rear upper link (not driven on the rig: plan section 1.3).'),
    ('The stop sleeves', ['leg_stop_sleeve_1', 'leg_stop_sleeve_2', 'leg_stop_sleeve_3', 'leg_stop_sleeve_4'],
     {f'leg_stop_sleeve_{k}': (0, 50, 0) for k in range(1, 5)}, RIG_VIEW, 'rig',
     'One post at a time: out, its TPU sleeve on, back in (the B4 torque into the M8 insert, 5 N m until B4). Swing the leg by hand to both '
     'stops: no part touches another; the knees stay free.'),
    ('Ballast and tethers', ['ballast_plates'], {'ballast_plates': (0, -60, 0)}, BACK_VIEW, 'rig',
     'Weigh the plates. For 14.75 kg: one 2.5 lb plate per post and the trim washers exports/rig/rig.json lists, retained '
     'by the 2 in washer and a 3/8-16 x 3/4 in screw (25 N m). The carriage tether: the endless sling girth-hitched round '
     'the post under the top stop, a screwgate through the plate\'s tether hole, 150 mm slack above the highest jump. The '
     'link tether: a sling round the wheel link next to its knee boss to the same hole, slack over the whole range (sweep '
     'by hand).'),
]


def parts_at(zh: float) -> dict:
    """Every part by name: the rig (deck frame) and the leg at 300 mm with its hip at zh, the leg's names prefixed."""
    P = dict(br.fixed_parts())
    t = (0.0, 0.0, zh)
    P['carriage_plate'] = rp.carriage_plate().translate(t)
    P['blocks'] = rp.blocks().translate(t)
    P['ballast_posts'] = rp.ballast(0).translate(t)
    P['ballast_plates'] = rp.ballast(1).cut(rp.ballast(0)).translate(t)
    P['tof_arm'] = rp.tof_arm().translate(t)
    for n, (s, k) in br.leg_parts(300.0, 0.0, zh).items():
        P[n] = s
    return P


def colour(n: str):
    return br.colour(n)


def main():
    from cadagent.render import Renderer
    OUT.mkdir(parents=True, exist_ok=True)
    rig = parts_at(ZH)
    leg = {n: s.translate(cq.Vector(0, 0, -ZH)) for n, s in rig.items() if n.startswith('leg_')}
    r = Renderer(OUT, size=(1400, 1000), subtitle='GYROPUP LEG RIG | ASSEMBLY')
    done_rig, done_leg, rows = [], [], []
    for k, (title, add, lift, view, where, how) in enumerate(STEPS, 1):
        P = leg if where == 'leg' else rig
        missing = [n for n in add if n not in P]
        if missing:
            raise KeyError(f'step {k}: not in the CAD: {missing}')
        shapes = []
        done = done_leg if where == 'leg' else done_rig
        for n in done:
            if n in add or n not in P:
                continue
            v = P[n].val() if hasattr(P[n], 'val') else P[n]
            shapes.append((v, GREY))
        for n in add:
            off = lift.get(n, 0)
            off = (0, 0, off) if isinstance(off, (int, float)) else off
            v = P[n].val() if hasattr(P[n], 'val') else P[n]
            shapes.append((v, colour(n), off))
        if not shapes:
            continue
        f = f'step-{k:02d}.png'
        first = how.split('. ')[0]
        r.render(f, shapes=shapes, view=view, caption=f'{k}. {title}', note=(first[:118] + ' ...') if len(first) > 120 else first, zoom=0.9)
        rows.append({'step': k, 'title': title, 'adds': add, 'how': how, 'picture': f'exports/rig/assembly/{f}'})
        if where == 'leg':
            done_leg += [n for n in add if n not in done_leg]
        else:
            done_rig += [n for n in add if n not in done_rig]
            if k >= 10:                                  # the leg's half that came from the bench is on the rig now
                done_rig += [n for n in rig if n.startswith('leg_') and n in done_leg + add and n not in done_rig]
        if title.startswith('The leg\'s upper half'):
            done_rig += [n for n in done_leg if n not in done_rig]
    (OUT / 'steps.json').write_text(json.dumps(rows, indent=1) + '\n')
    write_doc(rows)
    print(f'{len(rows)} steps -> {OUT}, docs/leg-rig-assembly.md')


def write_doc(rows):
    """docs/leg-rig-assembly.md from the steps (regenerated with the pictures; edit STEPS, not the page)."""
    L = ['# Leg rig: assembly', '',
         'The order to build the single-leg rig and the first leg on it, from `cad/rig_assembly.py` (the pictures come from '
         'the CAD: each step\'s new parts in colour, lifted along the way they go in; what is already fitted in grey). Part '
         'numbers: `docs/leg-rig-orders.md`; wiring: `docs/leg-rig-wiring.md`; before anything moves: `docs/leg-rig-safety.md`; '
         'the tests: `docs/leg-bench-tests.md`.', '',
         '**Tools:** metric hex keys 2.5-6 mm and a 5/16 in key (the ballast screws), a torque wrench 2-25 N m and a torque screwdriver 1-6 N m (the M5s into printed parts), a soldering iron '
         'with heat-set tips (M4, M5, M8) at the coupon-proven temperature, an arbor press or a vise with soft jaws (bearings, '
         'sleeves), DIN 471 circlip pliers for a 60 mm ring, a machinist\'s square, the ferrule crimper. Threadlocker '
         '(medium) on every screw into steel; never a hard press into PA6-CF: the coupons set every fit.', '']
    for r in rows:
        L += [f"## {r['step']}. {r['title']}", '', f"![step {r['step']}](../{r['picture']})", '', r['how'], '']
    L += ['## Torques', '',
          '| Joint | Torque |', '|---|---|',
          '| Extrusion brackets (M8 into drop-in nuts) | 20 N m |', '| Rails (M4 x 16 into drop-in nuts) | 4 N m |',
          '| Blocks to plate (M4 x 10 into the block) | 3 N m |', '| Plate to hip frame (M5 x 16 into heat-set inserts) | the B4 torque (1.5 N m until B4) |',
          '| Motor lugs (M4 x 20, 12.9, into the RS-04) | 2.5 N m |', '| Adapter to motor (M5 x 25, D46) | 6 N m, threadlocker |',
          '| Upper link to adapter (M5 x 40 into tapped 6061, heads on the printed link) | the B4 torque (1.5 N m until B4) |',
          '| Knee nut (M10 nyloc onto the steel sleeves) | 20 N m |',
          '| Stop posts (M8 into heat-set inserts) | the B4 torque (5 N m until B4) |', '| Wheel (M6 x 30 into the BotWheel) | 8 N m, threadlocker |',
          '| Ballast posts (3/8-16) | 25 N m |', '| Contactor mounting (M4) / load terminals (M5) | 2.3 / 4 N m (TE) |', '']
    (R / 'docs' / 'leg-rig-assembly.md').write_text('\n'.join(L))


if __name__ == '__main__':
    main()
