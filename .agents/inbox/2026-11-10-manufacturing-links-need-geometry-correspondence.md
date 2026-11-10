# A manufacturing file identity does not establish a current-part match

On 2026-11-10, whole-robot guide collection 260 produced current source-bound
assembled meshes. Its initial pure mapping identified retained manufacturing
originals by plan membership, filename and SHA256. That proves which file a
download serves; it does not establish that an older manufacturing export
corresponds to the newly collected CAD instance. The posed assembly STL is also
not a manufacturing replacement.

Evidence, using the ordinary kernel-free test command:

```text
python3 -B -m unittest discover -s tests/site/assembly -p 'test_robot*.py'
Ran 16 tests ... OK
```

`test_named_and_rehashed_stale_original_does_not_enable_current_print` copies
the real plan/original input structure, replaces the named original, and checks
that its newly calculated digest still leaves geometry correspondence pending.
The mapper preserves `kind: print` as a manufacturing category, but explicitly
emits `geometry_match.status: pending`. The product consumer must require an
accepted `matched` correspondence as well as the actual original-file digest
before enabling a current-part Print action. A pending original may remain a
clearly labelled retained download.

There is useful narrower provenance: `hardware/exports/leg/hip_frame.stl` is
byte-identical to the RS04 fit-study STL recorded by its existing strict receipt,
and that receipt validates against current inputs. Its native producer exports
`fivebar.hip_frame()` with the authored print transform. This is a possible
specific correspondence chain, not permission to promote every similarly named
original. The retained study still records eight support failures and no
physical/strength qualification. The first guide mapping keeps all rows pending;
it does not infer readiness from a valid receipt or reproduce CAD for cosmetics.

Preserve the original native collection/archive and distinguish later pure
metadata serialization from the executed native source. Product UI tests own
the actual stale/missing-match Print-action rejection; the data regression alone
does not claim browser acceptance.
