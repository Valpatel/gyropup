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
    ('The base frame', ['side_left', 'side_right', 'front_member', 'wheel_member', 'bumper_member', 'post_member', 'rear_member',
                        'base_brackets'], {'base_brackets': 30}, RIG_VIEW, 'rig',
     'On the rubber mat: the two 900 mm sides, the four 620 mm cross members (front; the wheel member at y +104.6, under '
     'where the tyre lands; the bumper member against the post member; the rear) and the 4080 lying flat as the post\'s '
     'member. A corner bracket on each free vertical face of every joint (16: the bumper member and the post member lie '
     'against each other, so those two joints take one each side), their own M8 screws and drop-in nuts, square by the '
     'diagonals (equal to 1 mm), every screw 20 N m.'),
    ('The post and the brace', ['post', 'post_brackets', 'brace', 'brace_hinges'],
     {'post': 60, 'post_brackets': 40, 'brace': (0, -60, 60), 'brace_hinges': (0, -60, 60)}, RIG_VIEW, 'rig',
     'The 8080 on its member, square to it (a machinist\'s square both ways), four corner brackets at its foot, two on each '
     'side face. The 720 mm brace from the post\'s back face 668 mm above the deck\'s top (686 above the frame) to the rear '
     'member\'s top on a free-angle bracket at each end. Tighten the brace last, with the post plumb.'),
    ('The rails', ['rails'], {'rails': 80}, RIG_VIEW, 'rig',
     'Both HGR15 rails on the post\'s front slots (x = +-20), M4 x 16 into drop-in nuts at every hole (17 each), their '
     'bottom ends 1 mm above where the deck\'s top will be (a 19 mm block on the frame while tightening). Snug them, run '
     'a block along both by hand, then tighten from the middle outwards (4 N m) while a second block rides the other rail: '
     'the carriage must slide its whole travel with no tight spot. The rails\' top ends stay open until the carriage is on.'),
    ('The deck and the ToF sensor', ['deck', 'deck_screws', 'tof_mount'], {'deck': 40, 'deck_screws': 60, 'tof_mount': 30}, RIG_VIEW, 'rig',
     'The 600 x 400 plywood from the post\'s front face forwards on the bumper, wheel and front members: 8 x M6 x 30 with '
     'oversized washers into drop-in nuts in the members\' top slots (none under the tyre\'s landing, x within +-130 at '
     'y 60-150). The VL53L1X in its mount, facing up, at x -212 under the carriage\'s target: two M4 x 16 wood screws; '
     'its STEMMA QT lead to the pod.'),
    ('The bumpers', ['bumper_base_left', 'bumper_base_right', 'bumper_tpu_left', 'bumper_tpu_right', 'bumper_cap_left',
                     'bumper_cap_right', 'bumper_screws'],
     {'bumper_base_left': 40, 'bumper_base_right': 40, 'bumper_tpu_left': 70, 'bumper_tpu_right': 70, 'bumper_cap_left': 100,
      'bumper_cap_right': 100, 'bumper_screws': 120}, RIG_VIEW, 'rig',
     'The bases on the deck at x = +-75 under where the plate\'s bottom edge comes down: 2 x M6 x 35 each, from the '
     'pocket\'s floor through the deck into drop-in nuts in the bumper member\'s top slot (the holes sit 11 mm behind the '
     'base\'s centre, over the slot); a TPU block in each pocket, a cap on each (R0 in docs/leg-bench-tests.md picks the '
     'infill first).'),
    ('The pod', ['pod', 'pod_lid', 'pendant_clip', 'pod_screws'], {'pod': (0, -60, 0), 'pod_lid': (-50, 0, 0), 'pendant_clip': (40, 0, 0),
                                                                   'pod_screws': (0, -90, 0)}, BACK_VIEW, 'rig',
     'Wired on the bench first (docs/leg-rig-wiring.md): the contactor on its two M4 inserts (2.3 N m), the relay on its '
     'one, the Class CC fuse holder and the 12 V converter on the printed rail, the U2C in its pocket, the Feather on its '
     'FeatherWing on the -y wall; the panel\'s XT60s, jack and fuse holder. Then on the post\'s back face: 4 x M8 x 16 '
     'through the 6 mm pads into drop-in nuts. The pendant\'s clip on the -y wall: 2 x M4 x 10 into its inserts.'),
