"""The body's pictures with the turret and the VLP-16 drawn as they are, not as the layout's envelopes.

    .venv/bin/python tools/body_pictures.py     # exports/body/body-*.png and exports/body/views/*.png

cad/body_layout.py keeps the turret as one item: a Ø172 cylinder the turret's mass and height (the P1 dummy), and the
VLP-16 as a plain cylinder. That is right for the mass ledger, the keep-outs and the clash checks, which still use them.
In a picture the turret's can reads as a broken turret, so this draws the same pictures as cad/build_body.py's render()
and cad/body_views.py with those two items swapped for tools/robot_view.py's visual_items(): the turret from
cad/turret.py at its TM face on the riser and its pan axis (body_params.tm(), as sim/robot_v2.py places it), and a
VLP-16 shaped like one. Everything else is the same code and the same views. Flat patterns (flat-*.png) are not redrawn:
they have no turret.

It lives in tools/ because receipts pin cad/'s sources (tools/test-rs04-lug-stacks.py and the carrier checks).
cad/build_body.py, when it is run again, still draws the envelopes: run this after it.
"""
from __future__ import annotations

import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'tools'))
sys.path.insert(0, str(R / 'cad'))
sys.path.insert(0, str(R))

import robot_view as rv  # noqa: E402


def main():
    import body_frame as bf
    import body_params as bp
    import body_views as bv
    import build_body as bb
    layout = bb._layout()
    layout['items'] = rv.visual_items(layout['items'], bp.tm())
    bb._layout = lambda: layout                      # body_views.main() reads the layout through build_body._layout()
    made = bb.render(bf.all_parts(layout['mounts']), layout['items'], bb.OUT)
    print('\n'.join(f'exports/body/{m}' for m in made))
    bv.main()


if __name__ == '__main__':
    main()
