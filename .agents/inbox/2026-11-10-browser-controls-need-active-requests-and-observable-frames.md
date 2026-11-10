# Match browser controls to the active request and observable frame

On 2026-11-10, Gyropup #287 at `d8180b5c` failed three browser
harnesses after the current Robot became the default. The original jobs remain
failed.

- [Loading job 130171476898](https://github.com/Valpatel/gyropup/actions/runs/42913926552/job/130171476898)
  showed Talk ready with zero escaped errors while the fixture waited for an
  archived rig manifest fault. The active Talk loader fetches the adopted
  collection. Give the old-field mutations a page-local explicit null authority
  and assert the archive request count. Separately corrupt a required mesh named
  in the adopted manifest, assert interception, and verify the default Talk
  retry recovers the adopted identity and original canvas. Chrome 151 exercised
  eight archived manifest faults, the current mesh failure and recovery, and
  the explicit archived fallback.
- [Presentation-content job 130171477088](https://github.com/Valpatel/gyropup/actions/runs/42913926552/job/130171477088)
  passed the normal/still checks preceding a wrong-still pixel failure. A
  bounded Chrome 151 probe retained actual image sources, capture times and PNGs.
  The original opacity mutation changed locally. A separate 4-second stepped
  swatch yielded five equal home images with 4.137–4.409-second captures, while
  the same decoded swatch on the README yielded both colors. This demonstrates
  phase aliasing. The original CI cause remains undetermined. Give a negative
  control continuously changing visible child pixels and capture enough distinct
  sample times to reject it through the real image. Keep the genuine still and
  normal animation pixel checks. The focused badge test passed on both pages
  in Chrome 151. Disabling the injected animation yielded three identical
  captures and the expected assertion failure.
- [Playground job 130171477286](https://github.com/Valpatel/gyropup/actions/runs/42913926552/job/130171477286)
  timed out on the downward tilt sweep after reaching the upper stop. The
  Chrome 151 original path reached −25° from +12° in 25 stage callbacks and
  1.25 seconds of clamped stage time, taking 7.987 wall seconds to the first
  lower-stop observation. The CI job retained no angle or frame trace at this
  boundary. Test the lower endpoint from a verified margin with normal controls
  and real held pad input within the existing 15 seconds. Log input, angle and
  stage progress if it fails. The focused check reached −25° from −21°. A
  neutral-pad mutation left the angle at −21° through 43 observed stage frames
  and failed at 15 seconds. The full-sweep timing remains a local diagnostic.

See the related [mesh request identity](2026-11-10-mesh-request-controls-need-manifest-file-identities.md)
and [stage-clock](2026-11-10-hop-completion-needs-the-actual-stage-clock.md) lessons.
