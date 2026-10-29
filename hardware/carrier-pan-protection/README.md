# PAN supply cutoff — circuit candidate

**Unselected and unqualified. Do not fabricate or energize this checkpoint.**

Tracking [issue83](https://github.com/Valpatel/gyropup/issues/83), following the [reviewed protection requirements](../../research/protection/carrier-input-protection.md). This directory will contain an editable U2-only active cutoff and 60 V converter circuit candidate, manufacturer pin mapping, rendered schematic, BOM and fault review. It changes no installed hardware, existing catalog selection or carrier geometry.

Interfaces are coordinated against carrier PR67 head `8b86e7f`: C2-P carries the whole fused head BUS, while this candidate intercepts only the PAN converter feed. C2-S pin3 is SAFETY_A from 12V_PAN through F4; pin4 is SAFETY_B returning to NE555 pins8/4. PAN servo connector cavity numbering remains unverified. No space is allocated for an extra protection PCB; the existing U2 reservation is 25.4×25.4×9.5 mm on a 50.8×30 mm carrier board. Mounting is not frozen.

Pending: native schematic, netlist, candidate BOM, pin validation, fault-state review and independent review. Source transients, reverse polarity beyond −40 V, output regeneration, thermal/SOA and safe recovery are unresolved release gates.