('The hip frame and the motors (bench)', ['leg_hip_frame', 'leg_bearing_61812_front', 'leg_bearing_61812_rear', 'leg_motor_front',
                                              'leg_motor_rear', 'leg_screws_lugs', 'leg_stop_posts'],
     {'leg_hip_frame': 0, 'leg_bearing_61812_front': (0, -25, 0), 'leg_bearing_61812_rear': (0, -25, 0), 'leg_motor_front': (0, -70, 0),
      'leg_motor_rear': (0, -70, 0), 'leg_screws_lugs': (0, 40, 0), 'leg_stop_posts': (0, 40, 0)}, LEG_VIEW, 'leg',
     'The historical sequence fits the frame\'s inserts and two 61812s before the motors, using coupon results to '
     'establish the bearing fit. Those physical coupon results have not been recorded. Each motor uses two Ø5 '
     'locating dowels and ten M4 x 20 mounting screws. The former counterbore and lug-tightening instructions are '
     'superseded: use [the current motor-fit evidence](rs04-mounting-fit.md) to establish the measured screw stack, '
     'and qualify support and preload separately. Fit the lug screws before upper links and stop posts as specified '
     'by the bounded driver-access study. This historical sequence does not approve dimensions, bearing retention, '
     'tightening torque or a powered zeroing test.'),
('The upper links (bench)', ['leg_eye_sleeve_front', 'leg_eye_sleeve_rear', 'leg_upper_link_front', 'leg_upper_link_rear', 'leg_screws_links'],
     {'leg_eye_sleeve_front': (0, 60, 0), 'leg_eye_sleeve_rear': (0, 60, 0), 'leg_upper_link_front': (0, 40, 0),
      'leg_upper_link_rear': (0, 40, 0), 'leg_screws_links': (0, 70, 0)}, LEG_VIEW, 'leg',
     'Two DIN 179 sleeves pressed end to end into each link\'s knee eye from the outer face (the eye coupon\'s fit). Each '
     'link onto its adapter\'s face: the two Ø5 dowels, 8 x M5 x 40 into the adapter\'s threads (D46: tapped aluminium), '
     'at the B4 torque (1.5 N m until B4 has run: the printed link under the heads sets it, for the 1,200 N per screw '
     'cad/leg_studies.py assumes). Both links swing freely to their bare posts.'),
    ('The carriage (bench)', ['carriage_plate', 'blocks', 'block_screws', 'ballast_posts', 'tof_arm', 'frame_screws',
                              'leg_hip_frame', 'leg_motor_front', 'leg_motor_rear', 'leg_upper_link_front', 'leg_upper_link_rear',
                              'leg_output_adapter_front', 'leg_output_adapter_rear', 'leg_bearing_61812_front', 'leg_bearing_61812_rear',
                              'leg_screws_lugs', 'leg_stop_posts', 'leg_screws_links', 'leg_eye_sleeve_front', 'leg_eye_sleeve_rear'],
     {'carriage_plate': (0, -60, 0), 'blocks': (0, -100, 0), 'block_screws': (0, 50, 0), 'ballast_posts': (0, -140, 0),
      'tof_arm': (0, 40, 0), 'frame_screws': (0, -90, 0)}, BACK_VIEW, 'rig',
     'On the bench, before the carriage goes on the rails: two of the hip frame\'s six M5s (x = 0) would be behind the '
     'post. The four HGH15CA blocks onto the plate\'s back (16 x M4 x 10 from the front, no washers: 3.65 mm into their 5 mm '
     'threads; 3 N m); the two ballast posts (3/8-16 x 1 in and a plain washer from the front, 25 N m: out at x = +-138 the '
     'heads clear the motors\' rear covers, which sit 2 mm in front of the plate); the ToF target arm (2 x M4 x 10 from the '
     'back into its inserts). Each motor\'s lead through its slot first (XT30 and GH plug together), then the upper half '
     'face down on the plate: 6 x M5 x 16 with washers from the back into the frame\'s inserts (the B4 torque).'),
    ('The carriage onto the rails', [], {}, RIG_VIEW, 'rig',
     'Two people: the carriage (about 8 kg with the upper half) over the rails\' top ends, each block lined up with its '
     'rail and slid off its plastic retainer onto the steel, then down until it rests on the bumpers: the plate\'s edge '
     'lands on both caps at once (shim a base if not). On the plate\'s back: the two XT30s into the Y-splice, the two GH '
     'plugs into the CAN junction, the service loop up to the post\'s top (cable-tied to the plate\'s top edge).'),
    ('The top stop', ['top_stop_bracket', 'top_tpu_left', 'top_tpu_right', 'top_stop_screws'],
     {'top_stop_bracket': (0, 50, 0), 'top_tpu_left': (0, 50, -40), 'top_tpu_right': (0, 50, -40), 'top_stop_screws': (0, 90, 0)},
     RIG_VIEW, 'rig',
     'Its four drop-in nuts into the post\'s front slots from the top (the rails\' screws fill the slots below), the '
     'bracket on them above the rails\' ends: 4 x M8 x 16, 6 mm of bracket under each head; its two TPU blocks in its cups.'),
('Zero the motors', [], {}, RIG_VIEW, 'rig',
     'The bench supply (36 V; docs/leg-bench-tests.md, commissioning C1-C5): set each motor\'s id (127 -> 1 front, '
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
     'Weigh the plates. For 14.75 kg: one 2.5 lb plate per post (within 2 %: exports/rig/rig.json), retained by the 2 in '
     'washer and a 3/8-16 x 3/4 in screw in the post\'s end (25 N m). The carriage tether: the endless sling girth-hitched '
     'round the post under the top stop, a screwgate through the plate\'s tether hole, 150 mm slack above the highest jump. '
     'The link tether: a sling round the wheel link next to its knee boss to the same hole, slack over the whole range '
     '(sweep by hand).'),
]


