# PAN carrier packaging proposal

This bounded checkpoint advances [issue #96](https://github.com/Valpatel/gyropup/issues/96) with source records for all 47 electronic items, a logical terminal map, a mechanical service proposal and a two-assembly paper allocation. It does **not** freeze a board layout, heat path, harness route or fabrication design. The broader issue remains open.

The existing 50.8 × 30 mm control board is occupied. Its old U2 box and the C3 support are not spare PCB space. A manufacturer's 40 × 40 mm thermal test board is neither an allocated region nor a demonstrated minimum size. The source/servo contract remains 15–20.5 V stand / 30–42 V robot input and 12 V PAN output. There have been no purchases or energized tests.

The [electrical source record](electrical-envelope.md) distinguishes maximum dimensions, nominal profiles, formed-lead datums, copper lands and unknown assembly allowances. Every electronic row has primary package evidence; this is not a complete physical BOM. Actual mounting, junctions, soldered leads and adjacent harness parts remain unresolved. The [mechanical proposal](mechanical-envelope.md) records the bumper-sector and C3-parking prerequisites without claiming a new CAD clearance or strength result.

The [paper allocation](paper-allocation.md) assigns all 47 electronic entries to a control/termination board and a PAN power assembly. It lists 19 control-board and four power-board wire-pad candidates, a finite trial power-board outline and conditional height screens. No component or terminal has an accepted physical placement. The capacitor screen leaves only 0.5 mm before unknown mounting and tolerance allowances; it is not a stack approval.

Reproduce the committed checkpoint from the repository root:

```sh
python hardware/carrier-packaging/check.py
python -m unittest discover -s hardware/carrier-packaging -p 'test_*.py'
```

After an intentional source change, regenerate with `inventory.py` followed by `allocation.py`, then review the diff and repeat the checks. CI checks committed evidence without silently refreshing it.

Next: resolve the remaining delivery/lead-form specifications and critical supply gaps; assign every actual component, terminal, mounting and thermal region; then validate the complete seated, released, parked and removal sequence. Source transients, charged reversal, startup, regeneration, material strength and energized behavior remain separate qualification gates. No native circuit or CAD revision is produced by this checkpoint.

Ownership: the electrical author is the sole Git committer and owns these records/checks; the mechanical author owns only `mechanical-envelope.md` and its read-only investigation. Independent review is required before integration.
