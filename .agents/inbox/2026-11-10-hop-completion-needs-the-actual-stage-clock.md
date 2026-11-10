# Bound simulation completion with the actual stage clock

On 2026-11-10 PR279 head02d7fb71, CI run42877244400 gamepad job130043726706
failed the generic15s `until` timeout while waiting for hop completion. Its
recorded jump.t1.35, landedAt0.33 and y0 are consistent with recovery before
completion near1.40 simulated seconds. That snapshot has no frame count, paused
or callback-error trace; the exact original CI cause remains unknown. Preserve
[the actual CI identities and investigation](../plans/assembly-staging/ci-frame-budget/investigation.json).
No documented product hop responsiveness requirement used that generic15s value.

An actual gamepad/stage callback control on nativeChrome151 observed normal
completion in29 frames/1.434 stage-dt seconds but5.292 wall seconds. An explicit
1000ms rAF gate reproduced the original15s failure class with y0 and an unfinished
recovery, actual demo off/playing, visible scene and no callback/page errors;
releasing the gate completed normally. The shared stage clamps dt to0.05, so
software-render wall time is not the hop clock. No curve was copied or product
state reset. [Raw stage traces](../plans/assembly-staging/ci-frame-budget/hop-frame-starvation.json)
remain qualified as a controlled failure class, not a reconstruction of CI.

The corrected test contract explicitly changes landing completion: preserve the
actual gamepad input/start and rendered>0.12m airborne checks at their original15s
bounds; then require final jump=null/y0 within3 seconds summed from actual existing
stage callback dt,30s hard wall from first observed hop frame, and10s without a
frame. Reject paused/replay/hidden/error states and over-budget completions. The
selected kinematic illustration normally completes near1.4–1.6 simulated seconds;
3s is a bounded failure guard, not a new physical/continuous-motion claim.

The test-only pure guard contains no hop trajectory. Its ordinary controls reject
continuing frames whose jump never ends, frozen-frame samples, hard-wall excess,
false ground-only completion, hidden/paused/error/invalid state and Promise-valued
guards. Browser controls must demonstrate the deliberately gated hop fails the
old wall contract but genuinely completes the new contract, and actualstage.stop
is rejected. Actual receipts state whether those controls completed; a prepared
observer or passing pure tests alone is not qualification.

The initial implementation repeated the known async-predicate failure class:
Playwright accepted a returned Promise before its false resolution. Actual frozen
geometry and the next unchanged gamepad assertion caught this false acceptance.
[Rejected attempts](../plans/assembly-staging/ci-frame-budget/rejected-observers/README.md)
remain INVALID, including their apparent newPass. The synchronous polling adapter
is now passed directly to Playwright and unit-tested to return a boolean; no RPC
or async predicate can certify completion. This follows the existing
[async-polling lesson](2026-11-05-layout-readiness-must-wait-for-fonts-not-global-load.md).

## Exercise gamepad controls with the existing touch renderer

On 2026-11-10, [PR #287 run 42919310218](https://github.com/Valpatel/gyropup/actions/runs/42919310218/job/130190545896)
hit the 30-second hop wall guard after the adopted Robot passed the tilt checks.
[The original artifact](https://github.com/Valpatel/gyropup/actions/runs/42919310218/artifacts/13810854546)
records 27 callbacks at 0.05 simulated seconds each and a 1,122.8 ms median
wall gap. The robot rose 0.182 m and touched down. At the last callback it was
still recovering at `jump.t=1.30`, with a visible manual scene and no callback error.

One bounded Chrome 151 comparison on the same build ran the real pad hop at
1440 × 1000 CSS pixels and DPR 1. Both contexts rendered the adopted model and
completed in 30 frames. The existing coarse-pointer profile selected by touch
support completed in 7.307 seconds versus 9.290 seconds in the fine-pointer
profile. The roughly 21 percent difference is a local association with the
rendering profile. Pinned Chromium CI still owns acceptance.

The functional pad test now selects that existing profile, asserts the exact
adopted presentation and drawn canvas, and retains the 15-second input and
airborne checks and the 30-second wall, 3-second stage and 10-second stall caps.
The separate desktop presentation and motion suites retain fine-pointer coverage.
The live-demo checks bind the same native and collection identities and use
the adopted holder's existing 21.3 m/s simulation value after each return from
a recording.
