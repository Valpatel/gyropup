# A receipt validator must require the complete evidence set

On 2026-10-29 UTC, independent PR86 review reproduced a false acceptance in frozen source `306bfb0`. The actual failed support-run receipt was modified only by removing its failed `carrier:installed_neighbours` record and emptying `public_artifact_sha256`; its `bounded_geometry_checks_pass` still said false. `validate_receipt()` nevertheless returned true. See [the verified review finding](https://github.com/Valpatel/gyropup/pull/86#discussion_r4413341160).

The relevant reproduction in the frozen checkout was:

```python
receipt['checks'] = [c for c in receipt['checks'] if c['id'] != 'carrier:installed_neighbours']
receipt['public_artifact_sha256'] = {}
assert receipt['bounded_geometry_checks_pass'] is False
validate_receipt(receipt)  # old result: True
```

Cause: validating only the records present in a report made missing evidence optional. Iterating `get('public_artifact_sha256', {})` silently skipped missing exports, and checking that the remaining result rows passed did not establish complete coverage or a true summary.

The correction requires the exact three published artifact names, all 58 expected check identities exactly once, a summary that is literally true, and every result that is literally true. Actual files are hashed after membership validation. `tools/test-carrier-connector-support.py` includes missing/empty/partial binding, changed-file, deleted-clearance, duplicate-check and false-summary negatives. The frozen `120d531` compute run and generated checkpoint `1efa1c0` pass these guards; independent recheck is tracked on the PR.

Corrective rule: define the required evidence inventory independently of whichever rows a receipt happens to contain. Fail closed on missing, duplicate or unexpected outputs/checks. Preserve unsuccessful runs rather than deleting their failing rows. Full input hashes alone do not prove result completeness.

Limits: these guards check source/output identity and recorded coverage. They do not rerun CAD, establish the truth of fabricated numerical evidence, or qualify physical fit, strength, flexible clips or a complete harness. The support's separate readiness fields remain false.

## Terminal inventories need membership checks before counts

On 2026-10-29, independent early PR97 review reproduced the same failure class in `hardware/carrier-packaging/check.py` at `e93272e`. The current terminal map was correct, but each of these separate mutations still returned `{'external_positions': 21, 'all_terminals_allocated': False}`:

- Delete the CAN_H continuous bypass.
- Change servo datasheet pin2 from `SERVO_12V_AFTER_F1` to raw `BUS_HEAD_FUSED`.
- Drop `PROTECTION.GND` from `J_RETURN`.
- Drop `H.F4.1` from `J_12V`.
- Duplicate the `C3.module` interface.

The author independently repeated all five against `git show e93272e:hardware/carrier-packaging/check.py`. Counting pins after converting interface rows to a dictionary hid duplicates; checking only selected BUS pins and shunt ends left other required connections optional. Hashing the inventory did not establish the terminal map's semantics.

The correction independently states the exact unique interface IDs and pin/net maps, all legacy and adjacent protection pin maps, three external protection ports, three bypasses and three junctions with every member. It rejects duplicates before dictionary conversion and verifies endpoint existence and net agreement. Physical position totals are derived only after this membership check. The existing harness now includes every-interface deletion/duplication/renaming, every-pin deletion/net substitution, every-bypass deletion and missing endpoint, every-junction member deletion/duplication, legacy/protection mutations and false allocation controls.

Reproduce with `python hardware/carrier-packaging/inventory.py`, `python hardware/carrier-packaging/check.py` and `python -m unittest discover -s hardware/carrier-packaging -p 'test_*.py'`: 16 tests pass, while all physical allocation and qualification flags remain false. This is a logical candidate contract, not a new native schematic, actual wire-end allocation, solder instruction or electrical/physical qualification.
