# Sampled thread alignment does not prove complete mating

On 2026-10-29, the carrier review found reduced overlap in twelve material rays after rotating the detailed 91290A111 screw by +153° about its seated axis. The samples were diagnostic and retained nonzero overlap. They could not establish global clearance.

Evidence: released cad-agent `2ad4269`, exact asserted private input hashes, `tools/volume_probe.py prepare` with nested rigid matrices and a 900 s deadline. The corrected run started at `2026-10-29T11:32:53Z`; its final messages were `START Boolean common`, `START Boolean cut_a`, `RUN-DONE rc=124`. It produced no completed volume/conservation receipt. The preceding invocation rejected flattened matrices before importing geometry. Commands, sanitized logs, hashes and limits are in [the bounded probe record](../../research/thread-mating-2026-10-29/README.md).

Cause and rule: local material-ray sampling is not an exhaustive BREP relation. The whole-geometry preparation did not finish within its budget; that timeout does not reveal clearance, interference or invalidity. Retain an inconclusive state. Do not infer a global pass from a few improved rays, copy phase to another part, move a required seat, or relax an overlap threshold to hide an unresolved result.

Keep public no-thread preview geometry separate from private detailed-thread qualification. Seat, hole, tip clearance, engagement, tool access and physical coupon checks remain independently required. No expensive timeout-dependent regression is asserted as a deterministic test; the released toolkit's valid-solid, uncertainty and conservation controls remain in force.
