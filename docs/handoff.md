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
