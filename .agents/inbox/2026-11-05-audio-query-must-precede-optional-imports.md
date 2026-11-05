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
