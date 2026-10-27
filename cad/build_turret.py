"""Build the foam-ball turret on its own bench stand (M4): pictures, the print plan, the parts list.

    .venv/bin/python cad/build_turret.py [--no-render]

The turret is cad/turret.py's, mounted with its TM face on the stand's top (cad/turret_stand.py) instead of on the
robot's head. Writes exports/turret/bench/: the stand's parts (STEP, print-ready STL), turret-bench-*.png,
print-plan.json (the turret's printed parts and the stand's), bom.json (what to buy for a bench turret), bench.json.
The turret's own part files come from `cad/turret.py` (exports/turret/).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cadquery as cq

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import printplan  # noqa: E402
import turret as tu  # noqa: E402
import turret_stand as ts  # noqa: E402
from cadagent.geometry import export_print_stl  # noqa: E402
from cadagent.robot import solid_mass_properties  # noqa: E402

OUT = R / 'exports' / 'turret' / 'bench'
MATERIALS = json.loads((R / 'catalog/materials.json').read_text())
CAT = {i['id']: i for i in json.loads((R / 'catalog/turret.json').read_text())}
HW = {i['key']: i for i in json.loads((R / 'catalog/hardware.json').read_text())}
# the turret's bought parts and where each comes from (catalogue id, or a plain description until it is catalogued)
TURRET_BOUGHT = {
    'pan_servo': ('feetech-sts3215-c018-12v', 1), 'tilt_servo': ('feetech-sts3215-c018-12v', 1),
    'flywheel_motor_l': ('dji-robomaster-snail-2305', 1), 'flywheel_motor_r': ('dji-robomaster-snail-2305', 1),
    'esc_l': ('repeat-robotics-am32-35a-esc', 1), 'esc_r': ('repeat-robotics-am32-35a-esc', 1),
    'feed_motor': ('dji-robomaster-m2006-p36', 1), 'feed_esc': ('DJI C610 (CAN), comes with the M2006 kit', 1),
    'laser': ('Picotronic DD520-1-24(12x40), 520 nm Class 2', 1), 'pan_bearing': ('61810-2RS (50 x 65 x 7)', 1),
    'tilt_bearing': ('MR126-2RS (6 x 12 x 4)', 1), 'dt_receptacle': ('TE Deutsch DT04-12PA-L012 flange receptacle', 1),
    'dt_plug': ('TE Deutsch DT06-12SA plug + W12S wedge + 12 x 0462-201-16141 sockets', 1),
}
BENCH_BOUGHT = [('Amass XT60E-F panel socket (24 V in)', 1), ('KCD1 rocker switch, 16 A', 1), ('5 x 20 mm panel fuse holder + 5 A slow-blow fuse', 1),
                ('3.5 mm panel jack + a hold-to-run pendant (momentary button on 2 m of cable)', 1),
                ('USB-CAN adapter (CANable 2.0 class)', 1), ('70 x 50 mm board with a 24 V terminal block', 1),
                ('rubber bumper feet, Ø12.7 x 5.5', 4), ('worker-cheetah-rival-rounds-100', 1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-render', action='store_true')
    a = ap.parse_args()
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    T = tu.Turret({'bodyTop': -(20.0 + tu.SADDLE_T)})            # mount face at z = 0: the stand's top
    stand = ts.parts()
    plan = {}
    for name, m in T.meta.items():
        v = T.local[name].val()
        g = solid_mass_properties(v, MATERIALS[m['material']]['density_g_cm3'], 1.0 if m['solid'] else 0.45, name).mass * 1000
        plan[name] = printplan.row(v, m['print_rotation'], m['material'], m['qty'], g, m['solid'], m['note'])
    for name, shape in stand.items():
        mat, qty, how, rot = ts.PARTS[name]
        v = shape.val()
        cq.exporters.export(v, str(OUT / f'{name}.step'))
        export_print_stl(v, OUT / f'{name}.stl', rotation=rot)
        g = solid_mass_properties(v, MATERIALS[mat]['density_g_cm3'], 0.45, name).mass * 1000
        plan[name] = printplan.row(v, rot, mat, qty, g, False, how)
    too_big = printplan.write(OUT / 'print-plan.json', plan, note='the turret (cad/turret.py) and its bench stand; hours are rough')
    rows = []
    for name, (src, qty) in TURRET_BOUGHT.items():
        it = CAT.get(src)
        rows.append({'item': (it.get('name') or it.get('model') or src) if it else src, 'id': src if it else None, 'qty': qty, 'for': name,
                     'price_usd_each': it.get('price_usd') if it else None, 'mass_g_each': T.bought[name][2] if name in T.bought else None})
    for src, qty in BENCH_BOUGHT:
        it = CAT.get(src)
        rows.append({'item': (it.get('name') or it.get('model') or src) if it else src, 'id': src if it else None, 'qty': qty, 'for': 'bench stand' if not it else 'ammo',
                     'price_usd_each': it.get('price_usd') if it else None, 'mass_g_each': None})
    (OUT / 'bom.json').write_text(json.dumps({'bench_turret': rows, 'not_modelled': tu.NOT_MODELLED_G,
                                              'price_usd_known': round(sum((r['price_usd_each'] or 0) * r['qty'] for r in rows), 2),
                                              'note': 'the turret\'s screws, inserts, dowels and circlips are in cad/turret.py\'s notes; McMaster part numbers next'},
                                             indent=1) + '\n')
    summary = {'too_big': too_big, 'print_hours': round(sum(p['hours'] for p in plan.values()), 1),
               'printed_g': sum(p['grams'] for p in plan.values()), 'stand_mm': [ts.W, ts.D, ts.H]}
    if not a.no_render:
        from cadagent.render import Renderer
        r = Renderer(OUT, subtitle='GYROPUP TURRET | ON ITS BENCH STAND')
        col = lambda n: {'barrel': (1.0, .42, .07), 'hopper': (.6, .78, .91, .55), 'hopper_lid': (.6, .78, .91, .55),
                         'flywheel_tyre': (.15, .15, .17), 'stand_box': (.22, .24, .28), 'stand_bottom': (.18, .19, .22),
                         'bumper_ring': (.12, .12, .13), 'dt_plug': (.55, .55, .2)}.get(n, (.36, .38, .42) if n in T.meta else (.2, .2, .22))
        pics = []
        for pan, tilt, tag in ((0.0, 0.0, 'level'), (35.0, -20.0, 'aimed')):
            posed = T.posed(pan, tilt)
            shapes = [(s.val(), col(n)) for n, s in posed.items()] + [(s.val(), col(n)) for n, s in stand.items()]
            shapes += [((sh.val() if hasattr(sh, 'val') else sh), (.15, .15, .17)) for sh, _, _ in ts.bought().values()]
            for view, vec in (('iso', (1.0, -1.1, 0.7)), ('front', (1.0, 0.0, 0.15))):
                if tag == 'aimed' and view != 'iso':
                    continue
                f = f'turret-bench-{tag}-{view}.png'
                r.render(f, shapes=shapes, view=vec, caption=f'The turret on its bench stand, pan {pan:.0f} deg, tilt {tilt:.0f} deg ({view})')
                pics.append(f)
        summary['pictures'] = pics
    (OUT / 'bench.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(f"bench turret: {summary['printed_g'] / 1000:.2f} kg printed, ~{summary['print_hours']} h; stand {ts.W:.0f} x {ts.D:.0f} x {ts.H:.0f} mm"
          f"{'; TOO BIG: ' + ', '.join(too_big) if too_big else ''}; {time.time() - t0:.0f} s")


if __name__ == '__main__':
    main()
