# Repair public acceptance evidence without changing the product

Refs #281. Actual main delivery is b894a51c; final-source fixtures remain useful,
but full public checklist acceptance is outstanding. No browser execution is
part of this follow-up authoring/checking step.

The original public attempt A failed at an orders screenshot after one misframed
queue PNG. It admitted six JS/CSS assets, never HTML, and its positive horizontal
measurements did not establish visibility through nested scrolling panels. V2
admitted all seven exact identities, then failed before any screenshot at a
five-second Playwright scroll/stability wrapper. Its collector also incorrectly
combined the root document rectangle with viewport clientHeight. V3 corrected
those test mechanisms and produced two correctly framed real desktop PNGs, but
overall failed when graceful browser close exceeded its unchanged 15-second
bound. These are separate failed outcomes; none supplies full/PDF acceptance.

## Implementation and verification contract

- Keep the four raw JS/two built CSS identities exact. Distinguish compiled HTML
  from its actual deployment response by full hashes and one explicitly bound
  byte insertion. Reject unexpected content; admit all seven before capture.
- Treat the standards-mode HTML root as a viewport in viewport coordinates.
  Preserve BODY, planner and table-wrapper clips. Reject unsupported viewport,
  zoom or overflow-propagation profiles. Retained V2 geometry must remain clipped
  after the root-only correction.
- Pin the same real table/header/document, perform one native instant/center/
  nearest scroll within the existing total five-second bound, then require two
  passive geometry samples 100 ms apart to agree within one pixel, valid hits
  and unchanged horizontal offsets. Record unavailable/unsupported/unstable
  outcomes. Keep existing alignment and full/matched/status/12-PDF requirements.
- Observe required screenshots with the existing passive helper and unchanged
  30-second bound. Preserve every capture/error and prohibit fallback/retry.
- Add passive cleanup phase timing/status only. Context close remains five
  seconds and browser close 15 seconds; failure stays failure even when the
  separate owned-cgroup collector proves terminal emptiness.
- Run pure geometry/native-scroll/HTML/observer/cleanup/admission controls and
  static/privacy checks. Do not start a browser, unit, server, install or capture.
- Retain public-safe measured outcomes and the root/identity/cleanup lessons in
  existing repository evidence/guidance and symptom index, with immutable hashes.
  Keep concrete providers/contracts/seals private and templates disabled.

Independent GPT-6 source review and normal delivery gates follow coherent source.
Any later full acceptance needs a separately bound/reviewed concrete packet and
its own authorization; this PR does not close #281 or excuse historical failures.
Printed legs, CAD, product assets, rendering, toolkit and application behavior
remain outside this change.

## B follow-up: ensure panel state before choosing an action

Full B remained failed after two correct desktop images: made's helper repeated
a Buy click despite a selected Buy flag, then native actionability timed out. No
made visibility or motion sample was captured. The narrow repair uses coherent
sole selected-tab/panel plus connected CSS-rendered target proofs before/after
zero-click reuse; genuine Print/Buy transitions retain one native click and the
existing visibility wait. Bounded passive receipts keep native errors unchanged.
This is a helper-contract correction, not an app/environment cause or performance
fix, and it cannot retroactively turn B into a pass. Failing-state controls and
independent source review/normal CI precede any separately reviewed future action.

## C preserves a measured failure without a speculative repair

The [selected C receipt](../public-observation/attempt-C.json) records actual
selected Buy/made target reuse, native framing and visible grid proof on reviewed
`9f42715f`. Queue/orders captures returned; made exceeded 30 seconds. Preparation,
fonts/layout and restoration returned, while no native capture reply was observed
before detach. All cleanup returned and the exact owned cgroup was empty. Overall
C remains failed, with no made/mobile/PDF/state result or established cause.
This update adds only evidence/lessons, not a helper change or another attempt.
