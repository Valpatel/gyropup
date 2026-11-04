# What stops an over-commanded leg from breaking itself

The owner asked on 2026-11-03: "what prevents us from ripping apart the legs by over commanding the motors?" and
"What's the point of having 120nm motors if we cap at 60nm?" ([issue #202](https://github.com/Valpatel/gyropup/issues/202)).

Work in progress: the layer-by-layer audit, the per-build torque limits and the protections added are being written
on branch `feat/leg-command-limits`.
