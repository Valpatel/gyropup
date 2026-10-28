"""Generate the fuse board's KiCad 10 project from design.py: the schematic (fuse-board.kicad_sch), the PCB
(fuse-board.kicad_pcb, zones filled), the project file with JLCPCB's 2 oz rules, the custom footprints
(fuse-board.pretty) and the library tables. Run with KiCad's own Python (it imports pcbnew):

    nice -n 15 ~/.local/share/kicad-10.0.1/bin/python3.11 hardware/fuse-board/generate.py

build.sh runs this, then kicad-cli for ERC, DRC (with schematic parity), the gerbers, the drill file, the BOM/CPL
and the pictures. Every UUID is derived from a name, so the output is the same on every run.
"""
from __future__ import annotations

import json
import math
import os
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import design as D  # noqa: E402
import sexp as S  # noqa: E402

KICAD = Path(os.environ.get('KICAD_SHARE', Path.home() / '.local/share/kicad-10.0.1/share/kicad'))
SYMLIB = KICAD / 'symbols'
FPLIB = KICAD / 'footprints'
PRJ = D.NAME
NS = uuid.UUID('6a1f0d1e-6b9e-4c55-9d0a-2f5b3c4e1b05')


def uid(*parts) -> str:
    return str(uuid.uuid5(NS, '/'.join(str(p) for p in parts)))


def top_blocks(text):
    """(start, end) of every list one level inside the file's outer list, skipping quoted strings."""
    out, depth, i, start, n = [], 0, 0, None, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 2 if text[i] == '\\' else 1
        elif c == '(':
            depth += 1
            if depth == 2:
                start = i
        elif c == ')':
            if depth == 2:
                out.append((start, i + 1))
            depth -= 1
        i += 1
    return out


def stable_board(path: Path):
    """KiCad orders a board's items by their (random) UUIDs when it saves. Give every top-level item UUIDs derived from
    its own content (uuids blanked), then let KiCad load and save it again so the order follows them: a rebuild with
    nothing changed leaves the file as it was."""
    import re
    text = path.read_text()
    pat = re.compile(r'\(uuid "[0-9a-fA-F-]{36}"\)')
    seen, parts, last = {}, [], 0
    for a, z in top_blocks(text):
        block = text[a:z]
        key = pat.sub('(uuid "")', block)
        k = seen[key] = seen.get(key, -1) + 1
        n = [0]

        def sub(m, key=key, k=k):
            n[0] += 1
            return f'(uuid "{uid(key, k, n[0])}")'
        parts.append(text[last:a])
        parts.append(pat.sub(sub, block))
        last = z
    parts.append(text[last:])
    path.write_text(''.join(parts))
    b = P.LoadBoard(str(path))
    P.SaveBoard(str(path), b)


def stable_uuids(path: Path):
    """KiCad gives every saved item a random UUID: renumber them in file order from the file's name, so a rebuild with
    nothing changed leaves the files as they were. Only (uuid "...") tokens change; footprint paths keep the schematic's."""
    import re
    n = [0]

    def sub(m):
        n[0] += 1
        return f'(uuid "{uid(path.name, n[0])}")'
    path.write_text(re.sub(r'\(uuid "[0-9a-fA-F-]{36}"\)', sub, path.read_text()))


ROOT_UUID = uid('root')

# ======================================================================================== the parts list
# ref -> dict(sym, fp, value, pins {pin: net}, fields)
FL1 = 'fuse-board:Littelfuse_MINI_FL1_178.6764.0001'
PARTS = {}


def part(ref, sym, fp, value, pins, **fields):
    PARTS[ref] = dict(sym=sym, fp=fp, value=value, pins=pins, fields=fields)


for ref, label, wire, amps, net_in, col, row in D.HOLDERS:
    part(ref, 'Device:Fuse', FL1, f'{label} {amps:g} A' if amps else 'SPARE (no fuse)', {'1': net_in, '2': D.out_net(ref)},
         MPN='Littelfuse 178.6764.0001 (MINI FL1, 58 V DC, 22 A cont.)', LCSC='C142933',
         Fuse=(f'Littelfuse {"099707.5" if amps == 7.5 else f"0997{int(amps):03d}"}.WXN MINI 58V {amps:g} A') if amps else 'none (spare)', Wire=wire or '-')
for ref, label, net, x, y, size, wires in D.STUDS:
    part(ref, 'Connector_Generic:Conn_01x01', f'fuse-board:Stud_{size}_Lug', label, {'1': net},
         MPN=f'{size} stud: socket head up from below, nyloc, lug(s), nyloc', Wires='; '.join(wires))
part('R1', 'Device:R_Shunt', 'fuse-board:Bourns_CSS2H-3920_Kelvin', '1mR 1% 8W', {'1': '+BAT_IN', '2': 'SNS_P', '3': 'SNS_N', '4': '+BUS'},
     MPN='Bourns CSS2H-3920R-1L00F', LCSC='C4087295')
part('U1', 'Sensor_Energy:INA228', 'Package_SO:TSSOP-10_3x3mm_P0.5mm', 'INA228',
     {'1': 'BUS-', '2': 'BUS-', '4': 'SDA', '5': 'SCL', '6': '3V3', '7': 'BUS-', '8': 'VBUS', '9': 'INN', '10': 'INP'},
     MPN='TI INA228AIDGSR', LCSC='C2887910', Note='address 0x40; fit U1 or wire an Adafruit 5832 to TP1-TP3, not both')
for ref, value, fp, x, y, rot, n1, n2, lcsc, note in D.SMALL:
    part(ref, 'Device:C' if ref.startswith('C') else 'Device:R', fp, value, {'1': n1, '2': n2}, LCSC=lcsc, Note=note)
part('J17', 'Connector_Generic_MountingPin:Conn_01x04_MountingPin', 'Connector_JST:JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal',
     'I2C GH', dict(D.GH_PINS), MPN='JST SM04B-GHS-TB', LCSC='C189895', Pinout='1 GND (BUS-), 2 3V3, 3 SDA, 4 SCL')
for ref, net, x, y, note in D.TPS:
    part(ref, 'Connector:TestPoint', 'TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm', net, {'1': net}, Note=note)
for ref, label, net, x, y in D.MOUNTS:
    part(ref, 'Mechanical:MountingHole_Pad', 'fuse-board:Mount_M5_PlateBond', label, {'1': net},
         Note='M5 x 12 button head into the power plate\'s flush nut through an 8 mm printed standoff: bonds the plate to BUS-')
