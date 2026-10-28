"""Writes catalog/rig.json: the single-leg rig's bought and ordered parts (rig, electronics, the bench, leg additions),
from the price reads of the date below (public product pages; McMaster through cadagent.mcmaster, one page at a time).
One item per line of the order list, in catalog/SCHEMA.md's shape plus key, group, qty and alternates (each a second
seller with a price: D40).

    .venv/bin/python tools/rig_catalog.py            # -> catalog/rig.json; then tools/rig_orders.py
"""
import json
import sys
from pathlib import Path

D = '2026-10-27'
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'catalog' / 'rig.json'
items = []


def alt(supplier, pn, url, price_text, each, pack=1, stock=None, drop_in=True, changes=None, how='product page'):
    return {'supplier': supplier, 'part_number': pn, 'url': url, 'price': price_text, 'price_usd_each': each, 'pack_qty': pack,
            'stock': stock, 'drop_in': drop_in, 'changes': changes, 'checked': D, 'how_read': how}


def add(key, group, category, vendor, model, name, price, qty, url, *, seller=None, pack=1, pack_price=None, stock=None,
        in_stock=True, ships='US', how='product page', note='', alts=(), specs=None, used_for='', confidence=None):
    items.append({
        'id': key.replace('_', '-'), 'key': key, 'group': group, 'category': category, 'vendor': vendor, 'model': model, 'name': name,
        'price_usd': price, 'price_note': (f'{pack} per pack at ${pack_price:.2f}' if pack > 1 and pack_price else '') + (f'; read {how}' if how != 'product page' else ''),
        'price_checked': D, 'pack_qty': pack, 'pack_price_usd': pack_price if pack > 1 else price,
        'buy': [{'seller': seller or vendor, 'url': url, 'in_stock': in_stock, 'ships_from': ships, 'stock_text': stock}],
        'specs': specs or {}, 'sources': [url], 'confidence': confidence or ('product page' if how == 'product page' else how),
        'used_for': used_for, 'qty': qty, 'notes': note, 'alternates': list(alts)})


MIS = 'https://us.misumi-ec.com/vona2/detail/'
MCM = 'https://www.mcmaster.com/'
# ------------------------------------------------------------------ the rig: guide, frame, fasteners
add('rail_hgr15_kit', 'rig', 'fastener', 'Amazon (iMetrx 3D)', 'ASIN B0GJZCLXWJ (1000mm / 2)',
    'HGR15 rail 1000 mm x 2 + HGH15CA block x 4 (one pack)', 69.99, 1, 'https://www.amazon.com/dp/B0GJZCLXWJ',
    stock='Only 12 left in stock', specs={'rail': 'HGR15, 1000 mm', 'blocks': 'HGH15CA x 4', 'rating': 'none (unbranded HIWIN-pattern copy)'},
    used_for='the carriage guide: two rails on the post\'s front slots, two blocks each',
    note='Generic HIWIN-pattern copy (no load rating; the checks use HIWIN\'s 2017 C0 16.97 kN: worst block 2.6 kN, SF 6.6). On arrival: '
         'blocks run smooth with no play by hand; same hole pitch (60) and end distance (20) as the drawing. HGR20 is not a drop-in: '
         'its 44 mm blocks overlap at the post\'s 40 mm slot spacing.',
    alts=[alt('Amazon (Coavoo Transmission)', 'ASIN B0BMWQ5J7T', 'https://www.amazon.com/dp/B0BMWQ5J7T', '$72.99 per 1 rail + 2 blocks (buy 2)', 72.99,
              stock='Only 3 left in stock', changes='two packs ($145.98) for the same parts'),
          alt('VXB Bearings', 'VXB0BMWQ5J7T', 'https://vxb.com/products/beefy-square-cnc-linear-rail-kit-hgh15-39-37-inch', '$159.95',
              159.95, changes='the Coavoo kit resold, 5-10 business days'),
          alt('Amazon (Mycncshop)', 'ASIN B087ZCH3BW (FBT HGR15CA-L1000mm)', 'https://www.amazon.com/dp/B087ZCH3BW', '$151.00', 151.0)])
for key, pn, L, qty, price, a_price, used in (
        ('extrusion_8080_1200', 'HFS8-8080-1200', 1200, 1, 97.44, 151.73, 'the post'),
        ('extrusion_4040_900', 'HFS8-4040-900', 900, 2, 27.72, 42.69, 'the base\'s side members'),
        ('extrusion_4040_620', 'HFS8-4040-620', 620, 4, 19.09, 30.34, 'the base\'s cross members: front, wheel, bumper, rear'),
        ('extrusion_4040_720', 'HFS8-4040-720', 720, 1, 22.17, 34.75, 'the brace'),
        ('extrusion_4080_620', 'HFS8-4080-620', 620, 1, 34.65, 54.69, 'the post\'s member, lying flat under it')):
    series = {'8080': '110302690740', '4040': '110302689860', '4080': '110302690310'}[pn.split('-')[1]]
    add(key, 'rig', 'sheet_material', 'MISUMI', pn, f'Aluminium extrusion {pn.split("-")[1]}, 8 series (10 mm slot), cut to {L} mm', price, qty,
        f'{MIS}{series}/?HissuCode={pn}', stock='Ship Date Wed. Oct 28, 2026', ships='US', used_for=used,
        specs={'length_mm': L, 'alloy': 'A6N01SS-T5', 'section': pn.split('-')[1]},
        note='Price shown without logging in; cut to the exact length (no waste). Order the whole frame from MISUMI: its brackets and nuts are 8-series.',
        alts=[alt('80/20 Inc.', f'40-{pn.split("-")[1]} cut to {L} mm', f'https://8020.net/40-{pn.split("-")[1]}.html',
                  'per mm + cut charge', a_price, drop_in=False,
                  changes="80/20's own 40-series slot: MISUMI's brackets and nuts are not verified to fit; switch the whole frame and its fasteners together")])
