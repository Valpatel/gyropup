# Ordered turret motor: prepare the interface before changing the cartridge

**Ordered identity is confirmed; dimensional fit is not.** On 2026-10-30 the
owner confirmed the Deeahdah PRO3115-900KV threaded-shaft motor sold as
[Amazon B0GJNX17YX](https://www.amazon.com/dp/B0GJNX17YX). This is the confirmation
date, not an inferred order or delivery date. Purchased pack count and arrival
remain unknown. The listing's four-pack does not establish how many were ordered.
See [purchases](purchases.md) and [acceptance issue #124](https://github.com/Valpatel/gyropup/issues/124).

The current cartridge still models **SunnySky X2216 1400KV V3**, including its
separate prop adapter. It has not been silently relabelled as the ordered motor.
The new part's mounting face, shaft seating and retention must be measured before
we adapt that cartridge. This work does not release a full turret print or a
powered test.

## What is known, and what must be measured

The exact Amazon listing was retrieved on 2026-10-30. Its A+ specification table
adds useful claims that were absent from the earlier research. These are seller
claims, not a manufacturer drawing or measurements of the delivered samples.
The [source packet](../research/ordered-turret-motor/seller-claims.json) records
the selected ASIN, source URL, retrieval date and SHA-256 of the cached HTML.

| Interface | Exact listing claim | Still needed from the actual sample |
| --- | --- | --- |
| Body | Diameter 37.1 ± 0.15 mm | Maximum rotating envelope, stationary base and lead clearance |
| Axial envelope | 47.8 ± 0.3 mm, including output shaft | Mounting-face-to-bell and mounting-face-to-shaft-tip datums; rear protrusion |
| Output thread | M5 | Pitch, hand, usable threaded length, shoulder/pilot and clamping seat |
| Mount | M3, described as 19 × 19 mm | All four hole coordinates, thread pitch and usable depth; face reliefs |
| Mass | 120 g including 30 cm 16 AWG leads | Each motor's actual mass and delivered lead lengths/diameters |

The listing photos show the underside and threaded output, but contain no
usable dimensioned drawing. They also mix colour variants. Do not infer thread
pitch, hole depths, datums or tolerances from their pixels. A different brand's
3115 motor, or the old SunnySky's M5 × 0.8 adapter, is not evidence for this part.

The current CAD's 27.7 mm diameter, 32 mm mount-to-bell length, 16/19 mm opposing
mount-hole spans, separate adapter and 72 g mass are **legacy SunnySky inputs**.
The seller's larger diameter alone is enough to reject a simple name/KV swap;
it is not enough to design the new bracket or qualify its clearance.

## Delivery-day survey

1. Keep the motor unpowered. Assign each delivered motor an individual sample ID.
   Photograph the package/label, complete motor, underside, shaft and lead exit.
   Record the actual received quantity separately from the purchase confirmation.
2. Copy the [measurement template](../research/ordered-turret-motor/measurements.template.json)
   into a sample folder. Keep that sample's evidence files inside the same folder.
   Record the operator and observation date. Add each evidence file's relative
   path and SHA-256; an absolute path or a path escaping the folder is rejected.
3. Establish the datum: mounting face at **z=0**, shaft along **+z**, **+x toward
   the lead exit**, using a right-handed frame. Record all four mounting-hole
   centres in that frame. The [1:1 survey sheet](../research/ordered-turret-motor/mount-pattern-survey.svg)
   shows two interpretations of the seller's wording, explicitly as hypotheses.
   Print at 100% and check both 100 mm scale bars. It is **not a drill template**.
4. For every interface field, record the value, method, instrument, uncertainty
   and supporting evidence. Scalar/vector uncertainty is in the field's unit
   (mm, or g for mass); thread handedness has `null` uncertainty and requires
   explicit identification evidence. A zero shoulder or rear protrusion means
   its absence was observed: both corresponding length and diameter must be zero.
   Leave unknown values `null`; do not copy seller claims into measured fields.
5. Identify thread pitch/hand and usable engagement separately. A matching
   nominal diameter does not prove either. Do not force a nut or probe blind
   holes with screws into the windings. If safe usable depth cannot be established
   from an exact drawing or a suitable inspection method, leave it unknown.
6. Run the survey checker below. It rejects incomplete fields, wrong identity,
   missing/changed evidence, inconsistent datums and claims that the survey has
   qualified a design. Its pass means **the survey record is complete enough for
   engineering review**, not that the observations are correct or a fit is proven.

```sh
# cad-agent 0.4.2 must be installed in the selected Python environment.
# Acquisition and template generation themselves use only the Python standard library.
python tools/ordered-turret-motor.py template --out build/motor-sample-01/survey.json
sha256sum build/motor-sample-01/identity-photo.jpg
python tools/ordered-turret-motor.py check build/motor-sample-01/survey.json \
  --out build/motor-sample-01/checks.json
python tools/test-ordered-turret-motor.py
```

The untouched template intentionally fails. A successful survey still reports
`physical_fit_verified`, `mount_design_released`, `hub_design_released`,
`slicer_run` and `powered_operation_qualified` as **false**. Repeat for every
motor; variation between samples matters. Keep private order details and personal
information out of any evidence selected for publication.

## Design work that follows the survey

| Step | Required evidence before proceeding |
| --- | --- |
| Motor mount and rear relief | Measured mounting coordinates, face seating, protrusions, usable thread depths, screw stack and driver access |
| Flywheel hub and retention | Measured output thread/hand, usable length, seating face, pilot/shoulder, tolerance stack and a reviewed retention approach |
| Cartridge packaging | New body/bell envelope and mass, swept clearance, lead exits, service access and cable routing with justified bend radii |
| Unpowered specimen | Source-bound STEP/STL, CAD/mesh checks, actual material and slicer evidence, documented physical fit on the identified samples |
| Powered qualification | Separate balance, containment, overspeed, electrical and thermal review and controlled tests; none is implied by an unpowered fit |

Manufacturer hardware CAD and catalog identities should be used where available,
following the existing cad-agent hardware workflow. Missing supplier geometry
must stay visibly incomplete; no generic 3115 cylinder is a qualified motor
model. Exact manufacturer drawings remain a useful missing input.

## Reproducing the acquisition

The raw vendor HTML and photographs are cached locally, not redistributed.
The parser reads the selected ASIN input, product title/brand and semantic table
rows. It rejects another ASIN, a mismatched identity, missing rows and conflicting
rows. It does not scrape dimensions from images or silently change current CAD.

```sh
python tools/ordered-turret-motor.py acquire \
  --html build/ordered-motor-source/amazon-B0GJNX17YX.html \
  --observed 2026-10-30 \
  --out research/ordered-turret-motor/seller-claims.json
python tools/ordered-turret-motor.py sheet \
  --out research/ordered-turret-motor/mount-pattern-survey.svg
```

The earlier CAN actuator research remains in [PR #46](https://github.com/Valpatel/gyropup/pull/46).
This packet settles purchased identity and prepares interface acquisition; it
does not settle bus selection, an ESC rail, motor operating limits or physical
acceptance. [Issue #124](https://github.com/Valpatel/gyropup/issues/124) remains open
until its physical acceptance conditions are met.
