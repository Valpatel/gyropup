# Two-assembly packaging proposal — not a PCB layout

This bounded proposal assigns the47 electronic inventory entries to two carrier-retained assemblies. It does not generate native circuitry, PCB placement or CAD. The [machine-readable proposal](allocation-proposal.json) binds the inventory, terminal contract and mechanical source; all physical readiness flags remain false.

| Assembly | Paper assignment | Finite outline being screened | Unresolved physical work |
|---|---|---|---|
| Control and termination | All nine L.* parts; retain the existing functional circuit and explicitly allocate adjacent F4/D8/D14 obligations | Replacement PCB within the existing50.8×30 mm outline;1.6 mm thickness is a proposal | Every actual component/formed lead, BUS/return junction, wire termination and tool route; the old U2 rectangle and pad-strip box are not automatically free space. |
| PAN power | All28 P.* and ten I.* parts, including Pololu5577 | Candidate40×36×1.6 mm PCB at X6..46,Y55..91,Z24.4..26 within the mechanical44×40×18 mm trial region | Actual placement, routing, retention, insulation and heat path. The module cannot float above the board without selected mounting and electrical interconnects. |

The trial region remains held on the proposed bumper/support service redesign. It is not established available volume. The retained legacy board also needs complete placement: its NE555/R3/fuse reservations are not complete maximum envelopes. Replacing perfboard with a custom board is a proposal requiring review, not a silent catalog or manufacturing change.

## Real wire-end accounting

Three continuous CAN/TTL bypasses consume six of the21 external connector positions without landing on either PCB. The remaining15 positions require actual control-board terminations. A proposed four-wire power interconnect adds four more: BUS_IN/GND_IN and12V_OUT/GND_OUT, giving **19 control-board wire-pad candidates and four power-board wire-pad candidates**. Each candidate is individually listed with its endpoint and net; all positions, hole/land sizes and strain-relief assignments remain null.

The two ground pads are distinct physical connections to the same GND net. They do not add an isolated rail, change the three logical protection ports, or prove quiet/star return behavior. Raw C3 BUS remains outside the protected PAN path. Whole-head10 A BUS/return junction capacity, copper and fault heating need explicit engineering; a nominal perfboard trace or unspecified splice is insufficient. No new connector family or servo lead qualification is assumed.

## Conditional height checks

The candidate power PCB top is Z26. An upright Panasonic capacitor's12.5 mm maximum body plus its2 mm required vent space reaches Z40.5, leaving **only0.5 mm** under the trial Z41 ceiling before any mounting gap, tolerances or insulation. Those missing allowances are null, not zero. This screen cannot pass the assembled stack.

For a conditional module stack, placing the Pololu PCB underside at Z30 gives a nominal top of Z37.67 after its1.57 mm PCB and6.1 mm upper profile. Its1.4 mm lower profile reaches Z28.6. A1.8 mm part on the base PCB would nominally reach Z27.8, leaving0.8 mm between them. Profile tolerances, solder, insulation, mounting, actual module pad access and combined heat remain unresolved. The tall FET and capacitor cannot be assumed to fit under that screen. No XY overlap or real placement is accepted here.

The existing94459A140 insert requires6.5 mm minimum surrounding material in its catalog record. It cannot silently be used as a thin under-board support while preserving this height budget. Other mounting hardware or an altered envelope requires an explicit source-backed proposal and mechanical review. A40×40 thermal reference board does not establish these outlines or an enclosure temperature.

## Review gates before the next design iteration

Complete actual component/terminal placement and all formed lead stacks; choose and model real mounting/strain relief; validate the full C2-release, bumper-sector, C3-parking and carrier-removal sequence; and establish current/thermal/insulation boundaries. The capacitor differential waveform, open-source transient/charged-output limits, startup behavior and output regeneration remain electrical qualification gates. The split assemblies preserve the existing source and12 V servo contract. No purchases or energization are authorized by this proposal.

Reproduce with `python hardware/carrier-packaging/allocation.py`, followed by the shared `check.py` and unittest commands. The generator assigns ownership and wire-end obligations only; it does not place or route any component.