add('bracket_corner_8', 'rig', 'fastener', 'MISUMI', 'HBLTS8-C-SEP', 'Corner bracket, 8 series, with 2 x M8 screws + 2 drop-in spring nuts', 4.42, 24,
    f'{MIS}110300450470/?HissuCode=HBLTS8-C-SEP', stock='Ship Date Same Day', used_for='the base\'s 10 joints (2 each) and the post\'s foot (4)',
    specs={'allowable_load_n': 2058, 'mass_g': 65.8}, note='Each bracket brings its own two screws and drop-in nuts.',
    alts=[alt('MISUMI', 'HBLTS8-C-SEC', f'{MIS}110300450470/?HissuCode=HBLTS8-C-SEC', '$5.24', 5.24, changes='another screw set'),
          alt('80/20 Inc.', '40-4376 + 3 x 75-3422', 'https://8020.net/40-4376.html', '$7.48 + 3 x $1.14', 10.90, drop_in=False, changes='80/20 slot system')])
add('bracket_free_angle_8', 'rig', 'fastener', 'MISUMI', 'HBLTBA40-SET1', 'Free-angle bracket for 40 mm 8-series profile, with its mounting screws and nuts',
    8.78, 4, f'{MIS}110302255430/?HissuCode=HBLTBA40-SET1', stock='Ship Date Same Day',
    used_for='the brace\'s two ends, two per end (both side faces): up to 2.9 kN in the brace in a jump',
    note='M10 pivot screw included. Two per joint so no single pair of drop-in nuts carries the brace\'s peak.',
    alts=[alt('MISUMI', 'HBLTBBN40-SET', f'{MIS}110302255430/?HissuCode=HBLTBBN40-SET', '$10.15', 10.15),
          alt('80/20 Inc.', '40-2085 hinge', 'https://8020.net/40-2085.html', '$14.34', 14.34, drop_in=False,
              changes='rated 34 kg: too light for the brace; not a substitute')])
add('nut_m8_dropin', 'rig', 'fastener', 'MISUMI', 'HNTA8-8', 'Drop-in nut, 8 series, M8', 0.90, 16, f'{MIS}110302257010/?HissuCode=HNTA8-8',
    stock='Ship Date Same Day', used_for='top stop (4), drop bracket (2), pod (4), spares',
    alts=[alt('80/20 Inc.', '75-3422 (M8 x 16 BHSCS + slide-in nut)', 'https://8020.net/75-3422.html', '$1.14', 1.14, drop_in=False, changes='slide-in, 80/20 slot')])
add('screw_m8x16_bh', 'rig', 'fastener', '80/20 Inc.', '13-8316', 'M8 x 16 button head socket cap screw', 0.61, 16, 'https://8020.net/40-4376.html',
    how='product page (related-products block of 40-4376)', used_for='with the extra M8 drop-in nuts',
    alts=[alt('80/20 Inc.', '75-3422', 'https://8020.net/75-3422.html', '$1.14 (screw + nut)', 1.14)])
add('nut_m4_dropin', 'rig', 'fastener', 'MISUMI', 'HNTA8-4', 'Drop-in nut, 8 series, M4', 0.90, 36, f'{MIS}110302257010/?HissuCode=HNTA8-4',
    stock='Ship Date Same Day', used_for='the rails: 17 per rail at 60 mm, 2 spare',
    alts=[alt('MISUMI', 'PACK-HNTA8-4 (100)', f'{MIS}110302257010/?HissuCode=PACK-HNTA8-4', '$61.83 per 100', 0.62, pack=100)])
add('nut_m6_dropin', 'rig', 'fastener', 'MISUMI', 'HNTA8-6', 'Drop-in nut, 8 series, M6', 0.90, 12, f'{MIS}110302257010/?HissuCode=HNTA8-6',
    stock='Ship Date Same Day', used_for='the deck (8) and the bottom bumpers (4)')
add('screw_m4x16_rail', 'rig', 'fastener', 'McMaster-Carr', '91292A118', '18-8 stainless socket head screw M4 x 16', 0.1163, 36, f'{MCM}91292A118/',
    pack=100, pack_price=11.63, used_for='the rails into the drop-in nuts (HIWIN\'s M4 x 16)',
    note='7 mm head fits the rail\'s 7.5 mm counterbore; a flanged head would not.',
    alts=[alt('Bolt Depot', '23082 (class 12.9, zinc)', 'https://boltdepot.com/', '$0.19 each', 0.19)])
add('screw_m4x10_block', 'rig', 'fastener', 'McMaster-Carr', '91290A144', 'Black-oxide alloy steel socket head screw M4 x 10', 0.1355, 16,
    f'{MCM}91290A144/', pack=100, pack_price=13.55, used_for='the four blocks onto the plate: 3.65 mm into the 5 mm threads (0.9 d, steel)',
    note='Same part as catalog/turret.json turret_screw_m4x10. No washer (a washer would leave 2.9 mm of thread).')
