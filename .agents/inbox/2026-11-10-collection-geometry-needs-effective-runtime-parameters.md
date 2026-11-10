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
