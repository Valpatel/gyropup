# A scheduled greeting must preserve an active conversation

On 2026-11-10 PR279 CI run42872278158, presentation-controls job130026340603
failed at test-audio-settings.mjs190: the current speech adapter utterance was
null after the second volume input. That baseline audio source is unchanged by
the assembly recipe. The original test retained no active design/timer trace;
its exact original scheduling cannot be reconstructed. Preserve the failed
[run/artifact identities](../plans/assembly-staging/ci-279-a9/ci-failures.json).

A deterministic nativeChrome151 reproduction on the actual talk demo exposes a
concrete product race. Install/pause the browser clock before navigation, mount
the real page with the existing explicit browser-speech adapter, start a
conversation, then advance exactly400ms across its scheduled greeting:

```text
2026-11-10: controlled talk-demo clock; original say greeting at400ms
before: active="A volume controlled answer", cancelled=1, busy=true
after:  active=null, cancelled=3, busy=false
2026-11-10: same controlled clock; existing guarded announce greeting
before: active="A volume controlled answer", cancelled=1, busy=true
after:  active="A volume controlled answer", cancelled=1, busy=true
```

[Before/after receipts](../plans/assembly-staging/ci-279-a9/README.md) preserve
that result. Cause: the unconditional greeting calls `say`, whose voice path
stops current speech before awaiting its clip. Corrective rule: background
scheduled speech uses the existing guarded `announce` path; an active answer
owns the bubble/voice. The ordinary audio browser test now crosses the400ms
deadline while an answer is active, asserts its utterance and busy state survive,
then verifies the same current-volume and last-word restart behavior. Controlling
the clock makes the race mandatory rather than hoping the test runs before it.

Limits: this is browser adapter/control evidence, not real voice hardware or
proof of the missing original CI timer trace. Local nativeChrome151 is distinct
from CI's pinned bundled Chromium; normal final-head CI remains required. No
sleep increase, retry, skipped assertion, shared component fork or CAD change
is part of the correction.

The first local WebKit control found a separate fixture setup defect before
loading the talk page: `clock.install({time:T}); clock.pauseAt(T)` rejected
`Cannot fast-forward to the past` because the installed clock was already
running. Preserve [that attempt](../plans/assembly-staging/ci-279-a9/local-first-pass.json).
Pause at a future boundary before navigation instead; the real talk-page greeting
is then scheduled on load and still advanced by exactly400ms. This does not add
a real-time sleep or extend the product deadline. Only the affected WebKit audio
scope needs a successor; passing playback/Chrome scopes are not repeated.
