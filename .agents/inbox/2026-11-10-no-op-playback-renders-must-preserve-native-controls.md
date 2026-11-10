# A no-op playback refresh must leave native controls alone

2026-11-10, PR #286, independent review of built tree `559c897c` / runtime `6eeea9e0`.

## The footer correction was not the complete cause

Fixed primary-action footers stabilized Reset, Isolate and Print, but did not
make every in-content action safe. Moving one button at a time would hide the
common producer path and separate contextual actions from their controls.
The earlier native-focus diagnosis identified the symptom, not the complete
cause: the playback adapter re-rendered native controls from a host-capture
`pointerdown` pause handler, before the actual button activation.

## Actual browser evidence

```text
2026-11-10: native WebKit Robot overview /1366×900 /dark /reduced motion
Parts+Tools+expanded instructions → L.hip_frame → close details → section plane z → Flip
pointerdown: trusted BUTTON target, Flip.y665, content.scrollTop218, pointer.y687
focusin:    Flip.y708, content.scrollTop175
pointerup:  trusted SELECT target (section axis), pointer.y687
click:      trusted DIV target
section before and after: {axis:z, flipped:false, depth:1}
```

The original unmodified failure trace and image are retained in
`plans/instruction-docking/independent-559-flip/`. It failed before depth entry,
so changing the range was not responsible. A diagnostic that forced layout while
observing native setters masked the failure; that instrumented pass is not used
as acceptance evidence.

## Cause and corrective rule

`mountPlayback.pause` refreshes its UI before orbit/pick and view actions. The
old renderer rewrote Loop/Speed properties, labels, status and the Play icon even
when their values were unchanged. Those redundant writes disturbed the scrolling
native-control container during the pointer sequence.

Keep that renderer idempotent: compare current native properties, attributes and
text before assigning them. Keep Loop/Rotate/Flip beside their existing context;
do not intercept focus, synthesize clicks, or move test targets to mask the bug.
Genuine playing→paused transitions still update the displayed state and stop the
shared player before the view action. Section axis/side/depth and playback
preferences must survive that pause.

The real-page regression now covers the exact stopped Robot flow, already-paused
controls, actively playing Flip/Rotate that really pause time, live Loop that
keeps playing, and trusted touch actions after hip selection/close. It records
native pointer targets/rectangles and shared-player/section state at each phase.

## Limits

These checks establish software interaction and presentation behavior. They do
not identify every native browser implementation detail or qualify hardware.
