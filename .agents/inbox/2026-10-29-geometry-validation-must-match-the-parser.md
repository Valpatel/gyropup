# Geometry validation must match the parser's byte classifier

On 2026-10-29 UTC, source review of the new required-STL guard found a classifier mismatch. The guard trimmed leading whitespace and accepted case-insensitive `solid`; the vendored Three.js STLLoader recognizes lowercase `solid` only at byte offsets0–4. Other payloads are classified as binary, with the face count read at byte80 before allocation.

The following reproduction evaluated only the guard and classifier; it did not invoke the dangerous allocation:

```js
const bytes = new TextEncoder().encode(' '.repeat(80) + 'solid invalid\nendsolid invalid\n').buffer;
validateSTLBytes(bytes); // returned successfully before the fix
new DataView(bytes).getUint32(80, true); // 1768714099
```

The actual diagnostic output was:

```text
{"accepted":true,"recognizedASCII":false,"binaryTriangleCount":1768714099,"bytes":111}
```

The correction requires the parser's minimum header length and either an exact binary byte count or the same byte-level ASCII prefix offsets. The same111-byte payload, uppercase114-byte payload and short26-byte empty ASCII response were then rejected before parsing:

```text
{"bytes":111,"accepted":false}
{"bytes":114,"accepted":false}
{"bytes":26,"accepted":false}
```

Rule: a pre-parser validator must agree with the actual parser's format selection. Text cleanup that seems friendly can send a small invalid download into an unrelated binary allocation path. The `prefix` case in `tools/test-loading-portal.mjs` requires a visible error, no partial scene and a successful native retry. The accepted production binary STL files remain covered by current-model and viewer suites.

Limits: this is a payload admission guard, not a proof of valid CAD topology or safe manufacturing. It does not claim a general-purpose STL parser or expand accepted formats beyond the vendored parser.
