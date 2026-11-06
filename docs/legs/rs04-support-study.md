# RS-04 mounting support: eight ring comparisons

Eight authored support-ring concepts have completed a nominal contact and clearance
comparison against the actual RS-04 manufacturer solids. **Mounting acceptance
remains open in [issue #116](https://github.com/Valpatel/gyropup/issues/116).**
These files are research geometry, not selected hardware or a fabrication release.
The existing [eight mounting-support failures](rs04-mounting-fit.md) remain unchanged.

## What the contact investigation found

The motor has ten output-side mounting holes. At two positions, native −15° and
165°, an adjacent factory-retainer recess interrupts the motor-side support beneath
the printed screw stack. Its factory screw head is 0.21 mm below the mounting plane.

| Projected M4 screw-head footprint outside the clearance bore | Nominal area |
| --- | --- |
| Complete annulus, Ø7 outside / Ø4.5 inside | 22.5802 mm² |
| Supported area at each of the two interrupted positions | 19.0810 mm² |
| Unsupported area at each interrupted position | 3.4992 mm² |
| Supported area at each of the other eight positions | 22.5802 mm² |

These are geometric face-intersection areas. They are not pressure distributions,
bolt-preload limits or strength fractions. The older 2.5 N·m instruction has been
withdrawn from current documentation and the assembly generator; no replacement
mounting torque has been established from manufacturer or joint-validation evidence.

## Inspect the comparison rings

Each authored ring has ten Ø4.5 lug holes on PCD106 and two provisional Ø5.3 dowel
clearances. The thicknesses correspond to 0.080 in and 0.125 in stock. The
[research method and stock source](../research/rs04-support/README.md) retain the
exact assumptions. Open a STEP preview to orbit or zoom the complete ring.

| Outside / inside diameter (mm) | Thickness (mm) | Motor contact (mm²) | Area without motor backing (mm²) | Model |
| --- | --- | --- | --- | --- |
| 118 / 80 | 2.032 | 5,505.66 | 200.51 | [STEP](../research/rs04-support/results/od118-id80-t2.032.step) |
| 118 / 80 | 3.175 | 5,505.66 | 200.51 | [STEP](../research/rs04-support/results/od118-id80-t3.175.step) |
| 118 / 94 | 2.032 | 3,592.43 | 200.51 | [STEP](../research/rs04-support/results/od118-id94-t2.032.step) |
| 118 / 94 | 3.175 | 3,592.43 | 200.51 | [STEP](../research/rs04-support/results/od118-id94-t3.175.step) |
| 120 / 80 | 2.032 | 5,819.49 | 260.53 | [STEP](../research/rs04-support/results/od120-id80-t2.032.step) |
| 120 / 80 | 3.175 | 5,819.49 | 260.53 | [STEP](../research/rs04-support/results/od120-id80-t3.175.step) |
| 120 / 94 | 2.032 | 3,906.26 | 260.53 | [STEP](../research/rs04-support/results/od120-id94-t2.032.step) |
| 120 / 94 | 3.175 | 3,906.26 | 260.53 | [STEP](../research/rs04-support/results/od120-id94-t3.175.step) |

All eight rings have exact positive contact with the mounting plate. Across the
complete comparison there are **472 required relations: 168 exact queries and
304 separation bounds**. No nominal interference was reported. Every ring includes
all 43 manufacturer solids at their source pose, plus the actual authored leg
output adapter and dyno hub at eight clock angles each. Manufacturer motion
ownership is not inferred, and eight poses do not establish continuous-motion or
loaded clearance. The closest exact nominal gap to either authored rotating part
is 8.25 mm across these comparisons.

A separation bound is explicitly marked `exact: false` in the report. It proves
nominal apart status under the recorded 0.01 mm touch/broad-phase policy; it is not
an exact measured surface clearance or a manufacturing allowance. Possible contact
pairs retain exact geometry checks. Unsupported face area can remain under a ring:
its capacity to distribute load across that area is a separate engineering question.

## What must happen before selecting a ring

1. Establish the actual motor mounting faces, screw lengths, usable thread and
   manufacturing tolerances from the arriving hardware. Record the intended
   tightening/preload basis and the motor casing/thread limits.
2. Evaluate local load transfer, contact opening, ring bending, printed compression
   and creep. The existing linear frame FEA does not model bolt preload or local
   contact and cannot qualify this interface by itself.
3. Model the selected ring's pocket in the actual frame and fixture. The comparison
   assumes ring thickness replaces equal printed thickness, retaining 15.6 mm
   nominal total grip and 4.4 mm screw penetration. **That replacement pocket and
   complete redesigned stack have not been implemented or accepted.**
4. Recheck full assembly, dowels, tool access, motion, tolerances and source-bound
   print specimens, then record unpowered physical observations before larger prints.

The separate [RS-04 coupon job](rs04-fit-job.md) represents the existing corrected
parent candidate. It does not include one of these rings or validate a ring pocket.
The full leg's frame/bearing, wheel, cable and load-case work remains open.

## Evidence and reproduction

- [Complete machine-readable comparison](../research/rs04-support/results/probe.json).
- [Producer, method and integrity-check command](../research/rs04-support/README.md).
- [Current parent mounting receipt](../exports/leg/rs04-mounting-fit/checks.json).

The complete run used frozen source `612594d`, the fresh parent receipt generated
at `2a4b2fd`, and cad-agent v0.4.2 at `2ad4269`. The report binds the before/after
source, toolkit, private inputs, all manufacturer identities, authored poses and
eight public exports. Private manufacturer models remain private. Independent
review reconstructs those inventories and inspects the exported solids; integrity
checks preserve false engineering, physical-fit, strength and fabrication flags.

**After any change under `cad/`, `catalog/` or `designs/`** the CI check of this
receipt fails on purpose, because the receipt binds those sources. Restore it in
this order: regenerate the parent mounting receipt, rerun the support probe on the
compute host against the private models (about 15 minutes), have the new receipt
independently reviewed, then update the two inventory pins in
`tools/test-rs04-support-probe.py`. The research README is itself a hashed input,
so it is not edited without that rerun.
