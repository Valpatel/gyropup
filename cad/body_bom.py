"""The body's parts list (milestone M5, task T8): exports/body/bom.json in the leg's and turret's format, read by the
build page (designer/build.js) and by docs/body-orders.md.

    .venv/bin/python cad/body_bom.py          # after cad/build_body.py (it reads exports/body/body.json)

Every bought line names a catalogue key (catalog/body.json, or the shared files for parts other workstreams already
list), its quantity for one robot, what it is for, and its sellers: the first is the one to order from, the rest are
the backups (D40: a listed price, a buy link, a backup). Quantities come from the CAD where the CAD has them (screws
per joint, standoffs, inserts) and carry a few spares where a lost part would stop the build (fuses, cells).

Lists
  p0_power_skid       the power plate's parts: switch, main fuse, branch fuses, converters, shunt, monitor
  p0_battery          the 13S2P P30B brick, its BMS, the pack-building supplies, the plugs, the charger
  p0_control          the balance MCU, its CAN transceivers, the BMS's Bluetooth bridge, the radio stop
  p0_wiring           wire, lugs, ferrules, connectors
  p1_frame_hardware   McMaster screws, standoffs, inserts, the grommet
  tools               bought once: the spot welder and the ferrule crimper
  made_to_order       the SendCutSend parts (STEP and DXF), the backup service and an estimate each
  to_source           parts specified but not yet tied to a listed product page (the build page leaves them out)
  not_in_this_order_* the compute and sensors (R13: priced at retail, bought with the sensor head) and the leg
                      workstream's VESCs: listed so the body's total is honest, not ordered here
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
OUT = R / 'exports' / 'body' / 'bom.json'
READ = '2026-10-27'


def catalogue() -> dict:
    """Every catalogue item by id and by key (catalog/index.json's files, hardware.json and body.json)."""
    files = ['hardware.json', 'body.json', *json.loads((R / 'catalog/index.json').read_text())['files']]
    out = {}
    for f in dict.fromkeys(files):
        p = R / 'catalog' / f
        if not p.exists():
            continue
        for it in json.loads(p.read_text()):
            for k in (it.get('key'), it.get('id')):
                if k and k not in out:
                    out[k] = it
    src = json.loads((R / 'catalog/sourcing.json').read_text())                # parts not in a catalogue file yet (as build.js)
    for it in src.get('parts', []):
        for k in (it.get('key'), it.get('id')):
            if k and k not in out:
                out[k] = it
    return out


# extra sellers for shared catalogue items that list only one (read 2026-10-27 by the sourcing reports)
EXTRA_SELLERS = {
    'meanwell-ddr-120c-24': [
        {'seller': 'Bravo Electro', 'url': 'https://www.bravoelectro.com/ddr-120c-24.html', 'price_usd': 69.20, 'in_stock': True, 'ships_from': 'US',
         'stock': 'listed (no quantity shown)', 'read_on': READ},
        {'seller': 'TRC Electronics', 'url': 'https://www.trcelectronics.com/products/mean-well-ddr-120c-24', 'price_usd': 88.66, 'in_stock': True,
         'ships_from': 'US', 'stock': '156 can ship now', 'read_on': READ}],
    'blue-sea-5191-mrbf-terminal-fuse-block': [
        {'seller': 'go2marine', 'url': 'https://www.go2marine.com/products/mrbf-terminal-fuse-block-30-to-300a', 'price_usd': 31.50, 'in_stock': True,
         'ships_from': 'US', 'stock': 'available', 'read_on': READ},
        {'seller': 'go2marine', 'url': 'https://www.go2marine.com/products/mrbf-terminal-fuse-block-single-output-30-300-a-retail-pack', 'price_usd': 17.25,
         'in_stock': True, 'ships_from': 'US', 'stock': 'available; Egis MRBF block, single output, 58 V DC', 'read_on': READ}],
}


ALTERNATES = json.loads((R / 'catalog/alternates.json').read_text())
EXTRA_BACKUP = {        # a second source where neither the catalogue nor alternates.json has one
    'turret_screw_m3x6_flat': [{'seller': 'McMaster-Carr', 'url': 'https://www.mcmaster.com/91294A128/', 'price_usd': 5.82, 'pack_qty': 100,
                                'seller_pn': '91294A128', 'stock': 'M3 x 8 of the same series (4.8 mm into the standoff)', 'read_on': READ}],
    'grommet_cable_pass': [{'seller': 'printed', 'url': 'https://www.mcmaster.com/9307K884/', 'price_usd': 0.0,
                            'stock': 'print a split TPU 95A grommet (as the deck\'s lidar pass)', 'read_on': READ}],
}


def line(cat, key, qty, why, **kw):
    """A parts-list line from the catalogue: its sellers are the catalogue's buy list (first = order from it)."""
    it = cat.get(key)
    if it is None:
        raise KeyError(f'{key}: not in the catalogue')
    sellers = [dict(x) for x in EXTRA_SELLERS.get(it.get('id')) or []]
    if not sellers:
        for b in it.get('buy', []):
            x = {k: b[k] for k in ('seller', 'url', 'in_stock', 'ships_from', 'stock', 'read_on') if k in b}
            if 'price_usd' in b:
                x['price_usd'] = b['price_usd']
            if 'pack_qty' in b:
                x['pack_qty'] = b['pack_qty']
            if 'seller_pn' in b:
                x['seller_pn'] = b['seller_pn']
            sellers.append(x)
    if len(sellers) < 2:                                     # the shared catalogue's alternates (catalog/alternates.json)
        for a in (ALTERNATES.get(key) or ALTERNATES.get(it.get('id')) or []):
            pk = a.get('pack_qty') or 1
            x = {'seller': a.get('supplier'), 'url': a.get('url'), 'stock': a.get('stock'), 'read_on': a.get('checked'),
                 'seller_pn': a.get('part_number')}
            if a.get('price_usd_each') is not None:
                x['price_usd'] = round(a['price_usd_each'] * pk, 2)
            if pk != 1:
                x['pack_qty'] = pk
            if a.get('changes'):
                x['note'] = a['changes']
            sellers.append(x)
    sellers += [dict(x) for x in EXTRA_BACKUP.get(key, []) if len(sellers) < 2]
    if sellers and 'price_usd' not in sellers[0] and it.get('price_usd') is not None:
        sellers[0]['price_usd'] = it.get('pack_price_usd') or it['price_usd']
        if it.get('pack_qty'):
            sellers[0]['pack_qty'] = it['pack_qty']
    mass = (it.get('specs') or {}).get('mass_g') or (it.get('specs') or {}).get('mass_g_estimate')
    row = {'key': key, 'id': it.get('id'), 'qty': qty, 'for': why, 'vendor': it.get('vendor'), 'part_number': it.get('model'),
           'name': it.get('name') or f"{it.get('vendor')} {it.get('model')}", 'mass_g_each': mass,
           'price_usd_each': it.get('price_usd'), 'url': (sellers[0].get('url') if sellers else None)}
    if it.get('pack_qty'):
        row['pack_qty'] = it['pack_qty']
    row['sellers'] = sellers
    row.update(kw)
    return row


def hardware_counts():
    """Screws, standoffs and inserts per robot, from the frame's own lists."""
    import body_battery as bb
    import body_frame as bf
    import body_layout as bl
    L = bl.layout()
    m = L['mounts']
    cheek_nuts = 2 * sum(1 for f in bf.cheek_part().features if f.kind == 'pem')          # tray and belly screws into them
    bay = sum(1 for r in m['belly'] if r[0] == 'pem')
    plate_m5 = sum(1 for r in m['plate'] if r[0] == 'pem' and r[3] == 'F-M5-2')
    plate_m4 = sum(1 for r in m['plate'] if r[0] == 'pem' and r[3] == 'F-M4-2')
    tray_m4 = sum(1 for r in m['tray'] if r[0] == 'pem' and r[3] == 'S-M4-0')
    posts = 2 * len(bf.bp.POSTS)
    plate_posts = 2 * len(bf.PLATE_STANDOFFS)
    riser = 4                                                # the riser's four legs into the deck, from below
    spacers = len(bf.SPACERS_XZ)
    return {
        'screw_m5x12_button': (12, 'the hip frames to the cheeks: six each, from inside the gap (3 N m)'),
        'screw_m5x10_button': (cheek_nuts + bay + posts + plate_posts + riser + plate_m5,
                               f'{cheek_nuts} tray and belly into the cheeks\' flange nuts, {bay} battery bay into the belly, {posts} deck posts, '
                               f'{plate_posts} plate posts, {riser} riser legs, {plate_m5} VESC flanges and shunt into the plate\'s nuts'),
        'screw_m4x10_flat': (2 * spacers + plate_m4 + 2, f'{2 * spacers} the spine standoffs (flush on the frame side), {plate_m4} switch cradle, MCU '
                                                       'carrier and DIN rail into the plate\'s nuts, 2 the DDR-120C rail into the tray'),
        'standoff_m4x31_ff': (spacers, 'the spine: between the cheeks in the hip frames\' bolt rows'),
        'standoff_m3x16_ff': (4, 'the J501 carrier on the compute pallet'),
        'insert_m5': (posts + plate_posts + 2 * riser, f'{posts} deck posts, {plate_posts} plate posts, {2 * riser} riser (its legs, both ends)'),
        'insert_m3': (8, 'the two bus-bar insulators (two from above, two from below each)'),
        'screw_m4x20': (tray_m4 - 2, 'the compute pallet through its printed TPU isolators into the tray\'s nuts'),
        'screw_m3x6': (4, 'the J501 carrier onto its standoffs'),
        'turret_screw_m3x6_flat': (4, 'the carrier standoffs up through the pallet\'s countersinks'),
        'grommet_cable_pass': (1, 'the turret harness through the deck'),
        'screw_m3x8_socket': (8, 'the bus bars to their insulators (4), the insulators to the plate from below (4)'),
    }


def made_to_order(body):
    """The SendCutSend parts from exports/body/body.json, with the order's callouts and an estimate each."""
    est = {'cheek': 60.0, 'floor_tray': 62.0, 'belly_plate': 33.0, 'deck': 65.0, 'compute_pallet': 30.0, 'power_plate': 39.0, 'bus_bar': 17.0}
    out = []
    for name, s in body['sheet'].items():
        spec = [f"{s['material']}, {s['thickness_in']} in ({s['thickness_mm']} mm); qty {s['qty']}; flat {s['flat_mm'][0]} x {s['flat_mm'][1]} mm"]
        if s['bends']:
            b = s['bend_spec']
            spec.append(f"{s['bends']} bends, 90 deg, SendCutSend's {b['inside_radius_in']} in radius (K {b['k_factor']}, bend deduction "
                        f"{b['bend_deduction_in']} in): the DXF's BEND layer marks the lines; flanges as the STEP")
        for k, n in (s.get('hardware') or {}).items():
            spec.append(f'{n} x PEM {k} pressed by SendCutSend (hardware insertion), positions as the STEP')
        for k, n in (s.get('countersinks') or {}).items():
            spec.append(f'{n} x 90 deg countersinks for {k} flat heads (SendCutSend countersinking), the side the STEP shows')
        if name == 'bus_bar':
            spec.append('tapping: the five Ø5.0 holes M6 x 1.0 (SendCutSend tapping)')
        if name == 'floor_tray':
            spec.append('tapping: the two Ø2.5 holes M3 x 0.5 (the VN-100)')
        spec.append('deburr (tumble or linear grain); no finish needed')
        out.append({'key': name, 'qty': s['qty'], 'vendor': 'SendCutSend (sendcutsend.com: upload the DXF for the instant price)',
                    'backup': 'OSH Cut (oshcut.com: instant price from the DXF or STEP; bends and PEM nuts)',
                    'material': f"{s['material']} {s['thickness_in']} in", 'mass_g_each': s['mass_g_each'],
                    'size_mm': [round(v, 1) for v in s['flat_mm']] + [s['thickness_mm']], 'step': s['step'], 'dxf': s['dxf'],
                    'drawing': s['dxf'], 'spec': spec, 'rules': s['rule_violations'] or 'SendCutSend rules checked: none broken',
                    'price_usd_each': None, 'price_estimate_usd_each': est.get(name),
                    'price_note': 'an estimate until the instant price is read on upload (D40: no quotes): cutting by area and cut length, '
                                  'bending, hardware and countersinks per piece; SendCutSend ships in 2-5 days, free shipping over its threshold'})
    return out


def build():
    cat = catalogue()
    body = json.loads((R / 'exports/body/body.json').read_text())
    L = lambda key, qty, why, **kw: line(cat, key, qty, why, **kw)
    hw = hardware_counts()
    bom = {
        'note': 'One robot. The first seller of each line is the one to order from; the rest are backups (D40). Quantities include '
                'spares where noted. Generated by cad/body_bom.py from the CAD (cad/body_frame.py, cad/body_layout.py) and '
                'catalog/body.json; docs/body-orders.md is the order list by seller, docs/body-electrical.md the wiring.',
        'p0_power_skid': [
            L('main_switch', 1, 'the main switch: low side, between the shunt and the - bus; momentary mode (D54)'),
            L('blue-sea-5191-mrbf-terminal-fuse-block', 1, 'the main fuse\'s block on the battery + lead (its M8 post insulated from the plate)'),
            L('mrbf_80a', 2, 'the main fuse (80 A, 58 V DC, 2 kA at 58 V); one spare'),
            L('fuse_mini58_20a', 8, 'the four RS-04 branches (14 AWG); four spares'),
            L('fuse_mini58_30a', 4, 'the two VESC branches (12 AWG); two spares'),
            L('fuse_mini58_10a', 4, 'the DDR-120C-24 input and the charge port (18 AWG); two spares'),
            L('fuse_mini58_5a', 6, 'the DDR-60L-12 input, and the 24 V J501 and turret branches (18 AWG); three spares'),
            L('fuse_holder_mini_inline', 12, 'one per branch (11) and a spare: labelled "58 V fuses only"; pull only with the pack unplugged'),
            L('meanwell-ddr-120c-24', 1, '24 V 5 A, isolated: the J501 and the turret; on a printed TS35 rail on the tray'),
            L('ddr60l_12', 1, '12 V 5 A, isolated: the lidar interface box, the 5 V buck, the radio-stop jack (and the P3 lights and eyes)'),
            L('buck_5v', 1, '5 V from the 12 V rail: the MCU, VN-100, CAN transceivers, QT Py, radio receiver'),
            L('shunt_150a', 1, 'the current shunt in the battery negative (before the switch: it sees charge and discharge)'),
            L('ina228', 1, 'pack voltage and current to the MCU over I2C (its own 15 mOhm shunt removed, wired to the external shunt)'),
        ],
        'p0_battery': [
            L('cell_p30b', 28, 'the 13S2P brick (26) and two spares'),
            L('bms_daly_13s', 1, 'the pack\'s BMS (common port, negative side); cell over-voltage set to 4.15 V, the charger stops at 4.10 V'),
            L('nickel_2p_18650', 1, 'the 2P groups and the series links (doubled on every series link)'),
            L('fish_paper_18650', 26, 'one ring on every cell\'s + end'),
            L('kapton_20', 1, 'between the layers, over every weld, round the BMS'),
            L('xt90s_pair', 1, 'the pack\'s anti-spark plug: female on the pack lead, male on the robot (5-pair pack)'),
            L('xt60h_f', 1, 'the charge port on the robot (female: no live pins), held in a printed bezel in the belly'),
            L('charger_13s', 1, 'the charger: XT60 output, set to 90 % and metered to 53.3 V before the first charge, 2-3 A'),
        ],
        'p0_control': [
            L('nucleo_g474re', 1, 'the balance and power MCU (three FDCAN: buses A, B, C)'),
            L('can_pal', 4, 'CAN transceivers: three for the MCU\'s buses A, B, C, one for the QT Py on bus C'),
            L('qtpy_esp32s3', 1, 'reads the BMS over Bluetooth and puts it on CAN bus C (no wire to the BMS: its UART ground is B-)'),
            L('radio_stop_rx', 1, 'the radio stop\'s receiver (D37), on the 5 V rail'),
            L('radio_stop_relay', 1, 'the radio\'s switch: its contact feeds the stop relay\'s coil (closed = run, open on the failsafe)'),
            L('stop_relay_dpdt', 2, 'the stop relay (one spare): pole A the turret\'s safety loop, pole B its 24 V branch; on the MCU board'),
        ],
        'p0_wiring': [
            L('wire_8awg', 1, 'the pack leads, the MRBF, the shunt, the switch and the bus bars (about 1.5 m; red heat-shrink on the + runs)'),
            L('wire_12awg', 1, 'the two VESC branches (about 1.2 m red + black)'),
            L('wire_14awg', 1, 'the four RS-04 branches (about 3 m red + black)'),
            L('wire_18awg', 1, 'the converters\' inputs, the 24 V and 12 V outputs, the charge port (about 3 m red + black)'),
            L('wire_22awg', 1, '5 V and signal wiring; the CAN pairs twisted by hand (about 6 m)'),
            L('lug_8awg_m6', 10, 'the bus bars\' M6 taps'),
            L('lug_8awg_m8', 4, 'the MRBF block\'s M8 studs and the shunt'),
            L('ferrules', 1, 'every screw terminal (the converters, the switch)'),
            L('xt60h_m', 6, 'the RS-04 and VESC branch plugs'),
            L('xt30_m', 6, 'the 24 V and 12 V branch plugs (J501, turret, lidar box, radio jack, two spare)'),
            L('xt30_f', 6, 'their mating sockets'),
            L('gh_lead_2p_300', 8, 'CAN and I2C leads to the transceivers and the INA228'),
            L('te-dt06-12sa-kit', 1, 'the turret\'s TM plug on the body\'s harness (docs/turret-wiring.md 1.1): 24 V, CAN (J501 can1), SAFETY'),
        ],
        'p1_frame_hardware': [L(k, q, why) for k, (q, why) in hardware_counts().items()],
        'tools': [
            L('spot_welder', 1, 'welding the pack\'s nickel (once)'),
            L('ferrule_crimper', 1, 'the ferrules (once)'),
        ],
        'made_to_order': made_to_order(body),
        'to_source': [
            {'item': 'M3 x 35 flat head, ISO 10642 (the cooler tie-down: the j501-agx rule, 4 mm into the module-to-heatsink standoffs)', 'qty': 4,
             'for': 'the J501 cooler tie-down up through the pallet',
             'note': 'McMaster\'s 91294A flat heads stop at M3 x 25 (91294A138); the fallback is an M3 x 35 socket head (DIN 912: Belmetric '
                     'BSH3X35 on its M3 page, belmetric.com/m3x0-5-socket-head-cap-screw-din-912-class-12-9/) with its head under the pallet, '
                     'in the 8 mm the isolators leave'},
            {'item': '1/4-20 UNC x 3/8 in socket button head (the VLP-16 to the deck)', 'qty': 1, 'for': 'the lidar', 'note': 'any hardware store'},
            {'item': 'Ø4 x 10 mm dowel pin (the VLP-16\'s two locating holes)', 'qty': 2, 'for': 'the lidar', 'note': 'McMaster 98381A series'},
        ],
        'not_in_this_order_sensors_compute': [
            L('seeed-j501-agx-orin-32gb', 1, 'the compute (R13: listed at retail, bought with the sensor head)'),
            L('velodyne-vlp-16', 1, 'the lidar (R13)'),
            L('vectornav-vn-100-rugged', 1, 'the balance IMU (R13, R17)'),
        ],
        'not_in_this_order_leg_workstream': [
            L('flipsky-75100', 2, 'the wheels\' drivers, hung under the power plate: on the leg workstream\'s order (docs/body-plan.md 8)'),
        ],
    }
    priced = [r for k, v in bom.items() if isinstance(v, list) and not k.startswith(('not_', 'to_source', 'made_to_order')) for r in v]
    bom['price_usd_known'] = round(sum(_line_cost(r) for r in priced), 2)
    bom['made_to_order_estimate_usd'] = round(sum((m['price_estimate_usd_each'] or 0) * m['qty'] for m in bom['made_to_order']), 2)
    return bom


def _line_cost(r):
    """What a line costs to order: whole packs at the first seller's price."""
    s = (r.get('sellers') or [{}])[0]
    pack = s.get('pack_qty') or r.get('pack_qty') or 1
    p = s.get('price_usd')
    if p is None:
        p = (r.get('price_usd_each') or 0) * pack
    return math.ceil(r['qty'] / pack) * p


def write_orders(bom, path=R / 'docs' / 'body-orders.md'):
    """docs/body-orders.md: the order list by seller (T8), from the parts list and the print plan."""
    import collections
    from urllib.parse import urlparse
    pp = json.loads((R / 'exports/body/print-plan.json').read_text())

    def cost(r):
        s = (r.get('sellers') or [{}])[0]
        pack = s.get('pack_qty') or r.get('pack_qty') or 1
        p = s.get('price_usd')
        if p is None:
            p = (r.get('price_usd_each') or 0) * pack
        n = math.ceil(r['qty'] / pack)
        return n, pack, p, round(n * p, 2)
    groups = collections.OrderedDict()
    lists = [k for k, v in bom.items() if isinstance(v, list) and not k.startswith(('not_', 'to_source', 'made_to_order'))]
    for lst in lists:
        for r in bom[lst]:
            groups.setdefault((r.get('sellers') or [{}])[0].get('seller') or r.get('vendor') or '?', []).append((lst, r))
    T = {'p0_power_skid': 'T5', 'p0_battery': 'T5', 'p0_control': 'T5', 'p0_wiring': 'T5', 'p1_frame_hardware': 'T2', 'tools': 'T5'}
    out = ["""# Body orders: everything to buy, cut and print for the first prototype (P0 power skid, P1 open frame)

Generated by `cad/body_bom.py` from `exports/body/bom.json` (the CAD and `catalog/body.json`) and the print plan;
regenerate it rather than editing it. One robot. The task numbers are the body plan's (docs/body-plan.md section 5):
T2 the frame, T5 the electrics, T8 this list. Prices were read on the sellers' own pages (or their public store JSON)
on 2026-10-27; McMaster's one product page at a time (cadagent.mcmaster). Every line has a backup (D40): the second
seller in `bom.json`, shown in the last column.

How to order:

1. **SendCutSend** (section 1): upload each DXF from `exports/body/sendcutsend/`, pick the material and thickness in
   its file name, add the bends, PEM nuts, countersinks and tapping listed, and read the instant price. No quotes.
2. **McMaster-Carr** (section 2, first table): one cart, next-day.
3. **The other sellers** (section 2): the ones that ship from China first (LCSC, Daly, Flipsky): one to three weeks.
4. **Print** (section 5) while the orders arrive.
""", "## 1. SendCutSend (T2: the frame and the power plate): custom parts at an instant price\n",
           "| Part | Qty | Material | Flat (mm) | Operations | Files | Estimate |", "|---|---|---|---|---|---|---|"]
    tot_m = 0.0
    for m in bom['made_to_order']:
        ops = '; '.join(x for x in m['spec'][1:] if not x.startswith('deburr'))
        tot_m += (m['price_estimate_usd_each'] or 0) * m['qty']
        out.append(f"| {m['key']} | {m['qty']} | {m['material']} | {m['size_mm'][0]} x {m['size_mm'][1]} | {ops} | "
                   f"[DXF](../{m['dxf']}), [STEP](../{m['step']}) | ~${m['price_estimate_usd_each']:.0f} each |")
    out.append(f"\nEstimate ~${tot_m:.0f} for the set until the instant prices are read. Backup: OSH Cut (oshcut.com), which prices the "
               "same DXF instantly and also bends and inserts PEM nuts. The bus bars can instead be two Victron VBB115040020 (150 A, 70 V, "
               "$17.82 each, in catalog/body.json), which need no insulators.\n")
    grand = 0.0
    order = sorted(groups.items(), key=lambda kv: (0 if kv[0] == 'McMaster-Carr' else 1, -sum(cost(r)[3] for _, r in kv[1])))
    out.append("## 2. Bought parts, by seller\n")
    for seller, rows in order:
        sub = round(sum(cost(r)[3] for _, r in rows), 2)
        grand += sub
        url = (rows[0][1].get('sellers') or [{}])[0].get('url', '')
        host = urlparse(url).netloc.replace('www.', '') if url else ''
        out += [f"### {seller}{f' ({host})' if host else ''}: ${sub:.2f}\n",
                "| Task | Part | Used | Order | Price | Line | For | Backup |", "|---|---|---|---|---|---|---|---|"]
        for lst, r in rows:
            n, pack, p, c = cost(r)
            s0 = (r.get('sellers') or [{}])[0]
            b = (r.get('sellers') or [])[1] if len(r.get('sellers') or []) > 1 else {}
            bl = (b.get('seller', '') + (f" ${b['price_usd']:.2f}" if b.get('price_usd') is not None else '')
                  + (f" ([link]({b['url']}))" if b.get('url') else '') + (f": {b['stock']}" if b.get('stock') else ''))
            link = f"[{r.get('part_number') or r.get('key')}]({s0.get('url')})" if s0.get('url') else (r.get('part_number') or r.get('key'))
            out.append(f"| {T.get(lst, '')} | {link}: {(r.get('name') or r.get('key'))[:90]} | {r['qty']} | "
                       f"{f'{n} x {pack}-pack' if pack != 1 else n} | ${p:.2f} | ${c:.2f} | {r['for'][:100]} | {bl[:160]} |")
        out.append('')
    out.append(f"**Bought parts: ${grand:.2f}** (whole packs at the first seller's price; shipping and tax extra).\n")
    out.append("## 3. Listed, not in this order\n")
    for k in [k for k in bom if k.startswith('not_')]:
        for r in bom[k]:
            s0 = (r.get('sellers') or [{}])[0]
            pr = s0.get('price_usd') if s0.get('price_usd') is not None else r.get('price_usd_each')
            out.append(f"- {r['name']} x {r['qty']}: {r['for']}" + (f" (${pr:,.2f} at {s0.get('seller')})" if pr else ''))
    out.append("\n## 4. Still to source (not tied to a listed product page yet)\n")
    for r in bom['to_source']:
        out.append(f"- {r['item']} x {r['qty']}: {r['for']}. {r.get('note', '')}")
    out += ["\n## 5. Printed (Bambu P1S, 256 mm bed)\n", "| Part | Qty | Material | Size (mm) | g each | Hours | How |",
            "|---|---|---|---|---|---|---|"]
    for n, p in pp['parts'].items():
        out.append(f"| {n} | {p['qty']} | {p['material']} | {' x '.join(str(v) for v in p['size_mm'])} | {p['grams_each']} | {p['hours']} | {p.get('how', '')} |")
    bm = pp.get('by_material', {})
    fil = sum(v.get('cost_usd', 0) for v in bm.values())
    out.append("\nBy material: " + '; '.join(f"{m} {v.get('grams', 0) / 1000:.2f} kg, {v.get('hours', 0):.1f} h, ${v.get('cost_usd', 0):.2f}"
                                            for m, v in bm.items()) + f". STLs beside the plan in `exports/body/`.\n")
    out.append(f"## 6. Totals\n\n| | |\n|---|---|\n| Bought (section 2) | ${grand:.2f} |\n| SendCutSend (section 1, estimate) | ~${tot_m:.0f} |\n"
               f"| Filament used (section 5) | ${fil:.2f} |\n| **Body P0 + P1** | **~${grand + tot_m + fil:.0f}** |\n\n"
               "Not included: the compute and sensors (section 3, R13), the legs and their VESCs (the leg workstream's order), the turret "
               "(the turret workstream's), the shell and head (P3, T7), shipping and tax.\n")
    path.write_text('\n'.join(out))
    return grand, tot_m


def main():
    bom = build()
    OUT.write_text(json.dumps(bom, indent=1) + '\n')
    write_orders(bom)
    n = sum(len(v) for k, v in bom.items() if isinstance(v, list))
    print(f"exports/body/bom.json: {n} lines; bought ${bom['price_usd_known']:.2f} + made to order ~${bom['made_to_order_estimate_usd']:.2f}")


if __name__ == '__main__':
    main()
