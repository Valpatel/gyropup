# Documentation map

Gyropup is at the CAD and simulation stage. There is no assembled robot or print release. The
[prototype warning](guide/prototype-safety.md) applies to every design and download: these prototypes are unsafe,
for research purposes only, and will not be offered for sale.

<p>
<picture style="display:block;max-width:640px;margin:0 auto"><source media="(prefers-reduced-motion: reduce)" srcset="img/navigation/project-map-still.svg"><img src="img/navigation/project-map.svg" width="640" height="240" style="display:block;max-width:100%;height:auto;padding:0" alt="Fictional wheeled Gyropup robots chase and duel in a pixel workshop. Sources, test, review and reuse form a learning loop."></picture>
A fictional playground. <a href="program/physical-progress.md">Follow the real build evidence.</a><br>
<a href="https://gyropup.com/designer/sim.html">Play</a> · <a href="https://gyropup.com/designer/build.html">Build</a> · <a href="#design-and-qualification">Understand</a> · <a href="../.github/CONTRIBUTING.md">Contribute</a>
</p>

**Owner report, 2026-11-05:** first motors in hand; main motor holder and motor adapter printed.
[Physical progress](program/physical-progress.md) records the limits of that observation.

## Choose an entry point

| Purpose | Start here |
| --- | --- |
| Explore the project | [Website](https://gyropup.com), [browser playground](https://gyropup.com/designer/sim.html) |
| See published progress and evidence | [Progress](https://gyropup.com/designer/progress.html), [Build and downloads](https://gyropup.com/designer/build.html) |
| Find current work and remaining blockers | [Program #31](https://github.com/Valpatel/gyropup/issues/31), [turret print readiness #61](https://github.com/Valpatel/gyropup/issues/61), [the turret carrier #66](https://github.com/Valpatel/gyropup/issues/66) |
| Prepare for the ordered motors | [RS-04 motor tool](software/rs04-motor-tool.md), [RS-04 mounting candidate](legs/rs04-mounting-fit.md), [support-ring comparison](legs/rs04-support-study.md), [3115-900KV survey and gauge](turret/ordered-turret-motor.md), [purchase ledger](program/purchases.md) |
| Read with an agent or HTTP client | [Public reading guide](guide/agent-guide.md), [llms.txt](https://gyropup.com/llms.txt) |
| Contribute or resume work | [Contributor orientation](../.github/CONTRIBUTING.md), then the relevant GitHub issue and PR |

The website is a published snapshot. GitHub issues hold active work; individual reports hold evidence for their
stated revision and inputs. A current-looking model, a passing software check, or a downloadable print file does
not establish mechanical readiness. Older plans remain available for context and may contain superseded choices.

## Design and qualification

- [Requirements](architecture/requirements.md), [decisions](program/decisions.yaml), [milestones](program/milestones.yaml),
  [engineering architecture](architecture/architecture.md), [weight ceiling and historical load limits](architecture/design-weight-budget.md).
- [Mechanical review criteria and baseline history](architecture/mechanical-readiness.md), [interface standard](architecture/mechanical-interfaces.md),
  [print-source provenance](validation/print-source-provenance.md).
- Leg: [current RS-04 mounting fit](legs/rs04-mounting-fit.md), [unpowered fit job](legs/rs04-fit-job.md), [motor thermal model](legs/motor-thermal.md), [historical prototype plan](legs/leg-prototype-plan.md), [bench tests](legs/leg-bench-tests.md),
  [RS-04 motor tool](software/rs04-motor-tool.md),
  [rig assembly](legs/leg-rig-assembly.md), [wiring](legs/leg-rig-wiring.md), [safety](legs/leg-rig-safety.md),
  [over-command protection and torque limits](legs/leg-protection.md).
- Turret: [ordered motor interface](turret/ordered-turret-motor.md), [prototype plan](turret/turret-prototype-plan.md), [next plan](turret/turret-next-plan.md),
  [assembly](turret/turret-assembly.md), [wiring](turret/turret-wiring.md), [bench tests](turret/turret-bench-tests.md),
  [physics](turret/turret-physics.md).
- Body: [plan](body/body-plan.md), [next plan](body/body-next-plan.md), [frame](body/body-frame.md),
  [electrical](body/body-electrical.md), [thermal](body/body-thermal.md), [safety](body/body-safety.md).
- Hardware: [one folder per component](../hardware/README.md) (references, interfaces, config, inventory, bring-up),
  [the robot computer's deployment](../software/deploy/jetson/README.md), the [RS-04 bring-up checklist](../hardware/actuators/rs04/bring-up.md).
- Carrier: [packaging evidence](../hardware/carrier-packaging/README.md),
  [protection candidate](../hardware/carrier-pan-protection/README.md), [service connectors](electronics/carrier-service-connectors.md),
  [insert-fit specimens](research/carrier-insert-fit/README.md). Physical fit, wiring and printed strength remain open.

## Sources, parts and recorded evidence

- [Recovery audit, 2026-11-05](validation/recovery-2026-11-05.md): every open issue, branch and preserved worktree.

- [Parts catalog format](../hardware/catalog/SCHEMA.md), [purchases](program/purchases.md),
  [supplier audit](research/supply/turret-carrier-2026-10-29.md), [part-image provenance](validation/part-image-provenance.md).
- [Reference robots](research/reference-robots.md), [actuator interfaces](research/actuator-interfaces.md),
  [wheel study](research/air-tyre-hub-wheels.md), [power electronics](research/power-electronics.md),
  [launcher study](research/turret-launcher-study.md).
- [Structural media and its limits](validation/structural-study-media.md), [current browser model](validation/current-model.md),
  [turret motion](validation/turret-motion.md), [carrier inspection](validation/carrier-connector-inspection.md),
  [landing highlights](validation/landing-highlights.md).
- [Historical unmerged body, leg-rig and CAN drafts](archive/2026-10-31-unmerged-drafts.md): preserved source
  references, recorded failures and the issues that own remaining acceptance work.

## Website

[Development and publishing](software/site-deployment.md) explains the static build, shared local preview and checks.
The [design notebook](https://gyropup.com/site/) lists the full published document collection. Published document
and download URLs are retained; source folders group the material by domain.
