"""The fuse board (D60, task B5): its parts, nets, placement and copper, as plain data. The one source for
generate.py (the KiCad schematic and PCB, run with KiCad's own Python) and for cad/body_fuse_board.py (the board's
facts for the body's layout and wire list). No imports beyond the standard library.

Board-local frame (mm): x along the robot's +x (forward), y along the robot's +y (left), origin at the board's
rear-right corner; robot (x, y) = (bx + ORIGIN[0], by + ORIGIN[1]). The board lies flat on the power plate's top face
on 8 mm printed standoffs (docs/body-fuse-board.md 6).

Topology (docs/body-fuse-board.md 2): the shunt is on the HIGH side, between the MRBF's load stud (J1) and the
board's + bus (+BUS), so the INA228 (85 V common mode, -0.3 V minimum) never sees its inputs below its ground; its
ground is the switched - bus (BUS-), the same as the MCU's. Ten MINI 58V holders hang off +BUS (the four RS-04, the
two VESCs, the two converters' inputs, the charge port, a spare); two hang off the 24 V rail (the J501, the turret).
The charge port's fuse is fed from +BUS, after the shunt, so the charge current is counted (as TI's own high-side
application draws it). The - star point (J15) and the frame bond (J16) are BUS-; MH1's plated M5 screw bonds the
power plate to BUS- through the plate's flush nut.
"""
from __future__ import annotations

NAME = 'fuse-board'
REV = 'A'
SIZE = (88.0, 76.0)                 # board outline (mm), corners rounded
CORNER_R = 2.0
ORIGIN = (34.0, -14.0)              # robot (x, y) of the board's (0, 0) corner: the free area x 34..122, y -14..62
THICKNESS = 1.6
COPPER_OZ = 2.0
COPPER_UM = 70.0                    # 2 oz finished outer copper

# ---------------------------------------------------------------------------------------------------- nets
# name: (domain, what). Domains set the clearances (fuse-board.kicad_dru): P48 the 48 V side, P24 the 24 V rail,
# GND the switched - bus, LV the 3.3 V logic. Between domains (and between different P48/P24 nets) 1.0 mm.
NETS = {
    '+BAT_IN': ('P48', 'from the MRBF\'s load stud (W4), before the shunt'),
    '+BUS': ('P48', 'after the shunt: feeds ten holders'),
    '+24V': ('P24', 'the DDR-120C-24\'s +V (W_24): feeds the J501 and turret holders'),
    'BUS-': ('GND', 'the switched - bus: star point, frame bond, plate bond, the INA228\'s ground'),
    'SNS_P': ('P48', 'Kelvin tap, battery side of the shunt'),
    'SNS_N': ('P48', 'Kelvin tap, bus side of the shunt'),
    'INN': ('P48', 'INA228 IN- after its 10 Ohm (battery side)'),
    'INP': ('P48', 'INA228 IN+ after its 10 Ohm (bus side)'),
    'VBUS': ('P48', 'INA228 VBUS after its 4.7 kOhm'),
    '3V3': ('LV', 'from the MCU on the GH lead'),
    'SCL': ('LV', 'I2C (pull-ups on the MCU carrier, or the Adafruit 5832\'s own)'), 'SDA': ('LV', 'I2C'),
}

# ---------------------------------------------------------------------------------------------------- the holders
# Littelfuse MINI FL1 178.6764.0001 PCB holders (58 V DC, 22 A continuous, MINI fuses to 30 A; Littelfuse's page,
# read 2026-10-27). (ref, branch label, wire, fuse A (None: spare, no fuse fitted), input net, column x, row)
COLS = (26.0, 36.0, 46.0, 56.0, 66.0, 76.0)
ROW_Y = {'N': 54.4, 'S': 21.6}      # holder centres; pin 1 (input) toward the bus band, pin 2 (output) outward
PIN_DY = 4.0                        # the holder's terminals are 8 mm apart
HOLDERS = [
    ('F1', 'RS-04 LF', 'W10', 20, '+BUS', 0, 'N'),
    ('F2', 'RS-04 LR', 'W11', 20, '+BUS', 1, 'N'),
    ('F3', 'RS-04 RF', 'W12', 20, '+BUS', 2, 'N'),
    ('F4', 'RS-04 RR', 'W13', 20, '+BUS', 3, 'N'),
    ('F5', 'VESC L', 'W14', 30, '+BUS', 4, 'N'),
    ('F6', 'VESC R', 'W15', 30, '+BUS', 5, 'N'),
    ('F7', 'DDR-120C IN', 'W16', 10, '+BUS', 0, 'S'),
    ('F8', 'DDR-60L IN', 'W17', 5, '+BUS', 1, 'S'),
    ('F9', 'CHARGE PORT', 'W8', 10, '+BUS', 2, 'S'),
    ('F10', 'SPARE', None, None, '+BUS', 3, 'S'),
    ('F11', 'J501 24V', 'W21', 5, '+24V', 4, 'S'),
    ('F12', 'TURRET 24V', 'W22', 5, '+24V', 5, 'S'),
]


