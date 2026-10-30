# Documentation map

Gyropup is at the CAD and simulation stage. There is no assembled robot or print release. The
[prototype warning](prototype-safety.md) applies to every design and download: these prototypes are unsafe,
for research purposes only, and will not be offered for sale.

## Choose an entry point

| Purpose | Start here |
| --- | --- |
| Explore the project | [Website](https://gyropup.com), [browser playground](https://gyropup.com/designer/sim.html) |
| See published progress and evidence | [Progress](https://gyropup.com/designer/progress.html), [Build and downloads](https://gyropup.com/designer/build.html) |
| Find current work and remaining blockers | [Program #31](https://github.com/Valpatel/gyropup/issues/31), [mechanical integration #61](https://github.com/Valpatel/gyropup/issues/61), [carrier packaging #96](https://github.com/Valpatel/gyropup/issues/96) |
| Read with an agent or HTTP client | [Public reading guide](agent-guide.md), [llms.txt](https://gyropup.com/llms.txt) |
| Contribute or resume work | [Contributor orientation](../CONTRIBUTING.md), then the relevant GitHub issue and PR |

The website is a published snapshot. GitHub issues hold active work; individual reports hold evidence for their
stated revision and inputs. A current-looking model, a passing software check, or a downloadable print file does
not establish mechanical readiness. Older plans remain available for context and may contain superseded choices.

## Design and qualification

- [Requirements](requirements.md), [decisions](decisions.yaml), [milestones](milestones.yaml),
  [engineering architecture](architecture.md), [weight ceiling and historical load limits](design-weight-budget.md).
- [Mechanical review criteria and baseline history](mechanical-readiness.md), [interface standard](mechanical-interfaces.md),
  [print-source provenance](print-source-provenance.md).
- Leg: [current RS-04 mounting fit](rs04-mounting-fit.md), [historical prototype plan](leg-prototype-plan.md), [bench tests](leg-bench-tests.md),
  [rig assembly](leg-rig-assembly.md), [wiring](leg-rig-wiring.md), [safety](leg-rig-safety.md).
- Turret: [prototype plan](turret-prototype-plan.md), [next plan](turret-next-plan.md),
  [assembly](turret-assembly.md), [wiring](turret-wiring.md), [bench tests](turret-bench-tests.md),
  [physics](turret-physics.md).
- Body: [plan](body-plan.md), [next plan](body-next-plan.md), [frame](body-frame.md),
  [electrical](body-electrical.md), [thermal](body-thermal.md), [safety](body-safety.md).
- Carrier: [packaging evidence](../hardware/carrier-packaging/README.md),
  [protection candidate](../hardware/carrier-pan-protection/README.md), [service connectors](carrier-service-connectors.md),
  [insert-fit specimens](../research/carrier-insert-fit/README.md). Physical fit, wiring and printed strength remain open.

## Sources, parts and recorded evidence

- [Parts catalog format](../catalog/SCHEMA.md), [purchases](purchases.md),
  [supplier audit](../research/supply/turret-carrier-2026-10-29.md), [part-image provenance](part-image-provenance.md).
- [Reference robots](../research/reference-robots.md), [actuator interfaces](../research/actuator-interfaces.md),
  [wheel study](../research/air-tyre-hub-wheels.md), [power electronics](../research/power-electronics.md),
  [launcher study](../research/turret-launcher-study.md).
- [Structural media and its limits](structural-study-media.md), [current browser model](validation/current-model.md),
  [turret motion](validation/turret-motion.md), [carrier inspection](validation/carrier-connector-inspection.md),
  [landing highlights](validation/landing-highlights.md).

## Website

[Development and publishing](site-deployment.md) explains the static build, shared local preview and checks.
The [design notebook](https://gyropup.com/site/) lists the full published document collection. Existing document
paths are retained; this map groups them without moving their sources or changing download URLs.
