# Fresh fit evidence without changing printed-leg originals

Proposal, 2026-11-10; no native or slicing run is approved by this document.
The strict current validator and original receipts remain unchanged.

Update: [independent RouteA review](https://github.com/Valpatel/gyropup/issues/193#issuecomment-6775808908)
selected explicit historical integrity plus a separately measured current
hip-to-original correspondence. [Current implementation and remaining gates](current-print-correspondence.md)
preserve the complete historical guard and default-current stale rejection.
The genuine CAD/slice refresh below remains RouteB, not an executed run or a
requirement to redate unchanged protected legs. CI ownership/public guide
adoption still require their own complete positive/negative acceptance.

## Observed boundary

The retained-fit CI failure is
[run 42866125306/job 130005097895](https://github.com/Valpatel/gyropup/actions/runs/42866125306/job/130005097895).
Independent review at `3df450b2` enumerated 11 changed inputs within the same
94-file conservative CAD/config closure: `body_battery`, `body_bom`,
`body_frame`, `body_joints`, `body_layout`, `body_sections`, `body_shell`,
`body_views`, `build_body`, `hardware/catalog/body.json`, and the existing
`tests/hardware/body/test_body.py`. The separate actuator-interface document
and lug-stack test context files remain exact.

`rs04_lug_checks.validate_receipt` intentionally compares the complete closure.
The protected leg-only source/export equality does not make the old receipt
current. Its native geometry routine directly uses `fivebar`, `rig_bench`,
`gmi`, the original manufacturer lug plate and normalized McMaster screw; the
changed global closure still requires a genuine fresh check. No old report is
restamped, its default guard is not narrowed, and the known eight unsupported
stack sectors must not be promoted to passes.

## Proposed current evidence sequence

1. Independently review the final immutable source and a detached bounded
   packet. Use the exact existing released toolkit
   `2ad426943ce2c7232875e105e50810849f9a3e5e` / 0.4.2 required by the unchanged
   checker, the declared toolkit-source fingerprint and all existing private
   manufacturer/normalized-screw hashes. This is separate from the newer body
   collection runtime; neither runtime may silently substitute for the other.
2. Run the existing protected checker, in an immutable worker, with a fresh
   external destination:

   ```sh
   python hardware/cad/legs/rs04_lug_checks.py \
     --vendor-root "$PRIVATE_VENDOR_ROOT" \
     --out "$RUN_OUT/current-lug-candidate" --export
   ```

   The operator packet must resolve these role variables to reviewed private
   paths and freeze the source SHA, executables, fingerprints, CPU/memory/time
   caps, logs and collection method before submission. No installation or
   printer operation is implied. Exported candidate copies stay outside the
   protected source/manufacturing directories.
3. Validate that genuinely recomputed receipt using the original strict
   `validate_receipt` against the final current 94-file closure. Preserve all
   readiness flags as false, actual failure/warning membership, measured
   witnesses, recess controls and declared driver limits. A different result
   remains a finding to investigate; it must not be rewritten to match the old
   result. Compare source/geometry identities with the original three authored
   exports, and independently verify unchanged leg trees, five source hashes
   and firmware limits. Do not replace the original files even if equal.
4. Downstream packaging needs a separately reviewed explicit captured
   engineering-source input, because the current packager's `SOURCE` is the
   protected original `hardware/exports/leg/rs04-mounting-fit`. A new option
   must capture the fresh receipt/STL under stable relative job identities,
   call the unchanged current validator, retain all input hashes, and generate
   a genuinely new slice using the pinned existing engine/profiles. It must
   not change the old source default, fake a new source stamp on an old slice,
   publish private paths, or overwrite the old job. That packaging option is
   proposed, not implemented or accepted by this caller-fix checkpoint.
5. Current CI can adopt only the genuinely verified new current candidate via
   an explicit reviewed ownership/pointer change. The old archive remains
   historical and may be verified against its immutable original full input
   closure using the original strict checker. Any explicit historical CI
   route needs its own review and must not label that archive as current
   end-pack/body qualification. No such CI exception is added here.

The original failing retained-fit job stays visible until this acceptance
boundary is resolved. A successful new bounded fit/slice integrity check still
does not approve the printed leg, adapter retention, body supports or drops.
The initial same-object BREP/STL body collection is a separate proposed run;
neither result substitutes for the other.
