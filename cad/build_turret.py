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
import turret_boards as tbd  # noqa: E402
import turret_stand as ts  # noqa: E402
from cadagent.geometry import export_print_stl  # noqa: E402
from cadagent.robot import solid_mass_properties  # noqa: E402

OUT = R / 'exports' / 'turret' / 'bench'
MATERIALS = json.loads((R / 'catalog/materials.json').read_text())
# every catalogue item by id and by key (catalog/index.json's files and the parts catalog/sourcing.json holds that no
# catalogue file has yet), so a parts-list line can name its part either way
def _catalogue():
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


CAT = _catalogue()
# what to buy for one turret, by catalogue key: {line: (key, qty)}. A line named after a part cad/turret.py draws is
# that part; 'hw_' lines are its screws, inserts, pins and springs (cad/turret.py's notes say where each goes); 'el_'
# lines are the electronics on its boards (docs/turret-plan.md 2, docs/turret-wiring.md). Qty 0: bought with another.
TURRET_BOUGHT = {
    'pan_servo': ('feetech-sts3215-c018-12v', 1), 'tilt_servo': ('feetech-sts3215-c018-12v', 1),
    'flywheel_motor_l': ('sunnysky-x2216-880kv-v3', 1), 'flywheel_motor_r': ('sunnysky-x2216-880kv-v3', 1),
    'esc_l': ('repeat-robotics-am32-35a-esc', 1), 'esc_r': ('repeat-robotics-am32-35a-esc', 1),
    'feed_motor': ('feetech-sts3215-c018-12v', 1), 'cartridge_board': ('proto-board-52x50', 1),
    'laser': ('quarton-vlm-650-03-lpt', 1), 'pan_clamp': ('sendcutsend-pan-clamp', 1),
    # the cradle's aluminium (D48): the same SendCutSend cart as the clamp
    'cradle_plate_l': ('sendcutsend-cradle-plate-l', 1), 'cradle_plate_r': ('sendcutsend-cradle-plate-r', 1), 'stop_lug': ('sendcutsend-stop-lug', 1),
    'pan_bearing': ('vxb-6810-2rs', 1), 'pan_bearing_inner': ('vxb-6810-2rs', 0),
    'tilt_bearing': ('bearing_mr126', 1), 'tilt_bearing_inner': ('bearing_mr126', 0),
    'circlip_50': ('circlip_50', 1), 'shoulder_screw': ('shoulder_6x12_m5', 1),
    'dt_receptacle': ('te-dt04-12pa-l012', 1), 'dt_plug': ('te-dt06-12sa-kit', 1),
    'slip_ring': ('sparkfun-rob-13065', 1), 'slip_ring_rotor': ('sparkfun-rob-13065', 0), 'ring_leads_rotor': ('sparkfun-rob-13065', 0),
    'ring_coupling': ('turret_tube_coupling', 1), 'index_magnet': ('turret_magnet_disc', 1), 'hall_switch': ('allegro-a1120lua-t', 1),
    'ct_thumbscrew': ('turret_thumbscrew_m4x12', 1),
    'base_board': ('proto-board-52x50', 1), 'turret_board': ('proto-board-52x50', 3),
    # hardware
    'hw_tm_screws': ('screw_m5x16', 4), 'hw_tm_dowels': ('dowel_5x16', 2),
    'hw_screw_m2x10': ('turret_screw_m2x10', 4), 'hw_screw_m2x20': ('turret_screw_m2x20', 4), 'hw_flat_m2x6': ('turret_screw_m2x6_flat', 4),
    'hw_screw_m3x6': ('screw_m3x6', 20), 'hw_screw_m3x8': ('turret_screw_m3x8', 15), 'hw_screw_m3x10': ('turret_screw_m3x10', 2),
    'hw_screw_m3x16': ('turret_screw_m3x16', 4),
    'hw_flat_m3x14': ('turret_screw_m3x14_flat_ss', 4), 'hw_button_m3x8': ('turret_screw_m3x8_button', 8), 'hw_flat_m3x6': ('turret_screw_m3x6_flat', 2),
    'hw_screw_m4x10': ('turret_screw_m4x10', 8), 'hw_flat_m3x8': ('turret_screw_m3x8_flat', 4),
    'hw_flat_m3x10': ('turret_screw_m3x10_flat', 3), 'hw_setscrew_m3x6': ('turret_setscrew_m3x6_nylon', 4),
    'hw_insert_m3': ('insert_m3', 37), 'hw_insert_m4': ('turret_insert_m4', 9),
    'hw_washer_m3_large': ('washer_m3_large', 3),
    'hw_dowel_4x8': ('turret_dowel_4x8', 2), 'hw_oring_ct': ('turret_oring_ct', 1), 'hw_standoff_m3x12': ('turret_standoff_m3x12', 4),
    'hw_hub_nuts': ('nut_m5_nyloc', 2),
    'hw_standoff_m3x14': ('turret_standoff_m3x14', 4),
    # electronics (docs/turret-plan.md 2.4, 5.4)
    'el_mcu': ('adafruit-feather-m4-can-4759', 1), 'el_flywheel_regulator': ('pololu-d24v150f12-2885', 1),
    'el_12v_regulators': ('pololu-d36v50f12-4095', 1), 'el_5v_regulator': ('pololu-d36v28f5-3782', 1),
    'el_safety_switch': ('pololu-2815', 1), 'el_capacitors': ('panasonic-eeu-fr1v102', 2),
    'el_555': ('ti-ne555p', 1), 'el_opto': ('vishay-4n35', 1), 'el_monostables': ('ti-cd74hc423e', 1), 'el_supervisor': ('microchip-mcp120', 1),
    'el_trip_latch': ('ti-sn74hc74n', 1), 'el_and': ('ti-sn74hc08n', 1), 'el_brake_driver': ('ti-sn74hct14n', 1), 'el_bus_buffer': ('ti-sn74ahct125n', 1),
    'el_gate_comparator': ('ti-lm393p', 1), 'el_brake_fets': ('infineon-irlz44npbf', 6), 'el_gate_emitters': ('vishay-tsal4400', 2),
    'el_gate_receivers': ('vishay-teft4300', 2),
    'el_ring_receptacles': ('molex-43025-1200', 2), 'el_ring_plugs': ('molex-43020-1200', 2),
    'el_ct_power_receptacle': ('molex-43025-0600', 1), 'el_ct_power_plug': ('molex-43020-0600', 1),
    'el_ct_signal_receptacle': ('molex-43025-1000', 1), 'el_ct_signal_plug': ('molex-43020-1000', 1),
    # crimps (docs/turret-wiring.md 1.3-1.4), with spares: CT power 6 + 6 (18 AWG); CT signal 10 + 10 and the ring's two board-side
    # plugs 24 males (24 AWG); the ring's own 28 AWG leads 24 females (26-30 AWG)
    'el_microfit_f18': ('molex-43030-0038', 8), 'el_microfit_m18': ('molex-43031-0021', 8),
    'el_microfit_f24': ('molex-43030-0001', 14), 'el_microfit_m24': ('molex-43031-0001', 40), 'el_microfit_f28': ('molex-43030-0010', 30),
    'el_fuse_holder': ('littelfuse-0fhm0001zxj', 1), 'el_fuse': ('littelfuse-0297005-wxnv', 2), 'el_laser_switch': ('onsemi-2n7000', 1),
    'el_polyfuse_3a': ('bourns-mf-r300', 3), 'el_polyfuse_2a': ('bourns-mf-r250', 1),
    'el_dt_wedge': ('te-w12p', 1), 'el_dt_pins': ('te-0460-202-16141', 12),
    'el_wire_24awg': ('pololu-ul1007-24awg-60ft', 4), 'el_wire_18awg': ('remington-18ptfestr-25ft', 1),
}


