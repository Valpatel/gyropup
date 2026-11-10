# Keep the Build fixture safe without changing recorded capture inputs

The [actual ba89804 CI failure](ba-failure.json) was the existing highlight-media
source guard rejecting a changed historical test helper. The preceding real
Chromium and WebKit Build-guide reports each passed15groups with no page/runtime
errors. Layout and presentation aggregate failures were the downstream
`BROWSER_RESULT=failure` gate, with no additional suite cause. The verified
50-member artifact is bound by [all member hashes](ba-artifact-members.json).
This does not turn the failed run into a pass.

The correction restores `tests/site/content/test-prototype-session.mjs` exactly
to its existing1a/recorded bytes SHA997a3929. Build-guide instead imports the
14-line guarded fixture from its own test directory. That new local file is
byte-identical to ba's previously exercised guarded helper SHA73aa9c59. Its four
transported-init tests move with it and remain in the ordinary test command.
The actual existing highlight source/decoded-media/fault check now passes without
changing any receipt, media, historical helper behavior or validation assertion.

[New actual controls](actual-controls.json) retain all8 outcomes across native
Chrome151 and existing WebKit: old opaque failures2/1, guarded opaque/wrong-origin
no-write plus real/site/ack0errors, and matchingHTTP storage denial and ordinary
script error1each. Strict pageerror capture and the zero-livepoll-request contract
remain. All contexts/browsers closed and owned listener43415 refused connections.
The short runner did not capture its served version; the subsequent rebuild's
version is recorded separately. The product/tool/hardware trees remain byte-equal
to1a. No new fullguide or CI pass is inferred from these controls.

The [source/check receipt](results.json) binds the exact staged code, raw controls
and runner, ordinary23tests, full highlight-media check, build,11privacy and6
Markdown checks. Existing073/ba failures and earlier qualified evidence remain
unchanged. Final-head independent review and normalCI are still required.
