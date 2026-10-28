# The Gyropup website

The landing page and existing playground, progress, and build portal are one
static website, in this repository. Cloudflare Pages serves the same `dist/`
bundle that the local preview serves. There is no separate website repository,
server process, or new downloads product. Existing build/report file links
continue to expose the committed design artifacts alongside their context.

## Local development

Use Node 22 (see `.nvmrc`):

```sh
nvm use
npm ci
npm run dev
```

Open the printed URL (default `http://127.0.0.1:8644`). If that port is taken,
use `PORT=8764 npm run dev`. After editing sources, run `npm run build` and
refresh. The preview serves the latest bundle without restarting. The original
`cad-agent site --serve` remains available for CAD-specific work; it redirects
its root to the engineering notebook. `npm run dev` is the full public-site
preview, including the landing page.

`npm run build` packages the landing page, existing designer modules, committed
CAD/physics artifacts, catalog, design sources and engineering documents. It
renders Markdown and decisions to the design notebook. It does not build CAD,
run solvers, copy local credentials, include vendor source downloads, or copy RL
training data. Source/evidence files must be tracked in git to be published.
The existing build page's directory queries receive generated static indexes.

## Continuous publishing

The Cloudflare Pages project **gyropup** is connected directly to
**Valpatel/gyropup**. Production branch: **main**. Build command:
`npm ci && npm run build`. Output directory: **dist**. Node: **22**.

A reviewed merge/push to main builds and deploys production automatically.
Feature branches receive preview deployments. This path uses Cloudflare's GitHub
integration and does not depend on a developer's local OAuth token.

For an explicitly requested immediate publication from a reviewed source commit:

```sh
nvm use
npx wrangler whoami
npm run deploy
```

`npm run deploy` builds the current checkout and uploads it to production. Commit
and push the source first. `/version.json` records the source revision so a
published artifact can be matched to GitHub. `wrangler.toml` declares the output
folder; keep it aligned with the dashboard configuration.

### Returning browsers and local edits

