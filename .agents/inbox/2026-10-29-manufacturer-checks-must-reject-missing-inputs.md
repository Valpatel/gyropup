# Missing manufacturer CAD must make validation fail, not switch geometry modes

On 2026-10-29, independent review of PR #67 at `87a4b7e` pointed the process-local hardware cache at an empty temporary directory and ran `hardware_gate('base_board_screws', manufacturer=True)`. It returned `pass: true` with 28 passing checks because `available_private=True` silently substituted authored public shapes. The separate availability audit did not participate in `pass_model_checks`. The recorded candidate happened to fail on detailed inputs; that did not make the checker fail closed when inputs disappeared.

The correction removes mixed hardware loading. Both manufacturer stages preflight every private STEP input they include and return an explicit failing, unperformed-geometry verdict if any is missing. A second aggregate predicate requires all selected models to be present and valid. Public geometry remains a separately labelled mode. No tolerances or manufacturer geometry changed.

Regression command: `python tools/test-base-board-manufacturer.py` in the CAD environment. It covers an empty private cache, each single missing SKU for both stages, missing/invalid final inventory, strict hardware loading and a real public BREP positive control. Presence sentinels in partial-cache tests must never reach a geometry loader; they are not vendor models. The independent public positive control still passes 28 checks.

Limits: complete input coverage is a prerequisite, not proof of correct source identity, physical fit, thread retention, service slack or structural strength. Historical receipts retain their actual source hashes and failure state; a changed checker needs a new candidate run. Manufacturer STEP files remain private.


## 2026-10-31: copy the cache contents into an existing worktree directory

A fresh isolated `2a4b2fd` worktree already contained tracked files under
`references/vendor/`. Copying a whole cache directory onto that path created
`references/vendor/vendor/`. The RS04 producer correctly stopped before geometry:
`incomplete-geometry`, six missing pinned private inputs, and 0/0/1 checks. The
subsequent complete-membership guard rejected that diagnostic; exit 1 alone was
not mistaken for the expected eight engineering failures. Attempt 1's log,
completion code 1 and incomplete report were retained in the mechanical task.

Use `cp -aL "$task_source/." "$task_destination/"` when the destination exists,
then run the producer's private-input hash preflight before launching the long
job. On 2026-10-31 the corrected copy passed every pinned private hash, and the
same frozen producer was restarted. Never edit a missing-input report to look
like a geometry run. This is input preparation evidence, not a geometry or
manufacturing acceptance result.
