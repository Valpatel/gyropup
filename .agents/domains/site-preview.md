# One shared preview; tests own temporary listeners

The normal public-site preview uses loopback port 8899 across all worktrees and
clones on a host. `npm run preview:status` identifies its PID and exact served
directory. `npm run preview` reuses that directory if already running; another
checkout is rejected. Never work around that conflict with another persistent
port or an ad hoc HTTP server. Coordinate with the owner, stop the exact process,
then start the intended checkout. Rebuilding the selected `dist/` needs no restart.

`npm run dev` builds and starts the same managed preview. Normal serving stays
in the foreground; Ctrl+C/SIGTERM closes listeners and connections. The status
endpoint is read-only. Startup never kills or takes over a listener, and fails
if the port owner cannot be recognized.

Tests may run `node tools/serve-site.mjs --ephemeral` (an OS-assigned port by
default). `PORT=0` is the compatibility form. An explicit fixed port is allowed
only in ephemeral mode for existing CI. These CLI servers stop when their parent
changes or after 30 minutes, even if discovery/health checks keep polling them.
`--ttl-seconds N` can shorten that hard deadline. Always retain the child handle
and stop/wait in `finally`, or use a shell EXIT trap; automatic expiry is a backup.
Automated launchers also pass `GYROPUP_PREVIEW_PARENT_PID` as their own PID
(`$$` in the CI shell, `process.pid` in Node). This rejects a parent already gone
when the child begins startup. Without that explicit identity, a manual CLI can
only observe parent changes after its code starts; the hard deadline still applies.
Imports of `createSiteServer` remain test-owned and require explicit teardown.

Do not retire a process merely because its title, age, or CPU resembles another.
Verify the exact listener/PID identity, served source, ancestry and outstanding
work. Preserve worktrees and builds. The `node_modules` ignore rule includes
symlinks: a dependency link is not unfinished product source. Different loaded
builds or live clients still matter even if Git source is already merged.

Regression: `npm run test:preview` uses real child processes for shared reuse,
checkout conflicts, concurrent starts, unrelated listeners, parent death, TTL,
signals and CLI/CI compatibility. `node --test tools/test-site-ranges.mjs` covers
the unchanged static handler and media ranges.