add('screw_m5x16_plate', 'rig', 'fastener', 'McMaster-Carr', '91290A232', 'Black-oxide alloy steel socket head screw M5 x 16', 0.1727, 6,
    f'{MCM}91290A232/', pack=100, pack_price=17.27, used_for='the plate onto the hip frame\'s six M5 inserts (with washers)',
    note='Same part as catalog/hardware.json screw_m5x16.')
add('washer_m5_plate', 'rig', 'fastener', 'McMaster-Carr', '93475A240', '18-8 washer for M5', 0.0424, 6, f'{MCM}93475A240/', pack=100, pack_price=4.24,
    used_for='under the plate screws', note='Same part as catalog/hardware.json washer_m5.')
add('screw_m6x30_deck', 'rig', 'fastener', 'McMaster-Carr', '91290A332', 'Black-oxide alloy steel socket head screw M6 x 30', 0.2272, 8, f'{MCM}91290A332/',
    pack=50, pack_price=11.36, used_for='the deck into the members\' top slots (18 mm ply + washer + the slot\'s lip, 7.6 mm into the nut)',
    note='Same part as catalog/hardware.json screw_m6x30.')
add('washer_m6_deck', 'rig', 'fastener', 'McMaster-Carr', '91116A150', '18-8 oversized washer for M6 (18 mm OD)', 0.294, 8, f'{MCM}91116A150/',
    pack=50, pack_price=14.70, used_for='under the deck screws', note='Same part as catalog/hardware.json washer_m6_large.')
add('screw_m6x35_bumper', 'rig', 'fastener', 'McMaster-Carr', '91290A334', 'Black-oxide alloy steel socket head screw M6 x 35', 0.2422, 4, f'{MCM}91290A334/',
    pack=50, pack_price=12.11, used_for='the bottom bumpers\' bases, counterbored 14 mm', note='Same part as catalog/hardware.json screw_m6x35.')
# ------------------------------------------------------------------ ballast
add('ballast_shaft', 'rig', 'fastener', 'McMaster-Carr', '6649K433', 'Tapped linear shaft 1 in x 6 in, 1050 steel, 3/8-16 x 3/4 in deep both ends', 52.94, 2,
    f'{MCM}6649K433/', used_for='the two ballast posts', specs={'mass_g': 607},
    alts=[alt('McMaster-Carr', '4162N31 + 6435K18 collar', f'{MCM}4162N31/', '$32.35 + $6.07', 38.42, changes='tapped one end only: a collar retains the plates')])
add('screw_3_8x1', 'rig', 'fastener', 'McMaster-Carr', '91251A624', 'Alloy steel socket head screw 3/8-16 x 1 in', 0.4992, 2, f'{MCM}91251A624/',
    pack=25, pack_price=12.48, used_for='each post through the plate (17.8 mm into the 19 mm thread with the washer)',
    alts=[alt('McMaster-Carr', '91251A622 (3/4 in, no washer)', f'{MCM}91251A622/', '$11.17 per 25', 0.4468, pack=25)])
add('washer_3_8', 'rig', 'fastener', 'McMaster-Carr', '91090A121', 'Oversized washer for 3/8 in, 1.25 in OD', 0.1424, 2, f'{MCM}91090A121/',
    pack=50, pack_price=7.12, used_for='under the post screws on the plate\'s front')
add('screw_3_8x3_4', 'rig', 'fastener', 'McMaster-Carr', '91251A622', 'Alloy steel socket head screw 3/8-16 x 3/4 in', 0.4468, 2, f'{MCM}91251A622/',
    pack=25, pack_price=11.17, used_for='the posts\' free ends, with the 2 in washers that hold the plates on')
add('washer_2in', 'rig', 'fastener', 'McMaster-Carr', '91117A219', 'Oversized washer 0.406 in ID x 2.000 in OD', 2.718, 2, f'{MCM}91117A219/',
    pack=5, pack_price=13.59, used_for='retain the weight plates')
add('weight_plate_2p5', 'rig', 'fastener', 'Body-Solid', 'RPB2-5', 'Cast iron standard plate, 2.5 lb, 1 in hole (129.5 x 20.3 mm)', 6.65, 2,
    'https://bodysolid.com/cast-iron-standard-plates', how='product page (size selected)', used_for='ballast: one per post at 14.75 kg',
    specs={'mass_kg': 1.134, 'diameter_mm': 129.5, 'thickness_mm': 20.3},
    alts=[alt('Amazon (CAP Barbell)', 'ASIN B0FNPPH748 (4-pack)', 'https://www.amazon.com/dp/B0FNPPH748', '$17.81 per 4', 4.45, pack=4,
              changes='the page gives no diameter: check under 150 mm')])
add('weight_plate_1p25', 'rig', 'fastener', 'Body-Solid', 'RPB1-25', 'Cast iron standard plate, 1.25 lb, 1 in hole (101.6 x 10.2 mm)', 3.33, 2,
    'https://bodysolid.com/cast-iron-standard-plates', how='product page (size selected)', used_for='ballast: the 16 kg sweep',
    specs={'mass_kg': 0.567, 'diameter_mm': 101.6},
    alts=[alt('Amazon (CAP Barbell)', 'ASIN B002BRAN66', 'https://www.amazon.com/dp/B002BRAN66', '$18.97', 18.97)])
