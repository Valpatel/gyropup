# Valid vendor solids can omit functional connector cavities

On 2026-10-29, issue 85 / PR 86 retrieved exact Molex 43020-1200 and 43025-1200 housing CAD from their distributor product CAD links. Both imported as valid single solids, yet their wire-entry ends and internal cavities were simplified. The drawing-derived 24.77 mm mated length produced 82.499925 mm³ overlap in the supplied solids. A reversed-latch control also overlapped; 16 mm separation was clear. The exact 43030-0010 female terminal also imported as a valid single solid, but its uncrimped shape did not qualify a completed harness.

Reproduction, with the existing CAD environment and separate released cad-agent v0.4.2 source checkout:

```sh
PYTHONPATH=/home/scubasonar/Code/cad-agent-carrier-validation/src \
  /home/scubasonar/Code/gyropup/.venv/bin/python tools/check-carrier-connector-inputs.py \
  --out /tmp/carrier-private-input-diagnosis.json
python3 tools/test-carrier-connector-inputs.py
```

The source-controlled diagnosis binds the complete current CAD/config/catalog closure, imported toolkit fingerprint, checker, manifest and private model hashes. The private STEP files and vendor-derived geometry remain unpublished. Missing files, changed variants and paths escaping the vendor cache are negative controls; none may fall back to an authored substitute in a manufacturer check.

Cause: topology validity answers whether the supplied boundary representation is usable, not whether its internal features are complete. A manufacturer-format filename also does not establish a current supplier revision. The official servo resource supplied a similar warning: its root was named SCS215, one solid was invalid, and it lacked detailed mating connectors despite being linked as ST3215.

Corrective rule: inspect the actual mating features, cavity views, pin and wire exits against dimensioned drawings before claiming fit. Preserve contrary geometry evidence. Separate usable external-outline placement from incomplete internal mating, crimp, latch-flexure and service claims. Never heal away an invalid part, cut out an inconvenient vendor overlap, or add a blanket intended-overlap allowance to produce acceptance.

Limits: this finding does not prove the physical Molex parts interfere. It identifies a representation/fit gap requiring more detailed geometry or measured parts. A sampled cavity point does not bound the full omitted region. Wire diameter, bend radius, actual crimp, terminal retention and printed support still need independent evidence.
