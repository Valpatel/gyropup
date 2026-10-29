# A modal warning can break focus, hide controls or consume the first greeting

During the 2026-10-29 UTC prototype-notice change, actual browser checks caught three integration defects. The native dialog let reverse Tab from its scrollable text move focus to BODY. Adding a 44 px reopen control pushed a talk-page control beyond a 320 px overflow-hidden header, despite a passing page-width check. The landing clock reached 3.05 seconds / one attempted announcement while the entry dialog blocked speech, consuming the first greeting before acknowledgement.

Evidence from the built preview and independent source/visual probe:

```text
$ SITE_URL=http://127.0.0.1:8891 npm run test:notice
AssertionError: Native modal contains keyboard focus
$ SITE_URL=http://127.0.0.1:8891 npm run test:audio
AssertionError: Talk demo master controls fit a 320px phone
trace.json: modal=true, seconds=3.05, announcements=1; Tab -> content, Shift+Tab -> BODY
```

The correction adds explicit Tab boundary wrapping, compacts only notice-bearing narrow headers while retaining 44 px controls, and pauses the landing active clock while the notice is open. The active turret also releases its transient ARM/trigger/aim holds when the dialog opens, because stopping modal keyup propagation alone could strand a held command. Audio is temporarily gated without replacing saved mute/volume preferences or the conversation.

The revised built Chromium notice suite passes all six layouts, session/storage cases, retained-scene checks, input cleanup and audio gates. The independent visual pass confirms header control bounds and readable no-script warning text; final WebKit/CI/hosted receipts are tracked on PR52. Probe screenshots and `trace.json` are under `/tmp/gyropup-notice-visual` for this session; committed tests and guidance are the durable regression.

Limits: this validates browser presentation and application continuity, not hardware safety, training, legal acceptance or physical child safety. See [prototype notice guidance](../domains/prototype-notice.md).
