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
    'dewalt-dcb609': [
        {'seller': 'The Power Tool Store', 'url': 'https://thepowertoolstore.com/products/dewalt-dcb609', 'price_usd': 259.0, 'in_stock': True,
         'ships_from': 'US', 'read_on': '2026-10-25'},
        {'seller': 'Ace Tool', 'url': 'https://acetool.com/Dewalt-DCB609-p/dew-dcb609.htm', 'price_usd': 259.0, 'read_on': READ, 'stock': 'listed'}],
    'traco-tep-150-4812wi': [
        {'seller': 'Newark', 'url': 'https://www.newark.com/search?st=TEP%20150-4812WI', 'price_usd': 275.99, 'read_on': READ,
         'stock': '4 (as an aggregator, electronicsdatasheets.com, lists it: confirm on the order)'},
        {'seller': 'Farnell', 'url': 'https://www.farnell.com/search?st=TEP%20150-4812WI', 'price_usd': 222.65, 'read_on': READ,
         'stock': 'listed (via the same aggregator)'}],
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
    'screw_m6x16': [{'seller': 'Belmetric', 'url': 'https://belmetric.com/m6x1-0-socket-head-cap-screw-din-912-class-12-9/', 'price_usd': 0.20,
                     'seller_pn': 'BSH6X16', 'read_on': READ,
                     'stock': 'in stock: DIN 912 class 12.9, black oxide, fully threaded (the same screw); $0.12 each from 25'}],
    'nut_m6_nyloc': [{'seller': 'Global Industrial', 'url': 'https://www.globalindustrial.com/p/m6-x-1-0-nylon-insert-lock-nut-304-stainless-steel-din-985-pkg-of-100',
                      'price_usd': 25.95, 'pack_qty': 100, 'seller_pn': 'WBB2298457 (Titan Fasteners AAV06)', 'read_on': READ,
                      'stock': 'ships in 2 business days: DIN 985 M6 in 304 stainless (the same size, 6 mm tall)'}],
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
    if len(sellers) < 2:                                     # the shared catalogue's alternates (catalog/alternates.json):
        alts = list(ALTERNATES.get(key) or ALTERNATES.get(it.get('id')) or [])          # a priced, drop-in one first
        alts.sort(key=lambda a: (a.get('price_usd_each') is None, 'not drop-in' in (a.get('changes') or '').lower()))
        for a in alts:
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


def joint_hardware(stage):
    """Every screw, insert and nut the joints of a stage add (cad/body_joints.py: the same joints the integrity checks
    read through the CAD, so the parts list and the checked stacks cannot disagree): {key: (qty, why)}. P1 counts the
    P0 and P1 joints; P2 and P3 only the joints that first appear there."""
    import body_joints as bj
    import build_body as bb
    J = bj.joints(bb._layout()['items'])
    first = {'P1': ('P0', 'P1'), 'P2': ('P2',), 'P3': ('P3',)}[stage]
    out = {}

    def add(key, n, why):
        q, w = out.get(key, (0, []))
        out[key] = (q + n, w + [why])
    for j in J:
        if j.stage not in first:
            continue
        n = len(j.at)
        add(j.bom, n, f'{n} {j.name.replace("_", " ")}')
        kind = j.receiver[0]
        if kind == 'insert':
            add(f'insert_{j.thread.lower()}', n, f'{n} {j.name.replace("_", " ")}')
        elif kind == 'nyloc':
            add(f'nut_{j.thread.lower()}_nyloc', n, f'{n} {j.name.replace("_", " ")}')
        elif kind == 'nut':
            add(f'nut_{j.thread.lower()}', n, f'{n} {j.name.replace("_", " ")}')
    return {k: (q, f'{stage}: ' + ', '.join(w) + ' (cad/body_joints.py)') for k, (q, w) in sorted(out.items())}


