# Check a screw stack on both sides of an interface, and again when a layer is added

On 2026-11-01 the insert-joint inventory (`research/insert-joints/`, issue #137) found two TM joints whose screws
bottom in blind insert pilots. It also found that the turret's published centre of mass uses the wrong datum. No
existing check had covered any of the three.

## Evidence

The turret's mount contract, `exports/turret/mount.json`, gives `M5 x 16, 4 off` and asks the head for
`bolt_hole_depth_min_mm: 12.0`.

- **The riser.** `cad/body_frame.py` `riser()` cut its TM pilots 9.5 deep (139db9f). The contract was written later
  (0f5721d) and already asked for 12. The riser was never re-checked against it. Before D66 the screw came through the
  pan base's 5 mm foot, so its tip ended 11 mm down: 1.5 mm past the pilot's floor. D66 (2c31210) put the plinth's
  tray on the riser instead. Its heads sit on a 5.5 mm counterbore floor 4.5 mm above the TM face, so each tip now ends
  11.5 mm down and the screw bottoms 2.0 mm early.
- **The plinth's columns.** D66's new `compute_shell()` takes the pan base's same M5 x 16 in
  `insert_hole(x, y, 0.0, 'M5')`, at the generic INSERT_DEPTH of 8. Through the 5 mm foot each tip ends 11 mm down, so
  the screw bottoms 3.0 mm early.
- **The turret's centre.** `mount.json` says frame T's origin is "in the TM face", but since D66 the turret reaches
  86 mm below that origin (`envelope.lowest_z_mm`). The origin is the pan base's foot. The published `com_mm` z of
  49.2 is therefore 135.2 mm above the real TM face. The turret's own TM-bolt hand check uses 49.2 (233 N a bolt;
  measured from the face it is 637 N). The body reads max(49.2, 100), so its riser and deck studies use 100 mm.

`cadagent.mechanical.fasteners.blind_insert_stack(head_seat=4.5, screw_length=16, insert_top=0, insert_length=7.9,
hole_bottom=-9.5)` returns `tip_clearance_mm: -2.0`. The body's joint check (`exports/body/integrity.json`) does not
include the TM. The turret's fastener gate covers only the hopper and laser screws. Each side passed its own checks.

## Cause and corrective rule

The contract stated the screw, the depth it needs and the frame, but no check read both sides of it. When a contract
names a screw and a receiving depth, check the receiving part against it, whichever was written first. When a part
goes into a screw stack (a plinth, a spacer, a washer, a thicker foot), re-run the stack against the receiving pilot on
both sides of the interface. Re-check the contract's datum too: a layer added under the old origin moves the TM face,
and every moment taken about it.

A screw that bottoms in a blind insert pilot jacks the insert out instead of clamping (Spirol). Re-check the dowels
the same way: the tray's 8 mm dowel holes leave a 16 mm pin needing 8.5 mm in the riser, which cuts 8.

## Limits

These findings come from the CAD, not from an assembled turret. The fixes (deeper pilots or M5 x 12, the contract's
datum) are `cad/` changes and need the carrier receipts regenerated on the CAD host. See
`research/insert-joints/joints.md`.
