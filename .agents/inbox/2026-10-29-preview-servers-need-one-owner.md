# Preview servers need one owner and an explicit end

2026-10-29: a local listener/process/Git audit found 13 Gyropup web previews
across 11 worktrees. Eleven processes served revisions already included in the
newest preview and had no tracked changes; `git status --porcelain` reported
only `?? node_modules`. `stat node_modules` identified a dependency symlink.
Two servers read the same directory and returned identical homepage SHA-256.
The eleven older processes had approximately 907 MiB summed RSS (shared pages
mean this is not a promise of reclaimable physical memory).

Evidence commands: `ss -H -ltnp`, process cwd/start identity, `git status
--porcelain`, `git merge-base --is-ancestor OLD CURRENT`, and bounded HTTP GET
hash comparisons. Exact host/PID details stay out of this public repository.
The user authorized retiring redundant previews. Targeted SIGTERM through
verified process handles stopped the eleven old listeners; source/build
directories were preserved, and ongoing publication previews were retained
until their work was complete. Tracking: #109.

Cause: the deployment guide instructed agents to select another port when one
was occupied. The CLI accepted any PORT and provided neither ownership reuse
nor temporary lifetimes. The directory-only `node_modules/` ignore pattern
missed the dependency symlink, causing inventory to label merged worktrees as
unfinished work. Health polling kept producing requests to unused previews.

Correction: one normal address, exact served-directory status, same-checkout
reuse, explicit conflict for a different checkout, and parent-bound temporary
listeners with a hard deadline. Ignore dependency symlinks as well as folders.
The agent entry point and deployment guide direct work to this lifecycle;
real-process regression cases enforce it. See [the procedure](../domains/site-preview.md).

Limits: old checkouts and hand-written servers can bypass newer code, so process
retirement still requires ownership checks. A Git ancestor or an empty connection
snapshot does not prove no client needs a preview. Ephemeral tests own their
teardown; expiry is only a fallback. The imported server factory intentionally
does not take ownership of the caller's test lifecycle.

Independent review reproduced a startup race three times: a parent that exited
during Node module loading was replaced by a subreaper before the child sampled
its PID. CI and spawned test helpers now supply the actual launcher's PID, and a
real immediate-parent-exit regression verifies refusal to bind. Manual callers
without that identity retain the hard deadline as the pre-execution fallback.
