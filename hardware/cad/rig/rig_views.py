"""Headless review renders of the rig with every bought part in place (cad/rig_hardware.py): the whole rig solid, a
section through its middle, the same exploded, and close-ups of the carriage from the front and the back.

    .venv/bin/python cad/rig_views.py          # -> exports/rig/views/*.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import cadquery as cq

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_rig as br  # noqa: E402
import rig_parts as rp  # noqa: E402

OUT = br.OUT / 'views'


def everything(L: float = 300.0):
    zh = br.zh_on_deck(L)
    fixed = br.fixed_parts(hardware=True)
    car = br.carriage_parts(zh, hardware=True)
    leg = br.leg_parts(L, 0.0, zh)
    return zh, fixed, car, {n: s for n, (s, k) in leg.items() if k == 'static'}, {n: s for n, (s, k) in leg.items() if k == 'moving'}


def shapes(groups, offsets=None):
    offsets = offsets or {}
    out = []
    for g, parts in groups.items():
        off = offsets.get(g)
        for n, s in parts.items():
            v = s.val() if hasattr(s, 'val') else s
            out.append((v, br.colour(n), off) if off else (v, br.colour(n)))
    return out


def main():
    from cadagent.render import Renderer
    OUT.mkdir(parents=True, exist_ok=True)
    zh, fixed, car, static, moving = everything()
    frame_keep = {n: s for n, s in fixed.items()}
    rails = {n: s for n, s in fixed.items() if n.startswith(('rail', 'top_stop', 'top_tpu'))}
    pod = {n: s for n, s in fixed.items() if n.startswith(('pod', 'pendant'))}
    base = {n: s for n, s in fixed.items() if n not in rails and n not in pod}
    groups = {'base': base, 'rails': rails, 'pod': pod, 'carriage': car, 'leg_frame': static, 'leg_links': moving}
    r = Renderer(OUT, size=(1500, 1100), subtitle='GYROPUP LEG RIG | REVIEW')
    made = []
    made.append(r.render('rig-solid.png', shapes(groups), view=(1.0, 0.85, 0.45), caption='The rig with the leg standing at 300 mm',
                         note='Every bought part drawn: rails, blocks, brackets, screws, washers, ballast'))
    made.append(r.render('rig-solid-back.png', shapes(groups), view=(-0.6, -1.0, 0.45), caption='From behind',
                         note='The pod on the post, the brace and its hinges, the ballast posts on their spacers'))
    made.append(r.render('rig-section.png', shapes(groups), view=(1.0, 0.0, 0.0), clip=((20.0, 0, 0), (1, 0, 0)),
                         caption='Section through the right rail (x = 20, looking from +x)',
                         note='Post, rail, blocks, plate, hip frame; the deck on the members; the bumpers under the plate'))
    near = {'post': {n: s for n, s in base.items() if n in ('post', 'pod')}, 'rails': rails, 'carriage': car, 'leg_frame': static}
    made.append(r.render('rig-section-plan.png', shapes(near), view=(0.0, -0.001, 1.0), clip=((0, 0, zh + 30.0), (0, 0, 1)),
                         caption='Plan section 30 mm above the hip axis',
                         note='Post, the two rails and their blocks, the plate, the frame and both motors, the ballast posts'))
    off = {'rails': (0, 70, 0), 'carriage': (0, 180, 0), 'leg_frame': (0, 330, 0), 'leg_links': (0, 480, 0), 'pod': (0, -220, 0)}
    made.append(r.render('rig-exploded.png', shapes(groups, off), view=(1.0, 0.55, 0.35), caption='Exploded along y',
                         note='Post and base; rails; carriage with its screws; the hip frame and motors; the links and wheel'))
    cg = {'carriage': car, 'leg_frame': static}
    made.append(r.render('carriage-front.png', shapes(cg), view=(0.35, 1.0, 0.25), caption='The carriage from the front',
                         note='The hip frame on the plate; the block screws above and below; the ballast screw heads clear of the motors'))
    cb = {'carriage': car, 'leg_frame': static, 'rails': rails}
    made.append(r.render('carriage-back.png', shapes(cb), view=(-0.45, -1.0, 0.3), caption='The carriage from behind',
                         note='Blocks on the rails, the frame\'s six M5 heads, the ballast posts, spacers and plates'))
    made.append(r.render('carriage-section.png', shapes(cb), view=(1.0, 0.0, 0.05), clip=((rp.BLOCK_X, 0, 0), (1, 0, 0)),
                         caption='The carriage cut through the right blocks (x = 20)',
                         note='Rail, block, its M4 screws through the plate, the hip frame on the plate\'s front'))
    for m in made:
        print(m)


if __name__ == '__main__':
    main()
