# A readiness timeout needs the current scene and requests at its failed wait

On 2026-11-11, PR315 source59f20 CI run42961981559 completed314views in each
phone, iPhone and tablet partition but failed the simulator's existing30s core
readiness check. Those artifacts reported zero simulator layout findings, but
retained no body/startup/scene/error/request state at the failed wait. Neither
zero gap findings nor the generic message establishes whether model loading,
a script exception, a late ready flag or another condition caused the timeout.
The default route resolves to the current v2 model; no blocked-v1 cause is assumed.

```text
2026-11-11T05:02:45Z phone-360:314views;0findings
empty-space /designer/sim.html: diagrams or reports did not finish loading
2026-11-11T05:07:36Z tablet-768:314views;0findings
empty-space /designer/sim.html: diagrams or reports did not finish loading
```

The original [phone](https://github.com/Valpatel/gyropup/actions/runs/42961981559/job/130330602124),
[iPhone](https://github.com/Valpatel/gyropup/actions/runs/42961981559/job/130330602176)
and [tablet](https://github.com/Valpatel/gyropup/actions/runs/42961981559/job/130330602150)
failures remain preserved. A proposed separate local diagnostic was prepared but
never executed. Instrument the existing harness so normal CI retains the actual
failing environment rather than treating a fresh different-engine success as its
explanation.

The original predicate,30s deadline and failure string are unchanged. Record the
failure first, then make one bounded read-only snapshot and one exclusive report
write. Retain body readiness, startup/status text, selected design, current scene,
frame/triangle/context state, errors/warnings and failed/pending requests. Scope
network records to the navigation and bound their count with explicit totals.
Keep only owned-origin paths, no query strings, headers or bodies; redact external
endpoints, addresses, private paths and bearer values. Native controls and stage
state are never changed by the observation.

The existing selection/partition unit harness now exercises the actual serializer
and observer with partial/current scenes, error/network redaction, failed state
reads/writes and a stalled bounded snapshot. Diagnostic failure still retains
the original timeout and never retries it. Normal CI must provide the next actual
result: this records an unreproduced failure, not a product fix, readiness waiver,
timeout increase or rendering/physical qualification.

## 2026-11-11 — passing controls missed private path and non-HTTP URL forms

Independent review [5854558025](https://github.com/Valpatel/gyropup/pull/315#pullrequestreview-5854558025), [thread4534565407](https://github.com/Valpatel/gyropup/pull/315#discussion_r4534565407), found a concrete privacy blocker at `d0dfd096`. The existing nine controls passed while three synthetic calls still leaked their input:

```text
safeReadinessText('failed at /tmp/private-session/key.json', origin) -> same private path
safeReadinessText('ws://private-host:1234/stream?token=secret', origin) -> same endpoint/query
safeReadinessURL('about:blank?token=secret', origin) -> same query
```

These are synthetic examples, not real machine paths or credentials. A pure evaluation of the actual old Git blob reproduced all three. The original sanitizer covered HTTP(S) and two home-directory roots, then treated about URLs as safe wholesale. Its test coverage did not justify the broader redaction claim. Preserve that failed review and old evidence rather than narrowing the claimed requirement afterward.

The same serializer now normalizes common percent/escaped forms, keeps only known about document labels without query/fragment, redacts external authority and opaque URL schemes, and removes filesystem paths beyond home directories. It retains sanitized owned-site paths, normal relative source/replay names and numeric scene state. The existing control harness adds the actual three repros, adjacent schemes, malformed/encoded endpoints, POSIX/Windows/file error forms and full written error/console/state serialization. Header/body collection remains absent; the original30s wait,2s read bound and failure behavior are unchanged.

Diagnostic privacy is a separate gate from diagnosing the simulator timeout. These controls exercise known diagnostic formats and preserve the old coverage gap; they are not a generic arbitrary-secret detector or evidence that loading is repaired. The source CI timeout and its original artifacts remain unresolved until actual evidence supports a correction.

## 2026-11-11 — distinguish fixture errors and observation clocks from a timeout cause

The actual d0 [phone artifact](https://github.com/Valpatel/gyropup/actions/runs/42969242638/artifacts/13833176477) retained a repeated30s failure: body ready absent, v2 selected, startup loading, robot absent and frame0 with contextLost=false. The current manifest and robot-actions CSS appeared pending near the snapshot. Those pending timestamps were Node request-handler receipt times, not browser network start times; they do not prove a30s asset stall or CPU/GPU cause. The simulator bootstrap's dynamic import is not awaited by its small entry module, so DOMContentLoaded can precede the module graph/catalogue/setup covered by the original wait.

The same artifact recorded a generation0 about:blank sessionStorage error from the layout caller's unguarded acknowledgement helper and an optional ignored development-poll404. The caller now reuses the existing guarded assembly-session helper with an explicit base. Actual caller/callback controls prove no storage read on opaque/wrong origins, the exact matching-origin write, and preserved denied-current-origin errors. The old helper bytes and old error evidence remain unchanged. This fixes a demonstrated fixture defect, not a proven readiness cause.

The bounded observer now separates Node navigation/DOMContent/core-wait clocks from numeric Playwright request.timing fields, retains relevant completed and pending resources, and records page/context identity, previous routes, document time origin/navigation timing, visibility and focus. It reads no headers/bodies and adds no production module instrumentation. Pure controls retain these clock semantics and privacy. The original30s predicate,2s snapshot bound and failure remain unchanged; actual new CI still determines the next evidence.


## 2026-11-11 — Keep full CI coverage while scheduling one page loop per job

At source `7cd24223`, normal run `43003806788` tablet job `130466178200`
passed all 314 route/theme views with zero findings after the reviewed one-worker
policy. Phone job `130466178170` still failed its original 30-second simulator
readiness predicate, despite completing 314 views with zero layout findings.
Its complete sampled profile spanned 35.776514 seconds; native WebGL2 context
creation took 7.0005 seconds, followed by Three renderer setup. These wall and
sample observations do not identify a GPU/CPU/scheduler mechanism. The earlier
two-arm controller also remained FAILED after its post-comparison load check;
neither arm nor later CI erases that outcome.

Use one worker in each ordinary full single-size GitHub CI partition while
retaining all five matrix jobs, the dynamic full page set, both themes, planted
controls and original deadlines. Preserve explicit overrides and other modes.
This follows [Playwright's CI worker recommendation](https://playwright.dev/docs/ci#workers)
for reproducibility; it is a scheduling policy, not a waiver or a proven causal
fix. The existing selection controls exercise all five sizes and larger future
page sets, including exactly-once Home-to-Sim ordering.

The exact jobs, artifact digests and remaining acceptance are retained in the
[closeout diagnosis](../plans/public-entry-closeout/source-ci-diagnosis.json).
New ordinary CI must still validate the final source; no browser retry or
production instrumentation is implied by these pure controls.
