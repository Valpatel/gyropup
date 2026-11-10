# Whole-robot assembly data: source and test amendment

Issue #266 now includes real body, leg, knee and wheel stages. This extends the
existing assembly-guide contract and current CAD collector; the product UI is
owned separately in PR #267. No renderer, physical action or geometry redesign
is proposed. The bounded native collection completed at immutable source
`540056ba4e59b197859236cb693463e10c9c8901`; independent visual-asset review
and product integration remain separate from physical qualification.

```mermaid
flowchart LR
  A[Named CAD parts] --> B[Bound assembled meshes]
  B --> C[Robot and combined stages]
  C --> D[Frame and identity tests]
```

<details>
<summary>Observed source boundaries and minimal design</summary>

The current `software/site/designer/robot_v2.js` playground reads
`hardware/exports/sim/v2/rig/manifest.json`. That retained manifest contains an
`interim_body`, old fixed output adapters and only coarse moving-link groups.
Its presentation replaces adapters from the separately source-bound
`leg-attachments` bundle. It is useful display precedent, not a current assembly
recipe or a complete knee hardware inventory.

The actual body CAD differs in a material way: `body_params.to_robot()` and
`body_frame.legs()` rotate the physical right module 180 degrees about Z; the
playground mirrors Y. Preserve the CAD mapping, including front/rear ownership,
instead of adopting the animation manifest as the mechanical oracle.

`tools/engineering/robot/robot_view.py::collect()` already returns individual
named, assembled shapes for the real P3 body, both complete five-bar legs at
300mm stance and the mounted turret. Its normal publisher merges these into
colour groups. Reuse that collector before grouping; do not split a merged
hardware mesh into invented individual parts. `fivebar.assembly()`,
`link_frames()` and `body_frame.all_parts()/legs()` are the construction owners.
The existing `rig_assembly.py` contains knee/apex/wheel sequence evidence, but
its exported instructions are explicitly archived and motor-lug torque/fit
claims withdrawn. Preserve that history; do not copy its fastener instructions
as a newly qualified procedure.

Minimal implementation:

1. Freeze the actual source commit, CAD/context inputs and the existing
   collector. In one independently reviewed bounded compute-host collection,
   tessellate its individual named shapes into a fresh owned output. Keep real
   part identity, source functions, already-assembled CAD-mm/Z-up frame, colour,
   exact bounds and hashes. Do not modify manufacturing exports. Bought shapes
   remain their existing project-authored envelopes, not redistributed vendor
   STEP derivatives or evidence of fit.
2. Author explicit WIP operation membership for body structure/equipment,
   each hip/motor/upper-link pair, each knee/lower link, apex, wheel and remaining
   enclosure. Bind every included instance to its actual construction source
   and joint/support owner. Keep physical-only and unmodeled fastening gaps
   visible; no powered calibration, torque, fit or strength approval follows.
3. Emit robot-without-turret and combined-with-mounted-turret guides through
   `cad-agent.assembly-guide/1`. The combined turret uses the actual collected
   body mounting datum and source-authored order; it must not be the bench
   guide dropped onto an assumed height. Preserve source/recipe/BOM/hash
   relationships and regenerate text/static fallback from those same stages.
   Expected snapshot IDs are `robot-wip-<source12>` and
   `combined-wip-<source12>`; the index adds `assembly: robot|combined`.
4. Bake the actual assembly frame exactly once. Offsets describe explanatory
   explosion only. Keep the same ordered-step/state contract, without a new
   renderer or parallel publishing service. Actual source-bound posters follow
   the final product rendering contract; no old image is relabelled current.

The existing full-model showcase pack is grouped for homepage rendering; inspect
its retained inputs before deciding whether individual meshes can be reused.
If they cannot, a genuine per-instance collection is required. No native run is
authorized by this document alone.

</details>

<details>
<summary>Meaningful positive and negative test plan</summary>

