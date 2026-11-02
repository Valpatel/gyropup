#!/usr/bin/env bash
# Build the fuse board's outputs from design.py: the KiCad project, ERC and DRC (with schematic parity) reports,
# JLCPCB's gerber/drill zip, the BOM and placement files for JLCPCB's assembly, and the pictures.
#   hardware/fuse-board/build.sh
# KiCad 10 (kicad-cli and its own Python with pcbnew) from ~/.local; every KiCad step runs niced, one at a time.
# The parts library (footprints and 3D bodies) comes from cad-agent (cadagent.library, the cad extra): the repo's
# .venv, or CAD_AGENT=<path to cad-agent>.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
KPY="${KICAD_PYTHON:-$HOME/.local/share/kicad-10.0.1/bin/python3.11}"
KCLI="${KICAD_CLI:-$HOME/.local/bin/kicad-cli}"
CAD_AGENT="${CAD_AGENT:-$HERE/../../.venv/bin/cad-agent}"
export KICAD10_3DMODEL_DIR="${KICAD10_3DMODEL_DIR:-$HOME/.local/share/kicad-10.0.1/share/kicad/3dmodels}"
N="nice -n 15"
cd "$HERE"
mkdir -p fab reports pictures
TMP="$(mktemp -d "${TMPDIR:-/tmp}/fuse-board.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

# cad-agent's parts library: lib/cad-agent.pretty and lib/cad-agent.3dshapes (with a MINI fuse body per rating used)
"$CAD_AGENT" library --help > /dev/null 2>&1 || {
  echo "build.sh: $CAD_AGENT has no 'library' command; install a cad-agent with cadagent.library (cad-agent #295)" \
       "with the cad extra, or set CAD_AGENT=<path to one>" >&2
  exit 1
}
FUSES="$(python3 -c 'import design as D; print(*sorted({h[3] for h in D.HOLDERS if h[3]}))')"
$N "$CAD_AGENT" library build lib --project . --fuse $FUSES > /dev/null
$N "$KPY" generate.py > /dev/null
# zones are filled by DRC with the project's rules, then the filled board is saved
$N "$KCLI" pcb drc --refill-zones --save-board --schematic-parity --severity-all --exit-code-violations \
    -o reports/drc.rpt fuse-board.kicad_pcb
$N "$KCLI" sch erc --severity-all --exit-code-violations -o reports/erc.rpt fuse-board.kicad_sch
sed -i '/^\*\* Created on /d' reports/drc.rpt reports/erc.rpt   # no dates in the committed reports
$N "$KPY" measure.py > /dev/null                     # the filled board's copper areas -> reports/board-facts.json
$N python3 analysis.py > /dev/null                    # copper sizing, the INA228 budget, the mass -> reports/analysis.json
# every placed part shows: a 3D model that resolves, or the reason it is not a part
$N "$CAD_AGENT" library audit fuse-board.kicad_pcb --env "KICAD10_3DMODEL_DIR=$KICAD10_3DMODEL_DIR" \
    --waive 'TP*=a bare test pad (copper; the Adafruit 5832 lands here by wire)' \
    --waive 'H*=a non-plated slot for a cable tie (a hole)' --output reports/model-audit.json

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
$N "$KCLI" pcb render --side top --rotate '-50,0,30' --perspective --zoom 0.9 --width 1400 --height 1050 --quality basic \
    -o pictures/angle.png fuse-board.kicad_pcb > /dev/null
$N "$KCLI" sch export pdf -o pictures/schematic.pdf fuse-board.kicad_sch > /dev/null
# the board with every part's body, for the body's CAD (1.4 MB, not committed: .gitignore)
$N "$KCLI" pcb export step --subst-models --drill-origin --force -o fab/fuse-board.step fuse-board.kicad_pcb > /dev/null
rm -rf fuse-board-backups fp-info-cache
echo "fuse board: DRC and ERC clean, every part has a body; fab/fuse-board-gerbers.zip, fab/bom-jlcpcb.csv, fab/cpl-jlcpcb.csv, fab/fuse-board.step, pictures/"
