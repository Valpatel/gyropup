# Turret firmware plan

The turret's controller is an Adafruit Feather M4 CAN Express (SAME51) on level 2 of the turret bay. This page is
what its firmware does and how it talks to the robot (docs/turret-plan.md task T4): the pin map, the states, pan
homing with continuous rotation, the flywheel spin-up and the feed, the aiming rules the physics asks for, the CAN
message set, and the bench harness. The hardware arm chain (docs/turret-wiring.md section 3) sits under all of it: the
firmware can stop the turret, never start it on its own.

## 1. Pin map (Feather M4 CAN Express)

| Pin | Use | Notes |
|---|---|---|
| D0 / D1 (Serial1) | the Feetech servo bus (pan in the base across the ring S5, tilt on the +y arm) | half-duplex through the 74AHCT125, 500 kbit/s (below the 1 Mbit/s default, for margin over the ring) |
| D4 | SERVO_DIR | the buffer's direction |
| D5, D6 | ESC_L, ESC_R | bidirectional DShot300 (timer channels) with eRPM telemetry back on the same pin |
| D9, D10 | GATE_1, GATE_2 | the chronograph comparators; interrupts with microsecond timestamps |
| D11 | PAN_INDEX | the hall switch (A1120, open drain, pull-up to 3.3 V); interrupt on both edges |
| D12 | ARM_IN | the arm chain's output (read only) |
| A1 | TRIP_IN | the trip latch (read only) |
| A4 | PULSE_MON | the opto's output: counts missing safety pulses (the ring-drop counter) |
| D13 | LASER_EN | through a logic MOSFET |
| A2 | HOPPER_BEAM | the hopper-full break beam |
| A3 | NEOPIXEL | the 12-LED ring |
| A0 | BUS_V | the ring's +24 V through a 10:1 divider |
| CAN (on-board transceiver) | the turret's CAN segment | 1 Mbit/s classic; the C610 and the robot's host share it (section 6) |

## 2. States

```
BOOT -> HOMING -> IDLE <-> ARMED -> SPIN_UP -> READY <-> FIRING
                    ^         |          |         |         |
                    +---- SAFE <---------+---------+---------+   (ARM low, heartbeat older than 200 ms, TRIP, a fault)
```

- **BOOT**: read the configuration (tyre size, the depression table and the keep-out sectors for the mount in use),
  set the servos' torque limits (pan 50 %: the printed pinion is SF 2.52 there; tilt 50 %), their speed limits (both
  axes at most 100 deg/s: D7; the pan can do 90 at most anyway), and their protection current.
- **HOMING**: section 3. Nothing else moves until it is done; the host sees HOMING in the heartbeat.
- **IDLE**: aims and holds; the laser may be on; the wheels and the dial are off (their rails are cut anyway unless
  the hardware is armed).
- **ARMED**: the hardware ARM is high and the host asks to arm (with a heartbeat no older than 200 ms). Still no
  spinning until a fire request.
- **SPIN_UP**: section 4. **READY**: the wheels are within 5 % of the set speed. **FIRING**: section 5.
- **SAFE**: zero throttle, the dial stops, the event goes to the host; the hardware has already cut both motor rails
  and shorted the flywheel phases. Back to IDLE when the cause clears (TRIP only by its recessed button).

## 3. Pan homing and continuous pan

The pan servo's 12-bit angle covers one servo turn, 120 deg of pan through 63:21, so at power-up the pan is known
only modulo 120 deg. Reference implementation: firmware/turret/homing.py (ported line for line).

1. Tilt to the 0 deg stop first: then nothing can meet the lidar or the deck while the pan searches.
2. Sweep in +pan at 60 deg/s (the direction the index was calibrated in) until the hall's window has been crossed:
   its two edges are timestamped by the interrupt, the servo position by its reads (>= 50 Hz), and the window's centre
   comes from interpolating the reads at the edge times. The centre sits half the switch's hysteresis past the magnet
   in a +pan sweep; the assembly calibration measured that offset in the same direction, so it cancels.
3. Zero the turn counter there: pan = (unwrapped servo counts - counts at the index) x 120 / 4096 deg. The unwrapping
   is unambiguous at 50 Hz (90 deg/s of pan is 270 deg/s at the servo: 5.4 deg a read; three failed reads in a row
   still leave it below half a turn).
4. The gear's 0.44 deg of backlash: the tracker follows the drive's direction and adds the backlash back after a
   -pan move; aiming finishes every move in +pan anyway (section 5), so the turntable always rests on the same flank.
5. Every later +pan pass over the index re-checks the count; more than 2 deg off asks the host for a re-home.
6. Drive mode: the STS3215 in position mode with its angle limits at 0 (multi-turn, +-7 servo turns = +-840 deg of
   pan); the firmware re-bases the goal within that window while the turret rests, so continuous pan never runs out.
   A bus fault leaves the servo holding, never free-running.

**Proof (task T4: 1,000 random starts):** firmware/turret/test_homing.py runs the reference against a model of the
hardware (random start and servo zero, 50-100 Hz reads with jitter and up to 3 % failures, +-1 count of noise, the
gear's backlash, a 60 ms drive lag, hall windows of +-1.5..4 deg with 0.3-1 deg hysteresis, +-50 us interrupt jitter,
+-0.3 deg calibration), then 20 s of random moves up to +-720 deg at up to 90 deg/s with the index re-check. Results:
exports/turret/firmware/homing.json.

## 4. Flywheels

- **Set speed**: 9,408 rpm for 55 fps on Ø36 tyres (docs/turret-physics.md section 4); 50-57 fps is the usable range
  on 12 V. The tyre in use (Ø34 or Ø36, cad/turret.py `TYRE_SET`) is in the configuration; the set speed scales with it.
