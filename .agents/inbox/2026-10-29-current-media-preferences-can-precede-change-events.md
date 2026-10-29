# Current media preferences can precede retained-list change events

On 2026-10-29, a WebKit preference-cancellation trace for PR112 showed a short gap
between the current reduced-motion query and a retained MediaQueryList's update.
A hero could finish inside that gap and start the queued movie.

The actual `webkit-preference-trace.json` for build `896422a` includes:

```text
after-emulate at1186 ms: fresh query=true, retained list=false, UI=queued
retained change event at1212 ms: matches=true, movie src already assigned
settled at1493 ms: both=true, movie src remains assigned
```

Two other repetitions delivered the event after 1 ms and did not request the
movie. The third delayed it by 26 ms and did. This was not merely an assumption
that the automation RPC meant a change event had already fired: a fresh in-page
query already exposed the user's new preference.

Read the current preference at the final download/play/recovery decision, while
keeping the retained change listener to cancel existing activity. Test the
same-task hero completion during the measured fresh/retained mismatch; a test
that waits for the retained event first would erase this case.

This records the observed WebKit ordering, not a universal browser timing
guarantee. It does not justify ignoring preference events or changing the
visitor's saved settings.
