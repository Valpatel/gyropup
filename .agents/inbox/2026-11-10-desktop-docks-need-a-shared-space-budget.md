# Desktop docks need one shared space budget across window modes

2026-11-10, issue #285 / PR #286.

## What happened and evidence

The previous Build workspace switched to a bottom sheet at 1280px. Actual native
Chromium before the fix showed instruction widths of 1196px windowed and 1262px
fullscreen at that viewport. The Parts and Tools tab centers were reachable in
both captures: this probe reproduced the unwanted desktop placement, **not** the
reported disappearing tabs. Preserve that distinction.

The first right-dock implementation passed all desktop panel combinations at
1440 and 1024, then failed at the intermediate 1280 width in both browser engines:

```text
2026-11-10: npm run test:instruction-docking
AssertionError: windowed resize 1280x900 retains useful model width
workspace width 1214; Parts width 278; Tools width 278; Instructions width 315.625
measured model lane: 274.375px (required >=320px)
```

## Why the first bounds check missed the case

The instruction card and the side panels each had independent responsive width
limits. Their sums consumed more space at the intermediate width than at either
previously checked endpoint. Reserving a fixed panel width in the camera insets
would also have disagreed with the responsive rendered boxes.

## Corrective rule

Budget Parts and Tools from the actual workspace width **after** accounting for
the responsive instruction card and the model lane. Keep instructions on the
right in both reading sizes; expanding changes its height, and opening Tools
moves it immediately to the left of Tools. Measure the real Tools box to set its
neighbor's offset and the real instruction box for the camera's right inset.
Use the same CSS in ordinary, native fullscreen and denied-fullscreen expansion.

The regression checks every instruction/Parts/Tools state, intermediate widths,
actual native fullscreen completion, denied fullscreen, resize across the mobile
boundary, true target hits, and projected real mesh vertices. Windowed landscape
is a scrolling document: bring the workspace under app navigation and separately
scroll each mobile tab into view before testing its actual pointer target. A
naturally offscreen control is distinct from an overlay intercepting a hit.

## Limits

The narrow bottom sheet remains a separate layout at <=760px. Simultaneous
320px model-lane acceptance applies to desktop workspaces at least 950px wide;
a shorter/narrower window can require ordinary page/panel scrolling. Browser
checks establish presentation and control behavior, not physical assembly fit.
