# Generators wrote this machine's paths into public exports

On 2026-11-01 a release review (issue #141) found absolute home-directory paths in 17 tracked files and compute host
names in 6 more, on `dev` and published on gyropup.com. Most came from generators, not from people:

- `cad/assembly.py` wrote each mesh as `str(path)`, so `exports/assembly.json` named the main checkout's folder 94 times.
- `cad/turret_box.py` and `cad/build_turret_box.py` wrote the J501 project's files the same way into `box.json` and the
  turret scene manifest.
- `sim/turret_e2e.py` put absolute mesh paths in the committed MuJoCo world; `rig/compare.py` did the same for a run's
  plot; `sim/leg_spring_study.py` printed one into a committed log; `rl/scripts/sim2sim.py` records its model folder.
- Notes quoted the commands their author ran, with absolute paths, and design notes named the host each run used.

A path built on one machine also fails on every other one: `sim/model.py` silently loaded another checkout's meshes.

## Corrective rule

- Write paths from the repository root (or from the file that names them, as MuJoCo's `meshdir` does), and files of
  another project from its root variable (`J501_DIR/...`). Name machines by role: "the recording compute host",
  "a CAD host". The hardware family (a GB10) is fine.
- `npm run test:privacy` (CI job `privacy`) scans the tracked files and the built `dist/`. It reports only path, line and
  kind, because public CI logs would otherwise republish the string.
- Findings that cannot be fixed at once go on `tools/privacy-ratchet.txt` with a reason. The ratchet may only shrink.
- `cad/`, `catalog/` and `designs/` are hashed whole by the carrier receipts: a generator fix there ships with the next
  CAD regeneration, and the guard fails that regeneration if the fix is missing.

## Limits

Git history keeps the old strings; nothing was rewritten. The guard knows private repository names only as slugs under
the project's accounts (or from `GYROPUP_PRIVATE_NAMES`), and recognises host names by pattern, so a host named like an
ordinary word passes. Review still matters.
