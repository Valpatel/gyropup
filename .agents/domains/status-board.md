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
