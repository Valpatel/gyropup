# The turret's onboard controller: adopt or build (D76)

Issue [#192](https://github.com/Valpatel/gyropup/issues/192). Recorded 2026-11-03, before D76 was written.

On 2026-11-03 the owner dropped the turret's own Jetson (D66's compute plinth):

> "Turret runs off the orin AGX on the robot or an Orin NX on a desktop (optional 2nd variation). Turret has something
> like an ESP32 for it's control system? Some standard turret controler common drone thing or similar."

After that change, the onboard controller still has the same job. It must:

- run the three STS3215 bus servos (pan, tilt, feed) on one half-duplex serial bus;
- drive the two AM32 ESCs with bidirectional DShot300 and read their eRPM, for the pre-feed speed check;
- time the two chronograph gates to the microsecond;
- read the hardware arm chain (ARM, TRIP, PULSE_MON) through 100 k, so it can never drive the chain;
- talk classic CAN to a host: the J501 on Gyropup, or an Orin NX on a desk through the stand's USB-CAN lead.

It **stops** the turret. It never starts it on its own. The hardware arm chain (D7, D9, D10, D47) and the trimmed
flywheel rail's 105 fps ceiling (D68) hold whatever the controller does. Kid safety is a hard rule in every variant.

## Candidates

Prices were read on 2026-11-03 from the sellers' pages or search listings. Nothing was bought.

| Candidate | What it is | Price | Fits the job? |
|---|---|---|---|
| **Adafruit Feather M4 CAN Express** (4759), today's | SAME51 at 120 MHz, CAN-FD controller with an on-board transceiver, 3.3 V logic; on level 2 of the board bay since v0 | US$24.95 (catalogue) | Yes. The pin map, the firmware reference and its tests (`firmware/turret/`), and D47's reviewed arm-chain interfaces are all built on it. |
| ESP32-S3 Feather + Adafruit CAN Pal (5708, TJA1051T/3) | Dual-core 240 MHz with TWAI (classic CAN), Wi-Fi and BLE; the transceiver is a separate breakout | about US$17.50 + US$3.95 | Yes on paper: RMT can make DShot, there are enough timers for the gates, and the logic is 3.3 V too. But it needs a new pin map, a firmware port and a new review of D47's interfaces. Its radio would also be a new way to command a blaster. |
| Waveshare ESP32 Servo Driver Expansion Board (21593) | ESP32-WROOM with a bus-servo port for ST/SC servos (the STS3215's family), Wi-Fi | US$14.97-15.99 | Partly. It drives the servo bus out of the box, but it has no CAN transceiver and no free timer pins for DShot and the gates. It is a good no-fire pan/tilt demo board, not the turret's controller. |
| BaseCam SimpleBGC 32-bit (Extended, Tiny, CAN_MCU) | Camera-gimbal controller: an IMU-stabilised drive for brushless gimbal motors, with RC/PWM in and out | US$255-293 (resellers) | No. It is made for brushless gimbal motors with field-oriented drive, not bus servos, and it has no flywheel, feed or chronograph functions. |
| Flight controller on ArduPilot (e.g. Matek H743) | STM32H743, DShot outputs, servo PWM, CAN, a "mount" (gimbal) library | US$60-145 | No. It could aim servos and spin ESCs, but it does not speak the Feetech servo bus, has no chronograph trip or feed sequencing, and puts a large firmware we do not own around a device that fires at people. |
| STorM32 (open-source gimbal controller) | Brushless gimbal controller, the same class as SimpleBGC | about US$30-60 | No, for the same reasons as SimpleBGC. |

## Decision: keep the Feather M4 CAN (adopt what is already built)

- **It already does the whole job.** The firmware reference (`firmware/turret/turret_fw.py`, `homing.py`, `feed.py`,
  `flywheel.py`, `dshot.py`, `can_msgs.py`) and its tests run against it. The wiring (docs/turret-wiring.md section 3),
  the boards (`cad/turret_boards.py`) and D47's review are built round its 3.3 V pins.
- **CAN is native and on the board.** The DT12 already carries CAN to the J501's can1 (pins 5-6), and the Feather's own
  120 R terminates the turret's end. The desk variation uses the same frames, through the stand's USB-CAN (gs_usb) lead
  to the Orin NX. The firmware does not change.
- **No radio.** The only command paths are the CAN cable and the hold-to-run line. A Wi-Fi or BLE chip next to the arm
  chain would be a path that needs its own safety case.
- **The off-the-shelf "turret controllers" are camera-gimbal and drone boards.** They drive the wrong actuators and know
  nothing about a feed, a chronograph or an arm chain. The safety chain would stay external anyway, so adopting one
  saves no work and adds a second firmware.

**Revisit** the ESP32-S3 + CAN Pal (about US$21 against US$25) if the Feather goes out of stock, or for a v1 cost pass.
Its radio must then stay disabled in firmware and on the bench.

## What changes with D76

| | D66 (superseded) | D76 |
|---|---|---|
| Vision and aiming on Gyropup | the turret's Orin NX | the J501 (AGX Orin), with the body's depth cameras, over CAN |
| Standing alone | the turret's Orin NX | optional: an Orin NX on a desk, over the stand's USB-CAN lead (and a USB camera on the desk if it is to aim by sight) |
| Onboard controller | the Feather M4 CAN | unchanged: the Feather M4 CAN |
| Power in | XT30 on the plinth, 12-54 V | the DT12's pins 1-4 (as before D66): the body's fused turret branch, or the stand's fused DCB609 |
| Hardware arm chain, 105 fps rail, barrel never above level | in the turret | unchanged, in the turret |

Sources:
[Adafruit CAN Pal](https://www.adafruit.com/product/5708),
[Waveshare ESP32 Servo Driver](https://www.waveshare.com/servo-driver-with-esp32.htm),
[BaseCam SimpleBGC 32-bit](https://basecamelectronics.com/simplebgc32bit/),
[SimpleBGC 32-bit Extended at iFlight](https://shop.iflight.com/basecam-simplebgc-32-bit-extended-encoder-version-gimbal-controller-pro276),
[ArduPilot SimpleBGC notes](https://ardupilot.org/rover/docs/common-simplebgc-gimbal.html),
[Matek H743-SLIM](https://www.hobbyrc.co.uk/matek-h743-slim-flight-controller).