| Requirement | Positive evidence | Required rejection/sensitivity | Status |
| --- | --- | --- | --- |
| Source and part identity | Exact Git/input/collector/runtime hashes and one-to-one named output membership | Stale source, missing/duplicate/unexpected part or altered mesh digest | Native collection passed; sealed audit passed |
| Actual CAD frames | Independent representative module landmarks through left translation and right180deg-Z rotation; actual exported vertices in common mm frame | Y-only mirror, wrong side/front-rear owner, axis sign, 1000x units or double transform | 88 actual landmarks passed; mirror/unit/double-transform controls rejected |
| Hip/knee/apex/wheel ownership | Motors fixed to hip support; upper adapters rotate with links; knee bearings/pins and wheel hub/tyre remain separately named | Stationary motor attached to rotating link, wrong knee parent, merged hardware masquerading as individual parts | Source/recipe tests and native compound checks passed; animated product checks pending |
| Mounted combined assembly | Actual TM face/pan datum agrees with body CAD and collected assembled turret | Bench-local mesh/assumed mounting height or missing mount relation | Native four-bolt XYZ match passed; actual wrong-XY shift rejected |
| Genuine stages | Explicit source operation, prerequisites and exact included/highlighted instance sets, both sides | Arbitrary colour-group hiding called an assembly operation; invented fastener/qualification claims | 23 source operations exactly cover 171 robot instances |
| Coherent immutable snapshots | Robot and Combined use exact model/mesh/recipe/BOM/source bindings; text/static fallback same stages | Cross-version asset substitution, stale prose, incomplete source coverage | Native-generated 242 outputs verified; final product/static pictures pending |
| Manufacturing originals | Exact existing file/plan identity, kept separate from current geometry correspondence | A named, rehashed stale original must not enable Print | Only L/R hip source-match accepted; other mappings pending; stale-file controls passed |
| Hip geometry-only 3MF | Existing writer/read-back preserves source triangles, finite millimetres, winding and volume after an existing packer's rigid placement | Changed original/project, wrong units/coordinates/faces/build transform reject | Actual single-part project and persistent corruption controls passed |
| Regression/integration | Existing shared validator/controller and product browser coverage applied to imported new data | Existing turret guide or procurement state changed unintentionally | Planned; UI owner integrates |

Geometry-valid CAD/poses and passing presentation tests do not establish
physical assembly order, access, fits, preload, motor operation or strength.
Existing #8, #193 and #201 limits remain open. Preserve failed runs and report
any source/placement disagreement before adopting a candidate.

</details>

<details>
<summary>Bounded hip geometry-only project handoff</summary>

The identified hip STL remains the manufacturing original. Its retained
`hip_frame.3mf` also remains unchanged. Prepare one distinctly named derivative
with the existing `cadagent.manufacturing.plates` footprint/packing functions
and `mesh3mf.write_3mf`/read-back; no new writer, CAD, slicing or transport.
Metadata uses a separate `prepared_projects` list with project/original hashes,
`kind: geometry-only`, immutable identity and explicit limitations.

Actual footprint inspection rejected a 256 mm square with a 5 mm margin. The
existing packer finds a 45-degree yaw in a generic 256 mm rectangle with a
3 mm margin (249.216815 mm square footprint). This is only a finite geometric
layout with no keepouts. It is **not** a P1S/X1E profile, keepout, adhesion,
material, support or slicing proof. Users must select and check their actual
printer/material/orientation/support/slicing settings. No job starts.

Compare the saved project's exact triangle topology and every vertex against
the original after that known rigid transform (allowing only the writer's
0.0001 mm coordinate serialization), as well as finite coordinates, mm units,
closed consistently wound edges, signed volume and actual rectangle bounds.
Persist the layout and source/tool hashes. Reject altered originals, geometry,
units and triangle indices; missing or changed proof/project must remove the
prepared-project offer rather than falling back to a differently bound file.
The UI owner verifies the same declared project/original hashes at handoff.

The single pure generation completed in under one second using the pinned
existing toolkit. Read-back preserves 14,794 vertices and 29,676 triangles,
with maximum coordinate error 0.0000499998 mm and closed consistent edges.
Signed volume changes from 1,014,809.5856 to 1,014,809.5215 mm³ through decimal
serialization. Actual generic bounds are `[3.3916, 3.3916, 0]` through
`[252.6084, 252.6084, 81.3]` mm. A content-addressed project URL includes its
full SHA256; metadata retains the original STL separately. The derivation record
is `.agents/plans/robot-assembly/hip-prepared-project.json`. This project has no
printer/process/material settings, slice or job command. Existing original STL,
retained 3MF, whole hardware tree and all neutral assembly meshes are unchanged.

</details>

<details>
<summary>Source preparation checkpoint</summary>

