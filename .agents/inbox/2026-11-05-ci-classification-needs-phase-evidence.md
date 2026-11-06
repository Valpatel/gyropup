# Separate provisioning and cancellation from validation failures

On 2026-11-05 (local; timestamps below UTC on 2026-11-06), current reviewed
Gyropup PRs hit the existing 20-minute GitHub job ceiling after unusually long
dependency installation. Both attempts remain incomplete, not passing evidence.

Dated command/output evidence:

```text
gh api repos/Valpatel/gyropup/actions/jobs/127629288820
  head 0e95b67a; conclusion cancelled; 00:32:03–00:52:18
  Playwright installation 00:32:26–00:41:08 (8m42s)
  validation started 00:41:21; interrupted during highlight integration

gh api repos/Valpatel/gyropup/check-runs/127629288820/annotations
  The job has exceeded the maximum execution time of 20m0s

gh api repos/Valpatel/gyropup/check-runs/127629356508/annotations
  The job has exceeded the maximum execution time of 20m0s
  layout installation 00:33:29–00:41:45 (8m16s); validation 00:41:56 onward
```

The first job's preview log scheduled its temporary listener until 01:11 UTC.
Runner cancellation around 00:52 stopped it early. Integration then reported an
interactive-robot failure and connection refusal at 00:52:13; its retained
request report shows interrupted transfers. These terminal messages are not a
completed source assertion verdict. The second job's unfinished layout sweep
also received connection refusals during teardown. The layout measured 1486 of its required 1520 views (152 pages), with zero
findings in that subset. Neither run becomes passing because a measured subset
had no findings.

The separate full presentation job 127629356441 passed at reviewed head
e6102749 after a 22-second dependency step. The exact cause of the slow
installation was not established; do not invent a mirror, cache or package-lock
explanation from duration alone.

Corrective rule: inspect the first failing event, check annotations, step timing,
listener lifetime and retained per-command artifacts. Distinguish an actual
assertion, core readiness timeout, provisioning delay and global cancellation.
A narrowly targeted same-head rerun is appropriate for a classified incomplete
job; it must actually finish every required case. Keep failed/cancelled attempts
and compare the new phase receipts. Do not rerun a genuine assertion until green,
count a subset as coverage, weaken thresholds, or enlarge a budget merely from
a summary check marked failed. Existing limits, mirrors and caches stayed
unchanged for the two targeted attempt-2 jobs (127638099588 and 127638106379).

Limits: a timeout can coexist with a real product defect. Cancellation does not
prove every preceding message harmless; inspect event order and require complete
validation. This record establishes this observed failure class, not a blanket
infrastructure exemption. No physical hardware result is implied.


## A cloned checkout still needs the requested runtime

Fleet job 182 on cpu-c at `bd95fb6d930a02a9fa4fde57a84e48d17a99cd4e`
cloned successfully but exited 127 because `npm` was unavailable, before any test
ran:

```text
fleet-run status 182: FAILED, exit=127, command_wall_s=0
fleet-run log 182: bash: line 2: npm: command not found
```
 This is a runtime-provisioning failure, not a failed test or completed
validation. The unchanged source/command/limits were resubmitted on the known
Node-capable cpu-b role, where the earlier fleet 177 recipe had succeeded. No
global runtime installation or source edit was performed to hide that failure.
Check runtime availability for the selected execution role; a successful clone
alone does not establish that a build or its assertions ran.


The unchanged-head targeted reruns completed: presentation job 127638099588
used 22-second dependency setup and finished successfully at 01:09:41 UTC;
layout job 127638106379 used 16-second setup and actually measured all 1520 views
with zero findings in 518 seconds. This accepts the completed new executions,
not the incomplete original attempts.

In these reruns, GitHub also returned new IDs for previously completed matrix
siblings while preserving their original execution timestamps. For example,
job 127638136358 reports attempt 2 but ran 00:32:02–00:36:40 UTC, before the
targeted rerun began at 00:54. Compare actual step times, not only an attempt
number, before claiming that a check executed again. Unchanged-head prior
completed checks were retained; only the incomplete jobs were rerun.


