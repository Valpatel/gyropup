# Read actual collection geometry before inferring an isolated default

On2026-11-10, consumer mapping for issue193 briefly inferred an85.65mm wheel
radius from `fivebar.botwheel`'s isolated default. Actual accepted collection266
was checked before any source, clearance record or asset was changed:

```text
L.wheel_tyre X bounds: -127 .. 127 mm; Y span:64 mm
R.wheel_tyre X bounds: -127 .. 127 mm; Y span:64 mm
sampled STL Z span:253.28977966308594 mm
```

The actual collection uses the254mm D69 envelope. `robot_view.collect` calls
`build_body._layout`; its body dependencies use `body_params._fivebar`, which
applies `D69_WHEEL_CAD` through the existing wheel adapter. The isolated leg
default is not the effective body-collection configuration. The hypothesis was
retracted before edits; nominal127mm and the existing source clearance
arithmetic were not changed.

Corrective rule: trace the complete producing call path and verify actual
bound mesh bytes before changing an inferred dimension. Carry effective
overrides with conversion provenance. A sampled axis extent can miss a curved
extreme; do not silently replace the source radius with half an approximate
STL bounding span. This evidence establishes presentation identity, not tyre
manufacturing dimensions, contact, fit or drop qualification.

## Effective overrides also invalidate inherited procurement labels

Independent review [193#6777689267](https://github.com/Valpatel/gyropup/issues/193#issuecomment-6777689267)
found the composed current guide still called the collected wheel BotWheel and
mapped its hub/tyre to the retained `buy/odrive-botwheel` row (BW0124,2200g).
The collected D69 envelope is not that ordered part. On2026-11-10 the current
mapper was changed to leave every collected wheel's procurement unresolved;
the accepted266 mapping names the source-derived254×64mm envelope and keeps
ordered-SKU and physical-measurement flags false. The old BOM and already
published historical guides remain unchanged.

```text
python3 -B tests/site/assembly/test_robot_guide.py -q:5 PASS
python3 -B tests/site/assembly/test_robot_recipe.py -q:8 PASS
test_robot_current_print_match.py --collection-folder <accepted266> -q:6 PASS
export_robot_guide.py --collection <accepted266>/collection.json --out <fresh-candidate> --check:
PASS233 source-bound outputs; all4 hub/tyre mappings unresolved; no legacy buy key
```

Rule: source overrides must follow through to current human-facing catalogue
labels. Reusing a logical component name does not prove bought-part identity.
Preserve archival procurement as archival; do not select a substitute supplier
or transfer old mass/fit acceptance from a differently sized wheel. These
checks establish current metadata truthfulness, not wheel procurement approval.
