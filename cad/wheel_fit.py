"""Wheel fit (issue #18): the leg's clash sweep with an air-tyre hub wheel in place of the BotWheel, on a scratch copy
of the wheel's solid. cad/fivebar.py is not edited: fivebar.botwheel is replaced in memory before leg_parts() builds.

    python cad/wheel_fit.py [--wheels hb10 hb85] [--quick]

Writes exports/wheels/fit_clashes.json: for each wheel, fivebar.clashes() at the standard stances (130-380 mm,
leans -20/0/20) and the stop poses, with the bought parts; plus the track, the standing hip height and the foot's
reach. --quick: the three extreme stances only.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
sys.path.insert(0, str(R))

import fivebar as fb  # noqa: E402

CANDIDATES = json.loads((R / 'sim' / 'wheel_candidates.json').read_text())
OUT = R / 'exports' / 'wheels'


def patch(w: dict):
    def wheel():
        od, width, hub_d, hub_w = w['od_mm'], w['tyre_width_mm'], w['hub_od_mm'], w['hub_width_mm']
        y_in = fb.Y['wheel_boss'] + 7.5                              # the tyre's inner face where the BotWheel's is
        yc = y_in + width / 2
        tyre = fb.ycyl(od / 2, yc - width / 2, yc + width / 2).cut(fb.ycyl(od / 2 - w['tyre_section_mm'], yc - width / 2 - 1, yc + width / 2 + 1))
        hub = fb.ycyl(hub_d / 2, yc - hub_w / 2, yc + hub_w / 2)
        axle = fb.ycyl(w['axle_d_mm'] / 2, fb.Y['hub'][0] + 2.0, yc - hub_w / 2 + 0.01)   # the single-sided axle, into the foot
        return tyre, hub.union(axle)
    fb.botwheel = wheel
    fb.leg_parts.cache_clear()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--wheels', nargs='*', default=['botwheel', 'hb85', 'hb10'])
    ap.add_argument('--quick', action='store_true')
    a = ap.parse_args(argv)
    out = {}
    for name in a.wheels:
        w = CANDIDATES[name]
        patch(w)
        t0 = time.time()
        heights = (130, 260, 380) if a.quick else (130, 200, 260, 320, 380)
        leans = (0,) if a.quick else (-20, 0, 20)
        cl = fb.clashes(heights=heights, leans=leans, with_bought=True, poses=fb.stop_poses())
        real = [c for c in cl if c[0] != 'out of range']
        wheel_cl = [c for c in real if 'wheel' in c[0] or 'wheel' in c[1]]
        y_in = fb.Y['wheel_boss'] + 7.5
        track = 2 * (y_in + w['tyre_width_mm'] / 2 - fb.Y['centre_plane'])
        out[name] = {'wheel': w, 'clashes': real, 'wheel_clashes': wheel_cl, 'out_of_range': [c[3] for c in cl if c[0] == 'out of range'],
                     'track_mm': round(track, 1), 'hip_height_at_300_mm': round(300 + w['od_mm'] / 2, 1),
                     'tyre_y_mm': [round(y_in, 1), round(y_in + w['tyre_width_mm'], 1)], 'wall_s': round(time.time() - t0)}
        print(f"{name}: {len(real)} clashes ({len(wheel_cl)} with the wheel), track {track:.0f} mm, hip {300 + w['od_mm'] / 2:.0f} mm at a 300 mm leg "
              f"({out[name]['wall_s']} s)")
        for c in wheel_cl:
            print('   ', c)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'fit_clashes.json').write_text(json.dumps(out, indent=1) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
