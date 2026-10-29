# Output-adapter ownership (work in progress)

Issue #64, under mechanical integration #61, corrects the current full-robot presentation's four output adapters. `cad/fivebar.py:assembly` places each adapter in its upper-link frame, and `screw_groups` puts its output screws in that same frame. The committed interim body rig and the current `sim/robot_v2.py:export_rig` instead classify adapters as fixed body meshes. The public renderer follows that classification.

The archived rig is a recorded physics snapshot. Its meshes, mass and trajectory provenance must remain available unchanged. A current presentation correction must record its source hashes and datums separately and must not imply that the later body, hardware fit, mass, FEA or robot dynamics were regenerated.

Implementation and validation are pending. The intended regression compares actual rendered STL vertices in the body coordinate frame against independent CAD datums, includes both mirrored sides and stationary motor housings, and rejects a seeded wrong parent that has the correct home pose. Future CAD exports must put the adapter and output-screw meshes in the upper-link group. No hardware dimensions change in this work.
