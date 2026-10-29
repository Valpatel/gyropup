# Carrier inspection regression coverage

On 2026-10-29, the actual imported C2 and C3 support STEP assemblies passed Chromium and WebKit checks at 320×568, 390×844 and 1440×1000. This is twelve document→viewer cases across the two artifacts and engines. The inspected bundle was `b3a9a47`; geometry source and receipts remain bound to `120d531`.

`npm run test:carrier-inspection` now runs both contracts through the same browser harness. The existing browser CI's build-portal suite already calls that command. Set `PLAYWRIGHT_BROWSER=webkit` to repeat with installed WebKit; the default uses system Chrome unless `PLAYWRIGHT_CHANNEL=chromium` selects the installed Chromium build.

| Contract | Actual named model | Explicit hardware |
| --- | --- | --- |
| Existing C2 interface | 30 members | Eight screws and eight inserts |
| C3 support candidate | 34 members | Ten screws, eight inserts and two nuts, including every new support fastener by exact name |

The C3 contract also requires the support's own material, the labelled incomplete housing body, and both module-side C2 reservations. The current C3 assembly hash is `7a1ee25ffefbbf961b7aa83b17c89455ecfa42e8b4191c9d17b24821151c4824`, matching its committed support receipt. Public geometry is project-authored; the test does not serve private supplier CAD.

Both contracts enter through the design note's native Preview link, verify the original download bytes, wait for ready **or a terminal error**, inspect actual visible meshes/materials, test all camera buttons, fine wheel increments and Fit, and return through the native Back link. Phone framing and document overflow are checked. Each run preserves a candidate-specific report, screenshots and terminal diagnostics.

The default evidence directory is newly allocated per process. When setting `TEST_OUTPUT`, choose an agent/run-specific path; parallel reviews must not share screenshot paths. An early C3 review had a temporary path collision, so those screenshots are not treated as uniquely attributable evidence; its separately named programmatic reports remain valid, and the independent reviewer repeated the visual check in an isolated directory.

Deliberate browser-scene corruption must be detected: lost materials, swapped part colors, hidden inserts, invisible/zero-opacity fastener materials and removed screws. The C3 case additionally hides its support, one added nut and one added screw in turn. The real imported scene is restored and checked afterward. All twelve cases completed without page, HTTP or request errors.

These browser tests establish inspection behavior and preserved model identities. They do not qualify the incomplete C3 housing representation, flexible clips, wiring, printed support strength, physical fit or whole-module removal. The current candidate remains unqualified for fabrication.
