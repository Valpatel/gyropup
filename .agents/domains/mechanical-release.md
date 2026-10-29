# Mechanical release coherence

Review entry point: [mechanical readiness](../../docs/mechanical-readiness.md). Keep CAD source, selected hardware, installed instances, public meshes, print files and instructions bound to one explicit configuration. Imported reports remain historical until the affected geometry and gates are rebuilt on that configuration.

`cad-agent check` reads existing reports; it is not a CAD rebuild. Run the appropriate geometry build and affected gates on the committed candidate, record source/toolkit/input/output hashes, and inspect the evidence. Keep visual completeness, assembly/clearance, fabrication readiness and physical acceptance separate. A valid solid, a successful render or an unchanged bearing boundary does not establish the other outcomes.

For articulated exports, review both conflicting and automatically merged coordinate conversions. Every cartridge-to-joint conversion is applied once. Verify actual rendered vertices against independent mechanical datums after regeneration, including attachments and effects. Preserve archived geometry for its recorded trajectory.

Portal coverage checks must compare complete identities against the served revision and BOM, rather than a hard-coded historical count. New components require their own matching geometry and thumbnail receipts; do not suppress a missing-image failure because the older release looked correct. Keep private manufacturer CAD private and identify public authored representations honestly.

Assembly verification includes preassembly, tool access and service/removal in the finished machine. A checker that only fits individual parts cannot certify a preassembled module merely by rearranging its steps. Require explicit module evidence until generic tooling can express the actual sequence. Continue to report unrepresented cables, missing measurements and unperformed physical trials.

Print packaging must use verified immutable input copies, bind resolved slicer profiles and the actual executable, reject failed/non-finite results, and derive totals only from accepted rows. Geometry-file coverage, successful slicing and physical qualification are separate states. See [the packaging incident](../inbox/2026-10-29-print-preflight-is-not-a-generation-transaction.md) and `tools/test-print-provenance.py` / `tools/test-print-packaging-mesh.py` for adversarial controls.