add('washer_trim_3p5in', 'rig', 'fastener', 'McMaster-Carr', '91117A251', 'Oversized washer for 1 in screw, 3.5 in OD (~0.14 kg)', 6.19, 4,
    f'{MCM}91117A251/', used_for='fine ballast: trims the carried mass to within 0.07 kg')
add('quick_pin', 'rig', 'fastener', 'McMaster-Carr', '92384A274', 'Ball-lock quick-release pin with D-ring, 3/8 in, 1-1/2 in usable, 17-4 PH', 38.21, 1,
    f'{MCM}92384A274/', used_for='the drop test\'s release (S4)', specs={'double_shear_lbf': 20700},
    alts=[alt('McMaster-Carr', '92384A760 (1-3/4 in usable)', f'{MCM}92384A760/', '$40.73', 40.73)])
add('pin_lanyard', 'rig', 'fastener', 'McMaster-Carr', '90312A296', 'Lanyard, 3/64 in cable, loop-to-eye, 12 in', 3.26, 1, f'{MCM}90312A296/',
    used_for='keeps the pin on the drop bracket')
add('sling_1in', 'rig', 'fastener', 'Amazon (Megamart USA)', 'ASIN B0026GIUMG', 'Lift-All Type 5 endless polyester sling 1 in x 5 ft (2400 lb vertical)', 17.08, 2,
    'https://www.amazon.com/dp/B0026GIUMG', used_for='the tethers: the carriage to the post (girth-hitched under the top stop), the wheel link to the carriage',
    alts=[alt('Amazon (Kivomot)', 'ASIN B0FRRVHXTR (2-pack, eye-eye 6.5 ft)', 'https://www.amazon.com/dp/B0FRRVHXTR', '$12.58 per 2', 6.29, pack=2)])
add('carabiner', 'rig', 'fastener', 'Amazon (XINDA)', 'ASIN B07D73RRH5 (2-pack)', 'Screwgate carabiner, 25 kN, 2-pack', 8.495, 4,
    'https://www.amazon.com/dp/B07D73RRH5?th=1', pack=2, pack_price=16.99, used_for='the tethers\' ends',
    alts=[alt('Amazon (STURME)', 'ASIN B085HLB374 (2-pack)', 'https://www.amazon.com/dp/B085HLB374', '$16.99 per 2', 8.495, pack=2)])
add('plywood_18', 'rig', 'sheet_material', 'The Home Depot', 'Internet #202093836', 'Sanded plywood 23/32 in, 2 x 4 ft project panel', 23.76, 1,
    'https://www.homedepot.com/p/Handprint-23-32-in-x-2-ft-x-4-ft-Sanded-Plywood-300969/202093836', how='search snippet',
    used_for='the deck (600 x 400) and the load plate\'s pad (400 x 300)', confidence='search snippet',
    note='The store page blocks automated reads; the price is a search snippet (one snippet showed 0 in stock online). Any 18 mm plywood or MDF.',
    alts=[alt("Lowe's", 'Item #7710, Model #12611', 'https://www.lowes.com/pd/Unbranded-23-32-in-x-2-ft-x-4-ft-Pine-Sanded-Plywood/5001997945',
              '$25.98-29.48 (snippets)', 27.5, how='search snippet')])
add('rubber_mat', 'rig', 'sheet_material', 'Amazon (Boomerang Rubber)', 'ASIN B0F8RCXB7D', 'Rubber mat 3 x 4 ft x 5/16 in, 2-pack', 52.0, 1,
    'https://www.amazon.com/dp/B0F8RCXB7D', used_for='under the base: the floor carries every member (the wheel member under the tyre most)',
    alts=[alt('Amazon (uxcell)', 'ASIN B0DP9TXB59 (M8 levelling feet, 8)', 'https://www.amazon.com/dp/B0DP9TXB59', '$33.99 per 8', 4.25, pack=8,
              drop_in=False, changes='feet in the bottom slots; one must go under the wheel member\'s middle (it carries 3.4 kN at a jump)')])
add('carriage_plate', 'rig', 'fab_service', 'SendCutSend', 'carriage_plate.dxf, 6061-T6 0.250 in',
    'Carriage plate, laser-cut 6061-T6 aluminium 0.25 in, 300 x 320 mm, 28 holes and 2 slots', None, 1, 'https://sendcutsend.com/materials/6061-t6-aluminum/',
    how='instant price on upload', used_for='the carriage: the hip frame on its front, the blocks and the ballast posts on its back',
    specs={'drawing': 'exports/rig/sendcutsend/carriage_plate.dxf', 'thickness_mm': 6.35, 'mass_g': 1609},
    note='Instant price on upload of the DXF (no quote, no account needed to see it at upload); estimate $60-90. Deburr option on.',
    alts=[alt('Xometry', 'carriage_plate.step, 6061-T6 1/4 in sheet cutting', 'https://www.xometry.com/', 'instant price on upload', None)])
