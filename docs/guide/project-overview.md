# Gyropup project guide

The project entrance is the [short README](../../README.md). This guide keeps the detailed orientation, historical artwork context and build paths one click away. Reports retain their own revisions and limits. Root READMEs answer What/Why/Join briefly; the owner explicitly wants plentiful badges, so badge collections are exempt from that prose budget.

## Project links

[<img class="repo-badge" src="https://github.com/Valpatel/gyropup/actions/workflows/body-firmware.yml/badge.svg?branch=main" alt="Firmware" width="158" height="20" style="width:158px;height:20px;object-fit:contain;padding:0;border-radius:0">](https://github.com/Valpatel/gyropup/actions/workflows/body-firmware.yml)
[<img class="repo-badge" src="https://github.com/Valpatel/gyropup/actions/workflows/web-scene.yml/badge.svg?branch=main" alt="Playground and presentation" width="236" height="20" style="width:236px;height:20px;object-fit:contain;padding:0;border-radius:0">](https://github.com/Valpatel/gyropup/actions/workflows/web-scene.yml)
[<img class="repo-badge" src="https://img.shields.io/badge/licence-MIT-287d8d" alt="Licence: MIT" width="78" height="20" style="width:78px;height:20px;object-fit:contain;padding:0;border-radius:0">](../../LICENSE)
[<img class="repo-badge" src="https://img.shields.io/website?url=https%3A%2F%2Fgyropup.com&amp;label=gyropup.com&amp;up_message=live" alt="Site" width="112" height="20" style="width:112px;height:20px;object-fit:contain;padding:0;border-radius:0">](https://gyropup.com)
[<img class="repo-badge" src="https://img.shields.io/github/last-commit/Valpatel/gyropup/dev" alt="Last commit" width="116" height="20" style="width:116px;height:20px;object-fit:contain;padding:0;border-radius:0">](https://github.com/Valpatel/gyropup/commits/dev)
[<img class="repo-badge" src="https://img.shields.io/github/stars/Valpatel/gyropup?style=flat&amp;logo=github" alt="Stars" width="71" height="20" style="width:71px;height:20px;object-fit:contain;padding:0;border-radius:0">](https://github.com/Valpatel/gyropup/stargazers)
[<img class="repo-badge" src="https://img.shields.io/badge/PRs-welcome-ec4899" alt="PRs welcome" width="90" height="20" style="width:90px;height:20px;object-fit:contain;padding:0;border-radius:0">](../../.github/CONTRIBUTING.md)

[Website & playground](https://gyropup.com) · [Documentation map](../README.md) · [Prototype warning](../guide/prototype-safety.md) · [Contributing](../../.github/CONTRIBUTING.md)

## Original CAD artwork and generator

[Open the original CAD artwork](../img/hero/gyropup.svg).

<sub>Project artwork generated from Gyropup CAD · <a href="https://github.com/mvalancy/mvalancy/tree/9a878ce602d8a5256027c9f4367d2ae5ea4784da/tools/hero">generator credit</a></sub>

The original banner used the project's CadQuery code at `cad/build_leg.py`, `cad/turret.py` and
`cad/turret_stand.py`, with hidden lines removed and placement from `tools/readme_hero.py`.
Their current homes are [leg building](../../hardware/cad/builders/build_leg.py),
[turret CAD](../../hardware/cad/turret/turret.py), [stand CAD](../../hardware/cad/turret/turret_stand.py) and
[artwork generation](../../tools/engineering/robot/readme_hero.py). The artwork retains its original design context.

## Explore Gyropup

Gyropup is a research robot with wheel-legs and a foam-ball turret. It evolves with cad-agent through good sources,
virtual and real testing, independent review and methods worth reusing. CAD, simulation and evidence are developed
in the open; the playground runs in your browser.

**Physical progress, owner report 2026-11-05:** first motors in hand; main motor holder and motor adapter printed.
[The dated record](../program/physical-progress.md) keeps received/printed status separate from measured fit, installation
and testing. No assembled robot or full print release is recorded.

**Gyropup prototypes are unsafe, are for research purposes only, and will not be offered for sale.**
Read the [prototype warning](../guide/prototype-safety.md).

## Follow the build

1. [One leg on its test rig](../legs/motor-day.md): motor-day preparation, fit observations and bench evidence.
2. [The turret on a bench base](../turret/turret-prototype-plan.md): mechanisms, parts and qualification work.
3. [The body around two legs](../body/body-plan.md): compute, power, structure and integration.

[Progress and reports](https://gyropup.com/designer/progress.html) show published evidence;
[program #31](https://github.com/Valpatel/gyropup/issues/31) holds current priorities and remaining work.
Historical reports retain their own geometry, loads and limitations. The
[weight record](../architecture/design-weight-budget.md) distinguishes design estimates from tested loads and the 100 lb ceiling.

## Work with the repository

[Hardware](../../hardware/README.md) holds physical design and evidence; [software](../../software/README.md) holds firmware,
control, simulation and the website. [Tools](../../tools/README.md), [tests](../../tests/README.md) and [docs](../README.md)
have their own short maps.

Start with [CONTRIBUTING.md](../../.github/CONTRIBUTING.md) and the [documentation map](../README.md).
Run the same website locally with `nvm use && npm ci && npm run dev`.
[Website development and deployment](../software/site-deployment.md) explains checks, previews and publishing.
Agents can use the [public reading guide](../guide/agent-guide.md) and [llms.txt](https://gyropup.com/llms.txt).

## Licence

[MIT](../../LICENSE) covers repository code, CAD sources, generated models, docs and data. Vendor CAD is excluded;
`hardware/vendor/**/SOURCE.txt` records sources. Product names and trademarks belong to their owners.

## Keeping the design illustration current

The pixel header explains a stable learning method. The realistic figure depicts
a stated CAD revision and its published baseline; it is an illustration, not a fit, strength,
collision, fabrication or physical-operation verdict. Bought components include
engineering envelopes. The original artwork above retains its historical context.

The current [source receipt](../../tools/engineering/robot/current-design.receipt.json)
records the actual CAD revision, published baseline, complete hardware identity,
camera and tool versions; the [projected scene](../../tools/engineering/robot/current-design.scene.json)
retains the geometry used by the vector renderer. A candidate remains a candidate
until its normal main promotion and actual publication are verified. The figure
is current only while its complete input bindings still match.

The figure uses the existing shared [CAD motif extractor and renderer](https://github.com/mvalancy/mvalancy/tree/70c325d0111427647e2e782d6c04b4123d23cebf/tools/hero).
[The project configuration](../../tools/engineering/robot/readme-design.json)
pins that toolkit, camera, CAD runtime and published input files. The complete
conservative CAD/config/catalogue closure includes the five tests formerly under
`cad/`; the actual `robot_view.collect()` source is also bound. Extraction reads
the CAD into memory and never calls its engineering export or raster-render functions.
The complete published hardware Git tree also binds supplemental board, mount
and exported-data inputs. Local parameter overrides are rejected; the constructor
uses the tracked J501 parameter snapshot and a fresh measurement cache in the
owned run output, never a neighbouring checkout or an old local cache.

Refresh after relevant published CAD changes. A weekly cheap job checks input
drift and pure SVG parity; it does not run CAD, update hashes to hide drift, or
automatically publish a picture. Normal PR and main browser suites retain their
full commands, thresholds and limits. The intended cadence is weekly review of
that drift result and a genuine refresh when inputs changed.

1. Fetch published `main` normally. In a scoped branch whose CAD inputs equal
   that revision, run `python tools/engineering/robot/readme_design.py bind-source --revision <immutable-main-sha>`.
   This updates requested source configuration only: it deliberately leaves any
   old scene, SVG and receipt stale. It verifies every input byte against that Git revision.
   A genuine source repair may instead use clean committed current HEAD with
   `--candidate-source`; the configuration records published `main` separately
   as its baseline. Call that source a candidate until normal promotion and
   actual main publication have been verified.
2. Prepare and independently review the exact bounded fleet recipe, with the
   pinned profile and CAD-agent checkouts. Run
   `python tools/engineering/robot/readme_design.py extract --profile <profile-checkout> --toolkit <cad-agent-checkout> --out <new-owned-output>`
   on the fleet. Keep its complete source guards, candidate scene/SVG/receipt,
   runtime evidence and any failed attempts. Never run this native CAD stage on
   the shared workstation or regenerate unrelated engineering exports for artwork.
3. Inspect the genuine candidate and obtain independent adoption review. Copy
   only the coherent scene, SVG and receipt into their configured homes, verify
   bytes and run `python tools/engineering/robot/readme_design.py check --profile <profile-checkout>`.
   Presentation-only changes may use `render` with a still-current committed scene;
   that command cannot rebind stale CAD inputs.
4. Review the actual compiled README at desktop and phone sizes in both themes,
   including static/reduced motion, old anchors, ordinary links and the detailed guide.
   Publish through normal reviewed dev → main merges and check the actual public result.

### The fictional pixel playground

The header's wheel-legged robot duel is original conceptual art, separate from
the source-bound CAD illustration and dated physical evidence. Regenerate its
animated SVG and explicit still with
`python tools/site/readme_workshop.py --svg-library <cad-agent>/software/cadagent/publish/anim/svg.py`.
Use cad-agent revision `e662a1ce79b4f63f7352b9d065c5027f77d53a81`; the producer verifies the
shared component's exact hash and safety rules. Add `--check` for cheap deterministic parity.
No CAD kernel, font download or new dependency is involved. The README's `picture`
selects the generated still for reduced motion. Existing browser checks compare
actual image pixels and reject an intentionally animated still; page media
emulation alone does not establish that an external SVG image has stopped.

### Made with cad-agent badge

The two self-contained badge SVGs are copied unchanged from [cad-agent2c340775](https://github.com/Valpatel/cad-agent/tree/2c340775b1429a67e207e9668b2a3003009d4999/docs/img/hero), copyright2026Valpatel Software LLC, under the [MIT licence](https://github.com/Valpatel/cad-agent/blob/2c340775b1429a67e207e9668b2a3003009d4999/LICENSE). Their producer is `tools/anim/made_with_badge.py` from8ec8511fd468b843e8410c7305df01946534b0a5. Animated SHA256: `bcbe24827a5b8f9ca6aef2528eaec8f7f66448aa713ba83f95ab37fc04a9ac85`; still: `3dae18a9ccba77199d61b18645865c523209082c7fdb5ea95304f9b7ecadd8b9`. The README and homepage serve local copies and select the explicit still for reduced motion; no third-party image request or engineering claim is involved.
