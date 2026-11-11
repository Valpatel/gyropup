# A short homepage should link to engineering state rather than copy it

On 2026-11-10 the owner found the “Big robots. Backyard legends.” section outdated and asked for a playful, robot-centered entrance with details in the other tabs. Source `2011e4f3` still described `/exports/body/views/exploded.png` as “current CAD (stage P3)” and repeated the old D71 mass value. The accepted current body already used front/rear end packs, and the original P3 image/old mass records were historical. The existing source records were intact; the homepage's copied current-language claim was stale.

Read-only source evidence:

```text
rg -n 'Big robots|current CAD \(stage P3\)|37.5 kg' software/site/designer/home.html
# meet section: exploded.png, “current CAD (stage P3)”, “37.5 kg (83 lb, D71)”
```

The correction for #313 removes that image/current claim and duplicated engineering wall from Home. Existing status/timeline generators, JSON and the full Progress readings remain. The dated cad-agent stories move into a closed Progress fold with an explicit historical boundary, including an archived-image link. The old Home anchors become useful entrances to the full records. The hero's character/runtime/bootstrap and the underlying CAD, receipts and media bytes are not changed by this content pass.

Node22's actual HTML parser counted 1,033 authored main-content words before and 247 built words after, excluding the separately inserted safety dialog. The five new structural controls passed, including rejection of an injected old image, even-hidden engineering wall, missing anchor/deep target, omitted primary route and unsafe prototype wording. The home contract caps main copy at 300 words. Initial build, 11 privacy checks and six Markdown checks passed; browser/source-bound media/public verification are separate and pending at this checkpoint.

**Corrective rule:** keep the entrance evergreen and exciting, with concise prototype truth. Put changing numbers, dates, study verdicts and historical layouts on their existing evidence routes. Preserve their sources and anchors instead of hiding failures or calling an old illustration current. A relocation must keep its evidence checks; update the explicit build injection targets and verify the real destinations.

**Limits:** text/structure checks do not prove visual quality, accessibility in a browser, physical readiness or publication. The new page and separately reviewed v1 simulator must compose before one fresh bound media run. The existing media freshness gate must remain strict. Authored explosion sequencing and passive parking remain separate design work.
