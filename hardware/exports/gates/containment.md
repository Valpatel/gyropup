# Gate: containment

**WARN** · 65 checks: 64 pass, 1 warn, 0 fail · a check of the CAD model against its declarations; physical fit not verified

Geometry: `exports/dossier-geometry.json` digest `edd7861908ab4280`, 110 shapes

## Findings

| Check | Status | Parts | Message |
|---|---|---|---|
| `contains:hopper_cavity:ball:support` | warn | ball#14, ball#20 | 2 of 30 ball instance(s) rest on nothing within 0.5 mm along [0.0, 0.0, -1.0]: ball#14, ball#20 |

## Exclusions (declared)

- laser_foot_screws, laser_inserts: thread envelope: the M3 screw's nominal Ø3 in the insert's Ø2.5 minor diameter, by design
- hopper_screws, hopper_inserts: thread envelope: the M3 screw's nominal Ø3 in the insert's Ø2.5 minor diameter, by design
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

## Assumptions

- each content instance is tested against the registered cavity solid with non-destructive OCCT booleans (common and cut volumes, cross-checked) against the registered cavity solid
- inside means no more than contain_mm3 of the instance is outside the cavity; touching the cavity boundary is inside
- the wall check tests each instance against the container's solid: touching is allowed, shared volume above overlap_mm3 fails
- the point furthest outside is the furthest of the vertices of a tessellation of the escaped piece, climbed to the piece's extreme point along the outward direction; its depth is a lower bound
- an instance touching the cavity boundary is re-checked by classifying points on its surface (tessellation nodes at probe_deflection_mm and a UV grid of about probe_spacing_mm per face) against the cavity, because the boolean can miss a shallow near-tangent crossing; a crossing whose footprint falls between samples, or no deeper than touch_mm, can still be missed
- the cavity-fit check requires the cavity to share no volume with the container and to lie within the box of the container and its closed_by parts; a cavity that stays inside that box but outside the material (beside an L-shaped container) is not caught
- support is a static contact test (the instance moved support_mm along `down` pushes further out of the cavity or into a supported instance than before the move, by boolean volume or, for a pair with no shared volume within support_mm, by the surface probe), not a settling or stability simulation; only the cavity and other instances count as support
- mesh-only items are sample-only: Monte Carlo volume estimates against the exact solids, with no interpenetration or support check
- the model is checked, not the print: no tolerance stack, shrink or deflection

## Limits

- `touch_mm`: 0.2
- `contain_mm3`: 1.0
- `overlap_mm3`: 1.0
- `volume_check_mm3`: 0.2
- `support`: "report"
- `down`: [0.0, 0.0, -1.0]
- `support_mm`: 0.5
- `witness_deflection_mm`: 0.05
- `witness_max_points`: 600
- `contact_probe`: false
- `probe_deflection_mm`: 0.01
- `probe_points`: 20000
- `probe_spacing_mm`: 0.5
- `mesh_samples`: 4000
- `seed`: 0
- `poses`: {}
