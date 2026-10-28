# Body electrics: the 13S bus, the battery, the power skid and the CAN buses

The P0 power system of Gyropup's body as built from `cad/body_wiring.py` (the wire list and the drawing),
`cad/body_battery.py` (the brick and the drawer), `cad/body_layout.py` (where every part sits on the power plate) and
`exports/body/bom.json` (what to buy, by catalogue key). It is the build package for milestone M5's power skid: a
person with the parts, a spot welder and a crimper can build and test it from this page and
[the wiring diagram](../exports/body/wiring.svg). Decisions: D43 (the 13S bus), D45 (the converters and the turret's share),
D54 (the battery and its BMS), D55 (the protection and the switch).
Written 2026-10-27.

![Power and CAN wiring](../exports/body/wiring.svg)

## 1. The numbers

| | |
|---|---|
| Pack | 13S2P Molicel INR-18650-P30B (26 cells), in the belly drawer |
| Voltage | 48.1 V nominal; charged to 53.3 V (4.1 V a cell, not 4.20: about 9 % of the capacity traded for cycle life); empty at 39.0 V (3.0 V a cell) |
| Capacity | 6.0 Ah, 256 Wh to 4.10 V a cell |
| Current | 80 A for a jump's 0.2-0.3 s; 72 A continuous rating (36 A a cell); 9 V of sag at 80 A |
| BMS | Daly K 13S 100 A, BT + UART, common port (B-/P-) |
| Main fuse | MRBF 80 A (Blue Sea 5181 on a 5191 block), 58 V DC, 2 kA interrupting at 58 V |
| Branch fuses | Littelfuse MINI 58V (0997 series), 1 kA at 58 V |
| Rails | 24 V 5 A isolated (Mean Well DDR-120C-24), 12 V 5 A isolated (DDR-60L-12), 5 V 3.2 A (Pololu D36V28F5 from the 12 V) |
| Below SELV | 53.3 V is under the 60 V DC limit: nothing on the robot is a shock hazard, but the pack's short-circuit current is |

The bus was chosen in docs/body-plan.md (D43): every load is rated across 39-53.3 V (the RS-04 15-60 V, the 75100
14-84 V, the switch 12-84 V, the DDR converters 33.6-67.2 V and 18-75 V, the MINI 58V fuses and the MRBF 58 V), and
regeneration has room to 57 V before anything is near its limit.

## 2. The battery

### 2.1 The brick

26 Molicel P30B (18650, 3.0 Ah, 36 A) in 13 groups of two. The cells lie along y (across the robot) in two layers of
13 columns (`cad/body_battery.py` `brick()`: 266 x 76 x 60 mm with the BMS on top, 1.54 kg with its share of nickel and
insulation); a column is one 2P group, its two cells one above the other; the groups' + ends alternate side to side, so
every series link is a short strip from one column to the next.

1. **Match the cells.** Charge or discharge every cell to the same voltage (3.6-3.7 V, within 0.02 V of each other)
   before welding. Write each cell's voltage on a list; reject any below 2.5 V or that warms on the bench.
2. **Fish paper.** One ring on every cell's + end (the 18650's can is the - terminal right up to the + cap).
3. **Lay out the columns** in the printed cell nest (the bay halves, `exports/body/bay_rear.stl` and `bay_front.stl`),
   + ends alternating, so that column 1's - end and column 13's + end come out at the same end of the brick.
