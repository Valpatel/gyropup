# Rejected first RS04 slice

**Do not print the archived job.** [rejected-7b67f03.zip](rejected-7b67f03.zip)
is diagnostic evidence from the first real slice, not a downloadable print kit.
Although Bambu Studio reported success, the executed startup selected205°C
instead of the declared PA6-CF275°C. No hardware was operated.

The archive is the original complete job produced at7b67f03, including its
original receipt. That receipt records slice completion, not thermal approval;
the later executable-temperature guard rejects it. The CAD candidate remains
failed with eight mounting-support failures. Source changes after this capture
also make its freshness check fail, as intended.

See the [cause and corrective rule](../../.agents/inbox/2026-10-30-slicer-includes-control-executed-temperatures.md).
