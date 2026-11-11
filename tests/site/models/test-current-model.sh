#!/usr/bin/env bash
# Existing actual-current observer/shared validator; no CAD/native solver or new geometry.
set -euo pipefail
: "${CURRENT_MOTION_TOOLKIT:?Set the existing clean pinned cad-agent checkout}"
readonly motion_python="${CURRENT_MOTION_PYTHON:-python3}"
readonly motion_node="${CURRENT_MOTION_NODE:-node}"
readonly motion_revision=c67149b0a35127f93a237d3083ac0b70fcf0d17d
readonly motion_engines="${PLAYWRIGHT_BROWSER:-chromium webkit}"
case "$motion_engines" in chromium|webkit|'chromium webkit') ;; *) printf 'Unknown browser selection\n' >&2; exit 1;; esac
readonly motion_output="$(mktemp -d "${TMPDIR:-/tmp}/gyropup-current-motion-ci-XXXXXX")"
printf 'Current motion evidence: %s\n' "$motion_output"
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
# Fixed actual cache/index/authority and source checks are mandatory before capture.
"$motion_python" -B tests/site/assembly/test_robot_current_snapshots.py -q
/usr/bin/timeout --foreground --signal=TERM --kill-after=5s 30s "$motion_python" -I -B tools/engineering/robot/current_motion.py \
  --candidate software/site/assets/robot-current --toolkit "$CURRENT_MOTION_TOOLKIT" --toolkit-revision "$motion_revision" --output "$motion_output/reference.json"
readonly reference_hash="$("$motion_python" -I -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$motion_output/reference.json")"
export CURRENT_MOTION_REFERENCE="$motion_output/reference.json" CURRENT_MOTION_REFERENCE_SHA256="$reference_hash"
export CURRENT_MOTION_SITE_ROOT="$PWD/dist" CURRENT_MOTION_SOURCE="$(git rev-parse HEAD)" CURRENT_MOTION_MODE=adopted
# The default ordinary CI command covers both engines sequentially. Each owns
# its browser/listener and closes before the next complete capture is started.
for motion_engine in $motion_engines; do
  export TEST_OUTPUT="$motion_output/$motion_engine" PLAYWRIGHT_BROWSER="$motion_engine"
  /usr/bin/timeout --foreground --signal=TERM --kill-after=10s 200s "$motion_node" tests/site/models/test-current-robot-motion.mjs
  /usr/bin/timeout --foreground --signal=TERM --kill-after=5s 90s "$motion_python" -I -B tools/engineering/robot/current_motion.py \
    --reference "$CURRENT_MOTION_REFERENCE" --reference-sha256 "$reference_hash" --captures "$TEST_OUTPUT" \
    --toolkit "$CURRENT_MOTION_TOOLKIT" --toolkit-revision "$motion_revision" --output "$motion_output/$motion_engine-validation.json"
done
