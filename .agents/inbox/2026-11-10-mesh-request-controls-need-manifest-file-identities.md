# Resolve mesh request controls from the captured manifest before launching

On 2026-11-10 the first PR #287 Chrome motion campaign at `2e90c6cc`
exited1 after47.340s. It saved18 output files, including945 live samples,
51 rigid samples,91 operation samples and seven fault captures, then timed out
waiting10s for `item.battery_front.stl`. The accepted manifest names the logical
part `item.battery_front` but its actual file is `meshes/item__battery_front.stl`.
The held-load control never intercepted its intended request. The same invented
filename also appeared in the later mobile503 control, which was not reached.
The original incomplete campaign and raw output remain retained by the review
action; no shared validation, WebKit campaign or qualification followed it.

`tests/site/models/current-motion-target.mjs` now resolves exactly one logical
part from the already hash-bound manifest, checks its local mesh path and actual
file SHA, and returns an exact URL-path matcher. Both controls reuse that matcher.
Resolution happens before output creation, server or browser startup. The mobile
assertion also requires an observed interception before accepting an error state.

The bounded command `node --test tests/site/models/test-current-motion-target.mjs`
with the explicit accepted candidate runs2 tests with0 skips (75.364ms on the
author's existing Node22.23.4). Controls reject a missing/duplicate logical part,
missing file, dotted logical-name filename, escaping path and altered file bytes;
the actual accepted battery mesh SHA and double-underscore filename pass. Syntax
and whitespace checks pass. These are preflight controls, not a browser rerun.

Keep request identity separate from display/logical identity. Do not increase a
request timeout or retry an unchanged capture when its stimulus never matched.
Previously saved observations remain incomplete evidence until the complete
reviewed controls and independent validator finish successfully. This resolver
is confined to the campaign's existing safe STL naming contract; it is not a
general URL or archive parser.
