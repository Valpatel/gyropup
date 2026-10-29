# Supplier family ratings do not qualify an exact part

2026-10-29, carrier purchasing issue #79 / PR #80. The initial audit concluded that the selected Littelfuse 0FHM0001ZXJ was definitively limited to 32 V on a documented 30–42 V BUS. **That conclusion was too strong.** Later manufacturer evidence explicitly included that bare part in a 58 V family. The correct result is conflicting revision evidence and an unresolved current qualification basis, not a proven physical 32 V limit.

## Receipt

The [dated audit](../../research/supply/turret-carrier-2026-10-29.md) retains the exact supplier/PDF URLs and source lines:

- Newark exact 0FHM0001ZXJ: 32 VDC. Littelfuse 062923-B: family maximum 32 V, bare part absent from its table.
- Littelfuse 113020: family maximum 58 V and bare 0FHM0001ZXJ present. Littelfuse 020425: several suffixed variants explicitly 58 V, bare part absent, with remaining 32 V headings.
- Frozen `faed5f510586ab282db4a27f6453165ac56f70d2:docs/turret-wiring.md:139,457–458` puts the holder before regulation on the robot BUS. The separate stand operates at a lower voltage.
- TE's selected contact is 16–20 AWG against documented 24 AWG signals. The selected N-seal accepts 2.23–3.68 mm insulation against the selected wire's 1.4 mm OD. A candidate 24 AWG contact alone cannot fix that second mismatch.

The source-coverage checker is deliberately narrower than supplier qualification:

```text
$ python research/supply/validate_carrier_audit.py
PASS: 10 frozen source hashes, 29 unique catalog keys, 13 circuit designators, 16 mounting instances, wire arithmetic; no build qualification
```

## Why the first conclusion failed

An exact distributor field plus a newer family sheet looked sufficient, but a family-level revision did not identify every exact order code consistently. Likewise, a listed crimp gauge could obscure an incompatible wire seal. Catalog descriptions and generic packaging fields hid the distinctions between a retail blank and the pieces fabricated from it.

## Corrective rule and limits

Bind each engineering assertion to an exact part and accepted document revision; preserve conflicts rather than choosing the convenient number. Record stock, replenishment, access failure and qualification separately. Keep candidates explicitly unselected. See [supplier evidence](../domains/supplier-evidence.md) for the durable rule.

The audit adds source-hash, designator, duplicate-key and unknown-stock checks. It cannot automatically resolve conflicting electrical ratings or qualify physical assemblies. No purchases, substitutions or catalog changes were made; the carrier still needs its electrical and serviceability work.
