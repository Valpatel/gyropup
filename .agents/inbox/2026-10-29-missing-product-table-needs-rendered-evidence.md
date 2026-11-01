# Verify the rendered cause before classifying a missing product table

Date: 2026-10-29. Selected part: McMaster-Carr 91290A113, M3 × 8 mm socket-head screw.

## Evidence

The cache-first lookup failed with `is not a product page (no specification table)`. No manufacturer STEP was cached; the 2026-10-27 specification metadata is historical evidence only. A single inspection with the existing cad-agent McMaster session returned HTTP 200 at 2026-10-29T08:16:39Z, with an explicit rendered login requirement, zero specification rows, and zero CAD selectors. The screenshot was inspected privately; no page/form contents, credentials, browser profile data, or vendor geometry are published. The session closed normally and no product catalog or geometry changed.

## Cause and corrective rule

The fresh session encountered a login gate. Missing markup alone does not identify authentication failure: inspect the response and rendered state before classifying the cause. Stop repeat parser attempts after a confirmed login gate, and use an authorized interactive session when available. Keep the exact selected part and historical specifications separate from current CAD availability. Do not substitute an authored envelope for a verified manufacturer model.

## Limits

This observation applies only to this session and time. It does not establish that the manufacturer model is unavailable, that all sessions require login, or that the historical dimensions changed. At that checkpoint, exact STEP download, normalization, and dimensional validation were outstanding.

## Later acquisition supersedes the missing-input status

At 2026-10-29T13:04:12Z a single standard cad-agent session successfully downloaded the proposed support's exact 90592A085 nut. That changed access evidence justified one later sequential retry of 91290A113, which downloaded successfully at 13:07:22Z (HTTP 200). Both sessions closed normally; no credentials, account changes or access-control workaround were used. The earlier login observation remains true for its own session.

Offline normalization with the existing project tool produced a 5.5×5.5×11.0 mm screw envelope (8 mm shaft plus 3 mm head) and a 6.3083×5.5×2.4 mm nut envelope (5.5 mm across flats). Sources, full specification tables, prices, private file hashes and topology observations are recorded in `research/carrier-service-connectors/support-hardware-catalog.json`. The raw and normalized models stay private. These observations close the exact-input acquisition gap; they do not establish assembled thread fit, engagement, retention, tool access or physical acceptance. The historical product catalog pending note must be reconciled when this candidate is promoted with regenerated source-bound artifacts.

## Recurrence on 2026-10-31: 5972K86 (6301-2RS), issue #29

The knee bearing's product page (McMaster-Carr 5972K86) showed a login prompt and no specification rows or CAD controls in two sessions on 2026-10-31: the first lookup and the one allowed retry. `cad-agent mcmaster` reported both as `is not a product page (no specification table)`. The public search page for the trade number still listed the part number, the price ($12.53) and the dynamic load rating, but not the static rating C0.

The static rating C0 was taken from the bearing maker's own datasheet, the SKF 6301-2RSH product page (C0 4.15 kN). `catalog/hardware.json` `bearing_6301` records both sources. It also records that McMaster's C0 is unconfirmed and must be checked on the page before the McMaster part replaces the SKF one. No envelope stands in for a vendor model: the knee bearing is drawn from its catalogue dimensions as before (`cad/fivebar.py` `bearing()`). The cad-agent tool's misleading message is filed as toolkit feedback, asking it to detect the login text.
