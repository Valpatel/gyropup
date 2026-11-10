Desktop Build instructions should stay docked at the right in ordinary, expanded-workspace, and native fullscreen layouts. Expanding instructions must keep Parts and Tools controls accessible. Narrow mobile layouts retain their compact bottom sheet. Requested 2026-11-10.

**Done**
- [x] Isolated source branch from dev and read overlay/preview guidance.

**Next**
- [ ] Reproduce actual fullscreen expansion and record pre-fix geometry.
- [ ] Keep desktop right docking and panel controls consistent across modes.
- [ ] Verify real hit targets, panel state combinations, mobile, and independent review.

**Running**
- None. Tests will own temporary listeners and close them.

**Resume:** branch `fix/build-instructions-dock`; no CAD or battery changes.
