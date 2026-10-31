# Historical body, leg-rig and CAN drafts

Inventory checked **2026-10-31** for [documentation task #129](https://github.com/Valpatel/gyropup/issues/129).
These drafts contain useful unmerged work and unresolved failures. Preserving or closing their PRs does not
integrate their code, qualify their hardware, or complete their acceptance issues. Resume future design work
from current `dev`, using the owning issue and the source references below.

The comparison baseline was main `b4eaa00269655cedccd719a99989f84e2799fa47` and dev
`9b8710b6ff733fb55454f4f96af9d4b027ad62d9`, which had identical trees. The three remote source branches still
existed at this audit. Their unique non-merge commits were absent from both baselines, including by patch
comparison. This is an inventory for archival preparation; it does not claim that archival tags have been published.

## Source references and remaining ownership

| Historical draft | Exact source tip | Remaining acceptance work |
| --- | --- | --- |
| [#28: body mass and pad retention](https://github.com/Valpatel/gyropup/pull/28), `body/program` | [`5fe10c632f201cf886027fcd8499564b55dcda03`](https://github.com/Valpatel/gyropup/tree/5fe10c632f201cf886027fcd8499564b55dcda03) | [#10: body mass, geometry and load evidence](https://github.com/Valpatel/gyropup/issues/10); [#26: retained pads and physical coupons](https://github.com/Valpatel/gyropup/issues/26) |
| [#30: leg-rig predictions and gates](https://github.com/Valpatel/gyropup/pull/30), `legrig/program` | [`d862b59e4d101a43ba746a26d772cf529be58eee`](https://github.com/Valpatel/gyropup/tree/d862b59e4d101a43ba746a26d772cf529be58eee) | [#8: coherent rig design and evidence](https://github.com/Valpatel/gyropup/issues/8); [#14: gate integration](https://github.com/Valpatel/gyropup/issues/14); [#29: structure/bearings](https://github.com/Valpatel/gyropup/issues/29); [#24: measured wheel](https://github.com/Valpatel/gyropup/issues/24) and [#25: interface](https://github.com/Valpatel/gyropup/issues/25); [#116: current RS-04 mounting](https://github.com/Valpatel/gyropup/issues/116) |
| [#46: CAN actuator and motor research](https://github.com/Valpatel/gyropup/pull/46), `research/can-actuator-candidates` | [`40b5c5f2967ed8253a0e67cd8af875e06e3d27a3`](https://github.com/Valpatel/gyropup/tree/40b5c5f2967ed8253a0e67cd8af875e06e3d27a3) | [#45: electrical/protocol candidate evaluation](https://github.com/Valpatel/gyropup/issues/45); [#124: ordered Deeahdah motor interfaces](https://github.com/Valpatel/gyropup/issues/124) |

The [complete inventory](2026-10-31-unmerged-drafts.json) records each full commit SHA, merge base and changed
path, including rename sources. Source-tip links retain the original files and their historical context. The
inventory does not copy old active CAD, simulation, control, generated manufacturing or operator-guidance files
into the current design.

## Body: retained work and failed or missing evidence

The body draft contains four unique non-merge commits, one merge commit and 33 changed paths:

- [`220e02c`](https://github.com/Valpatel/gyropup/commit/220e02c397cfc306aef65bd831662cdfb6b50f4d): the historical 2.56 kg turret mass/centre, shorter lidar-cable allowance and 1.46 kg pack assumption.
- [`c899d30`](https://github.com/Valpatel/gyropup/commit/c899d3090f84e779cad0a3d9f7d261eae0cc3e36): TPU pad retention lips, solid webs and longer M3 screws into existing floor-flange nuts.
- [`c980012`](https://github.com/Valpatel/gyropup/commit/c9800128be7c7ebf8b901631135472621a6b50de): cheek lightening windows, 1/8 in deck and revised intake pitch.
- [`5fe10c6`](https://github.com/Valpatel/gyropup/commit/5fe10c632f201cf886027fcd8499564b55dcda03): merged-leg mass reconciliation and the 3.53 kg wheel assumption in the robot simulation.

The unique scope is in `cad/body_battery.py`, `cad/body_frame.py`, `cad/body_joints.py`, `cad/body_layout.py`,
`cad/body_legloads.py`, `cad/body_params.py`, `cad/body_sheet.py`, `cad/test_body.py`, `sim/robot_v2.py`, the body
order/section notes and corresponding exports. Main retained the pre-draft contents for 32 of these paths.
Its later `sim/robot_v2.py` change assigns output adapters and screws to moving upper links; that does not
incorporate this draft's mass changes.

The committed [mass report](https://github.com/Valpatel/gyropup/blob/5fe10c632f201cf886027fcd8499564b55dcda03/exports/body/mass.json)
has `gate.pass: false`: **37.75 kg**, or **37.25 kg with scheduled levers**, versus the historical **37.0 kg** gate.
The [last #10 checkpoint](https://github.com/Valpatel/gyropup/issues/10) describes the
previous deck's D2 result as **SF 1.83**, with the thicker replacement still awaiting FEA. Cheek/deck prices,
strength/convergence, scenarios and pad-study evidence require reconciliation with the chosen current design.
The source reports historical clean integrity and 22 clash-free stances; these bounded results do not replace
the missing evidence. The current [100 lb ceiling](../design-weight-budget.md) does not convert the failed
historical configuration into a validated design.

[#26](https://github.com/Valpatel/gyropup/issues/26) preserves the retention implementation and its physical
coupon, crush, rebound and slanted-drop work. The later retention checkpoint supersedes the initial plan's
new-floor-PEM proposal: the committed candidate uses existing nuts, so that retention change did not require a
new floor quote. No physical pad acceptance was performed by this archival audit.

## Leg rig: predictions exist and retain their failure

The rig draft contains four unique non-merge commits, one merge commit and 24 changed entries:

- [`0767c0e`](https://github.com/Valpatel/gyropup/commit/0767c0e328117dd132ffbb832ac171bfea22779c): 18.75 kg scenarios with a 185 mm controlled crouch, a separate 140 mm low case and the 254 mm tyre envelope.
- [`2ab0b49`](https://github.com/Valpatel/gyropup/commit/2ab0b49b50f344bdf79d5111369bea44aebc87f8): proposed hip-frame proof load and undamped power-cut restrictions/inspection.
- [`d7b0863`](https://github.com/Valpatel/gyropup/commit/d7b0863126803b6ee95b0753871423865a38ae3e): unfinished migration from the old integrity checker to `cad/rig_gates.py`.
- [`edd1486`](https://github.com/Valpatel/gyropup/commit/edd1486ecac0da2ee00f9f07fdde1075169c5084): historical prediction, fault and reproduction results generated from `0767c0e`, plus bench-document updates.

**The predictions are committed, not missing.** The later PR wrap-up checklist does not accurately describe
their existence. The [prediction report](https://github.com/Valpatel/gyropup/blob/d862b59e4d101a43ba746a26d772cf529be58eee/exports/rig/predictions.json)
records an 18.75 kg model with one tick of latency at 500 Hz. It includes **17.2 N m** stand-up torque and a
**141.1 mm** jump. The jump verdict is explicitly **false** against the unchanged **200–320 mm** criterion.
The committed [criteria](https://github.com/Valpatel/gyropup/blob/d862b59e4d101a43ba746a26d772cf529be58eee/rig/criteria.json)
also retain a **14.75 kg** load-plate description while the runner defaults to 18.75 kg. Some prediction-following
and physical load-cell checks are unmeasured; the report does not represent a complete bench pass. Preserve
these recordings and their actual inputs rather than relabeling them as a current run.

The unique code is in `cad/build_rig.py`, `cad/rig_assembly.py`, `cad/rig_gates.py`, `cad/rig_hardware.py`,
`cad/rig_parts.py`, `cad/assembly_checks.py` and `rig/`, with bench/safety/section notes and `exports/rig/` results.
The draft removes the old integrity report and checker but contains **no committed `exports/rig/gates/` output**.
Main retained the pre-draft contents for 23 changed entries; its bench-document addition warns about the
unacceptable old RS-04 mounting fixture and does not integrate this draft's proposed procedures.

The [#8 recovery checkpoint](https://github.com/Valpatel/gyropup/issues/8) records **136 old-checker failures**
around the larger tyre and rig, **0.55 kg** insufficient ballast, and an unrun gate migration. The historical
prediction job finished; its pre-gate CAD outputs were not accepted. Current mounting, wheel interfaces,
clearances, structure/bearings, load assumptions and criteria must be reconciled before new evidence or a
powered fixture release. The proposed bench tests are unperformed acceptance work, not proof of resolution.

## CAN research: keep the dated sources and unresolved limits

The two unique commits are [`8b3cd3a`](https://github.com/Valpatel/gyropup/commit/8b3cd3aa7cc93b69d413ec05cbae73b0b7e74a1a)
and [`40b5c5f`](https://github.com/Valpatel/gyropup/commit/40b5c5f2967ed8253a0e67cd8af875e06e3d27a3).
The four changed paths comprise three added documents and an operator symptom-index entry. None of the three
added documents was present in the comparison baselines:

- [Candidate assessment, checked 2026-10-29](https://github.com/Valpatel/gyropup/blob/40b5c5f2967ed8253a0e67cd8af875e06e3d27a3/research/can-actuator-candidates-2026-10-29.md).
- [Original repository hardware-selection guidance](https://github.com/Valpatel/gyropup/blob/40b5c5f2967ed8253a0e67cd8af875e06e3d27a3/.agents/domains/can-hardware-selection.md).
- [Original architecture-evaluation incident record](https://github.com/Valpatel/gyropup/blob/40b5c5f2967ed8253a0e67cd8af875e06e3d27a3/.agents/inbox/2026-10-29-check-the-proposed-architecture-before-rejecting-a-part.md).

The assessment preserves the proposed direct-main-battery MAD ESC architecture, hardware/firmware revision
conflicts, CAN position-servo candidates, mixed classical-CAN bus constraints, and the exact Deeahdah listing's
unverified dimensions and ratings. Its availability, pricing and vendor claims are dated research, not current
stock information or approved substitutions.

The owner subsequently confirmed purchase of the Deeahdah PRO 3115-900KV motor family under
[#124](https://github.com/Valpatel/gyropup/issues/124). That issue owns current mounting, shaft/thread and retention
work; [#45](https://github.com/Valpatel/gyropup/issues/45) retains electrical/protocol candidate evaluation.
Purchase confirmation does not establish physical fit, mixed-bus timing, full-battery motor compatibility,
regeneration handling, thermal limits or rotating-part acceptance. The old note's no-purchase wording describes
its 2026-10-29 research checkpoint. This inventory does not select the proposed ESC/servo architecture.

## Archive preparation and resumption

At the audit, all three PRs were drafts with no requested reviews, submitted reviews or review threads. Their
head checks were complete: firmware for #28/#30, firmware and site deployment for #46. Branch-filtered Actions
queries showed no unfinished runs for these three branches. Those checks did not qualify the mechanical or
electrical proposals. Historical issue checkpoints say the old body/rig jobs finished and CAN research had no
running job; live remote processes were not re-inspected by this documentation task.

Before retiring a source branch, the coordinator must publish and verify a durable archival ref at its exact
tip above, record that ref in the tracking issue, and recheck that no newer commits or active ownership would
be lost. A raw SHA in a document or a local reflog alone is not the retention mechanism. Closing a draft should
say **historical, unmerged and unqualified**, link this inventory and its acceptance issues, and avoid closing
those issues as completed. The inventory's original branch names are recovery context, not an instruction to
restore them as active development branches.

Local owner worktrees remain preserved. Their clean status and matching upstream tips at audit time do not
authorize their removal or prove that no external environment imports them. Future work starts from current
`dev` and selectively re-evaluates relevant historical work through a focused PR. Read
[program #31](https://github.com/Valpatel/gyropup/issues/31) and
[mechanical tracker #61](https://github.com/Valpatel/gyropup/issues/61) for current priorities and ownership.
