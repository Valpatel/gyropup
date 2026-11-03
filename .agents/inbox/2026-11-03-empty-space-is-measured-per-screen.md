# Empty space is measured per screen, scrolled like a reader, not in a full-page screenshot

On 2026-11-03 the owner reported that the landing page "has large empty sections of the screen … on mobile". On a
phone, the joins between the landing page's sections ("01 / The big idea", "02 / An experiment you can explore",
"03 / The systems behind the play") left blank bands of up to 0.24-0.29 of a phone screen's height (0.26-0.35 of a
wider screen), measured from the page's layout by `npm run test:empty-space`: the section padding
(100 px a side, 64 px on phones) was desktop-sized, and a card's bottom margin plus the next section's top padding
doubled it. At 390 px the build steps' links fell into the 32 px number column and wrapped one word a line.

A full-page screenshot misled the first look: lazy step pictures came out as empty white boxes, although each one
paints when a reader scrolls to it.

## Corrective rule

Space between sections comes from one screen-sized step (`--gp-step` in `web/landing.css`, a `clamp()` of the
screen's width and height), never a fixed desktop figure. A join is two steps, so a step stays near a fourteenth of
the screen's height.

## Check

`npm run build && npm run test:empty-space` (CI: `browser-validation (layout)`). It scrolls every page one screen at
a time at five sizes in both themes, and fails on a blank band over the size's limit (0.18 of a phone screen, 0.22
of a wider one), a picture box painted blank once in view, or text squeezed to a word a line. Findings name the
elements on either side and leave an outlined screenshot in `test-results/empty-space/`. Planted defects run first
and must each be caught. `node tools/test-empty-space.mjs --report` lists every page's worst band.
