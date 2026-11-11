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
