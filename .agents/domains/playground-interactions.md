# Playground controls must match their visible promise

A PAUSE label freezes mechanism time and positions, not only stage advancement. Camera inspection and manual stage selection remain usable. Focused native controls own their keys; global scene shortcuts must release on keyup even if focus moved. Hold buttons need pointer and keyboard down/up handling plus blur release.

Overlay changes must be tested against camera position, target and projection. On phones, select a part before checking action-bar hit targets: an empty-screen screenshot misses card overlap. Measure text centering and tap sizes, not just a CSS declaration.

Asynchronously styled overlays must refresh their measurements after CSS loads and after their actual box size changes. Ignore their temporary normal-flow boxes when computing canvas coverage. Queue observer-triggered canvas updates to the next animation frame to avoid ResizeObserver delivery loops. Test a fresh ready-state page with delayed overlay CSS and project the visible model bounds into the available canvas; model switching or window resizing can hide a broken initial measurement. `tools/test-robot-controls.mjs` covers the talk dock race and preserves summary-card projection stability.

Reload reuses the scene, renderer, character and a cloned conversation snapshot, gradually fills only missing capacity, gates conflicting actions and honors reduced motion. `talk.conversation` returns a clone; compare its content, not object identity.

Run `npm run test:interactions`, `test:camera`, `test:robot`, `test:viewers` against the built site. Wait for state/frame predicates under software rendering; short wall-clock sleeps do not prove simulated progress. Keep the should-versus-does inventory in `docs/validation/playground-behavior-audit.md` current. These checks validate software interaction, not hardware safety or whether children find the game fun.
