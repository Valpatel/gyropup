# A retry card must be visible above the actual overlay stack

On 2026-10-29 UTC, the simulator's new retry card had z-index12 but phone screenshot review showed a speech bubble covering the error. Its ancestor HUD had z-index4; the body-level speech bubble had z-index7. Raising the child did not escape the ancestor stacking context.

The correction places loading feedback in a body-level host anchored to the stage and bounds it above the action bar. It does not alter camera insets, replace the scene or reset conversation state. The focused browser regression samples actual topmost elements over message text and controls, not only card bounds.

Receipt inspected from the focused Chromium and WebKit artifacts on2026-10-29:

```sh
cat /tmp/gyropup-loading-sim/chromium-report.json
cat /tmp/gyropup-loading-sim/webkit-report.json
```

Both reports record `moduleAttempts:2`, `designAttempts:2`, `summaryAttempts:2`, `recordingAttempts:2`, `meshAttempts:2`, and `errors:[]`. At320×568 and844×390, each reports `height:44`, `reachable:true`, `aboveControls:true` and `readable:true` for Retry. The reports point to the local8892 preview; they do not establish a production deployment.

Rule: loading feedback is an interactive layer. Test readable text and native buttons against the whole overlay stack at fresh phone sizes. Also verify that retry sends a new request after malformed metadata; visual buttons alone do not prove recovery. The durable contract is in [loading readiness](../domains/loading-readiness.md).

Limits: these are selected layouts and two automated browser engines, not every device. This change does not address arbitrary third-party browser overlays.