def _passive_line(key: str) -> str:
    """The parts list's line name for one of the boards' passives: el_r_10k, el_c_100n, el_c_1u_film, el_d_1n4148, ..."""
    if key.startswith('yageo-mfr-25fbf52-'):
        return 'el_r_' + key.rsplit('-', 1)[1]
    return {'yageo-rsf100jb-73-2k2': 'el_r_2k2_1w', 'cap-film-100n-5pct': 'el_c_100n_film', 'cap-mlcc-100n-50v': 'el_c_100n',
            'cap-mlcc-1u-50v': 'el_c_1u', 'panasonic-ecq-e1105kf': 'el_c_1u_film', 'onsemi-1n4148': 'el_d_1n4148',
            'omron-b3f-1000': 'el_sw_reset', 'vishay-bat85': 'el_d_bat85', 'schottky-1n5817': 'el_d_1n5817',
            'schottky-1n5822': 'el_d_1n5822', 'tvs-p6ke15a': 'el_d_tvs15', 'bourns-mf-r010': 'el_polyfuse_loop'}.get(key, 'el_' + key)


# the boards' resistors, capacitors, diodes and the reset button, counted from cad/turret_boards.py COMPONENTS (the
# circuit in docs/turret-wiring.md section 3), with a spare or two of each (one per five)
for _k, _n in sorted(tbd.passive_counts().items()):
    TURRET_BOUGHT[_passive_line(_k)] = (_k, _n + max(1, -(-_n // 5)))

# not fitted on the bench (D42): the robot's (v1) lines, listed apart in bom.json and left out of the v0 order sheets
V1_ONLY = {
    'hw_bumper_screws': ('turret_screw_m3x20', 5), 'hw_bumper_washers': ('washer_m3_large', 5), 'hw_bumper_inserts': ('turret_insert_m3_short', 5),
    'hw_flap_pin': ('turret_pin_2x20', 1), 'hw_flap_spring': ('turret_spring_flap', 1),
    'el_hopper_beam': ('adafruit-2167', 1), 'el_lights': ('adafruit-neopixel-ring-12-1643', 1),
}
# the robot's printed parts the bench leaves off (D42; cad/turret_print.py NOT_PRINTED): out of the bench's print plan
V1_PRINTED = ('bumper_ring', 'hopper_flap')
# the bench stand (cad/turret_stand.py), its supply, the reference chronograph and the ammunition: [(key, qty)]
BENCH_BOUGHT = [('amass-xt60e-m', 1), ('turret_screw_m2_5x8', 2), ('turret_nut_m2_5', 2), ('bulgin-r13244aaaa', 1),
                ('fuse-holder-5x20-panel', 1), ('littelfuse-0477005-mxp', 2), ('switchcraft-tb3m', 1), ('switchcraft-ta3flx', 1),
                ('pendant-hold-to-run', 1),
                ('usb-can-canable2', 1), ('proto-board-70x50', 1), ('bumper-feet-12.7', 4), ('insert_m5', 4), ('insert_m3', 8),
                ('turret_screw_m3x8', 4), ('meanwell-lrs-350-24', 1), ('caldwell-ballistic-precision-chronograph-bt', 1),
                ('worker-cheetah-rival-rounds-100', 3)]
# bought once for the build (docs/turret-assembly.md's tools): [(key, qty)]
TOOLS = [('waveshare-bus-servo-adapter-a', 1), ('tool-deutsch-crimper-iwd1620', 1), ('tool-microfit-crimper', 1), ('tool-am32-usb-linker', 1),
         ('tool-circlip-pliers', 1), ('tool-insert-tips', 1), ('tool-reamer-5mm', 1), ('tool-dial-indicator', 1)]


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
    for name in V1_PRINTED:                                # not printed for the bench (D42): the robot's bumper and fill flap
        plan.pop(name, None)
    # the slicer's own grams and hours where cad/turret_print.py has sliced the part in its print orientation
    pj = R / 'exports' / 'turret' / 'print' / 'print.json'
    sliced = json.loads(pj.read_text())['parts'] if pj.exists() else {}
    for name, r in plan.items():
        sp = sliced.get(name) or {}
        if sp.get('grams') and sp.get('minutes'):
            q = r['qty']
            r.update(cost_usd=round(r['cost_usd'] * sp['grams'] * q / max(r['grams'], 1), 2), grams_each=round(sp['grams']),
                     grams=round(sp['grams'] * q), hours=round(sp['minutes'] * q / 60, 1), sliced=True,
                     settings=sp.get('settings'), print_file=sp.get('file'), orientation=sp.get('orientation'))
    too_big = printplan.write(OUT / 'print-plan.json', plan,
                              note='the bench turret (cad/turret.py, v0: no bumper, no fill flap) and its stand; grams and hours are '
                                   'Bambu Studio\'s where the part is sliced (sliced: true, cad/turret_print.py), rough otherwise')
    rows = []
    for name, (key, qty) in TURRET_BOUGHT.items():
        it = CAT.get(key) or {}
        rows.append({'item': it.get('name') or it.get('model') or key, 'id': key, 'key': key, 'qty': qty, 'for': name,
                     'part_number': it.get('model'), 'vendor': it.get('vendor'), 'url': ((it.get('buy') or [{}])[0]).get('url'),
                     'price_usd_each': it.get('price_usd'), 'mass_g_each': T.bought[name][2] if name in T.bought else None,
                     'note': 'bought with the line above it' if qty == 0 else None})
    def line(key, qty, use):
        it = CAT.get(key) or {}
        buys = it.get('buy') or [{}]
        return {'item': it.get('name') or it.get('model') or key, 'id': key, 'key': key, 'qty': qty, 'for': use,
                'part_number': it.get('model'), 'vendor': it.get('vendor'), 'url': buys[0].get('url'), 'price_usd_each': it.get('price_usd'),
                'pack_qty': it.get('pack_qty'), 'mass_g_each': None,
                'sellers': [{k: b.get(k) for k in ('seller', 'url', 'seller_pn', 'price_usd', 'pack_qty', 'in_stock', 'stock', 'read_on')} for b in buys if b.get('url')]}
    bench = [line(key, qty, 'ammo' if key.startswith('worker-') else 'bench') for key, qty in BENCH_BOUGHT]
    tools = [line(key, qty, 'tool') for key, qty in TOOLS]
    v1 = [line(key, qty, name) for name, (key, qty) in V1_ONLY.items()]
    for r in rows:
        it = CAT.get(r['key']) or {}
        r['pack_qty'] = it.get('pack_qty')
        r['sellers'] = [{k: b.get(k) for k in ('seller', 'url', 'seller_pn', 'price_usd', 'pack_qty', 'in_stock', 'stock', 'read_on')}
                        for b in (it.get('buy') or []) if b.get('url')]
    drawn = {k for k, _ in [(v[0], 0) for v in TURRET_BOUGHT.values()] if (CAT.get(k) or {}).get('vendor') == 'SendCutSend'}
    missing = sorted({r['key'] for r in rows + bench + tools if r['key'] not in CAT})
    unpriced = sorted({r['key'] for r in rows + bench + tools if r['qty'] and r.get('price_usd_each') is None and r['key'] not in drawn})
    try:
        from bom_media import enrich                     # the pictures and alternates (catalog/images.json, alternates.json)
        rows, bench, tools = enrich(rows), enrich(bench), enrich(tools)
    except ImportError:
        pass
    no_backup = sorted({r['key'] for r in rows + bench + tools if r['qty'] and len(r.get('sellers') or []) < 2 and not r.get('alternates')
                        and r['key'] not in drawn})
    priced = lambda rs: round(sum((r['price_usd_each'] or 0) * r['qty'] for r in rs), 2)
    sheet = {n: {'drawing': f'exports/turret/{n}.dxf', **tu.SHEET[st], 'thickness_in': tu.SHEET[st]['thickness_in'],
                 'operations': tu.SHEET_OPS.get(n, 'none')} for n, st in tu.SHEET_PARTS.items()}
    (OUT / 'bom.json').write_text(json.dumps({'bench_turret': rows, 'bench_stand': bench, 'tools': tools, 'v1_only': v1, 'not_modelled': tu.NOT_MODELLED_G,
                                              'price_usd_known': {'turret': priced(rows), 'bench_stand': priced(bench), 'tools': priced(tools)},
                                              'not_in_a_catalogue': missing, 'no_listed_price': unpriced, 'no_second_source': no_backup,
                                              'ordered_to_drawing': sheet,
                                              'note': 'every line names a catalogue key (catalog/turret.json, hardware.json, sourcing.json): off '
                                                      'the shelf with a listed price, printed, or ordered to our drawing at an instant online price '
                                                      '(docs/decisions.yaml D40); qty is per turret; packs are bought whole (each item\'s pack_qty); '
                                                      'thumbnails and alternates from cad/bom_media.py'}, indent=1) + '\n')
    summary = {'too_big': too_big, 'print_hours': round(sum(p['hours'] for p in plan.values()), 1),
               'printed_g': sum(p['grams'] for p in plan.values()), 'stand_mm': [ts.W, ts.D, ts.H],
               'note': 'printed_g and print_hours are print-plan.json\'s (the slicer\'s where sliced); sliced is cad/turret_print.py\'s own total'}
    pj = R / 'exports' / 'turret' / 'print' / 'print.json'
    if pj.exists():                                       # the slicer's own grams and hours for the v0 parts (cad/turret_print.py)
        pr = json.loads(pj.read_text())
        summary['sliced'] = {'grams': pr.get('total_grams'), 'hours': pr.get('total_hours'), 'by_material': pr.get('by_material'),
                             'file': 'exports/turret/print/print.json'}
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
    import turret_orders                                  # the order sheets from bom.json and the catalogue
    summary['orders'] = {k: v for k, v in turret_orders.write(OUT / 'bom.json').items() if k in ('grand_total_usd', 'lines', 'sellers')}
    (OUT / 'bench.json').write_text(json.dumps(summary, indent=1) + '\n')
    sl = summary.get('sliced') or {}
    print(f"bench turret: {summary['printed_g'] / 1000:.2f} kg printed, ~{summary['print_hours']} h"
          + (f"; sliced {sl['grams'] / 1000:.2f} kg, {sl['hours']} h" if sl.get('grams') else '') + f"; stand {ts.W:.0f} x {ts.D:.0f} x {ts.H:.0f} mm"
          f"{'; TOO BIG: ' + ', '.join(too_big) if too_big else ''}; {time.time() - t0:.0f} s")


if __name__ == '__main__':
    main()
