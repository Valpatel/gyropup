# Include charged-output differential stress and enabled-load startup corners

2026-10-29, Gyropup issue87 / PR88, continuing the reviewed but unqualified PAN circuit candidate.

**Evidence.** Source inspection of `cad/turret_boards.py:139–141` and `docs/turret-wiring.md:141,241,441–443` showed D8 is a BUS-to-GND shunt after the head fuse, not a series reverse blocker. LTC4368 rev C separately limits VIN to−40 V and VIN−VOUT to−60 V. A−42 V source with+42 V retained output produces−84 V differential; at the proposed55 V output acceptance bound it is−97 V. Its negative-hot-insertion guidance also requires overshoot mitigation beyond−20 V. No fuse-clearing or transient evidence justified crediting D8.

The previous10 mΩ sense choice had2.956 A minimum startup trip, already below a3.25 A nominal input scenario before capacitor charging. The revised candidate explicitly converts3.25 A at12.36 V output to input demand using the minimum enabled input and80% assumed efficiency. On2026-10-29:

```sh
python hardware/carrier-pan-protection/build.py
python hardware/carrier-pan-protection/test_circuit.py
```

produced zero KiCad10.0.1 ERC violations and24 passing tests, including nine deliberately corrupted native-schematic exports. The source-bound calculation reports4.153 A total startup demand versus4.434 A minimum trip, but only69 mV enable headroom at the15 V source corner, and5.98 W series-diode loss under the proposed worst-case bounds. Those results expose unresolved conditions; they are not startup or thermal qualification.

**Cause.** A single absolute-voltage headline ignores energy stored at another pin. A nominal current trip ignores converter efficiency, enabled voltage, output tolerance, startup threshold and charging current. The legacy shunt diode's purpose was mistaken for demonstrated fuse coordination. A further sourcing trap appeared: DigiKey listed TPS3760E012 as a parametric equivalent for TPS3760A012, while TI's variant table distinguishes OV from UV. The function matters even if package and threshold match.

**Corrective rule.** Enumerate charged and uncharged fault states, every differential rating, source impedance/energy unknowns, and actual series/shunt topology. Derive input load and inrush separately; sequence EN deliberately and test the limits of the model. Preserve explicit conditional bounds and failed alternatives. Exact MPN/function and physical pin maps belong in the independent exported-net contract. Do not allocate nonexistent PCB space or call a10 A rating on an aluminum board a perfboard rating.

**Regression and limits.** `static_screen` rejects excessive Cin, low efficiency, higher diode drop/path resistance, excessive slew, charged reverse stress and a missing ramp capacitor. Native controls reject reversed series/clamp diodes, bypassed EN and missing parallel sense resistor; the independent MPN contract rejects the OV supervisor variant. The public schematic/receipt bind30 parts and104 leads. These tests do not establish actual slew, diode clamp energy, cold drop, thermal path, converter dropout, MOSFET SOA,12 V regeneration, or physical single-fault tolerance. Hardware remains unselected and unqualified. Manufacturer links, exact numerical assumptions and dated offers are in the candidate `fault-review.md`, `pins.md` and `availability.json`.

## Review correction: startup timing depends on the installed delay network

Independent review of `8e00df1` found that TPS3760's 2 ms startup limit explicitly assumes CTR/MR open; p9 footnote4 says a CTR capacitor adds time. The candidate installed C9=6.8 nF but the calculation omitted its delay. Adding the prior calculated maximum 11.414 ms gives a conservative 13.414 ms and approximately7.033 V at the proposed ramp, invalidating the former3.346 V sequencing result for that topology. This was a real unsupported calculation, not evidence that a physical startup pulse occurred. [Review finding](https://github.com/Valpatel/gyropup/pull/88#discussion_r4412960913).

The optional C9 is removed and U3.9 is explicitly NC; no required release dwell existed. `supervisor_timing()` now binds the open-pin condition, rejects unreviewed connected timing networks and accounts for the prior capacitor when restored by a negative control. A second regression changes the native CTR NC to a connected net and requires the exported contract to reject it. The corrected candidate has29 parts,102 leads,14 nets and12 NC groups;26 tests pass, including ten real native corruption exports. Source/artifact receipts are regenerated.

Even with CTR open, the datasheet's timing test uses a10 kΩ pullup to5.5 V,10 pF load and1 V/µs slew. This circuit has different pullups, unknown EN capacitance and a much slower ramp. The2 ms application bound therefore remains an unqualified acceptance assumption. Rule: carry the full timing test configuration into calculations; never reuse a headline delay after changing its programmed network, and never promote a conditional static screen into a measured sequencing guarantee.
