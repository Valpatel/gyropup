# Static build module references

`tools/build-site.mjs` copies publishable repository assets from `git ls-files`. A new JavaScript module can exist locally and still be absent from `dist` until its exact source path is staged. Stage new web source before building; retain this allowlist so untracked credentials, licensed downloads and local runs are not published.

`versionSiteAssets` in `tools/site-cache.mjs` checks the shipped JavaScript module files before rewriting HTML. Missing literal relative imports, re-exports and dynamic imports fail the build with the importing file and expected target. Query strings and fragments do not change the required file. Import-map aliases and remote URLs remain supported.

Run `npm run test:cache`: negative fixtures omit a module under four import forms, while positive fixtures retain aliases, remote imports, comments, quoted examples and versioned relative URLs. The existing browser test also checks real cache migration across releases.

Network failure fixtures must match the versioned URLs that the build actually
ships. Use a URL pathname predicate when query parameters are irrelevant, and
assert both interception count and the intended held/failed state. A successful
downstream action cannot prove that a missing-module fixture ran.

Limits: this is a conservative literal-reference check, not a JavaScript parser or a complete dependency graph. Computed imports, escaped/template expressions, inline HTML scripts, runtime fetches and dynamically inserted CSS still need build/browser validation. A passing module check does not establish that every application feature works.

Generated HTML downloads need explicit closing `head` and `body` tags, even
when a browser would infer them. On 2026-11-10, the Robot guide fallback omitted
them and ordinary build run 42780003951 stopped at `build-site.mjs:186` with
`Cannot add prototype notice to web/build-guides/robot-wip-540056ba4e59/instructions.html`.
The authored exporter now emits the complete document; regenerate its immutable
fallbacks and run the real build. Do not bypass prototype injection or classify
this build refusal as a browser/geometry failure.

Asset copying and human document discovery are separate. Tracked `hardware/` Markdown joins `docs/` and `research/` in the notebook; keep instruction/handoff exclusions consistent. Render source-relative links into the published page set and verify original CAD downloads remain byte-identical. Large-format vector drawings need a responsive page preview; their native paper dimensions are not a phone layout. See [engineering publication checks](../inbox/2026-10-29-downloadable-cad-notes-still-need-a-usable-portal.md).

## Verify the actual publication

After a normal main merge, require its actual ordinary public version plus source-byte identities and canonical routes, with the same version before and after the readback. An observed new version can precede an older document response; retain that incomplete observation and require the full final check without changing source/hash expectations. Verify GitHub-specific discovery through its actual API separately from site publication. See [the observed version/byte boundary](../inbox/2026-11-05-ci-classification-needs-phase-evidence.md#a-new-version-response-is-not-complete-publication-evidence).
