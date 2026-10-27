# Turret wiring and harness

The electrics of the foam-ball turret as built from cad/turret.py: what crosses the slip ring, every connector and its
pinout, every conductor's gauge and length, the fuses, the hardware arm chain (safety pulses, the overspeed trip, the
phase-short brake) and the current budget. It implements docs/turret-plan.md section 2 (the architecture) and task T2;
the numbers from the physics come from docs/turret-physics.md. Part numbers are the catalogue keys of
exports/turret/bench/bom.json (catalog/turret.json, hardware.json, sourcing.json).

Three places, two moving joints:

```
 robot / bench stand          | BASE (fixed)                  | SLIP RING |  TURRET (pans)                | CT  | CARTRIDGE (tilts,
 DT06-12SA plug on the harness|  DT04-12PA receptacle         |  stator   |  rotor -> turret bay (-y arm)  |     |  lifts off)
                              |  base board (+x, in the base) |  -> rotor |  3 boards: power, logic, MCU   |     |  2 x AM32 ESC, C610,
                              |  pan servo (STS3215)          |           |  tilt servo (+y arm), laser    |     |  phase-short brake,
                              |                               |           |  (cradle), hall switch          |     |  gates, hopper beam
```

The pan joint is the slip ring (continuous pan). The tilt joint (yoke to cradle) is a lead loop: everything that rides
the cradle or the cartridge leaves the turret bay as one bundle and crosses the tilt axis in a 40 mm loop beside the
-y pivot. The cartridge (CT) is unplugged by hand when it is changed: two Micro-Fit connectors on a short pigtail.

## 1. Connectors and pinouts

### 1.1 TM connector: DT12 (base, -y pad)

TE Deutsch DT04-12PA-L012 receptacle on the pan base (`te-dt04-12pa-l012`, W12P wedgelock `te-w12p`, 12 x size-16 pins
`te-0460-202-16141`); the mating DT06-12SA plug with its W12S wedge and sockets on the robot's or the stand's harness
(`te-dt06-12sa-kit`). Size-16 contacts, 13 A each. 16 AWG on the power pins, 22-24 AWG twisted pairs on the signals.

