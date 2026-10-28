# Handoff: where the work stopped (2026-10-27)

The session stopped near the weekly usage limit. Everything below was saved first: committed on main, committed on the
turret branch, or written in the plan docs. Pick the work up from here.

## How the work is organised

Each workstream has a planner (Fable 5.1) and an implementer (Opus 5.5).

- **The planner** reviews the workstream and writes a plan towards a first physical prototype. It picks highly
  available parts and keeps the design simple.
- **The implementer** works through the plan's tasks with evidence, in its own worktree and branch, and the main
  session merges the branch.
- **The parts rule** applies to everyone (docs/decisions.yaml D40): every part is off the shelf, printed, or ordered
  online. No quotes.
- **A program tick** (a session cron, every 2 h) kept the agents going. It was cancelled at the stop. To recreate it,
  ask for a tick that, for each workstream:
  - merges the implementer's finished branch into main and pushes;
  - starts the next Opus implementer on the plan's open tasks;
  - starts a Fable planner when a plan is done.

| Workstream | Plan | Implementer |
|---|---|---|
| Turret | docs/turret-prototype-plan.md (Fable; may have TODO sections) | worktree ~/Code/gyropup-turret, branch turret/program; charter docs/turret-program.md |
| Leg test rig (M3) | docs/leg-prototype-plan.md (Fable) | not started: worktree ~/Code/gyropup-legrig, branch legrig/program |
| Body (M5) | docs/body-plan.md (Fable) | not started: worktree ~/Code/gyropup-body, branch body/program |

## Open items

### The turret sim mode's sound

The user wants the main sim's sound effects in the turret mode (designer/turret_bench.js). A diagnosis was done; no
fix yet.

What was found:

- On desktop the sound context does start (SPACE counts as a gesture), and the existing calls play: flywheels, laser,
  shot, reload.
- Many turret events have no sound at all: the dial stepping, a ball dropping into the chute, and cans landing. Paper,
  cans and plates all play the same "bop and ring".
- The journey walkthrough is nearly silent: only one of its 8 stages makes a sound, and nothing plays in slow motion.
- The flywheel hum is one ramp and then a 1.8 s coast. It doesn't follow the wheels' speed and has no brake on
  release (D9).
- The servo whine is about 30× quieter than a shot.
- On a real iPhone: sfx.js unlocks on pointerdown, keydown and touchstart, but iOS counts the end of a tap as the
  gesture, so taps alone may never start the sound.

The fix:

- **In sfx.js (additions only, same compressor, limiter and reverb chain):**
  - a turret flywheel voice set every frame from the wheels' speed, with a brake sound;
  - sounds for the dial step, the ball drop, and a muzzle shot without the dial click;
  - hit sounds for paper and cans, and a sound for a can landing;
  - a slow-motion factor for the journey.
- **In turret_bench.js:** call those sounds, and unlock audio on pointerup and touchend.

The test harness (Playwright, system Chrome with `--use-gl=angle --use-angle=gl-egl`) was in the session's temp
scratchpad. Rebuild it from the description above.

### Leg (main session's files)

- **Validation state:** exports/leg/fea/summary.json and the rig's exports/leg/rig-results.json. The leg carries
  13.1 kg, half the 26.2 kg robot.
- **The stops:** a power cut is the legs' fault case (D39). With the thicker TPU 95A stop sleeves (Ø26, 8 mm wall,
  E = 9.8 MPa from Bambu's datasheet), the undamped collapse puts 1.46 kN on the knees (it was 3.0 kN with the
  previous sleeve and an unsourced, too-stiff modulus).
- **Follow-up (over-travel):** at the stops' full 7.4° squeeze, the knee-out stops let the wheel link touch the hip
  frame (about 1.4 cm³). Rig events never load the knee-out stops; a 120 N·m motor fault would. Fix it with a
  stiffer, shorter-travel sleeve on the knee-out posts: TPU_SLEEVE per post, and the rig's stop model per direction.
- **Follow-up (output adapter):** its R1 study holds it only at the motor's screws, which is conservative (1.15
  against 1.2). Add the 61812's radial support to that study.
- **Bench tests for the first leg (milestone M3):**
  - an unpowered RS-04, back-driven (its power-off damping);
  - the stop sleeve's stiffness;
  - an M5 heat-set insert's torque against preload;
  - the tyre's stiffness;
  - the rotor inertia.

### Springs

research/leg-suspension.md has the answer. For now there's no spring (D39). A knee-to-knee outboard spring is the
add-on if jump height or runtime ever need it.

### cad-agent

PR #19 (pure-couple torques in fea) is merged. Gyropup's venv imports cadagent from ~/Code/cad-agent-gyropup-int.
Repoint it to dev once nothing else depends on that worktree.

## Update 2026-10-27 midday (usage limit reached again)

- **Leg committed** at the 14.75 kg design mass with the machined output adapters (D46). Everything passes in
  exports/leg/fea/summary.json except **wheel_link R1w: SF 1.13 against 1.2** (the full 2,065 N drop_150 axle spike
  on the wheel link alone, a deliberately conservative case; R1 on the same link is 1.89). Fix next: thicken the wheel
  link's body (P['wheel_t']) a few mm or add material where its arm meets the hub, rerun cad/leg_studies.py. The drop
  test is the last bench test, so nothing earlier waits on it. Front link R1 is 1.21 (just passes).
