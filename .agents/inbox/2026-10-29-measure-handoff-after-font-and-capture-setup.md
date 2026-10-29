# Capture the handoff baseline after fonts and screenshot setup settle

On 2026-10-29 UTC, hosted Chromium validation of production `1475902b25813d4be378aef36c307ec605b0bc30` (assets `66439acf6bf81af9e305`) failed the strict hero handoff assertion at 320×568, DPR2. The baseline was taken before explicitly loading fonts and taking the loading screenshot. The original failure remains in `/tmp/gyropup-pr59-live-hero-chromium-first-failure.log`:

```text
$ SITE_URL=https://gyropup.com node tools/test-hero-preview.mjs
AssertionError: Loading handoff does not move the hero frame
before: { x: 16, y: 77.15625, width: 288, height: 444 }
after:  { x: 16, y: 76.40625, width: 288, height: 444 }
```

The diagnostic probe held the model module while recording bounds before fonts, after fonts, after the screenshot, immediately before module release, and after ready. Three fresh ordinary runs were stable because Inter had already loaded. A controlled delayed-Inter run reproduced the exact difference before releasing the model. Delaying only JetBrains Mono did not reproduce it. Command and selected output from `/tmp/gyropup-pr59-phase-fonts/results.json`:

```text
$ node /tmp/gyropup-pr59-phase-fonts.mjs
Inter delayed, beforeFonts: scrollY=815, hero.y=77.15625, documentY=892.15625
Inter delayed, afterFonts:  scrollY=776, hero.y=76.40625, documentY=852.40625
afterScreenshot / beforeRelease / ready / ready2Frames: identical to afterFonts
hero size at every phase: 288×444; x=16
ready poster and canvas: x=16, y=131.40625, width=288, height=257
page errors: []
```

The Inter swap reduced the hero's document position by 39.75 px; browser scroll anchoring moved by 39 px, leaving a 0.75 px viewport difference. The original baseline attributed this earlier setup change to the later model handoff. This was not evidence that the poster and canvas were misaligned.

Correction: finish explicit font loads, two rendered frames, the loading screenshot and another two frames while the model remains held. Capture the strict baseline immediately before releasing the module. The existing harness now deliberately holds Inter in its DPR2 phone case and emits phase receipts, retaining the exact bounding-box equality and all silhouette, color, size and layout assertions. No application presentation changes or tolerance increases are involved. Reproduce with `SITE_URL=https://gyropup.com TEST_OUTPUT=/tmp/gyropup-hero-measurement-live npm run test:hero`; select WebKit with `PLAYWRIGHT_BROWSER=webkit` and the installed browser cache as needed.

The earlier production WebKit hero suite and all 105 responsive route checks passed; the original Chromium run remains a failure. Those prior results do not substitute for running the corrected harness in both engines. The probe paths above are local diagnostic evidence; the measured values and regression are recorded here so the cause is recoverable without them.

The first corrected WebKit run also exposed a font-state probe limitation: `document.fonts.check('600 14px Inter')` returned true while the intercepted Inter request was still held. A focused fresh-browser probe (`node /tmp/gyropup-webkit-font-state.mjs`, results `/tmp/gyropup-webkit-font-state.json`) showed the registered Inter face in `error`, then `loaded` after the held response was released and the explicit font load completed. The regression therefore checks the registered FontFace statuses directly: at least one matching face exists, none is loaded while held, and every matching face is loaded before the baseline. FontFaceSet.check alone does not prove that the intended web font loaded.

Limits: this isolates the poster-to-canvas handoff. It does not certify zero font-related layout shift, every browser's scroll anchoring behavior, subjective appearance, or hardware correctness. For future failures, record viewport and document positions plus scroll offsets at each phase before blaming rendering or weakening an assertion. Durable guidance: [Landing preview](../domains/landing-preview.md).
