# A picture refresh can re-export retained slice inputs

On 2026-11-05, fleet job 156 ran the normal motor-day generator for issue #198 with
released cad-agent v0.20.0. It genuinely rendered pictures and accepted the new
visual receipt on replay, but also re-exported the foot and drill-template STL
bytes. The retained slice records still named their old SHA-256 values.

Dated evidence, checked against source 8ddcb4f and the fetched outputs:

```text
foot: baseline slice identity matches True; regenerated identity matches False
drill_template: baseline slice identity matches True; regenerated identity matches False
```

Bounds, enclosed volumes and unique vertex sets matched at 0.0001 mm; tessellation
bytes did not. Equal shape measurements cannot substitute for recorded input identity.
Cause: `motor_day.py` exports parts even in an ordinary picture refresh and checks
slice success flags without transactionally validating the source hashes.

Correction for this scope: retain only genuinely generated visuals and their
ordered-input metadata; restore independent print geometry, all 30 slice-input
relationships, material data and ZIP byte-for-byte. Label the ZIP snapshot beside
its download. The existing `tools/test-print-provenance.py` now checks the actual
motor-day slice/source relationship, including this planted real export drift.

Limits: the normal generator's full-package transaction is not fixed here. Future
full regeneration must preserve source bytes or perform a genuine matching slice;
never rewrite a slice hash to bless new bytes. The original ZIP retains its original
text and images. Picture generation supplies no print, fit or powered qualification.
