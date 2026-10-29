# Video replay needs real byte ranges in the local server

On 2026-10-29, the final landing highlights decoded and played in Chrome,
Chromium and WebKit, but WebKit failed after replay against `tools/serve-site.mjs`.
The movie was valid; the server answered every request with a complete HTTP 200.

Evidence from `tools/test-highlight-video.mjs`, pinned Playwright 1.56.1 WebKit:

```text
media.error.code = 2
R2: Received unexpected 200 HTTP status code for range request
```

The failure appeared after initial decoded-pixel and 13-viewport checks passed.
A successful first play did not exercise WebKit's later byte-range request.

The server now provides single byte ranges with HTTP 206 and correct
`Content-Range`, `Content-Length` and `Accept-Ranges`. Unsatisfiable ranges get 416;
HEAD, ETag revalidation and stale `If-Range` fallback retain their semantics.
Unsupported multiple ranges fall back to a full response. Reference:
[MDN HTTP range requests](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Range_requests).

```text
node --test tools/test-site-ranges.mjs
ok 1 - media GET, HEAD, seek ranges and cache validators
# tests 1
# pass 1
# fail 0
```

That check runs in `test:cache`; the browser highlights harness exercises actual
replay. Local server behavior is not proof of Cloudflare behavior: verify the
published movie's range response and browser replay after deployment too.
