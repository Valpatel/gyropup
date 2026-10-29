# Candidate B fault-state review

**This is an improved circuit candidate, not a qualified protector.** Source reversal and startup now have explicit circuit elements and numerical acceptance bounds. Passing those conditional bounds does not show that real hardware meets them. No purchase, energized test, transient simulation, PCB or thermal qualification occurred.

## Source, load and existing D8 topology

Retain [PR82's requirements](../../research/protection/carrier-input-protection.md): 15–20.5 V stand and 30–42 V robot steady sources. Source rise time, transients, impedance, inductance and energy remain unmeasured. U2 supplies one 12 V pan servo plus the estimated 10 mA pendant/555 load. The [selected Waveshare 12 V servo](https://docs.waveshare.com/ST3215_Servo) lists 2.7 A stall and 6–12.6 V operation. The calculation uses **3.25 A at the 12 V output**, including a deliberate contingency; it is not a guaranteed motor current limit. The worst output-tolerance corner is 12.36 V.

`cad/turret_boards.py:139–141` and `docs/turret-wiring.md:141,241,441–443` place D8 (catalog `diode-1n5408g`, onsemi 1N5408G) **across** BUS/GND after the whole-head 10 A fuse, cathode to BUS. It is not a series blocker. D14 is also a shunt on that node. Nominal fuse current and diode surge current do not establish clearing time, I²t coordination or a safe negative clamp. This candidate takes **no protection credit** for either legacy shunt or fuse; C3 shared BUS remains outside its scope. A reverse source can still damage the rest of the head.

## Why the reverse stage changes

The [LTC4368 rev C](https://www.analog.com/media/en/technical-documentation/data-sheets/ltc4368.pdf) has separate absolute limits: VIN −40..100 V, VOUT/SENSE −10..80 V, and VIN−VOUT −60..100 V. Raw −42 V with a charged +42 V output produces −84 V differential; +55 V would produce −97 V. The manufacturer also requires overshoot mitigation for negative hot insertion beyond −20 V. A single −40 V headline misses both failure modes.

D1 is now a **200 V V10P20-M3/87A series Schottky**, BUS anode to protected-input cathode. U1 VIN, Q1 drain and all three input dividers move behind it. Local D2 has anode GND and cathode VIN_PROTECTED; C4 provides nearby input decoupling and R11 bleeds that node. D2 is not placed across raw BUS. C3 shared BUS does not pass through D1.

For the proposed acceptance envelope VIN_PROTECTED ≥−2 V, PAN_INPUT ≤55 V, raw BUS ≥−42 V, the U1 differential is ≥−57 V and D1 sees at most 97 V reverse, below its 200 V rating. These are **conditional stress calculations**, not measured clamps. D1 capacitance/reverse leakage, C4's biased minimum, D2 pulse current/energy, cold forward voltage and actual loop inductance remain unknown. Negative hot insertion must demonstrate those bounds, including charged output; the circuit is not released for that event. PAN_INPUT itself is an internal wired node: ADI prohibits hot swapping VOUT above 24 V.

A compact low-loss alternative was screened and rejected: [LM74700D-Q1](https://www.ti.com/lit/ds/symlink/lm74700d-q1.pdf) advertises negative-input protection but its CATHODE−ANODE absolute limit is 75 V, below the 84–97 V charged reversal cases. That exact device is not a drop-in solution. No broad controller comparison or silent module substitution is implied.

[Vishay's V10P20 sheet](https://www.vishay.com/docs/89316/v10p20.pdf) distinguishes **2.4 A free-air operation** from its 10 A condition on a 30×30 mm aluminum PCB. Its 1.34 V maximum forward drop is specified at 10 A and 25°C; 5 A values are typical, and neither qualifies the cold bound used here. The 1.5 V proposed drop budget gives a conservative approximately 5.98 W steady screening loss and requires effective θJA ≤6.69°C/W for an 85°C ambient /125°C junction target. The sheet's typical 80°C/W free-air value plainly does not meet that target. **D1 requires an engineered thermal path; ordinary perfboard is not accepted.** No such area or heatsink is allocated. D1/D2 bodies are TO-277A, approximately 6.5×4.6×1.1 mm; package size is not cooling area.

## Startup and current-sense correction

R1 10 mΩ is paralleled by R10 20 mΩ, both exact Vishay WSL2512 1% parts. Effective nominal resistance is 6.667 mΩ. Including initial tolerance and 75 ppm/K over 65 K, startup trip spans **4.434–10.659 A**, steady trip **5.912–9.136 A**, and reverse trip **0.148–0.761 A**. The upper startup threshold exceeds the head fuse's nominal 10 A; no fuse coordination is claimed. The circuit is a breaker, not a constant-current regulator. Both Kelvin taps must span the combined resistor network. Per-part losses at the 60 mV steady threshold are 0.365 W and 0.183 W before layout/temperature derating.

C2/C6/C7/C8 are four **47 nF, 100 V, 1% C0G** parts, nominal 188 nF. The minimum after 30 ppm/K over 65 K is 185.753 nF. With ADI's 60 µA maximum gate pullup, its simplified source-follower relation predicts at most **323.009 V/s**. R8 remains 22 kΩ only in the capacitor branch, not in series with the MOSFET gates. C3 remains gate-to-common-source. The relation is a screening model: nonlinear MOSFET charge, initial gate offset through R8, actual source/output ramp and converter interaction still need waveforms and SOA review.

U3 **TPS3760A012DYYR** is an adjustable UV, active-low open-drain supervisor, powered by PAN_INPUT. R12/R13=150 kΩ/10 kΩ sense that same node. RESET drives U2 EN; R14=499 kΩ supplements the module's nominal internal 1 MΩ pullup. C9=6.8 nF sets release delay; CTS is NC for minimum assertion delay. **E012 is an OV variant and must not replace A012**, even where a distributor calls it a parametric equivalent. [TI rev A](https://www.ti.com/lit/ds/symlink/tps3760.pdf) supplies the exact pin map and variant table.

Independent corners include reference 0.792–0.808 V, ±100 nA sense leakage, resistor initial/temperature terms, and ±1.5% of the 16 mV hysteresis voltage (TI's p21 example confirms this interpretation). U3 falls at **12.595–13.007 V**, rises at **12.846–13.268 V**, and releases after approximately **6.622–11.414 ms** for the stated capacitor/timing corners. Delay specifications depend on their stated overdrive and load conditions; assertion's 17 µs maximum applies at 20% overdrive, not arbitrarily close to threshold. Added EN capacitance and the high-value pullups are not timing-qualified.

During initial ramp, TI's maximum 2 ms startup after VDD reaches 2.7 V implies PAN_INPUT ≤3.346 V under the proposed slew bound, below the Pololu family's 3.5 V minimum. Below TI's 1.4 V power-on-reset bound the output is undefined; the converter is also below its minimum input. This sequencing argument is conditional on the actual slew and pullup/loading behavior. It is not proof that the module never produces a startup pulse. The module's 12 V variant also needs output voltage plus dropout; EN thresholds alone do not guarantee 12 V regulation.

The reproducible [screen](reports/calculations.json) assumes total branch input capacitance ≤500 µF, converter efficiency ≥80%, auxiliary input ≤5 mA, D1 drop ≤1.5 V and hot MOSFET-pair resistance ≤30 mΩ. None is measured. Worst enabled input demand uses the **minimum falling** threshold and 12.36 V×3.25 A output: 3.987 A conversion +0.162 A capacitor charging +0.005 A auxiliary = **4.153 A**, leaving **0.281 A** below minimum startup trip. At the 15 V source corner, available input is 13.337 V versus the maximum EN release 13.268 V: only **69 mV headroom**. This narrow margin is explicitly unresolved, not rounded into a robust startup claim. Lower efficiency, excessive capacitance/slew, cold diode drop or more wiring loss can reject this candidate. Calculations include deliberate failing scenarios for those bounds.

R4 is reduced to the existing 100 kΩ part: U1 UV recovery is 10.728–11.409 V behind D1, allowing the ramp to reach U3's threshold. U3 handles converter brownout; U1 remains the deeper input disconnect. Automatic UV/OV/EN recovery does not implement a persistent arm interlock. The servo's output-voltage contract remains 12 V; dropout and sustained operation at stand minimum still require actual module evidence.

## Fault states and handoff

| Event | Candidate action | Residual limitation |
|---|---|---|
| Valid source applied | U1 window/delay, slow ramp, then U3 enables U2 | Conditional startup bounds above; supply enable is not motion permission |
| Falling PAN_INPUT | U3 inhibits converter; deeper UV opens Q1/Q2 | Assertion delay and output collapse need waveform validation |
| Positive BUS surge | U1 OV opens Q1/Q2 | Cutoff is not a clamp; peak, gate charge, source energy and interruption SOA remain unknown |
| −42 V source with output charged | D1 blocks steady reverse path; D2/C4 mitigate local negative coupling | Must demonstrate −2 V protected-input and ≤55 V output acceptance bounds, including hot insertion |
| D1 short or D2 open | Reverse protection can fail | Not single-fault tolerant; legacy D8/fuse still receives no credit |
| D2 short | Candidate input is clamped to GND through D1 | Whole-head fuse clearing, diode heating and branch isolation are unqualified |
| D1 open | U2 feed lost | Shared BUS can remain powered; no service-isolation claim |
| Forward OC | U1 latches off (RETRY=GND) | Breaker threshold is input current; startup upper threshold and fuse coordination remain open |
| R10 open | Sense resistance reverts toward legacy 10 mΩ | Startup can nuisance-trip; independent netlist regression rejects omitted R10 |
| U3 wrong variant, RESET open or EN bypassed | Startup inhibit may fail | Native/variant regressions catch design errors, not physical single faults |
| Source removed / output charged | R9 bleeds PAN_INPUT; U1 reverse logic isolates some input backfeed | No safe discharge time: unknown Cin, signal injection and output backfeed |
| Servo braking / 12 V regeneration | No new output clamp or sink | 12.36 V static maximum leaves only 0.24 V to 12.6 V; PG is not adequate output OVP |
| Ground break, sense-route fault or MOSFET short | Protection can be defeated | No redundant safety or diagnostic-coverage claim |

No extra protection-board area, connector footprint, solder pad, power junction, trace current rating or thermal copper is allocated. The legacy 50.8×30 mm carrier board and its 2.5×10.2 mm pad placeholder cannot absorb this circuit by assumption. C1 alone is Ø8×11.5 mm versus the legacy U2 height reservation of 9.5 mm. U2's matching board outline is not a qualified interchangeable footprint.

The external electrical boundary stays BUS_HEAD_FUSED, GND and 12V_PAN. CAN and TTL can bypass this candidate; C3 BUS must never use U2 A4/B4 (PAN_INPUT). A separate harness owner records unallocated external BUS and return junctions. Future steps are an accepted source/transient envelope, actual startup/dropout/thermal evidence, output regeneration solution, then PCB placement/routing and carrier revalidation. No energization or ordering is authorized by this note.

Legacy claims in `cad/turret_boards.py` that every BUS part is ≥50 V and that D14 necessarily clamps before U2's limit remain unqualified. This namespace does not modify another author's frozen carrier files or turn those claims into validated facts.