# ------------------------------------------------------------------ electronics
add('pack_adapter_60v', 'electronics', 'power_distribution', 'Terrafirma Technology (eBay)', 'eBay 142917514402',
    'DeWalt FLEXVOLT 60 V dock adapter, 12 AWG leads', 16.5, 1, 'https://www.ebay.com/itm/142917514402', how='search snippet', ships='US',
    used_for='the pack into the rig (XT60 on its leads)', confidence='search snippet',
    note='eBay blocks automated reads: price from the search snippet. Check the listing says it engages the 60 V mode (FLEXVOLT packs switch '
         'by the tool\'s tab); measure 54-60 V open-circuit on a charged pack before wiring.',
    alts=[alt('Newegg (heimakeji)', '1DK-013R-00A95', 'https://www.newegg.com/p/1DK-013R-00A95', 'about $23.35 (snippet)', 23.35, how='search snippet')])
add('bench_supply_48v', 'electronics', 'dcdc', 'Bravo Electro', 'Mean Well LRS-600-48', '48 V 12.5 A enclosed supply', 61.60, 1,
    'https://www.bravoelectro.com/lrs-600-48.html', stock='In stock', used_for='bench tests only (B1, B2, first enable): it cannot sink regeneration',
    note='Shuts down after 3 s at 105-150 % load and latches off above 55.2-64.8 V: never on the motors in a squat, jump or drop.',
    alts=[alt('TRC Electronics', 'LRS-600-48', 'https://www.trcelectronics.com/products/mean-well-lrs-600-48', '$66.80', 66.80, stock='210 can ship now'),
          alt('Bravo Electro', 'LRS-600N2-48 (200 % peak)', 'https://www.bravoelectro.com/lrs-600n2-48.html', '$66.10', 66.10)])
add('fuse_kldr030', 'electronics', 'power_distribution', 'Standard Electric Supply', 'Littelfuse KLDR030.TXP', 'Class CC time-delay fuse 30 A, 600 VAC / 300 VDC',
    31.70, 1, 'https://www.standardelectricsupply.com/Littelfuse-KLDR030-TXP-POWR-GARD-Time-Delay-Fuse', stock='812 In Stock',
    used_for='the pack\'s positive, before the contactor', note='300 VDC per Littelfuse\'s datasheet (self-certified; the UL listing is AC).',
    alts=[alt('Galco', 'Littelfuse KLDR30', 'https://www.galco.com/kldr30-lf.html', '$44.33', 44.33, stock='10 In Stock'),
          alt('Galco', 'Mersen ATDR30', 'https://www.galco.com/atdr30-shaw.html', '$19.96', 19.96, stock='31 In Stock', changes='check its DC rating before use')])
add('fuse_holder_cc', 'electronics', 'power_distribution', 'Galco', 'Littelfuse LPSC0001Z', 'Class CC fuse holder, 1-pole, DIN rail, 600 VAC/DC', 28.99, 1,
    'https://www.galco.com/lpsc0001z-littelfuse.html', stock='170 In Stock', used_for='holds the 30 A fuse on the pod\'s DIN rail',
    alts=[alt('Standard Electric Supply', 'Littelfuse LFPSC0001Z', 'https://www.standardelectricsupply.com/Littelfuse-LFPSC0001Z-Powr-Gard-Powr-Safe-Fuse-Holder',
              '$26.48', 26.48, stock='62 In Stock'),
          alt('Galco', 'Mersen USCC1', 'https://www.galco.com/uscc1-shaw.html', '$23.18', 23.18, stock='68 In Stock')])
add('contactor_lev100', 'electronics', 'estop', 'TTI, Inc.', 'TE Kilovac LEV100A4ANG (3-1618389-7)', 'Sealed DC contactor 100 A, 900 VDC, 12 V coil (5.5 W)',
    86.64, 1, 'https://www.tti.com/content/ttiinc/en/apps/part-detail.html?partsNumber=LEV100A4ANG&mfgShortname=TYC', stock='301 In Stock',
    used_for='the hold-to-run power cut in the pack\'s positive', specs={'coil_v': 12, 'coil_w': 5.5, 'contact_a': 100, 'contact_vdc': 900},
    note='Its contacts are polarised: wire its + terminal to the pack (the main current\'s direction); the reverse direction (regeneration) '
         'is rated for fewer breaks. Newark lists it as no longer made; TE\'s own page lists it active.',
    alts=[alt('TTI, Inc.', 'TE EV200AAANA', 'https://www.tti.com/content/ttiinc/en/apps/part-detail.html?partsNumber=EV200AAANA&mfgShortname=TYC',
              '$127.61', 127.61, stock='439 In Stock', changes='bigger (500 A); its own coil economiser'),
          alt('RS Americas', 'LEV100A4ANG (RS 70062417)', 'https://us.rs-online.com/product/te-connectivity/lev100a4ang/70062417/', '$76.47 (snippet)',
              76.47, how='search snippet')])
add('timer_offdelay', 'electronics', 'estop', 'AutomationDirect', 'ProSense T2R-M1-ADJ-240U', 'Timer relay, multifunction (off-delay with a trigger input), 0.1-10 s, 12-125 VDC / 240 VAC, 10 A',
    44.50, 1, 'https://www.automationdirect.com/adc/shopping/catalog/relays_-z-_timers/timer_relays/t2r-m1-adj-240u', stock='76 Available',
    used_for='holds the contactor\'s coil 1.0 s after the pendant is let go', note='The pendant switches its trigger input (a signal), never the coil. '
    'Not the Klemsan Z1K-M2A: a review reports its output on at power-up for the full delay.',
    alts=[alt('DROK', '200350 (LCD multifunction delay relay module, 6-30 V)', 'https://www.droking.com/all-items/relay-1402752649/relay/Time-Delay-Relay-Relay-Switch-DC6V-30V-LCD-Multifunction-Digital-Motor-Controller-Delay-power-cut-break-Trigger-delay-Cycle-timing-circuit-Relay-Module',
              '$6.55', 6.55, changes='a module, not DIN: screw it to the pod; set its mode and 1.0 s on its display'),
          alt('Galco', 'Finder 80.01.0.240.0000', 'https://www.galco.com/80-01-0-240-0000-finder.html', '$78.85', 78.85, stock='ships 11/6')])
