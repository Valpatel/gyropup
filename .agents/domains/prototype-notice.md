# The prototype notice preserves the application underneath it

The static build injects `web/prototype-notice.html`, its CSS and its controller into every public HTML page before asset versioning and Markdown generation. Do not distribute the template as a standalone HTML page. Agent Markdown removes the duplicate dialog but retains the static footer warning. No-script visitors must be able to read and scroll the warning.

The native dialog uses explicit acknowledgement for first entry. `sessionStorage['gyropup.prototype-notice']` must equal the current notice revision (`2026-10-29-v1`); storage failures never bypass it. Updating that revision requires a fresh acknowledgement. This is a research notice, not a legal waiver or permission to operate hardware.

Opening dispatches `gyropup:prototype-notice`, gates speech/SFX without changing saved settings, invalidates pending speech, releases held turret inputs, and pauses the landing character clock. Closing preserves scene and conversation identity. Keep first-entry keyboard focus inside the dialog and keep the acknowledgement/exit actions visible while long text scrolls.

The full footer remains on scrolling pages. Full-screen tools get a compact header reopen control, with a standalone-header fallback when no shared app navigation exists. Test every header control's rectangle: page `scrollWidth` alone can miss a button clipped by an overflow-hidden header. No warning may cover play controls.

Full-screen state is not always known when the notice initializes: FEA creates its HUD after a fetch, and retries may replace it. React to relevant header/HUD additions and replacements without rescanning on every speech mutation; move one reusable reopen control and hide the footer only after it has a usable home.

Existing feature suites use `tools/test-prototype-session.mjs` to exercise an acknowledged session. `tools/test-prototype-notice.mjs` independently covers fresh/direct entry, expired/blocked storage, focus, phone geometry, retained state, held inputs, audio gates, and static/Markdown warning text. Keep those separate; an automatic acknowledgement is not evidence that the entry flow works.
