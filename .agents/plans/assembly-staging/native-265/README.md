# Preserve blocked controls separately from sequence qualification

Job 265 completed two explicitly selected probes from the unchanged 90-query
plan. Both are blocked in the original 261 CAD snapshot: the old-order left
motor arrives through an installed hip frame, and its wrong-side inward arrival
starts inside the cheek. The actual native CLI exited 1. The outer wrapper exited
0 because the requested diagnostic execution completed and retained its findings;
that is not a passing geometry verdict. All ten preservation guards passed.

| Control | Fixed instance | Overlap at authored start mm³ |
| --- | --- | ---: |
| Old motor-after-hip order | L.hip_frame | 115749.939463 |
| Wrong-side inward motor | cheek_left | 15823.005812 |

Both results report `[null, 60]`: intersection already exists at the authored
60 mm starting offset. There is no last-clear/contact-onset bracket. These are
CAD/viewer path findings using the source's motor envelopes, not measured motor
fit or physical assembly approval. Original body/leg geometry and the old belly
bay remain unchanged; this snapshot does not describe the later battery redesign.

The [author audit](artifact-audit.json) and [independent audit](independent-audit.json)
verify all 485 archived and actual files, 475 preserved original frame inputs,
the full/effective plan seals, 472 exact progress records, actual CLI status and
all preservation/cleanup guards. The normal phase acknowledges all 472 flushed
and file-fsync records with no uncertain tail; this records file operations,
not a hardware durability guarantee. The [execution receipt](execution.json)
preserves raw terminal/argv hashes while removing private command paths.

Across the distinct 264 and 265 executions, 44 of 90 query identities have a
completed record: 36 clear finite checks, six terminal seats and these two blocked
controls. Forty-six remain uncompleted. The 88 queries unselected in this job
include the 42 earlier completed queries; they are not all globally unchecked.
Terminal seats provide no transient-path verdict. Existing hip/cheek rigid
contacts retain their [baseline classification](../native-264/seat-classification.json),
without an overlap exemption. Support, tools, continuous clearance, the entire
sequence and physical/manufacturing readiness remain unqualified.

```text
fleet-run fetch 265 <fresh-owned-directory> --outputs-only --max-mb 256
python3 -B audit.py <fetched-job-directory> <product-checkout>
python3 -B independent-audit.py <fetched-job-directory> <263-member-manifest> <full-plan> <264-report> <optional-fresh-receipt>
```

The portable independent audit replaces only private path literals with explicit
arguments and makes its optional receipt exclusive. Its assertions and original
receipt are preserved; replay reproduced that receipt byte for byte. The
[checkpoint](checkpoint.json) seals all retained evidence and reviewed action
identities. [Independent post-action acceptance](https://github.com/Valpatel/gyropup/issues/276#issuecomment-6775076990)
covers scoped execution/artifact correspondence. It grants no further native run,
geometry adoption or whole-robot pass.