add('dcdc_ddr30l12', 'electronics', 'dcdc', 'Bravo Electro', 'Mean Well DDR-30L-12', 'DIN-rail DC-DC, 18-75 V in, 12 V 2.5 A out', 27.60, 1,
    'https://www.bravoelectro.com/ddr-30l-12.html', stock='In stock', used_for='the 12 V rail: the contactor coil, the timer, the pendant loop',
    alts=[alt('TRC Electronics', 'DDR-30L-12', 'https://www.trcelectronics.com/products/mean-well-ddr-30l-12', '$35.36', 35.36, stock='10 can ship now')])
add('usb_can_u2c', 'electronics', 'can_adapter', 'BIQU Equipment', 'BIGTREETECH U2C V2.1 (SKU 1030000107)', 'USB to CAN adapter (candleLight gs_usb: SocketCAN)', 23.99, 1,
    'https://biqu.equipment/products/bigtreetech-ebb36-42-can-bus-u2c-v2-1-klipper-board?variant=39762747949154', stock='orderable', ships='CN',
    used_for='the laptop on the CAN bus at 1 Mbit/s',
    alts=[alt('InnoMaker', 'USB2CAN-Module (isolated)', 'https://www.inno-maker.com/product/usb-can/', '$34.99', 34.99,
              changes='isolated: use it whenever the laptop is on mains'),
          alt('West3D', 'FYSETC UCAN', 'https://west3d.com/products/fystec-ucan-usb-can-out-interface-module-connect-for-can-bus-klipper-expansion', '$19.99', 19.99)])
add('feather_m4_can', 'electronics', 'compute', 'Adafruit', '4759', 'Feather M4 CAN Express (ATSAME51)', 24.95, 1, 'https://www.adafruit.com/product/4759',
    stock='In stock', used_for='the rig node: the pendant\'s loop, RUN frames, the ToF, the load cells, the bus voltage',
    note='Same board as the turret (D41).',
    alts=[alt('Adafruit', '5724 RP2040 CAN Bus Feather', 'https://www.adafruit.com/product/5724', '$19.95', 19.95, drop_in=False,
              changes='an MCP25625 on SPI: rig/firmware needs its CAN driver swapped')])
add('tof_vl53l1x', 'electronics', 'sensor', 'Adafruit', '3967', 'VL53L1X time-of-flight breakout, 30-4000 mm', 14.95, 1, 'https://www.adafruit.com/product/3967',
    stock='In stock', used_for='the carriage\'s height (jump apex) at 50 Hz',
    alts=[alt('SparkFun', 'SEN-14722', 'https://www.sparkfun.com/products/14722', '$29.95', 29.95)])
add('hx711', 'electronics', 'sensor', 'SparkFun', 'SEN-13879', 'HX711 load cell amplifier', 4.95, 1, 'https://www.sparkfun.com/products/13879', stock='In stock',
    used_for='the load plate (stand and squat)', alts=[alt('Adafruit', '5974', 'https://www.adafruit.com/product/5974', '$9.95', 9.95)])
add('load_cells_4x50', 'electronics', 'sensor', 'Amazon (Geekstory)', 'ASIN B079FTXR7Y', '4 x 50 kg half-bridge load cells + HX711', 7.90, 1,
    'https://www.amazon.com/dp/B079FTXR7Y', stock='Only 10 left', used_for='the load plate under the wheel (not in jumps or drops)',
    alts=[alt('VXB', 'VXB07X87GYLQ', 'https://vxb.com/products/4-pack-50kg-half-bridge-load-cell-sensor-kit-with', '$39.99', 39.99)])
add('load_cell_s500', 'bench', 'sensor', 'Phidgets', '3140_0', 'S-type load cell 500 kg (C2), M12 x 1.75 both ends, 51 x 76 x 19 mm', 50.00, 1,
    'https://www.phidgets.com/?prodid=231', stock='Quantity Available: 358',
    specs={'capacity_kg': 500, 'max_overload_kg': 750, 'thread': 'M12 x 1.75', 'size_mm': [51, 76, 19], 'drawing': 'Phidgets 3140_0 mechanical drawing'},
    used_for='the press cage (B3 the stop sleeve to 2 kN, B4 the inserts and the link screws to 3.5 kN), read by an HX711',
    note='Calibration certificate included. 500 kg so B4 can go to an insert\'s pull-out (the 200 kg TAS501 is rated 1.96 kN).',
    alts=[alt('RobotShop', 'Phidgets S-Type Load Cell 500 kg (C3)', 'https://www.robotshop.com/products/phidgets-steel-s-type-load-cell-500kg-c3',
              '$71.54', 71.54, how='search snippet'),
          alt('SparkFun', 'SEN-14282 (TAS501, 200 kg)', 'https://www.sparkfun.com/products/14282', '$96.95', 96.95, stock='In stock',
              drop_in=False, changes='200 kg (1.96 kN), same 51 x 76 x 19 body and M12: B4 then stops at 1.9 kN (a proof load, not the pull-out)')])
