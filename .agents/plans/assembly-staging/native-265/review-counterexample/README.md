# Reject substituted prior evidence before certifying combined coverage

Independent review of frozen d8442c61 replaced all 42 prior264 report query IDs
with unrelated unique hashes. The old portable audit still exited 0 and emitted
the same accepted 44/90 receipt. [old-result.json](old-result.json) records that
reproduction; [wrong-prior-42.json](wrong-prior-42.json) and
[old-accepted-receipt.json](old-accepted-receipt.json) retain its exact inputs and
false acceptance. The latter is a rejected counterexample, not accepted evidence.
The genuine retained264 report and original accepted265 receipt remain unchanged.

[Review finding](https://github.com/Valpatel/gyropup/pull/280#discussion_r4528726930).
The corrected audit binds prior264 bytes to the report SHA/size already sealed in
its retained member manifest, and independently requires its ordered first42 IDs
of the exact90-query plan, states and result flags. The ordinary regression runs
the actual CLI with this substituted report and requires nonzero exit, no stdout
receipt and no output receipt file. It also tests the genuine report and altered
membership/order/state/completion controls without a native runtime or archive.
