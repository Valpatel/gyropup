# Static build module references

`tools/build-site.mjs` copies publishable repository assets from `git ls-files`. A new JavaScript module can exist locally and still be absent from `dist` until its exact source path is staged. Stage new web source before building; retain this allowlist so untracked credentials, licensed downloads and local runs are not published.

`versionSiteAssets` in `tools/site-cache.mjs` checks the shipped JavaScript module files before rewriting HTML. Missing literal relative imports, re-exports and dynamic imports fail the build with the importing file and expected target. Query strings and fragments do not change the required file. Import-map aliases and remote URLs remain supported.

Run `npm run test:cache`: negative fixtures omit a module under four import forms, while positive fixtures retain aliases, remote imports, comments, quoted examples and versioned relative URLs. The existing browser test also checks real cache migration across releases.

Limits: this is a conservative literal-reference check, not a JavaScript parser or a complete dependency graph. Computed imports, escaped/template expressions, inline HTML scripts, runtime fetches and dynamically inserted CSS still need build/browser validation. A passing module check does not establish that every application feature works.
