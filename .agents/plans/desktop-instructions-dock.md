Desktop Build instructions stay at the right edge, immediately left of open Tools, across ordinary, native fullscreen and expanded fallback modes. Expanding instructions preserves independent Parts/Tools controls. Portrait phones retain a compact bottom sheet; short coarse-pointer landscape at 600–1000px uses one tabbed right pane with actual right camera insets and a coherent selected-part popup.

Issue #285; PR #286; branch `fix/build-instructions-dock`.

**Done**
- Reproduced previous 1280px bottom-sheet placement; Parts/Tools disappearance was not reproduced in that probe.
- Desktop/right-dock source and responsive model-space budget are frozen at `b81e3cc5`.
- Corrected independent review findings: real phone-landscape classification and insufficient model space despite passing non-overlap checks.
- Chromium and WebKit each pass 103 actual states, including native/fallback fullscreen, all panel combinations, coarse 720/844, fine 844, portrait restoration and selected-part side placement.
- Fresh exact-source twelve-image native capture at b81e3cc5 passed; raw receipt SHA256 `1fea0d2c2aff82fc20d68e3afca8e67dfc402ebd32204893c158c04f4a07936f`. Previous receipts and actual failure images remain retained.
- 60 generated guide outputs and 19 pure tests pass.

**Next**
- [x] Final assembled tree 31de4cb5 built; 11 privacy checks pass; both browsers pass 103 final-tree states with matching source hashes.
- [ ] Independent PR review, complete normal CI and root integration through dev/main.

**Resume:** all browser/capture tests own temporary listeners and close them. Shared preview is untouched. No CAD/battery/manufacturing scope.
