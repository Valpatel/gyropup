# A correct label does not prove that its control performs the promised action

On 2026-10-29 UTC, the Gyropup PR44 interaction audit found that PAUSE only disabled journey auto-advance, native checkbox/slider keys were intercepted by global shortcuts, and focused ARM/FIRE had no keyboard hold handlers. Independent review also found a selected part card covered the phone action bar.

Evidence from the browser audit before correction: paused exit ball distance changed from 0.000436 to 0.001036 m, elapsed time from 0.0727 to 0.1727 s during a 700 ms wall-clock wait. Focused ARM plus Space returned `arm=[]`; focused FIRE plus Enter returned `{trigger:false,queue:0}`. At 390×844 the selected card spanned y504.94–708 while the action bar spanned658–782 (PR44 review discussion_r4407948823).

Cause: tests checked state flags and empty layouts, missing the behavior and occupied layout named by the controls. Correction: freeze motion time while paused; preserve native key ownership and keyup cleanup; implement hold-button key and blur handling; size card offsets from the action bar and separate landscape placement. The existing `tools/test-turret-interactions.mjs` now asserts these actual behaviors and selected-card hit targets.

Rule: use the behavior inventory and regressions in [Playground interactions](../domains/playground-interactions.md). Preserve real browser evidence; these checks do not certify hardware behavior, every device, or subjective play quality.