def parts_at(zh: float) -> dict:
    """Every part by name: the rig (deck frame) and the leg at 300 mm with its hip at zh, the leg's names prefixed;
    the bought hardware included, grouped below into what each step fits."""
    P = dict(br.fixed_parts(hardware=True))
    P.update(br.carriage_parts(zh, hardware=True))
    for n, (s, k) in br.leg_parts(300.0, 0.0, zh).items():
        P[n] = s
    return P


GROUPS = {   # a step's group name -> the prefixes of the parts it fits
    'base_brackets': ('bracket_front', 'bracket_wheel', 'bracket_bumper', 'bracket_rear', 'bracket_post_member'),
    'post_brackets': ('bracket_post_left', 'bracket_post_right'), 'brace_hinges': ('brace_hinge',),
    'rails': ('rail_left', 'rail_right', 'rail_screw'), 'deck_screws': ('deck_screw',), 'blocks': ('block_',),
    'block_screws': ('block_screw',), 'ballast_posts': ('ballast_shaft', 'ballast_screw', 'ballast_spacer'), 'tof_arm': ('tof_arm',),
    'bumper_screws': ('bumper_screw',), 'top_stop_screws': ('top_stop_screw',), 'pod_screws': ('pod_screw',),
    'tof_mount': ('tof_mount',), 'frame_screws': ('frame_screw',), 'ballast_plates': ('weight_plate', 'ballast_keeper'),
}


def expand(names, P: dict) -> list:
    out = []
    for n in names:
        if n in GROUPS:
            out += [m for m in P if m.startswith(GROUPS[n]) and not (n == 'blocks' and m.startswith('block_screw'))
                    and not (n == 'rails' and False)]
        else:
            out.append(n)
    return list(dict.fromkeys(out))


def colour(n: str):
    return br.colour(n)


def main():
    from cadagent.render import Renderer
    OUT.mkdir(parents=True, exist_ok=True)
    rig = parts_at(ZH)
    leg = {n: s.translate(cq.Vector(0, 0, -ZH)) for n, s in rig.items() if n.startswith('leg_')}
    r = Renderer(OUT, size=(1400, 1000), subtitle='GYROPUP LEG RIG | ASSEMBLY')
    done_rig, done_leg, rows = [], [], []
    for k, (title, add0, lift0, view, where, how) in enumerate(STEPS, 1):
        P = leg if where == 'leg' else rig
        add = expand(add0, P)
        lift = {}
        for g in add0:                                            # a group's lift applies to each of its parts
            if g in lift0:
                for m in expand([g], P):
                    lift[m] = lift0[g]
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
            if k >= 9:                                   # the leg's half that came from the bench is on the rig now
                done_rig += [n for n in rig if n.startswith('leg_') and n in done_leg + add and n not in done_rig]
        if title.startswith('The carriage (bench)'):
            done_rig += [n for n in done_leg if n not in done_rig]
    (OUT / 'steps.json').write_text(json.dumps(rows, indent=1) + '\n')
    write_doc(rows)
    print(f'{len(rows)} steps -> {OUT}, docs/leg-rig-assembly.md')


def write_doc(rows):
    """docs/leg-rig-assembly.md from the steps (regenerated with the pictures; edit STEPS, not the page)."""
    L = ['# Leg rig: assembly', '',
         '> **Unqualified assembly walkthrough:** this sequence and its loading assumptions do not establish a current '
         'print or operating release. The RS-04 lug support, physical fits and tightening procedure remain unqualified. '
         'Use [the current mounting-fit evidence](rs04-mounting-fit.md) and the separate '
         '[unpowered coupon job](rs04-fit-job.md); no physical coupon results are recorded.', '',
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
          '| Motor lugs (M4 x 20, 12.9, into the RS-04) | Not established; qualify the measured mounting joint and preload before use. |', '| Adapter to motor (M5 x 25, D46) | 6 N m, threadlocker |',
          '| Upper link to adapter (M5 x 40 into tapped 6061, heads on the printed link) | the B4 torque (1.5 N m until B4) |',
          '| Knee nut (M10 nyloc onto the steel sleeves) | 20 N m |',
          '| Stop posts (M8 into heat-set inserts) | the B4 torque (5 N m until B4) |', '| Wheel (M6 x 30 into the BotWheel) | 8 N m, threadlocker |',
          '| Ballast posts (3/8-16) | 25 N m |', '| Contactor mounting (M4) / load terminals (M5) | 2.3 / 4 N m (TE) |', '']
    (R / 'docs' / 'leg-rig-assembly.md').write_text('\n'.join(L))


if __name__ == '__main__':
    main()