4. **Weld the 2P groups and the series links** with the 2P pre-shaped strip (IMR 0.15 x 18.5 mm), four welds a cell
   end, then a second layer of strip on every series link (the jump's 80 A crosses each link). Test-weld scrap first
   and peel it: the nugget should tear the strip, not lift.
5. **Kapton** between the layers' ends, over every weld, and round the brick's edges where the strip turns.
6. **Balance leads** (the BMS's 14-wire harness, 24 AWG): B0 to the brick's - end (group 1 -), B1 to the group 1/2
   link, B2 to 2/3 ... B12 to the 12/13 link, B13 to the brick's + end (group 13 +). Solder each to its strip's tab, not
   to a cell. **Do not plug the harness into the BMS yet.**
7. **Check the harness**: with the BMS unplugged, measure each pin against B0: 3.6, 7.2, 10.8 ... 46.8 V, rising by
   one cell each pin, in order. Any step that is not one cell is a wrong tap: fix it before going on.
8. **BMS:** B- lead (10 AWG) to the brick's - end first; then plug the balance harness; then P- (10 AWG, to the
   XT90-S's - cup); the pack + lead (10 AWG) from the brick's + end to the XT90-S's + cup. The XT90-S female (sockets)
   goes on the pack, the male on the robot.
9. **Set the BMS** in Daly's app over Bluetooth before the first charge (and write the settings in the build log):
   cell over-voltage 4.15 V (release 4.1 V), under-voltage 3.0 V
   (release 3.2 V), charge over-current 6 A, discharge over-current
   100 A, charge temperature 0-45 °C, discharge
   -10-60 °C, balancing from 3.9 V at a
   15 mV spread. The over-voltage is the backstop: the charger stops at 4.10 V a cell.
10. **Wrap** the brick (Kapton, then the bay halves screw together round it: 4 x M5 x 10 each side into the belly's nuts).

The BMS's UART ground is B-, not the robot's ground (P-): a wire from it to the MCU would be a path round the BMS's
switches when they are open. So the BMS is read only over its Bluetooth, by the QT Py ESP32-S3 on the MCU board, which
puts the cell voltages and the state of charge on CAN bus C (D54). Nothing is wired to the BMS but the pack.

### 2.2 Charging

The charge port is an XT60H **female** in a printed bezel in the belly (no live pins on the robot). It goes straight to
the pack's + (through a 10 A MINI 58V fuse at the MRBF block's battery stud, W8) and to the shunt's load side (W9): it
charges with the main switch off, and the shunt counts the charge. The charger is the Luna 48V Advanced (XT60 output):
set its voltage knob to 90 % and **meter its open-circuit output before it ever meets the pack: it must read 53.3 V
(±0.2)**; if it does not, the backup is the Grin Satiator, which is set to 53.3 V directly. Charge current 2-3 A
(0.3-0.5 C). Charge on a non-flammable surface, attended, the robot's main switch off. The BMS's over-voltage at 4.15 V
is the backstop if the charger is mis-set.

## 3. The main path and the branches

On the power plate (`exports/body/sendcutsend/power_plate_*.dxf`; the layout in `cad/body_layout.py`): the pack's +
lead goes to the MRBF block's battery stud (its M8 post sits in a printed insulating bushing in the plate), the 80 A
fuse to the + bus bar; the pack's - lead to the shunt, then the main switch (Flipsky Smart Enhanced V2.0, momentary
mode: hold 0.3 s on, 1 s off; its smart mode off), then the - bus bar. **Flipsky draws its switch on the negative:
read the wiring card that comes with it before the first wire, and if it is high side, swap the switch and the shunt
into the + lead in the drawing.** The bus bars are SendCutSend C110 copper (0.125 in, five M6 taps each) on printed
insulators: no screw of a bar reaches the plate.

Every branch has its own MINI 58V fuse in an inline holder on the + side, as close to the bus bar as the lead allows.
The holders are rated 32 V by Eaton; the fuse does the interrupting (1 kA at 58 V), so each holder is labelled
**58 V fuses only** and a fuse is pulled only with the pack unplugged (D55). A fuse board with PCB holders (Keystone
3568, JLCPCB) replaces them in P3.

### 3.1 The wire list

Red +, black -, white sense or signal, green the frame bond. Silicone wire throughout (BNTECHGO, 200 °C, 600 V). Lengths
are cut to the plate in P0 and recorded.

| Wire | From | To | AWG | Colour | Ends | Fuse | Why |
|---|---|---|---|---|---|---|---|
| W1 | pack B+ (group 13 +) | XT90-S female (pack lead) | 8 | red | XT90-S solder cup | MRBF 80 A (on the robot side) | 80 A pulses, 72 A cells |
| W2 | BMS P- | XT90-S female (pack lead) | 8 | black | XT90-S solder cup | - | the BMS switches the negative |
| W3 | XT90-S male (robot) | MRBF block, battery stud (M8) | 8 | red | lug M8 | - | unfused until the MRBF: keep it short (<150 mm) |
| W4 | MRBF block, load stud (M8) | + bus bar, tap 1 (M6) | 8 | red | lugs M8 / M6 | MRBF 80 A | the whole robot |
| W5 | XT90-S male (robot) | shunt, battery side (M8) | 8 | black | lug M8 | - | the battery negative |
| W6 | shunt, load side (M8) | main switch IN- (B-) | 8 | black | ferrule / its lead | - | Flipsky draws the switch on the negative: check its card |
| W7 | main switch OUT- (P-) | - bus bar, tap 1 (M6) | 8 | black | lug M6 | - | the switched negative: everything below is off with it |
| W8 | charge port XT60H-F + | MRBF block, battery stud (M8) | 18 | red | XT60 / lug M8 | MINI 58V 10 A (inline, at the stud) | charger 2-3 A; the fuse guards the lead against a pack short |
| W9 | charge port XT60H-F - | shunt, load side (M8) | 18 | black | XT60 / lug M8 | - | after the shunt (it counts the charge), before the switch (the robot can be off) |
| W10 | + bus tap 2 | RS-04 left front (XT60H) | 14 | red | lug M6 / XT60H-M | MINI 58V 20 A | ~12 A at a jump, 25 A peaks: 14 AWG silicone |
| W11 | + bus tap 2 | RS-04 left rear (XT60H) | 14 | red | lug M6 / XT60H-M | MINI 58V 20 A | as W10 (two lugs share the tap) |
| W12 | + bus tap 3 | RS-04 right front (XT60H) | 14 | red | lug M6 / XT60H-M | MINI 58V 20 A | as W10 |
| W13 | + bus tap 3 | RS-04 right rear (XT60H) | 14 | red | lug M6 / XT60H-M | MINI 58V 20 A | as W10 |
| W14 | + bus tap 4 | VESC left (Flipsky 75100) + | 12 | red | lug M6 / XT60H-M | MINI 58V 30 A | the wheel: firmware limits it to 25 A |
| W15 | + bus tap 4 | VESC right + | 12 | red | lug M6 / XT60H-M | MINI 58V 30 A | as W14 |
| W16 | + bus tap 5 | DDR-120C-24 Vin+ | 18 | red | lug M6 / ferrule | MINI 58V 10 A | 120 W out: 3.3 A in at 40 V, plus its inrush |
| W17 | + bus tap 5 | DDR-60L-12 Vin+ | 18 | red | lug M6 / ferrule | MINI 58V 5 A | 60 W out: 1.7 A in at 40 V |
| W18 | - bus taps 2-3 | RS-04 x 4 (XT60H) | 14 | black | lug M6 / XT60H-M | - | returns, one per motor |
| W19 | - bus tap 4 | VESC left, right - | 12 | black | lug M6 / XT60H-M | - | returns |
| W20 | - bus tap 5 | DDR-120C-24 Vin-, DDR-60L-12 Vin- | 18 | black | lug M6 / ferrule | - | returns |
| W21 | DDR-120C-24 +V | J501 DC-IN (XT30) | 18 | red | ferrule / XT30-M | MINI 5 A | the J501: 60 W peak, 2.5 A |
| W22 | DDR-120C-24 +V | stop relay, pole B (in) | 18 | red | ferrule / screw terminal | MINI 5 A | the turret's branch: 60 W peaks (its own fuse stays in the turret too) |
| W23 | DDR-120C-24 -V | J501 and turret returns; star point | 18 | black | ferrule / XT30-M | - | one tie from -V to the - bus (the CAN reference) |
| W24 | DDR-60L-12 +V | lidar interface box (XT30) | 18 | red | ferrule / XT30-M | (the converter's 5 A limit) | VLP-16: 8 W, 3 A at spin-up |
| W25 | DDR-60L-12 +V | 5 V buck VIN (Pololu D36V28F5) | 22 | red | ferrule / solder | (the converter's 5 A limit) | ~0.6 A at 12 V |
| W26 | DDR-60L-12 +V | radio-stop jack pin 3 (+12 V) | 22 | red | ferrule / jack | (the converter's 5 A limit) | D37: the jack offers 12 V |
| W27 | DDR-60L-12 -V | lidar box, buck, jack GND; star point | 18 | black | ferrule | - | one tie to the - bus |
| W28 | 5 V buck VOUT | Nucleo E5V, 4 CAN Pal, QT Py 5V, VN-100, radio receiver | 22 | red | solder / GH | (the buck's 3.2 A limit) | ~1 A in all |
| W29 | 5 V buck GND | the same, GND | 22 | black | solder / GH | - |  |
| W30 | shunt sense + (battery side screw) | INA228 IN+ | 22 | white | ring / screw terminal | - | Kelvin pair, twisted, away from the 10 AWG |
| W31 | shunt sense - (load side screw) | INA228 IN- | 22 | white | ring / screw terminal | - | the INA228's own 15 mOhm shunt is removed |
| W32 | + bus (via the DDR-60L tap) | INA228 VBUS | 22 | red | ring | MINI 58V 5 A (shared with W17) | pack voltage, 85 V input |
| W33 | frame (a tray PEM stud) | - bus star point | 18 | green | ring M5 / lug M6 | - | a + short to the frame blows a fuse, not leaves it live |
| W34 | stop relay, pole B (out) | DT06-12SA pins 1, 2 | 18 | red | size-16 sockets | MINI 5 A (W22) | two pins in parallel, as the turret asks; dead whenever the stop relay is open |
| W35 | W23 (24 V return) | DT06-12SA pins 3, 4 | 18 | black | size-16 sockets | - |  |
| W36 | J501 can1 (H, L) | DT06-12SA pins 5, 6 | 22 | white | twisted pair, size-16 sockets | - | the turret terminates its end; the J501 its own |
| W37 | stop relay, pole A (closed = run) | DT12 pins 7, 8 (SAFETY_A, SAFETY_B) | 22 | white | twisted pair | - | the turret's dry safety loop (12 V at 2 mA; D41 D7: it cuts the flywheels and the dial in hardware) |
| W38 | stop relay coil, + side | MCU STOP sense (divider 12 V to 3.3 V) | 22 | white | GH | - | 12 V on the coil = the radio says run: the MCU sits the robot down when it drops (D37) |
| W39 | 12 V rail via the RC switch's contact | stop relay coil, + side | 22 | red | solder / screw terminal | (the converter's 5 A limit) | the coil (12 V, 33 mA) is fed only while the radio says run; its - side through the MCU's MOSFET (MCU_RUN), a diode across it |

### 3.2 The rails

- **24 V** (DDR-120C-24, 120 W): the J501 (60 W at MAXN) and the turret (60 W peaks, 40 W playing). Exactly its
  rating at the two peaks together: the firmware staggers the turret's flywheel start from the J501's boot, and a
  DDR-240C-24 (10 A, $132.74 at TRC) is the step up if the bench shows it at its limit.
- **12 V** (DDR-60L-12, 60 W): the lidar interface box (8 W, 3 A at spin-up), the 5 V buck (~5 W), the radio-stop
  jack; in P3 the SSC1 pods (25.6 W) and the eyes, switched on after the lidar has spun up.
- **5 V** (Pololu D36V28F5 from the 12 V, 3.2 A): the Nucleo (E5V), four CAN Pal, the QT Py, the VN-100, the radio
  receiver; about 1 A in all.

Both converters are isolated; each one's -V is tied once to the - bus at the star point (W23, W27), so the MCU, the CAN
transceivers and the motor drivers share one reference. The frame is bonded to the star point (W33): a + lead chafed
through to the aluminium blows its fuse instead of leaving the frame live.

## 4. CAN

| Bus | Master | Nodes, in order | Notes |
|---|---|---|---|
| A | MCU FDCAN1 (CAN Pal 1, 120 Ohm on) | RS-04 left front → RS-04 left rear (120 Ohm at its plug) | 1 Mbit/s, the left leg |
| B | MCU FDCAN2 (CAN Pal 2, 120 Ohm on) | RS-04 right front → RS-04 right rear (120 Ohm at its plug) | 1 Mbit/s, the right leg |
| C | MCU FDCAN3 (CAN Pal 3, 120 Ohm on) | VESC left → VESC right → QT Py ESP32-S3 (CAN Pal 4, off): the BMS over Bluetooth → J501 can0 (its own 120 Ohm on) | 1 Mbit/s: wheels, battery, the computer |
| T | J501 can1 | the turret (its own bus) | the turret workstream's |

All 1 Mbit/s classic CAN (the RS-04s and the VESCs speak it; the G474's FDCAN runs it), 22 AWG twisted by hand at
about 30 twists a metre, 120 Ohm at both ends of each bus and nowhere else (the CAN Pal's switch, the J501's built-in
terminator). The J501's two ports are capacitively isolated (Seeed wiki, read 2026-10-27); if only one comes up on the
board (`ip link`), the turret moves to an isolated USB-CAN adapter as on its bench (docs/body-plan.md 9).

## 5. The radio stop and the switches

The radio stop (D37, D55): the ER3C-i receiver (failsafe: no pulses) drives one Pololu RC relay switch; its contact feeds the coil of the stop relay (Omron G2RL-2, DPDT, 12 V), whose other end goes to ground through the MCU's MOSFET. The relay holds only while the radio says run AND the MCU says run. Pole A is the turret's dry safety loop (TM pins 7, 8: the turret cuts its flywheels and dial in 20 ms), pole B is in the turret's 24 V branch (the independent cut); the MCU senses the coil voltage and sits the robot down when the radio drops, and opens the relay itself when the robot sits. The main switch is the hard off.

No contactor, no e-stop button on the robot (D37): the radio stop sits the robot down, and the main switch on the
belly is the hard off for a person standing at the robot. The stop relay, its MOSFET (a logic-level N-channel on
MCU_RUN), the flyback diode and the 12 V-to-3.3 V divider for the sense sit on the MCU carrier's protoboard. The
turret's interface is docs/turret-next-plan.md 3.1-3.2 (TM pins 1-2 +24 V, 3-4 GND, 5-6 CAN, 7-8 the dry safety
loop): plug its DT12 only with the stop relay open (its three 1,000 µF capacitors charge through the plug otherwise).

## 6. Bring-up (P0, on the bench, before the plate goes into the robot)

The whole power skid is one plate: it is built and tested on the bench with dummy loads, then dropped into the body
on its four posts.

1. **Continuity, unpowered**: every W-row end to end; no + to - or + to plate (> 1 MOhm); the frame bond to the - bus
   (< 0.1 Ohm). Fuses out.
2. **Pack alone**: 46-49 V at the XT90 after the build; the BMS app shows all 13 cells within 15 mV.
3. **Plug in, switch off**: the bus reads 0 V (the low-side switch is open); the charge port reads the pack.
4. **Switch on** (hold the button 0.3 s): the bus at pack voltage. Fit the converter fuses only: the 24 V, 12 V and
   5 V rails within 2 % of nominal; their -V to the - bus 0 V.
5. **MCU**: the INA228 reads the pack within 0.2 V of a meter and the current within 0.1 A at a 2 A dummy load on the
   24 V rail; the QT Py relays the 13 cell voltages from the BMS onto bus C; with the transmitter switched off the
   stop relay opens within 0.5 s (the receiver's failsafe: no pulses), the turret's pins 7-8 read open and 1-2 dead,
   and the MCU logs the stop; MCU_RUN low opens it too.
6. **Branches**: fit the RS-04 and VESC fuses one at a time with nothing plugged; then each motor on its own (the leg
   workstream's bring-up) at a 10 A current limit.
7. **Switch off with the buses loaded**: no spark at the XT90 (the switch takes it); the rails fall in order.
8. **Charge**: the charger metered at 53.3 V; the first charge watched to the end: the charger stops at 53.3 V, the
   BMS does not trip.

## 7. Open items

- The Flipsky switch's side (low or high) from its wiring card on arrival (section 3).
- The Daly K BMS's mass and its short-circuit trip current: the MINI 58V (1 kA) and the MRBF (2 kA) interrupt
  ratings must be above the pack's prospective short-circuit current through the BMS; 26 P30B in 13S2P can source
  more than 1 kA into a dead short, and the BMS's short-circuit protection (microseconds) is what limits it. Read it
  from the BMS's card, or measure the trip on the bench with a current-limited supply.
- The Luna charger's 90 % voltage (metered before use).
- The INA228 breakout's on-board shunt removed (a 15 mOhm resistor in parallel with the 0.33 mOhm external shunt would
  take 2 % of the current: small, but it is not rated for it).
