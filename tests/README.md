# Tests

Checks are grouped by the behavior or evidence they protect, separately from the tools that produce it.

| Home | Coverage |
|---|---|
| [hardware/](hardware/) | Body, legs, turret, interfaces, inventory and manufacturing |
| [control/rig/](control/rig/) | Driver vectors, bridge lifecycle and bench control |
| [site/](site/) | Browser controls, models, media, layout, loading and content |
| [software/](software/) | Software-specific checks such as pronunciation |
| [evidence/](evidence/) | Report, media and refresh consistency |
| [fixtures/](fixtures/) | Recorded geometry references; unchanged identities are part of the checks |

Use the commands in [package.json](../package.json) and the applicable [workflows](../.github/workflows/). Browser checks require a built site. CAD/receipt checks may require their pinned toolkit and retained inputs; preserve failures instead of recomputing hashes to make them pass.
