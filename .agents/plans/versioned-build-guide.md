# Versioned Build guide pilot

Issue #266 extends the existing Build route, shared viewer and authored turret assembly sequence. Shared schema/viewer changes are owned by cad-agent issue #302; product composition, version selection, deep links, progress and source-bound recipe adaptation live here.

## Agreed data boundary

Use `cad-agent.assembly-guide/1`, an immutable snapshot identity and a SHA-bound ordinary `view.json`. Parts are baked into neutral assembled CAD millimetres/z-up before the shared viewer loads them; guide offsets are absolute and noncumulative in that same frame. Each step declares complete visible membership, highlighted additions, subassembly, authored offsets/camera, text, prerequisites and a SHA-bound poster. No old step PNG or JSON is relabelled current.

The current turret pilot adapts the exact committed 80-mesh scene through its existing neutral joint hierarchy, retaining original mesh/manifest/BOM/recipe identities. All 53 authored logical additions resolve, but that is mapping only: the old twelve images/text retain the zero-degree upper stop. They remain historical. The generated guide must use the actual authored +12/-25 recipe, with its physical qualification caveats visible.

## Implementation sequence

1. Export deterministic neutral meshes and guide metadata from committed original meshes and the existing literal `STEPS` recipe, without importing CAD, changing geometry or changing existing manufacturing outputs. Validate exact original digests, all instances, frames and offsets. Produce fresh posters through the same guide/viewer path; no historical image substitution.
2. Extend Build with snapshot/subassembly/step selection; previous/next/deep links, version-scoped assembly progress, highlighting/isolation/ghost/wireframe/explosion and text/poster fallback. Preserve existing Buy/Print anchors, calculations, downloads and procurement tracking. Browser code stays outside the existing static table renderer.
3. Include two deliberately distinct contract fixtures and exact-commit WIP; fixtures are tests, not invented released product history. No released versions are advertised until real coherent releases exist.
4. Check real multipart state, transforms exactly once, repeated instances, stale bindings, failed/late switches, no-WebGL/static fallback, Markdown, phone/desktop/reduced motion and scene cleanup. Normal independent review/CI/dev-main publication remains mandatory.

No robot geometry redesign, hip/camera work, hardware action, new rendering engine, service or dependency. Physical fit/strength/laser/feed qualification remains unresolved. Heavy native/render collection, if required, needs a separately reviewed bounded remote run.