All published files explicitly revalidate (`Cache-Control: public, no-cache,
max-age=0, must-revalidate`). The local preview uses the same policy and ETags,
so unchanged bytes can return304. Cloudflare Pages applies this through the
generated `_headers` file; its [header rules override the default response](https://developers.cloudflare.com/pages/configuration/headers/).

On2026-10-28, production CSS/JS responses had a four-hour freshness lifetime.
A real browser test showed that an ordinary reload refreshed HTML while keeping
old entry modules, nested modules and CSS, even after the server policy changed.
Headers alone cannot evict bytes that a returning browser still considers fresh.
The build now derives a cache key from the published content, versions asset
references, and adds exact import-map entries for nested and dynamic modules.
Existing Three.js aliases remain available. CSS imports/fonts and the character's
runtime stylesheet carry the same key. Static JSON fetches in the simulator and
navigation revalidate; conversation requests keep their existing behavior.

The key changes for local edits before a commit and is recorded as `assets` in
`version.json`. Run `npm run build`, then reload normally. Already loaded tabs
are not forcibly reloaded, so an update cannot interrupt an active conversation.
This is not a service worker or an automatic refresh mechanism.

`npm run test:cache` uses an actual browser HTTP cache: it first reproduces the
old four-hour behavior, then checks ordinary reloads through two new builds and
conditional304 reuse. Use `PLAYWRIGHT_BROWSER=webkit npm run test:cache` for
WebKit. After publication, check both HTML and a nested asset on the custom
domain for the explicit policy and verify `version.json`; a dashboard cache rule
must not replace the response policy. Do not rely on a CDN purge to clear browser
caches.

Cloudflare OAuth should be refreshed with `npx wrangler whoami` before treating
an expired token as a blocker. Pages deployment permission does **not** imply DNS
edit permission. For the custom domain, Pages must register `gyropup.com` and the
zone needs a proxied CNAME `@` → `gyropup.pages.dev`. A Pages domain reporting
`CNAME record not set` needs that DNS record; repeating a Pages deployment will
not fix DNS. No credentials belong in git, logs, or progress reports.

## Keep the playground current

`exports/sim/` is a committed browser snapshot. Its README records provenance and
limitations; the initial public snapshot is from October 25–26, 2026, and predates
some current hardware revisions. The UI must not present it as validation of the
latest hardware. The browser plays prerecorded physics or interactive poses;
it does not connect to or control a physical robot.

When a hardware change is ready, regenerate its browser meshes and matching
physics replays with the repository's simulation tools, validate them, and commit
the snapshot with the related design change. Update `docs/progress.json` alongside
new reports. Cloudflare then publishes that same reviewed evidence. Generated
files must come from the matching source revision, never hand-edited metrics.

## Web validation

With the local preview running and Chrome installed:

```sh
npm run test:web
SITE_URL=https://gyropup.com npm run test:web
```

The browser harness checks common phone sizes from 320 to 480 CSS pixels in
portrait and landscape, tablet and desktop layouts; navigation, overflow, the
simulator drawer, replay, pose, firing and turret; required network assets,
downloads, document anchors and genuine 404s. It writes screenshots and the
result matrix to ignored `test-results/`. This is viewport/touch emulation, not
a claim to have tested every physical phone or Safari version.

## Public launch and brand evidence

`gyropup.com` became active with a valid Cloudflare-managed certificate on
2026-10-28. The proxied apex CNAME points to `gyropup.pages.dev`. DNS propagation
can leave a local resolver with a negative cache briefly after creation; verify
against a public resolver and validate normal TLS rather than redeploying.

The landing page presents a 50-pound-class robot family as the ambition. Current
CAD uses37.5kg (see decision D71); do not turn the brand ambition into a verified
product specification. Tritium is a design requirement (D19). The Tritium,
Graphlings, and GraphDone cards describe the integration roadmap, not a running
connected robot. GraphDone coordinates development work, not onboard control.

`web/playground.png` is a browser capture of the committed target-practice
snapshot, taken2026-10-28. Regenerate it from the simulator when that snapshot
changes; do not use a screenshot of an obsolete landing page as the video poster.

## Markdown for agents

Every production build generates `/index.md`, `/llms.txt`, and a `.md` counterpart
for each public HTML page. HTML includes a `rel="alternate"` link with
`type="text/markdown"`. Use `/designer/sim.md`, `/designer/progress.md`,
`/designer/build.md`, and `/site/index.md` as entry points. Original CAD, JSON,
media, and document downloads keep their URLs.

`tools/site-markdown.mjs` converts published HTML. Progress and Build reuse their
trusted browser renderers against only the published bundle, so Markdown contains
current report and parts data instead of empty client-rendered placeholders. A
missing data snapshot fails the build. No separately maintained copy is needed.
`npm run test:markdown` checks content parity, tables, MIME, downloads, and404s;
`SITE_URL=https://gyropup.com npm run test:markdown` checks hosted routes too.

This uses explicit static routes on the existing Cloudflare Pages plan. It does
not negotiate `Accept: text/markdown` on the HTML URL. Cloudflare's native
[Markdown for Agents](https://developers.cloudflare.com/fundamentals/reference/markdown-for-agents/)
feature requires an eligible plan and Zone Settings Edit permission. Do not
silently purchase a plan or expand a DNS token to enable it.

## Continuous simulator experience

Ordinary replay/activity changes preserve the renderer, world, character, and
conversation. Targets and robot poses blend into the next activity, including
recording loops; the previous activity stays visible during loading. Late
requests cannot replace a newer selection. Hardware previews and replay props
are reused, and the turret re-racks its existing targets in place.

On2026-10-28, stage greetings were found to call `talk.say` directly, bypassing
the conversation's reaction cooldown. Use `talk.announce` for background stage
chatter and honor `talk.isBusy()` for expressions. Never interrupt a pending
answer, listening, or an answer still being presented. A stage change must not
recreate the talk panel, history, voice, or character.

Phone sliders previously inherited `#panel label { display:flex }`, squeezing
the label/value/track onto one line. Keep `.hud-slider` a grid with its track
below the label, a contrasting track, and a touch-sized thumb. Pooled inactive
target geometry must be hidden after its transition and excluded from raycasts.

Run `SITE_URL=http://127.0.0.1:8764 npm run test:sim` after the build; set
`PLAYWRIGHT_BROWSER=webkit` for WebKit. This checks an in-flight mocked reply
across stage changes, conversation and scene identity, loop blending, stale
fetches, cached models, target re-racking, and phone slider layouts. The mock
verifies browser continuity without claiming a production AI backend is online.
