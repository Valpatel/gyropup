# Symptom index

| Symptom | Canonical guidance |
| --- | --- |
| Supplier stock exists but exact rating, wire seal, retail pack or part identity does not match the assembly | [Supplier evidence and exact part identity](domains/supplier-evidence.md) |
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
| A study shows a zero-second player, or a valid encoded movie is frozen or mislabels static analysis as transient physics | [Structural media and recorded evidence](domains/structural-media.md) |
| Video works in local Chrome but CI Chromium reports no supported streams or never reaches ready | [Chrome and Chromium codec coverage](inbox/2026-10-29-chrome-and-chromium-do-not-share-video-codecs.md) |
| A native navigation works locally but the hosted test times out after Cloudflare removes .html | [Exact canonical navigation routes](inbox/2026-10-29-hosted-navigation-must-accept-the-canonical-route.md) |
| A mesher fails with OpenSSL symbols despite gmsh-first imports, or runtime version lookup fails after solving | [Select the mesher runtime before Python starts](inbox/2026-10-29-mesher-runtime-must-be-selected-before-python-starts.md) |
| A model reports ready but disappears or contains non-finite transforms after valid JSON loads | [Loading readiness and report availability](domains/loading-readiness.md) |
| A viewer's error/retry controls clip off a phone despite hidden page overflow | [Grid tracks and header minimums](inbox/2026-10-29-shrink-grid-tracks-before-truncating-headers.md) |
| Build thumbnails are missing, show unrelated parts, or disappear after publishing | [Part image identity and provenance](domains/part-images.md) |
| Sheet thickness or dimensional bounds change after STL export without a CAD edit | [Tessellation bounds versus stock dimensions](inbox/2026-10-29-tessellated-bounds-are-not-stock-dimensions.md) |
| Part status moves to another row after sorting, retries duplicate controls, or a model preview loses its original download | [Parts retain their identity when their table changes](domains/build-portal.md) |
| A newly integrated CAD viewer opens but disposal throws or its animation keeps running after removal | [Parts retain their identity when their table changes](domains/build-portal.md) |
| The 3D file viewer looks unrelated to the main site or its controls lose contrast | [Original-file viewer theme](domains/file-viewer-theme.md) |
| Phone status checkboxes remain reachable but their part names disappear, despite sticky cell styling | [Sticky identity and the scroll wrapper](inbox/2026-10-29-sticky-part-identity-needs-the-scroll-wrapper.md) |
| Wheel tests fail after a fixed sleep under software rendering | [Wait for rendered camera targets](inbox/2026-10-29-camera-tests-must-wait-for-rendered-targets.md) |
| A PCB is seated without overlap but cannot be installed, reached with a driver, or removed | [Final pose does not prove electronics service](inbox/2026-10-29-final-pose-does-not-prove-electronics-service.md) |
| A removable board has wire lengths but no verified disconnect travel, retained slack or wire exit | [Cutting allowance is not service slack](inbox/2026-10-29-wire-allowance-is-not-service-slack.md) |
| A bounded CAD check stays green after a configuration edit, or invalid Boolean geometry reports zero overlap | [Full input closure and valid Booleans](inbox/2026-10-29-bounded-cad-checks-need-full-inputs-and-valid-booleans.md) |
| A manufacturer check turns green when its private CAD cache is missing | [Manufacturer checks must reject missing inputs](inbox/2026-10-29-manufacturer-checks-must-reject-missing-inputs.md) |
| A McMaster lookup reports no specification table or no CAD controls | [Verify the rendered cause](inbox/2026-10-29-missing-product-table-needs-rendered-evidence.md) |
| Print hashes pass but package mixes revisions, slicer settings or stale totals | [Preflight is not a generation transaction](inbox/2026-10-29-print-preflight-is-not-a-generation-transaction.md) |
| Demo hit counts increase but targets stay upright, detach, or clip through the floor | [Hits must produce visible, validated motion](inbox/2026-10-29-target-hits-need-visible-motion.md) |
| Published notes show Mermaid source instead of a diagram | [Validate the published diagram consumer](inbox/2026-10-29-mermaid-needs-the-published-renderer.md) |
