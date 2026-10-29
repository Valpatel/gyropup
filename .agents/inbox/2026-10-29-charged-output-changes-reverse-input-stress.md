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
