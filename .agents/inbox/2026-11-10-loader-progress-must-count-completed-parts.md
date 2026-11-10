# Count validated completions, not the part about to download

On 2026-11-10, the Robot build workspace showed an empty viewport while loading
171 model parts. The shared viewer already emitted progress, but the workspace
never supplied `onProgress`. Its N-of-M message runs before fetching part N.

Evidence: `npm run test:build-loading` (Chromium) passed with real committed mesh
responses held at parts one and two: displayed completed counts stayed at 0/171
and 1/171. Failure/retry and superseded requests also passed. The initial test
fixture incorrectly registered two holds for the same URL: Combined deliberately
shares Robot mesh URLs. Registering the newer hold only after observing the older
request fixes the fixture; every expected interception now has a finite deadline.

Rule: consume real loader events, distinguish work started from work completed,
and scope updates to the current request. Unknown phases stay indeterminate.
Hold actual assets to test that time alone cannot advance a progress bar; verify
shared-resource URL identity when testing supersession.

Limits: the current adapter follows the pinned shared viewer's text callback.
Upstream callback changes require this consumer's browser regression, not a
simulated timer or an assumed percentage. Counts do not estimate time or bytes.

See [loading validation](../../docs/validation/build-loading.md).
