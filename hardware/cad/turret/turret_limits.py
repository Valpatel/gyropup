"""The turret's joint limits, written once from the CAD's hard stops, for everything that aims it.

    .venv/bin/python hardware/cad/turret/turret_limits.py          # writes exports/turret/limits.json
    .venv/bin/python hardware/cad/turret/turret_limits.py --check  # exits 1 if the file differs from the CAD

The tilt range is the hard stops in the yoke (cad/turret.py Geo.tilt_min and Geo.tilt_max; the stop lug against the
yoke's stop sectors). D77 (2026-11-03) replaced the old rule "the barrel never points above horizontal" with these
real mechanical stops: the browser playground (designer/turret3d.js, designer/sim.js), the physics (sim/turret.py,
sim/turret_flight.py, sim/turret_e2e.py, sim/robot_v2.py) and the firmware reference's config (firmware/turret/config.py,
checked by its tests) take the range from this file, so moving a stop in the CAD moves every one of them.

Firing has its own upper limit, below the stop: `fire_tilt_max_deg`, the highest tilt at which the gravity feed was
shown to feed as it does at level (sim/turret_feed.py --elevated, its fire_limit, in exports/turret/feed/feed-elevated.json),
capped at the upper stop. The barrel may aim up to the stop; the firmware and the sims do not fire above this. It is a
simulation's figure until the bench feed test (docs/turret-bench-tests.md) confirms it.

Pan is continuous (cad/turret.py CONTINUOUS_PAN, the slip ring); the robot's per-pan depression table over the lidar
(sim/robot_v2.py, cad/turret_lidar.py) narrows the range further where the body is in the way; it never widens it.
"""
from __future__ import annotations

# Support direct-file CLI execution as well as checkout package imports.
if __package__ in (None, ''):
    import sys as _checkout_sys
    from pathlib import Path as _CheckoutPath
    _checkout_sys.path.insert(0, str(_CheckoutPath(__file__).resolve().parents[3]))


import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R))
OUT = R / 'hardware' / 'exports' / 'turret' / 'limits.json'
FEED_ELEVATED = R / 'hardware' / 'exports' / 'turret' / 'feed' / 'feed-elevated.json'


def fire_limit(G):
    """(deg, source) the firing limit: the feed study's, capped at the upper stop; 0 (level) without the study."""
    if not FEED_ELEVATED.exists():
        return 0.0, 'no feed study above level: level only'
    feed = json.loads(FEED_ELEVATED.read_text())
    t = float(feed.get('fire_tilt_max_deg', 0.0))
    return min(t, G.tilt_max), f'{FEED_ELEVATED.relative_to(R).as_posix()} fire_tilt_max_deg (sim/turret_feed.py --elevated), capped at the upper stop'


def limits(tu=None) -> dict:
    if tu is None:
        import hardware.cad.turret.turret as tu
    G = tu.Geo()
    fire, fire_src = fire_limit(G)
    return {
        'what': "the turret's joint limits from its hard stops (cad/turret_limits.py; D77)",
        'source': 'cad/turret.py Geo.tilt_min, Geo.tilt_max (the stop lug on the yoke\'s stop sectors), CONTINUOUS_PAN',
        'tilt_deg': {'min': G.tilt_min, 'max': G.tilt_max, 'positive': 'muzzle up',
                     'stops': 'hard: the cradle\'s aluminium stop lug on the -y arm\'s printed sectors (D48)'},
        'fire_tilt_max_deg': fire,
        'fire_source': fire_src,
        'fire_note': 'no shot is fired above this tilt (the barrel may still aim up to the stop); a simulated figure until the bench feed test',
        'pan': {'continuous': bool(tu.CONTINUOUS_PAN), 'stop_deg': None if tu.CONTINUOUS_PAN else 173.5},
        'decision': 'D77',
    }


def text(tu=None) -> str:
    return json.dumps(limits(tu), indent=1) + '\n'


def main():
    want = text()
    if '--check' in sys.argv:
        have = OUT.read_text() if OUT.exists() else ''
        if have != want:
            print(f'{OUT.relative_to(R)} is stale: run hardware/cad/turret/turret_limits.py')
            sys.exit(1)
        print(f'{OUT.relative_to(R)} matches the CAD')
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(want)
    print(f'wrote {OUT.relative_to(R)}: tilt {json.loads(want)["tilt_deg"]["min"]} .. {json.loads(want)["tilt_deg"]["max"]} deg')


if __name__ == '__main__':
    main()
