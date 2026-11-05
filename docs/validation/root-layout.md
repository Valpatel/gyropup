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

## Live server branches versus cached refs

`git ls-remote --heads origin` on 2026-11-05 returned **seven actual server heads** at the following
snapshot. The earlier [recovery audit](recovery-2026-11-05.md) inventories local and remote-tracking refs;
remote-tracking refs can outlive their server branches after merges and are not proof that a branch is open.
Local branches and worktrees are preserved regardless of server presence.

| Live server branch | Exact observed head |
| --- | --- |
| `dev` | `b408b59bb995c9d155e277d694749f256ad4cc88` |
| `docs/recovery-navigation-20261105` | `9150bd3da0b7efcda43758694283a16fcaa46d16` |
| `feat/turret-tilt-range` | `eeccc07bacfca95464c703f6d730f975781f1fe0` |
| `fix/motor-day-render-inputs` | `8ddcb4fe0e9d1c5a097356be013e6c79495409a4` |
| `main` | `325a8b566456d07f6464ca75824510aee6ef9eea` |
| `refactor/root-presentation-layout` | `2cdb2fd455e8da9a9466aec4f97b0addb6756fc1` |
| `study/body-sheet-metal` | `4585596492a75a08489ef99b6b9e3b8334c5e5ee` |

The server no longer advertised `feat/leg-command-limits`, `feat/turret-offboard-compute`,
`fix/turret-box-rebuild` or `fix/turret-gates-current`, even though cached remote-tracking refs still existed.
Those caches were not deleted or treated as unmerged server work. The observed heads above precede this
follow-up documentation commit; consult the command again before acting on a branch.
