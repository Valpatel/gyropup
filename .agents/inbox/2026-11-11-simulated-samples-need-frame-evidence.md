# A motion sample timeout needs both stage progress and fixture state

On 2026-11-11 UTC, the Gyropup promotion mechanism job stopped in
`tests/site/models/test-turret-motion.mjs:193` with
`page.waitForFunction: Timeout 15000ms exceeded`. The earlier source/pose checks,
actual upper-stop pose, and reference-control setup had run. The timeout required
15 stage samples after the simulated speed crossed its existing threshold.
The [failed job](https://github.com/Valpatel/gyropup/actions/runs/42930151610/job/130226539624)
and [one-member artifact](https://github.com/Valpatel/gyropup/actions/runs/42930151610/artifacts/13816356512)
retain the original evidence. The archive contains only the server log and its
SHA256 is `722af461aee65eeaea80b93b06b7952dd140c89489d6800ccfd5ff99ece76f6a`.

The earlier [passing integration job](https://github.com/Valpatel/gyropup/actions/runs/42926680839/job/130214809742)
used the same pinned browser image, Node version, and Git tree
`80c3ae86ed007610ca22226a16bbade879277129`. The GitHub test merge commits
`4697a513` and `d1acecef` differ, while their file trees match. The
[passing artifact](https://github.com/Valpatel/gyropup/actions/runs/42926680839/artifacts/13814802963)
retains all 15 samples and the later full geometry checks. Its SHA256 is
`93523bbbd54c0c126529e27feec35745303d886cec754175a3b7a84da7be13a7`.

The stage caps its per-frame simulation increment. A 15-second wall-clock wait
alone cannot distinguish slow frames, a stopped stage, a cleared request, a
paused bench, or a callback failure. The failed artifact has no browser data to
choose among them. Keep the original failure and 15-second/15-sample contract.
Instrument the existing callback with bounded frame counters and elapsed stage
time. Capture the start/end render counters, speed fraction, request and pause
state, document focus/visibility, and error state on timeout. Retain the same
exception even if reading or writing that diagnostic fails. The Node controls
execute the actual wait predicate and cover zero, fourteen, and fifteen
samples, plus both diagnostic read and write failures.

The trace concerns the browser simulation. A subsequent passing run does not
identify why the original wait timed out or qualify physical behavior.
