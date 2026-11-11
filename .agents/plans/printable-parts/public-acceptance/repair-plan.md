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
