# Progress overview and disclosed evidence

The Progress page shows a current focus, the existing source-bound E1 deformation study, three recent evidence-linked updates and current project status. Detailed structural cases, CAD galleries, recorded rig tests, procurement and dated history open on demand. Earlier notes retain their date and a historical-context warning. The original tables, parts checklist and downloads remain available.

`docs/progress.json` is maintained content. Update it with meaningful engineering checkpoints and releases, including evidence links and the actual integration/publication state; build time is not a substitute for a report date. The original October 29 website release distinguished live software from candidates then available only on the engineering branch. The engineering publication adds direct inspection links and a dated update; older entries retain their historical branch context. None of these candidates is physical qualification.

`tools/test-progress.mjs` checks 21 viewport sizes in either browser engine, visible E1 playback readiness before long content, desktop column placement, three recent entries, archive completeness, native keyboard operation, preserved expanded dates on retry, cold nested deep links and repeated-hash reopening. It checks that disclosure changes preserve the same video element and that agent Markdown includes every historical entry. Each invocation uses a unique evidence directory.

The existing study-media harness checks actual advancing frames, the matching 3D field, failed/invalid media, still-only cases and reduced-motion behavior. The parts harness uses native disclosure controls before sorting and updating tracked rows. Loading tests retain independent section retry. Markdown tests check all log entries rather than only the newest one.

Reproduce against a built preview:

```sh
SITE_URL=http://127.0.0.1:8982 npm run test:progress
PLAYWRIGHT_BROWSER=webkit SITE_URL=http://127.0.0.1:8982 npm run test:progress
SITE_URL=http://127.0.0.1:8982 npm run test:study-media
SITE_URL=http://127.0.0.1:8982 npm run test:build-portal
SITE_URL=http://127.0.0.1:8982 npm run test:loading-portal
SITE_URL=http://127.0.0.1:8982 npm run test:markdown
```

Use the deployed URL for publication checks and bind receipts to `/version.json`. These checks do not qualify physical hardware, convert a static field into transient physics, establish present supplier stock, or validate the robot at its 100 lb design ceiling. Review and exact live receipts: [PR94](https://github.com/Valpatel/gyropup/pull/94), [issue93](https://github.com/Valpatel/gyropup/issues/93).
