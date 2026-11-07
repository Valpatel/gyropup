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


## Reference ownership and asset identity must also be independent

On 2026-11-07 UTC, preparing the recovered −25/+12-degree turret reference exposed two source-level gaps: the old reference generator selected each physical owner from the display manifest's `group`, and the browser recorded mesh URLs without binding the fixture to the actual loaded manifest/mesh bytes. Independently audited pivots alone could therefore bless copied ownership or stale landmark indices. The [bounded independent datum audit](https://github.com/Valpatel/gyropup/pull/255#issuecomment-6706754647) confirmed the actual Geo arithmetic, pose signs and right-handed millimetre→metre basis without importing CAD.

The existing reference producer now requires an immutable current-scene revision, explicit source-audited ownership for all 80 names, exact units/frame/membership, finite complete binary STL data and four noncoplanar actual landmarks. It rejects disagreement with display ownership instead of deriving the oracle from it. The existing Python consumer requires fixture→current raw-file hashes, and the browser binds actual loaded response hashes, version queries and part name/file/owner metadata. Keep whole motor cases on their supports; root pinion geometry retains its documented box-frame exception. Pan ±170 is bounded viewer coverage, not a mechanical stop.

Actual cheap preparation evidence: `python3 -B tests/evidence/test-turret-frames.py ReferenceInputGuards` passed two tests, including changed ownership/units/frame/name/file/pivot and malformed/nonfinite/planar STL controls. An isolated execution of the actual binding function on retained shipped bytes and an explicit independent-owner fixture passed its positive case and rejected six changes: self-consistent wrong-owner metadata, changed mesh bytes, missing mesh, missing loaded manifest, wrong cache key and duplicate name. Node syntax passed. These are parser/binding controls, not current geometry generation or browser acceptance.

The real-renderer test adds unit conversion, axis/sign, lost-parent and stationary motor ownership faults to the existing correct-home/wrong-pivot quarter-turn control, retaining the 0.02 mm tolerance. Actual current-scene generation, immutable reference refresh, two-engine live captures, fault outcomes and independent artifact review remain required. Do not label a synthetic parser fixture, old scene, source review or URL list as that evidence.

## Clearance freshness needs both current tilt boundaries and complete sampled grids

On 2026-11-07 UTC, before the recovered positive-elevation scene was generated, the existing builder's `ball_path_check()` considered `hardware/exports/turret/lidar/box.json` current solely from its TM/deck height. The actual published `b61f0cd4b4e27b8006c06e6a473a9984d63e2033` report still covered only `[-25, 0]`: its 181 sampled rows had no `max_elevation_deg`, and its 73 firmware rows had no `max_tilt_deg`. Height equality therefore did not support the scene's proposed `[-25, +12]` full-range clearance claim. The byte-exact old report is retained as `tests/fixtures/turret-box-ball-path-before-elevation.json` (SHA-256 `e6b4b3807f381ce9d1c073e7db1dea7a593c67c05aacceeb8fb63a1c4e45faab`).

The existing kernel-free reference/evidence consumer now uses `box_path_coverage()` for scene/shared-limit agreement, report identity and TM height, exact 181/73 pan grids, finite lower and upper bounds, the current 10 mm margin and ball assumptions, and absence of any depression or elevation limitation. Reference generation records the actual report and shared-limit hashes. The scene collector calls this same function before the builder and again against the genuine resulting manifest. The existing frame suite requires the same guard, not a private collector-only assertion.

Actual command `python3 -B tests/evidence/test-turret-frames.py ReferenceInputGuards` passes three tests, including the real old-report rejection and ten guard-fixture negatives (missing upper rows, narrowed lower/upper bounds, missing/duplicate pans, incomplete firmware upper bounds, changed margin/ball, changed TM height and scene/shared-range mismatch). The explicitly synthetic positive fixture tests the guard only; it is not native collision evidence. The new current-scene coverage test presently rejects the retained old scene/shared-limit mismatch, as expected before generation. All 94 frozen CAD input hashes remain unchanged.

Corrective rule: regenerate the actual existing `turret_lidar.py --scene box` report and plot, then require both current sampled boundaries before accepting a full-range scene. A genuinely narrowed or blocked result is evidence to preserve and reconcile, never a reason to force a row or relax this guard. These discrete samples remain computational evidence, not continuous-motion or physical qualification. The planned two-output refresh does not change the conservative manufacturing input closure and does not justify rerunning independent robot-lidar, historical FEA or feed studies.
