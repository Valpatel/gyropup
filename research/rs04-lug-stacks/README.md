# RS-04 mounting evidence

This is a record of a design investigation, not fabrication approval. The current
work is [issue #116](https://github.com/Valpatel/gyropup/issues/116) and
[PR #117](https://github.com/Valpatel/gyropup/pull/117). Read
[the mounting-fit note](../../docs/rs04-mounting-fit.md) for the intended geometry.

## First complete run: the candidate still fails

Source `3c9bc8f71221404bbcf4735365661f29cd735012`, cad-agent
`2ad426943ce2c7232875e105e50810849f9a3e5e` (v0.4.2), CadQuery 2.8.0,
OCP 7.9.3.1. The isolated run finished on 2026-10-30 at 06:55:03 UTC after
6 minutes 9 seconds, exit 1: **279 passes, 40 warnings and 8 failures**.

[The complete compressed JSON receipt](failed-3c9bc8f.json.gz) retains every
measurement, private-input hash and verdict. Its decompressed SHA-256 is
`17d6576f8f13c535785a1c8e1bbf9156cc3fd7d62652ad2fdb03d9baabca6548`.
For example, inspect it with `gzip -dc failed-3c9bc8f.json.gz`.

All forty lug screws have 15.6 mm measured nominal grip and 4.4 mm penetration.
The old frame and dyno seats fail the independent drawing-depth constraint, as
does a deliberately insufficient-engagement candidate. The forty warnings retain
the distinction between the modeled 7 mm drill depth and the drawing's 5 mm
guaranteed thread. The exact dyno plate/hub relation has a 1 mm nominal gap.

Eight receiver-support checks fail: `leg_front_04/09`, `leg_rear_03/08`,
`coupon_nom_04/09`, and `dyno_02/07`. These map to the manufacturer's native
−15° and 165° lug axes. Adjacent factory-retainer recesses at radius 57.6 mm
sit only 4.6 mm outboard of the M4 axes. Their Ø5 recesses and 45° countersinks
remove support under part of the sampled bearing annulus. The actual factory
fastener head is also recessed 0.21 mm below the mounting face; adding that
omitted solid does not establish flush support.

The next iteration must retain these failures while checking driver approach and
recording the complete contact evidence. A valid receipt means the evidence is
complete and unchanged; it does **not** mean the engineering verdict passes.
Contact/load spreading, manufacturing tolerances and physical fit remain open.
