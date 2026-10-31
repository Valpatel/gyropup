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

The declared trial uses a P1S with a **0.4 mm hardened nozzle**, Bambu PA6-CF,
0.20 mm layers, four walls, 100% zig-zag infill, textured PEI, and support disabled.
This is a new process trial, not an established leg-print recipe. Record the
actual nozzle, plate, calibration, filament lot and drying/feeding conditions
before printing. The machine profile does not prove what is installed.

Bambu's [PA6-CF preparation guidance](https://bambu-lab-jp.myshopify.com/en/products/pa6-cf)
(checked 2026-10-30) calls for drying at 80°C for 8–12 hours and dry feeding below
20% RH. It lists hardened 0.4/0.6/0.8 mm nozzles, preferring 0.6 mm, a 260–290°C
nozzle range, and an 80–100°C bed with glue. This trial retains 0.4 mm, 275°C and
100°C. Confirm the installed nozzle and extruder wear path; record drying,
feeding and measurement conditioning because moisture affects dimensions and
stiffness. Installed hardware and material conditioning remain unknown.

Trial revision 2 caps the faster deposition roles at 99 mm/s, retaining slower
wall/bridge settings where applicable, to respect the manufacturer's below
100 mm/s guidance. The verifier checks commanded feed on positive-extrusion
object moves, including modal feed inherited from earlier commands. Travel is
separate; acceleration is not used to excuse an excessive deposition command.
The previous temperature-correct diagnostic requested up to 250 mm/s for gap
infill and is not the final trial recipe.

The coupon preserves its parent's outer-face-down layer direction. Bambu may
rotate it within XY; the receipt records the actual rigid placement and verifies
the sliced mesh. A future parent print can have different raster direction,
thermal history, warping and support conditions. Successful coupon measurements
do not transfer automatically to the whole frame.

The package checks the actual P1S profile's 256×256 mm area, 250 mm height and
lower-left 18×28 mm exclusion. Both transformed mesh and object nozzle paths are
checked; printer startup/end homing, purge and wipe moves are separate vendor
operations. No printer was connected or started by generation.

## Inspect and measure

The retained critical-layer image is drawn from executable G-code, with bridge
deposition red and overhang walls orange. The counterbore roofs bridge at Z=8.8 mm.
The two outer-edge pockets clipped from the parent's blind stop-pin bores bridge
at Z=23.2 mm. Support is disabled and no support deposition is accepted. This
does **not** prove that PA6-CF bridges will produce usable screw-seat surfaces.

Inspect the bearing seat and lip, all ten motor holes and counterbores, dowel
holes, and the outer pocket roofs. Record sagging, strings, incomplete walls,
warping and first-layer distortion before any dimensional conclusion. Measure
counterbore depth and remaining grip at every screw location; a nominal 4.4 mm
penetration leaves only 0.6 mm to the drawing's 5 mm usable-thread minimum and is
not a manufacturing tolerance budget. Do not use screw torque to pull a warped
or obstructed part onto the motor. The axial-support checks remain unresolved
even if a printed coupon fits by hand. The 4 mm engagement and 0.5 mm reserve
limits are declared geometric screens, not thread-strength or torque qualification.

Keep a record of printer/nozzle/plate, slicer/job hashes, filament lot and drying,
calibration, measured seat diameters/depths, grip at all ten locations, flatness,
surface defects and photos. Physical measurements are currently absent.

## Reproduce and verify

Use cad-agent commit `2ad426943ce2c7232875e105e50810849f9a3e5e`, its `src/`
directory on `PYTHONPATH`, and the lightweight versions in
[`tools/fit-job-requirements.txt`](../tools/fit-job-requirements.txt). Generation
also needs Bambu Studio. The current installed build is 02.08.04.57, snap revision 8.
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
standalone G-code and the sliced 3MF containing the same G-code.

The [first rejected run](../research/retained-fit-jobs/README.md) demonstrates why
these checks matter: the old inheritance-only resolver selected 205°C startup
despite a 275°C filament label. It is diagnostic evidence and must not be printed.
The fixed resolver includes the installed vendor templates; no generated G-code
is manually patched.
