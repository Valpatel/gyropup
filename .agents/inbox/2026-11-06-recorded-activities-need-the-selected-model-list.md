# Wait for the selected model recording list before choosing an activity

Related guidance: [loading readiness](../domains/loading-readiness.md). A model
key or loaded geometry alone does not establish that its recorded activities
have loaded.

On 2026-11-06, PR238 CI at `a7125a47` failed in
`tests/site/controls/test-robot-controls.mjs:63` (job128013101155): the 30-second
wait for a targets replay expired after the phone activity selection. Earlier
`2f95ac5a` had the same predicate failure; `4933ab24` passed. Those CI logs did
not record the exact model or pending request, so their precise timing remains
unknown.

Root's bounded, test-owned installed-Chrome diagnostic used the genuine fleet226
site. Its `designer/sim.js` bytes equalled current source and the capture source
SHA256 `5042c0347f73092ce308beaf8fb7b1cb6c5e6b5183c066e05ca7c1de629ed591`.
Holding the actual `/exports/sim/default/summary.json` request produced:

| Boundary | Actual state |
| --- | --- |
| Old model helper resolved | `modelKey=designs/default.json`, options `['']` |
| Targets selected while held | no replay; loading recorded activities |
| Metadata released | target option present, but the earlier selection stayed lost |
| Targets selected after options loaded | actual replay `default/targets` |

The owned command was `node <read-only held-summary diagnostic.mjs>` under a
110-second outer bound. Script SHA256
`243d62286f35423aa06f557750c7d54a74a1f240d00a9be0bfed7cef15387ae5` returned
`PASS_REPRODUCED_READINESS_RACE`, zero page/request errors and closed resources.
The follow-up command executed the actual corrected `model()` helper extracted
from the existing test against the same product. Script SHA256
`196d98aee926911d40130ee03f3fb410629602bf2292eb504eeb1166c675dbcd`
returned `PASS_ACTUAL_NEW_MODEL_HELPER`: the helper stayed pending while the
summary was held, resolved after exact `default/drive` and `default/targets`
options appeared, then the real targets replay started. It also closed its
browser, context and listener.

The cause is a test precondition gap: the app assigns `modelKey` before awaiting
`listRuns()`, and an activity without a matching recording key does nothing.
Require the selected model, non-bench state and both exact model-stem recording
options before choosing activities. Preserve replay assertions and timeouts;
do not replace readiness with a sleep or infer an application defect from this
race. Installed Chrome proves the controlled failure class; mandatory CI uses
Playwright Chromium and must still pass on the final head.

The separate `2f02fa5b` gamepad hop-landing timeout had no recorded jump/model/y
state. Its cause remains unknown. The existing gamepad test now prints those
fields on that failure and rethrows the original error, preserving the exact
landing predicate and 15-second bound. This is diagnostics, not a hop fix.
