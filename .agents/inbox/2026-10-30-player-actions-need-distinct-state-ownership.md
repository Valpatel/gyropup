# A working replay can still present duplicate playback actions

On 2026-10-30 the live workshop reel reached its natural 22-second end in Chrome
at 390×844 and displayed two enabled, visible custom buttons named Replay.
The video had `controls=false`; this was application state, not native controls.
Issue #118 / PR #120 tracks the correction.

## Evidence and cause

The live browser probe loaded `https://gyropup.com/`, clicked the reel's primary
control, waited for real playback and `data-state="ended"`, then inspected all
buttons inside `.highlight-controls`. At `currentTime=22`, both were visible and
enabled: `Replay highlights` and `Replay highlights from the beginning`.

`web/highlight-video.js` changed the primary button to Replay at completion but
kept the permanent secondary Replay enabled whenever media was ready. Earlier
tests proved decoded frames, finite playback, recovery and replay; they did not
check that every state offered distinct actions.

## Corrective rule

Give the persistent primary control ownership of Play, Pause, Replay and Retry.
Offer Restart as a distinct auxiliary action only after unfinished playback has
made progress. An unavailable auxiliary action must be hidden, disabled and
absent from keyboard navigation. When it disappears while focused, transfer focus
to the persistent primary control without scrolling. Ensure author CSS does not
override the `hidden` attribute with a button `display` rule.

Check the rendered control and accessibility contract at idle, queued/loading,
paused, failed and ended states, including a complete second replay. Count visible
buttons and verify their names and operability; successful media playback is not
sufficient UI validation. The shared consumer assertions live in
`tools/highlight-control-contract.mjs` and are exercised by both existing player
and real hero/media integration harnesses. Read native `video.ended` during paint
as well as the application completion flag so event ordering does not briefly
advertise another action at the natural end.

## Limits

These are browser tests and network emulation, not physical-device coverage.
The encoded media and historical simulation evidence are unchanged. Player state
validation does not qualify CAD or hardware.
