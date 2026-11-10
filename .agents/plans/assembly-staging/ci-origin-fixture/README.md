# Preserve opaque-document fixture failures without filtering errors

The [original073 CI job/artifact receipt](original.json) and
[failed report](original-failed.json) retain9 storage-denied errors, all from
about:blank documents. The context-wide observer exposed an unsafe test init
fixture; this is not a product notice failure. No error is exempted or filtered.

The existing shared test acknowledgement helper now checks HTTP(S) and serialized
security origin before storage access, optionally bound to the intended origin.
Build-guide passes its base explicitly. Existing callers default to SITE_URL;
when unset, standalone HTTP compatibility remains, while opaque documents never
access storage. Matching-origin storage denial continues to throw.

[Actual controls](actual-controls.json), on nativeChrome151/existingWebKit, retain
oldopaque failures and new opaque/wrong-origin no-write + real/site/ack positive.
MatchingHTTP denial and an ordinary script error each remain observable. Four
ordinary tests execute the actual transported init function, including existing
caller defaults and storage accessors. [Both affected full guide suites](results.json)
pass15groups each,0page/runtime errors and0unsupported poll requests. Localnative
Chrome is not CI's pinned Chromium; final-head normalCI remains required.

Only fixtures/tests and their evidence changed. Product/runtime, notice behavior,
strict context-wide capture, timeouts, CAD and all prior native identities remain
unchanged. The [checkpoint](checkpoint.json) binds actual staged source/report
hashes; originals and earlier rejected attempts remain preserved separately.
