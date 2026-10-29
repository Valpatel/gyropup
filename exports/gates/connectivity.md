# Gate: connectivity

**FAIL** · 139 checks: 136 pass, 1 warn, 2 fail · a check of the CAD model against its declarations; physical fit not verified

Geometry: `exports/dossier-geometry.json` digest `edd7861908ab4280`, 110 shapes

## Findings

| Check | Status | Parts | Message |
|---|---|---|---|
| `connect:body:flywheel_m` | fail | flywheel_m, flywheel_tyre_m | 1 floating island(s): [flywheel_m, flywheel_tyre_m] (nearest grounded part flywheel_motor_r at 0.000 mm; touches flywheel_motor_r only across bodies; joint I-wheel-r does not hold flywheel_m (3.517 mm from cartridge_body)) |
| `joint:I-wheel-r` | fail | cartridge_body, flywheel_m | revolute joint I-wheel-r: flywheel_m is 3.517 mm from cartridge_body, needs <= 1.5 mm (declared clearance) |
| `contact:index_magnet\|pan_clamp` | warn | index_magnet, pan_clamp | index_magnet and pan_clamp are in contact (touching) but no interface, joint, fastener, contains or intended overlap declares it |

## Exclusions (declared)

- ball#0: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#1: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#10: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#11: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#12: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#13: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#14: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#15: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#16: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#17: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#18: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#19: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#2: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#20: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#21: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#22: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#23: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#24: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#25: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#26: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#27: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#28: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#29: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#3: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#4: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#5: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#6: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#7: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#8: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- ball#9: a loose round of the physics-settled hopper load (sim/turret_feed.py --pile); held by the hopper's cavity
- dt_plug: the robot harness's plug, a separate cable plugged into the receptacle (absent on the stand)

## Not checked

- {'pair': ['pan_ring', 'pan_pinion'], 'reason': 'skipped by the relation table (skip_pairs); never measured'}
- {'interface': 'I-mesh', 'reason': 'every pair of its parties is in ignore_pairs'}
- {'interface': 'I-horn', 'kind': 'other', 'reason': 'not geometric'}
- {'interface': 'I-dial-horn', 'kind': 'other', 'reason': 'not geometric'}
- {'interface': 'I-hub-l', 'kind': 'other', 'reason': 'not geometric'}
- {'interface': 'I-hub-r', 'kind': 'other', 'reason': 'not geometric'}
- {'interface': 'I-slip-ring', 'kind': 'electrical', 'reason': 'not geometric'}

## Assumptions

- contact is the relation table's: no shared volume and a gap within touch_mm, or shared volume; a contact in the model does not prove that printed parts meet, stay put or carry load
- a joint's moving part seeds a moving body, which grows across fixed joints and fastener clamps/into declarations; every other part belongs to the static frame and must reach a grounded part through contacts, fasteners and fixed joints inside its own group; contact across groups, or with an allowed-free part, holds nothing up
- a joint holds only when its parts are measured within the declared interface clearance, else within max_joint_gap_mm for a moving joint and in contact for a fixed joint
- an item inside its container's declared cavity (contains) is held by the container whether or not it touches
- a fastener with a modelled solid connects only what that solid touches; one without a solid connects what it clamps to what it threads into only when its axis, over its length, is measured to reach both
- an interface between sections, or between parts with several instances, is realised by any one contact between their instances

## Limits

- `touch_mm`: 0.05
- `near_mm`: 1.0
- `overlap_mm3`: 0.001
- `max_joint_gap_mm`: 1.0
- `strict_interfaces`: false
- `nearest_candidates`: 3
