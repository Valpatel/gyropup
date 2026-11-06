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

Nine source-guard controls passed. The generator genuinely rendered seven steps and five drawings, and its
subsequent no-render replay accepted the actual visual receipt. The job exited 0 after 116 seconds. Outputs were
fetched with `fleet-run fetch 156 <destination> --outputs-only`; no visual metadata was backfilled onto old pixels.
The retained-record integration check brings the local guard suite to ten passing tests.

## Fresh visuals and the preserved print snapshot

Only the fresh step/drawing PNGs, drawing PDF and ordered visual-input metadata are adopted from that run.
The renderer builds its scene from unchanged CAD functions, independently of the re-exported print meshes.
The hip-module sheet and motor step were inspected for labels, source stamp and the existing unqualified status.

The normal generator also re-exported foot/drill-template mesh bytes while retaining their old slice records.
Those new bytes did **not** match the recorded SHA-256 identities, even though bounds, enclosed volumes and
unique vertices at 0.0001 mm matched. That is a generation/provenance limitation, not proof of a new slice.
The attempted full regenerated package is **not** published as a coherent print package.

All original print geometry, all 30 mesh/slice relationships, derating data and the old ZIP are preserved
byte-for-byte. The ZIP remains an earlier snapshot, with its original text, pictures and source stamps; its
historical status is stated beside the download. The repository’s retained PLA record stays at 2700 MPa modulus,
25 MPa strength and a 12 N·m cap. The unrelated newer material-row description from the rendering environment is
not adopted. No new print package, material qualification or physical test is claimed.

The existing print-provenance harness now checks every actual motor-day slice record against its source bytes.
It rejects the two stale identities from the initially collected full export and passes the preserved snapshot.
Future full package regeneration must reslice changed source bytes or preserve the validated source snapshot;
the normal producer does not yet make this transaction atomic. These checks do not establish physical fit,
printing, load capacity or safe powered operation.