The authored recipe now has 23 construction operations covering 171 non-turret
CAD instance identities from the retained collector inventory. Each leg has
separate hip/support, fixed motor, upper-link, front knee, rear knee, apex,
wheel and stop operations. Source screw/washer compounds remain compounds.
The shared qualification lives once in guide.source; step text keeps specific
fit/access gaps without repeating that whole notice.

The import-safe collection worker reuses robot_view.collect before grouping.
It prepares actual module-local mesh landmarks for 11 representative parts on
both sides, checks the physical 180 degree-Z mapping within 0.02 mm, and checks
the actual riser/pan-base TM plane plus bolt-circle X/Y/Z centers. A rigid
wrong-X/Y native mount negative is required. Normalized output filename
collisions reject before writing. These native controls executed successfully
in collection 260; the maximum independent landmark error was
0.000004688 mm, below 0.02 mm. All 233 authored source shapes were valid;
38 meshes are explicitly declared source compounds.

The pure exporter prepares Robot and Combined snapshots with an honest full
CAD overview followed by construction stages. Installation presentation order
is explicit per stage, not manifest/BOM iteration. Plain HTML/JSON use the
same stage text and requirements. Manufacturing metadata identifies existing
print STL, machining STEP or sheet STEP/DXF originals by actual digest; baked
posed guide meshes are never offered for printing. Unknown catalogue relations
stay unresolved. File identity and print-plan membership are not proof that an
original matches the new collected shape. Manufacturing rows have an explicit
`geometry_match` status; Print must remain unavailable until a separately
accepted correspondence exists. Identified originals may be
offered as clearly labelled retained downloads. The default hip-frame STL is
byte-identical to the source-bound RS04 fit-study artifact, but that finding
does not qualify the whole leg or its known failing support checks. The narrow
hip proof additionally compares every vertex and triangle centre of that
original against the actual left and right collected hips in both directions,
after the source-authored print transform. The observed maxima are 0.156971 mm
and 0.136655 mm, below the declared 0.3011 mm combined tessellation/weld/float
allowance. This is sampled corroboration plus full source provenance, not a
continuous surface-distance proof. Only a reviewed record with current
source/receipt/original/mesh/sampler identities may mark these two instances
matched for WIP file preparation. All other mappings remain pending. The
original 90-second arithmetic timeout is preserved; the optimized equivalent
comparison completed in 55.09 seconds, including an actual 3 mm shift negative.
The [independent narrow review](https://github.com/Valpatel/gyropup/pull/270#issuecomment-6762537417)
accepted that geometry-source match for `L.hip_frame` and `R.hip_frame` only.
The separate acceptance file binds the immutable measurement; it does not edit
it or turn the eight failing support checks into passes. The remaining part
mappings stay pending. Prototype file preparation still requires explicit
printer, material/process and slice choices; the raw 274 mm width does not
prove fit on a 256 mm printer bed.
Body/leg planning quantities retain their original scope;
wheel hub and tyre share one bought-wheel identity.

All 24 kernel-free tests pass. They cover retained named
membership, stationary/moving ownership, grouped hardware, frame/unit/mirror
negatives, strict binary STL, symlink inventory rejection, import safety,
original-file mapping, snapshot/text integrity and changed-source rejection.
Synthetic serializer fixtures are test-only and are not CAD/asset acceptance.
The committed-data tests additionally reserialize all 242 actual outputs and
compare their bytes, check all current CAD/original/mesh identities, and apply
an independent left/right transform to the 88 recorded local landmarks against
actual committed mesh vertices. Wrong mirror, units and double-transform
controls must disagree with that real geometry.
Broad draft CI is deliberately deferred on preparation commits until genuine
assets are ready; final source/assets must run all ordinary required checks.

The actual collection used a retained read-only runtime on a CAD host: native
collection 132.85 seconds and pure guide serialization 1.07 seconds, both
exit zero with owned process groups gone. Complete project, hardware, runtime
and toolkit inventories were equal before/after. The immutable native archives
and their original guide metadata are preserved; the current pure exporter adds
the conservative manufacturing-match fields without re-tessellating geometry
or relabelling the native source. See the [run checkpoint](https://github.com/Valpatel/gyropup/issues/266#issuecomment-6761821545)
and the committed collection record for archive and output bindings.

</details>
