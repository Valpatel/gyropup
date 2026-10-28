# Body firmware: the balance controller on the Nucleo-G474RE (B8, D63)

The firmware that balances Gyropup: C on an STM32G474RE (Nucleo-G474RE), three CAN buses, the VN-100 IMU at 800 Hz,
a 1 kHz loop ported from the simulation's controller, and the safety behaviours a kids' robot needs (the radio stop,
the Jetson's heartbeat, under-voltage, the jump gate, people near). Code in [`firmware/balance/`](../firmware/balance/),
its HIL in [`firmware/balance/hil/`](../firmware/balance/hil/), CI in
[`.github/workflows/body-firmware.yml`](../.github/workflows/body-firmware.yml). Written 2026-10-27; task B8 of
docs/body-next-plan.md 4.1. Nothing has run on hardware yet: that is B13 (section 9).

## 1. What was shown

| Acceptance (B8) | Result | Where |
|---|---|---|
| The firmware builds in CI | the Nucleo image links: **text 42,620 B, data 100 B, bss 13,064 B** (8 % of the flash, 13 % of the RAM) with Arm GNU Toolchain 13.3.rel1; also with Ubuntu's gcc-arm-none-eabi 13.2 (CI's); the host library and 185 unit checks pass | `.github/workflows/body-firmware.yml`, `tests/test_core.c` |
| The HIL replays the sim's stand_up within 5 % of leg length and lean | **worst 0.36 mm (0.17 %) of leg length, 0.009 deg of lean** against `sim/leg_rig.py run()` at 16.25 kg and 36 V, both legs (the rig's own controller through the same HIL: 0.25 mm, 0.009 deg) | `hil/test_hil.py`, `hil/hil-results.json` |
| UVLO and the jump gate trip at their numbers (the 10S windows, D65, section 5.1) | on a pack falling 0.2 V/s: the warning at **35.00 V**, the jump gate closing at **34.00 V**, the sit at **32.00 V** (resting, the firmware's estimate; the open-circuit voltage then 0.2 V lower, the 1 s filter's lag), the **cut-off at 30.00 V** under load (29.98 V on the wire), latched; a drop to 29.5 V while standing cuts off in 194 ms (the resting estimate still 33.2 V), sits, stops the motors and stays latched through a fresh pack and a new RUN | the same |
| The jump scaled with the voltage | 41.0 V: **195 mm**, bus min 34.0 V, 70 A; 36.0 V: s 0.694, the push held to 50 A, **150 mm**, bus min 30.8 V; 34.1 V: s 0.431, 31 A, **104 mm**, bus min 30.9 V; 33.9 V: refused. Never through the cut-off | the same |
| The bus current limit | a full-pack jump (72 A unlimited) with the peak lowered to 50 A: held at it (51.8 A worst, the INA228's 2 ms behind), the motors scaled to 0.74, still 175 mm, nothing trips | the same |
| (beyond B8) the law on the whole robot | the robot profile balances `sim/robot_v2.py`'s B3 model (32.15 kg) through the same emulated devices like `sim/controller_v2.py` does, both at 36 V: stand, 0.5 m/s, stop, crouch; never past 5.6 deg (the simulation's controller 5.6 deg), x within 12 mm, v 7 mm/s, leg length within 1.2 mm, the pendulum-angle estimate within 0.023 deg of MuJoCo's | `hil/sil_robot.py` |
| (beyond B8) the radio stop, the heartbeat, people near | MCU_RUN open 1 ms after the coil sense drops, the legs down and the motors stopped 451 ms after; the heartbeat sit 2.198 s after the last setpoint; people near refuses the jump and sits after 2.008 s | `hil/test_hil.py` |

## 2. Architecture

