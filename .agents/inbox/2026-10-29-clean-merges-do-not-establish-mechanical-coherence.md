# A clean merge does not establish a coherent mechanical release

On 2026-10-29 UTC, mechanical integration combined published main `1475902`, turret program `14a4127` and dossier `630a2db`. Program integration `46460d9` had six exporter conflict regions; dossier integration `3f69645` merged cleanly. These facts did not make the imported artifacts current.

Evidence:

- The program exporter already converted journey focus through `tf(x,y,z) = (x - tilt_x, y, z - tilt_c)`. An automatically retained main-branch loop would subtract `tilt_x` again. At the current 48mm datum, a cartridge x0 focus would become -96mm instead of -48mm. The integration removes the second conversion and retains physical IR-gate positions from `GATES['x']`.
- At candidate `f2d0125`, cad-agent `28abd34` / v0.4.0, `cad-agent check --json` exited 1 with 37 pass / 47 fail / 1 skip, physical fit false, slicer false. It read imported report files; it did not build this candidate's geometry. [Report and provenance](../../docs/validation/mechanical/imported-reports-check-provenance.json).
- CI run `40834872578` on `6339e12` rejected the portal's fixed 495-model expectation: the integrated revision publishes 497. Its independent geometry-image check also failed with `No unique current turret geometry for cradle_plate_l`, because the new BOM and old public model differ. The latter is a real release blocker, not a count to update blindly.
- The old print script names `flywheel_tyre_d34.stl` while the program's selected tyre is Ø38. A mixed partial print package cannot be treated as a current kit.

Cause: separate workstreams advanced source, models, reports and presentation at different times. Textual merge success, cached gate passes and fixed historical file counts do not establish cross-artifact identity.

Corrective rule: follow [mechanical release coherence](../domains/mechanical-release.md). Compare exact artifact identities and hashes, regenerate affected evidence, inspect frame conversions, and retain missing-coverage failures until their actual geometry exists. The portal harness now compares the served Git tree and BOM identities; existing media checks continue to reject the missing new geometry.

Limits: this incident records integration and historical-report triage. It does not qualify the new turret, demonstrate continuous clearance, establish safe operation, or replace actual hardware measurements and bench trials.
