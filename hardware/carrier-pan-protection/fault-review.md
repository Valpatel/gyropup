# Candidate fault-state review

**Reviewable electrical topology, not a qualified protector.** The controller opens a switch; it does not regulate or clamp a surge. Datasheet thresholds alone cannot guarantee PAN_INPUT≤55 V. The entire carrier remains unreleased.

## Source and load envelope

Retain [PR82's requirements](../../research/protection/carrier-input-protection.md):15–20.5 V stand,30–42 V robot steady source; source transients, rise time, duration, impedance/inductance and repeated energy remain unmeasured. U2 powers **one**12 V pan servo plus the estimated10 mA pendant/555 load. [Waveshare's selected12 V variant](https://docs.waveshare.com/ST3215_Servo) permits6–12.6 V and lists2.7 A stall. The existing1.5 A simulation estimate is not a fault bound. Screening load is2.71 A;3.25 A is a deliberately assumed20% servo contingency. No current tolerance or reversal peak is established.

Q1/Q2/R1 serve only U2. The other head loads remain on the shared BUS and are not protected by this new stage. Existing upstream D8, D14 and fuse/holder coordination remains unresolved; the exact original holder rating has conflicting manufacturer revisions. No existing part is silently replaced.

## Intended behavior and residual faults

| Event | Candidate behavior | What is not established |
|---|---|---|
| Valid source, power applied | SHDN divider enables automatically; U1 delay then gate ramp; U2 EN floats high internally | This is **automatic supply startup**, not permission to arm/move. Firmware and existing safety chain must remain fail-off. |
| Falling source / UV | Divider triggers cutoff; recovers automatically above hysteresis threshold | Regulation near stand minimum still depends on load/dropout and wiring loss. UV is not proof that12 V is maintained. |
| Rising source / OV | Divider triggers fast gate pull-down; automatic recovery after valid window/delay | Comparator overdrive timing, actual gate charge/C3 and loop inductance do not establish terminal peak; qualify≤55 V against agreed source envelope. |
| Forward input overcurrent | R1 differential trips; RETRY grounded latches MOSFETs off | Breaker is not a precise constant-current limiter. Startup threshold is lower, and nuisance trip/repeated manual reset can stress FET SOA. |
| Forward fault reset | SHDN must go low then high; power loss/reapplication can also clear state | No persistent safety latch is implemented. A service pad is not an emergency stop. |
| Reverse current through input stage | -2 controller opens at its reverse threshold, then automatically reconnects when output sufficiently below input | This prevents some backfeed **at U2 input**; it is not a12 V regenerative brake/clamp. Reverse comparator needs VOUT above its UVLO. |
| Reversed42 V source | **Outside controller's−40 V protection limit** | D8/fuse cannot be credited without coordination. This remains a release blocker, not a claimed capability. |
| Source removed, output charged | Off MOSFET pair opposes passive through-conduction; R9 bleeds PAN_INPUT | U2 reverse conduction, capacitor bank, signal injection and output energy remain unbounded. No safe removal time is claimed. |
| Hot connection at PAN_INPUT | Forbidden interface operation | U1 VOUT cannot be hot-swapped above24 V; this is an internal permanently wired node, not a supply jack. |
| Servo reversal/braking/output overshoot | No output protection selected in this candidate | U2±3% static upper12.36 V leaves0.24 V. Neither PG nor an unspecified TVS proves≤12.6 V. Regeneration/source-sink behavior remains a blocker. |
| Q1 or Q2 drain-source short | The remaining single FET/body diode does not provide the original bidirectional isolation | Not single-fault tolerant. No redundant independent safety claim. |
| U1 GATE stuck high or divider faults | Some faults can leave the supply on or shift cutoff | No diagnostic coverage claim. R2-open/R3-short can defeat OV; sense wiring/R1 failure can defeat OC. |
| R1 short/open or common ground break | OC defeated or supply removed/uncontrolled references possible | Ground and Kelvin routing must be checked in PCB review; ERC cannot establish those physical properties. |

## Candidate values and margins

`calculate.py` emits reproducible static screening results using the actual resistor values and conservative temperature scenarios. Divider resistance budget includes0.1% initial tolerance plus25 ppm/K over65 K (−40..85°C relative25°C); it excludes aging, solder drift and thermal gradients beyond that scenario. UV/OV reference492.5–507.5 mV, hysteresis20–32 mV and input leakage±10 nA come from [LTC4368 rev C](https://www.analog.com/media/en/technical-documentation/data-sheets/ltc4368.pdf). SHDN threshold/leakage are separate and not borrowed from UV/OV.

R1 is10 mΩ1%, with75 ppm/K also included for the65 K scenario. Nominal5 A forward trip is **input current**, not servo current. Startup trip may occur below the3.25 A input screening load at15 V/80% efficiency even before charging capacitance. That is a known startup-qualification gap; the schematic is not described as guaranteed to start under a stalled servo. Selecting a lower resistance or sequencing U2 EN is a subsequent reviewed change, not silently assumed here.

C1 is22 µF100 V, ±20% at its specification conditions, from [Panasonic](https://industrial.panasonic.com/ww/products/pt/aluminum-cap-lead/models/EEUFC2A220). It exceeds the controller's1 µF local requirement nominally and at room-temperature tolerance; cold impedance/capacitance,260 mArms ripple rating at100 kHz and layout still require review. It is polarized: negative PAN_INPUT excursions are not qualified. The converter's total input capacitance is unknown. The shared940 µF slip-ring bank is **not** assigned to this branch.

R8=22 kΩ and C2=3.3 nF use ADI's inrush-network topology; C3=6.8 nF is across gate/common-source per its hot-swap guidance. These are candidate values. The calculated gate-slew inrush sensitivity is not a transient simulation; it omits active U2 startup and real MOSFET nonlinear charge. Combined capacitors/charge need measured turn-off, turn-on and SOA evidence. R9 discharge calculations apply only to the assumed capacitance and no externally supplied backfeed.

TI's [100 V MOSFET sheet](https://www.ti.com/lit/ds/symlink/csd19531q5a.pdf) gives6.4 mΩ maximum at10 V gate and25°C. Pair losses at3.25 A are a cold-resistance screening value; hot resistance, copper area and linear-mode startup/interruption are unqualified. Do not use the headline100 A rating as a board current rating. Package ratings are also not an accepted100 V source envelope.

## Mechanical and release handoff

The existing50.8×30 mm board has a25.4×25.4×9.5 mm U2 reservation. D42V55F12 has the same **board outline**, not a qualified interchangeable footprint. Extra circuitry has no allocated PCB location. C1's8×11.5 mm nominal body alone exceeds the U2 height reservation, before leads/mounting clearance. There is no PCB placement/routing, approved footprint, thermal copper, cable retainer or new mounting design here.

Next release decisions: source/reverse envelope and upstream protection;12 V regenerative/output protection; startup load/EN sequencing; actual converter Cin and C1 ripple; fault interruption/SOA/thermal; reset/arming and unpowered signal behavior; then PCB/package placement and carrier revalidation. No energized test or purchase occurred.

## Legacy assertions requiring later source correction

Carrier author verified that `cad/turret_boards.py` still says every BUS part is rated50 V or more and that D14 clamps before the50 V U2 limit. These legacy statements are **not validated by this candidate**; PR82 already rejects the guaranteed-clamp claim. The frozen PR67 files are deliberately untouched here. Correct those assertions when the selected circuit is integrated, then regenerate source-bound carrier evidence. Current author geometry places U2 at turret X36.9..46.4,Y−6.4..19.0,Z8.3..33.7 mm; PCB X46.4..48.0; solder gap X48..53 and window through X53..56. None of that window is newly allocated protection-component space.