```
            bus A (FDCAN1)  RS-04 1 (left front), 2 (left rear)
            bus B (FDCAN2)  RS-04 3 (right front), 4 (right rear)
Nucleo  --  bus C (FDCAN3)  VESC 10 (left wheel), 11 (right wheel), J501 can0
G474RE  --  USART1          VN-100 (921600 baud, 800 Hz binary)
        --  I2C1            INA228 (bus voltage and current on the pack's shunt: the windows, the current limit)
        --  PC0 / PC1       STOP sense (the stop relay's coil) / MCU_RUN (the relay's low-side MOSFET)
```

| Layer | Files | Platform code |
|---|---|---|
| The balance law: sim/controller_v2.py ControllerV2 (and sim/controller.py) in C | `src/core/gp_control.c` | none |
| The five-bar: cad/fivebar.py fk / ik / stance, an analytic Jacobian, sim/leg_control.py polar / vmc | `src/core/gp_fivebar.c` | none |
| Devices: RS-04 (rig/rs04.py's protocol), VESC, VN-100, INA228, the Jetson protocol | `src/core/gp_rs04.c`, `gp_vesc.c`, `gp_vn100.c`, `gp_ina228.c`, `gp_jetson.c` | none |
| The application: boot, the supervisor, the sit, the jump, the bench player, the 1 kHz tick | `src/core/gp_app.c` | one call out: `gp_plat_can_send()` |
| The generated model: LQR table, masses, the five-bar, the motors, the gains | `include/gp/gp_model.h` from `tools/gen_model.py` | none |
| The Nucleo: clocks, FDCAN, UART + DMA, I2C, timers, watchdog, the main loop | `src/mcu/` | ST HAL |
| The host build: the same application as `libgp_host.so` for the HIL | `src/host/gp_host.c` | none |

The core has no HAL in it: the MCU and the host library compile the same files. The application is called from one
context only (the tick), so it has no locks: on the MCU the CAN ISRs only queue frames into per-bus rings, the
UART's circular DMA and the INA228's interrupt-driven reads only fill buffers, and the tick drains them first.

**Two profiles** (`gp_config_default`): *robot* (the default: balance on, sim/controller_v2.py's leg gains, the IMU
required) and *rig* (the leg rig: balance off, sim/leg_control.py's gains and sim/leg_rig.py's feed-forward at
16.25 kg, no IMU, the bench player: `stand_up` or `squat` from sim/leg_rig.py). Build the rig image with
`-DGP_PROFILE=rig` for B13's first step on the leg rig.

## 3. The loop and its timing

TIM6 raises a tick every 1 ms; the main loop runs it in thread mode:

1. drain the CAN rings into the application (the RS-04s' replies to the last tick's frames, the VESCs' status, the
   Jetson's setpoints), the VN-100's new bytes, the INA228's last reading;
2. read the stop sense; run the supervisor (section 5); build the sensors (the IMU's frame to the robot's) and the
   command; run the law; queue the frames (four MIT frames, two VESC currents, one Jetson state frame);
3. set MCU_RUN and the LED, push the queued frames into the FDCANs' TX FIFOs, start the next INA228 read (every
   2nd tick), refresh the watchdog (20 ms), note the loop's time (`loop_us_max`).

A command acts one tick after the state it was computed from (the RS-04 replies to an MIT frame with its state when
the frame arrived): 1 ms of latency, modelled in the HIL. The emulated RS-04 path runs the same frames.

| Bus | Per millisecond | Load at 1 Mbit/s |
|---|---|---|
| A, B | 2 MIT frames out, 2 feedback frames back (29-bit, 8 bytes: 131-156 bits each) | 52-62 %; the replies are in by ~0.6 ms |
| C | 2 VESC currents (29-bit, 4 bytes), STATUS_1 from both VESCs at 500 Hz, one Jetson state frame every 5 ms per kind (3 kinds), the setpoint every 10 ms | about 45-53 % with status 4/5 at 50 Hz |

The VESCs' 29-bit ids (command << 8 | id) have their top 11 bits zero, so they win arbitration over every 11-bit
frame on bus C: the wheels' traffic before the Jetson's.

The INA228 converts the bus (150 us), the shunt (280 us) and the die temperature (50 us) four times averaged: a fresh
set every 1.92 ms; the firmware reads VBUS and CURRENT at 500 Hz. The VN-100 sends 30 bytes at 800 Hz (240 kbit/s of
921.6 kbit/s).

The loop's execution time on the G474 is not measured yet (B13); the control law is single precision (no
double-precision code in the image: checked with `-Wdouble-promotion` and the symbol table).

