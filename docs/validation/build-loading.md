# Build viewer loading feedback

The workshop shows actual completed model parts while the shared viewer downloads,
checks and parses the selected model. It keeps the previous model during a switch.
The index/guide phase is indeterminate; after all parts load, the bar still says
“Preparing the 3D view” until the new scene has been applied successfully.

The product adapts the existing callback in the pinned cad-agent viewer. Its
“Loading model part N of M” event precedes the download, so the completed count is
**N − 1**, not N. Only the known messages with the manifest's exact total receive
a numeric value. Unknown phases remain indeterminate. This is a part count, not
byte progress or an estimate of remaining time. The shared toolkit and its
30-second loading deadline are unchanged.

Run `npm run build && npm run test:build-loading`. It uses the existing installed
browser and an owned temporary server unless `SITE_URL` names the test server.
Set `PLAYWRIGHT_BROWSER=webkit` for the second engine. Both run in the existing
build-guide CI suite. The test holds actual committed mesh responses and checks:

- Unknown index work is indeterminate; blocked first/second meshes stay at zero/one.
- Desktop and phone layouts show the counter within the viewport.
- Failed replacement leaves the old model and ends busy feedback; retry succeeds.
- A superseded model request or initial-index retry cannot change or dismiss a newer load's progress.
- A corrupt initial mesh yields the text fallback; retry shows progress and real 3D.

Progress does not qualify a build sequence or physical design. Assembly path and
support validation have their own evidence.
