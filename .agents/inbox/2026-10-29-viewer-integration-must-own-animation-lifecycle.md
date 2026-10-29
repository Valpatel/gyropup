# A viewer integration must own its animation lifecycle

On 2026-10-29, the original-file viewer opened successfully against Gyropup's customized stage, but its teardown contract did not match that stage. The viewer called `stage.dispose()`, while the product stage exposed only `start()`. Making that call optional would avoid an exception while leaving animation callbacks, controls and the WebGL context alive.

The source compatibility receipt was measured before applying the product lifecycle addition:

```text
viewer commit: cad-agent d6b4b8e, file-viewer.js
product stage: gyropup 0f2ef3076b56, designer/kit/stage.js
{'viewer_calls_stage_dispose': True, 'original_product_stage_has_dispose': False}
```

The check reads both committed sources with `git show` and compares the presence of `stage.dispose()` in the viewer with a `dispose()` method in the stage. This is an API mismatch receipt, not a claim that the parser or CAD geometry is wrong.

The product fix adds a stored animation-frame handle, stop/resume, and idempotent disposal. Disposal disconnects resize observation, removes the product's smooth-wheel listeners and controls, releases the renderer/context, and removes its canvas. Existing camera, zoom and lighting behavior is retained. A frame callback that stops or disposes the stage prevents that frame from rendering again.

`tools/test-build-portal.mjs` opens actual published STL, STEP and 3MF files, then verifies that callbacks stop, resume, and stay stopped after disposal; the canvas disappears and its context is lost. Chromium and WebKit passed that integration on the pre-final-notice build on 2026-10-29. Later notice-placement and bootstrap refinements still require their own final run receipts on PR54.

Rule: integration must verify lifecycle APIs as well as the successful first frame. Preserve a product's customized rendering behavior and add the missing ownership contract; optional chaining around teardown is not resource cleanup. See [parts portal integration](../domains/build-portal.md) for the durable entry points.

Limits: this verifies the owned animation/renderer lifecycle, not every possible external reference or a browser memory-pressure model. Model parse corpus validation and hosted MIME/worker checks remain separate evidence.
