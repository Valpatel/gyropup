# First-load failure fixtures must precede cache population

On 2026-11-11 UTC, PR #312's normal playground CI timed out waiting for
selection to return to the current robot after a deliberately failed first
bench load. The [original failed run](https://github.com/Valpatel/gyropup/actions/runs/42954063469)
and [playground artifact](https://github.com/Valpatel/gyropup/actions/runs/42954063469/artifacts/13825304993)
remain the failure evidence; the artifact contains the transition screenshots
through `chromium-phone-sliders.png`, but no browser state at the failed wait.

Dated command/output evidence from that run:

```text
2026-11-11T03:47:09Z > node tests/site/controls/test-sim-transitions.mjs
2026-11-11T03:48:18Z page.waitForFunction: Timeout 30000ms exceeded.
2026-11-11T03:48:18Z at tests/site/controls/test-sim-transitions.mjs:148:14
2026-11-11T03:48:18Z Process completed with exit code 1.
```

Source inspection at `dbf324c1257dfab300b54eec68156c860a3d66a4` identifies the
fixture ordering error. Replacing the retired v1 round trip with supported
`turret-box` at test lines 110–113 initialized the bench before the manifest
failure route at lines 139–146. `enterBench` in
`software/site/designer/sim.js` only calls `createTurretBench` when `!bench`;
a later cached selection therefore skips the intercepted manifest fetch.
The expected failure cannot occur, so the selection cannot revert as asserted.
This is a source diagnosis, not a captured request count from the failed job.

Install first-load failures before the first successful visit to that model.
The existing transition harness now asserts the bench is uninitialized before
installing its route, retains both HTTP 503 attempts (including a held late
failure), and requires a third real fetch to recover. Only then does it test
returning to the cached robot and later reusing the identical recovered bench
without a fourth manifest request. Conversation, scene, target reset, speech,
loop blending and phone slider assertions remain in that same real harness.
The 30-second waits and other existing deadlines are unchanged.

The source fix does not establish browser acceptance, media freshness, CAD
correctness or release readiness. Exact-head focused transition checks and
normal CI remain required; historical receipts must remain historical.
