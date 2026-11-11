# A stage lifecycle change requires fresh captured frames even when geometry is unchanged

On 2026-11-10, PR #267 CI run `42813659763`, job `129821148989`, rejected the highlights reel with `Source changed: software/site/designer/kit/stage.js`. Comparing all 192 prior encoding bindings to source `76f1e243d1e87295ce085e3db28390eed12ec224` found exactly that changed path. The real lifecycle correction makes `onFrame` return an unsubscribe function and iterates a snapshot of callbacks; geometry identity does not make those changed renderer bytes equivalent evidence.

The correction was a genuine new 480-frame virtual capture from the immutable pushed source, followed by the unchanged normal encoder and independent strict decoded/raw-frame guard on an isolated rendering compute host. The guard accepted both 660-frame companions and rejected all 25 seeded faults; 11 binding tests passed. Mechanism footage emitted nine shots; battle recorded three shots, hits and knockdowns without frame errors. The adopted local files independently passed their generated output digests, all raw frame hashes and the current source bindings. [Commands, environment, hashes and raw validation output](../plans/versioned-build-guide-highlight-refresh/adoption.json) record the result.

Corrective rule: when a required captured renderer input changes, capture new frames against the frozen source. Retain the lifecycle fix and strict source/instrumentation contracts. Do not substitute hashes in an old capture receipt or treat a re-encode of old pixels as a fresh capture. Use the historical-insert exception only for its independently enumerated unchanged captured inputs, never a changed stage source.

The first compute attempt failed before capture because an existing dependency snapshot was copied to a folder named `deps`; Node resolved symlinked packages there and could not discover sibling dependencies through its `node_modules` ancestor lookup. An owned-scratch `node_modules` link restored resolution without installation. Preserve package layout or verify lookup before the capture; source and dependency content identity alone do not establish module resolution. Both ends matched 4,616 file entries and a sorted manifest digest recorded in the adoption receipt.


## Smoke-test the real staged package layout

The first current CAD media invocation at `76cc5b3d` repeated that layout failure on 2026-11-10. The frozen source fetch exited 0. The build exited 1 with `ERR_MODULE_NOT_FOUND` for `htmlparser2` under the symlinked `linkedom` package, before any capture. The [original terminal checkpoint](https://github.com/Valpatel/gyropup/issues/193#issuecomment-6781497743) records the failure separately.

The fresh invocation staged the same 4,616 dependency files in an actual `node_modules` directory. Its bounded pre-build Node ESM probe resolved both packages to the owned staged tree and parsed an HTML fragment through each. A copied-tree control reproduced the original failure before renaming the directory and passed afterward. Check module resolution from the exact source working directory before running the full build. The [adoption receipt](../plans/end-packs-highlights/adoption.json) preserves both attempts, the exact-byte identity and the separate browser diagnostics.

Limits: native Chrome capture does not establish pinned CI browser parity or physical behavior. Historical leg and E1 source/video/failed strength limits remain retained. No hardware or runtime source changed during media adoption. Independent review and full current CI are separate integration requirements. This repository has no `.agents/WRITING-IT-DOWN.md` at this revision; this incident follows the supplied lesson/evidence/cause/rule/limits format and is indexed here.

## A copied live phase guard must bind to the new sealed source

On 2026-11-11, independent [action review](https://github.com/Valpatel/gyropup/pull/315#pullrequestreview-5854097249) blocked the first composed-source media packet before any operator, preflight, SSH, browser or run. Its plan and built source named `59f20f62`, while copied `serve-phase.mjs` still asserted the historical `acd084a` version. The actual extracted assertion rejected the current source and accepted the archive. Correct plan/source hashes did not establish the identity of every executed phase consumer. The original 19-file packet and BLOCK remain immutable.

The separately reviewed corrected packet reads the sealed staged plan and calls the same pure revision validator tested before any producer child. Dated actual control evidence:

```text
2026-11-11 UTC: node version-guard-controls.mjs
LIVE_VERSION_BINDING_CONTROLS_PASS
currentAccepted=true; oldActualGuardRejectsCurrent=true; oldActualGuardAcceptsArchive=true
archival/different/missing/empty/short revision and invalid/missing plan source reject
browserLaunched=false; serverStarted=false; remoteAccessed=false
```

Run the actual helper/callsite controls before network probing and repeat them in the existing bounded observer-control phase. Audit live version comparisons separately from legitimate historical insert, fixture, model-authority and ancestor references; do not globally replace old revisions. The corrected packet retained all resource caps, observer bytes, context counts, mandatory source guards, originals and protected legs. Its [accepted adoption record](../plans/public-entry-closeout/media-adoption.json) binds the resulting fresh 480-frame capture, 486-source actual inventory and seven exact accepted outputs. Final worker/browser errors were empty; seeded historical negative-control stderr remains preserved and is not reclassified as an empty stream.

Pure controls establish the version binding, not rendering acceptance. Independent exact action review, root START, terminal/cgroup verification, actual artifact review and root acceptance remained separate. The source/capture receipts were not restamped, and the initial packet block was not a product failure or failed remote run. Pre-adoption CI failures remain separate acceptance work; media adoption alone does not clear them.