def holder_xy(col, row):
    return COLS[col], ROW_Y[row]


def holder_pins(col, row):
    """(pin1 (input), pin2 (output)) board-local positions."""
    x, y = holder_xy(col, row)
    s = -1.0 if row == 'N' else 1.0            # N row: input south of the centre; S row: input north
    return (x, y + s * PIN_DY), (x, y - s * PIN_DY)


def out_net(ref):
    h = next(h for h in HOLDERS if h[0] == ref)
    return f'OUT_{h[2] or "SPARE"}'


for _h in HOLDERS:
    NETS[out_net(_h[0])] = ('P48' if _h[4] == '+BUS' else 'P24', f'{_h[1]} after its fuse')

# ---------------------------------------------------------------------------------------------------- studs
# M4 studs: an M4 x 18 socket head up from below (head on the bottom pad), a nyloc on top clamping it (a captive
# stud), then the lug(s), a second nyloc. M6 the same with M6 x 20. (ref, label, net, x, y, size, wires landing)
STUD_PAD = {'M4': 7.0, 'M6': 12.0}         # pad diameters (both layers, a ring of vias)
STUD_DRILL = {'M4': 4.3, 'M6': 6.4}
N_STUD_Y, S_STUD_Y = 68.0, 8.0
STUDS = [
    ('J1', 'BUS+ IN', '+BAT_IN', 7.0, 21.0, 'M6', ['W4 (8 AWG) from the MRBF load stud']),
] + [(f'J{2 + i}', h[2], out_net(h[0]), COLS[h[5]], N_STUD_Y, 'M4', [f'{h[2]} {h[1]}'])
     for i, h in enumerate(HOLDERS[:6])] + [
    ('J8', 'W16', out_net('F7'), COLS[0], S_STUD_Y, 'M4', ['W16 DDR-120C-24 Vin+']),
    ('J9', 'W17', out_net('F8'), COLS[1], S_STUD_Y, 'M4', ['W17 DDR-60L-12 Vin+']),
    ('J10', 'W8', out_net('F9'), COLS[2], S_STUD_Y, 'M4', ['W8 charge port +']),
    ('J11', 'SPARE', out_net('F10'), COLS[3], S_STUD_Y, 'M4', ['(spare)']),
    ('J12', 'W21', out_net('F11'), COLS[4], S_STUD_Y, 'M4', ['W21 J501 DC-IN']),
    ('J13', 'W22', out_net('F12'), 83.9, 18.0, 'M4', ['W22 stop relay pole B']),
    ('J14', '24V IN', '+24V', 83.9, 30.0, 'M4', ['W_24: DDR-120C-24 +V (18 AWG)']),
    ('J15', 'STAR', 'BUS-', 83.9, 44.0, 'M4', ['W23 DDR-120C-24 -V', 'W27 DDR-60L-12 -V', 'W_STAR: - bus bar tap 5 (14 AWG)']),
    ('J16', 'FRAME', 'BUS-', 83.9, 53.0, 'M4', ['W33 frame bond (18 AWG green)']),
]

# ---------------------------------------------------------------------------------------------------- mounting
# MH1: the plate's flush nut at robot (50, 47) (the Blue Sea shunt's base nut): an M5 x 12 button head down through
# the plated hole, a printed standoff (8.0 mm) and into the nut; it bonds the plate to BUS-. The plate's three
# cable-tie slots at robot (46, -6), (111, -6), (111, 24) take a tie each through the board's slots and a printed
# tie block. The shunt's other nut at (119, 47) falls 3 mm from the board's east edge: not used.
MOUNTS = [('MH1', 'PLATE BOND M5', 'BUS-', 16.0, 61.0)]
TIES = [('H1', 12.0, 8.0), ('H2', 77.0, 8.0), ('H3', 77.0, 38.0)]       # slot 4 x 10 (y), NPTH
TIE_SLOT = (4.0, 10.0)
STANDOFF_H = 8.0
UNDER_KEEPOUT = [(7.0, 43.15, 3.0, 'VESC L flange screw tip, 4.5 mm above the plate'),
                 (7.0, 70.15, 3.0, 'VESC L flange screw tip, 4.5 mm above the plate')]

