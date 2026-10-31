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
features. Here the frozen recipe/CAD remain unchanged and the documented fallback
uses numbered slot positions, with every actual width and uncertainty left blank.

Limits: this is a retained unpowered dimensional trial with an explicit missing-
label limitation, not a calibrated gauge or print release. Eight open slots in
CAD/toolpath views do not prove printed dimensions, surface quality or safe motor
fit. No motor measurements, mounting, retention or thread-gauging approval follow.