## 4. Every CAN message

### 4.1 RS-04 (buses A and B), rig/rs04.py's protocol

29-bit id: bits 28-24 the type, 23-8 'data area 2', 7-0 the destination. The host id is 0xFD. 16-bit fields scale
over 0..65535 by the manual's float_to_uint (clamp, scale, truncate): angle +-4 pi rad, speed +-15 rad/s, torque +-120
N m, Kp 0..5000, Kd 0..100. Multi-byte data in the MIT and feedback frames big-endian, parameters little-endian.

| Frame | Id | Data | When |
|---|---|---|---|
| MIT (type 1) | `1 << 24 | torque_u16 << 8 | motor` | angle, speed, Kp, Kd (all 0: the torque is pure feed-forward) | every tick while driving |
| Feedback (type 2) | `2 << 24 | (mode << 14 | faults << 8 | motor) << 8 | 0xFD` | angle, speed, torque, temperature x 10 | the motor's reply to every frame |
| Enable (3), Stop (4) | `3 or 4 << 24 | 0xFD << 8 | motor` | zeros (stop: byte 0 = 1 clears faults; the firmware sends 0) | arming; idle and limp (every 10 ms, which also keeps the angles coming) |
| Write (18), Read (17) | `18 or 17 << 24 | 0xFD << 8 | motor` | index (LE u16), 0, value (LE) | boot |

