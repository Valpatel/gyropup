# Capture transient-unit properties before the unit is collected

## Dated evidence

On 2026-11-11 the reviewed public smoke command ran with `systemd-run --user --wait --pipe`. Its original receipt reported `Finished with result: success`, exit 0 and runtime 4 min 33 s. The browser report recorded `pass: true` and all eight expected images.

After completion, `systemctl show` reported `LoadState=not-found`, `MainPID=0` and inactive state. The queried `MemoryMax` and `RuntimeMax` values were default infinity values rather than a retained effective configuration. The collector’s property assertion then failed with exit 1. Independent checks established current unit/cgroup absence and browser closure, and journal `USER_INVOCATION_ID` evidence joined the start and consumed-work records.

A separate terminal recovery receipt retains the original `unit.txt` and collector failure. It does not synthesize a successful original cleanup/property receipt. No private raw logs or infrastructure identifiers are published here.

## Cause and corrective rule

The collector assumed that a completed transient unit would remain loaded for property readback. A successful transient unit can instead be garbage-collected before that query.

Capture effective properties while the unit is loaded. Keep the configured command limits, any actually observed historical effective properties and independently observed current absence as separate claims. Preserve the failed collector receipt and reconcile it with the successful work and current cleanup evidence. Do not rerun successful browser work merely to repair a receipt.

## Limits

A later missing unit and default infinity values do not establish the historical effective CPU/RAM/runtime caps. Current absence establishes only current cleanup state; the successful child/browser report does not retroactively make the original property assertion pass. The independent terminal-recovery receipt is separate from the original failed collector.
