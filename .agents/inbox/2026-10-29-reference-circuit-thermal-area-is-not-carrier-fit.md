# Keep extended protection and thermal claims bound to the complete reference circuit

2026-10-29, Gyropup issue91 / PR92, after the candidate-B circuit review. The preferred next direction is a complete LTC4359 Figure 10 front end rather than its bare controller; no circuit or geometry was changed by this comparison.

**Evidence.** The [dated comparison and primary links](../../research/protection/carrier-practical-architecture.md) show a −42 V source and +55 V charged node impose 97 V externally. Bare LTC4359's −40 V input limit fails by 2 V; TI alternatives' 85/88 V differentials fail by 12/9 V. ADI Rev F Figure 10 instead uses a floating VSS return, sense resistor and clamp network for an extended reverse-input application. Its application diagram does not remove the need to check actual clamp currents, temperature and pin peaks.

```sh
python research/protection/calculate_practical_architecture.py --check
python -m unittest discover -s research/protection -p 'test_practical_architecture.py' -v
```

The bounded arithmetic gives 0.953652 W at a proposed 60 mΩ hot-FET bound and 41.944 K/W required for a chosen 125°C target at 85°C ambient. Infineon's 40 K/W example uses 6 cm² copper on 40×40 mm FR4, while the minimal-footprint condition is 62 K/W. Eight tests pass, including excessive resistance, raw-controller differential rejection, old 16 V module identity, missing/true qualification flags and source-receipt binding. Neither thermal number is a measured carrier result. The footprint alone cannot predict cooling, and the 40×40 mm test board is not a proven minimum design area.

**Cause.** A headline rating omits external reference topology and test conditions. Replacing a lossy diode with a nominally low-resistance FET can hide initial body-diode conduction and gate timing. Treating a thermal characterization board as allocated carrier space can turn a promising electrical calculation into an unsupported mechanical claim.

**Corrective rule.** Preserve all parts and reference nodes that enable an extended rating; calculate charged-pin differences before acceptance. Keep enhanced-state voltage/heat screens distinct from startup, negative insertion, clamp energy and regulation. Coordinate a real contour, heights, thermal path and cable zones before claiming fit. Carry supplier scarcity and exact variant differences into the decision.

**Limits.** No new native schematic, source transient model, PCB layout, thermal solve, waveform or physical test was performed. Clamp grade equivalence, startup, output regeneration and production supply remain unqualified. The source-bound comparison deliberately reports dynamic results as null and every qualification flag false; it does not certify an implementable assembly.
