# The design status board and the wall-of-text gate

The owner (2026-11-01) wants diagrams, status bars and real renders that show the design and when it changes, not
run-on agent prose. `tools/status-board.mjs` builds one panel a subsystem from committed records when the site is
built and writes it into `index.html` and `designer/progress.html` at their `<!-- status-board -->` markers, plus
`/site/status.json`. Never type a number into the board: add the record, then the reader. `npm run test:status-board`
counts every record again on its own and fails a board that disagrees.

- Colours: green meets its own target, teal noted, amber below target or the owner's call, red under 1.0 or a fix,
  hatched grey not measured. A missing record shows as missing; a sheet with blank rows is "not yet measured".
- "Records changed" is git's newest commit to the panel's `records`. Every meter's source must sit under them (the
  test checks). Cloudflare Pages clones shallowly: the build runs `git fetch --unshallow` only when `CF_PAGES` is set;
  anywhere else a shallow checkout shows no dates rather than wrong ones (`version.json` `history`).
- A new assembly in `research/insert-joints/joints.json` needs a panel (the test lists the owners).

`npm run test:walls` measures every published page at 1366 x 800 (`tools/site-walls.mjs`, the same measure as
cad-agent's #179): the longest stretch of content with no image, diagram or `[data-visual]` graphic of at least
120 x 80 px. Over 1200 px fails, except pages on `tools/wall-backlog.json`, which only shrinks. Mark `data-visual`
only on a real drawing of data or design (a bar chart, a flow diagram), never on a text card to pass the gate.

"What changed" (`tools/timeline.mjs`) is the design's history from git: each merged pull request or direct commit
(release and sync merges opened into the pull requests they carry, so main shows what dev shows) that changed CAD source, geometry, a render, hardware, a decision, or added a record, with git's date, the PR
title cut to its first clause, subsystem chips from the paths, and the render it changed before and after, copied
from git's objects to `/site/timeline/`. It sits at `<!-- timeline -->` on the landing page (newest 4) and Progress
(newest 5, the rest folded), plus `/site/timeline.json`. `npm run test:timeline` reads git again and fails if a pull request
or commit in the shown span that changed the design is missing, or if a release shows as one change. Good PR titles make good
labels: the first clause before "; " or " — " is what the timeline shows.

Design notes (`tools/doc-page.mjs`) are shown, never rewritten, by the build: a lead card (git date, length, sections,
and for a one-subsystem note that subsystem's render and first three status-board readings), a status strip over any
table whose `Status`/`Verdict`/`Result`/`State` column is a real scale of short words, and folds that keep each
stretch of prose between pictures under about a screen (opening kept, then only a short first paragraph, then only
the heading as the fold's summary). Pictures, diagrams and strips never fold. To make a note better than an outline,
give it something to look at: a render from `exports/`, a Mermaid diagram of its order or flow (and raise the count in
`tools/test-diagrams.mjs`), or a table with a status column. `npm run test:doc-pages` checks that every word of the
Markdown is still on the page and that every strip agrees with its table.
