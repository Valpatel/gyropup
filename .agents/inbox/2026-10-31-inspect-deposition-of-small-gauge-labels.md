# Inspect deposited features before calling a gauge labelled

On 2026-10-31, the source-bound shaft-survey gauge slice completed successfully
with an exact preserved mesh, valid P1S placement and verified temperature/feed
commands. Nevertheless, most raised text disappeared from the actual toolpaths.
The labels are 0.5 mm high with small font strokes; this unchanged 0.4 mm nozzle
recipe did not reproduce them legibly. The geometry receipt's twelve passes
establish geometry, not feature deposition or readability.

Evidence (owned `gyropup-survey-fit-job` checkout, no printer operation):

```
PYTHONPATH=/home/scubasonar/Code/cad-agent-fit-jobs-runtime/src \
  timeout --kill-after=10s 300s \
  /home/scubasonar/Code/gyropup-fit-jobs/build/fit-check-env/bin/python \
  tools/package-survey-fit-job.py --out exports/turret/shaft-survey-fit-job
```

The first run at `bb3f5a1` returned success, 8.4 g / 3.17 m / 27.107739 minutes.
`job.json` recorded only eleven deposition segments at each upper layer,
Z=3.2 and 3.4 mm. The actual G-code plot showed small fragments rather than eight
width labels. Source and sliced meshes remained identical; changing mesh identity
checks would not detect feature omission during toolpath generation. The final
wrapper uses the actual plate-top layer Z=3.0 in its four-panel witness.

Corrective rule: inspect the actual deposited paths at functional feature layers,
including raised/recessed markings and narrow walls, even after geometry and
process checks pass. Retain the G-code and image. Never infer printed label
legibility from text in CAD or silently assume the recipe preserves small
features. Reject avoidable missing-label results instead of accepting a labelled
tool without its markings. The unchanged first job is archived as rejected;
the replacement uses 5 mm bold text from an explicit hash-bound font file while
preserving slots, base and overall height. Its generator lives in the independent
research-tool directory, with complete source/font/artifact binding.

The replacement passed the original twelve remote CAD checks. Actual toolpaths
visibly show all eight widths and SURVEY ONLY. The wrapper checks every glyph's
centerline extent on both upper layers and rejects eighteen controls that remove
each label in turn, plus the actual original small-text slice. A provisional
0.30 mm centerline-edge allowance rejected a legible pointed glyph with a
0.33782 mm inset; the screen explicitly allows one declared 0.4 mm nozzle diameter
for finite-bead inset and rounded extrema. Recorded numerical extents and direct
visual reading remain separate evidence; neither certifies exact printed lettering.

Limits: this is a retained unpowered dimensional trial, not a calibrated gauge
or print release. Every actual width and uncertainty remains blank. Eight open slots in
CAD/toolpath views do not prove printed dimensions, surface quality or safe motor
fit. No motor measurements, mounting, retention or thread-gauging approval follow.