**Boot**, each motor in parallel, one request a tick, 20 ms timeout, 3 tries then again every second: stop; write
`run_mode` 0 (MIT), `limit_torque` 60 N m (D38's cap, in the motor), `canTimeout` 2000 (0.1 s), `zero_sta` 1; read
each back and refuse a motor whose value differs; read VBUS. The motor's angle maps to the leg as
`phi = phi_zero + dir x angle` with each motor's `dir` and `phi_zero` from rig/calibrate.py (section 9); the speed is
the angle's rate when the reported one sits on the field's +-15 rad/s rail; the angle is unwrapped across +-4 pi.

### 4.2 VESC (bus C)

| Frame | Id | Data |
|---|---|---|
| SET_CURRENT | `1 << 8 | id` (29-bit) | int32 mA, big-endian; the firmware's current = torque / 0.951 N m/A, clamped to +-25 A, times the wheel's direction |
| STATUS_1 | `9 << 8 | id` | int32 ERPM, int16 current x 10, int16 duty x 1000; the wheel's speed = dir x ERPM / 15 pole pairs |
| STATUS_2, 3, 4, 5 | `14, 15, 16, 27 << 8 | id` | Ah, Wh (x 1e4); FET and motor C x 10, input current x 10, PID position x 50; tachometer, input V x 10 (parsed, logged) |

VESC ids: left 10, right 11. Set in VESC Tool (B13): the CAN ids, 1 Mbit/s, status 1 at 500 Hz and 4/5 at 50 Hz,
the app's CAN timeout (0.1 s: the wheels freewheel when the MCU stops talking), motor and battery current limits
at 25 A. The right wheel's direction is -1 by default (the same motor turned round); check both at B13.

### 4.3 The Jetson (bus C, the J501's can0), 11-bit, little-endian

| Id | Name | Rate | Bytes |
|---|---|---|---|
| 0x110 | SETPOINT, Jetson -> MCU | 100 Hz | b0-1 speed int16 mm/s; b2-3 yaw rate int16 mrad/s (+ left); b4 height uint8 0..200 (0.005 of the leg range 150-375 mm); b5 lean int8 0.01 rad (+ = look up; the law clamps -0.1..0.35); b6 flags: bit0 RUN (stand and balance; 0 = sit), bit1 PEOPLE_NEAR, bits2-3 JUMP_SEQ (a jump each time it changes), bits4-7 JUMP_HEIGHT (n/15 of the maximum); b7 seq |
| 0x111 | BENCH | on demand | b0 = 1: select bench scenario b1 (rig profile, while sat) |
| 0x120 | STATE_A, MCU -> Jetson | 200 Hz | pitch int16 1e-4 rad (+ nose up); pitch rate int16 1e-3 rad/s; speed int16 mm/s; yaw rate int16 mrad/s |
| 0x121 | STATE_B | 200 Hz | leg length left, right uint16 0.1 mm; lean left, right int16 1e-4 rad |
| 0x122 | STATUS | 200 Hz | b0 mode (0 boot, 1 idle, 2 arming, 3 run, 4 jump, 5 sit, 6 settle, 7 limp); b1 flags: bit0 stop relay powered, bit1 MCU_RUN, bit2 link OK, bit3 people-near caps, bit4 UVLO warn, bit5 UVLO sat, bit6 a jump would be taken now, bit7 jumping; b2-3 bus uint16 10 mV; b4-5 bus current int16 10 mA (+ discharge); b6 reason (why it last sat or limped: 1 stop, 2 link, 3 people, 4 UVLO, 5 the Jetson, 6 no bus voltage, 7 the cut-off, 10 motor missing, 11 motor fault, 12 leg outside 95-395 mm, 13 over-voltage, 14 IMU, 15 fallen, 16 arm timeout); b7 seq |
| 0x123 | FAULTS | 10 Hz | b0-3 each motor (LF, LR, RF, RR): bit7 present, bits0-5 its feedback faults; b4: bits0-1 VESCs present, bit2 IMU fresh, bit3 bus voltage fresh, bit4 a latched fault, bit5 the cut-off latched, bit6 the bus current limit acting; b5 the jump's push allowed now (s(V) %: its bus current, % of 72 A); b6 the last refusal (1 people, 2 voltage, 3 not running, 4 link, 5 height 0); b7 seq |

The state frames go one per tick (STATE_A, STATE_B, STATUS in turn: 200 Hz each).

### 4.4 The leg rig node (rig profile, buses A/B)

The rig's node (rig/node.py) sends RUN 0x700 and VBUS 0x702; with `vbus_source` set to the rig node, the firmware
takes the bus voltage from 0x702 (the 10 ms maximum, the mean for the resting estimate) instead of the INA228.

## 5. The safety behaviours and their numbers

| Behaviour | Numbers | Source |
|---|---|---|
| **Radio stop.** The stop relay's coil + side (12 V while the radio says run) through a divider to PC0. Low for 2 ms: STOP. Standing: MCU_RUN low at once (the turret's loop and 24 V are already cut by the relay), a fast sit (0.3 s to the sit length, 0.15 s of the feed-forward fading), then the motors stopped. A stop during a jump's push ends the push; in the air the landing completes first. | sat and stopped in 451 ms in the HIL (B13 asks for 0.5 s from the transmitter) | D37, docs/body-electrical.md 5, W38/W39 |
| **MCU_RUN** (PC1, the relay's low-side MOSFET, a 100 k pull-down on its gate): high only while arming, standing and jumping; low at boot, sat, sitting, limp, a hard fault or a reset | | D37 |
| **Arming** needs: the coil sense high for 100 ms, the Jetson's RUN going 0 -> 1 with the link fresh, every motor configured and read back, a fresh bus voltage with the resting estimate at 33.0 V or over, no cut-off, no people near, no latched fault, the IMU fresh (robot). The firmware never stands up by itself: after any sit the Jetson must send RUN 0 then 1 | | |
| **Heartbeat.** Each setpoint with a new sequence number is a heartbeat. None for 200 ms: the link is lost; the robot holds its height and lean, the speed and turn slew to 0, no jumps; 2 s later it sits. Back within the 2 s: carry on | sit 2.2 s after the last setpoint (HIL 2.198 s) | D63 |
| **UVLO.** Resting voltage = bus + discharge current x 0.100 ohm (the sag taken back out), filtered over 1 s. Under 35.0 V: the warning flag (clears over 35.3 V). Under 32.0 V: a sit, and no stand until 33.0 V | trips at 35.00 / 32.00 V resting in the HIL | D65; 3.50 / 3.20 / 3.30 V a cell (5.1) |
| **The cut-off.** The bus under load (the INA228's VBUS, no sag correction) through a 0.1 s filter under 30.0 V: a sit (1 s, as UVLO's; in the air the landing first), the motors stopped, MCU_RUN low; latched until a power cycle: no RUN, no fresh pack clears it. Trips in any mode, idle too (a pack plugged in under 30 V never arms) | HIL: 30.00 V on a falling pack; a drop to 29.5 V while standing trips in 194 ms, sat 1.34 s after, still latched with 41 V back and a new RUN | D65; 3.00 V a cell |
| **Jump gate.** Refused under 34.0 V resting, with the cut-off latched, with people near, when not standing, with the link lost, or at height 0. The push's bus current is limited to `s(V) x 72 A`, `s(V) = clamp((V - 31) / (38.2 - 31), 0, 1)` (a factor on the leg torques in the push only, down by limit / I over it): the sag is `s x 7.2 V` and the bus stays over the 31 V floor, 1 V above the cut-off. 72 A x 0.1 ohm is the full push's own sag (HIL), so at and over 38.2 V resting the push is unlimited. The take-off speed is capped at `3.2 m/s x sqrt(n/15)` for the Jetson's height n/15 | 41.0 V: 195 mm, 70 A, bus min 34.0 V; 36.0 V: s 0.694, 50 A, 150 mm, 30.8 V; 34.1 V: s 0.431, 31 A, 104 mm, 30.9 V; 33.9 V: refused | D65, docs/body-next-plan.md 1.3 |
| **The bus current limit** (the INA228's current at 500 Hz): 80 A (`GP_BUS_I_PEAK_A`) for at most 0.5 s at a time (the allowance given back at the same rate under 40 A), else 40 A (`GP_BUS_I_CONT_A`), and 40 A whenever the 1 s average is over 40 A. Not a trip: one factor on every motor's command (legs and wheels), down by limit / I at once, back at 4 a second, never under 0.5 (balance and the legs' weight need torque) | HIL: a full jump with the peak set to 50 A held at 51.8 A worst, factor 0.74, 175 mm | D65; provisional until the dock adapters' ratings are confirmed |
| **People near** (the Jetson's flag; it decides from the lidar and both cameras): wheel speed <= 0.5 m/s, no jumps, the legs hold the height and lean they had, and after 2 s of it a sit | HIL: jump refused, sit at 2.008 s | docs/body-safety.md 24 |
| **Limp** (no torque at once: stop frames, VESC currents 0, MCU_RUN low; latched until the Jetson's RUN goes 0): a motor missing 3 ticks running, a motor fault bit, a leg outside 95-395 mm, the bus over 58 V (regeneration: 17 V over a full 10S pack; the RS-04 trips at 60), the IMU silent 20 ms or the pendulum past 0.9 rad (robot) | HIL: a silent motor limps on the 3rd missed tick | rig/leg_control.py Limits |
| **No bus voltage** for 50 ms: a sit, no stand | | |
| **Watchdog**: 20 ms without a tick resets the MCU; MCU_RUN falls with the pin; the RS-04s' own 0.1 s CAN timeout and the VESCs' stop the motors | | |
| **No crystal**: the image never drives anything (CAN at 1 Mbit/s needs the HSE; the HSI's 1 % is outside this timing's 0.78 %) | | |

### 5.1 The battery windows (D65), all in `include/gp/gp_config.h`

The pack is two DeWalt DCB609 FLEXVOLT 9.0 Ah packs in 20 V mode, in series in two dock adapters: **10S3P, 36.0 V
nominal, about 41 V full (4.1 V a cell), 30 V empty** (decision D65 in docs/decisions.yaml; it supersedes D43's 13S bus, and with
it D54's 13S2P pack and the Daly BMS read over Bluetooth). The packs have no BMS the robot can talk to, so the robot enforces the
cut-off and the current limit itself. Every window is a per-cell number times `GP_CELLS` (10), kept in one block of
`gp_config.h` (the battery section): change them there and nowhere else.

| Window | Per cell | Bus | Measured on | Action |
|---|---|---|---|---|
| Full | 4.10 V | 41.0 V | | the HIL's full-pack runs |
| Nominal | 3.60 V | 36.0 V | | the HIL's default; the motors' speed lines without a reading |
| Warn | 3.50 V | 35.0 V (clears 35.3 V) | resting, 1 s | STATUS flag: the Jetson heads home |
| Jump gate | 3.40 V | 34.0 V | resting, 1 s | no jump under it; the push's current scaled from the 31 V floor (above) |
| Stand | 3.30 V | 33.0 V | resting, 1 s | no arming under it |
| Sit | 3.20 V | 32.0 V | resting, 1 s | a sit, then stay down |
| Cut-off | 3.00 V | 30.0 V | under load, 0.1 s | sit, motors off, latched until power cycle |
| Push floor | 3.10 V | 31.0 V | the bus in a jump's push | the push's current limit keeps the bus over it |

The pack's resistance for the resting estimate is 0.100 ohm (two packs, their docks and the leads: the figure D65's
rig runs used; measure it at B12 with the 2 A load and a step). The bus current limit is 40 A continuous (1 s
average) and 80 A for at most 0.5 s (`GP_BUS_I_CONT_A`, `GP_BUS_I_PEAK_A`; the 80 A MRBF main fuse of D55), placeholders
until the dock adapters' ratings are confirmed; the robot's own jump draws 70 A at most (HIL, 16.25 kg a leg).

The sit lengths: 110 mm on the robot (25 mm of the skids' clearance is at the stops, 101.5 mm), 150 mm on the rig.
How the robot sits onto its skids (the wheels' torque fades, the legs fold onto the stops) is a skeleton: B13/B14 on
the tether decide it.

## 6. Pins (Nucleo-G474RE, STM32G474RET6 LQFP64)

| Signal | Pin | AF | To |
|---|---|---|---|
| FDCAN1 RX / TX (bus A) | PA11 / PA12 | 9 | CAN Pal 1 (120 ohm on) |
| FDCAN2 RX / TX (bus B) | PB12 / PB13 | 9 | CAN Pal 2 (120 ohm on) |
| FDCAN3 RX / TX (bus C) | PA8 / PA15 | 11 | CAN Pal 3 (120 ohm on) |
| USART1 TX / RX | PA9 / PA10 | 7 | the VN-100's 3 V serial port (TX to its RX) |
| I2C1 SCL / SDA | PB8 / PB9 | 4 | the INA228 (Adafruit 5832, address 0x40, its pull-ups) |
| STOP sense | PC0 | input, pull-down | the coil's + side through 27 k / 10 k (12 V -> 3.24 V) with a 3.3 V clamp |
| MCU_RUN | PC1 | push-pull | the logic-level N-MOSFET's gate (100 k to ground) |
| LED | PA5 | | LD2: on standing, 1 Hz blink sat, 5 Hz limp |
| HSE | PF0 / PF1 | | the Nucleo's 24 MHz X3 |
| SWD | PA13 / PA14 | | the on-board ST-LINK |

The alternate functions are the G474's (HAL `GPIO_AF9_FDCAN1/2`, `GPIO_AF11_FDCAN3`, `GPIO_AF7_USART1`,
`GPIO_AF4_I2C1`). PA15 is JTDI (free under SWD); PB8 is also BOOT0's pin, ignored while the option bit nSWBOOT0 is
at its factory 1. The morpho connector position of each pin is in the Nucleo's user manual (UM2505, the ST morpho
pinout): wire from it at B13 and check the X3 crystal and its solder bridges on the board in hand.
Clock: HSE 24 MHz / 6 x 85 = 340 MHz VCO, 170 MHz SYSCLK (boost mode, 4 wait states), the FDCAN kernel 85 MHz
(PLLQ / 4): 85 time quanta a bit, segments 1 + 67 + 17, sample point 80 %, SJW 17.

## 7. Build, flash, test

```
# the Nucleo image (ST's HAL v1.2.7, CMSIS device v1.2.6, CMSIS core 5.6.0 fetched and hash-checked at configure time)
cmake -S firmware/balance -B build/fw-mcu -DCMAKE_TOOLCHAIN_FILE="$PWD/firmware/balance/cmake/arm-none-eabi.cmake" \
      [-DGP_PROFILE=rig] [-DGP_SHUNT=blue_sea]       # ARM_TOOLCHAIN_DIR=<toolchain root> if not on PATH
cmake --build build/fw-mcu                          # balance.elf, .bin, .hex, .map; the sizes printed

# flash over the Nucleo's ST-LINK (any one)
STM32_Programmer_CLI -c port=SWD -w build/fw-mcu/balance.bin 0x08000000 -v -rst
openocd -f board/st_nucleo_g4.cfg -c "program build/fw-mcu/balance.elf verify reset exit"
cp build/fw-mcu/balance.bin /media/$USER/NOD_G474RE/        # the ST-LINK's drive

# the host library and the unit tests (CI runs these and the image)
cmake -S firmware/balance -B build/fw-host && cmake --build build/fw-host && ctest --test-dir build/fw-host

# the HIL (MuJoCo, CadQuery, the leg rig's `rig` package from this repository); the robot test also needs
# build/sim/v2 (python -m sim.robot_v2); GP_FW_HOST_LIB points at the host library if it is not in build/fw-host
GP_FW_HOST_LIB=build/fw-host/libgp_host.so python -m pytest firmware/balance/hil -q   # 13 tests, ~25 s on a GB10
python firmware/balance/hil/sil_robot.py               # the robot run on its own
```

`GP_SHUNT=blue_sea` sets the INA228 for the Blue Sea 150 A / 50 mV shunt of P0-P2 (0.333 mOhm, the 40.96 mV range);
the default is the fuse board's 1 mOhm (P3, D60). Either way SHUNT_CAL is 4096. W30/W31 put IN+ on the battery side of
the low-side shunt, so a discharge reads negative: the firmware's `ina_sign` is -1 (B12 checks it with the 2 A load).

**The HIL** (`hil/harness.py`): the host library's three buses are the rig's in-memory VirtualBus; buses A and B each
carry two `rig/rs04_emu.py` motors whose angles come from a MuJoCo rig (`rig/sim_bus.py` through `rig/hil.py`
HilLink, the plant stepped with what the motors were told), one rig a leg, both drawing from one pack (open circuit
V, 36 V by default, behind 0.100 ohm) that an emulated INA228 reads; bus C has the emulated Jetson and VESCs. The plant waits while the
firmware boots the motors. The transport is swappable: `harness.Bridge` joins a virtual bus to a real interface
(`harness.transport('socketcan:can0')`, a candleLight/gs_usb adapter being SocketCAN, or `'python-can:slcan:/dev/ttyACM0'`)
so the same emulated devices can face the Nucleo itself at B13, the plant then stepped in real time.

## 8. The generated model and how to regenerate it

`include/gp/gp_model.h` is written by `tools/gen_model.py` from `build/sim/v2/robot.xml` and `model.json`:
the LQR gains at 21 heights (sim/controller.py `lqr()`: the wheeled pendulum's parameters read from MuJoCo with the
robot placed standing, Q = diag(40, 600, 30, 20), R = 2; the firmware interpolates in the height where the simulation
recomputes at 0.05 steps), sim/controller.py Gains and sim/controller_v2.py LegGains, the centre-of-mass model the
pendulum angle is estimated with (the base group and each leg link's mass and centre in its frame; checked against
MuJoCo's angle at four heights: 2.4e-7 rad), the five-bar, the motors, the legs' feed-forward, and the rig profile's
gains and feed-forward at 16.25 kg.

```
python -m sim.robot_v2 && python firmware/balance/tools/gen_model.py      # then commit gp_model.h
python firmware/balance/tools/gen_model.py --check                       # 1 if the committed header is stale
```

Today's header is from B3's model of the real body (32.15 kg, d1900ea; `--check` passes against it). On that model the
robot SIL first fell (82 deg): not the firmware, but the SIL's emulated VN-100, which read the base's angular velocity
with `mj_objectVelocity(mjOBJ_BODY, local)`, in the body's principal-inertia frame. B3's full inertia tensor turns that
frame 81 deg about z from the base's (the interim model's 25 deg), so the gyro's pitch rate was 0.16 of the truth and
the LQR lost its theta_dot damping. The SIL now reads the `imu` site and checks its gyro against its own attitude.
The SIL moves both controllers' motor speed lines to 36 V (model.json is at robot_v2's BUS_V, still 48.1 V).

## 9. Not done yet, and what B13 must do

- **Nothing has run on the Nucleo.** B13: flash, measure the loop's time (`loop_us_max`, `overruns`), one RS-04 and one
  BotWheel closed-loop, the VN-100 at 800 Hz, the stop relay from the radio, then both legs on the P1 frame on the
  tether; the HIL's stand_up reproduced within 10 %; the stop sat within 0.5 s.
- **The motors' calibration is a placeholder** (ids 1-4, direction +1, the zero at the designed knee-out stop):
  `rig/calibrate.py` on each motor, then the four (id, dir, phi_zero) into `gp_config_default`. The ids are set with
  `python -m rig.rs04 --id 127 setid N`.
- **The VN-100**: its serial port (both are configured: register 75 async mode 3), its mounting (assumed aligned:
  x forward, y right, z down), the 921600 baud change at every boot, all to confirm on the bench; a mounting rotation
  is not in the code yet.
- **The INA228's I2C timing** (0x3042223B for 400 kHz from 170 MHz) is computed, not scoped.
- **The pendulum-angle trim** (`theta_trim`) and the wheels' directions are calibrated on the robot.
- **The sit onto the skids and the robot's jump** (balance through the crouch, push, flight and landing) are skeletons:
  the rig profile's jump is the simulation's; the robot's is untested beyond the code.
- **No regeneration governor**: over 58 V the robot limps; the P1 brake test with a scope stays the gate (body-next-plan 1.3).
  With no BMS, braking into a full pack (41 V) charges its cells past 4.1 V for as long as it lasts; nothing limits that
  yet but the VESCs' and RS-04s' own regeneration settings.
- **The cut-off is the pack's, not a cell's.** The firmware sees the 10S bus only: a weak cell can be under 3.0 V
  while the bus reads over 30 V. DeWalt's packs balance on their own chargers; check each pack's spread at B12.
- **The battery numbers to confirm on the bench (B12)**: the pack's 0.100 ohm (it sets the resting estimate and the
  push's 72 A), the current limits (the dock adapters' ratings), the cut-off's 0.1 s filter against the robot's real
  sag in a brake and a jump.
- **The 24 V converter**: the DDR-120C-24 starts at 33.6 V, inside the 10S range (D65); the body picks a replacement
  rated to 28 V or under. Nothing in the firmware depends on it now (the old jump floor did).
- **Other owners' 13S/15S numbers**: robot_v2's `BUS_V` (48.1 V: the motors' speed lines in model.json; the SIL moves
  them to 36 V itself), sim/leg_rig.py's `BUS_V` and rig/leg_control.py's `Limits` (the leg rig's 15S window, 46 V; the
  HIL's cross-check of the rig's own controller passes it the 10S one).
- **The gains** are the simulation's at 32.15 kg (B3's model, section 8).
