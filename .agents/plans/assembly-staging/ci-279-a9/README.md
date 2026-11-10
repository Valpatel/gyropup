# Preserve the failed CI observations and qualify their corrections

Pinned-image CI for PR279 head a9f2f361 tested merge521811c5 and failed two jobs.
The [source/artifact receipt](ci-failures.json) retains their actual run/job/artifact
identities and raw log/report hashes. [Playback failure](playback-failed.json)
normalizes only the preview origin; its [unchanged failure PNG](playback-failed.png)
is an original-belly-bay snapshot of that failed test, not a current CAD illustration.

The second of eight arrival observations failed while awaiting a dynamic Three
import after manual step navigation. One document token/creation, same-document
URL updates and no page errors/crash were recorded; the first L.motor_front
sample passed. Those facts do not identify the browser/runtime destruction
cause. The correction follows the existing late-wheel incident: use actual
loaded mesh vector constructors and keep player tick/pause/16 posed/rest vertices
inside one synchronous observation. All8x16 world-delta, dependency, direction,
pause/progress assertions remain, with document identity checked per arrival.
There is no retry, timer extension or alternative passed state.

The audio check read a null current utterance after adjusting volume. The old
CI test retained no design/timer trace. A controlled-clock reproduction of the
unchanged baseline talk demo confirms a concrete race: its unconditional400ms
`say` cancels an already active conversation before loading the greeting clip.
[Before](audio-greeting-before.json), the answer is busy/active then becomes
null/not busy with two more cancellations. [After](audio-greeting-after.json),
its active text, busy state and cancellation count remain unchanged. The existing
`announce` method already honors conversation ownership; use it for the greeting.
The audio test now explicitly advances that real400ms deadline during an answer
and retains the browser/Piper gain, word-boundary, mute/reload/phone assertions.

Local controls use native Chrome151 and existing WebKit2215 without installations.
They do not establish parity with the unavailable pinned bundled Chromium1194.
Reports bind the actual staged source/harness hashes; their built version remains
a9f2f361, not the later evidence-commit identity. Normal final-head CI and independent
review remain required. No CAD, printed leg, viewer/player fork or geometry change
is involved, and no native assembly query was run.

The first local WebKit audio attempt failed at clock setup before talk navigation:
installing a running clock atT then pausing atT may findT already past. Preserve
[its classified receipt](local-first-pass.json). The successor pauses at a future
boundary before loadingtalk, then advances the actual newly scheduled400ms timer.
Only that WebKit audio scope was repeated after the source correction; Chrome
passed the first clock variant. [Actual source hashes and qualifications](local-source-results.json)
keep those attempts distinct. Both full [Chrome](chromium-playback.json) and
[WebKit](webkit-playback.json) playback reports retain128 world vertices and one
unchanged document token each, with no page errors. The [checkpoint](checkpoint.json)
seals the retained evidence; original CI failures are not overwritten by local passes.
