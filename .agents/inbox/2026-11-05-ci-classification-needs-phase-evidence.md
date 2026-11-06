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
