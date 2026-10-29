# A correct home pose does not validate a rotation pivot

On 2026-10-28, the published Orin AGX turret rendered correctly at zero angle but its feed dial and wheels orbited away from fixed motor housings during firing. The CAD applied a 48 mm cartridge-to-tilt offset; the exported joint declarations did not.

Evidence from the actual deployed scene, before correction (`3eb32ba`):

```
node /tmp/gyropup-pivot-live-audit.mjs
101 rendered frames, ARM + six shots
feed dial center displacement: 96.000 mm
left/right wheel center displacement: 95.963 mm
motor housing displacement: 0.000 mm
```

All 66 binary STL files (151,176 triangles) had finite vertices and bounds matching manifest rounding within 0.050001 mm. Those static checks could not detect incorrect animation frames. After the source and coordinate regeneration fix:

```
python3 tools/test-turret-frames.py
Ran 4 tests ... OK
node tools/test-turret-motion.mjs
PASS chromium: 66 components × 46 poses; 26 real firing frames; max 0.000010mm; negative pivot control rejected
```

Apply every CAD datum transform to both geometry and attachment/joint metadata. Validate actual rendered landmarks against independently sourced mechanical axes at intermediate angles and compound parent poses. Explicitly distinguish motor housings from rotating members. A fixture copied from the same suspect manifest is not independent evidence. See `docs/validation/turret-motion.md` for provenance, reproduction, and the geometric/physical limits of this check.
