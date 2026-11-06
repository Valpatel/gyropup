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
actual `sim.js` request for 17 seconds with bounded release and finally cleanup:

```sh
SITE_URL=<test-owned-exact-build-url> node tools/test-audio-settings.mjs --startup-control
```

This artificial delay is a focused sequencing regression, rather than an extra
17 seconds charged to the core budget on every routine CI worker. The same
30-second core bound still applies in the stress run. Keep the actual old-product
mute rejection as a paired negative control; a successful stressed startup alone
would not establish the mute fix. No product source or media receipt changes for
this test correction. The unknown CI request is not relabelled as the deliberately
held source, and no retry-only success is accepted as its resolution.