def hardware_counts():
    """P1's screws, inserts and nuts from the joints, and the parts that are not joints (standoffs, the grommet, the
    lug stacks' M6 screws and nuts)."""
    import body_frame as bf
    out = joint_hardware('P1')
    out.update({
        'standoff_m4x31_ff': (len(bf.SPACERS_XZ), 'the spine: between the cheeks in the hip frames\' bolt rows'),
        'standoff_m3x16_ff': (4, 'the J501 carrier on the compute pallet'),
        'screw_m3x6': (out.get('screw_m3x6', (0, ''))[0] + 4, (out.get('screw_m3x6', (0, ''))[1] + '; ' if 'screw_m3x6' in out else '')
                       + '4 the J501 carrier onto its standoffs'),
        'turret_screw_m3x6_flat': (4, 'the carrier standoffs up through the pallet\'s countersinks'),
        'grommet_cable_pass': (1, 'the turret harness through the deck'),
        'screw_m6x16': (2 * len(bf.BUS_HOLES), 'the bus bars\' lug stacks: down through the lug(s) and the bar into the insulator\'s nut'),
        'nut_m6_nyloc': (2 * len(bf.BUS_HOLES), 'held in the bus insulators\' hex pockets under the bars\' holes (they cannot turn)'),
    })
    return out


PRICES = R / 'exports' / 'body' / 'sendcutsend' / 'prices.json'      # tools/sendcutsend_quote.py: SendCutSend's instant prices


def p3_shell(L, cat=None):
    """P3's bought hardware: the joints that first appear in P3 (cad/body_joints.py)."""
    return [L(k, q, why) for k, (q, why) in joint_hardware('P3').items()]


def made_to_order(body, prices=None):
    """The SendCutSend parts from exports/body/body.json, with the order's callouts and SendCutSend's instant price each,
    read in its app from the uploaded DXF (tools/sendcutsend_quote.py -> exports/body/sendcutsend/prices.json); a part
    not priced yet keeps an estimate and says what to upload."""
    if prices is None:
        prices = json.loads(PRICES.read_text()) if PRICES.exists() else {}
    est = {'cheek': 60.0, 'floor_tray': 62.0, 'belly_plate': 33.0, 'deck': 65.0, 'compute_pallet': 30.0, 'power_plate': 39.0, 'bus_bar': 17.0,
           'turret_plate': 25.0, 'tub_floor': 45.0, 'tub_side': 30.0}
    out = []
    for name, s in body['sheet'].items():
        spec = [f"{s['material']}, {s['thickness_in']} in ({s['thickness_mm']} mm); qty {s['qty']}; flat {s['flat_mm'][0]} x {s['flat_mm'][1]} mm"]
        if s['bends']:
            b = s['bend_spec']
            spec.append(f"{s['bends']} bends, 90 deg, SendCutSend's {b['inside_radius_in']} in radius (K {b['k_factor']}, bend deduction "
                        f"{b['bend_deduction_in']} in): the DXF's BEND layer marks the lines (the app reads them; each 90 deg UP); flanges as the STEP")
        for k, n in (s.get('hardware') or {}).items():
            spec.append(f'{n} x PEM {k} pressed by SendCutSend (hardware insertion), positions as the STEP')
        for k, n in (s.get('countersinks') or {}).items():
            spec.append(f'{n} x 90 deg countersinks for {k} flat heads (SendCutSend countersinking), the side the STEP shows')
        if name == 'bus_bar':
            spec.append('cut only: the five Ø6.4 holes take the lugs\' M6 screws into nuts held in the printed insulator (SendCutSend does '
                        'no service on a part under 1 in wide)')
        if name == 'floor_tray':
            spec.append('tapping: the two Ø2.5 holes M3 x 0.5 (the VN-100)')
        spec.append('deburr (SendCutSend\'s deburring); no finish needed')
        row = {'key': name, 'qty': s['qty'], 'vendor': 'SendCutSend (sendcutsend.com: upload the DXF, pick the material, add the services above)',
               'backup': 'OSH Cut (oshcut.com: instant price from the DXF or STEP; bends and PEM nuts)',
               'material': f"{s['material']} {s['thickness_in']} in", 'mass_g_each': s['mass_g_each'],
               'size_mm': [round(v, 1) for v in s['flat_mm']] + [s['thickness_mm']], 'step': s['step'], 'dxf': s['dxf'],
               'drawing': s['dxf'], 'spec': spec, 'rules': s['rule_violations'] or 'SendCutSend rules checked: none broken',
               'price_estimate_usd_each': est.get(name)}
        pr = prices.get(name) or {}
        fin = pr.get('final') or {}
        same = pr.get('order', {}).get('qty') == s['qty'] and not pr.get('refused') and not pr.get('error')
        if fin.get('each') is not None and same:
            row.update({'price_usd_each': fin['each'], 'price_read_on': pr['read_on'], 'price_usd_line': fin.get('subtotal'),
                        'price_breaks_usd_each': fin.get('breaks'), 'ships_by': fin.get('arrives'),
                        'price_note': (f"SendCutSend's instant price, read in its app on {pr['read_on']} from the uploaded DXF "
                                       f"(tools/sendcutsend_quote.py): {s['material']} {s['thickness_in']} in, "
                                       + (', '.join(f'{k} {v if isinstance(v, str) else len(v)}' for k, v in (pr.get('picked') or {}).items()
                                                    if k != 'finish') or 'cut only')
                                       + f", deburred, qty {s['qty']}; cutting alone ${(pr.get('cut_only') or {}).get('each')} each")})
        else:
            row.update({'price_usd_each': None,
                        'price_note': ('an estimate until the instant price is read: run tools/sendcutsend_quote.py --only ' + name
                                       + (f" (last read: {pr.get('refused') or pr.get('error')})" if pr else ''))})
        row['stage'] = s.get('stage', 'P1')
        out.append(row)
    return out


