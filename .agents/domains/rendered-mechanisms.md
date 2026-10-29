# Rendered mechanism frames

Canonical product convention and verification: [turret motion](../../docs/validation/turret-motion.md).

CAD millimetres `(x forward, y left, z up)` map to page metres `(y,z,x)`. Child joint origins are relative to their parent; exported vertices are relative to their owning joint. Rotating parts require independently checked physical datums; motor-case envelopes remain on the fixed parent. Keep effects, pocket balls and firing paths in the same documented frames.

Run `npm run test:turret` against a built local site or set `SITE_URL` to the deployed site. The test compares actual rendered vertices to independently audited CAD intent and must reject a deliberately displaced shaft. It does not certify physical fit or continuous collision clearance.
