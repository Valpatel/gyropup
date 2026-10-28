# Turret firmware plan

The turret's controller is an Adafruit Feather M4 CAN Express (SAME51) on level 2 of the turret bay. This page covers
what its firmware does and how it talks to the robot (docs/turret-plan.md task T4, docs/turret-prototype-plan.md task
T7): the pin map, the states, pan homing on continuous rotation, the flywheels and the feed, the aiming rules the
physics asks for, the CAN message set, and the bench harness. The hardware arm chain (docs/turret-wiring.md section 3)
sits under all of it. The firmware can stop the turret, never start it on its own.

The reference implementation is pure Python in `firmware/turret/`, and the Feather port follows it line for line:

| File | What it is |
|---|---|
| `config.py` | every number on this page: the build constants (KV, pole pairs, the eRPM limit, the feed's timings) and the runtime CONFIG the host may set within limits |
| `turret_fw.py` | the firmware: states, safety gates, homing, aim, bursts, bench commands, telemetry; one `tick()` a millisecond against a `HAL` |
| `homing.py` | pan homing and turn counting (unchanged since T4) |
| `feed.py` | the dial: the bus port, the driver (step, settle, jam, reverse, retry, dither, drop-off and re-init) and the gate-paced burst |
| `flywheel.py` | set speed, the 300 ms ramp, the bounded trim, READY, the eRPM guard (the pre-feed check) |
| `sts.py`, `dshot.py`, `can_msgs.py` | the STS3215 protocol, bidirectional DShot with eRPM/EDT telemetry, the CAN set |
| `sim_servo.py`, `sim_turret.py` | the simulated servo and turret the tests run against (not firmware) |
| `test_homing.py`, `test_feed.py`, `test_firmware.py` | the proofs (section 8) |
| `bench_host.py` | the host that runs the bench tests on the turret or on the simulation (section 7) |
| `am32_settings.md` | the AM32 configurator settings for the two flywheel ESCs |

## 0. What changed for v0 (2026-10-27)

v0 is the turret as drawn, with the slip ring, continuous pan and the pulse-train safety line, plus three swaps for
availability (docs/turret-prototype-plan.md section 0). For the firmware:

- **Feed.** The DJI M2006 + C610 are gone. A third STS3215 (bus ID 3) steps the dial 45 deg (512 counts) on the same
  servo bus. Its power is 12 V FLY, the switched rail, so it leaves the bus on every release and is
  re-initialised when it answers again. Its rate is paced on gate 1 (section 5), at most 3 balls/s; the feed rerun
  rules out 4/s. The C610's CAN frames (0x200/0x201) and the 24 V dial rail have gone with it.
- **Flywheels.** Two SunnySky X2216 880 KV (7 pole pairs) run on AM32 ESCs on the fixed 12 V rail, with Ø34 tyres
  only. 52 fps is 8,855 rpm (61,985 eRPM). The pre-feed check is eRPM <= 1.10 x 880 x 12 V x 7 = 81,312. The
  ramp is 300 ms (200 ms put 3.56 A on the ring's pair). The AM32 settings are in `am32_settings.md`.
- **Servo bus.** Three IDs share it at 500 kbit/s. The pan and the feed run in step mode (each move a relative step
  from the absolute angle) instead of multi-turn position mode with re-basing (section 3, item 6).
- **Safety line.** The hardware is as drawn. On top of it the firmware now judges the train's frequency on PULSE_MON
  and treats a 4 ms gap as a release, zeroing the throttle ~16 ms before the monostable cuts the rail. Arming needs
  the host's request after the line is held (the re-arm, section 2).
- **CAN.** POSE now fits classic CAN's 8 bytes, a new 0x317 EVENT frame carries per-event data, COMMAND gains bench
  codes, and the fields of CONFIG, FIRE, FEED and POWER are pinned down (section 6).
- **Not fitted in v0.** The hopper-full beam (A2) and the NeoPixel ring (SDA) come in v1.
- **Inputs.** Every input pin runs with the SAMD51's own pull-ups and pull-downs off (the boards have theirs); ARM_IN and
  PULSE_MON come through 100 k, so the Feather cannot drive the arm chain even if a pin is set wrong
  (docs/turret-wiring.md 3.1, 3.5).
- **Homing** is unchanged.

## 1. Pin map (Feather M4 CAN Express)

| Pin | Use | Notes |
|---|---|---|
| D0 / D1 (Serial1) | the Feetech servo bus: pan (ID 1) in the base across ring circuit 9, tilt (ID 2) on the +y arm, feed (ID 3) through CT signal pin 3 | half-duplex: TX through the 74AHCT125, RX through a Schottky with a 10 k pull-up (it echoes TX); 500 kbit/s (margin over the ring) |
| D4 | SERVO_DIR | the buffer's direction |
| D5, D6 | ESC_L, ESC_R | bidirectional DShot300 (timer channels), eRPM and EDT telemetry back on the same pin; held low (no frames) while ARM_IN is low, so nothing feeds an unpowered ESC |
| D9, D10 | GATE_1, GATE_2 | the chronograph comparators; interrupts (EXTINT 3, 4) with microsecond timestamps |
| D11 | PAN_INDEX | the hall switch (A1120, open drain, pull-up to 3.3 V); interrupt (EXTINT 5) on both edges |
| D12 | ARM_IN | the arm chain's output through 100 k (read only; interrupt EXTINT 6) |
| A1 | TRIP_IN | the trip latch (read only), **polled**: A1 shares EXTINT 5 with D11 |
| A3 | PULSE_MON | the 4N35's output through 100 k: interrupt (EXTINT 9) on falling edges (the opto turning on: the fast edge); the train's period (0.85-1.15 ms), the release, the ring-drop counter. Not A4: A4 shares EXTINT 4 with D10 |
| A5 | LASER_EN | through the 2N7000 (Quarton VLM-650-03 LPT, Class 2); not D13, which also lights the red LED and which the bootloader pulses on a reset (the laser would flash) |
| A2 | HOPPER_BEAM | v1 (not fitted in v0) |
| SDA | NEOPIXEL | v1 (not fitted in v0); SCL spare |
| A0 | BUS_V | BUS (the XT30's 12-54 V, D66) through R20 182 k / R21 10 k (19.2 : 1: 0.78 V at 15 V, 2.81 V at 54 V); it sets the supply profile (section 4, D70) |
| CAN (on-board transceiver) | the turret's CAN segment | 1 Mbit/s classic; only the turret and the host are on it now |

## 2. States

```
BOOT -> HOMING -> IDLE <-> ARMED -> SPIN_UP -> READY <-> FIRING
                    ^         |          |         |         |
                    +---- SAFE <---------+---------+---------+   (any condition lost: zero throttle, dial stopped)
                    +---- FAULT (a latched fault, or homing failed: aim only)
```

- **BOOT.** Ping the pan and tilt servos (12 V PAN and 12 V MAIN are always on). Each servo's EEPROM is read and
  verified, never written: a release can cut the feed servo mid-write, and the setup tool owns EEPROM. The pan must be
  in step mode, the tilt in position mode with angle limits that keep it at most 1 deg above level. Then the RAM
  registers are written (torque limit 50 %, acceleration, speed: at most 100 deg/s, D7) and torque is enabled. Wrong
  EEPROM latches SERVO_CONFIG and the turret stays in FAULT.
- **HOMING.** Section 3. Nothing else moves until it is done, and HOMING shows in the heartbeat. It fails after 15 s
  without the index, or past 400 deg of sweep.
- **IDLE.** Aims and holds; the laser may be on. The wheels and the dial are off, and their rails are cut anyway
  unless the hardware is armed.
- **ARMED.** Needs ARM_IN high, the 1 kHz train good on PULSE_MON, a host heartbeat no older than 200 ms, the
  host's arm request, homed, no trip and no latched fault. It also needs the re-arm: whenever ARM_IN is low the
  firmware waits, and it accepts the request only after seeing it low while the line is held. So the pendant alone
  never arms the turret, and nothing re-arms by itself after a SAFE (the plan's 6.5, "armed again only after the
  firmware's re-arm sequence").
- **SPIN_UP.** Section 4: the muzzle goes to -25 deg for the stray ball, the 300 ms ramp runs, and the barrel comes
  back to the aim. **READY.** Both wheels are within 5 % of the set speed for 50 ms. **FIRING.** Section 5.
- **SAFE.** Entered when any arming condition is lost while armed: zero throttle in the same millisecond, the dial
  stopped, the burst ended, and an EVENT with the cause and its latency. The hardware has already cut 12 V FLY and
  the feed servo and braked, or will within 25 ms. SAFE goes to IDLE once the wheels have stopped, or to FAULT if a
  latched fault remains (eRPM limit, overspeed, trip, CONFIG mismatch).
- **FAULT.** Aim only. The eRPM and overspeed latches clear on COMMAND CLEAR_FAULTS, and only with the safety line
  released. TRIP clears only with its recessed button. A homing failure clears with a successful re-home.

## 3. Pan homing and continuous pan

The pan servo's 12-bit angle covers one servo turn, 120 deg of pan through 63:21, so at power-up the pan is known
only modulo 120 deg. Reference implementation: firmware/turret/homing.py (ported line for line).

1. Tilt to the 0 deg stop first: then nothing can meet the lidar or the deck while the pan searches.
2. Sweep in +pan at 60 deg/s (the direction the index was calibrated in) until the hall's window has been crossed:
   its two edges are timestamped by the interrupt, the servo position by its reads (100 Hz), and the window's centre
   comes from interpolating the reads at the edge times. The centre sits half the switch's hysteresis past the magnet
   in a +pan sweep; the assembly calibration measured that offset in the same direction, so it cancels.
3. Zero the turn counter there: pan = (unwrapped servo counts - counts at the index) x 120 / 4096 deg. The unwrapping
   is unambiguous at 50 Hz and above (90 deg/s of pan is 270 deg/s at the servo: 5.4 deg a read at 50 Hz).
4. The gear's 0.44 deg of backlash: the tracker follows the drive's direction and adds the backlash back after a
   -pan move. Aiming ends every move in +pan (section 5), so the turntable always rests on the same flank.
5. Every later +pan pass over the index re-checks the count; more than 2 deg off asks the host for a re-home (fault
   bit REHOME, EVENT REHOME_ASKED).
6. **Drive mode (changed for v0): step mode (mode 3).** Every move is one relative step computed from the unwrapped
   angle, compensated for the read's age. Moves longer than 30,000 counts (~880 deg of pan) are chained in segments,
   so continuous pan has no window. Position mode's multi-turn window (+-7 servo turns, +-840 deg of pan) could not
   hold the bench's 10 continuous turns (test 3.5) or an hour at 15 rpm (3.8, 4.9), and moving its frame is not a
   documented RAM operation. Step mode's reference (the present position or the last goal) is checked on the bench
   first (test 3.9 on the feed servo); the code supports both. A bus fault leaves the servo holding, never
   free-running.

**Proof (task T4: 1,000 random starts).** firmware/turret/test_homing.py runs the reference against a model of the
hardware: random start and servo zero, 50-100 Hz reads with jitter and up to 3 % failures, +-1 count of noise, the
gear's backlash, a 60 ms drive lag, hall windows of +-1.5..4 deg with 0.3-1 deg hysteresis, +-50 us interrupt
jitter, and +-0.3 deg of calibration. It then runs 20 s of random moves up to +-720 deg at up to 90 deg/s with the
index re-check. Results are in exports/turret/firmware/homing.json: 1,000 of 1,000 homed, at most 6.7 s, repeatability
0.07 deg, unchanged by v0. On the simulated turret with the full firmware (test 3.5), 50 power-ups homed in at most
6.3 s, with a 0.053 deg spread of the index centre.

## 4. Flywheels

- **Set speed (D68).** It comes from CONFIG: rpm = (v_set / ratio) x 60 / (pi x D), with D the Ø38 tyre and the
  launch model's ratio 0.952, so 95 fps on Ø38 is **15,286 rpm = 107,002 eRPM**, 97 % of the trimmed rail's no-load
  speed. The band is 40-100 fps; 100 asks for more than the rail gives a Hasbro ball (97.1 fps flat out), so the
  wheels run flat out on the rail, which is the ceiling (105 fps for the fastest accepted ball). FIRE carries the ball
  speed (0 means 95); CONFIG may carry a bench-measured ratio after test 4.4.
- **Tyre.** Ø38 only (40 % crush on this cage). A CONFIG tyre row other than 38 is refused and latches
  CONFIG_MISMATCH: no arming until it is put right.
- **Control.** Throttle = a feed-forward from the throttle map (test 4.3's table in CONFIG, else the no-load model),
  plus a PI trim on each wheel's eRPM. The trim is bounded to +-8 % throttle and moves at most 0.05 % a millisecond.
  Bumpless: a trim that stepped at the ramp's end put a 3 A spike on the ring in the simulation. Bounded: a doubled
  rail cannot hide under the loop.
- **Soft spin-up: 800 ms on the bus** from zero to the set speed (open-loop bench modes likewise). The wheels hold
  19.4 J for the pair at 95 fps; 0.8 s keeps the input's peak at about 98 W. The firmware never steps: a new set speed
  while spinning ramps too. AM32's `max_ramp` and its current limit are the second and third lines
  (`am32_settings.md`).
- **The supply profile (D70).** The ramp and the burst rate follow BUS_V, the lowest reading over the last 2 s (the
  pack sags under the spin-up's own current), so the slip ring's three power pairs stay within 2 A a circuit and the
  stand's switch within its rating (docs/turret-wiring.md section 5, sim/turret_power.py):

  | BUS_V (lowest over 2 s) | Ramp | Burst rate, at most |
  |---|---|---|
  | 24 V and over (Gyropup's 10S bus, 30-41 V) | 0.8 s | 3/s (the feed's own maximum) |
  | 20.5-24 V (a full FLEXVOLT in 20 V mode) | 1.0 s | 3/s (4/s allowed) |
  | 18-20.5 V | 1.6 s | 2/s |
  | under 18 V (to 15 V, the pack empty) | 2.4 s | 1/s |

  A row holds from its voltage up; between rows the slower one applies. A pack that sags below a row mid-ramp
  stretches the ramp from where it is (its slope only falls, the current never steps), and a burst under way slows
  to the new rate; neither speeds up mid-way. An unmeasured BUS_V (under 9 V: a cut lead) takes the slowest row; over
  54 V (D66's ceiling) the firmware refuses to spin (EV_SHOT_REFUSED, reason 210). Tests: `test_firmware.py`
  `supply_*` (the table, the four rows on the simulated turret, a sag mid-ramp, unmeasured, over 54 V).
- **ESC arming.** After ARM_IN rises, the firmware sends zero throttle for 0.6 s (AM32 arms on 0.5 s), and turns on
  extended telemetry (DShot command 13) for the temperatures.
- **The pre-feed check (D68).** Every eRPM read of either wheel above **114,730 eRPM** (16,390 rpm: the no-load
  speed at which the densest accepted ball would reach ASTM F963's 2,500 J/m^2, just under the 16,496 at which the
  fastest would leave at 105 fps) counts. Three in a row (3 ms; one corrupt frame is not a fault) latch SAFE: zero
  throttle, no dial step, until CLEAR_FAULTS with the line released. With the converter bypassed (the ESCs on the
  20.5 V pack) the turret was SAFE within 100 ms of the first read over it in the simulation. A dial step also needs
  both wheels' eRPM fresher than 20 ms, under the limit and READY. With no eRPM the firmware never feeds, and spinning
  without eRPM for 200 ms is SAFE.
- **Stray ball.** Every spin-up starts with the muzzle depressed (-25 deg, or the depression table's limit). A ball
  at the gates in the ramp's first 100 ms is logged as the stray ball of the last release (~6 fps; physics section 5).
- **Stops.** Zero throttle; AM32 brakes on stop. On a release the firmware sees the 1 kHz train stop on PULSE_MON (no
  edge for 4 ms), commands zero at once, and AM32 brakes ~16 ms before the monostable cuts the rail. Then the hardware
  phase-short closes about 8 ms after ARM falls (5-14 ms; docs/turret-wiring.md 3.3): on the short alone the X2216
  slows with an effective tau of 23 ms from 15,286 rpm (18 ms at low speed; the 1400 KV's winding inductance at
  speed), 5 % speed about 80 ms after ARM falls (config.BRAKE_TAU_S). The firmware does not drive the brake.
- **Overspeed (D68).** The latch trips in hardware on a gate pair under 1.87 ms (105 fps over 60 mm); the firmware
  only reports TRIP and goes SAFE. It also times both gates for every ball, and a ball over 105 fps latches its own
  OVERSPEED SAFE.

## 5. Feeding and aiming

**The dial** (feed.py) is an STS3215 in step mode, with the pockets at absolute positions (the assembly zero +
512 k), so errors never accumulate.

- **Step.** 512 counts (45 deg) at 2,608 counts/s (4.0 rad/s, the feed rerun) with ACC 0, which leaves the
  acceleration to the 50 % torque cap. The rerun's 60 rad/s^2 is above the ACC register's top (254 x 100 counts/s^2 =
  39 rad/s^2), and at ACC 254 the step settles in ~260 ms, over the 250 ms target. Settled means within 23 counts
  (2 deg): the rerun gives 232-246 ms under load, and the simulated servo 230 ms empty and 240 ms full.
- **Jam.** A step not settled in 300 ms (scaled with the distance: a retry after a reverse travels up to 65 deg and
  gets 433 ms), or a load reading over 40 % of stall (80 % of the cap) for 60 ms after the first 40 ms. The dial then
  reverses 20 deg from where it stuck and retries the same pocket. Three jams in a row stop feeding (FEED_JAM, EVENT
  FEED_FAULT) and the dial holds; a clean step resets the count.
- **Lost replies.** A relative step is never re-sent blindly, because a lost reply can hide an applied step and a
  doubled step can drop two balls. An unacknowledged step is re-sent only if the dial has not moved 40 ms later.
- **The release.** The feed servo's 12 V FLY is cut with ARM. The firmware forgets it on ARM_IN falling (or after 5
  failed reads), pings it at 20 Hz without counting those pings as bus errors, and on its answer verifies its EEPROM
  (step mode), rewrites the RAM registers (torque limit, acceleration, speed), enables torque, and rests it where it
  stands. A step interrupted by the release is completed by the next one. EVENTs SERVO_LOST and SERVO_BACK report it.

**The burst** (feed.py `Burst`) is paced on the chronograph, because the feed rerun found balls hanging in the exit
hole through their own step at -25 deg, when panning at 90-150 deg/s and under a 15 Hz shake, and a step on top of a
hung ball releases two.

- One ball in the hole at a time. After a step, the firmware waits for GATE_1 (the ball in the barrel, ~300-330 ms
  after the command).
- With GATE_1 seen, the next step may follow, never sooner than **335 ms** after the last step's command (the
  rerun's ~235 ms step plus 100 ms with the pocket over the hole) and never faster than 3/s.
- With no GATE_1 within **400 ms** of the command, the dial does not step on. It dithers +-10 deg to free a hanging or
  bridged ball, then waits another 400 ms. The 400 ms is derived from the plan's 130 ms ball drop: a 250 ms step,
  130 ms of drop and chute and 12 ms to gate 1 make 392 ms.
- After two dithers with no ball the step counts as empty (the plan's "empty steps after the dither") and the dial
  steps on. A full step is never commanded while a ball may still be in the hole.
- Below -12 deg of tilt the second dither is preceded by a lift to level for 0.4 s, because the last balls pool on
  the baffle. The first dither alone frees a bridged or hung ball, so the lift costs time only when that fails.
- A second GATE_1 edge in one step's window is a double (SHOT flag). Four empty steps in a row end the burst:
  the hopper is empty.
- The rate is 3/s at most (RATE_MAX). With the rerun's ~1 empty pocket in 8, the simulation delivered 2.0-2.4 balls/s
  at 3/s (2.4 level, 2.2 at -25 deg, 2.05 panning), with 0 doubles in all three.

**Aiming** (unchanged rules, with the v0 details):

- **Depression table.** The most depression allowed at each pan for the mount in use: cad/turret_lidar.py's
  `firmware_table` for the robot over its lidar, the box scene for the Orin box. The firmware clamps the tilt goal to
  it, interpolating between rows and rounding toward safety. Every tilt goal is also clamped to [-25, 0] deg. A goal
  above level is clamped and counted, and the barrel never points above level. With mount robot and no table
  loaded, the firmware holds its built-in copy of the robot's table (`config.ROBOT_DEPRESSION`, made for the VLP-16
  143 mm ahead of the pan axis), so the robot is never without one; a table loaded over CAN replaces it.
- **Keep-out sectors.** Pans where the turret may aim but never fire (the operator's side on the bench and the box).
  A burst held in a keep-out for 3 s ends.
- **Settle before firing.** A dial step only when the pan rate is under 10 deg/s, the pan has been still 0.25 s after
  its last command, and pan and tilt are within 0.5 deg of the goal. The 340 ms from command to muzzle outlasts a
  moving aim (physics findings 8, 10). The bench-only burst for test 5.1's panning pose skips this rule and nothing
  else.
- **One-sided approach.** Every pan move ends in +pan by more than the backlash. A goal below the present pan, or one
  closer than 1 deg, goes 1 deg under first and comes back, unless the + flank is known engaged. homing.py's tracker
  turns its direction after 3 counts, while the turntable changes flank only after the full backlash (15 counts), so
  the firmware tracks the flank itself.
- **Laser.** On at least 0.35 s before the first shot at a target (the simulator's rule). The laser (Class 2, under
  1 mW) and the servos stay live when the safety line is released (D7); only the wheels and the dial lose power. Pan
  and tilt are capped at 100 deg/s (the pan servo tops out at 90).

## 6. CAN message set

The turret has its own CAN segment (DT12 pins 5-6, ring circuits 5-6) to the host: the Jetson's turret port on the
robot, the USB-CAN on the bench. Classic CAN at 1 Mbit/s, the 0x300 block, little-endian, at most 8 bytes a frame
(`can_msgs.py` is the definition). The C610 is gone, so the turret and the host are the only nodes.

| ID | Direction | Rate | Payload |
|---|---|---|---|
| 0x300 HOST_HEARTBEAT | host -> turret | 10 Hz | counter u8, host state u8, flags u8 (bit 0: arm request); older than 200 ms = no arm |
| 0x301 AIM | host -> turret | on change | pan goal i32 (0.01 deg, continuous), tilt goal i16 (0.01 deg; above 0 is clamped), rate limit u8 (deg/s, <= 100) |
| 0x302 FIRE | host -> turret | on request | balls u8, rate u8 (0.1/s, <= 3/s), ball speed u16 (0.1 fps; 0 = the CONFIG default, 52), request id u8 |
| 0x303 LASER | host -> turret | on change | on u8 |
| 0x304 CONFIG | host -> turret | at start | kind u8, index u8, a i16, b i16. Kinds: 1 depression row (pan 0.1 deg, min tilt 0.01 deg), 2 keep-out (from, to: 0.1 deg), 3 tyre (mm: 34 only), 4 ring type (1 = ring, must match the build), 5 mount (0 bench, 1 robot, 2 box), 6 launch ratio (x 10^4), 7 throttle map row (throttle 0.1 %, rpm), 8 clear a table |
| 0x305 COMMAND | host -> turret | rare | code u8, a u16, b u16, c u8: 1 re-home, 2 stop feeding, 3 spin down, 4 clear faults (line released only); bench codes, accepted only with CONFIG mount = bench: 0x10 dial steps alone (n, rate), 0x11 wheels at an open-loop throttle (0.1 %, hold), 0x12 balls at an open-loop throttle (throttle, balls, rate), 0x13 stream POSE (Hz, s), 0x14 wheels at the set speed (fps, hold), 0x15 a burst that does not wait for a settled aim (balls, fps, rate) |
| 0x310 TURRET_HEARTBEAT | turret -> host | 10 Hz | state u8, fault bits u16, flags u8 (ARM, TRIP, homed, pulses good, armed, re-arm wait, feed servo online, wheels ready), seq u8 |
| 0x311 POSE | turret -> host | 50 Hz (up to 1 kHz streamed) | pan i32 (0.01 deg), tilt i16 (0.01 deg), pan rate i8 (deg/s), tilt rate i8 (deg/s) |
| 0x312 WHEELS | turret -> host | 20 Hz | rpm L u16, rpm R u16, ESC temperatures u8 x 2 (EDT) |
| 0x313 SHOT | turret -> host | per shot | shot no u16, speed u16 (0.1 fps), wheel rpm u16, flags u8 (stray, over 66 fps, after a release, gate 1 only, throttle mode, double) |
| 0x314 FEED | turret -> host | 5 Hz | balls fired u16, empty steps u8, jams u8, flags u8 (hopper full [v1], feed fault, servo online, hopper empty), dial angle u8 (360/256 deg) |
| 0x315 POWER | turret -> host | 5 Hz | ring bus voltage u16 (mV), the servos' supply as each reads it u8 x 3 (0.1 V: 12 V PAN, 12 V MAIN (the tilt), 12 V FLY (the feed); 0 = off the bus) |
| 0x316 HEALTH | turret -> host | 1 Hz | CAN TEC u8, REC u8, bus-off count u8, ring-drop counter u16 (missing safety pulses), servo bus errors u16, index re-check worst u8 (0.01 deg) |
| 0x317 EVENT | turret -> host | per event | code u8, seq u8, a u16, b u16, c u16: homed (time, index centre in 1/16 count, swept), home failed, feed step (step, settle ms, load mean, clean flag), jam (step, ms since the command, cause and count in a row), feed fault, empty step, SAFE (cause bits, latency ms, value), servo lost or back, burst done (balls, steps, why), dither, stray ball, re-home asked, bench done, refused (why), lift |

**What changed in the set, and why it was forced:**

- **POSE** was 10 bytes (i32 + 3 x i16), which classic CAN cannot carry. The rates are now whole deg/s in i8.
- **0x317 EVENT is new.** The bench needs per-event data the periodic frames cannot hold: each homing's index centre
  (3.5's spread), each step's settle time and load (3.9), and each SAFE's cause and latency (4.6).
- **COMMAND's bench codes** cover the modes the operational frames cannot express: the dial alone (3.9), open-loop
  throttle (4.1-4.3, 4.6), a 1,000 frames/s stream (3.8), the wheels without balls (4.7, 4.8), and a burst while
  panning (5.1).
- The C610's DJI frames are gone. FIRE's speed 0 now means the default, and CONFIG's kinds, the fault bits and the
  flags are now defined; these are definitions, not new frames.

This mirrors the simulator's turret (sim/turret.py `TurretController`): aim within the depression table, the laser
before shots, fire only when settled, and report shots. The host-side bridge maps one onto the other.

## 7. Bench harness and the host bridge

On the stand (cad/turret_stand.py), 24 V comes through the XT60E-M inlet, the rocker switch and the DC-rated 5 A fuse
to DT12 pins 1-4. The pendant powers the base's 555 through DT12 pins 7-8. The USB-CAN adapter (a candleLight /
gs_usb one, as can0 under socketcan) sits on pins 5-6 to the laptop and terminates that end. The ring map and its
mandatory soft start are in docs/turret-wiring.md section 1.2.

`firmware/turret/bench_host.py` runs every test of docs/turret-prototype-plan.md section 5 that needs the firmware,
its CAN link or a reading to record: 3.1-3.10, 4.1-4.10, 5.1-5.5 and 6.1-6.8. Tests 1.x and 2.x need neither. Each
test writes its readings and pass/fail to `exports/turret/bench/<file>.json` (`--list` shows the files).

- On the bench, `--can socketcan:can0` (python-can) is used. The script tells the operator what to do and asks for
  the instruments' readings, or takes them from `--answers`. The host heartbeat runs in a thread, so the turret stays
  armed while the operator reads a scope.
- `--sim` runs the same tests against `sim_turret.py`, which simulates the turret with this firmware on it, and writes
  to `exports/turret/bench/sim/` only, so a simulated result can never be mistaken for a bench reading. Phases longer
  than 120 s are shortened (the JSON says so), and readings the simulation cannot make (ring ohms, IR temperatures,
  paper) are stated stand-ins, listed in each JSON. A dry run of all 33 tests takes about 2 minutes.

**The host bridge.** `firmware/turret/host.py` is the one host for the turret outside the bench tests: manual firing
on the laptop, on the Orin box and on the robot, and later the game. It is built on bench_host.py's protocol layer
(its `SimLink` and `CanLink` and its `Turret`, imported, so the bench tests are unchanged). It:

- sends the 10 Hz heartbeat, with the arm request high only while the user has asked to arm; the request drops on any
  SAFE, FAULT or turret restart, so nothing re-arms without the user asking again;
- sends the CONFIG rows for the mount as soon as the turret has homed, and again after the turret restarts (a gap in
  its heartbeat, a break in the heartbeat's sequence, or BOOT). `--mount` is required: with no default, the robot can
  never get the bench's full-range table by omission.

  | Mount | Depression table | Keep-outs (aim, never fire) |
  |---|---|---|
  | robot | exports/turret/lidar/lidar.json `firmware_table`: the VLP-16 143 mm ahead of the pan axis, its top 41.7 mm above the TM face (`config.ROBOT_DEPRESSION` if the file is missing) | none: the body's business |
  | box | exports/turret/lidar/box.json `firmware_table` | box.json's `keep_out_fire_pan_deg`: within 60 deg of straight back |
  | bench | explicit: -25 deg at every 30 deg of pan | within 60 deg of straight back, where the operator stands |

  With these go tyre 34, ring on, the launch ratio, and the throttle map once bench test 4.3 has passed
  (exports/turret/bench/speed_map.json; in --sim, the simulated one). `--keepout none` or `--keepout FROM:TO`
  replaces the keep-outs;
- refuses to arm until those rows have gone out since the turret's last boot and its next heartbeat has come back
  without CONFIG_MISMATCH. The reference echoes no CONFIG row, so that heartbeat and the restart watch are the
  acknowledgement it allows (section 9);
- sends AIM, FIRE and LASER: the tilt is never asked above level or below the table; pan and tilt run at most 90 deg/s,
  and at most 50 deg/s while "people near" is set (the body's lidar and cameras, or the page). While it is set no FIRE
  goes out, a burst under way stops and its wheels spin down, and an aim under way slows (its goal is re-sent, nudged
  0.05 deg, because the firmware takes a new rate only with a new goal);
- logs every SHOT, FEED, POWER, HEALTH and EVENT frame, the state changes, the CONFIG rows and the commands to
  `exports/turret/bench/host-<UTC time>-<mount>.json`. In --sim the log goes to exports/turret/bench/sim/ and never
  to bench/ itself, as with bench_host.py.

The arm request is only a request. The safety line (the pendant on the bench, the body's STOP contact on the robot),
the firmware's own conditions and the hardware arm chain decide. Running it:

- **Simulated:** `.venv/bin/python firmware/turret/host.py --sim --mount robot`, or with
  `--script "pendant on; arm; aim 0 -10; fire 24; status"`. The simulated time runs only inside a command (`wait S`
  runs it), and `pendant on|off` and `load N` stand in for the operator.
- **On the laptop:** the gs_usb adapter on DT12 pins 5-6 as above, python-can in the venv (`pip install python-can`),
  `sudo ip link set can0 up type can bitrate 1000000`, then `.venv/bin/python firmware/turret/host.py --can
  socketcan:can0 --mount bench` (`--mount box` on the Orin box).
- **On the Jetson:** the J501's second CAN port as classic CAN at 1 Mbit/s (`sudo modprobe mttcan` if it is not
  loaded, `sudo ip link set can1 up type can bitrate 1000000`, `ip -details link show can1` to check), python-can,
  then `python3 firmware/turret/host.py --can socketcan:can1 --mount robot`. The body terminates its end of the bus at
  the J501. If only can0 comes up (body P0), the turret stays on the USB-CAN adapter, as on the bench.
- **For the game page's backend:** `--jsonl` reads one JSON object a line (`{"cmd": "aim", "pan": 10, "tilt": -5}`,
  `{"cmd": "fire", "balls": 3}`, `{"cmd": "near", "on": true}`, `{"cmd": "status"}`) and answers each with one
  JSON line. A Python backend can use `TurretHost` directly. No web server is needed.

The commands are status, aim PAN [TILT [RATE]], fire N [RATE [FPS]], laser on|off, near on|off, arm, disarm, stop,
spindown, rehome (refused while people are near: homing sweeps at 60 deg/s), clear, config, wait S and quit.

## 8. Proofs in simulation

| Test | What it proves | Result (2026-10-27) |
|---|---|---|
| `test_homing.py` | homing and turn counting, 1,000 random starts | unchanged: 1,000 / 1,000, max 6.7 s, repeatability 0.07 deg |
| `test_feed.py` | the feed driver against a simulated STS3215 through the real packet code: 3/s with a jam injected and recovered; three jams fault; the load catches a jam before the timeout; the drop-off on release and the re-init; lost replies never double a step; the step time; the gate-paced burst with hung balls freed by the dither, the 5-ball hopper at -25 deg, the empty hopper | all pass: jam caught 68 ms after contact (load), reversed, retried, recovered; clean steps 229 ms mean, 236 max; 6 of 6 hung balls freed by a dither, 0 by a step, 0 doubles; 335 ms step to step |
| `test_firmware.py` | protocols; 8,855 rpm / 61,985 eRPM; Ø36 refused; the tilt never above level; no spin without ARM; the re-arm; zero throttle when the heartbeat goes; a 300 Hz train refused though the hardware stays armed; the ramp never steps; the 24 V guard; one bad frame no trip; a 75 fps pair latches SAFE; aim live and capped while disarmed; the feed servo's drop-off and re-init through the firmware; a new set speed ramps; no DShot frame while the ESCs are unpowered; the host bridge end to end with mount robot (no arming before the table is loaded, the 85 CONFIG rows in the firmware, an aim, 24 balls, then people near: a burst stopped, fire refused, pan held to 50 deg/s) | all 20 pass; the host: 24 of 24 balls, 50.0 deg/s with people near (90.0 before) |
| `bench_host.py --sim` | every bench test runs end to end | 33 of 33 pass on the circuit as drawn now (docs/turret-wiring.md 3, D47); 6.8 on the table for the lidar 143 mm ahead |

## 9. Open items found while building v0 (for the hardware and the plan)

- **The pulse train's frequency is not checked in hardware (3.2).** An 18.5 ms retriggerable one-shot (CD74HC423E) stays triggered by
  any train faster than ~50 Hz. As drawn, a 300 Hz or 3 kHz train holds the rails on, and 50 Hz hum sits at the
  monostable's own period. The firmware refuses on PULSE_MON within 1-6 ms. Making "only the genuine 1 kHz train
  arms" true of the rails needs a frequency window in hardware, for example a second one-shot that rejects early
  edges, or a tone decoder.
- **Resolved in the hardware (docs/turret-wiring.md 3, D47):** the brake's release is now immediate (D3 and 1 k: 0.6-
  1.4 ms), test 3.3 judges the 60 mm gates' window, and the trip latch is set-only (a slower ball after a trip cannot
  clear it). One-shot A is 18.5 ms (16-21), inside test 4.7's 25 ms.
- **Firmware duties the hardware now relies on:** DShot pins held low while ARM_IN is low (`flywheel.update()` returns no
  frame); a new set speed or throttle while spinning ramps over 300 ms (never a step down: AM32's complementary PWM is
  off, but a step down would still be a hard brake; never a step up: the ring's current); the inputs' own pulls off;
  PULSE_MON on A3, TRIP_IN polled.
- **Test 6.7 cannot hold for a ball already at the nip.** A ball at the nip at the release, or reaching it within
  ~10 ms, leaves fast (the physics' own table). The early zero throttle narrows that window and cannot close it.
- **No CONFIG echo.** The firmware answers no CONFIG row, so the host bridge cannot see that each depression row
  arrived (a full receive FIFO on the Feather would drop one silently). It paces the rows (about 4 a millisecond), and
  the robot has the built-in table behind it. An EVENT per accepted row (kind and index in a, the stored values in b
  and c) would let the host check every row: proposed for the Feather port, not in the reference yet.
