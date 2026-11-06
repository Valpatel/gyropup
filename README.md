<div align="center">

<img src="docs/img/hero/gyropup.svg" alt="The name Gyropup grows from a graph-paper sketch while the current CAD is drawn: the bench stand is traced, the foam-ball turret drops onto it on its compute plinth, leg v2 slides in beside it (two RS-04 motors side by side at the hip, two orange links meeting at the wheel), then the turret head sweeps left and right, nods and holds a lock-on" width="100%">

# Gyropup

**A research robot designed to balance on two wheel-legs, with a foam-ball turret: CAD and simulation in the open.**

[<img class="repo-badge" src="https://github.com/Valpatel/gyropup/actions/workflows/body-firmware.yml/badge.svg?branch=main" alt="Firmware" width="158" height="20" style="width:158px;height:20px;object-fit:contain;padding:0;border-radius:0">](https://github.com/Valpatel/gyropup/actions/workflows/body-firmware.yml)
[<img class="repo-badge" src="https://github.com/Valpatel/gyropup/actions/workflows/web-scene.yml/badge.svg?branch=main" alt="Playground and presentation" width="236" height="20" style="width:236px;height:20px;object-fit:contain;padding:0;border-radius:0">](https://github.com/Valpatel/gyropup/actions/workflows/web-scene.yml)
[<img class="repo-badge" src="https://img.shields.io/badge/licence-MIT-287d8d" alt="Licence: MIT" width="78" height="20" style="width:78px;height:20px;object-fit:contain;padding:0;border-radius:0">](LICENSE)
[<img class="repo-badge" src="https://img.shields.io/website?url=https%3A%2F%2Fgyropup.com&amp;label=gyropup.com&amp;up_message=live" alt="Site" width="112" height="20" style="width:112px;height:20px;object-fit:contain;padding:0;border-radius:0">](https://gyropup.com)
[<img class="repo-badge" src="https://img.shields.io/github/last-commit/Valpatel/gyropup/dev" alt="Last commit" width="116" height="20" style="width:116px;height:20px;object-fit:contain;padding:0;border-radius:0">](https://github.com/Valpatel/gyropup/commits/dev)
[<img class="repo-badge" src="https://img.shields.io/github/stars/Valpatel/gyropup?style=flat&amp;logo=github" alt="Stars" width="71" height="20" style="width:71px;height:20px;object-fit:contain;padding:0;border-radius:0">](https://github.com/Valpatel/gyropup/stargazers)
[<img class="repo-badge" src="https://img.shields.io/badge/PRs-welcome-ec4899" alt="PRs welcome" width="90" height="20" style="width:90px;height:20px;object-fit:contain;padding:0;border-radius:0">](.github/CONTRIBUTING.md)

[Website & playground](https://gyropup.com) · [Documentation map](docs/README.md) · [Prototype warning](docs/prototype-safety.md) · [Contributing](.github/CONTRIBUTING.md)

<sub>The banner is drawn from the project's own CadQuery code (<code>cad/build_leg.py</code>, <code>cad/turret.py</code>, <code>cad/turret_stand.py</code>) with hidden lines removed, set as the project's own <code>tools/readme_hero.py</code> sets it, by the <a href="https://github.com/mvalancy/mvalancy/tree/9a878ce602d8a5256027c9f4367d2ae5ea4784da/tools/hero">README banner generator</a>.</sub>

</div>

## Explore Gyropup

[![Four paths through Gyropup: explore, build, understand and contribute](docs/img/navigation/project-map.svg)](docs/README.md)

[Playground](https://gyropup.com/designer/sim.html) · [Build and downloads](https://gyropup.com/designer/build.html) · [Engineering notes](docs/README.md) · [Contribute](.github/CONTRIBUTING.md)

A research project exploring a self-balancing wheel-legged robot and a foam-ball turret. The design combines
hub-motor wheels, two five-bar legs driven by RobStride RS-04 actuators, and a pan/tilt turret for Rival-size foam
balls. CAD, simulation, component libraries and evidence are developed in the open. The playground runs in your browser.

**Physical progress, owner report 2026-11-05:** first motors in hand; main motor holder and motor adapter printed.
[The dated record](docs/physical-progress.md) keeps received/printed status separate from measured fit, installation
and testing. No assembled robot or full print release is recorded.

**Gyropup prototypes are unsafe, are for research purposes only, and will not be offered for sale.**
Read the [prototype warning](docs/prototype-safety.md).

## Follow the build

1. [One leg on its test rig](docs/motor-day.md): motor-day preparation, fit observations and bench evidence.
2. [The turret on a bench base](docs/turret-prototype-plan.md): mechanisms, parts and qualification work.
3. [The body around two legs](docs/body-plan.md): compute, power, structure and integration.

[Progress and reports](https://gyropup.com/designer/progress.html) show published evidence;
[program #31](https://github.com/Valpatel/gyropup/issues/31) holds current priorities and remaining work.
Historical reports retain their own geometry, loads and limitations. The
[weight record](docs/design-weight-budget.md) distinguishes design estimates from tested loads and the 100 lb ceiling.

## Work with the repository

Start with [CONTRIBUTING.md](.github/CONTRIBUTING.md) and the [documentation map](docs/README.md).
Run the same website locally with `nvm use && npm ci && npm run dev`.
[Website development and deployment](docs/site-deployment.md) explains checks, previews and publishing.
Agents can use the [public reading guide](docs/agent-guide.md) and [llms.txt](https://gyropup.com/llms.txt).

## Licence

[MIT](LICENSE) covers repository code, CAD sources, generated models, docs and data. Vendor CAD is excluded;
`references/vendor/**/SOURCE.txt` records sources. Product names and trademarks belong to their owners.
