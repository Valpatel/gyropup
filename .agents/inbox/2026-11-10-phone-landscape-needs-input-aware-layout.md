# A phone in landscape needs an input-aware compact-layout check

2026-11-10, independent review of PR #286 at runtime source `82aa0e61`.

## Evidence

The review used actual Chromium with an 844×390 context, `isMobile:true` and
`hasTouch:true`, native fullscreen and Robot selected. Its recorded output was:

```text
2026-11-10: actual phone-landscape browser probe
mobile:false, coarse:true, fullscreen:native
Parts: x16 y156 width150 height218
Tools: x678 y156 width150 height218
Instructions: x426 y156 width240 height218
```

The first author regression used `hasTouch:true` but omitted `isMobile:true`, and
expected every viewport wider than 760px to use desktop panels. It checked the
wrong contract at the very boundary that needed a counterexample. The actual
review receipt is retained in `plans/instruction-docking/phone-landscape-before.json`.

## Cause and correction

Width alone cannot distinguish a short touch phone from a desktop browser of
similar width. Keep the ordinary <=760px compact rule, and also use the compact
sheet when width <=1000px, height <=500px and the primary pointer is coarse.
Apply the identical media query to CSS and workspace behavior. The short coarse
layout can keep the toolbar in one row when at least 600px wide; portrait and
fine-pointer desktop keep their existing toolbar contracts.

The persistent regression now uses an actual mobile/touch browser context and
checks 844×390 while fullscreen, every sheet pane and expanded instructions. A
separate fine-pointer 844×390 browser must still retain three independent desktop
panels. Normal 1024px desktop panel coverage remains unchanged. Record the input
mode as well as viewport dimensions in browser receipts.

## Limits

These bounded layout heuristics distinguish the covered phone-landscape case;
they are not hardware identification. A short ordinary browser window may need
natural page scrolling. This is presentation evidence, not physical qualification.
