# Turret plan: the pan joint's slip ring, the electrical architecture, and the road to a built turret

Written 2026-10-27 for the turret program agent (owner of cad/turret.py and the bill of materials in the turret
worktree) and the turret physics agent (owner of sim/turret_*.py). Research behind every number:
research/turret-slip-ring.md (sources and dates). Charter and checklist: docs/turret-program.md. The user's words:
"We likely need high quality electrical slip rings for the turret, make sure you are making something we can really
build, well researched" and "Make sure you do real physics simulations of the turrets with the foam balls end to end,
make something I can actually build, get good parts from mcmaster."

Hard rules stand: the barrel never points above horizontal; muzzle speed ≤ 70 fps (21.3 m/s); nothing spins or
feeds unless the safety line is held (the pendant on the bench, the radio stop on the robot).

## 0. The decision in one paragraph

Put a Ø22 mm gold capsule slip ring on the pan axis, flange down in the base foot, driven by the turntable through a
silicone-tube coupling. Across it: 24 V on two power rings per rail, CAN on a twisted pair, the safety line as a
1 kHz pulse train on its own pair, the pan servo's TTL bus on one ring with a signal ground, and two spare rings for
a camera later. One microcontroller rides on the turret (Adafruit Feather M4 CAN Express) and drives everything that
turns; the base stays passive (fuse, the pan servo's 12 V regulator, the safety-pulse oscillator, the DT12). The
flywheels soft-start over 200 ms, which turns an 11 A spin-up pulse into 2 A at the ring, with the ESC current limit
as the backstop. Pan becomes continuous; absolute pan comes from the STS3215's own 12-bit angle plus one index
magnet in the base, homed at power-up. Buy the $27.95 SparkFun/Senring ring now for the bench and request quotes for a
2 × 10 A + 12-signal ring for the robot. The 70 fps cap is **not** a firmware number: the flywheel ESCs run from a fixed
12 V regulator, which caps the wheels at 10,437 rpm and the worst ball at 64 fps flat out (the simulator's 123 fps is
the same wheels on 24 V), and a hardware window comparator on the barrel's two chronograph gates latches the safety
line open on any ball over the cap. Releasing the line cuts the ESC and dial power and shorts the flywheel phases: the
wheels are at 5 % speed in 36 ms, before a ball already dropped (96 ms) can reach them.

## 1. Decisions that need the user (with recommendations)

| # | Decision | Options | Recommendation and why |
|---|---|---|---|
| D1 | **Continuous pan (slip ring) or ±170° with a cable loop** | (a) ring, pan without limit; (b) keep the stop post, run the harness through the Ø40 centre as a clock-spring loop | **(a)**. The user asked for it; a balancing robot that turns often should not have to unwind; it removes a flexing harness from the bore and the clash risk of a loop; it costs $28-300 and about 40 g (est: Ø22 × 40 capsule 25-35 g plus carrier). (b) stays as a fallback: the stop post and finger remain in the CAD behind a `CONTINUOUS_PAN` flag |
| D2 | **Ring tier** | C: SparkFun ROB-13065 (Senring M220-12, 12 × 2 A, $27.95, in stock); B: Senring M220-0210-12S (2 × 10 A + 12 signal) or Moflon MC330-P0308-S06 / MC3309 grade (3 × 8 A + 6 × 2 A), quote, est $60-150; A: Servotecnica SVTS A 03-S-A-04/06 (4 × 6 A + 6 × 2 A, < 10 mΩ dynamic, 10⁷ revs, US office) or Moog AC6310 (3 × 10 A + 6 × 2 A), quote, est $150-400 (Moog's plain 12 × 2 A lists at about $192) | **Buy C now** for the bench (it carries the turret once the soft start is in: 2 A pulses on 4 + 4 paralleled rings) and **request quotes for B and A in parallel**. For the robot take the **Senring M220-0210-12S** if ≤ $120 and the **Servotecnica 04/06** if the user wants the specified dynamic resistance and US support; all three share the Ø22 / Ø44 flange envelope, so the carrier is a per-model print, nothing else changes |
| D3 | **Turret controller** | Adafruit Feather M4 CAN Express (SAME51, CAN transceiver and 5 V boost on board, $24.95, in stock) vs the robot's WeAct STM32G474 core + SN65HVD230 module (catalog) | **Feather M4 CAN** for the bench and the first robot: one board, no soldering of a transceiver, 16 PWM, 6 ADC, 3.3 V logic. The G474 stays the choice if the firmware team wants one toolchain with the balance controller; the pin map in section 2 fits both |
| D4 | **Where the pan servo is driven from** | (A) the turret MCU's servo bus crosses the ring on one TTL ring; (B) a second CAN node in the base drives the pan servo | **(A)**: one firmware, one CAN node, a checksummed protocol with retries on the one crossing line; a bus fault leaves the servo holding position (safe). (B) is the upgrade if the TTL-over-ring test (section 6) shows errors |
| D5 | **Flywheel rail regulator** (the physics design runs the flywheel ESCs from a 12 V regulated rail for the velocity ceiling) | one Pololu D24V150F12 (15 A, 40 V in, $79.95, rationed) or the newer D42V110F12 (6-16 A, 60 V in, $69.95; 12 V SKU to confirm on Pololu) shared by both ESCs; or one D36V50F12 (4.5 A, $39.95) per ESC as a hardware current ceiling | **One shared 15 A-class regulator** with the AM32 limit at 10 A and the 200 ms ramp. Per-ESC 4.5 A regulators give a hard ceiling but their overload behaviour (droop) can brown out an ESC mid-spin-up; test before adopting |
| D6 | **Camera provision** | reserve 2 signal rings as a pair now; or buy a USB-rated capsule later; or a Wi-Fi camera on the turret | **Reserve the pair now** (it costs nothing on a 12-signal ring). Decide the camera later |
| D7 | **What the safety line stops** | flywheels and dial only (the hard rule) vs all motion | **Flywheels and dial off in hardware; pan and tilt stay live but the firmware caps pan at the 100 deg/s people-near limit while disarmed**, so the turret can park and point without ever spinning or feeding |
| D8 | **Quotes** | The agents must not contact vendors (Gyropup is private) | The user sends the quote requests from section 5.2 (text provided) or approves the agent doing so |
| D9 | **How the safety line brakes the flywheels** | (a) a phase-short brake: three logic-level MOSFETs across the motor phases, closed by hardware 10 ms after the ESC power drops; (b) AM32 brake-on-stop, with the hardware chain forcing a zero-throttle pulse train into the ESCs and keeping them powered for 1 s; (c) both | **(c)**: AM32 brake-on-stop for every normal stop from firmware, and the phase-short as the release brake, because it needs no ESC firmware, no signal source and no power to work (section 2.11): τ = 12 ms, 5 % speed in 36 ms (calc) |
| D10 | **The independent overspeed cut-out** | (a) a hardware window comparator on the two chronograph gates that latches the safety line open on any ball faster than 66 fps; (b) a wheel-speed trip (frequency-to-voltage on one motor phase, LM2917 class); (c) firmware only | **(a)** now (6 logic parts, it measures the ball itself, it also covers a wrong regulator), with the firmware's own per-shot speed check and RPM-telemetry lockout on top; (b) only if the physics agent wants a cut before the first fast ball (section 2.10) |

## 2. The electrical architecture across the pan joint

### 2.1 What crosses the ring, and what does not

| Crosses | Stays in the base | Stays on the turret |
|---|---|---|
| +24 V (fused), GND | DT12 receptacle, 10 A blade fuse, the pan servo with its 12 V regulator, the safety-pulse oscillator, the index magnet | the Feather MCU, the 24→12 V flywheel regulator and its capacitor bank, the 24→12 V aux regulator (tilt servo, laser), the flywheel ESCs and C610 (on the cartridge), the tilt servo, the laser, the lights, the chronograph gates, the hopper sensor, the hall index sensor |
| CAN_H, CAN_L (one twisted pair) | | |
| SAFETY+ / SAFETY− (the pulse loop, its own pair) | | |
| SERVO_TTL + SIG_GND (the pan servo's bus) | | |
| CAM+ / CAM− (reserved, a pair) | | |

Ten rings in all: two power, six signal in use, two signal reserved. Everything with a motor driver except the pan
servo rides on the turret, so the ring sees one power rail and three low-current signals, and the count never grows
with features.

### 2.2 Ring pin map (for a 2 × 10 A + 12-signal ring; the 12 × 2 A bench ring in brackets)

| Ring(s) | Signal | Lead on the ring | Notes |
|---|---|---|---|
| P1 | +24 V | 17 AWG (power ring) [bench: rings 1-4 paralleled, 28 AWG] | from the base fuse |
| P2 | GND | 17 AWG [bench: rings 5-8 paralleled] | the only power return |
| S1, S2 | CAN_H, CAN_L | 26 AWG, **adjacent rings**, twisted on both sides | 120 Ω at the turret node; the other at the Jetson / CANable end |
| S3, S4 | SAFETY+, SAFETY− | 26 AWG, adjacent | 1 kHz pulse loop into an opto-coupler on the turret (2.8) |
| S5 | SERVO_TTL | 26 AWG | the Feetech half-duplex line to the pan servo |
| S6 | SIG_GND | 26 AWG | tied to GND on the turret board only; the TTL and pulse reference |
| S7, S8 | CAM+, CAM− | 26 AWG, adjacent | reserved; unconnected both ends, tied to GND through 100 kΩ |
| S9-S12 | spare | | [bench: 9-12 are the signals above, so the bench ring has no spares] |

Bench ring (12 × 2 A): rings 1-4 +24 V, 5-8 GND, 9 CAN_H, 10 CAN_L, 11 SAFETY+, 12 SAFETY−; SERVO_TTL and SIG_GND are
then not available, so on the bench the pan servo is driven from the Feather through a 2-wire loop **outside** the ring
(it only matters for the full 360° test: run that with the Tier B/A ring). Alternative bench map if TTL must cross:
1-3 +24 V, 4-6 GND, 7-8 CAN, 9-10 safety, 11 TTL, 12 SIG_GND, with the spin-up ramp mandatory (2.1 A peak on 3 × 2 A).

### 2.3 DT12 pinout (TE DT04-12PA-L012 receptacle on the base, DT06-12SA plug on the robot / stand harness)

Size 16 contacts, 13 A each (TE). Pins 1-2 +24 V (paralleled, 16 AWG each), 3-4 GND, 5 CAN_H, 6 CAN_L, 7 SAFETY_A,
8 SAFETY_B (the dry loop from the pendant or the radio stop: closed = run), 9-10 spare (a second CAN or USB pair for a
camera), 11 LINE_SENSE (24 V present on the stand, for the lights; optional), 12 spare. The stand's pendant jack goes
to 7-8; the robot's radio stop output (designed separately) will too. Twisted pairs for 5-6 and 7-8 in the harness.

### 2.4 Power rails

| Rail | Source | Feeds | Fuse | Part |
|---|---|---|---|---|
| 24 V in | DT12 → base | everything | 10 A ATO blade in the base, 32 V DC type | holder and fuse: McMaster (section 5) |
| 12 V pan (base) | Pololu D36V50F12 (13.3-50 V in, 4.5 A typ) | STS3215 pan servo (2.7 A stall) | 3 A polyfuse or 3 A blade | Pololu 4095, $39.95 |
| *(the three rails above are in the base; those below are on the turret, fed by the ring)* | | | | |
| 12 V flywheel (turret) | Pololu D24V150F12 (15 A) or D42V110F12 | 2 × AM32 ESC → Snail 2305 (10 A limit each) | 15 A mini blade at the regulator input | Pololu 2885 $79.95 / D42V110F12 $69.95 |
| 24 V dial (turret) | straight from the ring, through the safety switch | C610 → M2006 (10 A max) | 10 A mini blade | |
| 12 V aux (turret) | Pololu D36V50F12 | tilt STS3215 (2.7 A stall), laser (20 mA at 12-24 V) | 3 A polyfuse | Pololu 4095, $39.95 |
| 5 V logic (turret) | Pololu D36V28F5 class or the aux regulator → a 5 V buck (2-4 A family, $23.95-24.95; exact 5 V SKU to confirm) | Feather (USB/VBUS pin), servo-bus buffer, hall sensor, WS2812 lights (0.5 A), chronograph gates | 2 A polyfuse | |

The **safety switch** (Pololu 2815, 16 A, ON pin) sits between the ring's +24 V and the two motor rails (flywheel
regulator input and the C610), so with the line open the ESCs and the C610 have no power at all; the MCU, the servos,
the laser and the lights stay up. The aux and logic rails are upstream of the switch.

### 2.5 Current budget (data sheets and the launch model; research §11-12)

| Load | Continuous (game average) | Peak | Duration | Control |
|---|---|---|---|---|
| Flywheels, 2 × Snail 2305 on the 12 V rail | 0.36 A (idle at speed) + 0.3 A (10 shots/s recovery) at 24 V | **11.1 A at 24 V** stepped with a 10 A limit; **2.1 A** with the 200 ms ramp | 40 ms / 200 ms | AM32 `limits.current` = 10 A (verify on the bench), firmware ramp, regulator ~32 A instantaneous limit |
| Dial, M2006 + C610 at 24 V | 0.3-1 A while feeding (est: 1 N·m is 5.6 A; a 45° dial step needs far less) | 3 A step cap, 5 A jam threshold, 10 A C610 hard max | ≤ 0.5 s (jam timeout) | firmware current command; never during spin-up |
| Tilt STS3215 at 12 V | 0.3 A at 24 V (est) | 2.7 A stall → 1.5 A at 24 V | moves of 0.25 s | protection current register 28 |
| Pan STS3215 (base, not through the ring) | | 2.7 A stall at 12 V | | torque limit 50 % (cad/turret_motion.py: gear SF) |
| Laser | 0.02 A | | | GPIO |
| Lights, MCU, sensors | 0.25 A at 24 V (est) | | | |
| **Ring total** | **≤ 2 A at 24 V** (≤ 48 W, inside the 40 W average with the lights dimmed) | **≤ 13 A for 50 ms** worst case (stepped spin-up + a tilt move); **≤ 5 A** as flown (ramp + dial cap) | | |

### 2.6 Holding the peaks inside the ring's rating

1. **Soft spin-up:** the set speed ramps 0 → 9,408 rpm over 200 ms (firmware, then AM32's own `max_ramp` as a second
   limiter): 2.1 A at the ring instead of 11.1 A (research §12). The warning laser is on for 0.35 s before the first
   shot, so the ramp adds no delay.
2. **ESC current limit** at 10 A per motor (AM32 `limits.current`; the 2025 firmware makes it a PID loop; measure it).
3. **Regulator** between the ring and the ESCs: 24 V in, 12 V out, so the ring current is about half the ESC current.
4. **Sequencing:** the dial never steps while the wheels are below 95 % of set speed; a jam retry waits for the
   wheels.
5. **Capacitor bank** on the turret at the regulators' input: 3 × 1,000 µF / 35 V low-ESR (2,750 µF rides through a
   2 ms contact bounce at 11 A with 8 V droop; the regulators run down to 13.3 V), plus the regulators' own ceramics.
6. **Power rings**: two per rail at ≥ 8 A on the robot ring; four paralleled 2 A rings per rail on the bench ring
   with the ramp mandatory.

### 2.7 Signal integrity, grounding, shielding, EMI

- **CAN** at 1 Mbit/s classic (the Feather's transceiver; CAN-FD later if the J501 port wants it): the pair on
  adjacent rings, twisted on both sides of the ring, 120 Ω at the turret node and at the far end (CANable on the
  bench, the J501 port on the robot); no stub in the base (the base has no node). The ring's contact variation
  (≤ 60 mΩ) is nothing against 120 Ω. A bouncing contact makes bit errors, which the controller counts (TEC/REC) and
  retransmits; the firmware publishes both counters and the bus-off count every second.
- **Servo TTL** (5 V logic, 1 Mbit/s default; set the bus to 500 kbit/s or 115.2 kbit/s for margin): the Feetech
  protocol has a checksum and the master retries; the line is referenced to SIG_GND (its own ring), which the turret
  ties to GND at one point, so the power return's drop (≤ 0.1 V at 11 A on 10 mΩ) does not appear on the TTL
  reference. A 74AHCT125 buffer drives the half-duplex line from the Feather's UART (direction from a GPIO) with
  4.7 kΩ pull-up to 5 V.
- **Grounding:** one return path (the GND power rings). No chassis ground: the printed turret is an insulator; the
  base's aluminium parts (bearing, circlip) float.
- **EMI:** the flywheel ESCs' switching ripple is filtered on the turret by the capacitor bank and the regulators; the
  ring carries near-DC. Keep the power pair and the signal bundle on opposite sides of the Ø40 bore, twisted
  separately; ask the ring vendor to place the power rings at the flange end and the CAN pair adjacent (vendors do
  this on request; Moflon and Senring sheets).
- **Lead dress:** rotor leads strain-relieved on the driver disc, stator leads on the carrier, within 30 mm of the
  connectors (docs/mechanical-interfaces.md rule 5).

### 2.8 The safety line across the ring, failing safe on a bouncing contact

Static levels cannot be trusted through a contact that may bounce, short to +24 V or to GND. The line is therefore a
**dynamic signal**: the arm state exists only while pulses keep arriving.

- **Base:** the pendant / radio-stop loop (DT12 pins 7-8) powers an NE555 astable (1 kHz, 50 %) from the base 12 V
  through a 78L05; its output drives the ring's SAFETY pair through 2.2 kΩ (10 mA loop). Loop open → no oscillator
  power → no pulses. A stuck 555 output (DC) gives no edges either.
- **Turret:** the pair drives an opto-coupler LED (e.g. Vishay 4N35 class) with a series 2.2 kΩ / 1 W (a short to
  24 V cannot exceed 11 mA); the opto's output clocks a **retriggerable monostable** (74HC123, t = 20 ms). Its Q
  output drives the Pololu 2815's ON pin (> 1 V = on) and an MCU input. Missing pulses for 20 ms → Q falls → the
  flywheel and dial rails lose power within the switch's turn-off time; the ESCs coast, the dial stops on its gearbox
  friction (the feed sim's parked case covers this). A bouncing ring contact drops a few pulses in 1 ms and retriggers
  within the next ms; a real break trips in 20 ms.
- **The TRIP latch** (2.10) is ANDed with the monostable's output: pulses present AND no trip = armed. It also drives
  the phase brake's inverter, so a trip brakes the wheels like a release.
- **Firmware** also requires the ARM input high and a live CAN heartbeat (≤ 200 ms old) before any spin command, and
  commands zero throttle when either is lost; the MCU cannot arm the hardware chain by itself.
- **Fault tests** (section 6.5): open, short to GND, short to +24 V, 50 Hz hum coupled, a DC level, and a 300 Hz /
  3 kHz pulse train must all leave the rails off; only the 1 kHz train arms. Pololu's own note that the 2815 is not an
  emergency cutoff is why the robot's radio stop (designed separately) cuts the head rail upstream as well.

### 2.9 Fusing

Base: 10 A ATO blade (main). Turret: 15 A mini blade (flywheel regulator input), 10 A mini blade (C610), 3 A polyfuse
(12 V aux), 2 A polyfuse (5 V logic), 3 A polyfuse (base 12 V pan). All DC-rated (32 V) parts; the spin-up pulse
(11 A, 40 ms) is far below any 10-15 A blade's I²t.

### 2.10 The hardware speed ceiling and the independent overspeed cut-out

The simulator's breakdown (main cc58794) is right that a throttle number in firmware is no cap: the Ø36 wheels at the
Snail's 21,000 rpm no-load speed on 24 V have a surface speed of 39.6 m/s and would throw about 123 fps (calc, with
the launch model's 0.945 speed ratio). Two independent layers replace the firmware number:

1. **The ceiling is physical: the ESC rail voltage.** The flywheel ESCs are fed only by the fixed 12 V regulator (2.4):
   no-load 10,437 rpm, 19.7 m/s surface speed, and the launch model's worst ball flat out at 64.2 fps with a +5 % motor
   and a +4 % regulator (research §12; V1). An ESC cannot exceed its rail. Build rules that keep it so: the regulator is
   a fixed-output part (no trim pot); the CT connector's flywheel-rail pins carry 12 V only and are keyed apart from the
   24 V dial pins; the 24 V never reaches the cartridge's ESC side; the bench test V13 runs the wheels at 100 % throttle
   and measures. The firmware's set speed (55 fps) and its per-shot chronograph check (lockout above 66 fps, S2 of
   research/turret-launcher-study.md) sit under that ceiling.
2. **The cut-out measures the ball.** The barrel's two IR gates, 50 mm apart, feed a hardware window comparator: gate 1
   starts a 74HC123 one-shot of 2.49 ms (the time a ball at 66 fps takes; 70 fps is 2.34 ms, 123 fps 1.33 ms, calc for
   50 mm: scale with the printed spacing); gate 2 clocks a 74HC74 flip-flop whose D input is the one-shot's Q. A ball
   faster than 66 fps arrives while Q is still high, the flip-flop sets and **TRIP** latches: it is ANDed into the arm
   chain ahead of the monostable (2.8), so the flywheel and dial rails drop and the phase brake closes, and nothing
   re-arms until a recessed reset button (or a power cycle) clears the latch. The same gate edges go to the MCU, which
   logs every shot's speed and refuses to fire above 66 fps on its own. The trip acts after one fast ball has left,
   which is why layer 1 is the ceiling and this is the backstop against a wrong regulator or wrong wheels. A
   pre-shot trip on wheel speed (an LM2917 frequency-to-voltage converter on one motor phase, 7 pole pairs:
   1,098 Hz at the set speed, 1,397 Hz at 70 fps, calc) is the option if the physics agent finds a case where one fast
   ball is not acceptable; it is not in the first build.

### 2.11 Braking the flywheels when the line is released

Unbraked, the wheels coast on their 0.18 A friction (τ ≈ 2 s by the no-load current; the simulator saw ~1.4 s to a
stop), and a ball already past the dial reaches the nip about 96 ms after the release (simulator). The release must
therefore brake faster than 96 ms:

- **Phase-short brake (hardware, on the cartridge beside the ESCs):** three logic-level N-channel MOSFETs (IRLZ44N
  class, 55 V, 47 A) tie the three phases of each motor to a star point. Their gates are driven from the turret's 5 V
  by an inverter on the ARM signal through a 10 ms RC delay: ARM falls → the Pololu switch has already removed the
  ESC's 12 V → 10 ms later the phases are shorted. The motor's own back-EMF drives the braking current (peak
  29.6 A at the set speed, falling with τ = I·R/(ke·kt) = 12 ms, calc from the Snail's 0.363 Ω and the 3.92e-6 kg·m²
  wheel): 5 % of speed at 36 ms, 1.5 % at 50 ms, nothing at 96 ms. The 1.9 J per wheel goes into the windings; the FETs
  see about 50 mJ (est). Arming re-opens the short before the switch re-powers the ESCs (the same RC, inverted, gives
  the ESCs their 12 V 10 ms after the short opens).
- **AM32 brake-on-stop** (`brake_on_stop`, `drag_brake_strength`) is configured too, so every firmware stop (end of a
  game turn, idle timeout) brakes through the ESC without the hardware brake.
- **The dropped ball:** with the wheels at < 5 % speed when it arrives, it is not launched; it rests at the nip. On the
  next arm the spin-up pulls it through early in the 200 ms ramp at low speed. The physics agent simulates this case
  (V14) so the firmware knows the ball's exit speed and can treat a re-arm with a resting ball as a logged "stray
  ball" or add a pre-spin dial reverse to pull it back (if the chute geometry allows: the sim decides).
- **Release-to-safe timeline (targets, measured in 6.8):** pulses stop → monostable out in ≤ 20 ms → switch off within
  1 ms → short closed at +10 ms → wheels at 5 % by +46 ms; dial power off with the switch; the feed stops at once.

### 2.12 The Orin box control pod (cad/turret_box.py, main cc58794)

The pod gives exactly what the DT12 pinout (2.3) expects: 24 V in on an XT60 through a rocker switch and a 5 × 20 mm
5 A slow-blow fuse to DT12 pins 1-4 by WAGO 221s, the hold-to-run pendant's dry loop on pins 7-8, and the CANable's
CAN pair on 5-6 to the J501's rear USB. Nothing in the pod changes for this plan; three notes:

- the pod's 5 A slow-blow is fine with the 200 ms ramp (2.1 A peaks, 0.5 A RMS) and still passes a stepped 11 A /
  40 ms test pulse (2.2× for 0.04 s is inside a slow-blow's curve); fit 7.5 A if stepped spin-ups are run often;
- the J501 and the turret share one 24 V supply: size it for the J501's draw plus 12 A pulses, or rely on the ramp;
- use an **isolated** USB-CAN (CANable 2.0 Pro class) so the turret's ground shift under the spin-up pulse stays out
  of the Jetson's USB ground; the CANable supplies the second 120 Ω termination.

The breakdown's other three items (antennas met at full depression in four pan sectors, a 10.6 N tip, the muzzle
3 mm over the deck's rear corner at pan 140°) are box geometry: cad/turret_lidar.py's per-pan depression table is the
same mechanism for the box's antennas, and the firmware takes whichever table is loaded for the mount in use.

## 3. Mechanical integration (for cad/turret.py)

### 3.1 Placement on the pan axis (T frame, mm, z up from the TM face)

- **Carrier** (`ring_carrier`, PA6-CF): a Ø64 × 8 disc that sits up inside the base foot's Ø65 centre opening on a
  1 mm ledge (the foot is 5 mm thick: give the opening a Ø63 ledge from z 0 to 1 so the carrier's Ø64 shoulder rests on
  it and its Ø62 body passes), held by 3 × M3 × 8 screws from below into M3 heat-set inserts in the carrier; a Ø23 bore
  for the capsule, a 3-hole pattern for the ring's flange (Ø44-44.5 flange: Senring M220A, Adafruit SRC022A "3 × Ø5",
  Servotecnica A 03 "3 × Ø5.5 on Ø35"; printed per model), slots for the stator leads towards −y (the base's cable
  window at z 5..23) and a Ø8 pass for the pan servo's lead.
- **Ring:** flange at z = 1..3.5 (in the carrier's pocket), body Ø22 up the axis to z ≈ 44 (40 mm body) or 55
  (Servotecnica 41.2 + 9 stub); the rotor stub and leads at the top, inside the pan ring's Ø40 bore (z 23..69).
- **Driver** (`ring_driver`, PA6-CF): a Ø39.4 × 6 disc press-located in the pan ring's bore at z 58..64 with a Ø8 peg
  down the axis and a Ø14 lead hole beside it; a 20 mm length of soft silicone tube (5/16 in ID) joins the peg to the
  ring's rotor stub (Ø6-8 depending on the model: the Moog/Orbex "rubber tubing" coupling). The rotor leads pass the
  driver and the yoke's Ø30 hole (z 69..77) to the turret board.
- **Clearances:** the ring body Ø22 inside the Ø40 bore leaves 9 mm radial; the circlip (reach Ø60.8 at z 34..36) and
  the pan spacer are outside the Ø23 carrier bore; nothing else occupies the axis below z = 69 (checked against
  `pan_base`, `pan_ring`, `pan_spacer`, `circlip_z`, `tilt_yoke` on 2026-10-27). The clash sweep (`clashes()`) must
  include the ring body, carrier, driver and a Ø12 lead bundle from z 44 to 80 at pans 0..350 in 10° steps.
- **Concentricity:** the ring's flange centres on the carrier bore (print the Ø23 at +0.1 mm); the carrier centres on
  the foot's opening, which is on the pan axis by construction; the turntable's bore runout against the bearing is
  under 0.2 mm (printed on the same part as the journal). The coupling tube takes the rest: the ring never carries a
  radial load (research §10).
- **Service:** the carrier screws are reachable from below through the TM Ø45 hole and the head ring's Ø60; the
  rotor leads end in a 2 × 4 Micro-Fit 3.0 at the turret board and the stator leads in another at the base board, so
  the ring is replaced from below without touching the turntable: unplug both, remove 3 screws, draw the ring and its
  rotor leads down through the bore (connector ≤ Ø30 to pass the yoke hole).
- **Stop post and finger:** behind `CONTINUOUS_PAN = True` they are not built; the software limit ±170° goes away;
  the lidar depression table (cad/turret_lidar.py) already covers −180..180.

### 3.2 Continuous pan with the 63:21 STS3215 drive: absolute position and homing

- The servo's 12-bit angle is absolute per servo turn = 120° of pan, so pan is known modulo 120° at power-up.
- **Index:** one Ø1/8 × 1/16 in neodymium disc pressed into the base's clamp ring (or a bumper tab) at pan 0, and a
  unipolar hall switch (Allegro A1120 class, 3-24 V) on a tab of the yoke bridge 2-3 mm above it, wired to the turret
  MCU. Homing at power-up: tilt to the 0° stop first (so nothing can meet the lidar), then pan at ≤ 60 deg/s in the
  direction of the nearest of the three candidate positions until the index is seen (≤ 360°, ≤ 6 s), then zero the
  turn counter. From then on the MCU counts servo wraps (position read at 50-100 Hz; 90 deg/s at the turret is
  0.75 servo turns per second, so wraps are unambiguous) and re-checks the index every pass.
- **Drive mode:** position mode with the angle limits set to 0 (Feetech multi-turn, ±7 turns of the servo = ±840° of
  pan) and the MCU re-basing the goal within the window while the turret rests, or step mode (mode 3) for relative
  moves. Either way a bus fault leaves the servo holding, never free-running. Torque limit 50 % (the printed pinion's
  Lewis safety factor: cad/turret_motion.py).
- **Rate:** 90 deg/s at the turret (servo 45 rpm / 3); the 100 deg/s people-near cap is therefore met by hardware.

### 3.3 Wiring on both sides

- **Base harness:** DT12 → fuse → (a) base board (the 555 and the 12 V pan regulator) and (b) the ring's stator
  connector; the pan servo's 3-pin lead from its pocket through the existing channel to the base board; all inside
  the housing between the foot and the DT pad; the base board sits on the foot at +x/−y under the drip skirt (a
  50 × 35 mm board; detail the bay in `pan_base`).
- **Turret harness:** ring rotor connector → turret board; the board rides on the pan frame (yoke), not the cartridge:
  a printed bay on the −y arm's outer face or behind the bridge (the +y arm carries the tilt servo); the bay stays
  inside the swept Ø172 of the bumper ring and clears the pan servo pocket at every pan (clash sweep). From the board:
  the 12 V flywheel rail and the 24 V dial rail to the cartridge through the CT interface (the "CT pogo connector
  pair" in `NOT_MODELLED_G` must become a connector rated for the 10 A pulses, e.g. Micro-Fit 3.0 at 8.5 A per
  contact with two contacts per rail, or an XT30 plus a signal connector), ESC signals, CAN to the C610, the
  chronograph gates and the hopper sensor; the tilt servo lead on the +y arm; the laser lead to the cradle crossing
  the tilt axis as a 40 mm loop.
- **Lead rules:** power pair 16-18 AWG silicone from the ring to the board (≤ 150 mm), 18 AWG to the cartridge;
  signals 24-26 AWG twisted pairs; strain relief at the driver disc, the yoke hole and each connector; 5 mm clearance
  at every pose (docs/mechanical-interfaces.md).

### 3.4 What changes in the TM interface

- The Ø45 cable hole is no longer needed for a harness; **keep it** as the service opening for the carrier screws and
  the ring's stator leads (nothing routes through the head ring on the robot: the DT12 carries everything).
- The base foot's Ø65 centre opening gains the carrier ledge; the base's depth, the bolt pattern, the dowels and the
  DT pad do not change. The pan base grows the base-board bay (inside its Ø144 foot).
- The head ring (`head_ring_tm`) is unchanged; on the stand, the stand's top plate is unchanged.
- Mass: ring 35 g (est, Ø22 × 40 capsule with leads), carrier and driver 12 g (est), turret board with regulators and
  capacitors 70 g (est), base board 30 g (est): update `NOT_MODELLED_G` (which already carries 50 g wiring, 15 g MCU,
  10 g buck) so the panning group stays near 1.05 kg and the whole turret under the 1.5 kg budget (1.34 kg today).

## 4. Validation: the physics claims that gate the build, and what proves each

The physics agent owns sim/turret_launch.py, sim/turret_feed.py and the end-to-end sim/turret_e2e.py (hopper → dial →
chute → flywheels → barrel → flight → target). Numbers below are the current results in the turret worktree
(exports/turret/launch/launch.json, motion.json, lidar/lidar.json, read 2026-10-27).

| # | Claim | Today | Proof before building | Proof on the bench |
|---|---|---|---|---|
| V1 | Muzzle speed ≤ 70 fps at 100 % throttle for every ball, a +5 % motor and a +4 % regulator | worst ball 64.2 fps, margin 3.6 fps (Ø36 wheels, 25 % crush, 12 V rail) | e2e sim with the regulator's real tolerance (D24V150F12 ±4 %) and the AM32 `max_ramp` | chronograph (two gates in the barrel) on 20 balls at 100 % throttle: all ≤ 70 fps |
| V2 | Set speed 55 fps ± spread | population 54.7 fps mean, SD 1.0, p99 56.2 | e2e | 50 balls at the set speed: mean 53-57, none > 60 fps |
| V3 | **Flywheel spin-up current pulse** (sizes the ring's power rings) | 11.1 A peak at 24 V for 39 ms with a stepped 10 A limit; 2.1 A with the 200 ms ramp (research §12, calc) | e2e sim adds the ESC's DC input current (duty × phase current), the regulator (efficiency, 32 A instantaneous limit) and writes the 24 V-side current trace: peak, charge, RMS over 1 s, for step and ramp | 20 mΩ shunt in the ring's +24 V lead, scope at 1 MHz: peak ≤ 3 A with the ramp, ≤ 12 A stepped; RMS ≤ 3 A |
| V4 | Burst recovery: 8 shots at 10/s stay within the speed window | 7 % speed drop per shot, recovered on the 10 A limit (launch.json burst_10_per_s) | e2e burst with the ring's series resistance (60 mΩ) and the capacitor bank | chronograph on 8-ball bursts: every shot within ±3 fps of the set speed |
| V5 | Feed: exactly one ball per 45° step at every pose and rate; nothing leaves when parked, powered or not | sim/turret_feed.py cases (tilts 0/−25, body lean ±10 pitch / ±15 roll, 5 m/s² shake 8-25 Hz, three frictions) | e2e | 100 steps at each of 4 poses with real balls: 0 misses, 0 doubles; parked shake test on the stand: 0 balls out |
| V6 | Recoil ≤ 0.05 N·s per shot | 0.031 nominal, 0.0448 at the cap with the heaviest ball | e2e reports per-shot impulse | not measured directly; the stand's clamp tabs are the proxy |
| V7 | Pan and tilt servo margins | tilt move margin 7.6, hold 70; pan 90 deg/s max, a 90° move in 1.0 s at best; pinion SF 2.15 at 50 % torque | cad/turret_motion.py stays green after the ring, boards and connectors are added to the masses | time a 90° pan and a 25° tilt with the hopper full |
| V8 | Nothing panning or tilting comes within 10 mm of the lidar or its ball path at the firmware's depression limit | lidar.json per-pan table, 181 pans | regenerate after the CAD changes | a Ø103 × 72 mock lidar on the stand; sweep pan at the limit table |
| V9 | Ring: dynamic resistance, CAN errors, temperature, life | vendor ratings (10-60 mΩ, 10⁷ revs) | none | section 6 |
| V10 | Pan homing finds the index within one turn and the sector is right | design (3.2) | firmware unit test with simulated wraps | 20 power-ups at random pans: every home within 6 s, no wrong sector |
| V11 | Safety line: release → no spin, no feed; faults never arm | design (2.8) | none | section 6.5: release-to-rail-off ≤ 25 ms; all fault injections stay disarmed |
| V12 | End to end: the turret on the stand knocks down the targets scenario's plates | sim/turret.py `targets` (5 plates at 3.0-4.2 m) | e2e sim | 5 foam plates at 3-4 m, 24 balls: ≥ 3 down |
| V13 | **The speed ceiling is physical**: on the 12 V rail the wheels cannot throw over 70 fps at 100 % throttle; the chronograph trip latches on any ball over 66 fps | 64.2 fps worst ball (launch model); 123 fps if the ESCs ever saw 24 V (simulator breakdown) | e2e at 100 % throttle on the 12 V rail with +5 % KV, +4 % V, the lightest and heaviest balls; the trip's 2.49 ms window against the sim's gate times | 20 balls at 100 % throttle: all ≤ 70 fps; trip test 6.7: a 1.3 ms simulated gate pair latches, a 2.6 ms pair does not; reset only by the button |
| V14 | **Release brakes the wheels before a dropped ball arrives**: < 5 % speed within 50 ms; the resting ball's fate on re-arm is known | τ = 12 ms phase-short (calc); 96 ms ball arrival (simulator) | e2e: release at every ms of the dial-to-nip window with the phase-short model; report the ball's end state and its exit speed on the next ramp | 6.8: release → wheels at 5 % within 50 ms (RPM telemetry and a phase bEMF trace); 20 releases during feeding: no ball leaves the muzzle above 20 fps |

## 5. Bill of materials for the pan joint and its electrics

McMaster-Carr wherever McMaster sells the part; vendor parts only for the motors, ESCs, servos and the ring.
Electronic parts McMaster does not sell are from named vendors. Prices read 2026-10-27 unless noted; "verify" means
the part number could not be opened on McMaster's site during this research (the site renders nothing to a plain
fetch) and the turret agent confirms it with tools/mcmaster_cad.py before ordering. Catalogue numbers already in
catalog/hardware.json are marked (cat).

### 5.1 The ring

| Tier | Part | Spec | Price | Buy | Lead time |
|---|---|---|---|---|---|
| C (bench, now) | SparkFun ROB-13065 (Senring M220-12 / SNM022A-12) | 12 × 2 A, Ø22 × 26.5, flange Ø44.5, 28 AWG 250 mm leads, 250 rpm, IP51 | $27.95 | sparkfun.com, Digi-Key (21 in stock), RobotShop | stock |
| C alt | Adafruit 1196 (Prosper SRC022A-12) | 12 × 2 A, Ø22, flange Ø44, 28 AWG 6 in leads | $19.95 | adafruit.com (6 in stock) | stock |
| B | Senring M220-0210-12S | 2 × 10 A (17 AWG) + 12 signal (26 AWG), Ø22 × 40, 150 rpm, IP51 | quote (est $60-120, basis: the 12 × 2 A at $28 retail and Moflon's class) | sales@senring.com | est 2-3 weeks DHL |
| B alt | Moflon MC330-P0308-S06, or MC3309 grade | 3 × 8 A + 6 × 2 A, Ø22 × 33, 250 rpm, 10 mΩ (4 mΩ for MC3309), > 10 M revs (20 M) | quote (est $70-150) | sales@moflon.com | "standard models in stock", est 2-3 weeks |
| A | Servotecnica SVTS A 03-S-A-04/06 | 4 × 6 A + 6 × 2 A, Ø22 × 41.2, flange Ø44, < 10 mΩ dynamic, 10⁷ revs, 500 rpm, IP51 | quote (est $150-300) | Servotecnica USA, Fair Oaks CA, +1 925-640-7042 | est 3-6 weeks |
| A alt | Moog AC6310 | 3 × 10 A + 6 × 2 A, 1.38 in long, 60 mΩ, 250 rpm | quote (est $250-400; AC6023-12 about $192 on a distributor listing) | moog.com "Find a distributor" | "quick shipment" |

### 5.2 Quote request text (for the user to send)

"Please quote 1 piece (and 5 pieces) of [part], 2 × 10 A power rings plus 12 signal rings at 2 A, 300 mm leads, flange
on the stator, power rings at the flange end and two adjacent signal rings for a CAN pair; 24 V DC, 15 rpm, indoor
robot. Please include lead time, shipping to the US, and the STEP file."

### 5.3 Mechanical hardware (McMaster-Carr)

| Item | Qty | McMaster | Price | Note |
|---|---|---|---|---|
| Pan bearing 6810-2Z, 50 × 65 × 7 | 1 | 6656K229 (cad/turret.py) | (price not read) | the catalogue also holds 4668K273, the stainless sealed version at $194.88 (cat): use the steel shielded one |
| External retaining ring, 50 mm (DIN 471) | 1 | 98541A167 (cat) | $3.10 / 5 | under the pan spacer |
| Tilt bearing 126-2Z, 6 × 12 × 4 | 1 | 7804K112 (cat) | $8.89 | |
| Shoulder screw 6 × 12, M5 | 1 | 92981A101 (cat) | $2.82 | tilt pivot |
| Dowel pins Ø5 × 16 | 2 + 2 | 91595A352 (cat) | $0.38 each / 50 | TM and CT dowels |
| Heat-set inserts M3 | 20 | 94459A140 (cat) | $0.22 each / 50 | carrier, clamp ears, bays, bumper tabs, hall tab |
| Heat-set inserts M5 | 4 | 94459A775 (cat) | $0.27 each / 25 | head ring / stand top |
| Heat-set inserts M4 | 4 | 94459A... (verify: the M4 × 0.7 standard brass insert in the same family) | | pan ring → yoke |
| M3 × 6 socket head | 10 | 91290A111 (cat) | $0.12 each / 100 | |
| M3 × 8 socket head | 10 | 91290A113 (verify) | | carrier, boards |
| M3 × 10 and × 12 socket head | 10 + 10 | 91290A115, 91290A117 (verify) | | bays, hall tab |
| M4 × 12 socket head | 4 | 91290A... (verify) | | yoke to turntable (cad: 4 × M4 × 12) |
| M5 × 16 socket head | 4 | 91290A232 (cat) | $0.17 each / 100 | TM bolts |
| M2 × 20 and M2 × 12 socket head | 4 + 4 | (verify) | | pan servo posts, tilt servo |
| M3 oversized washers | 20 | 91116A120 (cat) | $0.05 each / 100 | under the ring flange screws (flat washers: Orbex) and the bumper tabs |
| M5 washers | 4 | 93475A240 (cat) | | |
| Neodymium disc magnet, 1/8 in dia × 1/16 in thick | 2 (1 + spare) | McMaster 5862K-series (verify the exact number; the catalogue's N42 discs) | | alternative: K&J Magnetics D21 |
| Soft silicone rubber tubing, 5/16 in ID, 1 ft | 1 | (verify: McMaster soft silicone tubing, 5/16 in ID × 7/16 in OD) | | the rotor coupling |
| Buna-N grommet for an 11/16 in hole | 2 | 9307K884 (cat) | $1.08 each / 10 | lead pass at the yoke hole and the base window |
| ATO blade fuse holder, in-line, 32 V DC, and ATO fuses 10 A | 1 + 5 | (verify: McMaster in-line fuse holders for standard blade fuses; fuses 10 A) | | base main fuse |
| Mini blade fuses 15 A and 10 A with in-line holders | 2 + 2 | (verify) | | turret motor rails |
| Silicone-insulated stranded wire 16 AWG (red, black), 18 AWG (red, black), 24 AWG (6 colours), 25 ft each | | (verify: McMaster high-temperature silicone-insulated wire) | | harnesses |
| Heat-shrink tubing assortment, 2:1 | 1 | (verify) | | |
| Nylon cable ties 100 mm and adhesive tie mounts | 100 + 20 | (verify) | | lead dress (rule 4: clips every 60 mm) |
| M3 brass standoffs, 6 mm and 10 mm, and M3 nylon screws | 8 + 8 | (verify) | | the boards in their bays |
| Rubber bumper feet Ø12.7 × 5.5 | 4 | (verify) | | the stand (cad/turret_stand.py) |
| Thumbscrew M4 (cartridge latch) | 1 | (verify) | | CT latch |

### 5.4 Electronics (not sold by McMaster)

| Item | Qty | Part | Price | Vendor |
|---|---|---|---|---|
| Turret MCU | 1 | Adafruit Feather M4 CAN Express 4759 | $24.95 | adafruit.com (in stock) |
| Flywheel rail regulator | 1 | Pololu D24V150F12 (12 V, 15 A, 40 V in) or D42V110F12 (12 V SKU to confirm) | $79.95 / $69.95 | pololu.com (rationed, backorder allowed) |
| 12 V aux regulator (turret) and 12 V pan regulator (base) | 2 | Pololu D36V50F12 | $39.95 each | pololu.com |
| 5 V logic regulator | 1 | Pololu D36V28F5 class (2-4 A family, 50 V in) | $23.95-24.95 | pololu.com (confirm the 5 V SKU) |
| Safety power switch | 1 | Pololu Big MOSFET Slide Switch HP 2815 (16 A, ON pin) | $8.49 | pololu.com |
| Capacitor bank | 3 | 1,000 µF / 35 V low-ESR electrolytic (Panasonic EEU-FR1V102 class) | est $1.50 each | Digi-Key / Mouser (verify the number) |
| Safety-pulse parts | 1 set | NE555, 78L05, 74HC123, opto-coupler 4N35 (or TLP291), 2.2 kΩ 1 W × 2, passives | est $5 | Digi-Key |
| Overspeed trip | 1 set | 74HC123 (one-shot, 2.49 ms), 74HC74 (latch), 74HC08 (AND into the arm chain), recessed reset button, passives | est $4 | Digi-Key |
| Phase-short brake | 6 + 1 | IRLZ44N class logic-level N-MOSFETs (3 per motor), 74HC14 inverter, 10 ms RC, 10 kΩ gate pull-downs; on a small board beside the ESCs | est $8 | Digi-Key |
| Chronograph gates | 2 pairs | 940 nm IR LED + fast phototransistor or PIN photodiode with an LM393 comparator per gate (rise time ≤ 20 µs; a ball at 21 m/s crosses a 1 mm beam in 48 µs) | est $6 | Digi-Key (the physics agent fixes the gate spacing and beam width) |
| Servo-bus buffer | 1 | 74AHCT125 + 4.7 kΩ | est $1 | Digi-Key |
| Hall index switch | 2 (1 + spare) | Allegro A1120LUA-T (unipolar, 3-24 V) or TI DRV5032 | est $1.50 each | Digi-Key |
| CAN termination | 2 | 120 Ω 0.25 W | | |
| Ring connectors | 2 pairs | Molex Micro-Fit 3.0, 2 × 4, receptacle + plug + crimp terminals (8.5 A per contact) | est $6 per pair | Digi-Key (verify numbers) |
| Signal connectors | | JST-XH 2.5 mm, 2-6 way, with crimps | est $5 | |
| Lights | 1 | Adafruit NeoPixel 12-LED ring (WS2812) | est $8 | adafruit.com |
| USB-CAN for the bench | 1 | CANable 2.0 Pro class (galvanically isolated) adapter (cad/turret_stand.py, cad/turret_box.py) | est $40 | |
| Chronograph gates | 2 | fast IR emitter / photodiode pairs (the physics agent specifies; the Adafruit 2167 break-beam is too slow per research/turret-and-safety.md) | est $10 | |
| Hopper-full beam | 1 | IR break-beam pair | est $4 | |

### 5.5 Motors, ESCs, servos, connector (vendor parts, catalog/turret.json unless noted)

| Item | Qty | Part | Price (2026-10-25 unless noted) | Vendor |
|---|---|---|---|---|
| Flywheel motors | 2 | DJI RoboMaster Snail 2305 | $40 each (aifitlab); $29 from the RoboMaster committee | aifitlab.com |
| Flywheel ESCs | 2 | Repeat Robotics AM32 35 A | $24.99 each | Palm Beach Bots |
| Feed motor + ESC | 1 | DJI M2006 P36 + C610 | $95 motor (aifitlab; $41 committee), C610 listed separately | aifitlab.com |
| Pan and tilt servos | 2 | Feetech STS3215 12 V (Waveshare ST3215 SKU 22414) | $21.99 each | waveshare.com |
| Aiming laser | 1 | Picotronic DD520-1-24(12x40), order no. 70121025 | (price not read; est $40-60) | picotronic.de |
| TM connector | 1 | TE DT04-12PA-L012 receptacle + DT06-12SA plug + W12S wedges + 12 × 0460-202-16141 pins + 12 × 0462-201-16141 sockets | est $25 the set | Mouser / Digi-Key (TE's own page shows "not currently available") |

Known total for the pan-joint electrics, bench tier: ring $28 + Feather $25 + regulators $160 + switch $8.50 + small
parts est $40 = about $262 (est), plus the McMaster hardware (est $60 for the new items) and the already-planned
motors, ESCs, servos and connector (about $320 at the catalogue prices).

## 6. Bench test plan

Rig: the turret on its stand (cad/turret_stand.py), the CANable on the laptop, the pendant, a 20 mΩ / 5 W shunt in
the ring's +24 V stator lead, a scope (≥ 1 MHz, two channels), a thermocouple on the ring body, a 24 V bench supply
with current limit at 15 A. The turret's own pan servo turns the ring for the functional tests (15 rpm max); a cheap
12 V gearmotor on the stand's top (driving the turntable rim by a rubber wheel) turns it for the life test.

### 6.1 Contact noise under flywheel current

1. Static: 5.0 A DC through +24 V/GND rings (the flywheels at a fixed throttle or a resistive load), measure the drop
   across the ring's power rings (stator lead to rotor lead) with the pan at 12 positions: record R per ring;
   **accept ≤ 30 mΩ per power ring** on tiers A/B (spec 10-60 mΩ) and ≤ 60 mΩ on 4 paralleled 2 A rings.
2. Dynamic: pan continuously at 15 rpm and at 2 rpm with 5 A flowing; scope the drop, 1 MHz, 10 s captures ×10;
   **accept no dropout > 100 µs and peak variation ≤ 60 mΩ** (Moog's spec class); log the histogram.
3. Spin-up pulses: 50 stepped spin-ups (ramp off, 10 A limit) and 50 ramped (200 ms) while panning at 15 rpm; capture
   the ring current and the bus voltage at the turret board; **accept peak ≤ 12 A stepped / ≤ 3 A ramped, bus never
   below 16 V at the board**, no ESC reset (RPM telemetry continuous). This is V3's bench proof.

### 6.2 CAN error counters during continuous rotation

Stream 1,000 frames/s (the turret's telemetry at 1 Mbit/s) with the pan running 15 rpm for 1 h (900 revolutions),
then 2 rpm for 1 h, both while the flywheels idle at speed and once while firing 8-ball bursts every 10 s; read
TEC/REC and the bus-off count from the Feather every second and the CANable's error frames; **accept 0 bus-off, error
frames < 1 per 10⁶ frames, no lost telemetry second**.

### 6.3 Temperature rise

5 A continuous for 1 h at 15 rpm (worst case, 2.5× the game average): thermocouple on the ring body and the carrier;
**accept ΔT ≤ 20 K** (est acceptance: the rings are rated at these currents in open air; a printed PA6-CF carrier tolerates
80 °C). Repeat at 8 A for 10 min on tiers A/B.

### 6.4 Life

100,000 revolutions at 60 rpm on the gearmotor (28 h) with 2 A flowing and CAN streaming; repeat 6.1 and 6.2 after
10,000 and 100,000 revolutions; **accept no criterion degraded by more than 2×**. (100,000 revolutions is 160 game
days at 600 revolutions a day; the rated lives are 10-20 million.)

### 6.5 Safety line faults

With the wheels armed and at speed: release the pendant (rail off ≤ 25 ms, measured at the switch output; wheels
coast; dial stops); open the SAFETY pair at the ring (same); short SAFETY+ to GND; short SAFETY+ to +24 V (the 2.2 kΩ
limits it; disarmed); inject a DC level, a 300 Hz and a 3 kHz train from a signal generator (disarmed); couple 50 Hz
hum (disarmed); replace the 1 kHz train (armed again only after the firmware's re-arm sequence). **Accept: only the
genuine 1 kHz train arms; every fault disarms within 25 ms.**

### 6.6 Servo bus over the ring (tier A/B rings)

1 h of 100 Hz position reads and writes to the pan servo at 500 kbit/s while panning; **accept checksum retries
< 0.1 % and no command lost (the servo position tracks within 2 counts).**

### 6.7 Overspeed trip

With the wheels off: feed the trip circuit simulated gate pulse pairs from a signal generator at 1.3, 2.2, 2.4, 2.6
and 3.0 ms spacing; **accept: latched at ≤ 2.4 ms, not latched at ≥ 2.6 ms, the latch survives until the reset
button, the arm chain cannot be re-armed while latched.** With the wheels on the 12 V rail at 100 % throttle: 20 balls,
all ≤ 70 fps (V13) and no trip; then with the one-shot temporarily set to 3.0 ms (a 55 fps threshold) fire 5 balls at
the set speed: the first ball trips. Never test the trip by feeding the ESCs 24 V.

### 6.8 Braking on release

Wheels at the set speed, no ball: release the pendant; scope one phase's back-EMF (through a 100:1 probe) and read the
RPM telemetry at 1 kHz; **accept: ESC rail off ≤ 21 ms after the last pulse, short closed at +10 ± 3 ms, speed ≤ 5 % by
+50 ms, FETs below 60 °C after 20 releases in 2 minutes.** Then 20 releases timed at random points of an 8-ball burst:
count balls leaving the muzzle after the release and their chronograph speeds; **accept: none above 20 fps**; record
where each resting ball ended (V14).

### 6.9 System checks (the charter's bench items)

Chronograph at 100 % throttle (V1) and at the set speed (V2), bursts (V4), the feed at four poses and the parked shake
(V5), homing 20× (V10), the mock-lidar sweep (V8), the five-plate shoot (V12). Each writes a JSON under
exports/turret/bench/ with the raw readings and the pass/fail against the numbers above.

## 7. The phased plan

### 7.1 Tasks for the turret program agent, in order, each with its acceptance check

| # | Task | Acceptance |
|---|---|---|
| T1 | **Ring in the CAD.** Add `RING = {...}` envelopes for the three candidates (Senring M220 Ø22 × 40, flange Ø44.5; Servotecnica A 03 Ø22 × 41.2 + 9 stub, flange Ø44 with 3 × Ø5.5 on Ø35; Moflon MC330 Ø22 × 33), `ring_carrier(G)`, `ring_driver(G)` and the coupling tube as bought envelopes; the carrier ledge in `pan_base`; `CONTINUOUS_PAN` removing the stop post and finger; the index magnet pocket and the hall tab; the base-board and turret-board bays; the ring and lead bundle in `bought_parts` with masses; update `NOT_MODELLED_G` | `clashes()` passes at pans 0..350 by 10° × tilts 0/−25 with the new parts; the lead bundle (Ø12) has ≥ 3 mm clearance from z 44 to 80; the carrier's screw heads are visible from below through the TM hole in a render; `cad/turret_motion.py` margins unchanged within 5 %; exports regenerated; turret.png relabelled |
| T2 | **Wiring and the harness table.** A page (docs, or a section in turret-program.md) with the ring pin map, the DT12 pinout, the CT connector change (12 V flywheel rail keyed apart from the 24 V dial rail, plus BRAKE and 5 V), every conductor's gauge and length, the safety-pulse, trip-latch and phase-brake schematics (2.8, 2.10, 2.11), the chronograph gate circuit, the fuse list, and the current budget table tied to section 2.5 | every connector and conductor named; the CT connector carries 10 A per rail; the schematic shows the arm chain (pulses AND not-tripped → switch and brake) with no MCU in it; the 24 V cannot reach the ESC rail by any mis-plug; the budget's peaks match research §12 |
| T3 | **The bench kit list and the quote texts.** Catalogue entries (catalog/turret.json) for the ring, the Feather, the regulators, the switch, the hall sensor, the magnets, the McMaster items with verified numbers (tools/mcmaster_cad.py, one at a time) | every row has a part number, price and date; the McMaster "verify" flags in section 5.3 cleared or replaced; the three quote requests ready for the user to send |
| T4 | **Firmware plan and the bench harness.** The Feather pin map, the homing routine (3.2), the soft spin-up and sequencing (2.6), the arm logic (2.8), the CAN message set (commands, telemetry with TEC/REC and the ring-drop counter) agreed with the simulator's turret interface; the stand's base board drawn | a written message set; a simulated homing test passes 1,000 random starts; the stand build updated (cad/build_turret.py bom.json shows the new parts) |
| T5 | **Build and test the pan joint first.** Print the carrier, driver and bays; fit the tier C ring; run 6.1-6.3, 6.5, 6.7 and 6.8 with the flywheels on the stand; then 6.9 | the JSON results under exports/turret/bench/ meet the acceptance numbers; the charter's checklist items ticked with links |
| T6 | Fit the tier A/B ring when it arrives; run 6.1, 6.2, 6.6; life test 6.4 in the background | as above; the ring choice recorded in decisions.yaml |
| T7 | Manual firing on the Orin box (the user's compute box carries the turret on the TM pattern with the stand's base electronics): CAN from the Jetson's port, the pendant held | 24 balls fired on command, chronograph logged, no fault |

### 7.2 For the turret physics agent

- Add to sim/turret_e2e.py the ESC DC-side current (duty × phase current), the 12 V regulator (efficiency 90 %,
  instantaneous limit 32 A, dropout at 13.3 V), the ring's series resistance (10 and 60 mΩ cases) and the 3 × 1,000 µF
  bank; output the 24 V-side current trace for a stepped and a 200 ms-ramped spin-up and an 8-shot burst (peak,
  charge, RMS over 1 s), so V3 is proven in simulation before the shunt measurement.
- Keep the velocity-ceiling study (V1) on the D24V150F12's ±4 % and report the ceiling with the ramp active (the
  ramp cannot raise it); add the 24 V-on-the-ESC fault case so V13's 123 fps figure and the trip's gate times are
  in the same JSON as the normal ceiling.
- Model the release: the phase-short brake (τ = 12 ms from the motor constants; check it against the model's own
  wheel inertia and resistance) and a ball released at every millisecond of the dial-to-nip window; report the
  ball's resting place and its exit speed on the next 200 ms ramp (V14), and whether a short dial reverse before the
  spin-up can pull it back.
- Fix the chronograph gate spacing and beam width for the barrel (the trip window scales with the spacing; a 1 mm
  beam is crossed in 48 µs at 21 m/s).
- The e2e ball chain (hopper → target) stays the gate for V5 and V12.

### 7.3 Risks

| Risk | Likelihood / effect | Mitigation |
|---|---|---|
| AM32's current limit does not limit (reported unreliable before the 2025 PID loop) | medium / the stepped spin-up pulse reaches the regulator's 32 A limit and the ring sees 20 A | the 200 ms ramp is the primary limit; verify the limit with the shunt (6.1.3) on the first spin-up; the 15 A fuse protects the wiring; per-ESC 4.5 A regulators as the fallback (D5) |
| Cheap ring contacts bounce under the pulse → CAN errors or ESC resets | medium on tier C / low on A/B | the capacitor bank (2 ms ride-through), the CAN error counters in telemetry, the tier A/B purchase |
| Pan homing wrong sector → the depression table misapplied near the lidar | low / the barrel could meet the lidar at depression | home with tilt at 0 first; the index check every pass; plausibility check of servo wraps; the lidar table is pan-periodic anyway |
| Safety switch (Pololu 2815) not a rated safety device | — | it is one layer: the radio stop cuts the head rail upstream; the firmware disarms; fault tests 6.5 |
| Regulator availability (Pololu "rationed") | medium / schedule | order early; the D42V110F12 alternative; a 12 V 15 A industrial buck as a last resort |
| Servotecnica/Moog lead time and price | medium / schedule, budget | tier C builds the bench now; tier B (Senring/Moflon) is the cost-effective robot ring if A is slow |
| The CT pogo interface cannot carry 10 A pulses | high if left as pogo pins | change to Micro-Fit 3.0 or XT30 + signal connector (T2) |
| 24 V reaches the flywheel ESCs (wrong regulator, mis-plug, a bench shortcut) → 123 fps | low / severe | the fixed 12 V regulator and keyed CT pins (2.10); the chronograph trip latches on the first fast ball; V13 measured at every build; the bench rule in 6.7 |
| AM32 brake-on-stop does not brake on a power cut, or brakes too weakly | medium / a dropped ball fires after release | the phase-short brake does not depend on the ESC (2.11); 6.8 measures 5 % speed within 50 ms |
| A resting ball fires at low speed on re-arm | medium / a shot without a command, under 20 fps (est) | V14 sim and the firmware's stray-ball handling; a dial reverse before spin-up if the chute allows |
| Printed carrier concentricity or a hard-mounted rotor loads the ring's bearings | low with the tube coupling | the coupling tube; "turns freely before tightening" check at assembly (Moflon) |
| Heat in the base: the pan servo regulator and the 555 under the drip skirt | low | the foot windows ventilate; the thermocouple test 6.3 includes the base board |
| The 12 × 2 A bench ring's 28 AWG leads at 11 A if the ramp is off | medium on the bench | the ramp is enforced in firmware before the first spin-up; the 10 A fuse and the lab supply's 15 A limit |

### 7.4 What the user decides now

D1 (continuous pan), D2 (order tier C now, quotes for B and A), D3 (Feather), D4 (option A), D5 (one 15 A-class
regulator), D6 (reserve the pair), D7 (flywheels and dial off, pan capped), D8 (who sends the quotes), D9 (phase-short
brake plus AM32 brake-on-stop), D10 (the chronograph trip latch). With D1, D2 and D8 answered, T1-T3 start
immediately; T5 needs the tier C ring and the Pololu parts in hand (about a week).
