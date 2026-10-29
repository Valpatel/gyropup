# Cutting allowance does not prove that an electronics module can disconnect

On 2026-10-29, PR #67's removable carrier still inherited a 120 mm C2 route estimate, a tie "at60mm", and a general20% cutting allowance. None identified retained free wire between anchors or a connector release pose. The seated carrier also had only0.25mm side/0.5mm top corridor clearances: those are not viable routes for1.4–2.032mm insulated wires.

The correction adds a rounded solder-side window, physical anchor features, separate power/signal disconnect identities, release directions and retained lengths. Reproduction:

```text
python cad/check_base_board_interfaces.py
python tools/test-base-board-interfaces.py
```

The source-hashed receipt lives at `exports/turret/base-board-service/interfaces/interfaces.json`. It distinguishes green bounded space reservations from `readiness: false`, and rejects a filled window, blocked latch,10mm tail and45mm withdrawal while still mated. Required length is explicitly a straight-exit-plus-endpoint-distance lower bound, sampled through the release travel; it is not a bend-radius or collision-free-harness proof. Missing bend, keeper, solder, C3/servo and physical evidence cannot become green merely because the connector boxes fit.

Corrective rule: identify both anchors, the exact disconnect operation and the length actually retained after trimming. Keep manufacturer straight/free-exit distances separate from bend radii. Include an unremoved-tie/still-connected counterexample. Prefer disconnecting accessible interfaces before withdrawing a drawer where the full travel cannot be supported by the harness. A printed anchor requires actual tie/clamp dimensions and retention evidence too.

A second review caught an outward carrier tie bridge lifting the original flat print face8mm off the bed. Two through-plate tie slots now preserve the original8mm depth; the BREP receipt checks this. Recheck print orientation after adding service hardware, not only after changing the main housing.

Limits: this lesson records an engineering candidate, not a harness, electrical-safety or printed-fit qualification. Connector solids remain labelled authored reservations. No vendor mesh was published.
