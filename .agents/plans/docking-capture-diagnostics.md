# Observe the original docking capture boundary

Issue [#292](https://github.com/Valpatel/gyropup/issues/292). This isolated branch
starts at frozen PR289 source `cdcf7a4c12356e9e7e7ef5d89cc5c772432608bc`;
its stacked PR targets `ci/browser-observation-contracts` without editing that
checkout. Product rendering, capture contents, the original15s timeout and failed
results remain unchanged. This is diagnosis, not a root-cause correction.

Two actual pinnedCI campaigns failed at the stopped Robot screenshot after125
passed observations and no page errors: main67d5ea2f run42889052519/job130084998921
and PR289cdcf7a4c run42896715114/job130111635244. Preserve both source/report/log
identities and their failed outcomes. A successful one-context localChrome151
probe established observation wiring only; it did not reproduce CI141/history.

## Implementation and acceptance

- Observe only the existing stopped Robot capture, after the original preceding
  campaign. Time preparation/font-ready, Chromium layout/capture and cleanup
  protocol calls; retain metadata only, forwarding original calls/results.
- Record bounded native document/font/frame/visibility/canvas/context-loss state,
  pending requests and build/browser/source identity without pausing or modifying
  the product, render loop, screenshots, native focus or playback.
- Re-throw the original screenshot error unchanged, never retry or accept a
  diagnostic image as the required artifact. Diagnostics must retain partial
  failure evidence even when collection or report writing fails separately.
- Meaningful pure controls prove unchanged argument/result/error identity,
  zero retries, bounded diagnostics and uncompleted later phases after capture
  failure. Run them in the existing required docking command.
- Independent GPT-6 review and the next normal pinnedCI campaign are required.
  No new local full browser campaign, installs or native work. Resource pressure,
  first section render/scene costs and compositor behavior remain hypotheses
  until actual phase/frame observations identify a boundary.

Implemented: protocol metadata is active only for the original stopped Robot
capture; native page state is read without forcing a render/frame/focus change.
Before/after and evidence writing have separate500ms diagnostic bounds; these do
not replace or enlarge the original15s capture. Missing snapshot data is explicit;
a report-write error cannot replace a failed capture, and cannot turn a passed
PNG into complete required diagnostic evidence. All132 interaction states remain.

The immediately preceding phone context may still own native fullscreen when
its existing close is requested. Passive before-close native state, awaited-close
completion and new-context markers retain that hypothesis without changing the
sequence. Material clipping is already enabled from scene creation; section
updates mutate existing plane values, so no first-section shader-cause claim is
made. The original phase remains unobserved until actual pinnedCI runs.

Both actual reports/ZIPs were verified and preserved with immutable identities;
the byte-identical report is stored once and linked from both failed attempts.
The local151 wiring receipt is qualified separately. Eleven pure guards pass.
Next: build/privacy and independent review of this test-only delta, followed by
the next normal pinnedCI campaign. The historical failures remain failed.