- **Soft spin-up**: the set speed ramps from 0 over 200 ms (2.2 A at the ring instead of 12 A); AM32's own `max_ramp`
  is the second limiter. Mandatory: the ring's power rails are two 2 A circuits each (D2).
- **Pre-feed RPM check**: before the first ball and at every ball, both wheels' eRPM (DShot telemetry) within 5 % of
  the set speed and **below 11,500 rpm**. A 24 V fault on the ESC rail spins them at ~21,000: refuse to feed and go
  SAFE (the chronograph trip is the backstop after one ball; this check is what stops the first).
- **Stray ball**: arming after a release while feeding may find a ball resting at the nip. Start every arm with the
  muzzle at -25 deg for the ramp's first 50 ms; a ~8 fps chronograph reading then is logged as a stray ball
  (docs/turret-physics.md section 5).
- **Stops**: AM32 `brake_on_stop` for every ordinary stop; the hardware phase-short does the release.

## 5. Feeding and aiming

- **Dial**: one 45 deg step per ball, the C610 allowed 10 A for the ~100 ms of a step (the plan's 3 A cap makes 3/s
  marginal: physics finding 2), then a hold. The step starts only when both wheels are READY.
- **Empty step** (no ball at gate 1 within 400 ms): a +-10 deg dither and one more try (physics finding 1); below
  -12 deg of tilt, lift to 0 deg for 0.4 s first (the feed simulation's finding: the last balls pool on the baffle).
- **Jam**: a step that has not finished in 300 ms (the C610's position feedback) reverses 20 deg and retries; three in
  a row stops feeding and reports.
- **Rate**: 3/s by default, 4/s at most (the clean maximum by stepping; physics section 11).
- **Per-shot check**: both gates time every ball; a ball over 66 fps stops feeding (the hardware trip also latches).
- **Depression table**: the most depression allowed at each pan for the mount in use (cad/turret_lidar.py for the
  robot over its lidar; the box scene for the Orin box). The firmware clamps the tilt goal to it, interpolating
  between table rows and rounding toward safety.
- **Keep-out sectors**: pans where the turret may aim but never fire (the operator's side on the bench and the box).
- **Settle before firing**: fire only when the pan rate is under 10 deg/s and the pan has been still 0.25 s after its
  last command (the 240 ms from command to muzzle outlasts a moving aim: physics findings 8 and 10).
- **One-sided approach**: every pan move ends in +pan (overshoot 1 deg and come back when arriving from above), so the
  gear's backlash is always taken up the same way (physics finding 6).
- **Laser**: on at least 0.35 s before the first shot at a target (the simulator's rule). The laser (Class 2, under
  1 mW) and the servos stay live when the safety line is released (D7); only the wheels and the dial lose power.

## 6. CAN message set

The turret has its own CAN segment (DT12 pins 5-6) to the host (the Jetson's turret port on the robot, the USB-CAN on
the bench), shared with the C610 (DJI IDs: command 0x200, feedback 0x201 at 1 kHz: ~13 % of a 1 Mbit/s bus). Turret
frames use the 0x300 block, little-endian.

| ID | Direction | Rate | Payload |
|---|---|---|---|
| 0x300 HOST_HEARTBEAT | host -> turret | 10 Hz | counter u8, host state u8, arm request bit; older than 200 ms = no arm |
| 0x301 AIM | host -> turret | on change | pan goal i32 (0.01 deg, continuous), tilt goal i16 (0.01 deg, <= 0), pan rate limit u8 (deg/s) |
| 0x302 FIRE | host -> turret | on request | balls u8, rate u8 (0.1/s), set speed u16 (0.1 fps), request id u8 |
| 0x303 LASER | host -> turret | on change | on u8 |
| 0x304 CONFIG | host -> turret | at start | indexed rows: the depression table (pan i16, min tilt i16), keep-out sectors, tyre size, ring type |
| 0x305 COMMAND | host -> turret | rare | re-home, stop, spin down |
| 0x310 TURRET_HEARTBEAT | turret -> host | 10 Hz | state u8, fault bits u16, ARM, TRIP, homed |
| 0x311 POSE | turret -> host | 50 Hz | pan i32 (0.01 deg), tilt i16, pan rate i16, tilt rate i16 |
| 0x312 WHEELS | turret -> host | 20 Hz | rpm L u16, rpm R u16, ESC temperatures u8 x 2 |
| 0x313 SHOT | turret -> host | per shot | shot no u16, speed u16 (0.1 fps), wheel rpm at the shot, flags (stray, over-speed) |
| 0x314 FEED | turret -> host | 5 Hz | balls fired u16, empty steps u8, jams u8, hopper-full bit, dial angle |
| 0x315 POWER | turret -> host | 5 Hz | ring bus voltage u16 (mV), regulator states |
| 0x316 HEALTH | turret -> host | 1 Hz | CAN TEC u8, REC u8, bus-off count u8, ring-drop counter u16 (missing safety pulses), servo bus errors u16, index re-check worst u8 |

This mirrors the simulator's turret (sim/turret.py `TurretController`): aim at a pan and tilt within the depression
table, the laser before shots, fire only when settled, and report shots; the host-side bridge maps one onto the other.

## 7. Bench harness

On the stand (cad/turret_stand.py): 24 V through the XT60E-M inlet, the rocker switch and the DC-rated 5 A fuse to
DT12 pins 1-4; the hold-to-run pendant's dry loop to pins 7-8; the USB-CAN adapter (`usb-can-canable2`) on pins 5-6 to
the laptop, terminating the far end. The laptop runs the host side of section 6. The ring map and its mandatory soft
start are in docs/turret-wiring.md section 1.2.
