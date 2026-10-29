# Visible models need fresh-viewport and fixed-overlay checks

2026-10-29: `SITE_URL=http://127.0.0.1:8890 node tools/test-portal-viewers.mjs` reached all five talk layouts after replacing the stand-in with the current robot. Visual inspection of `/tmp/gyropup-portal-viewers/talk-phone.png` still showed the speech bubble covering the turret. The harness filtered obstacles by `offsetParent !== null`; fixed-position chat and speech UI also have a null offsetParent, so they were silently absent from the overlap assertions.

A second independent fresh navigation at 844×390 showed a 52×90 px robot because its desktop panel stayed open alongside the short-landscape speech column. Resizing from 320 px had hidden that startup state by retaining the phone's collapsed panel.

Cause: layout checks measured geometry without all visible overlays, and a sequence of resizes was incorrectly treated as evidence for fresh responsive startup.

Rule: use rendered client rectangles plus visibility/opacity for fixed overlays, assert visible speech as well as model bounds, and supplement resize matrices with fresh contexts at breakpoint edges. Wait for the actual model-ready state before navigating away; a global controller can exist while required meshes are still downloading.

The talk demo now anchors speech to an invisible full-model envelope (a UI placement helper, not a CAD component), leaves speech space above portrait models and beside short-landscape models, and treats short screens up to 1024 px wide as compact event/chat drawers. The shared camera fitter expands its search bound when a tight overlay band needs more than six bounding radii. The portal regression includes actual visible bubbles, fixed chat UI and a fresh 844×390 context with minimum useful model dimensions and event/chat exclusivity.

Limits: a 568×320 screen with the conversation expanded still has little vertical model space; closing Talk expands the visible scene. This is screen-layout evidence, not physical CAD clearance or a claim that every possible viewport size has been enumerated.
