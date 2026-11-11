# A review preflight must use the target repository's actual contract

2026-11-11, #281 full acceptance B. The coordinator's separate read-only preflight
mistakenly required a cad-agent-style machine marker in Gyropup source review
5865337208. The actual review was COMMENTED, at exact head 90232f8b, and explicitly
stated independent GPT-6 source PASS under Gyropup's rules. The false predicate
raised `Source review missing or dismissed`. The exact original receipt SHA-256
is c9aea9211c131fa538b0f734d5e73dc43a501842fc3f3bd3e65147b081f605ff;
the [privacy-safe receipt](../plans/printable-parts/public-observation/coordinator-preflight-failure.json)
and [independent disposition](https://github.com/Valpatel/gyropup/pull/320#issuecomment-6807901966)
record the correction and limits.

The cause was borrowing another repository's review-format predicate without
checking Gyropup's AGENTS/CONTRIBUTING/review workflow. Correct the predicate to
the actual target contract: exact reviewed commit, permitted review state and
explicit independent verdict, resolved findings and every current required CI
check including aggregates. A source verdict is still not exact-action approval.
Do not invent approval, discard a block, or infer gate completion from most jobs.

The predicate correction changed no runtime input, review, seal or action and
started no earlier browser/unit/marker. It is not another public attempt and does
not clear later B failure. Preserve read-only preflight failures separately from
actual execution receipts so recovery does not replay work or miscount attempts.
This lesson records the operator mistake; it adds no new approval format or
runtime waiver to the acceptance harness.
