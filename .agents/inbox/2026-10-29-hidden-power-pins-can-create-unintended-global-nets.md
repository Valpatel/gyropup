# Check the exported netlist: hidden power pins can rename or join supply nets

2026-10-29, Gyropup issue83 / PR84, native KiCad10.0.1 PAN-cutoff candidate.

**Evidence.** Initial generation placed the module's duplicate VIN leads at the same symbol coordinate, with both typed `power_in` and the duplicate hidden. Running:

```sh
kicad-cli sch erc --severity-all --exit-code-violations -o /tmp/pan-erc.rpt hardware/carrier-pan-protection/pan-cutoff.kicad_sch
```

reported `Found 1 violations`, with `[multiple_net_names]: Both VIN and PAN_INPUT are attached to the same items; VIN will be used in the netlist`, pointing to U2 hidden pinB4 and the PAN_INPUT label. There were0 errors but1 warning; checking only error count would miss it. KiCad's actual XML export renamed the intended protected node. This was caught before any PCB or energized build.

**Cause.** Hidden power pins have implicit global connectivity semantics; they are not merely invisible repeated terminal labels. A renderer or generator-side net dictionary can look correct while the EDA export connects something else.

**Correction.** The candidate represents each physical lead, but stacked duplicates are passive with the first visible pin providing the power-in/out type. Its independent `verify.py` contract requires the exact pin/net membership of16 components and62 leads, including all4 module ground pads, separate VIN/VRP and separate PG/EN. ERC now reports0 violations. `test_circuit.py::test_native_hidden_power_pin_implicit_net` mutates the committed native symbol back to hidden `power_in`, exports it with KiCad and requires the independent contract to reject the resulting netlist. Other actual native mutations flip the output MOSFET, reverse current-sense pins, bypass the cutoff and miswire the hot-swap capacitor return.

**Rule.** Treat generated native EDA output as executable connectivity. Export with the real EDA tool and compare package pin identities and actual nets to an independently transcribed manufacturer/interface contract. Run all-severity ERC; don't suppress a naming warning merely because the picture looks reasonable. Use stable local module names when importing another design's helpers: this test initially imported the adjacent fuse-board's generic `design.py`; the candidate source is now uniquely named `circuit_design.py`.

**Limits.** These checks establish circuit connectivity and artifact provenance, not analog waveforms, tolerance coverage, PCB layout, component authenticity, manufacturability or safety. Current/source envelopes and mechanical fit remain unqualified. Primary pin sources and explicit unknowns are in `hardware/carrier-pan-protection/pins.md` and `fault-review.md`.

Independent visual review also found that correct D/S/G terminal boxes hid the body-diode direction and scattered net labels made the divider/gate branches difficult to audit. The revised native schematic draws source-anode/drain-cathode diodes and connected branch wires, while the independent exported contract remains 62 leads/11 nets. A deliberately reversed diode graphic now fails a separate symbol-geometry test even though it would not change ERC/net connectivity. This checks the drawing’s stated direction, not transistor behavior or physical qualification.
