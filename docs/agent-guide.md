# Reading Gyropup with an agent

Gyropup is a research project combining a wheel-legged robot design, a foam-ball turret and a browser
playground. It is at the CAD and simulation stage, with no assembled robot or print release. Prototypes are
unsafe, provided for research purposes only, and will not be offered for sale. Read the
[full warning](prototype-safety.md) before interpreting the plans as instructions.

## Reading order

1. Read the [documentation map](README.md) for the engineering topics and
   [Progress](https://gyropup.com/designer/progress.md) for the published status and report links.
2. Use [Build](https://gyropup.com/designer/build.md) for parts tables, original downloads and their status.
   File availability is not permission to manufacture or evidence that parts fit.
3. Follow a report to its source inputs, revision and limitations. Read
   [structural media](structural-study-media.md), [print provenance](print-source-provenance.md) and the
   [weight budget](design-weight-budget.md) when describing strength, printability or mass.
4. Check [program #31](https://github.com/Valpatel/gyropup/issues/31) and the linked workstream issue for live
   work. A published page may predate an issue update or an unmerged proposal.

## Fetching pages

[/llms.txt](https://gyropup.com/llms.txt) is the discovery entry point and includes the full generated page
catalog. Every public HTML page has a Markdown counterpart advertised by
`<link rel="alternate" type="text/markdown">`. For example, `/designer/progress.html` has
`/designer/progress.md`, while `/` has `/index.md` and `/site/` has `/site/index.md`.
Use the listed URL directly; no account, browser execution or content-negotiation header is needed.
Some Python clients currently receive a Cloudflare 1010 block, tracked in
[issue #107](https://github.com/Valpatel/gyropup/issues/107). Such a response is not evidence that the document is missing.

Markdown is generated from the published HTML on each build. Progress and Build include their rendered data
tables, including collapsed history. Interactive 3D scenes, audio and controls remain in the HTML view; their
presence in Markdown does not reproduce the interaction or constitute a new simulation run. Links may point
back to HTML for those views. Authored sources such as `/docs/agent-guide.md` also exist; the notebook's
`/site/pages/docs-agent-guide-md.md` is its generated, framed counterpart.

CAD, JSON, images, videos and other downloads keep their existing URLs and formats. Follow those original
links for evidence rather than treating the text conversion as a complete engineering dataset.

## Provenance and interpretation

[/version.json](https://gyropup.com/version.json) identifies the website's source revision and build time.
[/markdown-pages.json](https://gyropup.com/markdown-pages.json) maps HTML to Markdown with SHA-256 hashes for
the generated files. These identify the publication; a report or recording can describe an older model and
must still be checked against its own provenance.

Separate design targets, predictions, recorded results and physical measurements. The 100 lb maximum and
$10,000 budget are targets. Historical loads do not qualify the full weight ceiling; current CAD does not
retroactively update recorded physics. Static FEA load-scaling movies are not elapsed-time physical tests.
The browser playground does not control a real robot. Preserve failed, missing and unqualified results when
summarizing; do not turn a partial check into a whole-robot safety claim.

The [repository](https://github.com/Valpatel/gyropup) is the source for the website and design artifacts.
Quote the document, report revision or issue that supports a claim. Public reading guidance is separate from
repository contributor instructions and does not authorize deployment, purchases or hardware operation.
