# Gyropup working rules

Use an isolated worktree from `dev`; preserve other sessions' source, builds and
processes. Track substantial work in an issue and PR. Read `.agents/SYMPTOM-INDEX.md`
before rediscovering a known incident, and record new durable findings in `.agents/`.
Changes require relevant checks and independent review before merge.

## One shared website preview

Read [the preview lifecycle](.agents/domains/site-preview.md) before starting a
local website server. Use `npm run preview:status`, then `npm run dev` or
`npm run preview`. Normal previews share `http://127.0.0.1:8899`; do not invent a
new port, inline server, `http.server`, or detached per-worktree daemon to bypass
an occupied address. The launcher reuses the same served checkout and rejects a
different one. Coordinate with the current owner before stopping it or changing
the selected checkout; rebuilding its `dist/` updates the existing preview.

Tests may use `--ephemeral` (30-minute maximum, parent-bound) or import
`createSiteServer` and close it in `finally`/test teardown. Always record the
address and clean up the exact process you started. Keep at most one deliberate
user-facing preview after validation, and stop temporary captures/comparisons.
Never kill by process name or stop a shared terminal/agent scope.

## Public repository, public site

Never commit or publish absolute home paths, compute host names, LAN or tailnet addresses, or private repository
names. Generators write repository-relative paths; notes name a machine by its role ("a CAD host"). Run
`npm run build && npm run test:privacy`; see [the incident](.agents/inbox/2026-11-01-generated-exports-carried-home-paths.md).
