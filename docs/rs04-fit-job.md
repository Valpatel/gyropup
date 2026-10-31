# RS04 unpowered fit-observation slice

This job prepares one parent-derived motor-ring coupon for dimensional and
surface-quality observation. **It does not approve mounting, preload, tightening
torque, strength or powered operation.** The source candidate still has eight
failed mounting-support checks, including two on this coupon. Issues
[#116](https://github.com/Valpatel/gyropup/issues/116) and
[#124](https://github.com/Valpatel/gyropup/issues/124) remain open.

The ordered PRO3115 flywheel motors need their own interface geometry and fit
specimens; this RS04 package cannot qualify that motor family.

## Trial process and limits

The declared trial uses a P1S with a **0.4mm hardened nozzle**, Bambu PA6-CF,
0.20mm layers, four walls, 100% zig-zag infill, textured PEI, and support disabled.
This is a new process trial, not an established leg-print recipe. Record the
actual nozzle, plate, calibration, filament lot and drying/feeding conditions
before printing. The machine profile does not prove what is installed.

The coupon preserves its parent's outer-face-down layer direction. Bambu may
rotate it within XY; the receipt records the actual rigid placement and verifies
the sliced mesh. A future parent print can have different raster direction,
thermal history, warping and support conditions. Successful coupon measurements
do not transfer automatically to the whole frame.

The package checks the actual P1S profile's256×256mm area,250mm height and
lower-left18×28mm exclusion. Both transformed mesh and object nozzle paths are
checked; printer startup/end homing, purge and wipe moves are separate vendor
operations. No printer was connected or started by generation.

## Inspect and measure

The retained critical-layer image is drawn from executable G-code, with bridge
deposition red and overhang walls orange. The counterbore roofs bridge at Z8.8mm.
The two outer-edge pockets clipped from the parent's blind stop-pin bores bridge
at Z23.2mm. Support is disabled and no support deposition is accepted. This
does **not** prove that PA6-CF bridges will produce usable screw-seat surfaces.

Inspect the bearing seat and lip, all ten motor holes and counterbores, dowel
holes, and the outer pocket roofs. Record sagging, strings, incomplete walls,
warping and first-layer distortion before any dimensional conclusion. Measure
counterbore depth and remaining grip at every screw location; a nominal4.4mm
penetration leaves only0.6mm to the drawing's5mm usable-thread minimum and is
not a manufacturing tolerance budget. Do not use screw torque to pull a warped
or obstructed part onto the motor. Unresolved receiver support remains a
separate design failure even if a printed coupon fits by hand.

Keep a record of printer/nozzle/plate, slicer/job hashes, filament lot and drying,
calibration, measured seat diameters/depths, grip at all ten locations, flatness,
surface defects and photos. Physical measurements are currently absent.

## Reproduce and verify

Use cad-agent commit`2ad426943ce2c7232875e105e50810849f9a3e5e`, its`src/`
directory on`PYTHONPATH`, and the lightweight versions in
[`tools/fit-job-requirements.txt`](../tools/fit-job-requirements.txt). Generation
also needs Bambu Studio. The current installed build is02.08.04.57, snap revision8.
Keep input/work directories visible under home; the snap cannot read ordinary
`/tmp` or hidden project directories.

```sh
python tools/test-fit-job.py
python tools/test-print-provenance.py
timeout --kill-after=10s 300s python tools/package-fit-job.py --out build/new-rs04-fit-job
python tools/package-fit-job.py --verify build/new-rs04-fit-job
```

Generation refuses an existing output directory and a stale source receipt.
Verification does not run Bambu or CAD. It checks retained byte identities,
source/recipe membership, actual sliced geometry/placement, machine and filament
mapping, G-code thermal waits, paths, and raw time/material results. Keep the
whole generated directory together, including resolved settings, raw logs/results,
standalone G-code and the sliced3MF containing the same G-code.

The [first rejected run](../research/retained-fit-jobs/README.md) demonstrates why
these checks matter: the old inheritance-only resolver selected205°C startup
despite a275°C filament label. It is diagnostic evidence and must not be printed.
The fixed resolver includes the installed vendor templates; no generated G-code
is manually patched.
