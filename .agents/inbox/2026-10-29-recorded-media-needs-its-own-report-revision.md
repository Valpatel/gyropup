# Recorded media needs its own report revision

On 2026-10-29, the landing highlights audit found that `exports/leg/rig_jump.mp4`
still belongs to the 16.25 kg, 48.1 V leg study, while the adjacent current
`rig-results.json` describes an 18.75 kg, 36 V study. A shared filename or directory
does not establish that an animation and report came from the same run.

Evidence, from `python3` reading the current report and
`git show ae919f7211f236f398ff77cc25d00c2017c1ab9c:exports/leg/rig-results.json`:

```text
historical: half_mass_kg=16.25, bus_v=48.1
historical report SHA256=89e2fdb42a5250430592b6a2f3b97e0c1ddddf7e6fa33a8ec8510f913d223c80
current: half_mass_kg=18.75, bus_v=36.0
rig_jump.mp4 SHA256=7b59e8e0c807d04ca1387a4fd63f03536d44be5a637617e835fe5811ff50f217
```

The report was regenerated without regenerating the movies. Duration and decode
checks cannot find this mismatch: both files are individually valid.

The landing reel binds the movie to its historical report and producer source,
labels the insert as archived MuJoCo, and validates those identities in
`tools/check-highlights.py`. A new current model or report must not silently
relabel an old clip. Source binding and moving decoded pixels are separate checks.

This does not regenerate the leg solver or qualify hardware. The older Progress
leg-result gallery still pairs current results with these archive clips; that
separate consumer needs explicit provenance or newly generated matching videos.
