# Compare retained permissions against their actual lifecycle

On 2026-11-10 frame-only job 262 exited1 at recipe line 38 before any core checkout
or CAD query. Comparing captured inventories to the original 261 manifests found
486 candidate and 242 guide entries with identical names, SHA256 and sizes; every
producer 0600 mode had become0640. The four archived input seals still matched.
The installed epilog matched retained source SHA256
`7181d06f53a4a2ce84cb39bb376e67520c156471c689ed368222f483db67dce8`;
its lines 125/127 strip other/set-id bits and add group read during terminal freeze.
See the [sealed failure and diagnosis](../plans/assembly-staging/native-262/README.md).

Command/output evidence on 2026-11-10:

```text
fleet-run fetch 262 <fresh-owned-directory> --outputs-only --max-mb 256
recipe line 38: AssertionError; exit 1; phases={}
python3 -B -m unittest discover -s tests/site/assembly -p test_robot_data.py
Ran 8 tests; OK (0.174s)
```

Cause: producer-time file metadata was mistaken for post-job metadata. The
full-dictionary guard correctly refused the unexpected lifecycle state; it did
not reveal a CAD collision or changed input bytes. Candidate before/after
inventories were identical. Guide/hardware/tracked before-captures were absent,
so their false summary values cannot be interpreted as preservation failures.

Corrective rule: retain producer manifests and byte seals without rewriting
them. For this collector's 0600 regular files, require the exact documented0640
retained mode, unchanged membership/hash/size, and an exact actual-mode
before/after inventory. Reject unexpected producer/retained modes, content or
membership. `robot_data.verify_frozen_inventory` and its ordinary regression
controls encode that narrow contract without changing files. A new attempt
requires a fresh reviewed packet; preserve the failed attempt as evidence.

Limits: this permission transition applies to the recorded fleet epilog and
collector mode contract. It does not authorize ignoring modes generally, fixing
permissions, changing expected byte hashes, or claiming native validation.
