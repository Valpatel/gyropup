# A short homepage should link to engineering state rather than copy it

On 2026-11-10 the owner found the “Big robots. Backyard legends.” section outdated and asked for a playful, robot-centered entrance with details in the other tabs. Source `2011e4f3` still described `/exports/body/views/exploded.png` as “current CAD (stage P3)” and repeated the old D71 mass value. The accepted current body already used front/rear end packs, and the original P3 image/old mass records were historical. The existing source records were intact; the homepage's copied current-language claim was stale.

Read-only source evidence:

```text
rg -n 'Big robots|current CAD \(stage P3\)|37.5 kg' software/site/designer/home.html
# meet section: exploded.png, “current CAD (stage P3)”, “37.5 kg (83 lb, D71)”
```

The correction for #313 removes that image/current claim and duplicated engineering wall from Home. Existing status/timeline generators, JSON and the full Progress readings remain. The dated cad-agent stories move into a closed Progress fold with an explicit historical boundary, including an archived-image link. The old Home anchors become useful entrances to the full records. The hero's character/runtime/bootstrap and the underlying CAD, receipts and media bytes are not changed by this content pass.

At the first source checkpoint, Node22's actual HTML parser counted 1,033 authored main-content words before and 247 built words after, excluding the separately inserted safety dialog. The five new structural controls passed, including rejection of an injected old image, even-hidden engineering wall, missing anchor/deep target, omitted primary route and unsafe prototype wording. The home contract caps main copy at 300 words. Initial build, 11 privacy checks and six Markdown checks passed; browser/source-bound media/public verification are separate and pending at this checkpoint.

**Corrective rule:** keep the entrance evergreen and exciting, with concise prototype truth. Put changing numbers, dates, study verdicts and historical layouts on their existing evidence routes. Preserve their sources and anchors instead of hiding failures or calling an old illustration current. A relocation must keep its evidence checks; update the explicit build injection targets and verify the real destinations.

**Limits:** text/structure checks do not prove visual quality, accessibility in a browser, physical readiness or publication. The new page and separately reviewed v1 simulator must compose before one fresh bound media run. The existing media freshness gate must remain strict. Authored explosion sequencing and passive parking remain separate design work.


## Relocating markup also relocates its style and Markdown test authority

Initial PR314 CI at `ebdc45c615547b22604b5f82dc27cad1b38c5899` retained two real failures in presentation-content job130308791274/run42955279095: the FEA-card check still read `web/landing.css` for the plotted denominator, and the complete-link/accessible-text check still sliced `index.md` for the relocated loop. Nine other loop checks passed. Both stale-owner assertions failed rather than silently accepting missing evidence. The correction reads the extracted `workshop-stories.css` and the actual `designer/progress.md`; the denominator, every section link/anchor, full accessible numeric sentence and Markdown semantics remain asserted. This is a test-owner correction, not a new successful CI claim or a waiver. Preserve the original failed run.


The browser-candidate prototype line was shortened to an evergreen experimental-hardware boundary rather than copying a changing physical-testing stage. The complete safety notice is unchanged. Relocated static Progress fixtures reuse the existing exact-origin static-document opt-out and assert zero unsupported changes-endpoint requests after cleanup; no browser errors are filtered and the historical prototype helper is unchanged. These fixture helpers retain their existing wrong-origin and storage-failure controls. Browser checks have not run locally at this source checkpoint.


## A responsive hidden break still needs a word separator

All four original source605e browser units passed their functional assertions and cleanup guards. Root's actual Chromium320px full-page image nevertheless showed “scrolling.More” joined together. The new heading had dropped the literal space before its `<br>`, while the existing mobile CSS hides that break. This is a real typography regression; the focused Skip-to-content overlay in that test image is separately recorded test focus, not an assumed product defect.

The minimal correction restores the existing separator. The ordinary hero viewport test now reads the actual rendered `innerText` and computed break state across mobile/desktop. Its mobile DOM negative temporarily removes that separator, requires the actual joined rendered phrase and a synchronous validator rejection, then restores and rechecks the real heading. Source regexes alone cannot establish the visible result. Original605e screenshots/functional receipts remain unchanged; a separately reviewed bounded typography check must inspect the corrected candidate and record keyboard focus before deliberately clearing it for a resting screenshot. No hero/model runtime, CSS or geometry change is part of this correction.
