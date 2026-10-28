#!/usr/bin/env bash
# Build the fuse board's outputs from design.py: the KiCad project, ERC and DRC (with schematic parity) reports,
# JLCPCB's gerber/drill zip, the BOM and placement files for JLCPCB's assembly, and the pictures.
#   hardware/fuse-board/build.sh
# KiCad 10 (kicad-cli and its own Python with pcbnew) from ~/.local; every KiCad step runs niced, one at a time.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
KPY="${KICAD_PYTHON:-$HOME/.local/share/kicad-10.0.1/bin/python3.11}"
KCLI="${KICAD_CLI:-$HOME/.local/bin/kicad-cli}"
N="nice -n 15"
cd "$HERE"
mkdir -p fab reports pictures
TMP="$(mktemp -d "${TMPDIR:-/tmp}/fuse-board.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

$N "$KPY" generate.py > /dev/null
# zones are filled by DRC with the project's rules, then the filled board is saved
$N "$KCLI" pcb drc --refill-zones --save-board --schematic-parity --severity-all --exit-code-violations \
    -o reports/drc.rpt fuse-board.kicad_pcb
$N "$KCLI" sch erc --severity-all --exit-code-violations -o reports/erc.rpt fuse-board.kicad_sch
sed -i '/^\*\* Created on /d' reports/drc.rpt reports/erc.rpt   # no dates in the committed reports
$N "$KPY" measure.py > /dev/null                     # the filled board's copper areas -> reports/board-facts.json
$N python3 analysis.py > /dev/null                    # copper sizing, the INA228 budget, the mass -> reports/analysis.json

# JLCPCB: gerbers (Protel extensions) and Excellon drills, plated and non-plated apart, oval holes as G85 slots
$N "$KCLI" pcb export gerbers --layers F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts \
    --subtract-soldermask --use-drill-file-origin -o "$TMP/gerbers/" fuse-board.kicad_pcb > /dev/null
$N "$KCLI" pcb export drill --format excellon --excellon-separate-th --excellon-oval-format alternate \
    --excellon-units mm -o "$TMP/gerbers/" fuse-board.kicad_pcb > /dev/null
rm -f fab/fuse-board-gerbers.zip
(cd "$TMP/gerbers" && zip -q -X "$HERE/fab/fuse-board-gerbers.zip" *)

# JLCPCB assembly files (top side, SMD parts with an LCSC number, U1 not fitted)
$N "$KCLI" sch export bom --fields 'Reference,Value,Footprint,LCSC,MPN,${QUANTITY},${DNP}' \
    --labels 'Designator,Comment,Footprint,LCSC,MPN,Qty,DNP' --group-by 'Value,Footprint,LCSC' \
    --exclude-dnp -o "$TMP/bom.csv" fuse-board.kicad_sch > /dev/null
$N "$KCLI" pcb export pos --format csv --units mm --side front --smd-only --exclude-dnp --use-drill-file-origin \
    -o "$TMP/pos.csv" fuse-board.kicad_pcb > /dev/null
$N "$KPY" jlc_files.py "$TMP/bom.csv" "$TMP/pos.csv" fab/bom-jlcpcb.csv fab/cpl-jlcpcb.csv

# pictures
$N "$KCLI" pcb render --side top --width 1400 --height 1220 --quality basic -o pictures/top.png fuse-board.kicad_pcb > /dev/null
$N "$KCLI" pcb render --side bottom --width 1400 --height 1220 --quality basic -o pictures/bottom.png fuse-board.kicad_pcb > /dev/null
$N "$KCLI" sch export pdf -o pictures/schematic.pdf fuse-board.kicad_sch > /dev/null
rm -rf fuse-board-backups fp-info-cache
echo "fuse board: DRC and ERC clean; fab/fuse-board-gerbers.zip, fab/bom-jlcpcb.csv, fab/cpl-jlcpcb.csv, pictures/"
