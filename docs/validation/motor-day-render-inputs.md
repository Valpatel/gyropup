# Motor-day picture reuse inputs

Issue [#198](https://github.com/Valpatel/gyropup/issues/198) concerned stale exploded pictures when `--no-render`
accepted changed lift offsets or camera vectors. The receipt now binds each step’s parts, **ordered** lift-prefix
pairs and camera. Order matters because the renderer picks the first matching prefix. Legacy parts-only receipts
require a genuine render. Titles and instructions remain editable under the existing prose-only reuse policy,
even though their old text can remain in PNG captions until the next render.

On 2026-11-05, **fleet job 156 on cpu-b** ran source `8ddcb4fe0e9d1c5a097356be013e6c79495409a4` with released
cad-agent v0.20.0 (`3a4ec137a2a7cf52fa6072b5bc81b7e320d49701`):

```sh
python tools/test-motor-day-render-inputs.py
python tools/motor_day.py
python tools/motor_day.py --no-render
```

All nine source-guard controls passed. The normal generator rendered seven steps and five drawings, rebuilt the
PDF/package, and the subsequent no-render replay accepted its actual receipt. The job exited 0 after 116 seconds.
Outputs were fetched with `fleet-run fetch 156 <destination> --outputs-only`; no metadata was backfilled onto old pixels.
The final retained-record integration check brings the local suite to ten passing tests.

The toolkit’s PLA row now reports the sourced Z modulus of **2060 MPa**, replacing 2700 MPa, and a fuller material
note. Its strength remains 25 MPa, the derating verdicts remain unchanged, and the generated day-one cap remains
**12 N·m**. New foot/drill-template meshes have the same bounds, enclosed volume and unique vertices at 0.0001 mm
as the previous exports, with different triangulation bytes; CAD sources are unchanged. STEP/3MF headers and
rendered source stamps reflect the real regeneration.

The hip-module sheet and motor step were visually inspected for labels, source stamp and the existing unqualified
status. These are documentation-generation checks, not physical fit, printing, loading or motor qualification.
