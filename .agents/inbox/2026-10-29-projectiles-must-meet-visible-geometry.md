# A correct muzzle datum does not prove the visible barrel is still there

On 2026-10-29 UTC the user reported journey balls below the barrel. Independent PR44 probes measured the assembled STL mouth and muzzle/path endpoint within 0.000000608 mm across five pan/tilt poses (axis error0°). After Explode slider1 then Journey, the barrel remained about149mm above the nominal path, with155.12mm mouth error. Separate native JOURNEY → PAUSE →7×NEXT produced an11.2583m/s demonstration flight instead of15.85m/s because paused RPM remained6234.49.

The old checks verified a nominal endpoint and joint motion, not the visible exploded presentation or manual journey lifecycle. The correction always rejoins the same existing meshes before journey/live firing and uses nominal speed for teaching flight independent of partial wheel spin. No CAD geometry or live projectile speed specification is changed.

Regression commands: `python3 tools/test-turret-frames.py` (four tests passed after adding transverse mouth-center checks); `npm run test:interactions` now covers reassembly, the actual rendered bore and paused-stage flight. Evidence and limits belong in [Rendered mechanisms](../domains/rendered-mechanisms.md). The trajectory remains a simulation prediction, not measured hardware performance.
