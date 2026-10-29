# A seated electronics model does not prove installation or screwdriver access

On 2026-10-29 the turret base-board audit found a PCB envelope seated without overlap but trapped between the bearing housing, fixed +X support wall and drip skirt. The old dossier fitted the board before lowering the pan base around it; it did not represent a real bench subassembly or the blocked inward screwdriver path.

Dated command/output evidence (project-authored CAD, not measured hardware):

```
2026-10-29, bounded BREP probe against turret/dossier 630a2db
board translated +X 10 mm: pan-base interference 4991.29161 mm3
inward driver, diameter 6 mm and length 60 mm:
  interference at each of four PCB screw axes: about 113.57 mm3
```

The carrier implementation is tracked by issue #66 / PR #67. Its committed reproduction command is `python cad/check_base_board_service.py`; the first run at `056cb3b` recorded installation/removal passes and rejected the original wall, retained bumper and wrong-direction controls before fastener verification. A prototype opening initially left a disconnected 0.25 mm wall strip; checking solid count caught it before implementation.

Cause: static seated geometry, an assembly sequence expressed only in final coordinates, and a broad board envelope were mistaken for an installable assembly. The PCB fasteners had not been represented or checked with a real tool envelope.

Corrective rule: model real PCB holes, fastener seats and package envelopes; build the PCB/carrier on the bench, move every attached member as one rigid module, and check installation and removal against explicit obstacle sets. Record bumper/fastener/harness prerequisites. Include a negative control that retains the obstruction and a valid-single-solid check after opening a pocket. Do not waive a collision to compensate for missing subassembly support.

Limits: CAD path and tool checks do not establish printed tolerances, insert retention, solder clearance, cable service slack, connector access or strength. Manufacturer hardware coverage must be explicit; missing STEP files cannot be replaced by a claim that an authored envelope is manufacturer CAD.
