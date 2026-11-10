# Wait for the actual canvas presentation before recording visual recovery

On 2026-11-10 PR #287's WebKit action at `da5a07de` captured successfully in
46.083s and passed the separate shared motion validator (70.996s total). It
recorded27 output seals, no page errors, closed its browser/listener and retained
all source/data/protected-tree guards. Independent visual readback nevertheless
found `mobile-current-recovered.png` entirely blank inside the3D viewport. The
author also inspected that exact retained PNG and confirmed the missing robot.
The numerical motion result remains passed; visual recovery remains incomplete.
It is distinct from the earlier6dd observer exception and2e90 request mismatch.

`sim.js` intentionally sets canvas opacity0, starts the stage, schedules opacity1
with a0.35s transition in the next animation frame, and marks body ready before
that callback. Logical ready and correct model identity do not prove an opaque,
drawn canvas. Keep the product's transition unchanged.

The campaign now polls the existing stage renderer before each desktop/mobile
screenshot, bounded to10s with animation-frame polling. It requires the expected
collection,228 displayed parts, logical readiness, connected canvas, computed
opacity1, visible CSS and robot ancestors, positive canvas rectangle/buffer, and
finite positive renderer frame/call/triangle counters. Actual model, style,
rectangle, buffer and draw counters are retained in the capture index and mobile
recovery output. There is no fixed sleep and product page errors remain fatal.

The actual serialized helper has controls for opacity0/0.99, hidden CSS/model
parents, missing/zero/malformed draw counters, wrong source, missing parts and
zero canvas dimensions. Unexpected observer exceptions still propagate. These
pure controls establish the gate's failure behavior; they do not replace a new
reviewed actual WebKit campaign and independent inspection of its resulting PNG.
Nonzero draw counters alone do not prove every required part is on screen or
mechanically correct; retain the independent geometry traces and visual readback.
