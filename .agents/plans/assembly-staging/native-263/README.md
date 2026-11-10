# Original CAD and displayed meshes agree in their world frames

Job 263 checked all 233 original 261 BREP instances against the actual captured STL
and model bounds, using exact reviewed product 6acc8fda/core 5c29. The distinct
frame-only report has pass=true/status=warn: path and support checks remain
explicitly unperformed. Independent review reimported every native BREP and
reparsed 360367 STL triangles; native/report bounds differed by at most 2.85e-14mm.

The [checkpoint](checkpoint.json) links source/action and post-action reviews,
execution identities and all file seals. The [frame report](frame-report.json),
[phase](frame-phase.json), [progress](frame-progress.jsonl) and [member manifest](frame-members.json)
are exact captured bytes. The public [execution receipt](execution.json) replaces
private argv paths with roles while retaining their hashes and the raw terminal
receipt hash. All eight preservation guards passed; all six child groups ended.

The [author audit](artifact-audit.json) checked 475 archived and actual files.
The [independent audit](independent-audit.json) additionally imported 233 native
BREPs. Its [portable source](independent-audit.py) changes only private path
literals to CLI arguments; its original receipt is unchanged. Reproduction:

```text
fleet-run fetch 263 <fresh-owned-directory> --outputs-only --max-mb 256
python3 -B audit.py <fetched-job-directory> <product-checkout>
<native-python> -B independent-audit.py <fetched-job-directory> <product-checkout> [new-receipt]
```

Use the existing compatible native environment; install nothing for this audit.
All 941 progress records have contiguous source-bound context and per-instance
coverage, with 941 flushed/file-fsync-acknowledged records at complete close.
Those file operations do not certify power-loss durability. Maximum CAD/STL
bound difference is 0.3551178mm at both wheel tyres within the unchanged 0.5mm
limit; mesh/model error is 0. The binding equals accepted pure 261 exactly.

There were zero pair kernel queries and zero path operations. This is
producer-declared correspondence plus actual bounds evidence, not equivalent
solid, insertion, gravity/support, physical assembly or manufacturing proof.
The next separately reviewed slice must inspect changed arrivals and explicit
old-order/wrong-side controls. Keep the [failed 262 preparation](../native-262/README.md)
and all original 261 bytes/source identities unchanged.
