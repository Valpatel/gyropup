"""The turret's perfboards, laid out part by part (docs/turret-wiring.md section 6): which part sits where on which
board, checked against the board's edges, its standoff holes, each other and the height its level allows, and drawn on
the 0.1 in grid so a person can build them.

    .venv/bin/python cad/turret_boards.py

Writes exports/turret/wiring/board-<name>.png and boards.json. Sizes are the makers' (Pololu, Adafruit, the parts' data
sheets); a placement is the part's footprint on the board (its body and its leads), in mm from the board's lower left
corner, components side up. The bay's three boards are the CAD's (cad/turret.py TB: 52 x 50, M3 standoff holes 3 mm in
from the edges, parts at most 11 / 12.5 / 8.5 mm tall on levels 0 / 1 / 2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
OUT = R / 'exports' / 'turret' / 'wiring'
HOLE_KEEPOUT = 3.2                      # around each standoff hole: the standoff's Ø5.5 and the screw head

# footprints (w, h, tall) in mm: the modules and ICs, and the passive groups (the parts lying flat or standing in a
# block: a 1/4 W resistor lying is 10.2 x 2.5, a radial MLCC 5.1 x 3.2 x 6, the 100 nF film 7.6 x 3 x 7, the 1 uF film
# 10.5 x 5.5 x 10, the 1 W resistor 15.2 x 3.5 lying)
FP = {
    'D24V150F12': (43.2, 31.8, 11.0), 'D36V50F12': (25.4, 25.4, 9.5), 'D36V28F5': (17.8, 20.3, 7.0), 'Pololu 2815': (25.4, 20.3, 4.1),
    'Feather M4 CAN': (50.8, 22.8, 8.0), 'DIP-16': (20.3, 10.2, 4.5), 'DIP-14': (17.8, 10.2, 4.5), 'DIP-8': (10.2, 10.2, 4.5), 'DIP-6': (7.6, 10.2, 4.5),
    'TO-92': (5.1, 4.0, 5.0), 'TO-220': (10.2, 5.1, 21.0), 'cap 1000uF lying': (24.0, 12.5, 12.5), 'R 1/4 W': (10.2, 2.5, 2.5),
    'button 6x6': (6.0, 6.0, 5.0), 'polyfuse flat': (12.0, 14.0, 3.5), 'pad strip': (10.2, 2.5, 1.0),
}


def group(w, h, tall):
    """A block of passives: its outline on the board and its tallest part."""
    return ('group', w, h, tall)


# (name, size, holes, max part height, title, parts: [(label, footprint, x, y, rotated, note)]); the designators are
# COMPONENTS' (below), and docs/turret-wiring.md section 3 has the circuit
BOARDS = {
    'base': ((50.8, 30.0), [(3.0, 3.0), (47.8, 3.0), (3.0, 27.0), (47.8, 27.0)], 11.0, 'the base board, on the base\'s +x wall (4 x M3 x 6), parts towards the housing', [
        ('D36V50F12 12 V PAN (U2)', 'D36V50F12', 19.0, 2.3, False, '24 V in from the 5 A fuse, 12 V out to the pan servo and the pendant loop'),
        ('NE555 1 kHz (U1)', 'DIP-8', 6.5, 0.5, False, 'astable on the pendant loop\'s 12 V: R1 1.0 k, R2 6.8 k, C1 100 nF film: 986 Hz'),
        ('R1 R2 C2 C3', group(12.0, 5.0, 6.0), 6.5, 10.8, False, 'the 555\'s timing resistors, CTRL and supply decoupling'),
        ('MF-R300 (F1, pan servo)', 'polyfuse flat', 6.5, 15.95, False, 'in the 12 V PAN to the pan servo\'s V'),
        ('R3 2.2 k 1 W, D1', group(5.4, 17.0, 3.5), 0.6, 6.4, False, 'the 555\'s output through D1 (blocks a +24 V fault) and R3 to ring 7 (SAFETY+)'),
        ('C1 film', group(3.2, 8.0, 7.0), 44.6, 6.5, False, 'the 555\'s 100 nF timing capacitor (film, 5 %)'),
        ('servo, ring, CAN pads', 'pad strip', 48.0, 8.0, True, 'the pan servo\'s 3-pin, the ring plug\'s 24 AWG tails, CAN through'),
    ]),
    'level0': ((52.0, 50.0), [(3.0, 3.0), (49.0, 3.0), (3.0, 47.0), (49.0, 47.0)], 11.0, 'bay level 0 on the tray\'s four bosses: the fixed 12 V regulator', [
        ('D24V150F12 12 V MAIN (U3)', 'D24V150F12', 4.4, 9.1, False, 'always on: the speed ceiling (the fixed 12 V rail) and the tilt servo\'s supply'),
        ('2N7000 laser switch (Q1)', 'TO-92', 8.0, 1.0, False, 'gate from LASER_5V (the bus buffer on level 2) through R6 100 R, R7 100 k to GND; drain to the laser\'s -'),
        ('R6 R7', group(10.2, 5.1, 2.5), 14.0, 1.0, False, ''),
        ('12 V pads', 'pad strip', 26.0, 1.5, False, '12 V MAIN out to the 2815 (level 1) and the tilt servo\'s lead (MF-R300 in line)'),
        ('24 V pads', 'pad strip', 20.0, 46.5, False, '+24 V and GND from the bank (level 1)'),
        ('D9 TVS (12 V MAIN)', group(12.7, 4.0, 4.0), 6.5, 42.0, False, 'P6KE15A across 12 V MAIN: Pololu\'s TVS at the 2815\'s input'),
        ('D10 1N5822 (12 V FLY)', group(15.2, 5.5, 5.5), 30.5, 42.0, False, 'across 12 V FLY: Pololu\'s Schottky at the 2815\'s output'),
    ]),
    'level1': ((52.0, 50.0), [(3.0, 3.0), (49.0, 3.0), (3.0, 47.0), (49.0, 47.0)], 12.5, 'bay level 1 on 12 mm standoffs: the safety switch, 5 V and the arm chain\'s front end', [
        ('Pololu 2815 safety switch (U4)', 'Pololu 2815', 6.4, 0.5, False, 'switches 12 V MAIN to 12 V FLY; ON from ARM; its slide switch OFF'),
        ('D36V28F5 5 V (U5)', 'D36V28F5', 32.4, 6.5, False, '24 V in, 5 V out through the MF-R250 (F2, in line) to levels 1 and 2 and the cartridge'),
        ('1000 uF bank (C4)', 'cap 1000uF lying', 6.4, 21.4, False, 'across the ring\'s +24 V and GND'),
        ('1000 uF bank (C5)', 'cap 1000uF lying', 6.4, 34.3, False, ''),
        ('CD74HC423E (U7, both one-shots)', 'DIP-16', 31.2, 27.4, True, 'on 3.3 V. A: the 18.5 ms retriggerable pulse detector (R10 39 k, C6 1 uF); '
         'B: the 3.0 ms trip window (R11 63.4 k to start, selected at bench test 3.3, C7 100 nF film)'),
        ('4N35 opto (U6)', 'DIP-6', 42.2, 27.4, False, 'its LED on SAFETY+/- through R8 2.2 k 1 W, D2 across it reversed; its transistor pulls PULSE low (R9 10 k to 3.3 V)'),
        ('R8 2.2 k 1 W, D2', group(5.5, 17.0, 3.5), 0.6, 6.4, False, 'the opto LED\'s resistor and reverse diode'),
        ('C6 R10', group(5.5, 19.8, 6.0), 0.6, 23.8, False, 'one-shot A\'s timing: 39 k 1 %, 1 uF'),
        ('C7 film, R11, C8', group(7.6, 5.6, 7.0), 41.6, 38.0, False, 'one-shot B\'s timing (R11 chosen from 60.4-73.2 k at bench test 3.3) and U7\'s decoupling'),
        ('R9 R20 R21 R50 C13', group(13.2, 5.7, 11.0), 32.4, 0.5, False, 'standing: PULSE\'s 39 k pull-up and its 100 k to the Feather; BUS_V, '
         'the +24 V through 91 k / 10 k to the Feather\'s A0'),
    ]),
    'level2': ((52.0, 50.0), [(3.0, 3.0), (49.0, 3.0), (3.0, 47.0), (49.0, 47.0)], 8.5, 'bay level 2 on 14 mm standoffs: the MCU, the trip latch and ARM', [
        ('Feather M4 CAN (U8)', 'Feather M4 CAN', 0.6, 13.6, False, 'on its two header rows, USB towards the bay\'s open side; its 3V pin is the logic\'s 3.3 V; '
         'its own 120 R terminates CAN (the Trm jumper left closed)'),
        ('74HC74 trip latch (U9)', 'DIP-14', 7.0, 0.8, False, 'on 3.3 V: D from one-shot B, CLK from GATE_2, /CLR from the button and the power-up RC'),
        ('74HC08 ARM (U10)', 'DIP-14', 26.0, 0.8, False, 'on 3.3 V: ARM = pulses (one-shot A) AND /TRIP'),
        ('74AHCT125 bus buffer (U11)', 'DIP-14', 26.0, 39.4, False, 'on 5 V: the Feather\'s TX onto the half-duplex servo bus (direction on D4), R14 4.7 k pull-up'),
        ('R12 R13 R14 U14 D6', group(17.8, 10.2, 6.0), 7.0, 39.4, False, 'the power-up reset (U14) and its pull-up R12, DIR\'s pull-up R13, the bus pull-up R14, '
         'the RX diode D6'),
        ('R16-R18', group(37.0, 2.5, 2.5), 7.0, 11.05, False, 'resistors lying: RX\'s pull-up, the gates\' 1 k pull-ups to 3.3 V'),
        ('R19 R49 R53', group(37.0, 2.6, 2.5), 7.0, 36.6, False, 'the hall\'s pull-up; LASER_EN\'s pull-down; ARM\'s 100 k to the Feather'),
        ('C9 C11', group(5.6, 6.9, 6.0), 0.6, 6.4, False, 'U9 and U10 decoupling'),
        ('C12', group(7.0, 7.0, 6.0), 44.6, 36.6, False, 'U11 decoupling'),
        ('RESET (SW1, trip)', 'button 6x6', 44.0, 6.5, False, 'recessed: clears a trip without a power cycle'),
    ]),
    'cartridge': ((50.0, 44.0), [(4.0, 6.0), (4.0, 38.0), (36.0, 3.5), (36.0, 40.5)], 21.0, 'the cartridge board on its four posts over the ESCs and the cage plate (4 x M3 x 6)', [
        ('IRLZ44N R-A (Q2)', 'TO-220', 39.8, 4.2, False, 'the right motor\'s three: drains to its phases, sources to GND'),
        ('IRLZ44N R-B (Q3)', 'TO-220', 39.8, 10.3, False, 'gates from BRAKE through 1 k, 10 k gate to GND'),
        ('IRLZ44N R-C (Q4)', 'TO-220', 39.8, 16.4, False, ''),
        ('IRLZ44N L-A (Q5)', 'TO-220', 39.8, 22.5, False, 'the left motor\'s three'),
        ('IRLZ44N L-B (Q6)', 'TO-220', 39.8, 28.6, False, ''),
        ('IRLZ44N L-C (Q7)', 'TO-220', 39.8, 34.7, False, ''),
        ('LM393 gates (U13)', 'DIP-8', 20.0, 2.0, False, 'the two gates\' comparators, 0.3 V hysteresis, open-collector to GATE_1/2'),
        ('74HCT14 brake driver (U12)', 'DIP-14', 8.0, 30.0, False, 'ARM -> 6.8 k / 1 uF -> one Schmitt inverter -> BRAKE (high ~8 ms after ARM falls; '
         'D3 + 1 k release it at once when ARM rises)'),
        ('MF-R300 (F3, feed servo)', 'polyfuse flat', 8.0, 15.0, False, 'in the 12 V FLY to the feed servo\'s V'),
        ('R39-R48 C16', group(15.0, 7.0, 6.0), 20.0, 13.0, False, 'the gates: emitters 100 R from 5 V, receivers 4.7 k pull-ups, 10 k into the comparator, '
         '10 k / 10 k reference, 100 k hysteresis'),
        ('R27-R38 C17-C22', group(18.0, 9.0, 6.0), 20.0, 20.5, False, 'the FETs\' 6 x 1 k gate resistors, 6 x 100 k and 6 x 100 nF gate to GND '
         '(the capacitors right at each FET\'s gate and source legs)'),
        ('R55-R57', group(8.6, 5.6, 11.0), 30.7, 6.8, False, 'standing: 1 k in series in ESC_L, ESC_R and FEED_TTL at the cartridge end'),
        ('D11 TVS (12 V FLY)', group(12.7, 3.6, 4.0), 19.5, 40.2, False, 'P6KE15A across 12 V FLY at the pigtail pads'),
        ('R24-R26 D3 C14 C15', group(12.0, 6.0, 6.0), 26.5, 30.0, False, 'the brake\'s RC and its fast release, U12\'s decoupling, ARM\'s 100 k pull-down'),
        ('pigtail pads', 'pad strip', 8.0, 41.0, False, 'from the two CT plugs: 12 V FLY x 3, GND x 3, ARM, +5 V, GATE_1/2, SIG_GND, ESC_L/R, FEED_TTL'),
    ]),
    'stand': ((70.0, 50.0), [(2.0, 2.0), (68.0, 2.0), (2.0, 48.0), (68.0, 48.0)], 30.0, 'the stand\'s terminal board on the bottom plate\'s four bosses', [
        ('24 V in / out pads', 'pad strip', 10.0, 40.0, False, 'from the fuse and the rocker; to the DT06 plug pins 1-2 (+) and 3-4 (-), 18 AWG'),
        ('pendant pads', 'pad strip', 10.0, 25.0, False, 'the pendant socket\'s (TB3M mini-XLR) pins 1 and 2 to DT06 pins 7 and 8 (the dry loop)'),
        ('CAN pads', 'pad strip', 10.0, 10.0, False, 'the USB-CAN\'s H and L to DT06 pins 5 and 6, twisted; the 120 R is on the USB-CAN'),
    ]),
}

# Every part on the boards: (designator, board, value, catalogue key, what it does). docs/turret-wiring.md section 3
# draws the circuit; cad/build_turret.py counts the parts list's passives from here.
R14W = 'yageo-mfr-25fbf52-{}'                          # 1/4 W 1 % metal film
COMPONENTS = [
    # base board: the 1 kHz pulse oscillator on the pendant loop's 12 V; the reverse-polarity diode; the loop's polyfuse
    ('U1', 'base', 'NE555P', 'ti-ne555p', 'astable: 1.44 / ((R1 + 2 R2) C1) = 986 Hz, 53 %; VCC = the pendant loop (DT12 8), pin 4 to VCC'),
    ('R1', 'base', '1.00 k 1 %', R14W.format('1k'), 'VCC to pin 7'),
    ('R2', 'base', '6.8 k 1 %', R14W.format('6k8'), 'pin 7 to pins 2 and 6'),
    ('C1', 'base', '100 nF film 5 %', 'cap-film-100n-5pct', 'pins 2 and 6 to GND: the timing capacitor'),
    ('C2', 'base', '100 nF X7R', 'cap-mlcc-100n-50v', 'pin 5 (CTRL) to GND'),
    ('C3', 'base', '1 uF X7R', 'cap-mlcc-1u-50v', 'VCC to GND at pin 8'),
    ('D1', 'base', '1N4148', 'onsemi-1n4148', 'pin 3 (anode) to R3: a +24 V fault on the line cannot drive back into the 555'),
    ('R3', 'base', '2.2 k 1 W', 'yageo-rsf100jb-73-2k2', 'D1 to ring 7 (SAFETY+); ring 8 (SAFETY-) is the base\'s GND'),
    ('F4', 'harness', 'MF-R010', 'bourns-mf-r010', 'in line in the wire from the base board\'s 12 V PAN to DT12 7 (the pendant loop out), heat-shrunk: a short of the loop to GND trips it'),
    ('D8', 'harness', '1N5822', 'schottky-1n5822', 'across +24 V and GND right after the 5 A in-line fuse, at the base board\'s input pads (cathode to +24 V): a reversed supply blows the fuse'),
    ('U2', 'base', 'D36V50F12', 'pololu-d36v50f12-4095', '12 V PAN from the +24 V after the 5 A fuse'),
    ('F1', 'base', 'MF-R300', 'bourns-mf-r300', '12 V PAN to the pan servo'),
    # level 0: 12 V MAIN, the laser's switch, the 2815's protection (Pololu: a TVS across its input, a Schottky across its output)
    ('U3', 'level0', 'D24V150F12', 'pololu-d24v150f12-2885', '12 V MAIN, always on'),
    ('Q1', 'level0', '2N7000', 'onsemi-2n7000', 'the laser\'s low side: drain to the laser\'s -, source GND; the laser\'s + on 5 V'),
    ('R6', 'level0', '100 R', R14W.format('100r'), 'LASER_5V (U11 2Y, level 2) to Q1\'s gate'),
    ('R7', 'level0', '100 k', R14W.format('100k'), 'Q1\'s gate to GND'),
    ('D9', 'level0', 'P6KE15A', 'tvs-p6ke15a', 'across 12 V MAIN and GND (cathode to 12 V): the 2815\'s input'),
    ('D10', 'level0', '1N5822', 'schottky-1n5822', 'across 12 V FLY and GND (cathode to 12 V FLY): the 2815\'s output when it opens on a running load'),
    # level 1
    ('U4', 'level1', 'Pololu 2815', 'pololu-2815', '12 V MAIN in, 12 V FLY out, ON = ARM; the slide switch OFF (glue it there)'),
    ('U5', 'level1', 'D36V28F5', 'pololu-d36v28f5-3782', '5 V from +24 V'),
    ('F2', 'level1', 'MF-R250', 'bourns-mf-r250', 'in line in the 5 V'),
    ('C4', 'level1', '1000 uF 35 V', 'panasonic-eeu-fr1v102', '+24 V to GND'),
    ('C5', 'level1', '1000 uF 35 V', 'panasonic-eeu-fr1v102', '+24 V to GND'),
    ('U6', 'level1', '4N35', 'vishay-4n35', 'pin 1 (anode) from R8, pin 2 (cathode) to ring 8; pin 5 (collector) = PULSE; pin 4 (emitter) GND; pin 6 open'),
    ('R8', 'level1', '2.2 k 1 W', 'yageo-rsf100jb-73-2k2', 'ring 7 (SAFETY+) to U6 pin 1: a +24 V fault drives 10 mA, steady, so no edges'),
    ('D2', 'level1', '1N4148', 'onsemi-1n4148', 'across U6\'s LED reversed (anode at pin 2): the LED never sees a reverse voltage'),
    ('R9', 'level1', '39 k', R14W.format('39k'), 'PULSE to 3.3 V (0.085 mA: the 4N35 at 2 mA sinks over 0.36 mA even hot)'),
    ('R50', 'level1', '100 k', R14W.format('100k'), 'PULSE to the Feather\'s A3 (PULSE_MON): the Feather can read PULSE but not drive it'),
    ('U7', 'level1', 'CD74HC423E', 'ti-cd74hc423e', 'on 3.3 V. 1A (1) = PULSE, 1B (2) = 3.3 V, 1/R (3) = /CLR_PU, 1Q (13) = Q_A; '
     '2A (9) = GND, 2B (10) = GATE_1, 2/R (11) = 3.3 V, 2Q (5) = Q_B. The 423 (not the 123): a rising /R never triggers it'),
    ('R10', 'level1', '39 k 1 %', R14W.format('39k'), '3.3 V to pin 15: one-shot A, K x 39 k x 1 uF = 18.5 ms (16-21 ms; K = 0.475 at 3.3 V)'),
    ('C6', 'level1', '1 uF X7R', 'cap-mlcc-1u-50v', 'pin 14 to pin 15'),
    ('R11', 'level1', '63.4 k 1 % (from 60.4-73.2 k)', R14W.format('63k4'), '3.3 V to pin 7: one-shot B, 0.475 x 63.4 k x 100 nF = 3.01 ms (bench test 3.3 picks it)'),
    ('R11a', 'level1', '60.4 k 1 %', R14W.format('60k4'), 'one-shot B\'s choice, bench test 3.3'),
    ('R11b', 'level1', '66.5 k 1 %', R14W.format('66k5'), 'one-shot B\'s choice'),
    ('R11c', 'level1', '69.8 k 1 %', R14W.format('69k8'), 'one-shot B\'s choice'),
    ('R11d', 'level1', '73.2 k 1 %', R14W.format('73k2'), 'one-shot B\'s choice'),
    ('C7', 'level1', '100 nF film 5 %', 'cap-film-100n-5pct', 'pin 6 to pin 7'),
    ('C8', 'level1', '100 nF X7R', 'cap-mlcc-100n-50v', 'U7 pin 16 to pin 8'),
    ('R20', 'level1', '91 k 1 %', R14W.format('91k'), '+24 V to BUS_V'),
    ('R21', 'level1', '10 k', R14W.format('10k'), 'BUS_V to GND (10.1 : 1 to the Feather\'s A0)'),
    ('C13', 'level1', '100 nF X7R', 'cap-mlcc-100n-50v', 'across R21'),
    # level 2
    ('U8', 'level2', 'Feather M4 CAN', 'adafruit-feather-m4-can-4759', 'USB pin from 5 V through D7; 3V pin = the logic\'s 3.3 V (U7, U9, U10, U14 and the pull-ups); '
     'CAN to ring 5/6 (its own 120 R)'),
    ('D7', 'harness', '1N5817', 'schottky-1n5817', 'in line in the 5 V wire to the Feather\'s USB pin (anode at the 5 V, cathode at the USB pin), heat-shrunk: a laptop on the USB-C port and the turret\'s 5 V never feed each other'),
    ('U9', 'level2', 'SN74HC74N', 'ti-sn74hc74n', 'on 3.3 V, a set-only latch. 1D (2) = 3.3 V, 1CLK (3) = TRIP_CLK, 1/PRE (4) = 3.3 V, 1/CLR (1) = /CLR_PU, '
     '1Q (5) = TRIP to A1 (TRIP_IN, polled), 1/Q (6) = /TRIP; the second flip-flop\'s D and CLK to GND, /PRE and /CLR to 3.3 V'),
    ('U10', 'level2', 'SN74HC08N', 'ti-sn74hc08n', 'on 3.3 V. 1A = Q_A, 1B = /TRIP, 1Y = ARM (to U4 ON, CT signal 5, and D12 through R53); '
     '2A = GATE_2, 2B = Q_B, 2Y = TRIP_CLK (gate 2 while the window is open clocks the latch); 3 and 4: inputs to GND'),
    ('U14', 'level2', 'MCP120 (3.0 V)', 'microchip-mcp120', 'the power-up reset: VDD 3.3 V, its open-drain output = /CLR_PU, held low until 3.3 V is up'),
    ('R12', 'level2', '10 k', R14W.format('10k'), '/CLR_PU to 3.3 V (also U7 pin 3)'),
    ('SW1', 'level2', 'B3F-1000', 'omron-b3f-1000', '/CLR_PU to GND: the recessed RESET'),
    ('R53', 'level2', '100 k', R14W.format('100k'), 'ARM to the Feather\'s D12 (ARM_IN): the Feather can read ARM but not drive it'),
    ('U11', 'level2', 'SN74AHCT125N', 'ti-sn74ahct125n', 'on 5 V. 1A = TX (D1), 1/OE = SERVO_DIR (D4), 1Y = SERVO_BUS; 2A = LASER_EN (A5), 2/OE = GND, '
     '2Y = LASER_5V to R6 on level 0 (the 2N7000 wants 5 V on its gate: its threshold is up to 3 V); 3 and 4: A to GND, /OE to 5 V'),
    ('R49', 'level2', '100 k', R14W.format('100k'), 'LASER_EN (A5) to GND: the laser stays off while the Feather boots'),
    ('R13', 'level2', '10 k', R14W.format('10k'), 'SERVO_DIR to 3.3 V: the buffer is off until the firmware drives it'),
    ('R14', 'level2', '4.7 k', R14W.format('4k7'), 'SERVO_BUS to 5 V'),
    ('D6', 'level2', 'BAT85', 'vishay-bat85', 'RX (D0, anode) to SERVO_BUS (cathode): the bus pulls RX low; a high bus (3.3 or 5 V) leaves R16\'s 3.3 V'),
    ('R16', 'level2', '10 k', R14W.format('10k'), 'RX (D0) to 3.3 V'),
    ('R17', 'level2', '1 k', R14W.format('1k'), 'GATE_1 to 3.3 V (fast edges into the latch\'s clock and the one-shot)'),
    ('R18', 'level2', '1 k', R14W.format('1k'), 'GATE_2 to 3.3 V'),
    ('R19', 'level2', '10 k', R14W.format('10k'), 'PAN_INDEX to 3.3 V'),
    ('C9', 'level2', '100 nF X7R', 'cap-mlcc-100n-50v', 'U9 decoupling'),
    ('C11', 'level2', '100 nF X7R', 'cap-mlcc-100n-50v', 'U10 decoupling'),
    ('C12', 'level2', '100 nF X7R', 'cap-mlcc-100n-50v', 'U11 decoupling'),
    # in the harness: the hall's bypass capacitor at the sensor (Allegro: 0.1 uF recommended)
    ('C23', 'harness', '100 nF X7R', 'cap-mlcc-100n-50v', 'across the A1120\'s VCC and GND at the sensor, on its leads'),
    # the cartridge board
    ('U12', 'cartridge', 'SN74HCT14N', 'ti-sn74hct14n', 'on 5 V (CT signal 6). 1A, 2A, 3A (1, 3, 5) all = BRK_RC; 1Y, 2Y, 3Y (2, 4, 6) = BRAKE_A, _B, _C, '
     'each driving two gates; 4A-6A to GND'),
    ('R24', 'cartridge', '100 k', R14W.format('100k'), 'ARM (CT signal 5) to GND: unplugged reads as released'),
    ('R25', 'cartridge', '6.8 k', R14W.format('6k8'), 'ARM to BRK_RC: the delay, 6.8 ms x ln(3.3 / V_T-) = 5-14 ms'),
    ('D3', 'cartridge', '1N4148', 'onsemi-1n4148', 'anode at ARM, in series with R26 to BRK_RC: the release'),
    ('R26', 'cartridge', '1 k', R14W.format('1k'), 'D3 to BRK_RC (the short opens 0.6-1.4 ms after ARM rises)'),
    ('C15', 'cartridge', '1 uF X7R', 'cap-mlcc-1u-50v', 'BRK_RC to GND'),
    ('C14', 'cartridge', '100 nF X7R', 'cap-mlcc-100n-50v', 'U12 decoupling'),
    ('D11', 'cartridge', 'P6KE15A', 'tvs-p6ke15a', 'across 12 V FLY and GND at the pigtail pads (cathode to 12 V FLY)'),
    ('R55', 'cartridge', '1 k', R14W.format('1k'), 'ESC_L (CT signal 1) to the left ESC\'s signal lead'),
    ('R56', 'cartridge', '1 k', R14W.format('1k'), 'ESC_R (CT signal 2) to the right ESC\'s signal lead'),
    ('R57', 'cartridge', '1 k', R14W.format('1k'), 'FEED_TTL (CT signal 3) to the feed servo\'s signal: an unpowered servo is not fed from the bus'),
] + [(f'Q{2 + k}', 'cartridge', 'IRLZ44N', 'infineon-irlz44npbf', f'drain to the {"right" if k < 3 else "left"} motor\'s phase {"ABC"[k % 3]}, source GND')
     for k in range(6)] + \
    [(f'R{27 + k}', 'cartridge', '1 k', R14W.format('1k'), f'BRAKE_{"ABC"[k // 2]} to Q{2 + k}\'s gate') for k in range(6)] + \
    [(f'R{33 + k}', 'cartridge', '100 k', R14W.format('100k'), f'Q{2 + k}\'s gate to GND') for k in range(6)] + \
    [(f'C{17 + k}', 'cartridge', '100 nF X7R', 'cap-mlcc-100n-50v', f'Q{2 + k}\'s gate to source: the ESC\'s phase edges cannot lift the gate') for k in range(6)] + [
    ('F3', 'cartridge', 'MF-R300', 'bourns-mf-r300', '12 V FLY to the feed servo'),
    ('D4', 'cartridge', 'TSAL4400', 'vishay-tsal4400', 'gate 1\'s emitter: anode from R39, cathode GND'),
    ('D5', 'cartridge', 'TSAL4400', 'vishay-tsal4400', 'gate 2\'s emitter'),
    ('R39', 'cartridge', '100 R', R14W.format('100r'), '5 V to D4 (37 mA)'),
    ('R40', 'cartridge', '100 R', R14W.format('100r'), '5 V to D5'),
    ('Q8', 'cartridge', 'TEFT4300', 'vishay-teft4300', 'gate 1\'s receiver: collector to R41 and R43, emitter GND'),
    ('Q9', 'cartridge', 'TEFT4300', 'vishay-teft4300', 'gate 2\'s receiver'),
    ('R41', 'cartridge', '10 k', R14W.format('10k'), '5 V to Q8\'s collector (39 k if bench test 3.4\'s lit level stays over 1 V)'),
    ('R42', 'cartridge', '10 k', R14W.format('10k'), '5 V to Q9\'s collector'),
    ('U13', 'cartridge', 'LM393P', 'ti-lm393p', 'on 5 V. IN+ (3, 5) from the collectors through R43/R44, IN- (2, 6) = REF; OUT (1, 7) = GATE_1, GATE_2 (open collector)'),
    ('R43', 'cartridge', '10 k', R14W.format('10k'), 'Q8\'s collector to U13 pin 3'),
    ('R44', 'cartridge', '10 k', R14W.format('10k'), 'Q9\'s collector to U13 pin 5'),
    ('R45', 'cartridge', '10 k', R14W.format('10k'), '5 V to REF'),
    ('R46', 'cartridge', '10 k', R14W.format('10k'), 'REF to GND (2.5 V)'),
    ('R47', 'cartridge', '100 k', R14W.format('100k'), 'U13 pin 1 to pin 3: 0.3 V of hysteresis'),
    ('R48', 'cartridge', '100 k', R14W.format('100k'), 'U13 pin 7 to pin 5'),
    ('C16', 'cartridge', '100 nF X7R', 'cap-mlcc-100n-50v', 'U13 decoupling'),
]
PASSIVE_PREFIXES = ('yageo-', 'cap-', 'onsemi-1n4148', 'omron-b3f', 'schottky-', 'tvs-', 'vishay-bat85', 'bourns-mf-r010')     # the passives cad/build_turret.py counts


def passive_counts() -> dict:
    """{catalogue key: count} of the boards' resistors, capacitors, diodes and the button."""
    out: dict[str, int] = {}
    for _, _, _, key, _ in COMPONENTS:
        if key.startswith(PASSIVE_PREFIXES):
            out[key] = out.get(key, 0) + 1
    return out


