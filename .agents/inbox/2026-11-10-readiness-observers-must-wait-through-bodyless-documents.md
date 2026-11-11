# Let readiness observers wait through a temporarily bodyless document

On 2026-11-10 PR #287's WebKit campaign at `6dd7944b` failed after44.331s
at the final mobile retry readiness wait. All preceding motion, asynchronous
loading, mode, laser and route controls were saved in26 outputs. The exact error
was `TypeError: null is not an object (evaluating 'document.body.dataset')` at
the observer's line158. Its page-error log contained that same error. The owned
browser/listener closed and all source, accepted-data, webroot and protected-tree
guards remained unchanged. No shared validation followed this incomplete run.
The original failure and outputs remain retained; Chrome's independently accepted
complete campaign used the same unchanged product runtime and candidate data.

The campaign now serializes `currentRobotReady` from the focused helper into both
initial and retry waits. An absent body or incomplete simulator object returns
false until the body is ready and the actual collection identity matches.
`node --test tests/site/models/test-current-motion-ready.mjs` ran1 test with0skips
in52.148ms on existing Node22.23.4. It executes the actual serialized callback
against bodyless/loading/missing-state/wrong-source/ready states. A deliberate
throwing getter still propagates: errors are not caught or filtered.

The context-wide product page-error listener and final empty-error assertion
remain unchanged. This is a narrow observer correction; a fresh separately
reviewed WebKit action must still demonstrate actual retry completion and all
product errors remain fatal. Do not infer a passed campaign from the earlier26
outputs or repeat an unchanged action until the observer failure is understood.
