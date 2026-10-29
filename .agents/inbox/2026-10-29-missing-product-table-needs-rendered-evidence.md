# Verify the rendered cause before classifying a missing product table

Date: 2026-10-29. Selected part: McMaster-Carr 91290A113, M3 × 8 mm socket-head screw.

## Evidence

The cache-first lookup failed with `is not a product page (no specification table)`. No manufacturer STEP was cached; the 2026-10-27 specification metadata is historical evidence only. A single inspection with the existing cad-agent McMaster session returned HTTP 200 at 2026-10-29T08:16:39Z, with an explicit rendered login requirement, zero specification rows, and zero CAD selectors. The screenshot was inspected privately; no page/form contents, credentials, browser profile data, or vendor geometry are published. The session closed normally and no product catalog or geometry changed.

## Cause and corrective rule

The fresh session encountered a login gate. Missing markup alone does not identify authentication failure: inspect the response and rendered state before classifying the cause. Stop repeat parser attempts after a confirmed login gate, and use an authorized interactive session when available. Keep the exact selected part and historical specifications separate from current CAD availability. Do not substitute an authored envelope for a verified manufacturer model.

## Limits

This observation applies only to this session and time. It does not establish that the manufacturer model is unavailable, that all sessions require login, or that the historical dimensions changed. The exact manufacturer STEP remains a prerequisite for the private detailed check; download, normalization, and dimensional validation are still outstanding.