| Pin | Signal | Notes |
|---|---|---|
| 1, 2 | +24 V | paralleled, 16 AWG each; from the robot's head rail (the radio stop cuts it upstream) or the stand's fuse and switch |
| 3, 4 | GND | paralleled, 16 AWG each |
| 5, 6 | CAN_H, CAN_L | twisted pair; the turret's node terminates its end (120 R on the turret board); the robot's port (or the stand's USB-CAN) the other |
| 7, 8 | SAFETY_A, SAFETY_B | the dry loop from the hold-to-run pendant (bench) or the radio stop (robot): closed = run. Twisted pair |
| 9, 10 | spare | a second CAN or a camera's pair later |
| 11 | LINE_SENSE | 24 V present (for the lights); optional |
| 12 | spare | |

### 1.2 The slip ring

Robot ring, Senring M220-0210-12S (`senring-m220-0210-12s`): two 10 A power rings (17 AWG leads) and twelve 2 A signal
rings (26 AWG). Ask the vendor for the power rings at the flange end and the CAN rings adjacent (docs/turret-plan.md 5.2).

| Ring | Signal | Lead | Notes |
|---|---|---|---|
| P1 | +24 V (fused in the base) | 17 AWG | |
| P2 | GND | 17 AWG | the only power return |
| S1, S2 | CAN_H, CAN_L | 26 AWG, adjacent rings | twisted on both sides of the ring |
| S3, S4 | SAFETY+, SAFETY- | 26 AWG, adjacent | the 1 kHz pulse loop (section 3.1) |
| S5 | SERVO_TTL | 26 AWG | the Feetech half-duplex bus to the pan servo in the base |
| S6 | SIG_GND | 26 AWG | the TTL and pulse reference, tied to GND on the turret board only |
| S7, S8 | CAM+, CAM- | 26 AWG | reserved; both ends to GND through 100 k |
| S9-S12 | spare | | |

Bench ring, SparkFun ROB-13065 (`sparkfun-rob-13065`, twelve 2 A rings, 28 AWG): rings 1-3 +24 V, 4-6 GND (three in
parallel each way: 6 A), 7-8 CAN_H/L, 9-10 SAFETY+/-, 11 SERVO_TTL, 12 SIG_GND. With only 6 A per side the flywheels'
200 ms soft spin-up is mandatory on the bench ring (2.2 A peak at the ring against 12 A for a stepped start,
docs/turret-physics.md section 9); the firmware refuses a stepped start when it reads the bench-ring flag from its
configuration.

### 1.3 The ring's two connectors: Micro-Fit 3.0, 2 x 4

Both ends of the ring end in a Molex Micro-Fit 3.0 dual-row 8-way pair, so the ring is changed by unplugging two
connectors: the stator side at the base board, the rotor side at the turret bay's level-2 board. The ring's leads carry
the receptacle (`molex-43025-0800`, female contacts `molex-43030-0038` for 17-18 AWG, `molex-43030-0001` for 24-26 AWG);
the boards' harnesses the plug (`molex-43020-0800`, male `molex-43031-0021` / `molex-43031-0001`). 8.5 A per contact.

| Pin | Rotor and stator connector (same pinout both ends) |
|---|---|
| 1 | +24 V |
| 2 | GND |
| 3 | CAN_H |
| 4 | CAN_L |
| 5 | SAFETY+ |
| 6 | SAFETY- |
| 7 | SERVO_TTL |
| 8 | SIG_GND |

On the bench ring the three paralleled +24 V leads share pin 1 and the three GND leads pin 2 (crimp the 28 AWG
triplets into one 18 AWG contact with a short 18 AWG pigtail and a solder sleeve).

### 1.4 The CT connectors (turret to cartridge): power 2 x 3 and signal 2 x 6

The cartridge brings a 150 mm pigtail with two plugs; the cradle carries the two receptacles on its -y rail (behind the
latch) on the harness from the turret bay. The two connectors have different sizes, so neither can go into the other's
place, and Micro-Fit housings are polarised. The 12 V flywheel rail and the 24 V dial rail are on fixed pins of the
power connector, and on the cartridge the 24 V pin is wired to the C610 alone: no plug-in error can put 24 V on an ESC.

Power, Micro-Fit 3.0 2 x 3 (43025-0600 / 43020-0600 class, the 6-way of the same family), 18 AWG, 8.5 A per contact:

| Pin | Signal | Load |
|---|---|---|
| 1, 2 | +12 V FLY | the two AM32 ESCs (8.7 A peak in a 10/s burst, 3.9 A in the soft start; two contacts, 17 A) |
| 3 | +24 V DIAL | the C610 alone (10 A for the ~100 ms of a dial step: physics finding 2) |
| 4, 5, 6 | GND | both rails' return |

Signal, Micro-Fit 3.0 2 x 6 (24-26 AWG), so it cannot mate with the 2 x 3:

| Pin | Signal | Notes |
|---|---|---|
| 1 | ESC_L | bidirectional DShot300 from the Feather (eRPM telemetry back on the same wire) |
| 2 | ESC_R | as above |
| 3, 4 | CAN_H, CAN_L | to the C610, twisted |
| 5 | BRAKE | the arm chain's brake drive (high = phases shorted), to the brake board beside the ESCs |
| 6 | +5 V | gates, hopper beam |
| 7 | GATE_1 | first chronograph gate (LM393 output, open collector to the Feather and the trip one-shot) |
| 8 | GATE_2 | second gate |
| 9 | BEAM | hopper-full beam |
| 10 | SIG_GND | |
| 11, 12 | spare | |

### 1.5 Small connectors on the turret

| Run | From | To | Connector |
|---|---|---|---|
| Tilt servo | turret bay level 1 (the 74AHCT125 bus buffer, 12 V AUX) | STS3215 on the +y arm | the servo's own 3-pin lead (Feetech 5264-type), 200 mm extension |
| Pan servo | base board (12 V PAN, the TTL from ring S5) | STS3215 in the base | its own 3-pin lead |
| Laser | level 1 (12 V AUX through a logic MOSFET switched by the Feather's LASER_EN) | the laser on the cradle tab | 2-pin, 24 AWG, across the tilt loop |
| Hall index | level 2 (5 V, GND, PAN_INDEX) | A1120LUA-T in the turntable's underside | 3 x 26 AWG up the Ø2.8 hole beside it |
| Lights | level 2 (5 V, GND, NEOPIXEL) | the 12-LED ring | 3-pin |

## 2. Conductors

| Run | Conductors | Gauge | Length (est from the CAD) | Strain relief |
|---|---|---|---|---|
| Robot / stand harness to DT12 | 2 + 2 power, 3 pairs | 16 AWG, 22-24 AWG pairs | robot's | the DT06's backshell (TE 1011-248-1205 class) |
| DT12 to the base board | +24 V, GND, CAN pair, safety pair | 16 AWG, 24 AWG pairs | 120 mm round the housing | cable tie to the base's housing at 60 mm |
| Base board to the ring's stator plug | 8 (section 1.3) | 18 AWG power, 24 AWG signals | 100 mm | the carrier (the ring's leads), a tie at the board |
| Ring rotor leads to the turret bay | the ring's own leads | 17 + 26 AWG (robot ring), 28 AWG (bench) | 160 mm: up the Ø40 bore beside the coupling, through the yoke's slot and the -y arm's window | tied to the driver disc's crescent (rule: within 30 mm of the connector, docs/mechanical-interfaces.md rule 5) |
| Turret bay to the CT receptacles on the cradle | 2 x 3 power, 2 x 6 signal | 18 AWG, 24-26 AWG | 220 mm with the 40 mm tilt loop | a tie at the yoke arm, one at the cradle rail |
| Cartridge pigtail | the same | 18 AWG, 26 AWG | 150 mm | a tie at the cartridge's base plate |
| Turret bay to the tilt servo | 3 | the servo's own | 200 mm across the bridge | ties on the bridge |
| Turret bay to the laser | 2 | 24 AWG | 250 mm in the tilt loop | tie at the cradle tab |

Twisted pairs: CAN, SAFETY, the gates' signal with SIG_GND. Power and signal bundles run on opposite sides of the Ø40
bore (plan 2.7). 5 mm clearance from anything that moves at every pose (the clash sweep checks the Ø7.5 bundle the CAD
draws for the ring's rotor leads: 3.25 mm from the turntable's bore, 3.7 from the coupling, 3 at the yoke's slot).

## 3. The arm chain (no microcontroller in it)

### 3.1 Safety pulses across the ring

```
 BASE                                          RING                    TURRET (level 1)
 DT12 7 ──┐ pendant / radio stop (dry loop)                                                         
          └─ 12 V PAN ─> 78L05 ─> NE555 astable ── 2k2 ── S3 SAFETY+ ──────> 2k2/1W ─> 4N35 LED
                         (1 kHz, 50 %)                                                   │
 DT12 8 ── loop return                          S4 SAFETY- ─────────────────────────────┘
                                                                 4N35 transistor ─> 74HC123 #1 (retriggerable,
                                                                                    t = 20 ms) ─ Q ─┐
                                                                                                    │
 TRIP latch (section 3.2): /TRIP ──────────────────────────────────────────────────────────────────┤
                                                                                                    v
                                                                              74HC08: ARM = Q AND /TRIP
                                                                                 │          │          │
                                         Pololu 2815 ON pin (>1 V = on) <───────┘          │          └──> Feather ARM_IN
                                         +24 V ring ─> 2815 ─> 15 A MINI ─> D24V150F12 ─> +12 V FLY (CT 1-2)
                                                          └─> 10 A MINI ──────────────────> +24 V DIAL (CT 3)
                                                                                            │
                                                     74HC14 inverter + 10 ms RC (BRAKE) <───┘ (section 3.3)
```

- Loop open, no 12 V in the base, a stuck 555, a contact shorted to +24 V or to GND, mains hum: no 1 kHz edges, so the
  monostable's Q falls within 20 ms, ARM falls, the 2815 removes +24 V from the flywheel regulator and the C610, and
  10 ms later the brake shorts the motors' phases. The MCU, the servos, the laser supply and the lights stay powered
  (they are upstream of the 2815) so the turret reports what happened.
- The Feather sees ARM but cannot raise it. Its own conditions sit on top (the ARM input high, a CAN heartbeat no
  older than 200 ms) and only ever command zero throttle when they fail.
- A bouncing ring contact drops a pulse or two (< 1 ms) and the 20 ms monostable rides through it.

### 3.2 The overspeed trip

```
 GATE_1 (LM393, edge on the ball's leading edge) ─> 74HC123 #2: one-shot, t = 2.98 ms (60 mm gates: a 66 fps ball)
                                                       Q ──────────────┐
 GATE_2 ───────────────────────────────────────────────────> 74HC74 CLK, D = Q
                                                               └─ Q_latched = TRIP ─> /TRIP into the AND (3.1)
 recessed RESET button (and power-up reset RC) ──────────────> 74HC74 /CLR
```

A ball that reaches gate 2 while the 2.98 ms window from gate 1 is still open is faster than 66 fps: the flip-flop
latches TRIP, ARM falls exactly as for a released loop, and only the recessed button or a power cycle clears it. The
window's R and C: C = 100 nF C0G 1 %, R = 66.5 k 1 % (t = K R C with K ~ 0.45 for the HC123 at 5 V); K varies part
to part, so the bench test 6.7 (simulated gate pairs at 1.33, 2.6 and 3.0 ms) sets the final R by selection, never a
trimmer. The Feather times both gates too and logs every shot's speed; it refuses to feed above 66 fps on its own.

### 3.3 The phase-short brake (on the cartridge, beside the ESCs)

Three IRLZ44N per motor (`infineon-irlz44npbf`, 6 in all) from each phase to a common star; their gates from BRAKE
through 100 R, 10 k to source. BRAKE comes from the 74HC14 on level 1: ARM through a 10 ms RC (10 k, 1 uF) and two
inverting stages, so the short closes 10 ms after the 2815 has opened (the ESC is unpowered first) and opens again
before the 2815 re-powers the ESCs on the next arm. The motor's own back-EMF drives the braking current: tau 12 ms,
5 % speed in 45 ms (docs/turret-physics.md section 5). AM32 `brake_on_stop` is set too, for every ordinary stop.

### 3.4 The chronograph gates

Each gate: a TSAL4400 940 nm emitter (`vishay-tsal4400`) on 5 V through 100 R (~35 mA) in one side of the barrel's
gate boss, a TEFT4300 phototransistor (`vishay-teft4300`) with a 4.7 k pull-up in the other, the 1 x 2 mm slit between
them (cad/turret.py `GATES`). The phototransistor drives an LM393 comparator (`ti-lm393p`, one package for both gates)
with 50 mV of hysteresis; its open-collector output (10 k to 3.3 V) goes to the Feather and to the trip logic. A
ball cuts a 1 mm beam in 47-60 us: well inside the comparator's microsecond response.

## 4. Power rails and fuses

| Rail | Where | Source | Feeds | Fuse |
|---|---|---|---|---|
| +24 V in | base | DT12 1-2 | everything | 10 A ATO (`littelfuse-0287010-pxcn`) in a PCB holder (`keystone-3557-2`) on the base board |
| 12 V PAN | base | D36V50F12 (`pololu-d36v50f12-4095`) | the pan STS3215 (2.7 A stall); the 78L05 and the 555 | 3 A polyfuse (`bourns-mf-r300`) |
| +24 V ring | turret | ring P1 | the 2815 switch, the aux and logic regulators | (the base's 10 A) |
| 12 V FLY | turret level 0 | D24V150F12 (`pololu-d24v150f12-2885`) behind the 2815 | the two AM32 ESCs only | 15 A MINI (`littelfuse-0297015-wxnv`) at the regulator's input |
| +24 V DIAL | turret level 0 | behind the 2815 | the C610 only | 10 A MINI (`littelfuse-0297010-wxnv`) |
| 12 V AUX | turret level 0 | D36V50F12, upstream of the 2815 | the tilt STS3215, the laser | 3 A polyfuse |
| 5 V | turret level 1 | D36V28F5 (`pololu-d36v28f5-3782`), upstream of the 2815 | the Feather (USB/VBUS), the bus buffer, the hall, the lights, the gates | 2 A polyfuse (`bourns-mf-r200`) |
| Bank | turret level 1 | 3 x 1000 uF 35 V low ESR (`panasonic-eeu-fr1v102`) at the regulators' input | rides a 2 ms contact bounce at 11 A with 8 V droop | |

Every fuse is DC-rated (32 V blade). The 2815's own reverse-voltage protection covers a reversed supply on the motor
rails; the regulators are protected by the 15 A and 10 A blades.

## 5. Current budget (24 V side, at the ring)

From docs/turret-plan.md 2.5 and the physics' power model (docs/turret-physics.md section 9, 60 mOhm ring):

| Case | Ring peak | RMS over 1 s | Notes |
|---|---|---|---|
| Flywheel spin-up, 200 ms soft start (the default) | 2.2 A | 0.6 A | bank minimum 23.9 V |
| Flywheel spin-up, stepped at the AM32 10 A limit (never on the bench ring) | 12.0 A for 36 ms | 1.7 A | bank minimum 23.3 V |
| 8 shots at 10/s | 4.9 A | 1.2 A | 3 ms recovery pulses |
| Dial step, C610 at 10 A for ~100 ms | ~1.5 A | | 1.8 N m x 150 rpm = 28 W (physics finding 2) |
| Tilt servo move | 1.5 A | | 2.7 A stall at 12 V |
| MCU, sensors, lights, laser | 0.25 A | | |
| **Game average** | | **<= 2 A (48 W)** | inside the ring's rating with margin |

## 6. What this page settles for the T2 acceptance (docs/turret-plan.md 7.1)

- Every connector is named with its part number and pinout (sections 1.1-1.5); every conductor with its gauge, length
  and strain relief (section 2).
- The CT power connector carries 10 A per rail: two 8.5 A contacts for 12 V FLY, one for 24 V DIAL at 10 A for 100 ms.
- The arm chain is pulses AND not-tripped, driving the switch and the brake, with no MCU in it (section 3).
- The 24 V cannot reach the ESC rail by a mis-plug: the 2 x 3 and the 2 x 6 cannot cross-mate, both are polarised,
  and the cartridge's harness takes 24 V to the C610 alone; the bench's 100 % throttle test (V13) proves the build.
- The budget's peaks match the physics (2.2 A ramped, 12 A stepped, 4.9 A in bursts).

Open: the boards' layouts (which part where on each perfboard) are drawn when they are built (T5); the stand's base
board (the bench's terminal board) is the 70 x 50 board in cad/turret_stand.py; the Feather's pin map is in
docs/turret-firmware.md.
