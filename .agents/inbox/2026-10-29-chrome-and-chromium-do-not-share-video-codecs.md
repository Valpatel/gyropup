# Chrome and Chromium do not share every video codec

On 2026-10-29 the E1 player passed installed Google Chrome and WebKit but failed the first ready-state wait in CI run `40848940284`, job `123363283836`. Its artifact decode tests passed. The exact CI runtime was pinned Playwright 1.56.1 Chromium build 1194, `HeadlessChrome/141.0.7390.37`, while local tests defaulted to the installed `chrome` channel.

An isolated local reproduction with that same bundled browser reported H.264 `canPlayType` as an empty string, VP9 as `probably`, media error code 4 `DEMUXER_ERROR_NO_SUPPORTED_STREAMS`, readyState 0 and networkState 3. The product correctly retained its still/error UI; the clip itself lacked an encoding that this browser could decode. The original movie is AVC High level 3.1 (`ffprobe`: profile High, level31), so the capability query now uses `avc1.64001f`.

Corrective rule: test the same browser binary/channel as CI and record media capability, error, ready/network state and actual source on failure. Ship a VP9/WebM companion when H.264 is not supported; do not switch CI to Chrome to hide the product gap. Bind both encodings to the same source and solved field, decode all frames in both, and compare representative model pixels. The VP9 companion has the same 12 seconds and 288 frames; its unloaded/loaded model region differs from H.264 by a mean 0.83/255. Native source selection, failure/retry and real decoded playback are exercised in both Chromium variants and WebKit. Serve WebM with `video/webm`, including the local development server.

The renderer at `a0d9dc34` uses the existing solved field only; no FEA or geometry changes were needed. Source/output receipts, the companion corruption test, codec/profile checks, media MIME checks and browser diagnostics live in the normal study-media harness. Use an isolated pinned Playwright cache so another worktree's browser install cannot garbage-collect the tested runtime.

Limits: a capability query is not proof of successful decoding; readiness and advancing decoded frames remain required. This resolves presentation compatibility, not the mechanical strength failure or hardware safety.
