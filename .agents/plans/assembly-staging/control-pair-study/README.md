# Ask the two missing motor-arrival questions

The capped [study 264](../native-264/README.md) completed 42 of 90 probes, including
current outward arrivals, but reached no old-order or wrong-side diagnostic.
This [explicit selection](selection.json) chooses exactly two unperformed query
identities from the unchanged [full plan](../pair-study/plan.json): the old motor
arrival through an installed left hip frame, and the opposite motor arrival
through the left cheek. Directions, travel, source geometry and full installed
sets remain byte-bound to their original queries. No new path/order is generated.

The [selected-query projection](selected-queries.json) records two selected and
88 unselected IDs, with full-plan and effective query-plan hashes. The original
1126 predecessor rows/1052 CAD exclusions remain in the complete retained plan.
The other queries keep their prior checked/unchecked status. The hip/cheek final
seating overlap is separately [classified against retained baseline contacts](../native-264/seat-classification.json);
no overlap exemption or physical fit approval follows.

The [pure preflight](pure-preflight.json) ran the actual CLI while forbidding
CAD/OCP/VTK imports. The [source receipt](plan-source.json) preserves actual
experimental core 5c29 and the exact helper/input/selection hashes. It does not
repin to a newer release. Reproduce with existing original 263 bytes:

```text
python3 -B prepare.py <product-checkout> <original 263-frame-output> <exact-clean-5c-core> <fresh-output>
```

`robot_native_pairs.py --query-selection <file> --query-selection-sha <sha256>`
retains full `plan.json`, exact selection bytes and a separate `query-plan.json`.
Unknown/duplicate IDs, changed full-plan/direction hashes and mismatched case
labels fail before native load. Native execution uses the same existing engine,
arguments, sample limit and preserved progress protocol. Incomplete or non-clear
selected results return nonzero; 88 unselected queries gain no verdict.

Tests cover actual CLI failure/selection/byte guards, immutable directions and
installed contexts, external stop/storage prefixes, plus explicit simple native
boxes for selected blocked/clear/seat/sample-cap behavior. Those boxes are not
product geometry evidence. An exact short outer-cap source/action packet still
requires independent review before either product probe runs. No CAD, printing
leg, tolerance, source collection or historical guide is changed.
