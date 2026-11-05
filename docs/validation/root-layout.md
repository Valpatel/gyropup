# Repository-root layout migration

The owner requested a smaller, more legible repository entrance on 2026-11-05. This first source grouping reduces
**31 tracked root entries to 28**, excluding `.git`, local dependencies and generated builds.

| Source before | Source now | Consumers and public behavior |
| --- | --- | --- |
| `deploy/jetson/` | `hardware/deploy/jetson/` | Installer resolves the checkout one directory higher; staged-install checks exercise its default. Hardware links, structured inventory and CI paths follow the move. |
| `index.html` | `designer/home.html` | The builder copies it to `/index.html`; it is excluded from the designer file listing to avoid a duplicate home page. Landing source checks read the new path. |
| `wrangler.toml` | `.github/wrangler.toml` | Output is `../dist` relative to the config. `npm run deploy` uses Wrangler’s `--cwd .github` because Pages refuses custom config paths. Git-integrated publishing still builds at the repository root with output `dist`. |

The published homepage, `/web/` assets, simulator routes and existing engineering downloads retain their paths.
Deployment documentation is now part of the hardware document collection. Existing linked worktrees and their
uncommitted changes remain untouched.

## Next groupings

The larger cleanup stays open in [#219](https://github.com/Valpatel/gyropup/issues/219).
Moving `web/` into designer also moves source paths bound by the highlight receipt. That requires a genuine
capture/encode run and updated consumers. CAD, catalogue, design, research and reference movement requires its
own dependency inventory and, where bound, regenerated receipts. Historical evidence retains its original identity;
source guards are not loosened to make a move pass.