- **D39 text** still quotes the 13.1 kg numbers; the 14.75 kg rig (exports/leg/rig-results.json): jump gearbox
  101.5 N m (peak 107.3), undamped power cut 1,713 N on a knee (fault case, FEA R3K 1.27 >= 1.0), damped 263 N.
- **Agents were stopped** at the limit, their work uncommitted in their worktrees: turret (~/Code/gyropup-turret,
  7 commits ahead), leg rig (~/Code/gyropup-legrig), body (~/Code/gyropup-body). A Fable pre-order review of the leg
  package and a review of cad-agent PR #23 (the FEA temp-folder fix, already merged into ~/Code/cad-agent-gyropup-int)
  were also stopped. Restart each from its plan; recreate the 2-hour program tick (its prompt now carries the disk policy).
- **Disk:** heavy files go to /mnt/storage-10tb/claude-scratch/gyropup/ (memory: disk-space-policy).
- **Build page:** designer/build.html (top bar "Build"): everything to order and print, by seller.

## Update 2026-10-27 evening: where everything is tracked (pick up from any computer)

**GitHub is the record.** Every workstream branch is pushed to origin, and each one has a draft PR into main that
closes its issues:

| Workstream | Branch | PR | Issues |
|---|---|---|---|
| Turret: clean mechanics, its own computer (D66), Rival speed (D68), ammo (D67) | turret/program | #15 | #1, #2, #3 |
| Leg stops (D53) | leg/stops | #16 | #4 |
| Body: power for D65, P0 shunt fix, fuse board, sections | body/program (includes b5, b8) | #17 | #10–#13 |
| Leg core (main session): front link and dowels, the wheel link overlap, BUS_V 36 V | main | — | #5, #6, #7 |
| Rig: predictions at 16.25 kg / 36 V | legrig/program | — | #8 |
| Instant prices that need an upload | — | — | #9 |
| Move onto cad-agent's gates | — | — | #14 |

cad-agent's design-process work (dossier, integrity gates, section review) is tracked in Valpatel/cad-agent:
- the tracking issue is #41;
- tasks T2–T16 are issues #29–#40;
- PRs #25, #26 and #27 are merged into dev.

**Decisions from today:**
- D65: two DCB609 FLEXVOLTs in series, a 10S bus at 30–41 V.
- D66: the turret is its own robot, on a reComputer Mini with a Jetson Orin NX 16 GB.
- D67: Rival rounds, off-brand allowed within 22.2–22.8 mm and 1.6–2.0 g.
- D68: about 100 fps, with a 105 fps physical ceiling.

**Compute.** Heavy CAD, FEA and sim runs go to the compute hosts with `tools/gp-remote` (copy it to ~/.local/bin).
- It rsyncs the worktree and ~/Code/cad-agent-gyropup-int to `~/gyropup-compute/` on the compute hosts listed in ~/.config/gp-remote/hosts (SSH aliases) and pulls back the
  paths you list.
- The GB10 environment is a venv built from this venv's `pip freeze`, minus the Intel, pardiso and umf packages.
- gmsh comes from a micromamba env (`~/gyropup-compute/gmsh-env`, with gmsh.py symlinked into the venv), because PyPI
  has no aarch64 gmsh.
- gp-remote LD_PRELOADs that env's OpenSSL.
- There's no PARDISO on aarch64, so the FEA uses SciPy's solver.

**WIP sites** (`cad-agent site --serve --host 0.0.0.0` run in each worktree): main :8642, turret :8651, legrig
:8652, body :8653, legstops :8654.

## Update 2026-10-27 late night (5-hour usage limit)

Everything committed is pushed. Uncommitted edits in progress were also snapshotted to `wip/<branch>` branches on
origin. These are for recovery only, not reviewed: the agents' own commits supersede them.
- `wip/turret/program`: 39 files of the turret's mechanical cleanup, D66 and D68.
- `wip/leg/stops`: the stops work since its last commit, including the GB10 FEA outputs.
- `wip/wheels/study`: the air-tyre wheel study (#18).
- `wip/feat/gate-containment` in cad-agent: the PR #42 review fixes.

State at the limit:
- **Merged to main:**
  - the leg rig on 10S, with integrity checks (f50e5c4);
  - the body with the P0 shunt fix, fuse board, battery bay and 183-screw integrity checks (507de33, PR #17; #11, #12 and #13 closed).
- **cad-agent dev:** the plan (#25), the dossier (#26), the gates core (#27) and connectivity (#43, closing #30).
- **In flight:**
  - turret: issues #1-#3, PR #15;
  - leg stops: #4, PR #16;
  - wheels: #18, branch wheels/study;
  - containment: cad-agent PR #42, issue #31. It needs a rebase onto dev, now that #43 is merged.
- **Main-session leg work:** #5, #6 and #7 wait on leg/stops.
- **Mass:** the design mass is set after #18 picks a wheel (#10).
- **Purchases:** 4 RS-04s ordered (docs/purchases.md); a spare is #22.

To resume:
1. `gh issue list` in both repos.
2. Read each issue's last comment for its resume notes.
3. Restart each agent from its issue and branch.
