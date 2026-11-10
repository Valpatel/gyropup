# Derive interrupted native coverage from the plan and retained prefix

On 2026-11-10 selected-pair job 264 reached its reviewed 300s native-phase cap.
The process-group reaper killed/reaped the wrapper and native child; all ten
preservation guards passed. The result remains failed/incomplete. Command/output:

```text
fleet-run log 264
native-pairs: timed_out=true; seconds=300.04766771616414; group_gone=true
worker exit 1; 42 completed pair events; 48 queries have no completed event
python3 -B audit.py <fetched264> <product-checkout>
artifact_audit_pass=true; native_study_complete=false
```

The [sealed evidence](../plans/assembly-staging/native-264/README.md) retains 553
JSONL records: 42 completed pairs, one next start, 36 clear and six terminal-seat
results. The phase's 552 flushed/512 file-fsync-acknowledged counts and uncertain
tail remain distinct from observed retained bytes. No Python finally ran after
SIGKILL, so final unchecked IDs, world statistics and nativeCLI exit record are
absent. Forty-eight uncompleted queries are derived from the full 90-query plan
minus completed events; an absent result is never clear.

Cause: bounded native work legitimately exceeded the budget, and process death
cannot promise Python finalization. Corrective rule: persist source-bound plans
and started/completed records before work, retain the complete observed prefix,
and reconstruct coverage without requiring final-only fields. Keep primary cap
and cleanup evidence. Every failed or undecided row remains failed; distinguish
terminal seating checks from transient paths. Smaller explicitly reviewed
unperformed controls are a substantive next step; do not automatically retry or
raise the whole campaign's cap. The ordinary CLI test kills an owned explicit
dependency-double query and verifies running/uncertified partial evidence.

Limits: file flush/fsync acknowledgements are not power-loss certification.
Six seat overlaps and 36 finite clear results do not qualify the assembly or its
continuous clearance/support. Preserve printing leg source/exports; classify the
hip/cheek seating overlap before proposing geometry changes or exemptions. Its
exact volume/centroids already exist in retained pre-candidate rigid-contact
records; this numerical match does not make it a qualified insertion contact.
