# Mounted workspaces need Git identity checks before the build

On 2026-11-11, the first bounded tablet comparison for PR #315 stopped in
PREPARE before either browser arm ran. The unchanged builder at source
`84f8b9b91c4af99203005e5d976c3f58d3c8c355` called `git ls-files -z` at
`tools/site/build-site.mjs:27`; Git returned status 128:

```text
fatal: detected dubious ownership in repository at '/work/source'
```

The container exited 1 without an OOM or cap hit. The original failed logs,
terminal cleanup proof and zero-arm outcome were collected and independently
reviewed in [the prepare-failure review](https://github.com/Valpatel/gyropup/pull/315#pullrequestreview-5856106896).
This was a mounted-checkout trust failure, not evidence about tablet readiness.

The corrected executor trusts exactly its disposable `/work/source` mount
through counted, protected Git configuration in the container process
environment. It removes inherited counted/parameter configuration, disables
system/global-user configuration for that process tree, and writes no Git
configuration file. Never turn Git's diagnostic suggestion into a permanent
host-global or wildcard trust exception.

Before the normal builder, run real `git ls-files -z`, `git rev-parse HEAD` and
`git rev-parse HEAD^{tree}` in the mounted workspace. Require the frozen head,
tree and tracked-file count, and retain the Git version and trust scope. On
2026-11-11 at 09:14 UTC the corrected real prepare recorded Git 2.43.0, the
source above, tree `bc23795fd01eb1cc387f2a49b3c05ff4f558f53c`, and 4,399 tracked
files. The unchanged builder then succeeded and emitted that actual source
revision in `dist/version.json`.

The [independent action review](https://github.com/Valpatel/gyropup/pull/315#pullrequestreview-5856182802)
exercised the actual environment helper with real Git: a different owner and
a wrong trusted path each retained the status-128 failure; the exact path
allowed the identity commands; inherited wildcard entries were removed;
wildcard/relative inputs were rejected; user-global configuration bytes stayed
unchanged. These are executor controls, not new product tests or simulated
successful browser runs.

Keep the failed run and its one-use intent intact. Use a separately reviewed
fresh execution namespace after correcting setup; never reset an intent to
rerun an ambiguous submission. Source, browser and dependency identity checks,
original test deadlines, resource caps and terminal cleanup still apply.

Limits: successful preparation establishes the mounted workspace and build
identity only. It does not clear the original tablet failure, validate guide
images, grant a CI waiver, or qualify CAD for manufacture. The actual two-arm
outcome and final normal CI require their own evidence.
