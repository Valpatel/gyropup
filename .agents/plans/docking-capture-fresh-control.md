# Next control: fresh pinned browser, original stopped Robot capture

Source/action proposal for issue292. Prepare locally for independent review;
**do not push, launch, install or trigger CI before review**. Remote PR294 remains
at observed source57341468. The diagnostic failure and full logs/artifact
identities are preserved under `docking-capture-diagnostics/observed-573/`.

## Evidence driving the control

Normal pinned141 CI on573 failed at the original15s screenshot after125 passed
observations. Preparation12.574ms/fonts1.313ms/layout0.393ms returned; browser
Page.captureScreenshot had no reply during the remaining~14985ms. Both snapshots
were available, same visible/focused complete document, fonts loaded, no requests
or context loss/error, renderer frames37→48 and programs5. Endpoint frames are
not per-frame timing or a GPU/compositor diagnosis. The prior phone context
owned native fullscreen at close; context close completed, then a fresh playback
context was created. This witnesses lifecycle history, not its causality.

The earlier fresh-browser local151 control passed but differs from the affected
pinned141. The smallest useful new contrast is the **same capture on141 before
any other browser context/scene**. Keep the original full-history573 result
failed, and preserve the ordinary full campaign for comparison.

## Local source diff

- Existing docking harness accepts explicit `DOCKING_CASE=fresh-capture`; default
  `all` remains the complete132-state campaign. Unknown scopes fail.
- Fresh scope rejects wrong engine/channel before launch and rejects any browser
  version other than141.0.7390.37. Existing Playwright1.56.1 guard remains. There
  is no fallback/download/install or nativeChrome151 substitution.
- One new browser starts with0 contexts; reuse the existing stopped Robot
  playbackActivationCases path, dark1366×900/reduced motion, same panel/hip/plane/
  Flip/depth/Rotate/Loop trusted controls and the **same capture call/options**.
  Close after that capture; no synthetic interactions or forced renderer state.
- Distinct output suffix and scope-marked `completeCampaign:false` report prevent
  interpreting this3-observation control as full campaign coverage. Original
  failure/error/15s timeout and diagnostic image behavior remain unchanged.
- Add one separate case to the existing pinned-container CI matrix. The full
  docking case and both Chromium/WebKit commands remain present unchanged;
  failures in either job do not skip or replace the other required campaign.
  Existing20-minute job cap remains, and every native wait/capture retains its
  current bound; this is one finite scene/sequence/capture, not a retry loop.

## Review first, then one action

1. Review this local-only delta against573, including the scope/runtime guards,
   identical stopped controls/capture, workflow job separation and pure controls.
   Product/site-tool/rendering sources, dependencies and normal budgets stay put.
2. If accepted, publish once for the **next normal pinned CI** using the existing
   image digest `f1e7e01021efd65dd1a2c56064be399f3e4de00fd021ac561325f2bfbb2b837a`.
   Do not create a new framework/manual workflow, install141 locally or rerun old
   jobs. Existing web-scene has no dispatch trigger; adding one only on a topic
   branch would not be immediately dispatchable from the default workflow.
3. New case command (inside that already provisioned environment):
   `DOCKING_CASE=fresh-capture PLAYWRIGHT_CHANNEL=chromium npm run test:instruction-docking`.
   Keep exact source/merge/browser identities, all native/capture metadata, original
   error/logs and required PNG outcome; CRC/hash the uploaded artifact.
4. Interpret only a valid141 control. A fresh failure in the same capture phase
   shows full prior history is not necessary for that attempt; it does not prove
   a universal browser/product/GPU cause. A fresh pass against573 full-history
   failure leaves history/resources/browser-process conditions as candidates;
   distinct CI runners and observation overhead prevent causal attribution.
   Setup/runtime/metadata failures are not capture results and remain failed or
   explicitly limited. No outcome authorizes a mitigation automatically.

If more isolation is needed, propose a later bounded same-host history prefix
control (for example phone fullscreen/context closure) after reviewing actual
fresh141 evidence. Do not add that second experiment now. No new local browser
campaign or full CI has run for this preparation.

Source-only validation:13 pure guards pass (the original11 failure-retention
controls plus scope/runtime controls), syntax/diff checks pass. Parsed workflow
comparison proves removing the one new case restores every existing job, command,
image, budget and gate exactly. No browser or CI control has been executed.
