# Authored content navigation must survive Markdown conversion

On 2026-11-11, PR315 source CI run42961981559 failed the unchanged intended
Markdown destination assertion in `test-status-board.mjs:408`. The built HTML
correctly offered Engineering updates, Build history, workshop stories and Design
notes inside Home's main content. The generated `index.md` omitted all four.
This was a product conversion failure, not a reason to remove the destination
assertion. The [content failure](https://github.com/Valpatel/gyropup/actions/runs/42961981559/job/130330602105)
retains the actual Markdown and original assertion.

```text
2026-11-11T04:59:46Z not ok16 - Markdown routes keep the board’s readings and drop its drawn bars
input did not match /Engineering updates[^\n]*designer\/progress\.html#board/
Actual Markdown: BUILT IN THE OPEN / Curious how it works? / [gyropup .] ...
(no Engineering updates or other authored content-navigation destinations)
```

The converter removed every `nav` as presumed site chrome. The new Home used
semantic navigation within `main`, so that rule erased actual content. Keep
navigation inside the main content and remove global navigation separately.
Normal hidden/aria-hidden cleanup still applies. The existing Markdown harness
now exercises the actual converter with authored and header duplicate links:
current content destinations remain once, header chrome and hidden content stay
absent, and wrong/missing content destinations or a removed main all fail.

A separate controls failure matched both the header Design notes link and its
new body counterpart. Scope the no-script check to the exact header navigation
link so it still checks the original responsive promise. The iPhone empty-space
artifact independently measured a real124px band after the new closed workshop
fold in both themes (0.187 of its664px view, above0.18). Keep that threshold and
its planted gap controls. Reduce only Progress's bottom padding from60px to24px;
actual layout acceptance still needs the bounded browser/normal CI check.

None of these files belongs to the486 accepted highlight source hashes. All369
captured input rows and seven accepted media bytes remain unchanged. Simulator
readiness timeouts and the separately stale assembly-guide poster fingerprint
remain distinct unresolved failures; these corrections do not establish their
cause or waive a fresh guide capture. No browser/capture was run for this change.