for ref, x, y in D.TIES:
    part(ref, 'Mechanical:MountingHole', 'fuse-board:TieSlot_4x10', 'tie slot', {}, Note='cable tie through the plate\'s slot')
# ERC: the power-in pins (U1 VS, GND) and the mounting-hole pin are fed from off the board
for i, net in enumerate(('3V3', 'BUS-', '+BAT_IN', '+12V')):
    part(f'#FLG{i + 1:02d}', 'power:PWR_FLAG', '', 'PWR_FLAG', {'1': net})

DNP = {'U1'}                                 # the bare INA228 (LCSC had 0 in stock, 2026-10-27): hand-fit, or the Adafruit 5832 on TP1-TP3
NO_CONNECT = [('U1', '3')]                   # ALERT: the firmware polls
NO_BOM = {r for r in PARTS if r.startswith(('#', 'H', 'TP'))}

# ======================================================================================== the schematic

def lib_symbol(lib_id: str):
    lib, name = lib_id.split(':')
    path = SYMLIB / f'{lib}.kicad_symdir' / f'{name}.kicad_sym'
    tree = S.parse(path.read_text())
    sym = S.first(tree, 'symbol')
    ext = S.first(sym, 'extends')
    if ext:                                   # a derived symbol: the parent's body and pins, the child's properties
        parent = S.first(S.parse((path.parent / f'{ext[1]}.kicad_sym').read_text()), 'symbol')
        props = S.find(sym, 'property')
        body = []
        for x in parent:
            if isinstance(x, list) and x and x[0] == 'property':
                continue
            if isinstance(x, list) and x and x[0] == 'symbol':
                x = [x[0], x[1].replace(ext[1], name, 1)] + x[2:]
            body.append(x)
        sym = [body[0], name] + props + [x for x in body[2:] if isinstance(x, list) and x[0] != 'extends']
    out = [S.Sym('symbol'), lib_id] + [x for x in sym[2:]]
    return out


def pins_of(sym):
    """{number: (x, y, angle)} in the symbol's own frame (y up)."""
    out = {}

    def walk(n):
        for x in n:
            if isinstance(x, list) and x:
                if x[0] == 'pin':
                    at = S.first(x, 'at')
                    num = S.first(x, 'number')
                    out[num[1]] = (float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0)
                else:
                    walk(x)
    walk(sym)
    return out


def eff(hide=False, justify=None):
    e = [S.Sym('effects'), [S.Sym('font'), [S.Sym('size'), 1.27, 1.27]]]
    if justify:
        e.append([S.Sym('justify')] + [S.Sym(j) for j in justify.split()])
    if hide:
        e.append([S.Sym('hide'), S.Sym('yes')])
    return e


def prop(name, value, x, y, hide=False, ang=0, justify=None):
    return [S.Sym('property'), name, value, [S.Sym('at'), x, y, ang], eff(hide, justify)]


def g(v):                                     # the 1.27 mm schematic grid
    return round(v / 1.27) * 1.27


SCH_POS = {}                                  # ref -> (x, y) on the sheet (mm)


