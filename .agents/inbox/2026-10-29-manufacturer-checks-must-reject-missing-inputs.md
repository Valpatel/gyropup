# Missing manufacturer CAD must make validation fail, not switch geometry modes

On 2026-10-29, independent review of PR #67 at `87a4b7e` pointed the process-local hardware cache at an empty temporary directory and ran `hardware_gate('base_board_screws', manufacturer=True)`. It returned `pass: true` with 28 passing checks because `available_private=True` silently substituted authored public shapes. The separate availability audit did not participate in `pass_model_checks`. The recorded candidate happened to fail on detailed inputs; that did not make the checker fail closed when inputs disappeared.

The correction removes mixed hardware loading. Both manufacturer stages preflight every private STEP input they include and return an explicit failing, unperformed-geometry verdict if any is missing. A second aggregate predicate requires all selected models to be present and valid. Public geometry remains a separately labelled mode. No tolerances or manufacturer geometry changed.

Regression command: `python tools/test-base-board-manufacturer.py` in the CAD environment. It covers an empty private cache, each single missing SKU for both stages, missing/invalid final inventory, strict hardware loading and a real public BREP positive control. Presence sentinels in partial-cache tests must never reach a geometry loader; they are not vendor models. The independent public positive control still passes 28 checks.

Limits: complete input coverage is a prerequisite, not proof of correct source identity, physical fit, thread retention, service slack or structural strength. Historical receipts retain their actual source hashes and failure state; a changed checker needs a new candidate run. Manufacturer STEP files remain private.
