# Gate: motion

**WARN** · 3 checks: 2 pass, 1 warn, 0 fail · a check of the CAD model against its declarations; physical fit not verified

Geometry: `exports/dossier-geometry.json` digest `edd7861908ab4280`, 110 shapes

## Findings

| Check | Status | Parts | Message |
|---|---|---|---|
| `combination:I-pan+I-tilt+I-feed+I-flap+I-wheel-l+I-wheel-r+I-pan-drive` | warn | barrel, pan_pinion | I-pan+I-tilt+I-feed+I-flap+I-wheel-l+I-wheel-r and I-pan-drive were sampled one at a time, but the swept boxes of barrel and pan_pinion come within 0 mm: pass combine=[[...]] to sample them together |

## Exclusions (declared)

- circlip_50, pan_ring: the circlip drawn at its groove's d2: 0.05 mm^3
- ring_driver, pan_ring: the driver's three crush ribs in the turntable's bore: 2 mm^3
- slip_ring_rotor, ring_coupling: the tube stretched over the rotor stub: 0.10 mm^3
- bumper_ring, pan_base: the bumper's lug on a base tab: 0.04 mm^3 (curved faces)
- esc_l, cartridge_body: the ESC envelope drawn 0.01 mm into the cage plate: 3.4 mm^3
- esc_r, cartridge_body: the ESC envelope drawn 0.01 mm into the cage plate: 3.4 mm^3
- flywheel, flywheel_motor_l: each hub's bore on its X2216's prop adapter: a 0.008 mm^3 modelling overlap where the envelopes meet (a slip fit)
- flywheel_m, flywheel_motor_r: each hub's bore on its X2216's prop adapter: a 0.008 mm^3 modelling overlap where the envelopes meet (a slip fit)
- slip_ring_rotor, slip_ring: one bought slip ring drawn as two solids: the rotor stub drawn 0.01 mm into the stator's end face (0.28 mm^3)
- ct_thumbscrew, cradle: the captive thumbscrew's collar in the rail: 0.34 mm^3
- laser_screws, laser_mount: the set screws in the ring's tapped holes: the thread envelope (Ø3 in the Ø2.5 tap drill)
- panel_switch, stand_box: the rocker's 24 mm square envelope through its Ø20.2 round cut-out: the envelope, not the part
- panel_pendant, stand_box: the TB3M socket's square envelope through its round cut-out: the envelope, not the part
- dt_plug, dt_receptacle: the mated DT connector: the plug's shell drawn over the receptacle's insert
- ball, cartridge_body: the settle's soft contacts with the dial housing's floor (0.19 mm^3 at most); the hopper's containment checks the balls against the hopper
- ball, dial: the settle's soft contacts with the dial's cone, fins and pockets
- laser_foot_screws, laser_inserts: thread envelope: the M3 screw's nominal Ø3 in the insert's Ø2.5 minor diameter, by design
- hopper_screws, hopper_inserts: thread envelope: the M3 screw's nominal Ø3 in the insert's Ø2.5 minor diameter, by design

## Not checked

- I-pan+I-tilt+I-feed+I-flap+I-wheel-l+I-wheel-r with I-pan-drive: combined poses (sampled separately)

## Assumptions

- joints are sampled at discrete values across their declared ranges, both ends included; the density is reported per joint axis. A collision that starts and ends between two samples, or a feature thinner than the travel per sample, can be missed: this is not a swept-volume check
- a joint's range is measured from the pose the model was built in (0 = as modelled); a joint's axis is in assembly coordinates at that pose, and a child joint's axis is carried by its parent
- what moves with a joint is its moving part's body: the transitive closure over fixed joints and fastener clamps/into (relations.moving_bodies), or the assembly's own body labels
- joints in one chain are sampled on a grid; independent joints one at a time with the others at home (0 clamped into the range) unless combined
- pairs that do not move relative to each other (static against static, parts of one body) are not queried; the relation table and connectivity gate cover them
- exact B-rep relations within the relation tolerances; no tolerance stack, print shrink, deflection or backlash: a clear pose in the model does not prove the printed parts clear

## Limits

- `touch_mm`: 0.05
- `overlap_mm3`: 0.001
- `near_mm`: 1.0
- `volume_check_mm3`: 0.2
- `default_samples`: 12
- `max_step_deg`: null
- `max_step_mm`: null
- `max_poses`: 8000
- `refine_steps`: 8
- `strict_contacts`: false
- `combine`: []
