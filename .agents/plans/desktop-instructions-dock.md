Desktop Build instructions stay at the right in ordinary, expanded-workspace and native fullscreen layouts, immediately left of open Tools. Expanded instructions preserve independent Parts/Tools controls. Narrow layouts retain the compact bottom sheet.

Issue #285; PR #286; branch `fix/build-instructions-dock`.

**Done**
- Reproduced previous1280px bottom sheet in actual native Chromium; Parts/Tools disappearance was not reproduced.
- Unified desktop right docking and camera insets; reserved the model lane across simultaneous panels.
- Corrected intermediate1280px allocation after an actual274.375px lane failure.
- Chromium and WebKit each passed93 docking/control states, including real fullscreen, denied-fullscreen, resize and mobile touch.
-19 pure assembly tests and11 privacy tests passed.

**Next**
- Capture and attach twelve fresh source-bound posters from the committed final source, regenerate their consumers, build and check privacy.
- Record final-source receipts and independent review; root integrates through dev/main.

**Resume:** use the isolated branch. Tests own temporary listeners and close them. Shared preview remains untouched. No CAD/battery/manufacturing scope.
