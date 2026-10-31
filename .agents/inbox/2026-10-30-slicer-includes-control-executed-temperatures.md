# Resolve included printer templates and inspect executable temperatures

On 2026-10-30, the first retained RS04 coupon slice on Bambu Studio
02.08.04.57 (snap revision 8) returned exit 0 and `Success.`, estimating 172.43 g,
65.17 m and 386.611 minutes. The PA6-CF profile declared 275°C and the bed 100°C.
No printer operation occurred. The [rejected archive](../../research/retained-fit-jobs/rejected-7b67f03.zip)
retains the original job, profiles, source mesh, logs and executable G-code.

Command: `timeout --kill-after=10s 300s python tools/package-fit-job.py --out build/rs04-fit-job-7b67f03`
from commit 7b67f03. Inspection of actual `slice/out/plate_1.gcode` found only
`M109 S205` before object deposition; no 275°C command appeared before the final
heater-off command. **This slice is rejected and must not be printed.**

Cause: the installed `Bambu Lab P1S 0.4 nozzle` profile names five `include`
templates. `cad/print_slicing._profile` and upstream `cadagent.slicer.flatten`
previously followed `inherits` only, retaining generic base startup G-code.
The official [Bambu preset loader](https://github.com/bambulab/BambuStudio/blob/79df7ae309be398ed30c9f397c13c9911c2edc57/src/libslic3r/PresetBundle.cpp)
applies the inherited configuration, included templates in order, then explicit
child settings. The installed startup template uses the selected filament's
initial temperature. The project resolver now preserves that dependency and
hashes every included file. Upstream tracking: [cad-agent #92](https://github.com/Valpatel/cad-agent/issues/92).

Corrective rule: keep resolved settings, template hashes, actual executable
identity, raw result/log, and sliced archive together. Reject missing/cyclic
includes and changed template bytes. Inspect actual thermal waits before object
extrusion and actual machine/material/process mapping; labels and successful
estimates do not prove printable machine commands. Do not patch generated
G-code with an isolated temperature substitution.

The same first run demonstrated that `--orient 0` does not prevent `--arrange 1`
from rotating the part in XY. Compare the sliced mesh and full transform with
the source, preserving the parent +Z layer normal and documenting in-plane
rotation. Do not claim identical raster direction to a future parent print.

Limits: these checks do not qualify physical printer calibration, dry filament,
adhesion, bridge quality, support removal or motor mounting. Startup/end purge,
wipe and homing motion are distinct from object toolpath bounds. The original
eight RS04 mounting-support failures remain unresolved. Regression coverage:
`tools/test-print-provenance.py` and `tools/test-fit-job.py`.
