# Symptom index

| Symptom | Canonical guidance |
| --- | --- |
| CAD branches merge but the model, print kit, BOM or validation reports describe different revisions | [Mechanical release coherence](domains/mechanical-release.md) |
| Entry warning loses focus, hides controls, or changes saved audio/scene state | [Prototype notice](domains/prototype-notice.md) |
| Motto or landing graphics feel cheesy despite passing layout checks | [Gyropup visual character](domains/brand-presentation.md) |
| A motor, wheel, feed dial or flap orbits outside its assembly while animating; static bounds still pass | [Rendered mechanism frames](domains/rendered-mechanisms.md) |
| Upper links move while output adapters or their screws remain fixed to the robot body | [Output-adapter ownership](inbox/2026-10-29-output-adapters-belong-to-upper-links.md) |
| Static build succeeds but a new simulator module returns 404 or the page never initializes | [Static build module references](domains/static-build.md) |
| Buttons appear correct but keyboard, pause, overlays or reload behave differently | [Playground interactions](domains/playground-interactions.md) |
| A fresh simulator clips the robot above the screen, but resizing or switching models repairs it | [Late overlay layout and camera insets](domains/playground-interactions.md) |
| Loading poster and interactive hero jump in pose, scale or background | [Landing preview handoff](domains/landing-preview.md) |
| Hero handoff assertion changes by a fraction of a pixel after font loading or a screenshot | [Separate font/capture setup from the handoff](inbox/2026-10-29-measure-handoff-after-font-and-capture-setup.md) |
| Current pages show different robot versions, or archived balls miss a newly swapped barrel | [Current models and physics archives](domains/rendered-mechanisms.md#current-models-and-physics-archives) |
| Model bounds pass but speech hides the robot, or a fresh wide phone looks worse than resized tests | [Visible mechanism layout checks](domains/rendered-mechanisms.md) |
| A failed download looks unpublished, a partial model looks ready, or a retry overwrites newer data | [Loading readiness and report availability](domains/loading-readiness.md) |
| A model reports ready but disappears or contains non-finite transforms after valid JSON loads | [Loading readiness and report availability](domains/loading-readiness.md) |
| A viewer's error/retry controls clip off a phone despite hidden page overflow | [Grid tracks and header minimums](inbox/2026-10-29-shrink-grid-tracks-before-truncating-headers.md) |
| Build thumbnails are missing, show unrelated parts, or disappear after publishing | [Part image identity and provenance](domains/part-images.md) |
| Sheet thickness or dimensional bounds change after STL export without a CAD edit | [Tessellation bounds versus stock dimensions](inbox/2026-10-29-tessellated-bounds-are-not-stock-dimensions.md) |
| Part status moves to another row after sorting, retries duplicate controls, or a model preview loses its original download | [Parts retain their identity when their table changes](domains/build-portal.md) |
| A newly integrated CAD viewer opens but disposal throws or its animation keeps running after removal | [Parts retain their identity when their table changes](domains/build-portal.md) |
| Phone status checkboxes remain reachable but their part names disappear, despite sticky cell styling | [Sticky identity and the scroll wrapper](inbox/2026-10-29-sticky-part-identity-needs-the-scroll-wrapper.md) |
| Wheel tests fail after a fixed sleep under software rendering | [Wait for rendered camera targets](inbox/2026-10-29-camera-tests-must-wait-for-rendered-targets.md) |
| Print hashes pass but package mixes revisions, slicer settings or stale totals | [Preflight is not a generation transaction](inbox/2026-10-29-print-preflight-is-not-a-generation-transaction.md) |
