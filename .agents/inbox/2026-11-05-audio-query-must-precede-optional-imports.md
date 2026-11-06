# Apply the audio query before mounting consumers or awaiting optional modules

On 2026-11-05, PR #222 presentation CI failed the early master-mute assertion.
The failure was reproduced on both the pre-move and moved website artifacts by
holding the actual `sim_gamepad.js` import. The first talk instance inherited saved
SFX-enabled state; `?sound=0` was applied only after the optional import finished.

Dated browser evidence with saved sound enabled, volume 0.3 and voice unmuted:

```text
before root move: while import held, enabled=true, voiceVolume=0.165
 after root move: while import held, enabled=true, voiceVolume=0.165
both after import release: enabled=false, voiceVolume=0
```

Cause: URL preference application followed a top-level await after `mountTalk`.
Move query application immediately after `createSfx`; keep ordinary onChange/UI
wiring. The existing audio suite now holds that import with a bounded request
barrier, observes the actual talk mount and checks disabled master, zero voice
gain and SOUND OFF before release. It releases in finally and checks the stable
state afterwards. Existing positive sound/volume and independent voice-mute cases
remain; no sleep or weakened readiness assertion replaces the early-state check.

Limits: this is browser simulation audio initialization. It changes no hardware
command or robot physics. `sim.js` participates in the highlight source receipt,
so adoption requires a genuine capture/encode refresh, not hash relabeling.

## Start an optional-request deadline after its actual core precondition

Later on the same date, exact-head presentation CI at `24e214d` failed with
`The gamepad import was not held`, not with the original mute assertion
(run 42132727471, job 127613093114). The request/timing responsible in that CI
worker was not identified. The test's 15-second import deadline started at
navigation commit, before app/catalog/model loading and talk could reach the
optional import. Its separate 30-second actual-talk wait came afterward.

Controlled actual-helper evidence against the fleet 168 product:

```text
actual sim.js startup request held beyond 15 seconds:
  original ordering: missing-gamepad error at 15091 ms, no page errors
  corrected ordering: all unchanged assertions pass at 19969 ms
same corrected helper against the pre-fix fleet 155 product:
  original first-mounted mute assertion rejects at 2470 ms
```

Corrective rule: await the existing bounded actual-talk precondition first,
then start the unchanged 15-second optional-request bound. Neither phase's
value increases, and first-mounted sound/voice/UI checks still run before
releasing the real gamepad request. Core failure remains a readiness failure;
this does not replace a missing or slow model with a successful result.

The ordinary audio suite always runs that first-mount control. Its focused
`--startup-control` option additionally calls the **same helper**, holding the
actual `sim.js` request for a verified 17–18 seconds with bounded release and finally cleanup:

```sh
SITE_URL=<test-owned-exact-build-url> node tools/test-audio-settings.mjs --startup-control
```

This artificial delay is a focused sequencing regression, rather than an extra
17 seconds charged to the core budget on every routine CI worker. The same
30-second genuine-core budget still applies in the stress run. Keep the actual old-product
mute rejection as a paired negative control; a successful stressed startup alone
would not establish the mute fix. No product source or media receipt changes for
this test correction. The unknown CI request is not relabelled as the deliberately
held source, and no retry-only success is accepted as its resolution.

Fleet 176 at `013d727` passed the ordinary first-mount control but timed out in
the additional stressed talk-readiness phase. That is a failed run, not passing
validation. The injected delay consumes part of the unchanged 30-second phase,
but this run did not record request/release times, so its particular cause is
not established. The helper now records monotonic navigation, source gate,
core/talk and optional-import milestones; a failure also reports pending request
paths, readiness booleans and page errors. An instrumented unchanged-bound rerun
can diagnose that distinction without silently increasing a timeout.


Fleet 178 retained that failed result while recording the actual phases:

```text
navigation committed / talk wait started: 65 ms
startup requested: 270 ms; released: 17270 ms; continued: 17273 ms
30-second boundary: document complete; sim=true; robot=false; talk=false
pending request: /_cadagent/changes; page errors: none
```

The verified 17-second injection left about 13 seconds of genuine core work in
that phase. It does not establish the identity of the original CI delay, nor
whether an uninterrupted real startup would meet its full 30-second budget.

The focused stress mode now has a 48-second hard outer cap, **plus mandatory**
checks that the actual request-to-release hold is 17–18 seconds and talk-readiness
elapsed minus only its measured overlapping hold is at most 30 seconds. It targets
17.5 seconds inside that window to avoid a timer-resolution boundary. Request
continuation and subsequent network work are not excluded. A missing/unreleased
or excessive gate cannot qualify, and the outer cap alone is never acceptance.
The mandatory ordinary core bound remains 30 seconds, and the real held optional
import bound remains 15 seconds. Both failed runs remain failed; this adjustment
accounts for verified injected time rather than granting genuine startup more time.

Fleet 179 at `11d1941` passed the ordinary suite and stress with an actual timing
receipt: talk phase 42780.941 ms, held interval 17499.619 ms, excluded overlap
17499.619 ms, genuine core 25281.322 ms. The real optional request was held, and
all early/post mute assertions passed. Privacy passed 10 tests with one expected
skip; overall exit 0. The final actual-helper old-order mutation still rejected
at 15118 ms, and its unchanged first-mute assertions rejected the old fleet 155
product at 2410 ms. This establishes the focused procedure's positive and negative
controls; it does not identify the original CI request or qualify hardware.