add('pendant_specs', 'electronics', 'estop', 'AbleNet', 'Specs IC (10000114)', 'Momentary switch, 35 mm, 6 ft cord, 3.5 mm mono plug', 75.0, 1,
    'https://www.ablenetinc.com/specs-ic/', stock='In stock', used_for='hold-to-run: the trigger of the off-delay relay and the rig node\'s input',
    note='No current rating published: signal duty only (it switches the timer\'s trigger and the node\'s input, never the coil).',
    alts=[alt('AbleNet', 'Jelly Bean (10033400)', 'https://www.ablenetinc.com/jelly-bean', '$75.00', 75.0)])
add('wire_12awg', 'electronics', 'wiring', 'BNTECHGO', 'SW12G68008F10C2', '12 AWG silicone wire, 10 ft red + 10 ft black', 14.98, 1,
    'https://bntechgo.com/bntechgo-12-gauge-silicone-wire-kit-ultra-flexible-20-ft-black-and-red-each-color-10-ft-high-temp-200-c-600v-12-awg-silicone-wire-680-strands-of-tinned-copper-wire-stranded-wire-stranded-wire-for-model-battery/',
    used_for='the pack, fuse, contactor and motor runs',
    alts=[alt('BNTECHGO', 'SW12G68008F25C2 (25 + 25 ft)', 'https://bntechgo.com/', '$32.98', 32.98)])
add('xt30_male', 'electronics', 'wiring', 'RaceDayQuads', 'Amass XT30 (male)', 'XT30 connector, male', 0.99, 3, 'https://www.racedayquads.com/products/xt30-connector-male-or-female',
    used_for='the Y-splice to the two motors\' XT30 (female) leads, one spare')
add('xt60_pair', 'electronics', 'wiring', 'RaceDayQuads', 'Amass XT60H (male + female)', 'XT60H connector', 0.99, 4,
    'https://www.racedayquads.com/products/amass-xt60h-connector-1pc-choose-your-version', used_for='the pack lead (female) and the motors\' lead (male)',
    alts=[alt('Amazon', 'ASIN B0863HJZHB (XT60H pairs)', 'https://www.amazon.com/dp/B0863HJZHB', '$8.99', 1.80)])
add('can_cable', 'electronics', 'wiring', 'AutomationDirect', 'Quabbin Q0357-1', 'Shielded 22 AWG 1.5-pair data cable, 20 ft', 21.20, 1,
    'https://www.automationdirect.com/adc/shopping/catalog/bulk_wire_-a-_cable/data_-a-_communication_cable/q0357-1',
    used_for='the CAN chain (pair + ground) and the 12 V signal runs (pendant, timer, coil: under 0.5 A)')
add('resistor_120', 'electronics', 'wiring', 'TTI, Inc.', 'YAGEO CFR-25JB-52-120R', '120 ohm 1/4 W (1000)', 0.0156, 2,
    'https://www.tti.com/content/ttiinc/en/apps/part-detail.html?partsNumber=CFR-25JB-52-120R&mfgShortname=YAG', pack=1000, pack_price=15.60,
    used_for='CAN terminators where the adapter\'s or a motor\'s own is not used')
add('ferrule_kit', 'electronics', 'wiring', 'IWISS', 'HSC8 6-4-KIT', 'Ferrule crimper + 770 ferrules (23-10 AWG)', 19.99, 1,
    'https://www.iwiss.com/products/hsc8-6-4-kit-ferrule-crimping-tool-kit-awg-23-10-self-adjustable-ratchet-ferrule-crimper-plier-c-w-770end-sleeve-ferrules-connector-terminals',
    used_for='every screw terminal (fuse holder, contactor coil, timer, DC-DC)')
add('heatshrink_kit', 'electronics', 'wiring', 'RaceDayQuads', 'Heat Shrink Tube Set (530PC)', 'Heat-shrink assortment', 9.99, 1,
    'https://www.racedayquads.com/products/530-pcs-heat-shrink-tube-set', alts=[alt('SparkFun', 'PRT-09353', 'https://www.sparkfun.com/products/9353', '$10.95', 10.95)])
add('resistor_10r_25w', 'electronics', 'wiring', 'TTI, Inc.', 'TE HSA2510RJ', '10 ohm 25 W aluminium-housed resistor (box of 10)', 3.70, 1,
    'https://www.tti.com/content/ttiinc/en/apps/part-detail.html?partsNumber=HSA2510RJ&mfgShortname=TYC', pack=10, pack_price=37.00,
    used_for='optional: a 1 s pre-charge across the contactor at the first power-up if it sparks')