def placed(part):
    label, fp, x, y, rot, note = part
    w, h, tall = fp[1:] if isinstance(fp, tuple) else FP[fp]
    if rot:
        w, h = h, w
    return label, (fp[0] if isinstance(fp, tuple) else fp), x, y, w, h, tall, note


def check(name, b):
    (W, H), holes, hmax, _, parts = b
    errs = []
    rects = [placed(p) for p in parts]
    for label, fp, x, y, w, h, tall, _ in rects:
        if x < -0.01 or y < -0.01 or x + w > W + 0.01 or y + h > H + 0.01:
            errs.append(f'{label}: off the board ({x:.1f}..{x + w:.1f} x {y:.1f}..{y + h:.1f} on {W} x {H})')
        if tall > hmax + 0.01:
            errs.append(f'{label}: {tall} mm tall on a level that allows {hmax}')
        for hx, hy in holes:
            cx, cy = min(max(hx, x), x + w), min(max(hy, y), y + h)
            if (cx - hx) ** 2 + (cy - hy) ** 2 < HOLE_KEEPOUT ** 2 - 1e-6:
                errs.append(f'{label}: over the standoff hole at ({hx}, {hy})')
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            a, b_ = rects[i], rects[j]
            if a[2] < b_[2] + b_[4] - 0.01 and b_[2] < a[2] + a[4] - 0.01 and a[3] < b_[3] + b_[5] - 0.01 and b_[3] < a[3] + a[5] - 0.01:
                errs.append(f'{a[0]} overlaps {b_[0]}')
    return errs


