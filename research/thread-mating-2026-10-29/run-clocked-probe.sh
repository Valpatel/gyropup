#!/bin/bash
set -u
CAD_RUN_ROOT="${CAD_RUN_ROOT:-$HOME/gyropup-mechanical-runs/20261029-integration}"
CAD_PHASE_RUN="${CAD_PHASE_RUN:?Set a fresh output directory for this diagnostic}"
# Refuse before opening any existing evidence file. The parent must already exist.
if ! mkdir "$CAD_PHASE_RUN"; then
  echo 'Refusing to reuse or replace the diagnostic output directory' >&2
  exit 2
fi
exec >"$CAD_PHASE_RUN/run.log" 2>&1
trap 'CAD_PHASE_RC=$?; printf "RUN-DONE rc=%s\n" "$CAD_PHASE_RC"; printf "%s\n" "$CAD_PHASE_RC" > "$CAD_PHASE_RUN/done"' EXIT
date -u +%FT%TZ
cd "$CAD_RUN_ROOT/cad-agent-v042-thread-probe" || exit 1
CAD_EXPECTED_COMMIT=2ad426943ce2c7232875e105e50810849f9a3e5e
CAD_ACTUAL_COMMIT=$(git rev-parse HEAD) || exit 2
printf 'toolkit_commit=%s\n' "$CAD_ACTUAL_COMMIT"
CAD_TOOLKIT_STATUS=$(git status --porcelain --untracked-files=all) || exit 2
if [ "$CAD_ACTUAL_COMMIT" != "$CAD_EXPECTED_COMMIT" ] || [ -n "$CAD_TOOLKIT_STATUS" ]; then
  echo 'Refusing a different or dirty toolkit checkout; use the exact reviewed source'
  exit 2
fi
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
exit "$CAD_PHASE_RC"
