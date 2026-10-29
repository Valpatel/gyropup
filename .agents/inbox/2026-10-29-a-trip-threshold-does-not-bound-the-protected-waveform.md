# A trip threshold does not bound the protected waveform

2026-10-29, issue81 / PR82. The carrier's TVS minimum breakdown had been cited below a regulator's limit. Maximum breakdown was already above that limit. Replacing the TVS claim with a nominal active cutoff did not automatically solve the protection requirement: comparator overdrive, hysteresis and gate delay materially changed the usable window.

## Receipt

```text
$ python research/protection/calculate_carrier_protection.py --check
PASS: source bindings and deterministic calculation receipt; no build qualification
$ python research/protection/test_carrier_protection.py
Ran 7 tests
OK
```

The committed calculation binds integration6133c18 and the manufacturer revisions in its inputs. A 430 kΩ/4.99 kΩ independent divider, 0.1% resistors, 492.5–507.5 mV threshold and ±10 nA leakage gives a 42.843–44.332 V rising cutoff. Including 20–32 mV hysteresis gives a 40.059–42.585 V recovery range: recovery at a healthy42 V is not guaranteed. A 464 kΩ top resistor recovers above42 V, but the worst input needed to reach the specified50 mV comparator overdrive is52.506 V, above the existing50 V converter. The2 µs comparator delay was specified at12 V input; the separate gate-delay condition uses2.2 nF. Neither was silently extended to the proposed board at42 V.

## Why the obvious check missed it

Comparing only nominal trip voltage to a device maximum discards the conditions that make the timing number valid. Considering only U2 also hides that C2 carries the entire head branch, and that protecting the converter input says nothing about servo output regeneration.

## Corrective rule and limits

Enumerate tolerance/hysteresis corners; retain timing conditions and trace the actual protected nodes. Check the waveform at the device terminals, including parasitic overshoot, against a declared envelope. Unknown dynamic peaks remain unknown. The calculator checks arithmetic and source identity, not a completed circuit or measured hardware. No parts were selected or energized. Durable guidance: [electrical protection](../domains/electrical-protection.md).
