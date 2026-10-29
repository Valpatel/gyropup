# Build portal: expected behavior and validation

Work tracked in [Gyropup issue 53](https://github.com/Valpatel/gyropup/issues/53), using the shared components developed in [cad-agent PR 63](https://github.com/Valpatel/cad-agent/pull/63). The preceding warning/target release, PR52, is live and hosted-verified.

| Area | Should do | Baseline behavior | Work status |
| --- | --- | --- | --- |
| Order overview | Summarize quantities, whole-pack costs and seller choices in readable sections | One long paragraph followed by a raw missing-image identifier dump | Pending |
| Parts tables | Obvious keyboard/touch sorting, including correct numeric order | Static grids and tables | Pending shared tooling |
| Build status | Remember ordered/in-hand and print progress by stable part identity | No fulfillment tracking | Pending shared tooling |
| Seller summaries | Keep text readable, including filament quantities and cost | Dark background with low-contrast inherited text | Pending |
| Product pictures | Show genuine supplier images with source links where available | Many local-only image paths are absent from the public bundle | Pending |
| Custom parts | Show an accurate image for every machined/cut item | Several CAD renders missing | Pending |
| Body print queue | Show all 13 parts and a clear duration/order summary | Missing images and compressed heading text | Pending |
| 3D downloads | Offer orbit/pan/fine zoom for each published original, with download retained | Most individual files open as raw downloads | Pending shared STL/STEP/3MF viewer |

Acceptance covers actual source quantities/prices, unknown costs, stable state through filtering/sorting/reloads, import/export validation and storage denial, keyboard and phone interactions, image provenance and broken-image handling, every published 3D file's viewer mapping, actual parsing, and error/retry behavior. Model display does not establish physical fit or safety.

This page records an in-progress change. Runtime and deployment evidence will replace the pending states as each requirement is implemented and independently checked. Catalog and hardware selections are unchanged by this presentation work; a status checkbox does not place an order.
