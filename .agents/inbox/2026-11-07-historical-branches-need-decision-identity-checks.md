# Recover historical branch evidence without reusing its decision IDs

On 2026-11-07, the retained `study/body-sheet-metal` tip `4585596492a75a08489ef99b6b9e3b8334c5e5ee` was not an ancestor of dev. PR #158 had been closed unmerged; its 65 study files (4,971,231 bytes) remained unique. `git merge --no-commit --no-ff 4585596` into dev `48024e56` produced a real conflict in `docs/program/decisions.yaml`: the old branch proposed a body D75, while current D75 records pronunciation and later decisions already exist.

A normal ancestry merge retains the study tip, but conflict resolution must preserve current program decisions byte-for-byte. The old decision file is archived separately as `docs/research/body-sheet-metal/decisions-historical.yaml`, with its original SHA256 `604d9e582fdfc91f5a07369af88e998f964caace4fdb2af4098c00a6a05113f7`. The 65 study files move into the owning docs directory; only a reversible historical prefix is added to their README. The complete path/size/hash mapping is in [the recovery manifest](../plans/body-study-recovery.json).

Corrective rule: compare exact old and current decision identities before recovering an unmerged branch. Require a whole-tree allowlist, immutable original payload hashes, and an explicit historical scope. A proposal's old identifier is not authority to replace an unrelated decided record. Preserve runtime/CAD/catalog/program files exactly and run the actual publication/privacy/link/wall consumers before integration.

Limits: archival recovery does not make the old scripts runnable, refresh quotes or FEA, choose an option, or close engineering acceptance. Issue #155 retains its unresolved owner choices and acceptance work. Incorporated ancestry and later retirement of a completed remote name are separate from issue closure. No FEA, native CAD, purchasing or physical test was performed for this recovery.

## Keep closing keywords out of prose that must leave an issue open

On 2026-11-07, independent review caught the literal closing phrase `close #155` inside a negated sentence in the initial PR252 description. The body was changed to “Issue #155 remains open; no body design is selected.” Actual readback with `gh api graphql` for `pullRequest(number:252) { closingIssuesReferences(first:20) { nodes { number } } }` returned `nodes: []`; issue155 remained OPEN.

Corrective rule: when an issue must remain open, state that directly without a closing keyword followed by its issue reference. Read back the live body and GitHub's parsed closing references before merging; do not rely on natural-language negation. The old body is retained in review history. No automatic closure was observed in this case: the finding was caught before merge, and only the corrected body's empty reference set was measured. This is a workflow guard, not new engineering acceptance or a reason to alter the archived study.