## An executed negative-control assertion requires a source correction

Fleet 186 on cpu-b at `ed8000abd11cb8d011d1c9f606a1c0b7f95b4635`
ran the new walls controls and exited 1 at `lazy-primary must fail readiness`.
The earlier badge/font controls had completed, but no full sweep ran. Its held
primary exposed an actual source error: the pinned Playwright polling code
truth-tests a returned Promise before its false value resolves. An actual
`waitForFunction(async () => false)` probe returned false in 19 ms despite a
2-second deadline. The image readiness check therefore completed prematurely.
This required synchronous readiness polling and bounded native-promise
completion/error states, followed by strengthened font/decode controls. It was
not a runtime-installation failure, a global cancellation or grounds for a
retry-only green result. Preserve that failed source attempt and require fresh
corrected-source evidence.

## Per-face evidence separates a readiness contract defect from a slow run

At `998fd92c`, fleet187 failed the README held-badge positive and diagnostic188
retained the exact browser state: actual text-load promises done without error,
Inter/JetBrains Mono loaded with fulfilled native promises, global set status
still loading, and only the held Stars request pending. GitHub attempt1 run
42148700612/job127666350122 passed the six controls but later hit the same font
boundary in its ordinary page loop; that page/request was not recorded. These
are genuine incomplete readiness results, not ARM-only failures or successful
measurements. The narrow correction retains actual load-returned faces and
native loading/error checks, with a real failed-font negative. See the
[rendered-readiness incident](2026-11-05-layout-readiness-must-wait-for-fonts-not-global-load.md).
Fresh corrected-source full coverage remains the acceptance condition.

## Supply every historical and browser input to a validation command

On 2026-11-05, release-prep fleet 196 at c4154dd6 built successfully but the existing Progress historical-converter guard stopped before browser launch: the shallow command fetched original producer e7b512870a39259a04a4930e2908af84001bc84e but omitted recorded converter e93b3bbce57ee36fc966e8ba4513f05273a75967. Full-history git show of that converter matches its recorded SHA. The corrected command fetches both actual receipt pins; no source, receipt or guard changes.

Fleet 197 then genuinely passed the Progress consumer (21 layouts, actual verified movies/negative controls, 37 log entries, no page errors), but the following doc-pages global hook failed because PLAYWRIGHT_CHANNEL=chromium had been scoped only to the preceding subprocess. No doc-pages assertion ran and later checks were not reached. The remaining checks use an exported supported-browser choice and the same source/limits; Progress is not rerun. Both original attempts remain FAILED overall.

Corrective rule: enumerate every immutable producer/converter history input from the committed receipt before shallow validation, and apply the intended browser environment to every consumer in a command batch. Preserve missing-input and setup failures separately from actual assertions. Existing guards correctly refused unavailable prerequisites; do not weaken or reseal them. Record which assertions actually ran, retain products/screenshots on failure and rerun only the uncovered checks. This is a command-recipe correction, not a product or physical qualification result.

The later release #232 layout job 127696765197 was cancelled at the same
20-minute global ceiling after 8m40s browser setup. Its controls passed but its
retained artifact has no final results.json, so no completed coverage count is
claimed. The layout-only unchanged-head replacement 127703807998 used 21-second
setup and completed all 1,520 unique views with zero findings in 701 seconds.
Source, thresholds and limits stayed unchanged; only that completed execution
provided passing coverage.

## Compare generated cache queries without exempting engineering outputs

On 2026-11-05 (2026-11-06 UTC), stage-1 root cleanup at `5fe7e12430477ef76f80fb6666ed59bd095faa3f` kept the three motion fixtures byte-identical. Fleet 201 on cpu-b genuinely built baseline `4f1441b7a1ccb84d6222ccb095fcf30d302eb795` and candidate, then failed the overbroad expectation that every published engineering-prefix byte would be unchanged. No private-input controls or browser consumers ran in that attempt.

