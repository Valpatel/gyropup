# A new layer in a screw stack needs the receiving pilot re-checked

On 2026-11-01 the insert-joint inventory (`research/insert-joints/`, issue #137) found two TM joints whose screws
bottom in blind insert pilots. No check had covered either one.

## Evidence

The turret's mount contract, `exports/turret/mount.json`, gives `M5 x 16, 4 off` and asks the head for
`bolt_hole_depth_min_mm: 12.0`. D66 added the compute plinth, so the stack changed in two places:

- **The riser.** The plinth's tray now sits on the body's riser. Its heads sit on a 5.5 mm counterbore floor, 4.5 mm
  above the TM face, so each tip ends 11.5 mm down. `cad/body_frame.py` `riser()` cuts the pilot
  `cyl_z(3.2, H - 9.5, H + 1.0)`, 9.5 deep. The screw bottoms 2.0 mm early.
- **The plinth's columns.** The pan base now sits on the plinth's PETG columns. Through its 5 mm foot, each tip ends
  11 mm down. `compute_shell()` cuts `insert_hole(x, y, 0.0, 'M5')` (INSERT_DEPTH 8). The screw bottoms 3.0 mm early.

`cadagent.mechanical.fasteners.blind_insert_stack(head_seat=4.5, screw_length=16, insert_top=0, insert_length=7.9,
hole_bottom=-9.5)` returns `tip_clearance_mm: -2.0`. The body's joint check (`exports/body/integrity.json`) does not
include the TM. The turret's fastener gate covers only the hopper and laser screws. Each side passed its own checks.

## Cause and corrective rule

The contract's screw length moved to a new layer, but the receiving pilots kept the old depth. When a part goes
into a screw stack (a plinth, a spacer, a washer, a thicker foot), re-run the stack against the receiving pilot on
both sides of the interface. A screw that bottoms in a blind insert pilot jacks the insert out instead of clamping
(Spirol). Re-check the dowel lengths too: the tray's 8 mm dowel holes leave a 16 mm pin needing 8.5 mm in the riser,
which cuts 8.

## Limits

This is found from the CAD, not from an assembled turret. The fix (deeper pilots or M5 x 12) is a `cad/` change and
needs the carrier receipts regenerated on the CAD host. See `research/insert-joints/joints.md`.
