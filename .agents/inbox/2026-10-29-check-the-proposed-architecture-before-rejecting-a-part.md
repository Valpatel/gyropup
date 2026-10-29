# Check the proposed architecture before rejecting a part

On 2026-10-29, the initial MAD ESC research framed its 16 V minimum as a conflict with the existing flywheel rail. The user intended direct main-battery power and explicitly allowed different CAN command protocols on the same physical bus.

Evidence from the initial tracking body, read before correction (one output line excerpted):

```text
$ gh issue view 45 --json body --jq '.body'
- [x] Identified the 16 V minimum ESC input conflict with the published 12 V rail and the newer turret/program trimmed 10.8–11.9 V rail.
```

The manufacturer specifies 16–64 V input; the project's main battery is 30–41 V. The initial comparison held the old power architecture fixed without checking the intended alternative. Protocol-name matching made the same category mistake at the communications layer.

Corrective rule: evaluate the proposed architecture first, and preserve the intent of earlier constraints for explicit review. Separate power, CAN transport and application messages. The corrected assessment is in [CAN hardware selection](../domains/can-hardware-selection.md). No hardware change or bench result follows from a plausible paper comparison.
