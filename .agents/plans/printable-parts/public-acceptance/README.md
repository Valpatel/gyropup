# Public checklist acceptance

```mermaid
flowchart LR
    R[Reviewed release and main] --> B[Bind real source and providers]
    B --> G[Independent review of exact packet]
    G --> P[One bounded public Build check]
    P --> A[PDF and image review]
```

This is a recoverable procedure for #281, **not a record of a public run**. Source fixtures and their failures remain in [the parent packet](../README.md); the [source-fidelity packet](../source-fidelity/) contains the producer-DOM oracle and corrected PDFs. Main delivery, actual toolkit provenance, normal CI and public acceptance are separate requirements. This procedure never operates a printer or purchases parts.

## Prepare privately

Copy the three execution/audit scripts and the offline recovery test into an exclusive private packet directory. Copy the canonical `../source-fidelity/pdf-id-extractor.py` beside them unchanged. Copy each `.TEMPLATE.json` to its unsuffixed name. Keep machine paths and provider inventories out of the public repository. Templates deliberately have disabled execution, TODO identities and no review seal.

Bind the actual final main commit/tree, published asset key, real toolkit release tag/commit and component digest. Derive the four JS hashes from immutable Git objects, and the three transformed HTML/CSS hashes from the final built artifact. Bind the guide identity and all four tables from independently checked source: exact IDs, matching IDs, long notes, meaningful field fragments and final PDF page counts. Do not copy an old page count after restoring source text. Record actual installed Node, Playwright and Chrome identities; no installation is part of this procedure.

The final packet needs independent GPT-6 review under the repository review workflow. Set `approved_for_execution` to true only for that concrete review. Afterwards write `review-seal.json` with the review URL and `files_sha256` mapping for `run.py`, `public-checklists.mjs`, `audit-pdfs.py`, `pdf-id-extractor.py`, `contract.json`, `provider-reference.json` and `release-binding.json`. The seal records reviewed bytes; it is not an authentication mechanism. Any input change needs renewed review.

## Execute and inspect once

From the private packet, the reviewed command is `python3 run.py --execute-reviewed`. Admission validates bindings before creating its exclusive attempt marker. An existing marker/output/unit or changed input is rejected. Never repeat a completed browser run merely to repair an evidence collector.

One isolated browser loads the canonical `https://gyropup.com/designer/build` route, uses the actual notice and assembly viewer, and checks source-bound Combined geometry. It activates the real Print/Buy tables at desktop and phone widths, checks positive header/cell alignment, sorting, filtering, all-page printing and saved-status identity. Only disposable browser-local checkboxes/storage change. There is no route interception or injected application fixture.

The run retains six screenshots and twelve PDFs: queue and orders full/matching A4/Letter, plus Made and pending-turret full A4/Letter. Printed row order is checked against current live order; independent source ID membership remains fixed. Field fragments must appear in the correct column/note. The offline auditor requires the exact case matrix, unique IDs, repeated headers, page bounds, whole queue quantities, warnings and complete notes/source fragments in their own part segment and page. The known-ID extractor has positive wrapped-prefix controls and rejects real duplicates or missing IDs.

The owned transient unit caps CPU at two cores, memory at 3 GiB with no swap, tasks at 512 and runtime at 480 seconds. Browser work has a 420-second bound; actions, navigation, artifacts, PDFs and cleanup have separate limits. Live unit properties are captured before browser work; terminal empty/absent descendants are checked separately. A collected unit's default properties are never treated as its historical limits. Only the exact owned unit may be stopped.

Inspect `run.log`, `live-unit.json`, `report.json`, `terminal-cleanup.json` and `pdf-audit.json`, then actually view representative PDFs and screenshots. Retain failures, source identities and cleanup evidence. Publish a privacy-safe issue receipt with exact main/release bindings and independent review; close the issue only after every acceptance condition is met. These checks do not establish physical fit, manufacturing readiness or printer output.

## Collector failure controls

Run `python3 test-runner-recovery.py` before binding. Its six offline controls extract only the runner function and replace subprocess calls: no unit, browser, network or campaign is launched. Launch errors, stop timeouts/nonzero exits, terminal-query failures, malformed live receipts and wrong-unit cgroups must leave an honest terminal receipt without claiming cleanup success. The runner makes a best-effort finally-style collection even after launch/stop failure. If a receipt cannot be written, it emits the failure record to stderr; preserve that output and recover read-only. A retained error never authorizes a repeated browser campaign.

The public document route and built file have distinct names: on 2026-11-11, read-only GETs returned `308` from `/designer/build.html` to `/designer/build`, then `200` HTML at the canonical route. Navigate directly to the canonical route and bind its response bytes to the final built `designer/build.html` file. A redirect body is not HTML artifact evidence. These metadata requests did not launch a browser or execute acceptance.
