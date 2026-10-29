#!/bin/bash
set -u
CAD_RUN_ROOT="${CAD_RUN_ROOT:-$HOME/gyropup-mechanical-runs/20261029-integration}"
CAD_PHASE_RUN="$CAD_RUN_ROOT/thread-phase-v042-153-matrix"
mkdir -p "$CAD_PHASE_RUN"
exec >"$CAD_PHASE_RUN/run.log" 2>&1
date -u +%FT%TZ
cd "$CAD_RUN_ROOT/cad-agent-v042-thread-probe" || exit 1
printf 'toolkit_commit='; git rev-parse HEAD
python3 - "$CAD_RUN_ROOT/base-board-42db26b/references/vendor/mcmaster" <<'PYHASH'
import hashlib,sys
from pathlib import Path
for pn,expected in [('91290A111','5254e828992285b42974ce077f5b1443fb8831397bcd9e653c4f5680df3b4191'),('94459A140','2ee42df52bf86ee05039c239b23e0d589d0587bb604ee06c28531315631158a0')]:
 p=Path(sys.argv[1])/pn/(pn+'.norm.step');actual=hashlib.sha256(p.read_bytes()).hexdigest();assert actual==expected,(pn,actual);print(pn,actual)
PYHASH
CAD_PHASE_RC=$?
if [ "$CAD_PHASE_RC" -eq 0 ]; then
 timeout 900 "$CAD_RUN_ROOT/.venv/bin/python" tools/volume_probe.py prepare "$CAD_PHASE_RUN/fixed" --a "$CAD_RUN_ROOT/base-board-42db26b/references/vendor/mcmaster/91290A111/91290A111.norm.step" --b "$CAD_RUN_ROOT/base-board-42db26b/references/vendor/mcmaster/94459A140/94459A140.norm.step" --location-a '[[0, 0, -1, 46.4], [-0.45399049973954686, -0.8910065241883678, 0, -22.4], [-0.8910065241883678, 0.45399049973954686, 0, 9]]' --location-b '[[0, 0, 1, 48], [0, 1, 0, -22.4], [-1, 0, 0, 9]]'
 CAD_PHASE_RC=$?
fi
if [ "$CAD_PHASE_RC" -eq 0 ]; then
 timeout 300 "$CAD_RUN_ROOT/.venv/bin/python" tools/volume_probe.py measure "$CAD_PHASE_RUN/fixed" --method gk
 CAD_PHASE_RC=$?
fi
printf 'RUN-DONE rc=%s\n' "$CAD_PHASE_RC"
printf '%s\n' "$CAD_PHASE_RC" > "$CAD_PHASE_RUN/done"
exit "$CAD_PHASE_RC"
