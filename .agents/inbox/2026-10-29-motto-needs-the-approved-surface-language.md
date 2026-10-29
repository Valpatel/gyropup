# Match the user's approved visual reference, not a generic idea of “cool”

On 2026-10-29 UTC, release f719525 displayed the requested motto using italic capitals, yellow emphasized words, chevrons and a diagonal decoration. Responsive, contrast, Markdown and interaction checks passed, and independent visual reviews found no functional blocker. The user then said the motto looked “really cheesy,” liked its text, and preferred the warning modal's depth for other site surfaces.

Evidence:

```text
Published revision: f7195253e569cefcb3c2c22dd727a4750504c503
Asset bundle: 2cfcae547cac7cb8d9f0
Prior production checks: 105 responsive route checks PASS; Chromium/WebKit portal PASS
User feedback: motto wording retained; racing-banner aesthetic rejected
Independent follow-up: italic capitals + chevrons + diagonal stripe read as motorsport branding
```

Cause: the broad word “cool” was interpreted as racing graphics instead of the user's established reference: layered navy/amber surfaces and calm typography in the warning. Numeric validation did not measure aesthetic fit.

Correction: retain the exact wording, remove the racing motifs and individual word coloring, use upright sentence-case typography and restrained layered depth. Apply softer depth to the hero, cards and primary actions while leaving safety-specific symbols in the warning. Future visual reviews must explicitly compare against this preference as well as checking function.

Limits: this records a project-specific aesthetic decision. No new implementation-mirroring test is needed for the taste judgment; the existing hero, phone and Markdown checks remain appropriate for regressions. Canonical guidance: [brand presentation](../domains/brand-presentation.md).
