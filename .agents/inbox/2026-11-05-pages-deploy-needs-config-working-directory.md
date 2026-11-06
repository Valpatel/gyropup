# Pages deploy finds its config through the working directory

On 2026-11-05, the repository-root cleanup moved Wrangler configuration under `.github/`.
Before running a deployment, inspection of the installed Wrangler 4.154.0 CLI showed that
`pages deploy` explicitly rejects a supplied `--config` path.

Evidence (read only, no deployment):

```text
node node_modules/wrangler/bin/wrangler.js pages deploy --help
GLOBAL FLAGS: --cwd Run as if Wrangler was started in the specified directory

rg 'pages deploy custom config unsupported' node_modules/wrangler/wrangler-dist/cli.js
"Pages does not support custom paths for the Wrangler configuration file"
```

Cause: Pages has its own config-discovery path, unlike commands that accept custom config filenames.
Use `wrangler --cwd .github pages deploy ../dist`; declare `pages_build_output_dir = "../dist"`
in that directory's `wrangler.toml`. Keep Git-integrated Pages output at root-relative `dist`.

Limits: this establishes CLI argument/config path behavior for the installed version. It does not
establish authentication, project access, DNS access or successful publication. Recheck on an upgrade.
