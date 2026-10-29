# A valid object is not valid kinematic data

On 2026-10-29 UTC, independent review deleted only `fivebar.l1_mm` from the real v2 manifest and found that the builder still returned a robot with22 non-finite world transforms. The first loading guard checked that `fivebar` was an object, which admitted missing numeric inputs to link positions and joint rotations.

After validating the consumed dimensions, reference angles, height range and mount vectors before mesh requests, the same actual-builder probe was run:

```sh
node --no-warnings --experimental-loader /tmp/gyropup-pr51-node-loader.mjs /tmp/gyropup-pr51-schema-probe.mjs
```

The valid manifest returned with `nonfinite:0` and `heightM:0.91065`. The deleted-link variant returned:

```text
{"kind":"missing-l1-mm","returned":false,"error":"Robot manifest: the downloaded data has an unexpected format."}
```

The scratch probe is session evidence, not a repository dependency. The committed browser harness `tools/test-loading-portal.mjs` now exercises eight malformed kinematic fields through native retry, checks that no STL request or conversation mount occurs for them, and requires finite actual world matrices after the valid response.

Rule: availability guards must validate the numeric inputs actually consumed by rendering and motion. A successful JSON parse and object type check cannot establish a usable model. Keep source datums and geometry unchanged while rejecting invalid input; do not invent replacement dimensions to make the scene appear ready.

Limits: finite transforms are necessary, not sufficient, for correct kinematics. The independent current-model motion/landmark suite remains required and no new mechanical validity claim follows from this schema check.