add('gh_header_2p', 'electronics', 'wiring', 'LCSC', 'JST BM02B-GHS-TBT(LF)(SN) (LCSC C161690)', 'JST GH 1.25 mm 2-pin header, top entry (SMT)', 0.0897, 4,
    'https://www.lcsc.com/product-detail/C161690.html', stock='70,630 in stock', ships='CN',
    used_for='the CAN junction: mates each RS-04\'s GH1.25-2P plug (two used, two spare)',
    note='The true GH mate (the cheap \'1.25 mm\' pigtails are micro-JST copies without the GH latch). Surface-mount: solder it on a scrap of '
         'perfboard with short 26 AWG tails, or splice the motors\' CAN leads into lever connectors instead (docs/leg-rig-wiring.md).',
    alts=[alt('HQonline', 'BM02B-GHS-TBT(LF)(SN)', 'https://www.hqonline.com/product-detail/wire-to-board-connectors-jst-bm02b-ghs-tbt-lf--sn--2500404027',
              '$0.097 (5+)', 0.097, how='search snippet')])
add('diode_1n4001', 'electronics', 'wiring', 'SparkFun', 'COM-08589', 'Rectifier diode 1N4001 (1 A, 50 V)', 0.25, 2,
    'https://www.sparkfun.com/diode-rectifier-1a-50v-1n4001.html', stock='In stock',
    used_for='across the contactor\'s coil (cathode to +): spares the relay\'s contact the coil\'s kick; one spare')
add('resistor_kit', 'electronics', 'wiring', 'SparkFun', 'COM-10969', 'Resistor kit 1/4 W, 500 (incl. 2.2k, 4.7k, 10k, 100k)', 9.00, 1,
    'https://www.sparkfun.com/resistor-kit-1-4w-500-total.html', used_for='the node\'s dividers: the pendant loop 10k/2.2k (12 V -> 2.2 V), '
    'the motors\' bus 100k/4.7k (60 V -> 2.7 V)')
add('featherwing_proto', 'electronics', 'wiring', 'Adafruit', '2884', 'FeatherWing Proto', 4.95, 2, 'https://www.adafruit.com/product/2884',
    stock='In Stock', used_for='one under the Feather (the dividers, the sensors\' plugs); one as the carriage\'s CAN junction (the GH headers)')
add('pod_insert_m4', 'rig', 'fastener', 'McMaster-Carr', '94459A160', 'Heat-set insert M4 (brass)', 0.2346, 3, f'{MCM}94459A160/', pack=50, pack_price=11.73,
    used_for='the pod: the contactor (2), the relay (1)', note='Same part as catalog/turret.json turret_insert_m4.')
add('screw_m2_5x8', 'electronics', 'fastener', 'McMaster-Carr', '91290A102', 'Socket head screw M2.5 x 8', 0.246, 4, f'{MCM}91290A102/', pack=50, pack_price=12.30,
    used_for='the Feather\'s FeatherWing into the pod\'s bosses (self-tapping into PETG)', note='Same part as catalog/turret.json turret_screw_m2_5x8.')
add('xt60e_m_panel', 'electronics', 'wiring', 'Maplin (UK)', 'Amass XT60E-M', 'XT60 male panel plug (the pack\'s inlet)', 1.50, 1,
    'https://pro.maplin.co.uk/products/male-xt60e-panel-mount-gold-plated-connector-20a-amass', ships='UK',
    used_for='the pod\'s inlet: the pack lead carries the female', note='Same part as catalog/turret.json amass-xt60e-m; LCSC C3040679 $0.61 in stock (catalog/alternates.json).',
    alts=[alt('LCSC', 'XT60E-M.G.Y (C3040679)', 'https://www.lcsc.com/product-detail/C3040679.html', '$0.613', 0.613, stock='In stock (3,091)')])
add('xt60e_f_panel', 'electronics', 'wiring', 'Jameco Electronics', 'Amass XT60E-F', 'XT60 female panel socket (the motors\' outlet)', 0.95, 1,
    'https://www.jameco.com/z/XT60E-F-Amass-XT60-Female-Bullet-Plug-Connector-2-Position-for-RC-Battery-Panel-Mount-60A_2338319.html',
    used_for='the pod\'s outlet: the motors\' lead carries the male', note='Same part as catalog/sourcing.json amass-xt60e-f.')
add('jack_3p5', 'electronics', 'wiring', 'Master Electronics', 'Switchcraft 35PM2A', '3.5 mm panel jack', 6.95, 1,
    'https://www.masterelectronics.com/en/switchcraft/35pm2a-12319088.html', used_for='the pendant\'s plug on the pod\'s panel',
    note='Same part as catalog/sourcing.json jack-3.5mm-panel (a 6.35 mm hole).')
add('fuse_holder_5x20', 'electronics', 'power_distribution', 'Digi-Key', 'Littelfuse 03455LS1H', '5 x 20 mm panel fuse holder', 7.16, 1,
    'https://www.digikey.com/en/products/detail/littelfuse-inc/03455LS1H/553826', used_for='the 12 V converter\'s input fuse, on the panel',
    note='Same part as catalog/sourcing.json fuse-holder-5x20-panel.')
add('fuse_5a_dc', 'electronics', 'power_distribution', 'Digi-Key', 'Littelfuse 0477005.MXP', '5 x 20 mm fuse 5 A, DC-rated', 1.00, 2,
    'https://www.digikey.com/en/products/detail/littelfuse-inc/0477005-MXP/1979192', used_for='the 12 V converter\'s input (one spare)',
    note='Same part as catalog/turret.json littelfuse-0477005-mxp.')
# ------------------------------------------------------------------ the bench (B1-B6): what the leg and rig lists do not have
print(len(items), 'items')
OUT.write_text(json.dumps(items, indent=1) + '\n')
