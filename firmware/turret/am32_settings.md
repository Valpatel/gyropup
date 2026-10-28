# AM32 settings for the two flywheel ESCs

The settings to write with the AM32 configurator into both flywheel ESCs before the cartridge is assembled
(docs/turret-prototype-plan.md T7 (c), docs/turret-firmware.md section 4). They make the firmware's 800 ms soft start,
its zero-throttle stops and the hardware phase-short brake work together, and they give the Feather the eRPM
telemetry its pre-feed check depends on.

- **Primary ESC:** Repeat Robotics AM32 35 A (catalogue `repeat-robotics-am32-35a-esc`). It ships with Repeat's drive
  (crawler) build: bidirectional 3D mode, stall protection, crawler timing. Flash the stock AM32 release for its target
  first, then write the settings below.
- **Backup ESC:** Lumenier Razor Pro F4 45A AM32. It ships with stock AM32; write the same settings.
- **Motors:** SunnySky X2216 1400 KV, 12N14P (14 poles), on the trimmed FLY rail (D68: 10.9-12.0 V, set per turret at
  bench test 4.1 so the faster motor turns 15,930 rpm at 100 % throttle; that rail is the 105 fps ceiling).

## How to write them

1. Use the AM32 configurator (the web configurator at am32.ca, or the desktop one) with a USB linker (the AM32 /
   BLHeli_32 linker in the tools list) on the ESC's signal and ground pads. Do one ESC at a time.
2. Power the ESC from an 11.5 V bench supply with its current limit at 1 A, the motor connected and the tyre off.
   Never more than 12 V, not even to configure: on 20 V the wheels would turn 28,000 rpm.
3. Flash (Repeat ESC only), read, set every row below, write, and read back. Save each ESC's settings file next to the
   bench results as `exports/turret/bench/esc_left.json` and `esc_right.json`.
4. Label each ESC L or R on its heat-shrink.

Field names follow the AM32 configurator. They change a little between AM32 versions (for example `max_ramp` exists
only in recent ones). Where a version names a row differently, set the behaviour the "Why" column asks for.

## The settings

| Setting (configurator) | Value | Why |
|---|---|---|
| Motor direction reversed | L: off, R: on, then check by hand at 5 % | The two wheels counter-rotate so both tyre surfaces move toward the muzzle at the nip. Check with the bench host's spin at low throttle and a finger-light paper strip, before any ball |
| Bi-directional (3D) mode | **off** | The firmware's throttle is 0-100 % forward (DShot 48-2047). In 3D mode the lower half of the range runs the wheel backwards. The Repeat build ships with 3D mode on |
| Input / ESC protocol | Auto (DShot) | The Feather sends DShot300. Bidirectional DShot is the controller's choice (inverted frames) and AM32 answers on the same wire with eRPM. The pre-feed check (16,650 rpm x 7 = 116,550 eRPM: where the worst accepted ball would reach 105 fps) needs that telemetry: with no eRPM the firmware never steps the dial |
| Extended DShot telemetry (EDT) | allowed, if the version shows the option | The firmware turns EDT on with DShot command 13 at every power-up. The temperature frames then arrive interleaved with eRPM and go into the WHEELS frame and test 6.6 |
| Brake on stop | **on** | Zero throttle shorts the phases through the ESC's low-side FETs. That is every ordinary stop, and the firmware's reaction to a release: it sees the 1 kHz train stop on PULSE_MON within 4 ms and commands zero, so the ESC brakes ~16 ms before the monostable cuts the FLY rail |
| Drag brake strength | 10 (full) | The braking above is as strong as the ESC can make it |
| Complementary PWM | **off** | With it on, a slowing ESC rectifies the wheel's energy back into its supply (9.7 J a wheel at 15,269 rpm), and the flywheel rail's converter is a buck that cannot take it: 0.3 J would lift the rail to ~27 V. Off, a slowing wheel coasts or brakes in its own windings (brake on stop is a separate setting and still works). The speed loop's feed-forward map comes from bench test 4.3 with this setting (docs/turret-wiring.md 3.6) |
| Variable PWM frequency | on (default) | |
| PWM frequency | 24 kHz (default) | |
| Timing advance | default (level 2, ~15 deg) | A 14-pole 22xx runs well at the default; auto advance off |
| Startup power | default (100) | |
| Sine mode startup | off | The wheels start fine without it, and it drives the windings at low speed for longer |
| Stuck rotor protection | on | A tyre jammed by a ball: the ESC gives up instead of cooking the winding |
| Stall protection | **off** | A crawler feature that pushes extra power at low rpm. Off on a flywheel |
| RC car reverse | off | |
| Current limit | **10 A** | The second limiter on a stepped start, the one the power model assumed (12 A at the ring stepped). Effective only if the ESC has a current sensor: the Razor Pro has one; the Repeat 35 A is unconfirmed (bench test 4.5 measures). The firmware's 800 ms ramp is the primary limit either way: ~98 W at the input (D68) |
| Max ramp (`max_ramp`, recent versions) | a full 0-100 % change no faster than **200 ms** (0.5 % duty per ms; check the unit the version shows) | Never slower than the firmware's ramp (0-100 % in 800 ms = 0.125 %/ms; 0-96 % for the set speed), so the firmware stays in control. A stepped command (a bug, or the configurator's motor test) is held to 200 ms: ~4x the input power of the 800 ms ramp, instead of a stepped start's ~10x |
| Motor poles | 14 | The X2216 is 12N14P. The eRPM telemetry is electrical either way (the firmware divides by 7) |
| Motor KV | 1400 | |
| Temperature limit | 90 C | AM32 reduces power above it, which only slows the wheels. The bench's own limit is 80 C (test 6.6) |
| Low voltage cutoff | off | The rail is a regulated ~11.5 V, not a battery. A cell-count guess at power-up has nothing to protect here |
| Serial telemetry (30 ms interval) | off | There is no telemetry wire. eRPM and EDT come back on the signal wire |
| Beep volume | default (5) | The arming beeps at power-up tell the operator both ESCs came up |

