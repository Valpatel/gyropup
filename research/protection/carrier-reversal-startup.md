# PAN reversal and startup correction — work in progress

Issue87 continues the reviewed native circuit candidate from PR84 and the responsive portal checkpoint at `4e40a8d`. No circuit selection or geometry change is made by this initial tracking commit.

The legacy topology is explicit in `cad/turret_boards.py:139–141` and `docs/turret-wiring.md:141,241,441–443`: the 10 A head fuse precedes BUS_HEAD_FUSED; D8 (1N5408) and D14 (P6KE51A) are shunts from that BUS to ground, cathodes to BUS. U2 and the slip-ring feed share the node. D8 is not a series reverse blocker. Its surge rating and a fuse's nominal current do not establish coordinated interruption or a safe negative clamp. This candidate takes no credit for either shunt/fuse while bounding its own input.

The [LTC4368 rev C](https://www.analog.com/media/en/technical-documentation/data-sheets/ltc4368.pdf) gives separate limits: VIN −40..100 V, VOUT/SENSE −10..80 V, VIN−VOUT −60..100 V. Consequently a reversed −42 V source with a still-charged +42 V output yields −84 V differential, independently of the VIN violation; the +55 V internal acceptance target would yield −97 V. The manufacturer also calls for additional overshoot mitigation for negative hot insertion beyond −20 V. A static absolute-voltage table alone cannot qualify that event.

The current 10 mΩ sense choice has a startup minimum below the declared 3.25 A screening input at 15 V, before capacitor charging. The revision must distinguish 12 V output load from converter input current, account for converter voltage/efficiency and front-end losses, and include a bounded input-capacitance/inrush envelope or sequencing. Merely increasing a nominal current number is not a startup demonstration.

Next: compare a bounded series-reverse barrier and the differential limits of low-loss controller alternatives; send the circuit decision before committing extra board-area requirements. Then implement an editable candidate, exact part identities, calculations and deliberate failure controls. Preserve 12 V functionality and shared BUS assignments. Positive source transients, 12 V regeneration, waveform/SOA/thermal behavior and PCB/carrier fit remain independent release gates. No purchases or energized tests.

## Candidate B checkpoint

The concrete decision is implemented in [the native candidate](../../hardware/carrier-pan-protection/README.md):200 V series diode plus local negative clamp/decoupling; retained LTC4368 and12 V Pololu converter;10 mΩ||20 mΩ sense;188 nF C0G ramp bank; TPS3760A012 UV supervisor on the converter input driving EN. No connector, carrier or catalog source is modified. [Fault review](../../hardware/carrier-pan-protection/fault-review.md) records exact primary references, charged-output/negative hot-insertion limits and the low-loss candidate rejected on differential voltage.

The conditional calculation passes only with the declared bounds. It exposes a69 mV15 V startup headroom and approximately5.98 W diode-loss screen; those are material unresolved qualification constraints. The exact diode's2.4 A free-air condition is insufficient for this load; its10 A aluminum-board condition is not a perfboard rating. No extra board area or power-junction pad map is allocated. CAN/TTL pass-through and whole-head BUS remain owned by the separate harness work.
