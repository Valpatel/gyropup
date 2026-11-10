# Cached CAD projections need separate producer and consumer provenance

On2026-11-10, README preparation found a233-part illustration bound to native
sourcea86c230c while accepted collection266 contains224parts from3a408919 and the
front/rear battery body. Both the old scene and new collection retain80 protected
leg meshes. Matching names or a new config header cannot make the old body
geometry current.

The new consumer also reuses a shared binary-STL decoder whose current bytes
66d10769 differ from the original collector's0332582d. Those are separate roles:
the original producer-input fingerprint remains historical, and the projection
consumer records its actual decoder/tool bytes. Original nativeNumPy2.5.4 is not
the local fixture projection's2.5.2 runtime. No native collection is rebuilt or
relabeled by decoding its captured triangles.

Dated source checks are in [the checkpoint](../plans/end-packs-readme/source-checkpoint.json).
`python3 -B tests/evidence/media/test-readme-collection.py` passed12controls,
including unchanged shared topology/projection/motif on16 synthetic tetrahedron
triangles, a native-tessellation trap, changed bytes/membership/frames, malformed
STL, protected-leg faults, runtime faults, and primary/secondary failure
preservation. `python3 -S -B` passed9standard-library controls with3explicit
runtime/projection dependency skips. The full22-test entry point passed21and
rejected the unchanged old scene at mandatory real-artifact parity. The source
checkpoint preserves that failure; it is not a passing current-illustration claim.

Corrective rule: bind original mesh bytes and native provenance separately from
the new adapter, decoder, projection runtime and shared renderer. Require complete
input/frame/part/triangle correspondence and before/after guards. Run a fresh
projection into candidate output; inspect and independently review that actual
artifact before adoption. Never replace an old scene's headers to satisfy a new
source key. The regression retains the old91-part body membership and rejects it
against the current82-part body even with forged new binding headers.

Limits: the source checkpoint has no full product projection, new CAD construction,
tracked SVG/scene/receipt adoption, native geometry validation or physical fit
qualification. Fresh real-candidate renderer parity remains mandatory. Cached
STL and painter-order projection are illustration approximations.
