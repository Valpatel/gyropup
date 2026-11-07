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


## Isolated Python still has a system startup identity

The parent's first snap/screen collection at11514f3d on2026-11-06 failed in its toolkit probe before any generator or test. Its blanket assertion that `python -I` must have no `sitecustomize` rejected the observed standard Ubuntu startup hook: the system link resolves to `/etc/python3.12/sitecustomize.py` and loads Apport. All40 collection files remained byte-identical and the owned group was gone. [Original failure](https://github.com/Valpatel/gyropup/pull/238#issuecomment-6686461928) is retained. Presence of that named module is not evidence that a foreign cad-agent package was imported.

The minimally corrected bridge classified the actual nine system-startup records by exact identity/hash and still required the selected toolkit version, source origin and imported module hashes at Git pin8e244f0c. No global runtime, project source or permissions changed. Its actual collection completed in2.622s with all46 existing tests and three real toolkit child calls; original snapfit JSON and allfour measurement CSVs remained exact. After a fresh40-file guard, only the five reviewed genuine path/provenance outputs were adopted together; both existing final checks passed. [Artifact review](https://github.com/Valpatel/gyropup/pull/238#issuecomment-6686582412) and [adoption record](../plans/owning-hierarchy/snap-screen-adoption.json) preserve the original `adoption_pass=false` collection receipt.

Rule: distinguish observed system startup from user-site/PYTHONPATH or toolkit contamination, and verify the actual import/source boundary. This narrowly classified Ubuntu runtime is not a universal allowance for arbitrary startup hooks; unknown or changed startup identities still require diagnosis.

## Check shared runtime identity instead of a particular import spelling

On 2026-11-06, PR238 at bbf33b27 presentation job127939809811 reached the pronunciation suite and failed its literal `from pronunciation import pronounce` source-text assertion. The moved sidecar actually imported the same function through `tools.audio.pronunciation`; the preceding behavior checks passed. This was a stale implementation-spelling check, separate from the genuine source-bound media and geometry failures elsewhere in that run. Preserve that failed attempt rather than reporting the whole presentation group as passed.

The existing test now requires the actual sidecar function to be the same Python object as the tested shared implementation, and verifies that module's current checkout origin. Its key-file and browser/Python output comparisons remain. All 10 existing tests pass; substituting a different function in the actual imported sidecar makes the refined existing assertion fail. Current executable-help paths were corrected at the same time. An overly broad initial help replacement briefly doubled an already-qualified path; the actual test caught it before commit. Use bounded/idempotent path replacements and inspect runtime AST differences, not just source-text grep. The final two tools differ only in help/comments and the exact argparse description; no pronunciation rule or voice setting changed. This proves shared implementation/key use, not Piper synthesis, playback or whole-site acceptance.

## Provision every post-adoption reader before mutating its targets

On2026-11-06, the first guarded adoption of fleet223's reviewed15 public geometry targets reached three successful kernel-free readers, then the full acquisition/survey suite failed because the local system Python had no cad-agent module. The runner restored and rehashed all15 originals. This was a local reader-runtime setup failure; the genuine remote collection and independent artifact review remained their own evidence. It was not a reason to reduce the reader's test coverage.

Before the second adoption, the exact public toolkit2ad4269 source was extracted from the already-held immutable Git object into an owned temporary runtime, all136 source-file hashes were recorded, and its actual module origin/verdict import was checked. Only then were the full current inputs and original15 targets checked again and the same reviewed candidates copied. All five interface tests, specimen verifier/seven corruption tests and15 acquisition/survey/gauge tests passed. Keep the first failed reader log and rollback proof; do not report it as a passing attempt or install into shared user environments. The local archived-source reader runtime does not replace the collection's independently pinned CAD runtime.

## Fleet aliases are reporting labels, not scheduler selectors

On 2026-11-07 UTC, the reviewed README illustration command at Gyropup `933a222` was first submitted with `--node cpu-a`. The CLI exited 1 with empty stdout and `sbatch: error: Batch job submission failed: Invalid node name specified`. No job was assigned, and no dependency, CAD or test phase ran.

At fleet tool commit `602d954e2f5d5d76dd8ac85570c6609ae1a83fe8` (`slurm/scripts/fleet-run` SHA256 `cb520154788c008a05f86d7e76d7a868a0a2a989a32282b9dc43dc920502a6f8`), `--node` is forwarded as the literal scheduler node selector; `cpu-a` is the separate public reporting alias. After independent [selector-correction review](https://github.com/Valpatel/gyropup/pull/246#issuecomment-6702231633), one fresh guarded submission used the actual NODE from the authoritative `fleet-run nodes` table privately and created [job 231 on cpu-a](https://github.com/Valpatel/gyropup/pull/246#issuecomment-6702243083). Source, exact command and resource bounds were unchanged.

Use the real NODE column only in private operator arguments; publish the ALIAS and job ID. Preserve no-job scheduler refusals separately from native or test failures. This observed CLI version does not promise alias resolution, and successful scheduling does not prove a CAD or application result.

## Incremental retrieval can retain an earlier partial product

On 2026-11-07 UTC, job 232 on cpu-c completed after an earlier live output fetch. A second incremental `fleet-run fetch ... --outputs-only` retained the local earlier `support-candidate/probe-incomplete.json` (SHA256 `c19dd5c0ed5ae697711ceab89325bdd898256429fa3ee38004a45e82835b0712`). That file was absent from the final nine-member sealed support archive `0adbd18788044c32d9e1e43bd81879afd057d5ebd1b67e593e16b689d1cf7987`. The source/hardware restoration checks passed; this local retrieval union was not the final product membership. The observed fleet CLI was the same `602d954e`/`cb520154...` version identified above.

Preserve partial evidence separately. Rehash the sealed final archive and inventory, then extract its regular members into a fresh owned directory before adoption. Do not weaken the existing reader to ignore an extra partial file, delete evidence to manufacture a clean result, or credit a merged retrieval directory as an exact final product. The current adoption uses the exact seven lug plus nine support archive members; the earlier fetched union and partial result remain retained.

## Render the persisted scene representation before claiming parity

On 2026-11-07 UTC, README-art job237 on cpu-a at506a3a53 completed genuine read-only CAD collection/rendering in142.84s (618080KiB peak RSS), then failed the pure renderer parity command. The complete eight-member archive `3cf7df1edfb348368da755b5642e476f51456684f2fa29304fd629d6d6c8584a` preserves the scene and three unapproved candidates. Source, shared-profile and toolkit restoration guards passed; overall collection remained FAILED and the subsequent fault controls did not run.

The producer rendered its in-memory role dictionaries before writing sorted-key JSON. The shared motif paints those roles in iteration order. Re-reading the same JSON reordered the roles alphabetically: scene bytes and SVG leaf payloads remained equal, but SVG paint order and its receipt digest changed. This was a real producer/parity defect, not CAD geometry drift or a reason to replace the renderer check with unordered SVG comparison.

Render the exact persisted JSON representation during initial generation. The existing regression reconstructs the actual extraction role order and requires the real shared renderer to produce identical bundles before and after serialization. The helper's own digest is part of the extraction key, so a helper correction requires a new genuine extraction; never rewrite a captured scene's key to make an old run current. Preserve job237 and review the corrected painter order visually before adoption. Native construction success alone does not authorize artifact adoption or imply physical qualification.

## A missing local runner does not establish remote job state

During job238 monitoring on2026-11-07 UTC, the previously used local fleet-tools
checkout disappeared and its installed skill link was dangling. The cause was
not established; the coordinator had not retired it. Do not infer that a
scheduler job vanished, cancel it, or submit a duplicate from this workstation
symptom. The existing tool repository still retained main602d954e; a fresh owned
checkout was pinned after verifying the actual remote main, with the same
`fleet-run` SHA256 `cb520154788c008a05f86d7e76d7a868a0a2a989a32282b9dc43dc920502a6f8`.
No shared checkout, skill link, credentials or configuration was changed. Its
normal status/read/fetch commands established that238 had already completed
successfully and retrieved its sealed outputs. Tool recovery and actual remote
execution/artifact acceptance remain separate facts.

## Verify parser and browser ordering with the same actual document

At98a68d71, presentation job128334471366 in run42349524636 failed the new
README model-placement assertion. Actual Chrome151/WebKit26 compiled-page
checks showed What → explanation → model → Why correctly. The installed
Linkedom returned `2` for a nested image's `compareDocumentPosition` against the
following heading, even in a minimal `h2,p(a(img)),h2` document; selector traversal
returned the correct order. The new test had assumed browser-equivalent behavior
from that parser API. Replace the faulty comparison with exact ordered-node
membership, and require actual wrong-section and before-explanation mutations to
fail. This corrects the test; it does not excuse misplaced product content.

The same head's build-portal job128334471271 separately failed its unchanged
strict C3 request check after allthree viewport/assembly cases and nine negative
controls completed: one versioned `model-links.css` GET had `net::ERR_ABORTED`.
There were no HTTP/page errors. Preserve the complete29-member artifact
`8a357257a038cf373e3e4b4904fa1ddb542d7760aeb8bcd0d474f0094de83f11` and original
failure. A bounded actual-consumer trace on Chromium141 against the exact
Cloudflare98a product passed; that different hosting environment does not explain
or erase the CI cancellation. Pinned Playwright `waitForURL` already waits for
load, and that stylesheet is static: neither a redundant readiness wait nor a
blanket stylesheet-cancellation allowance is justified. Keep strict rejection
and add request identities, frame/load/navigation timestamps for recurrence.
A legitimate parser-test correction requires normal new-head CI, not a retry of
superseded98a or a claim that the unknown cancellation was a product fix.

## A correct spoken-text field does not establish the sound a visitor hears

On2026-11-07 the owner reported that the landing greeting still ran Gyropup
together. An actual production browser trace after a Sound gesture selected
recorded `c58eb622a507091c.mp3`, SHA256
`606502601e5221acf2700da76ad396aa30d9135daad9b298af7494697f9ff8cf`.
Its manifest already said “Hi! I’m gyro pup. Ready for a backyard adventure?”;
no live browser utterance or sidecar request occurred. The shared live dictionary
was therefore not evidence that the recorded acoustic complaint was resolved.
The initial no-gesture probe correctly remained master-muted and was not counted
as a reproduction. Preserve visual branding while adding the explicit short
“gyro, pup” boundary through the existing shared key and genuine clip producer.

Reviewed job239 on cpu-b rendered the seven genuinely changed clips;118other
rows/clips stayed exact. It then FAILED an existing JS assertion that still
expected the old space-only respelling. That later assertion was masked by stale
clips in preflight, and both author and reviewer missed it. Keep239FAILED and
its decode phases unreached; do not repeat synthesis to chase one green recipe.
All126original/candidate/observed archive members and final original-source stat
identities were retained. The minimum expectation correction preserves actual
key→row/hash checks and a wrong-space-only negative. An owned replay of the
sealed candidate passes actual producer check,11Python and7JS tests plus decoding
allseven changed MP3s; independent review permits coherent adoption without
resealing or regenerating. Existing recorded, sidecar-request and browser-utterance
consumer expectations use the same new boundary. The decoded greeting is3.81s
instead of3.25s, but duration or silence detection is not word alignment or a
human listening verdict. Link playable before/after evidence and retain that
acoustic limitation. No191movie source input changed.


## A no-job readability refusal is not a producer failure or an authentication diagnosis

On 2026-11-07 at11:09UTC, the reviewed short18 collection command `96a082b30d8f4b66b5926520cc7e176266dac4953f9dc62ade0e2f0485b5782e` at Gyropup `dba8954adb10cf4d796b35eaa457152e41cb89b3` was refused by the existing fleet CLI: exit1, empty stdout, `repo is not anonymously readable (public repos only): https://github.com/Valpatel/gyropup`. No job was assigned or private payload staged. The actual CLI's anonymous lookup precedes its controller request; this was not a CAD, dependency or test failure. [Original refusal](https://github.com/Valpatel/gyropup/pull/255#issuecomment-6706053012).

At11:11UTC, one bounded read-only replay of the same lookup, with the CLI's empty environment/temporary home/disabled credential helper and system config, returned public main `b61f0cd4` with exit0 and no stderr. That proves later readability, not the cause of the first failure. No account, credential or repository visibility change was established. After independent exact-operator [review](https://github.com/Valpatel/gyropup/pull/255#issuecomment-6706182087), one fresh normal submission at11:23UTC used a new exclusive0600 write-ahead receipt, unchanged command/source/resources and actual node/capacity/private-slot/no-duplicate guards. An explicit operator assertion kept `FLEET_RUN_SKIP_REMOTE_CHECK` disabled. It created [fleet job246](https://github.com/Valpatel/gyropup/pull/255#issuecomment-6706191864); the original receipt stayed unchanged.

Classify the actual boundary before retrying: a no-job precheck refusal needs retained stdout/stderr and authoritative queue/control-flow evidence. Do not infer a private repository, request broader authentication or bypass the anonymous check from this message alone. A later successful read is a diagnostic slice, not a native result or proof of the earlier cause. Any further submission needs fresh reviewed scope and its own durable receipt; this incident grants no automatic repeats. Job246 was still in progress when this incident was recorded, with actual producer/artifact acceptance separate.


## Cleanup failures must not replace the producer's original error

On 2026-11-07 UTC, independent preparation review of the turret scene collector found two error-path gaps: a settle failure could bypass phase-record persistence, and the outer cleanup could raise a new RuntimeError over an active primary producer exception. This was found before any scene producer executed.

The phase now catches cleanup and record-write errors independently and always attempts phase persistence; the original exception continues through a non-raising finally. The outer finally independently archives observations, attempts every available restoration, records cleanup/write errors and only raises a new cleanup error if there is no active original exception. Unknown nonquiescence blocks producer archives/restoration while still permitting failure metadata. First sealed payloads remain immutable; a changed later observation cannot overwrite that archive.

Actual software-only controls executed the current AST: a normal child starts unmasked; real TERM after OS child creation/before Popen return plus injected settle failure kills/reaps the owned child, retains the signal and persists its phase record; observation/archive failures still restore both files; a failed first restore still attempts the second; unknown nonquiescence performs no unsafe archive/restore; final result-write failure retains the original producer error. All six controls passed. The first scratch fixture lacked `stat` and failed its own inventory after both child controls completed; only that fixture import was corrected. No CAD, printer, native scene, adoption or current-geometry acceptance follows from these lifecycle controls.

## A private display and a private session bus are different isolation boundaries

On 2026-11-07 UTC, the first bounded RS04 package replay against `017e1e03` correctly rejected the stale original package, then failed after 12.33 seconds. The real slicer log reported a non-snap cgroup; the actual private-bus log showed `org.freedesktop.systemd1` activation failing. No sliced 3MF was produced, and the unchanged packager rejected the missing artifact. Its 24-file partial archive (SHA-256 `c590716f591df5d11ab799ceb6bce4e009b2ccfb4b1151cd676a7ac1b13f225e`) and FAILED receipt are retained; all original source, hardware, engine and profile bytes remained exact and every owned phase group was reaped.

Installed Snap/snapd was 2.78 and the pinned Bambu Snap revision 8 reported version `02.08.04.57`. Read-only source inspection of the [matching upstream release](https://github.com/bambulab/BambuStudio/blob/f977235e6d736c4c0b650520ac5a5b72cbfe9244/src/BambuStudio.cpp) shows action-bearing CLI arguments avoid `GUI_Run`; the existing-instance check is in [that GUI path](https://github.com/bambulab/BambuStudio/blob/f977235e6d736c4c0b650520ac5a5b72cbfe9244/src/slic3r/GUI/GUI_Init.cpp). The existing pinned slicer command includes both `--slice` and `--export-3mf`. This matching-version source audit is not a reproducible binary-build attestation. Snap's [scope tracking](https://github.com/canonical/snapd/blob/master/sandbox/cgroup/tracking.go) uses the user session bus, so an unrelated private bus is not equivalent to the normal setup.

After [independent runtime review](https://github.com/Valpatel/gyropup/pull/255#issuecomment-6707471244), one corrected invocation removed only the private D-Bus wrapper, retained private Xvfb/Xauthority and the unchanged normal user bus, and used a new private output/receipt. The harmless actual-prefix control first proved the child display differed from the user's display, HOME and the normal bus were preserved, Wayland was absent, and its owned group disappeared. That control did not prove Snap success. The actual corrected producer then completed in 38.34 seconds: generation 26.63 seconds and verification 4.93 seconds, with the original expected stale rejection still required. No source, engine, profile, slicing parameter, installation, GUI-instance command or printer action was changed.

Corrective rule: protect the desktop with an owned display and exact CLI/process ownership; do not assume a private D-Bus session preserves Snap/systemd functionality. Establish the installed tool's action/instance contract before using a normal bus, retain the first failure, and require a newly reviewed bounded invocation. This is the observed runtime's procedure, not blanket permission to connect to existing applications or devices.

The same preparation review found that one final `try` around engine/profile, tracked-source and hardware checks would skip the last two if the first failed. They now execute independently. Actual extracted-finally controls inject both capture failure and comparison failure, proving both remaining readbacks are saved and all errors retained without replacing the producer's primary exception. A successful cleanup or a later PASS never rewrites the first FAILED receipt.

The later scene-packet review found the same failure class across final project, complete hardware and external J501 guards. Those captures/saves and both repositories' status checks now execute independently; each declared J501 input is attempted even if another is missing. Four exact-AST controls inject tracked capture/save and hardware capture/save failures. All prove restoration still completes, later J501 hashes/status are saved, the result records the failed guard, and the original producer exception propagates. Existing signal-before-handle, next-child mask, observation/archive/restore/nonquiescent controls also pass against the corrected helper. This is failure-boundary evidence only, not native scene or artifact acceptance.

## An isolated depth-one worker needs the recorded source object too

On 2026-11-07, review of the final PR255 artwork recipe found a pre-native dependency error: the worker fetches only the submitted execution commit at depth one, while the figure configuration correctly records an earlier accepted scene commit. Current file and whole-hardware checks pass, but `git show <recorded-source>:<input>` cannot inspect an object that the worker never fetched. This was caught before submission, not a native extraction failure.

An actual owned two-commit Git fixture reproduced the depth-one missing-object result. Executing the collector's exact conditional `git fetch --depth 1 --no-tags origin <recorded-source>` recovered the expected blob; execution HEAD, full tree, hardware tree and clean status stayed identical. The existing bounded phase lifecycle applies to the fetch (180 seconds). Nine actual final-block error controls still pass after this addition.

Rule: distinguish executed checkout identity from recorded component-source identity, and fetch each actually consumed immutable object before comparing its blobs. Perform current source/hardware guards first, then recheck unchanged execution HEAD and clean status. This narrow fetch belongs only in the disposable fleet clone; never depth-fetch into the persistent shared worktree repository. Full history is unnecessary for this isolated artwork consumer, but remains mandatory for actual timeline/history builds. A missing-object setup failure is not geometry evidence or permission to substitute current blobs.

## Optional measurement tools must not block the actual producer

On 2026-11-07, fleet artwork job250 at `5cfe51dd` completed setup but failed before native extraction: `Popen` raised `FileNotFoundError` for `/usr/bin/time`. The extract log was empty, no process handle or figure directory was created, and the exact FAILED receipt remains. All earlier owned phase groups were recorded gone; the final phase conservatively retained its nonquiescent flag, which is not rewritten as a successful cleanup. Independent complete project stat/hash, hardware and both pinned-tool checks passed; the three originals remain in their hash-verified sealed archive.

The reviewed correction removes only the optional `time -v` argv prefix and calls the same already-running Python interpreter and unchanged extraction CLI directly. The 1,500-second owned phase bound and measured wall duration remain. No GNU-time install, CAD input, runtime, resource budget, parameter, renderer or artifact binding changes; no per-phase peak-RSS result is claimed. Classify this as a pre-native harness prerequisite failure, retain it separately, and require a fresh one-shot operational review before continuation. Never call setup completion or an empty extraction log a CAD or artifact pass.
