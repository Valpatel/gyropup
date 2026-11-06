# Folder ownership also changes publication and import contracts

On 2026-11-05, read-only consolidation review found that the existing site builder copies docs/**, hardware/** and sim/**, while root references, dossier, rig and rl are not publication roots. It separately renders Markdown under docs/research/hardware. A logical source move can therefore expose new files or pages without any explicit publication feature. Python module/service entry points and source-hashed artifacts are separate contracts, too.

Evidence: tools/build-site.mjs roots and document filters; hardware/deploy/jetson/files/gyropup-rs04-bridge.service invokes python3 -m rig.rs04_bridge; the RS04 and highlight validators bind actual source paths/bytes. The independent plan review identified these consumer/publication boundaries before any later-stage move.

Corrective rule: inventory the actual baseline bundle, pages, indexes and source/receipt consumers before moving a directory. Preserve public identities explicitly and plant tracked/untracked private/vendor inputs under every proposed home to prove they stay excluded. Prove installed module/service behavior outside the checkout, not just imports from a source root. Genuine changed producers need genuine runs with retained failures, not resealed metadata.

Limits: the following is a reviewed planning proposal with required preflights, not implemented moves or passing exclusion tests. Root 20 alone does not make 64 direct docs files and 136 direct tools files pleasant to navigate; short owning maps and domain organization remain in scope. Dirty RL ownership is not taken. The release and focused fixture move precede later stages.

# Candidate root consolidation after the current release

Read-only inventory at f23542a0 (2026-11-05 local date): 28 tracked top-level entries. No moves in this plan have been made. The earlier 31→28 migration is merged into dev. Public delivery and the existing fixture move still come first.

The following owning homes provide a concrete 28→19 route while keeping the standard Node manifests, `.nvmrc`, CAD anchors, README, LICENSE and agent instructions discoverable at root. Each stage requires a focused consumer/provenance review; 19 is an attainable result, not permission to ignore a guard or active owner.

| Stage | Source → owning home | Root entries after stage | Destination direct-file/subfolder impact |
|---|---|---:|---|
| 1 | tests/3 JSON fixtures → tools/fixtures; CONTRIBUTING.md → .github/CONTRIBUTING.md | 26 | tools remains 136 direct files, gains one subfolder; .github gains one direct file |
| 2 | research → docs/research; references → docs/references; dossier → docs/dossier | 23 | docs remains 64 direct files; subfolders 3→6; each moved group's internal organization remains intact |
| 3 | web → designer/site-assets | 22 | designer remains 30 direct files; subfolders 2→3; site-assets owns 23 direct files and one highlights folder |
| 4 | firmware → hardware/firmware; rig → hardware/rig | 20 | hardware remains one direct file; subfolders 11→13; firmware owns zero direct files/two subfolders, rig 21 direct files/three subfolders |
| 5 | rl → sim/rl | 19 | sim remains 29 direct files and gains one subfolder; rl retains three direct files/four subfolders |

The resulting root directories would be `.agents`, `.github`, `cad`, `catalog`, `designer`, `designs`, `docs`, `exports`, `hardware`, `sim`, and `tools`, plus the eight ordinary root files. Stage order beyond the small first stage should be chosen around actual owner availability and regeneration dependencies, not repeated independent source-hash churn. No new alias or duplicate evidence tree is proposed.

## Consumer and provenance boundaries

Stage 1 was prepared with the following consumer scope: three fixture bytes/datum/source hashes stay identical; six live readers/generators and two validation documents need path updates. Fixtures are not published roots and are outside the RS04 whole-project CAD closure. CONTRIBUTING has GitHub-supported `.github` discovery, four README links, docs map and SVG GitHub link plus relative contributor links to update. Existing Markdown privacy/discovery checks must still exclude repository operational instructions from publication.

Stage 2 is substantive. Tracked counts are research 132 (21 direct files/14 folders), references 112 (all under vendor), dossier 10 (3 direct/1 folder). Live research consumers include three workflows, cad-agent.yaml site pages, CAD producers, catalog records, site document discovery and evidence validators. `cad/rs04_lug_checks.py` specifically binds `research/actuator-interfaces.md`; its CAD source and all whole-project cad/catalog/designs source identities must remain enforced. References consumers include vendor-root commands, catalog source paths, normalized STEP loaders, service validators, .gitignore and Jetson workflow path filters. Dossier is configured by cad-agent.yaml (`dossier`, gate declarations), produced by cad/turret_dossier.py, and named by retained exports/dossier and gates. Neither references nor dossier is currently a published root: moving them under docs MUST NOT silently publish their entire contents or local licensed vendor downloads. Preserve the actual existing public asset set using an explicit publication/source-path map and test its byte identities. Preserve original historical receipt/pinned-commit paths as historical identities rather than globally rewriting them. Genuine changed producers require their real released-toolkit runs with recorded limits; failures stay visible.

Stage 3 has 29 tracked web assets. Build-site currently copies web wholesale, imports model-links from it, and injects public /web URLs; site-markdown also imports that module. Nineteen designer files, seventeen tools, catalog images, rig instructions and web imports refer to these paths (text-consumer counts include historical/context references). Seven current highlight source identities live under web: icon, model-links CSS/JS, prototype-notice CSS/JS and theme CSS/JS. The capture recipe, encoder and checker also name web/highlights. Moving source home must preserve deployed /web URLs and actual bytes, but receipt semantics must truthfully bind relocated source identities. Do not edit the old receipt or weaken expected_sources merely to accept a move. Batch with a genuine capture/encode/guard run if the exact closure cannot be represented without rewriting historical provenance. Keep report/movie original identities and the separate rig companions intact.

Before either documentation or hardware consolidation, retain an actual built-dist baseline inventory of every asset, rendered page, model link, Markdown/LLM page and index entry. Planted tracked and untracked fake vendor/private inputs under each new docs/references, docs/dossier and hardware/rig home must remain absent from every output and index. Existing public assets/pages keep their original identities and bytes through an explicit source-to-public-path map; do not broaden a copy/document allowlist just because a directory moved.

Stage 4 is not a shell-only move: rig is the importable Python package used by services, tests, HIL and hardware instructions. The installed service uses `python3 -m rig.rs04_bridge`, inventory/profile tools use the same package, and package.json/Jetson CI invokes rig.tests. Firmware path strings are live sourced-limit identities in hardware profiles/configs; body-firmware CI/CMake/MCU toolchain and HIL reference them. Both moves have publication consequences: the current builder copies hardware/** and renders all hardware Markdown, so hardware/rig would newly publish operator Python/README and hardware/firmware would newly render its Markdown unless excluded explicitly. Preserve former publication semantics with the same baseline inventory and planted tracked/untracked exclusions as the docs moves.

The Python import contract must be chosen explicitly before a move. A hardware.rig namespace requires every absolute rig import, service entry, CLI example and root-discovery calculation to be updated and genuinely exercised; moving the directory alone cannot preserve python -m rig. Prove the staged installer/service subprocess from outside the checkout using the emulator, and rerun the actual lifecycle/vector suite on both supported Python versions. Existing owners of #202/firmware and runtime work must be coordinated before changes. Regression evidence must include actual install/service command, protocol vectors/profile derivation, both Python lifecycle suites and host/MCU/HIL checks appropriate to changed paths. No hardware run or safe-stop qualification can be inferred.

Stage 5 groups learning with simulation, but RL work is currently heavily dirty/uncommitted in the original checkout. That work is outside this agent's ownership. Inventory actual imports/checkpoints and contact its owner before implementation; do not move or rewrite that dirty checkout. The 19-entry endpoint is conditional on this real ownership boundary. Publication is also conditional: sim/** is currently copied but rl/** is not, so sim/rl must not silently publish RL code, checkpoints or Markdown. Apply the same actual baseline and tracked/untracked planted exclusion proof to this optional home; do not assume a simulation parent is a safe publication boundary. If blocked, 20 entries is still achieved by the first four coherent homes without touching RL.

Manifests and tooling were considered explicitly: moving package.json/package-lock.json/.nvmrc below root would remove three more entries, but changes normal npm/Node discovery, Cloudflare build root/cwd, every workflow and many documented commands. Keeping these conventional root files is the lower-cost choice once the ownership grouping reaches 19–20. tools already has 136 direct files, so new fixtures get a subfolder and web assets go to their existing UI owner rather than adding29 more tools files.

This map is a proposal for independent review after current stack/release; no speculative geometry, physical qualification, alias, hash reseal or new product feature is included.

## Navigation beyond the root count

docs still has64 direct files and 136 direct tools files; 20 root entries alone is not completion of the requested human entrance. Follow the owning-home moves with short maps and domain groups rather than one long directory listing: docs should expose physical progress, body, legs, turret, controls/software and validation through a small number of linked topic entrances, while existing engineering anchors and evidence identities remain addressable. Tool entry points should be grouped by site build/check, evidence generation and engineering validation only after their root assumptions, entry commands and receipt recipes are mapped. Exact direct-file targets and consumer/publication updates belong in the focused implementation review; this plan does not claim the present64/136-file homes are already pleasant to navigate.


## Stage 1 publication checkpoint

Stage 1 completed through reviewed #233 and normal release #234: main `2a2e4853012ae16179818fea22f8f4a69b57bae1` has 26 root entries (28→26), identical fixture bytes and actual GitHub `.github/CONTRIBUTING.md` discovery. Complete fleet 202 publication/private-input/consumer checks and the [actual production readback](https://github.com/Valpatel/gyropup/pull/234#issuecomment-6678019881) provide the scoped evidence. The later stages above remain unexecuted and conditional; #219 stays open. Next is a dossier-only preflight for a possible 26→25 move, including actual toolkit/config/receipt readers, preserved bytes, unpublished-input exclusions and stale dossier facts. This does not refresh dossier engineering acceptance or authorize its regeneration by metadata editing.

## Dossier reader precondition and candidate scope

The [complete fleet 206 reader preflight](https://github.com/Valpatel/gyropup/issues/219#issuecomment-6679331962)
and [independent result](https://github.com/Valpatel/gyropup/issues/219#issuecomment-6679341482) verify the ten YAML
identities, actual input opens, unchanged semantic declarations/options and no-write protected files. Both actual
lint results still fail with 27 errors/two warnings, and six geometric gate rows stay stale. Failed 205 remains
failed: its first comparison rejected eight absolute gate-file locations and two embedded diagnostic locations;
the reviewed replay maps only those exact fields and rejects target/message/line/severity/data mutations.

The candidate implementation groups only those ten byte-preserved YAMLs in `docs/dossier/` and adds one short
GitHub reading map. Root 26→25; docs total 88→99 with 64 direct files unchanged, and tools 136 direct files
unchanged. These public-repository inputs retain their unpublished-site boundary through raw copy, model list,
document list, source-link classification and directory-index exclusions. Exact-source review and actual
tracked/untracked payload, sibling-boundary, GitHub-link and complete artifact controls remain required before
integration/publication. This is not a research/reference/firmware/rig/RL move, dossier refresh or engineering
acceptance; #31/#219 remain open. Keep the [branch-limit correction](2026-11-05-paused-work-needs-the-actual-head.md#keep-draft-limits-separate-from-the-published-branch)
when interpreting main versus unmerged #207.


## An ownership rename is not new design evidence

On 2026-11-06, the #238 timeline consumer still independently read Git with `--no-renames` and only the former decision-file path. A byte-preserved CAD move was consequently interpreted as deleted/added design evidence by the check, while its producer already excluded `R100` changes. The owning `hardware/` prefix also misclassified new unpublished CAD package glue as electronics. These are history-consumer consequences, separate from model/source freshness.

The existing timeline test now uses a real isolated Git repository: an actual R100 `cad/fivebar.py` move to its mapped owning path produces no design event, deliberately forcing the old no-renames behavior produces one, and a subsequent real CAD edit remains visible as one CAD/leg event. That focused actual test passed in1.1s using the retained219 product only to satisfy unrelated module imports; it is not a current-product browser or full-history validation. The temporary product link and owned test listener/browser were closed. Both current and historical decision paths remain checked, all timeline limits remain unchanged, and the independent full-history/current-product checks remain required. Timeline classification does not grant unpublished source a public URL.
