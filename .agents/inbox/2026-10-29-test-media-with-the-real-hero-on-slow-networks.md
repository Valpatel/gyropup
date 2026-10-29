# Test media with the real hero on a slow network

On 2026-10-29, the new highlights player passed three browser engines, 13 viewport
sizes, decoded-pixel and failure-recovery tests, both locally and on Cloudflare.
Those player tests deliberately failed the separate hero import to prove that the
video remained usable. They did not establish that both real downloads could run
together on a constrained connection.

A fresh Chrome 390×844 context, with CDP network emulation at 150 ms latency,
1.6 Mbps download and 750 kbps upload, exposed contention:

```text
normal hero + autoplay:
first decoded movie frame: 1.392 s after request; buffered 0.82 s
post-first-frame waiting intervals: 20; total waiting: 21.225 s
22 s movie completed: 44.632 s after request
hero: Turret part pan_base: the request timed out. Please retry.
pan_base and cartridge_body: aborted at their 20 s reader deadline

same network, normal hero + reduced-motion/manual movie:
movie GETs: 0
hero ready: 37.726 s; failed requests/warnings: 0
pan_base/cartridge_body: 18.547 s / 18.778 s
```

The source reader's 20 s timeout includes body transfer. Fetching the reel while
48 turret parts were loading pushed two otherwise successful part requests over
that deadline. Starting playback at the first decodable frame also left less than
a second buffered and produced repeated waits. No HTTP failure, exception or
wrong model geometry was involved. Main publication PR108 was held for issue111.

Test the real hero and movie together as well as in isolation. Give the active
hero load priority, make queued playback clear and cancelable, and require a
useful initial media buffer. Keep failed or missing hero modules from blocking
the independent player. Verify request ordering deterministically and repeat the
actual full-page network-emulated check; merely extending CAD timeouts does not
prove smooth playback.

These timings describe one desktop browser under network emulation, not a
physical phone or a universal speed guarantee. Normal WebKit loaded the real hero
in 2.296 s and played/replayed the reel without stalls. The correction does not
change the CAD or make new physics claims.