def draw(name, b, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle
    (W, H), holes, hmax, title, parts = b
    fig, ax = plt.subplots(figsize=(8.5, 8.5 * H / W + 0.8), dpi=140)
    ax.add_patch(Rectangle((0, 0), W, H, fc='#e8dcc0', ec='#5b4a2a', lw=1.5))
    g = 2.54
    xs = [1.27 + g * k for k in range(int((W - 1.27) / g) + 1)]
    ys = [1.27 + g * k for k in range(int((H - 1.27) / g) + 1)]
    for x in xs:
        ax.plot([x] * len(ys), ys, '.', color='#b59f72', ms=1.6)
    for hx, hy in holes:
        ax.add_patch(Circle((hx, hy), 1.6, fc='white', ec='#5b4a2a'))
        ax.add_patch(Circle((hx, hy), HOLE_KEEPOUT, fc='none', ec='#5b4a2a', ls=':', lw=0.8))
    col = {'D24V150F12': '#2563eb', 'D36V50F12': '#2563eb', 'D36V28F5': '#2563eb', 'Pololu 2815': '#7c3aed', 'Feather M4 CAN': '#0f766e',
           'TO-220': '#334155', 'cap 1000uF lying': '#1e3a8a', 'polyfuse flat': '#ca8a04', 'button 6x6': '#b91c1c', 'pad strip': '#9ca3af',
           'group': '#d6c49a'}
    for label, fp, x, y, w, h, tall, note in (placed(p) for p in parts):
        ax.add_patch(Rectangle((x, y), w, h, fc=col.get(fp, '#111827'), ec='black', lw=0.8, alpha=0.82, ls='--' if fp == 'group' else '-'))
        txt = label.replace(' (', '\n(') if fp != 'group' else (label if w >= h else label.replace(' ', '\n'))
        ax.text(x + w / 2, y + h / 2, txt, ha='center', va='center', fontsize=6.2 if w > 15 else 5,
                color='#3b2f16' if fp == 'group' else 'white', wrap=True)
    ax.set_xlim(-2, W + 2)
    ax.set_ylim(-2, H + 2)
    ax.set_aspect('equal')
    ax.set_xlabel('mm (0.1 in grid; components side up)')
    ax.set_title(f'{title}\n{W:g} x {H:g} mm, parts up to {hmax:g} mm tall', fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    res, bad = {}, False
    for name, b in BOARDS.items():
        errs = check(name, b)
        bad |= bool(errs)
        draw(name, b, OUT / f'board-{name}.png')
        (W, H), holes, hmax, title, parts = b
        comps = [c for c in COMPONENTS if c[1] == name]
        res[name] = {'title': title, 'size_mm': [W, H], 'max_part_mm': hmax, 'standoff_holes': holes, 'picture': f'exports/turret/wiring/board-{name}.png',
                     'parts': [{'label': q[0], 'footprint': q[1], 'at_mm': [q[2], q[3]], 'size_mm': [q[4], q[5]], 'tall_mm': q[6], 'note': q[7]}
                               for q in (placed(p) for p in parts)],
                     'components': [{'ref': c[0], 'value': c[2], 'key': c[3], 'does': c[4]} for c in comps],
                     'problems': errs}
        print(f'{name:10} {W:g} x {H:g}: {len(parts)} placements, {len(comps)} components' + ('' if not errs else '  PROBLEMS: ' + '; '.join(errs)))
    refs = [c[0] for c in COMPONENTS]
    dup = sorted({r for r in refs if refs.count(r) > 1})
    if dup:
        bad = True
        print('duplicate designators:', dup)
    res['passive_counts'] = passive_counts()
    (OUT / 'boards.json').write_text(json.dumps(res, indent=1) + '\n')
    write_parts_md()
    return 1 if bad else 0


def write_parts_md():
    """exports/turret/wiring/parts.md: every board's parts by designator, value and what each pin does."""
    names = {'base': 'Base board', 'level0': 'Bay level 0', 'level1': 'Bay level 1', 'level2': 'Bay level 2', 'cartridge': 'Cartridge board',
             'harness': 'In the harness (soldered in line, heat-shrunk)'}
    md = ['# The turret\'s boards, part by part (v0)', '',
          'Generated by `cad/turret_boards.py` from its COMPONENTS list; the circuit is docs/turret-wiring.md section 3 and the '
          'placements are the board pictures beside this file. Resistors are 1/4 W 1 % metal film unless the value says 1 W; '
          '"X7R" capacitors are 50 V radial ceramics; "film" capacitors are the timing parts. The catalogue key is the parts '
          'list\'s (exports/turret/bench/bom.json).', '']
    for b, title in names.items():
        md += [f'## {title}', ''] + ([f'![{b}](board-{b}.png)', ''] if b in BOARDS else []) + ['| Ref | Value | Part (catalogue key) | Where it goes |', '|---|---|---|---|']
        md += [f'| {c[0]} | {c[2]} | `{c[3]}` | {c[4]} |' for c in COMPONENTS if c[1] == b]
        md.append('')
    (OUT / 'parts.md').write_text('\n'.join(md))


if __name__ == '__main__':
    sys.exit(main())