def build():
    cat = catalogue()
    body = json.loads((R / 'exports/body/body.json').read_text())
    pending = []

    def L(key, qty, why, **kw):
        try:
            return line(cat, key, qty, why, **kw)
        except KeyError:                                   # specified, not yet tied to a listed product page
            pending.append({'item': key, 'qty': qty, 'for': why, 'note': 'not in the catalogue yet: a product page to read (D40)'})
            return None
    bom = {
        'note': 'One robot. The first seller of each line is the one to order from; the rest are backups (D40). Quantities include '
                'spares where noted. Generated by cad/body_bom.py from the CAD (cad/body_frame.py, cad/body_layout.py) and '
                'catalog/body.json; docs/body-orders.md is the order list by seller, docs/body-electrical.md the wiring.',
        'p0_power_skid': [
            L('main_switch', 1, 'the main switch: low side, between the bay\'s - and the - bus; momentary mode (D54)'),
            L('blue-sea-5191-mrbf-terminal-fuse-block', 1, 'the main fuse\'s block on the bay\'s + lead (on 3 mm printed PETG spacers; its M8 post insulated from the plate)'),
            L('mrbf_80a', 2, 'the main fuse (80 A, 58 V DC, 2 kA at 58 V); one spare'),
            L('fuse_mini58_20a', 8, 'the four RS-04 branches (14 AWG); four spares'),
            L('fuse_mini58_30a', 4, 'the two VESC branches (12 AWG; the VESCs\' battery current limit 20 A); two spares'),
            L('fuse_mini58_10a', 8, 'the TRACO input (W16), the turret\'s branch (W17), the J501 (W21) and the 12 V loads (W22); four spares'),
            L('fuse_mini58_5a', 2, 'the INA228\'s VBUS sense lead (W32, 22 AWG); one spare'),
            L('fuse_holder_mini_inline', 12, 'one per branch (11) and a spare: labelled "58 V fuses only"; pull only with the packs out'),
            L('traco-tep-150-4812wi', 1, '12 V 12.5 A, 18-75 V in, isolated (D65): the J501 and the 12 V rail, in place of the DDR-120C-24 '
                                        'and the DDR-60L-12 (both start too high or are too small for 30-41 V)'),
            L('buck_5v', 1, '5 V from the 12 V rail: the MCU, VN-100, CAN transceivers, radio receiver'),
            L('shunt_150a', 1, 'the current shunt in the + lead after the MRBF (high side: the INA228 survives the switch opening)'),
            L('ina228', 1, 'pack voltage and current to the MCU over I2C (its own 15 mOhm shunt removed, wired to the external shunt)'),
        ],
        'p0_battery': [
            L('dewalt-dcb609', 2, 'the battery (D65): two FLEXVOLT 9.0 Ah packs in 20 V mode, in series (10S, 30-41 V); '
                                  'the user\'s own packs and chargers serve'),
            L('terrafirma-dewalt-20v-adapter-10awg', 1, 'the packs\' rail adapters (4-pack: two used, two spare): 10 AWG leads, 30 A stated'),
            L('xt90s_pair', 2, 'the bay\'s lead (anti-spark: female on the bay, male on the robot) and the series link between the packs'),
            L('thumbscrew_m3x10', 4, 'the bay\'s two doors (two each, into the rails\' end inserts): tool-free'),
            L('vhb_tape_25mm', 1, 'the bay\'s TPU skids (3M VHB 5952, 25 mm)'),
        ],
        'p0_control': [
            L('nucleo_g474re', 1, 'the balance and power MCU (three FDCAN: buses A, B, C)'),
            L('can_pal', 3, 'CAN transceivers for the MCU\'s buses A, B, C'),
            L('radio_stop_rx', 1, 'the radio stop\'s receiver (D37), on the 5 V rail'),
            L('radio_stop_relay', 1, 'the radio\'s switch: its contact feeds the stop relay\'s coil (closed = run, open on the failsafe)'),
            L('stop_relay_dpdt', 2, 'the stop relay (one spare): pole A the turret\'s safety loop, pole B its bus branch (D66); on the MCU board'),
        ],
        'p0_wiring': [
            L('wire_8awg', 1, 'the bay\'s lead to the MRBF, the shunt, the switch and the bus bars (about 1.5 m; red heat-shrink on the + runs)'),
            L('wire_12awg', 1, 'the two VESC branches (about 1.2 m red + black)'),
            L('wire_14awg', 1, 'the four RS-04 branches, the frame bond (W33), the turret\'s branch and the J501\'s 12 V (about 4 m red + black)'),
            L('wire_18awg', 1, 'the converter\'s input, the 12 V loads (about 2 m red + black)'),
            L('wire_22awg', 1, '5 V and signal wiring; the CAN pairs twisted by hand (about 6 m)'),
            L('lug_8awg_m6', 10, 'the bus bars\' M6 taps'),
            L('lug_8awg_m8', 4, 'the MRBF block\'s M8 studs and the shunt'),
            L('ferrules', 1, 'every screw terminal (the converter, the switch)'),
            L('xt60h_f', 6, 'sockets on the robot, no live pins (D58, hazard 11): the six bus branch leads\' ends (W10-W15)'),
            L('xt60h_m', 2, 'the two VESC leads\' plugs (the devices carry the pins; the RS-04 pigtails\' XT60H-M come with the leg\'s '
                            'pigtails, docs/body-next-plan.md 5.1 item 5)'),
            L('xt30_f', 4, 'sockets on the robot: the J501 (W21), the lidar box (W24), the turret (W34); one spare'),
            L('xt30_m', 4, 'the devices\' pins: the J501\'s DC-IN and the lidar box\'s adapter leads, two spare'),
            L('gh_lead_2p_300', 8, 'CAN and I2C leads to the transceivers and the INA228'),
        ],
        'p1_frame_hardware': [L(k, q, why) for k, (q, why) in hardware_counts().items()],
        'p3_shell': p3_shell(L),
        'p2_head': [L(k, q, why) for k, (q, why) in joint_hardware('P2').items()],
        'tools': [
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
            {'item': '5/16-18 nylon-insert locknut (the SSC1 pods\' feet in the ear brackets, P3)', 'qty': 2, 'for': 'the ears',
             'note': 'McMaster\'s 95615A (grade 5, zinc) has it; the product page for 5/16-18 is still to read (A120 is 1/4-20, A140 3/8-16)'},
            {'item': 'Switchcraft TB4M mini-XLR 4-pin panel receptacle (the radio-stop jack, P3: STOP A/B, +12 V, GND)', 'qty': 1, 'for': 'the rear face',
             'note': 'a listed part (DigiKey, Mouser); price to read; the turret\'s pendant uses its 3-pin TB3M (catalog/turret.json)'},
            {'item': 'RP-SMA bulkhead pigtails x 4 (the J501\'s radios to the rear face, P3)', 'qty': 4, 'for': 'the rear face\'s D-flat holes',
             'note': 'with the J501\'s Wi-Fi module when it is chosen (the j501-agx project\'s antenna note)'},
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
    for k, v in list(bom.items()):
        if isinstance(v, list):
            bom[k] = [r for r in v if r is not None]
    bom['to_source'] += pending
    priced = [r for k, v in bom.items() if isinstance(v, list) and not k.startswith(('not_', 'to_source', 'made_to_order', 'p2_', 'p3_')) for r in v]
    bom['price_usd_known'] = round(sum(_line_cost(r) for r in priced), 2)             # P0 + P1's bought parts
    bom['p2_usd'] = round(sum(_line_cost(r) for r in bom.get('p2_head', []) if not r.get('from_pack_of'))
                          + sum((m['price_usd_each'] if m['price_usd_each'] is not None else (m['price_estimate_usd_each'] or 0)) * m['qty']
                                for m in bom['made_to_order'] if m.get('stage') == 'P2'), 2)
    bom['made_to_order_estimate_usd'] = round(sum((m['price_estimate_usd_each'] or 0) * m['qty'] for m in bom['made_to_order']
                                                  if m.get('stage', 'P1') in ('P0', 'P1')), 2)
    bom['p3_usd'] = round(sum(_line_cost(r) for r in bom.get('p3_shell', []) if not r.get('from_pack_of'))
                          + sum((m['price_usd_each'] if m['price_usd_each'] is not None else (m['price_estimate_usd_each'] or 0)) * m['qty']
                                for m in bom['made_to_order'] if m.get('stage') == 'P3'), 2)
    bom['made_to_order_usd'] = round(sum((m['price_usd_each'] if m['price_usd_each'] is not None else (m['price_estimate_usd_each'] or 0))
                                         * m['qty'] for m in bom['made_to_order'] if m.get('stage', 'P1') in ('P0', 'P1')), 2)
    bom['made_to_order_priced'] = all(m['price_usd_each'] is not None for m in bom['made_to_order'])
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
    lists = [k for k, v in bom.items() if isinstance(v, list) and not k.startswith(('not_', 'to_source', 'made_to_order', 'p2_', 'p3_'))]
    made01 = [m for m in bom['made_to_order'] if m.get('stage', 'P1') in ('P0', 'P1')]
    made2 = [m for m in bom['made_to_order'] if m.get('stage') == 'P2']
    made3 = [m for m in bom['made_to_order'] if m.get('stage') == 'P3']
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

1. **SendCutSend** (section 1): upload each DXF from `exports/body/sendcutsend/` at app.sendcutsend.com, pick the
   material and thickness in its file name, add the bends (the app reads the DXF's BEND layer: 90 deg, UP), PEM nuts,
   countersinks and tapping listed, deburring, and the quantity. The prices below were read that way in the app
   (`tools/sendcutsend_quote.py`, no account needed for a price); re-read them before the cart goes.
2. **McMaster-Carr** (section 2, first table): one cart, next-day.
3. **The other sellers** (section 2): the ones that ship from China first (LCSC, Daly, Flipsky): one to three weeks.
4. **Print** (section 5) while the orders arrive.
""", "## 1. SendCutSend (T2: the frame and the power plate): custom parts at an instant price\n",
           "| Part | Qty | Material | Flat (mm) | Operations | Files | Price each | Line |", "|---|---|---|---|---|---|---|---|"]
    tot_m, read = 0.0, []
    for m in made01:
        ops = '; '.join(x for x in m['spec'][1:] if not x.startswith('deburr'))
        each = m['price_usd_each'] if m['price_usd_each'] is not None else m['price_estimate_usd_each']
        tot_m += (each or 0) * m['qty']
        if m['price_usd_each'] is not None:
            read.append(m['price_read_on'])
        price = (f"${m['price_usd_each']:.2f} (read {m['price_read_on']})" if m['price_usd_each'] is not None
                 else f"~${m['price_estimate_usd_each']:.0f} (estimate)")
        out.append(f"| {m['key']} | {m['qty']} | {m['material']} | {m['size_mm'][0]} x {m['size_mm'][1]} | {ops} | "
                   f"[DXF](../{m['dxf']}), [STEP](../{m['step']}) | {price} | ${(each or 0) * m['qty']:.2f} |")
    est_all = sum((m['price_estimate_usd_each'] or 0) * m['qty'] for m in made01)
    out.append(f"\n**SendCutSend: ${tot_m:.2f}** for the set" + (f" (instant prices read {min(read)} in SendCutSend's app)" if read else '')
               + f"; the plan's estimate was ~${est_all:.0f}. Shipping is free over SendCutSend's threshold. Backup: OSH Cut "
               "(oshcut.com), which prices the same DXF instantly and also bends and inserts PEM nuts. The bus bars can instead be two "
               "Victron VBB115040020 (150 A, 70 V, $17.82 each, in catalog/body.json), which need no insulators.\n")
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
    priced = all(m['price_usd_each'] is not None for m in made01)
    # ---- the P2 cart: the head, ordered once P1 balances on its tether (D59)
    p2 = 0.0
    if made2 or bom.get('p2_head'):
        out += ["## 6. The P2 cart (the head: order it once P1 balances on its tether)\n",
                "The turret's mount plate (D59) goes under the deck at the riser: the riser's four screws grow to M5 x 16 through it, "
                "and its two ends are screwed down through the deck into its PEM nuts. **In the P1 deck, drill the two Ø5.5 holes "
                "by hand** at (x, y) = " + ' and '.join(f'({x:.0f}, {y:.0f})' for x, y in __import__('body_frame').turret_plate_end_holes())
                + " mm (robot frame): hold the plate on the riser's four screws and spot through its PEM nuts with an M5 transfer punch. "
                "A Rev B deck (lever 3) gets them cut.\n",
                "| Part | Qty | Made | Price each | Line | For |", "|---|---|---|---|---|---|"]
        for m in made2:
            each = m['price_usd_each'] if m['price_usd_each'] is not None else m['price_estimate_usd_each']
            p2 += (each or 0) * m['qty']
            price = (f"${m['price_usd_each']:.2f} (read {m['price_read_on']})" if m['price_usd_each'] is not None
                     else f"~${m['price_estimate_usd_each'] or 0:.0f} (estimate)")
            out.append(f"| [{m['key']}](../{m['dxf']}) | {m['qty']} | SendCutSend: {m['material']}, {'; '.join(x for x in m['spec'][1:] if not x.startswith('deburr'))} "
                       f"| {price} | ${(each or 0) * m['qty']:.2f} | {m.get('note', 'D59')} |")
        for r in bom.get('p2_head', []):
            n, pack, pr, c = cost(r)
            if r.get('from_pack_of'):                       # already bought with an earlier stage's pack
                n, c = 0, 0.0
            p2 += c
            s0 = (r.get('sellers') or [{}])[0]
            out.append(f"| [{r.get('part_number') or r['key']}]({s0.get('url')}): {(r.get('name') or r['key'])[:70]} | {r['qty']} | "
                       f"{s0.get('seller')} ({f'{n} x {pack}-pack' if pack != 1 else n}) | ${pr:.2f} | ${c:.2f} | {r['for'][:110]} |")
        out.append(f"\n**P2 cart: ${p2:.2f}** (whole packs; a line marked as taken from an earlier pack costs nothing here).\n")
    p3 = 0.0
    if made3 or bom.get('p3_shell'):
        out += ["## 6b. The P3 cart (the shell, the tub, the guards: order it with P3)\n",
                "The shell and the tub's printed parts are in `exports/body/shell/` with their own print plan; the leg's knee wedges and "
                "apex fillets are envelopes for the leg workstream (`exports/body/shell/*_envelope.step`).\n",
                "| Part | Qty | Made | Price each | Line | For |", "|---|---|---|---|---|---|"]
        for m in made3:
            each = m['price_usd_each'] if m['price_usd_each'] is not None else m['price_estimate_usd_each']
            p3 += (each or 0) * m['qty']
            price = (f"${m['price_usd_each']:.2f} (read {m['price_read_on']})" if m['price_usd_each'] is not None
                     else f"~${m['price_estimate_usd_each'] or 0:.0f} (estimate)")
            out.append(f"| [{m['key']}](../{m['dxf']}) | {m['qty']} | SendCutSend: {m['material']}, {'; '.join(x for x in m['spec'][1:] if not x.startswith('deburr'))} "
                       f"| {price} | ${(each or 0) * m['qty']:.2f} | the battery tub (D61) |")
        for r in bom.get('p3_shell', []):
            n, pack, pr, c = cost(r)
            if r.get('from_pack_of'):
                n, c = 0, 0.0
            p3 += c
            s0 = (r.get('sellers') or [{}])[0]
            out.append(f"| [{r.get('part_number') or r['key']}]({s0.get('url')}): {(r.get('name') or r['key'])[:70]} | {r['qty']} | "
                       f"{s0.get('seller')} ({f'{n} x {pack}-pack' if pack != 1 else n}) | ${pr:.2f} | ${c:.2f} | {r['for'][:110]} |")
        out.append(f"\n**P3 cart: ${p3:.2f}** (whole packs; the bought shell parts (the SSC1 pods, the D435s, the DualEye) are in the "
                   "sensor head's order).\n")
    out.append(f"## 7. Totals\n\n| | |\n|---|---|\n| Bought (section 2) | ${grand:.2f} |\n"
               f"| SendCutSend (section 1{', instant prices' if priced else ', partly estimated'}) | ${tot_m:.2f} |\n"
               f"| Filament used (section 5) | ${fil:.2f} |\n| **Body P0 + P1** | **${grand + tot_m + fil:.2f}** |\n"
               f"| P2 cart (section 6) | ${p2:.2f} |\n| P3 cart (section 6b) | ${p3:.2f} |\n\n"
               "Not included: the compute and sensors (section 3, R13), the legs and their VESCs (the leg workstream's order), the turret "
               "(the turret workstream's), the shell (P3), shipping and tax.\n")
    path.write_text('\n'.join(out))
    return grand, tot_m


def main():
    bom = build()
    OUT.write_text(json.dumps(bom, indent=1) + '\n')
    write_orders(bom)
    n = sum(len(v) for k, v in bom.items() if isinstance(v, list))
    print(f"exports/body/bom.json: {n} lines; P0 + P1: bought ${bom['price_usd_known']:.2f} + made to order ${bom['made_to_order_usd']:.2f}; "
          f"the P2 cart ${bom['p2_usd']:.2f} "
          f"({'every price read' if bom['made_to_order_priced'] else 'some estimated'}; the estimate was ${bom['made_to_order_estimate_usd']:.2f})")


if __name__ == '__main__':
    main()
