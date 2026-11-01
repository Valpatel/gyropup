# A gate read at one mesh needs its mesher named and a finer check

On 2026-10-31, issue #29 ran the same commit and the same `--mesh 4` on two compute hosts. One was x86-64 with the PyPI gmsh wheel, the other aarch64 with the conda-forge gmsh. The two builds made different meshes of the same hip frame (151,459 against 151,136 tetrahedra). Today's hip frame then read E1 SF 1.59 on one host and 1.50 on the other. The recorded `exports/leg/fea/summary.json` came from the aarch64 host, which reproduces the recorded front link exactly.

Coarse peaks also misled in two ways:

- **The front link.** With the 6301's Ø51 knee boss, it read R1 1.53 against 1.69 at 4 mm. That peak sat in the apex ring's 6 mm wall, which is one or two elements thick. At 3.5 and 3 mm the peak moves to the knee boss, and the new link is the stronger one: 2.04 / 1.96 against 1.82 / 1.87.
- **The hip frame's sweep leader** (root fillet 7.5 mm). It read E1 2.08 at 4 mm and 1.81 at 3 mm. Its peak is at a sharp corner: the tip of a knee-out ear's backing block, where the block ends on the web's motor face.

Two fixes there failed:

- Running the block on to the ear's edge left a knife edge, and E1 fell to 1.33.
- A revolved fillet round the block's boss side made slivers that the mesher refused ("PLC Error: A segment and a facet intersect").

Corrective rule:

- Name the host and the mesher build in every FEA record.
- Compare a before and an after only on one host and one mesh.
- Before calling a gate met, rerun the winner at about 0.75 × the mesh size.
- If a peak moves by more than a few percent, or sits in a wall one or two elements thick, the value is not a result. Look at where it sits before changing the design, not only at the number.
- Ending a stiff block on a plate in an open wedge or a square step is the same mistake as the gusset's sharp tip (`GUSSET_RUNOUT`). Run it out or fillet its whole foot.

Limits: at 4 mm, mesh dependence of 10–20 % is normal at re-entrant corners in this frame. A gate value that passes there but not at 3 mm should be reported as both.
