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

Open the shared URL, `http://127.0.0.1:8899`. Check its exact served directory and
owner with `npm run preview:status`. `npm run preview` starts the existing build
or reuses the same checkout's server. If another checkout owns the shared address,
coordinate with its owner and stop it before switching; do not select another
persistent port. After editing sources, run `npm run build` and refresh. The
preview serves the latest bundle without restarting. Stop it with Ctrl+C when
finished. Tests use `node tools/serve-site.mjs --ephemeral`, retain its child handle,
and stop/wait during teardown. Temporary CLI servers also expire after 30 minutes
and stop if their parent disappears; `PORT=0` remains supported. The original
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

The build emits revalidation headers for published files (`Cache-Control: public,
no-cache, max-age=0, must-revalidate`). The local preview uses this policy and ETags,
so unchanged bytes can return 304. Cloudflare Pages applies this through the
generated `_headers` file; its [header rules override the default response](https://developers.cloudflare.com/pages/configuration/headers/).

On 2026-10-28, production CSS/JS responses had a four-hour freshness lifetime.
A real browser test showed that an ordinary reload refreshed HTML while keeping
old entry modules, nested modules and CSS, even after the server policy changed.
Headers alone cannot evict bytes that a returning browser still considers fresh.
The build now derives a cache key from the published content, versions asset
references, and adds exact import-map entries for nested and dynamic modules.
Existing Three.js aliases remain available. CSS imports/fonts and the character's
runtime stylesheet carry the same key. Static JSON fetches in the simulator and
navigation revalidate; conversation requests keep their existing behavior.

After the `74829d3` rollout on 2026-10-28, the immutable Pages deployment served
the emitted policy, but the custom domain still overrode CSS/JS responses with
`public, max-age=14400, must-revalidate`. HTML, JSON and Markdown revalidated.
Content-derived module and stylesheet URLs still ensure release freshness on
normal reloads, even with the four-hour browser cache. The
[live verification receipt](https://github.com/Valpatel/gyropup/issues/36#issuecomment-6476128867)
records all 144 Markdown bodies matching that production build.

Setting the zone's Browser Cache TTL to
[Respect Existing Headers](https://developers.cloudflare.com/cache/how-to/edge-browser-cache-ttl/set-browser-ttl/)
would align the custom-domain policy with the build. This is optional hosting
alignment pending the owner's choice or existing authorized access, tracked in
[issue 36](https://github.com/Valpatel/gyropup/issues/36). Releases and cache
freshness do not depend on expanding permissions or changing that setting.

The key changes for local edits before a commit and is recorded as `assets` in
`version.json`. Run `npm run build`, then reload normally. Already loaded tabs
are not forcibly reloaded, so an update cannot interrupt an active conversation.
This is not a service worker or an automatic refresh mechanism.

`npm run test:cache` uses an actual browser HTTP cache: it first reproduces the
old four-hour behavior, then checks ordinary reloads through two new builds and
conditional 304 reuse. Use `PLAYWRIGHT_BROWSER=webkit npm run test:cache` for
WebKit. After publication, check both HTML and a nested asset on the custom
domain and verify `version.json`, recording any hosting override separately from
the emitted policy. Do not rely on a CDN purge to clear browser caches.

Cloudflare OAuth should be refreshed with `npx wrangler whoami` before treating
an expired token as a blocker. Pages deployment permission does **not** imply DNS
edit permission. For the custom domain, Pages must register `gyropup.com` and the
zone needs a proxied CNAME `@` → `gyropup.pages.dev`. A Pages domain reporting
`CNAME record not set` needs that DNS record; repeating a Pages deployment will
not fix DNS. No credentials belong in git, logs, or progress reports.

## Public access and local services

Both `gyropup.com` and `www.gyropup.com` are registered Pages custom domains,
with proxied CNAME records pointing to `gyropup.pages.dev`. Each redirects HTTP
to HTTPS. The www record was missing until the 2026-10-28 access investigation
([issue 39](https://github.com/Valpatel/gyropup/issues/39)); a negative DNS cache
can briefly outlive the repair. Both names serve the same static bundle.

A valid apex certificate does not prove a network filter permits a new domain.
When investigating a block, record the exact failing hostname, browser error or
filter category, and timestamp. Check normal TLS verification and redirects for
both names, then compare resolver results. Never bypass certificate validation
to declare a website healthy. Cloudflare's standard, malware and family DNS
resolvers returned real apex addresses during the initial investigation; this
only describes those resolvers at that time.

The hosted simulator uses browser voice and scripted replies by default. It must
not automatically probe a visitor's localhost or private-network AI services.
Local development keeps automatic discovery, and explicit service configuration
remains available subject to browser HTTPS/CORS/network permissions. Run
`npm run test:services` (or `PLAYWRIGHT_BROWSER=webkit npm run test:services`) to
exercise actual chat discovery on public, local and misleading hostnames, plus
configured services and failed-service fallback. The harness intercepts every
request and never contacts real local services.

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

The product weight ceiling is 100 lb (45.36 kg), recorded in decision D72 and
[the weight budget](design-weight-budget.md). Current CAD uses 37.5 kg (see D71).
The ceiling is a design requirement; existing load results retain their tested
masses and do not establish validation at the full 100 lb ceiling. Tritium is a design requirement (D19). The Tritium,
Graphlings, and GraphDone cards describe the integration roadmap, not a running
connected robot. GraphDone coordinates development work, not onboard control.

The landing highlights use fresh captures of the current public turret and demo,
plus explicitly archived leg physics and E1 static deformation inserts. The matching
WebP poster and H.264/VP9 movies live in `web/highlights/`. Rebuild them with the
[capture and encoding recipe](validation/landing-highlights.md); do not pair the
movie with a screenshot from another robot revision. The older `web/playground.png`
remains an archival asset and is no longer the landing movie's poster.

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

### Keep public progress current

At each meaningful engineering checkpoint and website release, update
`docs/progress.json` with a dated, evidence-linked entry and the current focus.
Distinguish live production work from candidates on an engineering branch and
physical measurements. Never use the build timestamp as the report date.
The Progress page keeps three recent entries visible and the complete history
in date-grouped disclosures; its Markdown route retains every entry.
See [Progress presentation checks](validation/progress-presentation.md).
