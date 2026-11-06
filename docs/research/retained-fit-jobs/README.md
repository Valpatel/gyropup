# Rejected first RS04 slice

**Do not print the archived job.** [rejected-7b67f03.zip](rejected-7b67f03.zip)
is diagnostic evidence from the first real slice, not a downloadable print kit.
Although Bambu Studio reported success, the executed startup selected 205°C
instead of the declared PA6-CF 275°C. No hardware was operated.

The archive is the original complete job produced at 7b67f03, including its
original receipt. That receipt records slice completion, not thermal approval;
the later executable-temperature guard rejects it. The CAD candidate remains
failed with eight mounting-support failures. Source changes after this capture
also make its freshness check fail, as intended.

See the [cause and corrective rule](../../.agents/inbox/2026-10-30-slicer-includes-control-executed-temperatures.md).

The [second diagnostic slice](rejected-speed-diagnostic.zip) uses the repaired
template resolver and correctly waits at 275°C/100°C. It remains rejected:
positive-extrusion object moves command up to 250 mm/s for gap infill, above
[Bambu's PA6-CF guidance](https://bambu-lab-jp.myshopify.com/en/products/pa6-cf)
of below 100 mm/s. Other measured maxima were 117.65 mm/s for floating vertical
shell, 106.08 mm/s for outer wall/top surface and 105.91 mm/s for internal solid
infill. These are commanded feeds, not claims about attained speed on short
moves. The archive retains the exact sliced 3MF, settings, identities, log and
raw result from that diagnostic. The regression test rejects its actual G-code.

Trial recipe revision 2 caps the faster roles at 99 mm/s and checks actual
object-deposition feed separately from travel. It requires a new slice; neither
archive is a print job to use on hardware.
