# Visible models need fresh-viewport and fixed-overlay checks

2026-10-29: `SITE_URL=http://127.0.0.1:8890 node tools/test-portal-viewers.mjs` reached all five talk layouts after replacing the stand-in with the current robot. Visual inspection of `/tmp/gyropup-portal-viewers/talk-phone.png` still showed the speech bubble covering the turret. The harness filtered obstacles by `offsetParent !== null`; fixed-position chat and speech UI also have a null offsetParent, so they were silently absent from the overlap assertions.

A second independent fresh navigation at 844×390 showed a 52×90 px robot because its desktop panel stayed open alongside the short-landscape speech column. Resizing from 320 px had hidden that startup state by retaining the phone's collapsed panel.

Cause: layout checks measured geometry without all visible overlays, and a sequence of resizes was incorrectly treated as evidence for fresh responsive startup.

Rule: use rendered client rectangles plus visibility/opacity for fixed overlays, assert visible speech as well as model bounds, and supplement resize matrices with fresh contexts at breakpoint edges. Wait for the actual model-ready state before navigating away; a global controller can exist while required meshes are still downloading.

The talk demo now anchors speech to an invisible full-model envelope (a UI placement helper, not a CAD component), leaves speech space above portrait models and beside short-landscape models, and treats short screens up to 1024 px wide as compact event/chat drawers. The shared camera fitter expands its search bound when a tight overlay band needs more than six bounding radii. The portal regression includes actual visible bubbles, fixed chat UI and a fresh 844×390 context with minimum useful model dimensions and event/chat exclusivity.

Limits: a 568×320 screen with the conversation expanded still has little vertical model space; closing Talk expands the visible scene. This is screen-layout evidence, not physical CAD clearance or a claim that every possible viewport size has been enumerated.

## Resize observations need the committed camera and draw

On 2026-11-11, [PR #305 at 0a5965](https://github.com/Valpatel/gyropup/actions/runs/42931576490/job/130231359534)
failed the 568 × 320 Talk overlap assertion. The reported model extended from
`y=102.223` to `228.959` through the dock top at `155`. The failure occurred
before the screenshot call, so artifact 13816463757 contains no failed Talk PNG.

[The passing #304 run](https://github.com/Valpatel/gyropup/actions/runs/42930151610/job/130226539705)
uses the same Talk, stage and test source. In its retained report, rescaling the
preceding 390 × 844 portrait projection into the 568 × 320 CSS rectangle
matches the failing left/right/bottom within 0.008 px and top within 0.374 px.
The failure also keeps the exact prior portrait bubble transform. Its CSS width
already follows the new breakpoint. The passing landscape PNG has a side-left
bubble and the robot at `x=408.212..443.981`, `y=72.942..135.646`.

This comparison identifies a mixed viewport observation. It does not show which
callback had yet to run or establish a persistent fit defect. Record the native
resize, retain the existing 800 ms settlement from that event, and then require
a later stage draw with the matching CSS canvas, drawing buffer and camera
projection. Talk's placement cache can reuse geometry for up to 300 ms, so the
first immediate frame alone cannot certify settlement. Same-size checks also
wait for a later draw. Keep the independent model-size, bounds and overlay
assertions. Retain the observed state and attempt a screenshot if the check fails.
