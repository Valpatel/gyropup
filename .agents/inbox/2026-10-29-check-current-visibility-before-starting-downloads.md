# Check current visibility before starting delayed downloads

On 2026-10-29, independent PR112 review reproduced a queued-video race in build
`61503da`: a hero-ready mutation could arrive after scrolling but before
IntersectionObserver delivered its new visibility state.

The probe queued manual playback under reduced motion, then performed scrolling
and hero completion in the same page evaluation:

```text
scrollTo(0,0); hero.dataset.ready='true'; hero.dataset.state='ready'
card top: 3286.7 px; viewport height: 844 px
result: video src assigned, one MP4 GET, then paused
intended result: no new movie request while the canceled queue is offscreen
```

The callback trusted a stale observer flag. Pausing after the observer caught up
did not undo the unnecessary download.

Check current card bounds before starting delayed loading or playback, and keep
queued intent cancelable independently of derived visibility. A cancellation
check cannot rely only on a predicate that has already become false after the
scroll. The regression must complete the hero in the same task as the scroll,
before observer delivery; waiting first would hide the race.

This does not require changing layout, resetting the hero, or canceling an
already useful downloaded movie. It concerns a new request triggered by stale
queued intent.