## How the soft start and the brakes fit together

```
 release   firmware          ESC (AM32)                   hardware arm chain           wheel
 t = 0     -                 driving at the set speed     pulses stop                  15,269 rpm
 ~4 ms     PULSE_MON gap:    brake on stop: low-side      monostable still high        braking
           zero throttle     FETs short the phases
 ~20 ms    -                 FLY rail gone, ESC off       ARM falls, 2815 opens        brake gone for 10 ms
 ~28 ms    -                 off                          BRAKE: IRLZ44Ns short the    tau 18-23 ms
                                                          phases to GND (+5-14 ms)
 re-arm    zero throttle     powered again; arms after    ARM rises, 2815 closes;      at rest
           for 0.6 s         0.5 s of zero throttle       BRAKE opens within 0.2 ms
 +0.6 s    muzzle to -25,    follows the throttle         -                            800 ms ramp; a stray
           800 ms ramp                                                                 ball leaves at ~3 fps
```

- **Re-arm.** The brake's RC opens the hardware short 0.6-1.4 ms after ARM rises (D3 and 1 k), while AM32 drives
  nothing until it has armed on 0.5 s of zero throttle; its own brake on stop puts the low-side FETs in parallel with
  the external short, which is the same short. Do not enable an option that runs the motor at power-up; the default
  arming beeps play later than that.
- **Never a stepped start.** The firmware ramps the set speed over 800 ms (100 % throttle over 800 ms in the bench's
  open-loop modes), and a new set speed while spinning ramps from the old one over 800 ms too. It never writes a
  step: a stepped start would pull several hundred watts through the ring's 2 A circuits. `max_ramp` and the 10 A limit are the second and third
  lines.
- **The speed trim is bounded.** The firmware's speed loop adds at most +-8 % throttle to the feed-forward and moves at
  most 0.05 % a millisecond. A wrong rail (the converter bypassed: the 20.5 V pack on the ESCs) therefore runs the wheels away, and the eRPM
  limit trips within 3 telemetry reads. Do not enable an ESC-side closed-loop speed mode if a version offers one: it
  would hold the speed on a wrong rail and hide the fault from the pre-feed check.

## After writing: the checks on the bench (before any ball)

1. Both wheels turn the right way at 5 % throttle.
2. The WHEELS frame shows rpm from both ESCs (eRPM telemetry works); with EDT, the temperatures are not 0.
3. Brake on stop: from the set speed, the bench host's `--tests 4.7` releases stop the wheel to 5 % by 50 ms after the
   rail drops (AM32's brake first; the hardware short alone takes ~80 ms from 15,269 rpm), and a plain zero-throttle stop takes well under 0.5 s.
4. Test 4.1 (no-load at 100 % throttle) and test 4.5 (spin-up current at the shunt) run before any other powered
   flywheel test.
