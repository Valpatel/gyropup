# Retired links need their moved source context

On 2026-11-06, the complete paired website products from fleet219 showed that
moving `research/` into `docs/research/` turned two existing historical-file
notices back into broken download links. The availability and LFP battery notes
still resolve `../catalog/…`, now to `docs/catalog/…`. The builder's existing
retired-link repair recognized only the former `catalog/…` GitHub targets.

The existing Markdown checks passed that product: preserving visible words did
not prove preservation of the link's historical status. The new actual-page
regression rejected the retained product, without changing it:

```text
node --test --test-name-pattern 'retired catalogue|built historical notes' tests/site/layout/test-doc-pages.mjs
retained fleet219 after-product: 1 pass, 1 fail
research-availability-2026-10-25-md.html: expected 1 historical notice, actual 0
```

At correction commit `86881e1a`, the real site build completed in13.682s. The
same actual-page check, scoped link controls and existing note-content check
passed together (3 tests); the Markdown and privacy checks also passed with
their existing environment-specific privacy skip. The exact narrow scope is
the two known notes, their two retired filenames, and their observed GitHub
`main` targets. Different filenames, notes, hosts and branches remain untouched.

Corrective rule: when an ownership move changes relative-link resolution,
compare actual generated link/status markup as well as visible text. Keep
historical exceptions tied to their authored context and known retired targets;
do not turn arbitrary unresolved links into historical notices. Keep the bad
product as a negative control, then validate a genuinely rebuilt product.

Limits: these short site checks do not accept the whole hierarchy migration,
refresh engineering outputs, validate physical hardware or prove public
deployment. The original fleet219 products remain unchanged. This incident and
its correction are tracked in [PR240](https://github.com/Valpatel/gyropup/pull/240)
as part of [PR238](https://github.com/Valpatel/gyropup/pull/238).