Complete retained inventories and actual products contain the same 2,973 paths. All 1,904 raw engineering records and 77 published JavaScript modules are strictly identical. The 132 changed engineering paths are generated directory `index.html` files, proven absent from tracked source in both immutable revisions. Every actual byte difference is the bounded actual-version query substitution `49bb352c2c4855d03109` to `5d22e57e5434776ee793` after `?v=`, `&v=` or `&amp;v=`. For example, `exports/motor-day/index.html` changes `/web/theme.js?v=49bb352c2c4855d03109` to `/web/theme.js?v=5d22e57e5434776ee793`.

The independently checked replacement retains every raw hash comparison and checks all 132 index files individually against only those exact keys from their actual `version.json` products. Planted changes to `href="parts/"` and an unexpected asset query value are rejected. Do not ignore HTML, strip arbitrary queries, replace all hash-like strings or narrow source/receipt closures. This classification is not new CAD evidence and does not authorize regenerating/resealing receipts.

## Verify fetched products against the remote inventory

The initial `fleet-run fetch 201 <owned-destination> --outputs-only` omitted real product files. At tool commit `602d954e2f5d5d76dd8ac85570c6609ae1a83fe8`, `slurm/scripts/fleet-run` SHA256 `cb520154788c008a05f86d7e76d7a868a0a2a989a32282b9dc43dc920502a6f8`, its unanchored rsync `--exclude src` also excludes nested product `src` directories. Missing paths included `out/{before-dist,dist}/firmware/balance/src/{index.html,core/index.html,host/index.html,mcu/index.html}` and their raw firmware files. The remote inventories still listed those files. A retrieved subset is not a complete product.

A full read-only `fleet-run fetch 201 <owned-destination> --max-mb 3072` recovered the complete owned run; the 2048 MB attempt correctly refused its 2492 MB size. Every path, size and hash in both recovered products then matched the remotely retained inventories. No product source or fleet tooling was edited to hide the omission.

Corrective rule: archive complete products inside the output directory before assertions, and retain their full inventories. Fetch the archives through the existing interface, extract them and verify all expected paths/sizes/hashes before claiming complete retrieved evidence. Keep temporary baseline worktrees outside the fetched run root. A future fleet-filter fix is separate work requiring its own concrete review; this fallback does not prove the tool's exclusion semantics correct.

