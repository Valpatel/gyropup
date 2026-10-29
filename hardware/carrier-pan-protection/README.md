# PAN supply cutoff — circuit candidate

**A complete 16-component circuit candidate is available for review. It is unselected and unqualified: do not fabricate or energize it.** It adds an LTC4368 active cutoff before a 60 V Pololu PAN converter, with a common-source MOSFET pair, input-current sense, UV/OV dividers, controlled gate ramp and local capacitance. It protects only the U2 feed; the shared head BUS remains separate.

Tracking [issue83](https://github.com/Valpatel/gyropup/issues/83) / [PR84](https://github.com/Valpatel/gyropup/pull/84), following [PR82's requirements](../../research/protection/carrier-input-protection.md). No current catalog selection, carrier geometry, connector or installed circuit is changed.

![PAN supply cutoff circuit candidate, including MOSFET body diodes and connected protection branches](pictures/pan-cutoff.svg)

The preview fits this page; pinch or use browser zoom to inspect the details. The original vector drawing retains its full A3 paper dimensions.

- <a href="pictures/pan-cutoff.svg" download>Download original SVG</a> and [native editable KiCad schematic](pan-cutoff.kicad_sch), with local [symbol library](candidate.kicad_sym).
- [Exact pins and carrier interfaces](pins.md); manufacturer facts and project-assigned module pad IDs are distinguished.
- [Candidate BOM](candidate-bom.csv), [dated availability and primary sources](availability.json). Several passive offer quantities remain unresolved; the 127 kΩ and 22 kΩ candidates are normally nonstock. This is not a ready-to-order list.
- [Fault-state review and remaining release gates](fault-review.md), [numerical screening](reports/calculations.json), [KiCad-exported netlist](reports/netlist.xml), [ERC report](reports/erc.rpt), [source/artifact receipt](reports/receipt.json).

The power path, common gate/source capacitor, gate-ramp branch and each UV/OV/SHDN divider use actual connected KiCad wires. Local labels connect the Kelvin sense taps and distributed BUS/ground. Every manufacturer lead is exported, including duplicate MOSFET and module pins. Q1/Q2 use authored enhancement N-MOS graphics with visible intrinsic body diodes: both source anodes face inward and drain cathodes face outward. A separate graphical regression checks this orientation, since ERC alone cannot detect a misleading symbol. This checkpoint intentionally provides no PCB or fabrication files.

## Reproduce

Use Python 3 and pinned KiCad CLI 10.0.1 (existing repository install). No new packages or board solver required:

```sh
python hardware/carrier-pan-protection/build.py
python hardware/carrier-pan-protection/test_circuit.py
python hardware/carrier-pan-protection/verify.py
```

The build regenerates the native schematic, local library, BOM, ERC, XML netlist and SVG from `circuit_design.py`; it captures source and artifact hashes. `verify.py` checks an independent pin/net contract against **KiCad's exported connectivity**, not the generator's intended net dictionary. Tests export genuinely corrupted native schematics: flipped Q2, swapped current-sense pins, a hidden power pin creating an implicit global net, bypassed cutoff and wrong hot-swap capacitor return. Additional faults check an omitted ground pad, wrong part variant/function and a reversed body-diode graphic that would otherwise leave the netlist unchanged.

Open `pan-cutoff.kicad_pro` / `.kicad_sch` in KiCad to inspect/edit. The files are native and portable; committing permanent changes requires updating `circuit_design.py` then rebuilding so the generator does not overwrite them. `hardware/fuse-board/sexp.py` is the existing shared parser; no fuse-board source is modified. SVG is the committed rendered view. Optional PDF export: `kicad-cli sch export pdf -o /tmp/pan-cutoff.pdf hardware/carrier-pan-protection/pan-cutoff.kicad_sch`.

## What this checkpoint establishes

The candidate has 62 package leads across 16 parts, 11 connected nets and 4 NC groups. ERC checks pin-level consistency; it cannot certify thermal behavior, physical routing, protection timing or safety. UV/OV automatically recover even with forward-overcurrent latch mode. The circuit therefore **does not implement a persistent arm interlock**.

The major blockers are still real: unknown positive surge envelope;−42 V reversal exceeds the controller limit;12 V servo regeneration/overshoot is not protected; input startup can trip under the conservative stalled-load scenario; MOSFET SOA and converter/C1 thermal/ripple are unqualified. No space is allocated for the extra board; the 8×11.5 mm capacitor exceeds the existing 9.5 mm U2 height reservation. A mechanically complete carrier cannot be inferred from this schematic.