# ---------------------------------------------------------------------------------------------------- the shunt and the INA228
SHUNT = ('R1', 13.5, 33.0)          # Bourns CSS2H-3920R-1L00F, 1 mOhm 1 % 8 W; pad 1 (+BAT_IN) west, pad 4 (+BUS) east
U1 = ('U1', 13.5, 46.0, 270.0)      # INA228 (TSSOP-10 3x3, TI DGS): analog pins (6-10) face the shunt (south), logic (1-5) north
SMALL = [  # (ref, value, footprint, x, y, rot, pin1 net, pin2 net, lcsc, note)
    ('R2', '10R 1%', 'Resistor_SMD:R_0603_1608Metric', 9.3, 38.7, 90.0, 'SNS_P', 'INN', 'C22859', 'IN- series (TI SLYS021A 8.1.4: 10 Ohm against a hard short\'s dV/dt; UNI-ROYAL 0603WAF100JT5E)'),
    ('R3', '10R 1%', 'Resistor_SMD:R_0603_1608Metric', 17.7, 38.7, 90.0, 'SNS_N', 'INP', 'C22859', 'IN+ series'),
    ('C1', '100nF 100V X7R', 'Capacitor_SMD:C_0603_1608Metric', 14.25, 38.3, 0.0, 'INN', 'INP', 'C15725', 'differential input filter (Samsung CL10B104KC8NNNC)'),
    ('R4', '4.7k 1W', 'Resistor_SMD:R_2512_6332Metric', 5.0, 38.0, 90.0, '+BAT_IN', 'VBUS', 'C163339', 'VBUS series from the battery side: 11 mA if VBUS fails short (Yageo RC2512FK-074K7L)'),
    ('C2', '100nF 50V X7R', 'Capacitor_SMD:C_0603_1608Metric', 10.2, 41.0, 0.0, '3V3', 'BUS-', 'C14663', 'VS decoupling (Yageo CC0603KRX7R9BB104)'),
]
GH = ('J17', 7.5, 53.5, 180.0)      # JST GH 4-pin SM04B-GHS-TB, opening north: 1 GND (BUS-), 2 3V3, 3 SDA, 4 SCL
GH_PINS = {'1': 'BUS-', '2': '3V3', '3': 'SDA', '4': 'SCL', 'MP': 'BUS-'}
TPS = [('TP1', 'INN', 8.4, 44.8, 'IN- (battery side) / Adafruit 5832 VIN-'),
       ('TP2', 'INP', 20.2, 41.5, 'IN+ (bus side) / Adafruit 5832 VIN+'),
       ('TP3', 'VBUS', 5.0, 43.6, 'VBUS / Adafruit 5832 VBUS')]

# ---------------------------------------------------------------------------------------------------- copper pours
# (net, polygon, both layers). Zones fill around everything of another net with the rule clearances.
POURS = [
    ('+BAT_IN', [(0.6, 13.6), (12.6, 13.6), (12.6, 37.0), (0.6, 37.0)]),
    ('+BUS', [(15.4, 22.6), (60.0, 22.6), (60.0, 37.2), (79.0, 37.2), (79.0, 53.0), (21.2, 53.0), (21.2, 37.0), (15.4, 37.0)]),
    ('+24V', [(61.6, 23.2), (87.4, 23.2), (87.4, 35.8), (61.6, 35.8)]),
]

# ---------------------------------------------------------------------------------------------------- branch copper
# The output copper from each holder's pin 2 to its stud: a straight run on both layers, stitched (widths below are
# what analysis.py checks against IPC-2221 for the fuse's rating).
OUT_W = 6.0                         # mm, both layers
OUT_NECK = (2.6, 3.6)               # width, length of the neck from the holder's pin 2 (clear of the peg slot) to the 6 mm run
SIGNAL_W = 0.2
