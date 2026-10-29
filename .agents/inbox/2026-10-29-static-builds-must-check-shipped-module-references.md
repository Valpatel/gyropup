# A copied entry module does not prove its dependencies were shipped

On 2026-10-28 Pacific time (2026-10-29 UTC), the simulator imported newly created `robot_actions.js`, but the first local static build omitted the unstaged file. The page could not initialize. Staging the new module and stylesheet, then rebuilding, restored the preview.

## Receipt

The failed preview build contained the import but only the older robot modules:

```text
rg -n 'robot_actions' dist/designer/sim.js
15:import { createRobotActions } from './robot_actions.js';
ls dist/designer/robot*
dist/designer/robot3d.js
dist/designer/robot_v2.js
```

`dist/designer/robot_actions.js` was absent in that listing. The camera browser test timed out waiting for `window.__sim?.bench()?.active` at `tools/test-camera-controls.mjs:37`.

The new negative fixture, run 2026-10-29 UTC by writing `import './robot_actions.js';` into a temporary `entry.js` and calling `versionSiteAssets(fixture)`, fails before publication:

```text
Missing relative module: entry.js imports ./robot_actions.js (expected robot_actions.js). New site sources must be git-tracked before building.
```

`npm run test:cache` passed its four missing-module cases and Chromium cache migration (`old → new → edited`, `errors: []`).

## Why the build appeared successful

The build intentionally copies `git ls-files` to avoid exposing arbitrary local files. It copied the already tracked simulator entry point, but did not verify that the entry point's imports resolved inside the published artifact. Source-file existence and successful copying were weaker evidence than the browser's module graph required.

## Corrective rule and limits

Stage exact new source paths before building, and validate literal relative module references against the output file set during the existing cache-versioning build step. Keep the tracked-file allowlist. The negative regression belongs in the existing cache harness, alongside the build guard. See [static build module references](../domains/static-build.md) for scope and the remaining runtime checks; this guard is not a complete JavaScript parser.