def sch_layout():
    """Two rows of six holders, each with its output stud below it; the inputs at the right; the shunt and the
    INA228 below."""
    studs = {s_[2]: s_[0] for s_ in D.STUDS}
    for i, h in enumerate(D.HOLDERS):
        X, Y = g(45.72 + 60.96 * (i % 6)), g(55.88 + 50.8 * (i // 6))
        SCH_POS[h[0]] = (X, Y)
        SCH_POS[studs[D.out_net(h[0])]] = (X + g(10.16), Y + g(15.24))
    SCH_POS['J1'] = (g(30.48), g(180.34))
    SCH_POS['R1'] = (g(66.04), g(180.34))
    SCH_POS['J14'] = (g(30.48), g(162.56))
    SCH_POS['J15'] = (g(330.2), g(165.1))
    SCH_POS['J16'] = (g(330.2), g(180.34))
    SCH_POS['MH1'] = (g(363.22), g(180.34))
    for i, (ref, *_r) in enumerate(D.TIES):
        SCH_POS[ref] = (g(350.52 + 15.24 * i), g(205.74))
    SCH_POS['U1'] = (g(182.88), g(182.88))
    pos = {'R2': (106.68, 175.26), 'R3': (127.0, 175.26), 'C1': (147.32, 175.26), 'R4': (106.68, 205.74), 'C2': (147.32, 205.74)}
    for ref, (x, y) in pos.items():
        SCH_POS[ref] = (g(x), g(y))
    SCH_POS['J17'] = (g(243.84), g(180.34))
    for i, (ref, *_r) in enumerate(D.TPS):
        SCH_POS[ref] = (g(279.4 + 12.7 * i), g(175.26))
    for i, r in enumerate(sorted(r for r in PARTS if r.startswith('#FLG'))):
        SCH_POS[r] = (g(279.4 + 15.24 * i), g(203.2))


def write_schematic():
    sch_layout()
    libs, placed, labels = {}, [], []
    for ref, p in PARTS.items():
        if p['sym'] not in libs:
            libs[p['sym']] = lib_symbol(p['sym'])
    for ref, p in sorted(PARTS.items()):
        X, Y = SCH_POS[ref]
        sym = libs[p['sym']]
        pins = pins_of(sym)
        u = uid('sym', ref)
        node = [S.Sym('symbol'), [S.Sym('lib_id'), p['sym']], [S.Sym('at'), X, Y, 0], [S.Sym('unit'), 1],
                [S.Sym('exclude_from_sim'), S.Sym('no')], [S.Sym('in_bom'), S.Sym('no' if ref in NO_BOM else 'yes')],
                [S.Sym('on_board'), S.Sym('no' if ref.startswith('#') else 'yes')],
                [S.Sym('dnp'), S.Sym('yes' if ref in DNP else 'no')], [S.Sym('uuid'), u],
                prop('Reference', ref, X + 3.81, Y - 1.27, hide=ref.startswith('#'), justify='left'),
                prop('Value', p['value'], X + 3.81, Y + 1.27, justify='left'),
                prop('Footprint', p['fp'], X, Y, hide=True), prop('Datasheet', '', X, Y, hide=True),
                prop('Description', '', X, Y, hide=True)]
        for k, v in p['fields'].items():
            node.append(prop(k, v, X, Y, hide=True))
        for num in pins:
            node.append([S.Sym('pin'), num, [S.Sym('uuid'), uid('pin', ref, num)]])
        node.append([S.Sym('instances'), [S.Sym('project'), PRJ, [S.Sym('path'), f'/{ROOT_UUID}', [S.Sym('reference'), ref], [S.Sym('unit'), 1]]]])
        placed.append(node)
        for num, net in p['pins'].items():
            if num not in pins:
                raise SystemExit(f'{ref}: no pin {num} in {p["sym"]}')
            px, py, ang = pins[num]
            ax, ay = X + px, Y - py
            la = (ang + 180) % 360
            just = 'left bottom' if la in (0, 90) else 'right bottom'
            labels.append([S.Sym('global_label'), net, [S.Sym('shape'), S.Sym('passive')], [S.Sym('at'), round(ax, 4), round(ay, 4), la],
                           [S.Sym('fields_autoplaced'), S.Sym('yes')], eff(justify=just.split()[0]), [S.Sym('uuid'), uid('label', ref, num)],
                           [S.Sym('property'), 'Intersheetrefs', '${INTERSHEET_REFS}', [S.Sym('at'), round(ax, 4), round(ay, 4), 0], eff(hide=True)]])
    for ref, num in NO_CONNECT:
        X, Y = SCH_POS[ref]
        px, py, ang = pins_of(libs[PARTS[ref]['sym']])[num]
        labels.append([S.Sym('no_connect'), [S.Sym('at'), round(X + px, 4), round(Y - py, 4)], [S.Sym('uuid'), uid('nc', ref, num)]])
    notes = [
        'Gyropup fuse board rev A (D60, task B5): docs/body-fuse-board.md. Generated by hardware/fuse-board/generate.py from design.py.',
        'Fuses: Littelfuse MINI 58V (0997 series, 1 kA at 58 V DC) ONLY, in Littelfuse MINI FL1 holders (58 V DC, 22 A continuous). '
        'A 32 V MINI fuse fits the same holder: the silk says 58 V FUSES ONLY at every holder. Pull a fuse only with both packs out (D55).',
        'High-side shunt R1 (1 mOhm) between J1 (from the MRBF load stud) and +BUS: the INA228\'s inputs stay inside -0.3..85 V of its ground '
        '(BUS-, the switched negative) whether the main switch is on or off. Positive current = into the packs (regeneration); discharge reads negative.',
        'Kelvin taps (R1 pads 2, 3) at Bourns\' measurement points; 10 Ohm in each input (TI SLYS021A 8.1.4); VBUS through 4.7 kOhm from the battery side.',
        'Fit U1 (bare INA228; the I2C pull-ups are on the MCU carrier), or leave it off and wire an Adafruit 5832 (its 15 mOhm shunt removed, '
        'VBUS jumper open): VIN+ to TP2, VIN- to TP1, VBUS to TP3, its STEMMA QT lead to the MCU. Not both (both answer at 0x40).',
        'J17 (JST GH 4-pin) pinout: 1 GND (BUS-), 2 3V3, 3 SDA, 4 SCL (the body makes this lead).',
    ]
    texts = [[S.Sym('text'), t, [S.Sym('exclude_from_sim'), S.Sym('no')], [S.Sym('at'), 25.4, g(228.6 + 6.35 * i), 0],
              eff(justify='left bottom'), [S.Sym('uuid'), uid('note', i)]] for i, t in enumerate(notes)]
    doc = [S.Sym('kicad_sch'), [S.Sym('version'), 20250114], [S.Sym('generator'), 'eeschema'], [S.Sym('generator_version'), '9.0'],
           [S.Sym('uuid'), ROOT_UUID], [S.Sym('paper'), 'A3'],
           [S.Sym('title_block'), [S.Sym('title'), 'Gyropup fuse board'], [S.Sym('date'), '2026-10-27'], [S.Sym('rev'), D.REV],
            [S.Sym('company'), 'Gyropup body, task B5 (D60)'], [S.Sym('comment'), 1, 'generated by hardware/fuse-board/generate.py']],
           [S.Sym('lib_symbols')] + list(libs.values())] + placed + labels + texts + [
           [S.Sym('sheet_instances'), [S.Sym('path'), '/', [S.Sym('page'), '1']]], [S.Sym('embedded_fonts'), S.Sym('no')]]
    (HERE / f'{PRJ}.kicad_sch').write_text(S.dump(doc) + '\n')
    return {ref: uid('sym', ref) for ref in PARTS}


# ======================================================================================== the PCB
import pcbnew as P  # noqa: E402

MM = P.FromMM
X0, Y0 = 100.0, 100.0 + D.SIZE[1]             # KiCad position of the board's (0, 0) corner (KiCad y points down)


def kc(bx, by):
    return P.VECTOR2I(MM(X0 + bx), MM(Y0 - by))


def board_xy(v):
    return (P.ToMM(v.x) - X0, Y0 - P.ToMM(v.y))


def new_fp(name, desc):
    fp = P.FOOTPRINT(None)
    fp.SetFPID(P.LIB_ID('fuse-board', name))
    fp.SetLibDescription(desc)
    return fp


def add_pad(fp, num, at, size, drill=None, shape=P.PAD_SHAPE_CIRCLE, attr=None, layers=None, drill_oval=None):
    pad = P.PAD(fp)
    pad.SetNumber(num)
    pad.SetShape(shape)
    pad.SetSize(P.VECTOR2I(MM(size[0]), MM(size[1])))
    if attr is None:
        attr = P.PAD_ATTRIB_PTH if drill else P.PAD_ATTRIB_SMD
    pad.SetAttribute(attr)
    if drill_oval:
        pad.SetDrillShape(P.PAD_DRILL_SHAPE_OBLONG)
        pad.SetDrillSize(P.VECTOR2I(MM(drill_oval[0]), MM(drill_oval[1])))
    elif drill:
        pad.SetDrillSize(P.VECTOR2I(MM(drill), MM(drill)))
    if layers is None:
        layers = {P.PAD_ATTRIB_PTH: pad.PTHMask(), P.PAD_ATTRIB_NPTH: pad.UnplatedHoleMask(), P.PAD_ATTRIB_SMD: pad.SMDMask()}[attr]
    pad.SetLayerSet(layers)
    pad.SetFPRelativePosition(P.VECTOR2I(MM(at[0]), MM(at[1])))
    fp.Add(pad)
    return pad


def fp_line(fp, a, b, layer, w=0.12):
    s = P.PCB_SHAPE(fp, P.SHAPE_T_SEGMENT)
    s.SetStart(P.VECTOR2I(MM(a[0]), MM(a[1])))
    s.SetEnd(P.VECTOR2I(MM(b[0]), MM(b[1])))
    s.SetLayer(layer)
    s.SetWidth(MM(w))
    fp.Add(s)


def fp_rect(fp, x0, y0, x1, y1, layer, w=0.12):
    for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        fp_line(fp, a, b, layer, w)


def fp_circle(fp, r, layer, w=0.12, c=(0, 0)):
    s = P.PCB_SHAPE(fp, P.SHAPE_T_CIRCLE)
    s.SetCenter(P.VECTOR2I(MM(c[0]), MM(c[1])))
    s.SetEnd(P.VECTOR2I(MM(c[0] + r), MM(c[1])))
    s.SetLayer(layer)
    s.SetWidth(MM(w))
    fp.Add(s)


def fp_ref_value(fp):
    fp.Reference().SetLayer(P.F_Fab)
    fp.Value().SetLayer(P.F_Fab)
    fp.Value().SetVisible(False)


def custom_footprints():
    """{name: FOOTPRINT}: the holder, the Kelvin shunt, the studs, the plate-bond hole and the tie slot."""
    out = {}
    # Littelfuse MINI FL1 178.6764.0001 (datasheet rev 111616): terminals 8 +-0.15 apart in 1.5 +-0.1 holes; the
    # snap-in peg in a 2.7 hole 0.8 off the terminals' line (its side is not dimensioned: an oval NPTH slot takes
    # either); body 14.2 x 6.
    fp = new_fp('Littelfuse_MINI_FL1_178.6764.0001', 'Littelfuse MINI FL1 PCB holder for MINI blade fuses, 58 V DC, 22 A continuous')
    fp.SetAttributes(P.FP_THROUGH_HOLE)
    add_pad(fp, '1', (-4.0, 0.0), (3.2, 3.2), drill=1.5)
    add_pad(fp, '2', (4.0, 0.0), (3.2, 3.2), drill=1.5)
    add_pad(fp, '', (0.0, 0.0), (2.7, 4.3), shape=P.PAD_SHAPE_OVAL, attr=P.PAD_ATTRIB_NPTH, drill_oval=(2.7, 4.3))
    fp_rect(fp, -7.1, -3.0, 7.1, 3.0, P.F_Fab, 0.1)
    fp_rect(fp, -7.35, -3.25, 7.35, 3.25, P.F_CrtYd, 0.05)
    fp_rect(fp, -7.22, -3.12, 7.22, 3.12, P.F_SilkS, 0.15)
    fp_ref_value(fp)
    out['Littelfuse_MINI_FL1_178.6764.0001'] = fp
    # Bourns CSS2H-3920: pads 3.40 x 6.20 at +-3.80 (the recommended layout); Kelvin taps (net-tie pads 2, 3) at the
    # recommended measurement points 8.40 apart, at the pads' north edges, so the sense lines leave sideways of the
    # current.
    fp = new_fp('Bourns_CSS2H-3920_Kelvin', 'Bourns CSS2H-3920 1 mOhm shunt, 4-terminal (Kelvin) layout, net-tied sense pads')
    add_pad(fp, '1', (-3.8, 0.0), (3.4, 6.2), shape=P.PAD_SHAPE_RECT)
    add_pad(fp, '4', (3.8, 0.0), (3.4, 6.2), shape=P.PAD_SHAPE_RECT)
    add_pad(fp, '2', (-4.2, -3.65), (0.5, 0.5), shape=P.PAD_SHAPE_RECT)
    add_pad(fp, '3', (4.2, -3.65), (0.5, 0.5), shape=P.PAD_SHAPE_RECT)
    fp_line(fp, (-4.2, -3.65), (-4.2, -2.9), P.F_Cu, 0.3)          # the Kelvin joints: copper of the net tie
    fp_line(fp, (4.2, -3.65), (4.2, -2.9), P.F_Cu, 0.3)
    fp.SetAttributes(P.FP_SMD)
    fp.AddNetTiePadGroup('1, 2')
    fp.AddNetTiePadGroup('3, 4')
    fp_rect(fp, -5.0, -2.6, 5.0, 2.6, P.F_Fab, 0.1)
    fp_rect(fp, -5.75, -4.15, 5.75, 3.35, P.F_CrtYd, 0.05)
    fp_line(fp, (-1.6, -3.35), (1.6, -3.35), P.F_SilkS, 0.15)
    fp_line(fp, (-1.6, 3.35), (1.6, 3.35), P.F_SilkS, 0.15)
    fp_ref_value(fp)
    out['Bourns_CSS2H-3920_Kelvin'] = fp
    # studs: a plated hole in a pad on both layers ringed with vias
    for size in ('M4', 'M6'):
        d, dr = D.STUD_PAD[size], D.STUD_DRILL[size]
        fp = new_fp(f'Stud_{size}_Lug', f'{size} lug stud: plated {dr} mm hole, {d} mm pad both sides, 8 stitching vias')
        add_pad(fp, '1', (0, 0), (d, d), drill=dr)
        rv = (dr / 2 + d / 2) / 2 + 0.15
        for k in range(8):
            a = 2 * math.pi * (k + 0.5) / 8
            add_pad(fp, '1', (rv * math.cos(a), rv * math.sin(a)), (0.95, 0.95), drill=0.4)
        fp_circle(fp, d / 2 + 0.25, P.F_CrtYd, 0.05)
        fp_circle(fp, d / 2 + 0.15, P.F_Fab, 0.1)
        fp_ref_value(fp)
        out[f'Stud_{size}_Lug'] = fp
    fp = new_fp('Mount_M5_PlateBond', 'M5 mounting hole, plated, 10 mm pad both sides with vias: the plate bond')
    add_pad(fp, '1', (0, 0), (10.0, 10.0), drill=5.3)
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        add_pad(fp, '1', (4.0 * math.cos(a), 4.0 * math.sin(a)), (0.95, 0.95), drill=0.4)
    fp_circle(fp, 5.5, P.F_CrtYd, 0.05)
    fp_circle(fp, 6.0, P.B_Fab, 0.1)                    # the printed standoff under the board (12 mm)
    fp_ref_value(fp)
    out['Mount_M5_PlateBond'] = fp
    fp = new_fp('TieSlot_4x10', 'non-plated slot 4 x 10 for a cable tie through the power plate\'s slot')
    add_pad(fp, '', (0, 0), (4.0, 10.0), shape=P.PAD_SHAPE_OVAL, attr=P.PAD_ATTRIB_NPTH, drill_oval=(4.0, 10.0))
    fp_rect(fp, -2.5, -5.5, 2.5, 5.5, P.F_CrtYd, 0.05)
    fp_ref_value(fp)
    out['TieSlot_4x10'] = fp
    lib = HERE / f'{PRJ}.pretty'
    lib.mkdir(exist_ok=True)
    io = P.PCB_IO_MGR.FindPlugin(P.PCB_IO_MGR.KICAD_SEXP)
    for name, fp in out.items():
        io.FootprintSave(str(lib), fp)
        stable_uuids(lib / f'{name}.kicad_mod')
    return out


def load_fp(lib_id):
    lib, name = lib_id.split(':')
    path = HERE / f'{PRJ}.pretty' if lib == 'fuse-board' else FPLIB / f'{lib}.pretty'
    fp = P.PCB_IO_MGR.FindPlugin(P.PCB_IO_MGR.KICAD_SEXP).FootprintLoad(str(path), name)
    if fp is None:
        raise SystemExit(f'footprint {lib_id} not found')
    fp.SetFPID(P.LIB_ID(lib, name))
    return fp


def placement():
    """ref -> (bx, by, rotation deg)."""
    pos = {}
    for ref, label, wire, amps, net_in, col, row in D.HOLDERS:
        x, y = D.holder_xy(col, row)
        pos[ref] = (x, y, 90.0 if row == 'N' else 270.0)
    for ref, label, net, x, y, size, wires in D.STUDS:
        pos[ref] = (x, y, 0.0)
    pos['R1'] = (D.SHUNT[1], D.SHUNT[2], 0.0)
    pos['U1'] = (D.U1[1], D.U1[2], D.U1[3])
    for ref, value, fp, x, y, rot, *_ in D.SMALL:
        pos[ref] = (x, y, rot)
    pos['J17'] = (D.GH[1], D.GH[2], D.GH[3])
    for ref, net, x, y, note in D.TPS:
        pos[ref] = (x, y, 0.0)
    for ref, label, net, x, y in D.MOUNTS:
        pos[ref] = (x, y, 0.0)
    for ref, x, y in D.TIES:
        pos[ref] = (x, y, 0.0)
    return pos


def build_board(sym_uuids):
    custom_footprints()
    b = P.BOARD()
    ds = b.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.SetBoardThickness(MM(D.THICKNESS))
    ds.SetAuxOrigin(kc(0.0, 0.0))             # drill and placement origin: the board's rear-right corner (design.py's frame)
    nets = {}
    for name in D.NETS:
        n = P.NETINFO_ITEM(b, name)
        b.Add(n)
        nets[name] = n
    pos = placement()
    fps = {}
    for ref, p in PARTS.items():
        if ref.startswith('#'):
            continue
        fp = load_fp(p['fp'])
        fp.SetReference(ref)
        fp.SetValue(p['value'])
        fp.SetPath(P.KIID_PATH(f'/{sym_uuids[ref]}'))
        fp.SetSheetname('Root')
        fp.SetSheetfile(f'{PRJ}.kicad_sch')
        for k, v in p['fields'].items():
            fp.SetField(k, v)
            fld = fp.GetField(k)
            if fld:
                fld.SetVisible(False)
                fld.SetLayer(P.F_Fab)
        if ref in DNP:
            fp.SetDNP(True)
        if ref in NO_BOM:
            fp.SetExcludedFromBOM(True)
        x, y, rot = pos[ref]
        b.Add(fp)
        fp.SetPosition(kc(x, y))
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            num = pad.GetNumber()
            if num in p['pins']:
                pad.SetNet(nets[p['pins'][num]])
            elif (ref, num) in NO_CONNECT:
                nc = P.NETINFO_ITEM(b, 'unconnected-(U1-~{Alert}-Pad3)')
                b.Add(nc)
                pad.SetNet(nc)
        fp.Reference().SetLayer(P.F_Fab)
        fps[ref] = fp
    return b, nets, fps


def pad_xy(fps, ref, num):
    for pad in fps[ref].Pads():
        if pad.GetNumber() == num:
            return board_xy(pad.GetPosition())
    raise KeyError(f'{ref}.{num}')


def track(b, net, pts, w, layer=P.F_Cu):
    for a, c in zip(pts, pts[1:]):
        t = P.PCB_TRACK(b)
        t.SetStart(kc(*a))
        t.SetEnd(kc(*c))
        t.SetWidth(MM(w))
        t.SetLayer(layer)
        t.SetNet(net)
        b.Add(t)


def via(b, net, at, drill=0.4, dia=0.8):
    v = P.PCB_VIA(b)
    v.SetPosition(kc(*at))
    v.SetDrill(MM(drill))
    v.SetWidth(MM(dia))
    v.SetNet(net)
    b.Add(v)


def zone(b, net, poly, layer, priority=0, clearance=None):
    z = P.ZONE(b)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetPadConnection(P.ZONE_CONNECTION_FULL)
    z.SetMinThickness(MM(0.25))
    z.SetAssignedPriority(priority)
    if clearance:
        z.SetLocalClearance(MM(clearance))
    ol = z.Outline()
    ol.NewOutline()
    for x, y in poly:
        ol.Append(MM(X0 + x), MM(Y0 - y))
    b.Add(z)
    return z


def text(b, s, at, h=1.0, layer=P.F_SilkS, rot=0.0, bold=False, just='c'):
    t = P.PCB_TEXT(b)
    t.SetText(s)
    t.SetPosition(kc(*at))
    t.SetLayer(layer)
    t.SetTextSize(P.VECTOR2I(MM(h), MM(h)))
    t.SetTextThickness(MM(0.2 if bold else 0.15))
    t.SetTextAngleDegrees(rot)
    t.SetHorizJustify({'c': P.GR_TEXT_H_ALIGN_CENTER, 'l': P.GR_TEXT_H_ALIGN_LEFT, 'r': P.GR_TEXT_H_ALIGN_RIGHT}[just])
    if layer == P.B_SilkS:
        t.SetMirrored(True)
    b.Add(t)


def outline(b):
    W, H = D.SIZE
    r = D.CORNER_R
    segs = [((r, 0), (W - r, 0)), ((W, r), (W, H - r)), ((W - r, H), (r, H)), ((0, H - r), (0, r))]
    for a, c in segs:
        s = P.PCB_SHAPE(b, P.SHAPE_T_SEGMENT)
        s.SetStart(kc(*a))
        s.SetEnd(kc(*c))
        s.SetLayer(P.Edge_Cuts)
        s.SetWidth(MM(0.1))
        b.Add(s)
    k = r * (1 - math.sqrt(0.5))
    for st, mid, en in (((0, r), (k, k), (r, 0)), ((W - r, 0), (W - k, k), (W, r)),
                        ((W, H - r), (W - k, H - k), (W - r, H)), ((r, H), (k, H - k), (0, H - r))):
        s = P.PCB_SHAPE(b, P.SHAPE_T_ARC)
        s.SetArcGeometry(kc(*st), kc(*mid), kc(*en))
        s.SetLayer(P.Edge_Cuts)
        s.SetWidth(MM(0.1))
        b.Add(s)


def route(b, nets, fps):
    """The copper: pours, the branch outputs, the sense lines and the logic. Coordinates are board-local mm; the
    small-signal routes were laid out by hand round the INA228's 0.5 mm pins (docs/body-fuse-board.md 3)."""
    for net, poly in D.POURS:
        for layer in (P.F_Cu, P.B_Cu):
            zone(b, nets[net], poly, layer)
    for net, pts in D.STITCH.items():
        for at in pts:
            via(b, nets[net], at, 0.4, 0.95)
    # BUS-: the east strip with the star and frame studs (both layers), a bottom strip along the north edge to the
    # west, and the west block round the plate bond (MH1) and the GH connector
    zone(b, nets['BUS-'], [(80.2, 39.0), (87.4, 39.0), (87.4, 61.6), (80.2, 61.6)], P.F_Cu)
    zone(b, nets['BUS-'], [(80.2, 39.0), (87.4, 39.0), (87.4, 75.4), (0.6, 75.4), (0.6, 72.9), (80.2, 72.9)], P.B_Cu)
    zone(b, nets['BUS-'], [(10.6, 55.4), (20.2, 55.4), (20.2, 66.6), (10.6, 66.6)], P.F_Cu)
    zone(b, nets['BUS-'], [(10.6, 49.0), (20.2, 49.0), (20.2, 75.4), (1.0, 75.4), (1.0, 55.8), (10.6, 55.8)], P.B_Cu, priority=1)
    # branch outputs: holder pin 2 to its stud, both layers, OUT_W wide
    studs = {s_[2]: s_ for s_ in D.STUDS}
    for ref, label, wire, amps, net_in, col, row in D.HOLDERS:
        net = D.out_net(ref)
        p2 = pad_xy(fps, ref, '2')
        s_ = studs[net]
        x, y = D.holder_xy(col, row)
        ux, uy = p2[0] - x, p2[1] - y
        L = math.hypot(ux, uy)
        ux, uy = ux / L, uy / L
        neck_w, neck_l = D.OUT_NECK
        q = (p2[0] + ux * neck_l, p2[1] + uy * neck_l)
        for layer in (P.F_Cu, P.B_Cu):
            if ref == 'F12':                  # east from pin 2 (the tie slot H2 is south of it); a 5 A branch
                track(b, nets[net], [p2, (s_[3], s_[4])], neck_w, layer)
                continue
            track(b, nets[net], [p2, q], neck_w, layer)
            track(b, nets[net], [q, (s_[3], s_[4])], D.OUT_W, layer)
    W = D.SIGNAL_W
    n = nets
    tp, tn = pad_xy(fps, 'R1', '2'), pad_xy(fps, 'R1', '3')
    u = {k: pad_xy(fps, 'U1', k) for k in [str(i) for i in range(1, 11)]}
    r2 = {k: pad_xy(fps, 'R2', k) for k in '12'}
    r3 = {k: pad_xy(fps, 'R3', k) for k in '12'}
    c1 = {k: pad_xy(fps, 'C1', k) for k in '12'}
    c2 = {k: pad_xy(fps, 'C2', k) for k in '12'}
    r4 = {k: pad_xy(fps, 'R4', k) for k in '12'}
    gh = {k: pad_xy(fps, 'J17', k) for k in '1234'}
    tps = {ref: pad_xy(fps, ref, '1') for ref, *_ in D.TPS}
    ROUTE_LOG.update(dict(tp=tp, tn=tn, u=u, r2=r2, r3=r3, c1=c1, c2=c2, r4=r4, gh=gh, tps=tps))
    yb = u['9'][1] - 0.725                    # the analog row's pad ends (south)
    yt = u['4'][1] + 0.725                    # the logic row's pad ends (north)
    # Kelvin taps to the 10 Ohm resistors
    track(b, n['SNS_P'], [tp, r2['1']], W)
    track(b, n['SNS_N'], [tn, r3['1']], W)
    # IN- (battery side) and IN+ (bus side): horizontals at y 39.6, up to the pins; the filter cap and test points hang off them
    yh = 39.6
    track(b, n['INN'], [r2['2'], (r2['2'][0], yh), (u['9'][0], yh), u['9']], W)
    track(b, n['INP'], [r3['2'], (r3['2'][0], yh), (u['10'][0], yh), u['10']], W)
    track(b, n['INN'], [c1['1'], (c1['1'][0], yh)], W)
    track(b, n['INP'], [c1['2'], (c1['2'][0], yh)], W)
    track(b, n['INN'], [(r2['2'][0], yh), (tps['TP1'][0], yh), tps['TP1']], W)
    track(b, n['INP'], [(r3['2'][0], yh), (19.4, yh), tps['TP2']], W)
    # VBUS: from pin 8 down to a via, west on the bottom, up beside R4's VBUS pad; TP3 above it
    v_vb, v_vb2 = (12.9, 40.75), (7.6, 40.75)
    track(b, n['VBUS'], [u['8'], (u['8'][0], 41.5), v_vb], W)
    via(b, n['VBUS'], v_vb, 0.3, 0.85)
    track(b, n['VBUS'], [v_vb, v_vb2], W, P.B_Cu)
    via(b, n['VBUS'], v_vb2, 0.3, 0.85)
    track(b, n['VBUS'], [v_vb2, (r4['2'][0], v_vb2[1])], W)
    track(b, n['VBUS'], [r4['2'], tps['TP3']], W)
    # GND (pin 7) and VS (pin 6) escape south-west to vias; C2 between them; both run north on the bottom
    v_g, v_vs = (11.9, 41.6), (11.0, 42.6)
    track(b, n['BUS-'], [u['7'], (u['7'][0], yb - 0.2), v_g], W)
    via(b, n['BUS-'], v_g, 0.3, 0.85)
    track(b, n['3V3'], [u['6'], (u['6'][0], yb - 0.1), (11.4, 42.6), v_vs], W)
    via(b, n['3V3'], v_vs, 0.3, 0.85)
    track(b, n['BUS-'], [c2['2'], v_g], W)
    track(b, n['3V3'], [c2['1'], (c2['1'][0] + 0.3, 41.9), (10.4, 42.6), v_vs], W)
    track(b, n['BUS-'], [v_g, (v_g[0], 49.4)], 0.4, P.B_Cu)
    v_3 = (gh['2'][0], gh['2'][1] + 1.85)              # under the GH's body, north of its pin 2
    track(b, n['3V3'], [v_vs, (v_vs[0], 51.0), v_3], W, P.B_Cu)
    via(b, n['3V3'], v_3, 0.3, 0.85)
    track(b, n['3V3'], [v_3, gh['2']], W)
    # the logic row (north) to the GH: SCL, SDA, GND (A0, A1)
    track(b, n['SCL'], [u['5'], (u['5'][0], 49.3), (gh['4'][0], 49.3), gh['4']], W)
    track(b, n['SDA'], [u['4'], (u['4'][0], 49.9), (gh['3'][0], 49.9), gh['3']], W)
    track(b, n['BUS-'], [u['2'], (u['2'][0], 50.9), (gh['1'][0], 50.9), gh['1']], W)
    via(b, n['BUS-'], (12.2, 50.9), 0.3, 0.85)
    mp = [pad for pad in fps['J17'].Pads() if pad.GetNumber() == 'MP']
    for pad in mp:
        mx, my = board_xy(pad.GetPosition())
        if mx < D.GH[1]:
            via(b, n['BUS-'], (mx, my + 1.9), 0.3, 0.85)
            track(b, n['BUS-'], [(mx, my), (mx, my + 1.9)], 0.4)
    track(b, n['BUS-'], [u['1'], (u['1'][0], yt + 0.4), (u['2'][0], yt + 0.9)], W)
    return W


ROUTE_LOG = {}


def silk(b, fps):
    """Every holder: its wire, branch and fuse rating in the gap toward its stud, and "58V FUSES ONLY" in line with it on
    the bus band; the studs' names; the warning along the north edge; the board's name on the back."""
    for ref, label, wire, amps, net_in, col, row in D.HOLDERS:
        x, y = D.holder_xy(col, row)
        tag = f'{wire} {amps:g}A' if wire else 'SPARE'
        dx = {'N': 1.2, 'S': -1.2}[row]
        if col == 5:                          # the tie slot H3 sits in line with column 6: its lines go west of it
            dx = {'N': -2.2, 'S': -3.6}[row]
        if row == 'N':
            text(b, tag, (x, 63.1), 1.0, bold=True)
            text(b, '58V FUSES ONLY', (x + dx, 39.6), 1.0, rot=90)
        else:
            if col < 5:
                text(b, tag, (x, 12.95), 1.0, bold=True)
            else:                             # F12: beside the holder (the tie slot H2 is below it)
                text(b, tag, (x + 4.0, 24.4), 1.0, bold=True, rot=90)
            text(b, '58V FUSES ONLY', (x + dx, 36.4), 1.0, rot=90)
    for ref, label, net, x, y, size, wires in D.STUDS:
        if y >= 60 and x < 80:
            text(b, label, (x + 5.0, y), 1.0, bold=True, rot=90)
        elif y <= 10:
            text(b, label, (x, 2.6), 1.0, bold=True)
    text(b, 'PULL A FUSE ONLY WITH BOTH PACKS OUT', (51.0, 74.2), 1.0, bold=True)
    text(b, 'BUS+ IN', (5.0, 13.4), 1.0, bold=True)
    text(b, '12V IN', (83.9, 35.2), 1.0, bold=True)
    text(b, next(s_[1] for s_ in D.STUDS if s_[0] == 'J13'), (83.9, 13.4), 1.0, bold=True)
    text(b, 'STAR', (83.9, 39.6), 1.0, bold=True)
    text(b, 'FRAME', (83.9, 57.6), 1.0, bold=True)
    text(b, 'PLATE BOND', (16.0, 67.6), 1.0)
    text(b, 'SHUNT', (13.5, 28.2), 1.0)
    text(b, 'INA228', (17.6, 46.0), 1.0, rot=90)
    text(b, 'GH 1 GND 2 3V3 3 SDA 4 SCL', (1.5, 59.0), 1.0, rot=90)
    for ref, net, x, y, note in D.TPS:
        text(b, {'INN': 'IN-', 'INP': 'IN+'}.get(net, net), (x, y + 1.9), 1.0)
    for i, line in enumerate(('GYROPUP FUSE BOARD REV ' + D.REV + '  2 oz  1.6 mm  D60',
                              'Littelfuse MINI FL1 holders: MINI 58V (0997) fuses only',
                              'docs/body-fuse-board.md')):
        text(b, line, (44.0, 34.4 - 2.2 * i), 1.2, layer=P.B_SilkS)

# ======================================================================================== project, rules, libraries
# JLCPCB's published capabilities for a 2-layer board in 2 oz copper, read on jlcpcb.com/capabilities/pcb-capabilities
# on 2026-10-27: track/space 0.16/0.16 mm (2 oz); PTH annular ring >= 0.254 mm (2 oz); via hole >= 0.15 (0.2
# preferred) with the pad >= hole + 0.1; pad hole-to-hole 0.45, via hole-to-hole 0.2; NPTH >= 0.5, NPTH slot width
# >= 1.0; copper to a routed edge >= 0.2; legend line >= 0.15, text height >= 1.0, pad to legend 0.15; SMD pad to pad
# (different nets) 0.15; drills 0.15-6.3 mm (larger holes routed).
JLC = {'track': 0.16, 'space': 0.16, 'annular': 0.254, 'via_hole': 0.2, 'hole_to_hole': 0.45, 'npth': 0.5, 'edge': 0.2,
       'silk_line': 0.15, 'text_h': 1.0, 'read_on': '2026-10-27', 'url': 'https://jlcpcb.com/capabilities/pcb-capabilities'}


def net_class(name):
    dom = D.NETS[name][0]
    if name in ('+BAT_IN', '+BUS'):
        return 'BUS48'
    if name in ('SNS_P', 'SNS_N', 'INN', 'INP', 'VBUS'):
        return 'SENSE'
    if name.startswith('OUT_'):
        return 'OUT48' if dom == 'P48' else 'OUT12'
    return {'P12': 'P12', 'GND': 'GND', 'LV': 'LV'}[dom]


DRU = f"""(version 1)
# Gyropup fuse board: clearances by net class (generate.py writes this file). JLCPCB's 2 oz minimums
# ({JLC['url']}, read {JLC['read_on']}) are the floor in fuse-board.kicad_pro; these rules add the voltage
# clearances. IPC-2221B table 6-1 for 51-100 V: B2 (external, uncoated) 0.6 mm, B4 (external, permanent polymer
# coating) 0.13 mm; the bus (D65, 10S) is 41 V charged and under 60 V in regen. 1.0 mm is used between every pair of different
# power nets (a blown branch's output sits at 0 V beside a 53 V neighbour).

(rule "between classes"
  (condition "A.NetClass != B.NetClass && A.NetName != '' && B.NetName != ''")
  (constraint clearance (min 1.0mm)))

(rule "between battery-bus branch outputs"
  (condition "A.NetClass == 'OUT48' && B.NetClass == 'OUT48' && A.NetName != B.NetName")
  (constraint clearance (min 1.0mm)))

(rule "between 12 V branch outputs"
  (condition "A.NetClass == 'OUT12' && B.NetClass == 'OUT12' && A.NetName != B.NetName")
  (constraint clearance (min 1.0mm)))

# the shunt's two sides and its sense lines differ by at most the shunt drop (0.08 V at 80 A)
(rule "shunt group"
  (condition "(A.NetClass == 'BUS48' || A.NetClass == 'SENSE') && (B.NetClass == 'BUS48' || B.NetClass == 'SENSE')")
  (constraint clearance (min 0.2mm)))

# the INA228's own pins put IN-, VBUS and GND 0.2 mm apart (TI DGS, 85 V rated); the sense lines' escape from them
# keeps 0.25 mm under solder mask (IPC-2221B B4: 0.13 mm at 51-100 V). These nets carry no current (VBUS through
# 4.7 kOhm, IN+/IN- through 10 Ohm).
(rule "sense lines beside the logic at the INA228"
  (condition "A.NetClass == 'SENSE' && (B.NetClass == 'GND' || B.NetClass == 'LV')")
  (constraint clearance (min 0.25mm)))

(rule "the INA228's own pin pitch"
  (condition "A.memberOfFootprint('U1') && B.memberOfFootprint('U1')")
  (constraint clearance (min 0.15mm)))

(rule "logic beside ground"
  (condition "A.NetClass == 'LV' && B.NetClass == 'GND'")
  (constraint clearance (min 0.2mm)))
"""


def write_project():
    classes = []
    for name, width in (('Default', 0.2), ('BUS48', 2.0), ('SENSE', 0.2), ('OUT48', 2.0), ('OUT12', 1.0), ('P12', 1.0),
                        ('GND', 0.4), ('LV', 0.2)):
        classes.append({'name': name, 'clearance': 0.2, 'track_width': width, 'via_diameter': 0.85, 'via_drill': 0.3,
                        'microvia_diameter': 0.3, 'microvia_drill': 0.1, 'diff_pair_width': 0.2, 'diff_pair_gap': 0.25,
                        'diff_pair_via_gap': 0.25, 'bus_width': 12, 'line_style': 0, 'wire_width': 6,
                        'pcb_color': 'rgba(0, 0, 0, 0.000)', 'schematic_color': 'rgba(0, 0, 0, 0.000)', 'priority': 2147483647 if name == 'Default' else len(classes)})
    pro = {
        'board': {'design_settings': {
            'defaults': {'board_outline_line_width': 0.1, 'copper_line_width': 0.2, 'copper_text_size_h': 1.5, 'copper_text_size_v': 1.5,
                         'copper_text_thickness': 0.3, 'silk_line_width': 0.15, 'silk_text_size_h': 1.0, 'silk_text_size_v': 1.0,
                         'silk_text_thickness': 0.15},
            'rules': {'min_clearance': JLC['space'] + 0.04, 'min_track_width': JLC['track'], 'min_connection': 0.16,
                      'min_via_annular_width': JLC['annular'], 'min_via_diameter': 0.85, 'min_through_hole_diameter': JLC['via_hole'] + 0.1,
                      'min_hole_to_hole': JLC['hole_to_hole'], 'min_hole_clearance': 0.25, 'min_copper_edge_clearance': 0.3,
                      'min_silk_clearance': 0.0, 'min_text_height': JLC['text_h'], 'min_text_thickness': JLC['silk_line'],
                      'min_microvia_diameter': 0.2, 'min_microvia_drill': 0.1, 'solder_mask_to_copper_clearance': 0.0,
                      'min_resolved_spokes': 1, 'max_error': 0.005, 'use_height_for_length_calcs': True,
                      'allow_blind_buried_vias': False, 'allow_microvias': False},
            'track_widths': [0.0, 0.2, 0.4, 1.0, 2.0, 6.0], 'via_dimensions': [{'diameter': 0.0, 'drill': 0.0}, {'diameter': 0.85, 'drill': 0.3}],
            'diff_pair_dimensions': [], 'drc_exclusions': [],
            'rule_severities': {'lib_footprint_issues': 'ignore', 'lib_footprint_mismatch': 'ignore', 'silk_overlap': 'warning',
                                'silk_over_copper': 'warning', 'silk_edge_clearance': 'warning', 'text_height': 'warning',
                                'text_thickness': 'warning', 'footprint_type_mismatch': 'ignore', 'courtyards_overlap': 'error'}}},
        'boards': [], 'libraries': {'pinned_footprint_libs': [], 'pinned_symbol_libs': []},
        'meta': {'filename': f'{PRJ}.kicad_pro', 'version': 3},
        'net_settings': {'classes': classes, 'meta': {'version': 4}, 'net_colors': None, 'netclass_assignments': None,
                         'netclass_patterns': [{'netclass': net_class(nm), 'pattern': nm} for nm in D.NETS]
                         + [{'netclass': 'LV', 'pattern': 'unconnected-*'}]},
        'pcbnew': {'last_paths': {}, 'page_layout_descr_file': ''},
        'sheets': [[ROOT_UUID, 'Root']], 'text_variables': {},
    }
    (HERE / f'{PRJ}.kicad_pro').write_text(json.dumps(pro, indent=2) + '\n')
    (HERE / f'{PRJ}.kicad_dru').write_text(DRU)
    (HERE / 'fp-lib-table').write_text('(fp_lib_table\n  (version 7)\n  (lib (name "fuse-board")(type "KiCad")(uri "${KIPRJMOD}/fuse-board.pretty")(options "")(descr "the fuse board\'s own footprints"))\n)\n')


def main():
    sym_uuids = write_schematic()
    b, nets, fps = build_board(sym_uuids)
    outline(b)
    route(b, nets, fps)
    silk(b, fps)
    path = HERE / f'{PRJ}.kicad_pcb'
    P.SaveBoard(str(path), b)
    stable_board(path)
    write_project()                           # after SaveBoard, which writes a default project file
    print(json.dumps({k: v for k, v in ROUTE_LOG.items()}, indent=0, default=lambda o: [round(x, 3) for x in o]))
    print('wrote', path.name)


if __name__ == '__main__':
    main()
