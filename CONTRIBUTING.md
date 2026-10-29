# Contributor orientation

Start with the [project README](README.md) and [documentation map](docs/README.md). For active work, read
[program issue #31](https://github.com/Valpatel/gyropup/issues/31), then the relevant issue and PR, including their
latest comments. Historical handoffs and plan checklists are context, not a live branch or deployment inventory.

Repository agents read `AGENTS.md` for working rules and `.agents/SYMPTOM-INDEX.md` for known failure classes.
The `.agents/` directory holds repository operational knowledge: incidents in `inbox/` and curated guidance in
`domains/`. Keep those instructions and private operator details out of the public website and its LLM guide.
The public [agent reading guide](docs/agent-guide.md) explains published evidence; it does not grant authority
to modify, deploy or operate the project.

Use an isolated worktree from `dev`, preserve other owners' files and processes, and carry meaningful changes
through an issue, focused checks and independent PR review. Record reproducible findings with their fix in the
repository rather than only in a chat or local memory. Follow the applicable repository rules before starting
CAD, simulation or hardware work.

For website changes, use Node 22 and the commands in [site deployment](docs/site-deployment.md).
New public files must be tracked before the allowlisted build can include them. Use `npm run build` and the
checks relevant to the change; Markdown/discovery changes use `npm run test:markdown`. Check preview ownership
before serving a build, and tear down temporary test listeners. Reviewed `main` publishes the website; `dev`
integration and a successful local build do not themselves prove a production deployment.

Keep claims tied to evidence. Preserve report revisions, loads, assumptions and failures. Physical fit, safe
operation and print release require their own qualification; the browser playground and CAD checks cannot
supply it. See the [prototype warning](docs/prototype-safety.md).