Evidence: [failed 201 command/classification](https://github.com/Valpatel/gyropup/pull/233#issuecomment-6677525523), [complete classification and exact 202 command](https://github.com/Valpatel/gyropup/pull/233#issuecomment-6677606687). Fleet 201 remains FAILED; only the actual completed assertions of a later run can validate the previously unreached controls and consumers. No physical qualification follows.

The unchanged-head replacement fleet 202 on cpu-b completed with exit 0 in 246 seconds (269 seconds total). Its strict 1,904 raw comparisons, 132 individually eligible generated-query comparisons and both planted mutations passed, then the actual stale-old/missing-current fixture control, tracked/untracked private inputs in both new homes, three real model consumers, Markdown 6/6 and privacy 10 passed / 1 expected skip all ran. Both archived products were completely retrieved and all 2,973 paths/sizes/hashes in each matched their original remote inventories. See the [completed 202 result](https://github.com/Valpatel/gyropup/pull/233#issuecomment-6677677245). This accepts those actual completed assertions without turning failed 201 into a pass.

## A new version response is not complete publication evidence

After normal release #234 merged main `2a2e4853012ae16179818fea22f8f4a69b57bae1` at 2026-11-06 05:46:55 UTC, initial ordinary production reads still reported preceding main `bfcdbc1188ebcb49c69d1ff9f8acde8f83558eb9`. The first new version response reported assets `c33c7d5c3224d20d4ae4`, built 05:48:50.105Z, but the source-byte check rejected `docs/README.md`: SHA-256 `9af20eda3828e784b69a646266f95e83119a979e99795b3be6936d658ebbbd66`, exactly the preceding committed source. No completed publication was claimed from that partial readback.

The next ordinary `curl --fail --silent --show-error --location --max-time 20 https://gyropup.com/docs/README.md` returned SHA-256 `8cc7e171bbc3aeeb6807f2413a71ccfd32ac80375351b49aada2b672b3731cea`, matching both the new committed source and the actual fleet 202 product. A subsequent complete readback verified all 25 selected committed files and four canonical routes/markers, with the identical ordinary `version.json` before and after. GitHub's community-profile API independently selected `.github/CONTRIBUTING.md`; its content API bytes, main root count 26 and all three fixture identities matched. See the [actual publication receipt](https://github.com/Valpatel/gyropup/pull/234#issuecomment-6678019881).

Cause and limits: the cache/deployment layer responsible for the old-then-new document response was not established. This is an observed initial mixed readback, not proof of a particular cache defect or a failed product build. No cache policy, authentication, source, hash expectation or route acceptance changed. The final full readback establishes those actual responses at that time; it does not turn the earlier mismatch into a pass or guarantee all future responses.

Corrective rule: verify the resulting normal main merge revision/tree, ordinary public version, changed source-byte identities and real canonical routes together. Record old-version or mixed-byte observations separately. Recheck a classified incomplete deployment readback with unchanged expectations, and require a complete consistent result before marking publication or closing dependent acceptance. A version response alone, a GitHub merge, a preview deployment or an unverified subset is insufficient.


## Materialize exact helper bytes before expensive setup

On 2026-11-06, dossier continuation fleet 212 on cpu-b at 949b73c2 verified all54 retained product/reader identities and the fresh clone's protected source, then FAILED before its reuse/browser/final checks. The exact-byte guard correctly rejected a shell heredoc that added one terminal newline: expected 23,201 bytes/SHA8095cd278c263e741f05ef1930799a750893e06388e094a7cf8bdc1f0b3ecdfb; emitted 23,202 bytes/SHAe1f41ae6d96a59d184948e3c5942c394e3e29256b359ddfb0ceb36746453d04e. The author's assembly and review's whitespace-equivalence comparison missed that conflict. Do not relax the guard. Materialize every helper and check actual emitted byte lengths/hashes before dependency installation. The corrected seven-helper Bash preamble was actually executed locally and matched all frozen bytes; no new job was submitted merely for a monolithic green label. [Final review 236](https://github.com/Valpatel/gyropup/pull/236#pullrequestreview-5798132539) instead composes independently verified retained controls with actual same-tree currentCI. Failed 205/210/211/212 stay failed; original 211 final worker state remains unverified.

The earlier 211 literal-marker failure was also a harness representation error: raw/HTML had literal underscores, while the actual Markdown renderer escaped them. Require full Markdown equality to the real renderer on the exact HTML and exact decoded marker identity; altered content and coherently missing marker controls must fail. Never strip escapes broadly.

## Shared worktrees also share shallow Git metadata

During immutable-tree proof on 2026-11-06, depth-one fetches were used in a linked checkout. The common repository subsequently reported `git rev-parse --is-shallow-repository` as true; the prior initial shallow state was not retained, so the first cause is unknown. Depth fetches can change the common shallow boundaries, affecting ancestry/parent display and history-aware builds in other worktrees without changing source bytes. A normal `git fetch --unshallow origin dev main` completed successfully and restored false; dev 776d5f44/main 2a2e4853 and source files remained unchanged.

Rule: never use depth-limited fetches for immutable-object proof in persistent shared-worktree repositories. Fetch normally, or use an isolated scratch clone. Before shared ancestry/history-sensitive operations, explicitly check the common repository's shallow state; do not treat truncated ancestry as a branch disposition. This guard is scoped to persistent shared repositories, not a demand that every intentionally shallow CI build claim full history. Record actual build history provenance and preserve already-produced artifacts.


## A passing summary can still miss an unintended publication

On 2026-11-06, owning-layout static fleet 215 at 65ef1874 passed its build, six Markdown checks and ten privacy checks (one environment skip); all 3,002 retrieved output records matched their inventories. Actual path inspection still found four unintended new web/index and web/highlights/index HTML/Markdown pages. Copying tracked web assets had accidentally added web to directory discovery as well. Keep copy and discovery/model/index ownership distinct. The existing Markdown exclusion test was refined and demonstrably rejected the retained real 215 product at web/index.html; the fix must then pass on a genuinely rebuilt product. Another 25 differences from 211 were historical timeline images under history=true versus 211's history=false, so before/after publication comparison must use compatible history provenance. None of this qualifies CAD, service, provenance or physical results.

Release 239 supplied a separate provisioning-only case: its original build-portal job reached the global 20-minute limit during 10m28s browser installation and 9m20s ffmpeg setup, before build/assertions/artifacts. [Independent classification](https://github.com/Valpatel/gyropup/pull/239#issuecomment-6682582144) allowed one unchanged targeted retry, requested at 2026-11-06 10:21:21 UTC. That failure is not an assertion result; the retry's actual executed phases must be read independently.

## Select the temporary worktree parent before dependency setup

On 2026-11-06, paired source-layout fleet217 on cpu-b at4aba2832 FAILED before either build. The strict outside-run check rejected `tempfile.mkdtemp()`'s default location inside `FLEET_RUN_DIR`; the fleet wrapper sets its per-job `TMPDIR` there. The dependency phase had exited0 in4.93s, but products, Markdown/privacy assertions and final source/product guards were not reached. The result retained `status: FAILED`, an empty product map and `owned_baseline_removed: true`; cleanup's128 means the rejected empty directory was never registered as a worktree and was then removed by the owned fallback. This is a helper/source assumption, not a product assertion, provisioning outage or flaky external dependency. No partial build is credited.

Rule: when a comparison worktree must live outside a run directory, explicitly select and resolve its parent (here `/tmp`), assert that boundary and create the owned empty directory before dependency setup. Do not assume Python's default temporary directory is outside the project. Keep both checkouts' full tracked source snapshots/clean-status guards, regular-only product inventories, compatible history/lock requirements and owned cleanup. The proposed correction preserves all build and output checks; it requires a fresh bounded run and independent review. This does not authorize shared temporary-directory cleanup or deletion of another worktree.

## Native verification needs its real library configuration and full output accounting

On 2026-11-06, the parent agent's isolated native carrier replay used exact sourceb6b6b3f3 and existing KiCad10.0.1. Exhaustive inspection found two stale entries among20 receipt bindings: README.md and fault-review.md, each changing only the input-requirements link after the research move. The first raised assertion names one file; it is not proof that only one binding changed. Enumerate the complete recorded set before describing the cause.

The [first bounded executor](https://github.com/Valpatel/gyropup/pull/238#issuecomment-6684577005) FAILED in2.12s at actual ERC exit5:23 footprint-link warnings, zero errors, because its isolated configuration lacked four stock library tables. No tests/postverify were reached. The source, failure and complete output archive were retained. Do not weaken `--severity-all` or the ERC exit check; prepare the required stock table and referenced footprints in the child-only runtime instead. The source did not need a circuit change.

The [reviewed revised executor](https://github.com/Valpatel/gyropup/pull/238#issuecomment-6684678492) completed in7.179s, maximum RSS287412KiB: zero ERC warnings/errors, all26 actual native tests without skips and post-verification passed. The29 components,102 package leads,14 nets and12 NC groups remained unchanged. Its full23-file archive SHA-256 is18e3191ad92feed563486e2a228c2db24240bcc9a9e0f7ff47e9d71e8991e941. All22 tracked input identities matched the frozen source; only the generated receipt changed its two documentation digests. The existing ignored `.kicad_prl` was retained as a runtime output, not adopted or treated as a new repository-ignore defect. [Independent artifact review](https://github.com/Valpatel/gyropup/pull/238#issuecomment-6684706031) allowed receipt-only adoption. The author freshly checked the22-file closure, copied the real receipt bytes SHA-2569337005e32f613cde0d010dd34105dcee0ea7df6d64aad1ee21109a8074c62e5 unchanged, and ran the actual verifier. No ERC, numerical, engineering-selection or physical qualification boundary changed.

Executor lessons also apply to other isolated producers: cleanup must account for owned descendants even if their group leader exits early; inventories must reject FIFOs and other nonregular entries as well as links; preserve and classify every runtime file before acceptance. Keep child-only runtime configuration separate from the source tree and shared user state. Archive complete outputs before assertions, preserve the original failed phase and actual passing phase separately, and verify the immutable input closure again before adoption. This bounded quick native phase does not authorize long CAD/simulation work on the shared workstation.


## Source relocation can require real paper recomputation without changing its conclusions

On 2026-11-06 the parent agent ran the three actual carrier inventory, allocation and practical-architecture producers at source1bfdee9c. Their two original stale checks rejected the old bindings; the genuine replay completed in0.718s with23 packaging and8 architecture tests, no skips. The complete28-file archive SHA-256 is a4373abf3cd2843123d42af6c07f18dcd9b67e6d3249fd2d5f8b28799e633656. Independent review classified every changed field:18 inventory source references and6 inventory bindings,3 allocation bindings and4 architecture bindings. All other data, dates, topology, arithmetic and qualification flags remained byte/field exact.

After freshly comparing all28 inputs to the original recorded identities, the author adopted only the three real generated JSON files together; the [adoption map](../plans/owning-hierarchy/paper-receipt-adoption.json) records their exact hashes. Both actual current checks then passed. The47 electronic items,19 control-wire candidates,4 power-wire candidates,21 external positions and retained0.5/37.67/0.8mm arithmetic remain unchanged; physical, fit and electrical qualification remain false. See [actual result](https://github.com/Valpatel/gyropup/pull/238#issuecomment-6684879845) and [independent artifact/adoption review](https://github.com/Valpatel/gyropup/pull/238#issuecomment-6684895033). This scoped paper replay does not validate pending CAD, media, slicing or whole-migration acceptance.


## Separate the collection inventory from each producer's actual freshness contract

The final paper/insert replay at67ae1605 on2026-11-06 tested an overly broad expectation that changed help-only source bytes must stale every generated study. The complete archived input inventory is evidence of the isolated collection; it is not automatically the digest/semantic contract of every generator. Read the actual consumers before requiring stale preconditions or changed outputs.

The genuine paper replay completed in0.717s with31 actual tests: only inventory's turret_boards.py binding and allocation's resulting inventory binding changed. Architecture was already current and remained byte-identical. After a fresh28-file original guard, only those two real JSON outputs were adopted together. The genuine insert replay completed in2.069s with43 tests and exact v0.18.2 imports; both initial checks were already current, and its entire39-file inventory, including allfour generated products, remained byte-identical. A fresh39-file guard confirms that result; no insert file was recopied or re-signed. [Independent artifact review](https://github.com/Valpatel/gyropup/pull/238#issuecomment-6685909967) and [exact adoption/confirmation identities](../plans/owning-hierarchy/final-paper-insert-confirmation.json) retain the original records and qualifications.

Corrective rule: derive producer ordering and acceptance from actual read/write dependencies. Keep complete collection inventories and unchanged-product evidence; do not manufacture a stale check, demand a fixed number of changed files, or update hashes merely because an archived source changed. Conversely, part-media's two catalog writers really are whole-CAD snapshot members, so they must precede the later92-input generation. That actual dependency caused220's cancellation; it cannot be bypassed by the insert study's different semantic contract.


## Capture the child handle before delivering termination signals

Before restarting the long CAD collection on2026-11-06, independent review injected a real SIGTERM after the operating-system child existed but before `Popen` returned its handle. The earlier helper marked the group nonquiescent and refused archive/restoration, but had no captured handle to settle that child. The reviewer killed/reaped its own harmless control process; no CAD producer ran in the test. This is a launch/cleanup boundary, not a geometry or source-input change.

The runner now uses the existing reviewed signal-blocked capture pattern: block SIGINT/SIGTERM through `Popen` and handle assignment, unmask the inherited set in the child, then restore the parent's mask inside the protected outer try/finally. A real-signal control on the actual helper sends TERM before returning the handle, observes the original interruption, and verifies that the captured group is killed/reaped; a second actual child confirms its signals are unblocked. The complete92 CAD inputs remain unchanged. This complements the subreaper/early-leader/observation controls; sending a signal alone does not prove quiescence. It does not claim recovery from uncatchable termination, or permit archiving/restoring while a producer remains active.
