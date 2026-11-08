#!/usr/bin/env bash
# Detached, owned compute-host invocation. Exact private paths come from the
# reviewed operator; this file neither installs nor changes the retained runtime.
set -uo pipefail
umask 077
: "${FOOT_RUN:?}" "${FOOT_HEAD:?}" "${FOOT_CPUS:?}" "${FOOT_RUNTIME:?}" "${FOOT_MOTOR_STEP:?}"
[ -d "$FOOT_RUN/src/.git" ] && [ -d "$FOOT_RUN/out" ] && [ -f "$FOOT_RUNTIME" ] || exit 90
cd "$FOOT_RUN/src" || exit 90
[ "$(git rev-parse HEAD)" = "$FOOT_HEAD" ] && [ -z "$(git status --porcelain)" ] || exit 91
export FLEET_RUN_OUT="$FOOT_RUN/out" HOME="$FOOT_RUN/home" TMPDIR="$FOOT_RUN/tmp"
export XDG_CACHE_HOME="$HOME/.cache" PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_MAX_THREADS=1
# Timeout's TERM reaches the collector, whose approved phase cleanup reaps its
# independent native group. An interrupted/missing final receipt is incomplete.
setsid timeout --signal=TERM --kill-after=20s 1800s taskset -c "$FOOT_CPUS" \
  /usr/bin/python3 -B .agents/plans/hip-study/collect-foot-geometry.py \
  --head "$FOOT_HEAD" --runtime "$FOOT_RUNTIME" --motor-step "$FOOT_MOTOR_STEP" < /dev/null > "$FOOT_RUN/run.log" 2>&1 &
cpid=$!
printf '%s\n' "$cpid" > "$FOOT_RUN/collector-group.pid"
disk_watch() {
  while sleep 5; do
    kill -0 "$cpid" 2>/dev/null || return 0
    used=$(timeout 5s du -sx --block-size=1 -- "$FOOT_RUN" | cut -f1) || used=unknown
    if [ "$used" = unknown ] || [ "${used:-0}" -gt 8589934592 ]; then
      printf '%s\n' "Owned scratch exceeded 8 GiB or disk measurement failed" > "$FOOT_RUN/disk-stop"
      kill -TERM -- "-$cpid" 2>/dev/null || true
      return 0
    fi
  done
}
disk_watch & wpid=$!
stop_owned() { kill -TERM -- "-$cpid" 2>/dev/null || true; }
trap stop_owned INT TERM
wait "$cpid"; rc=$?
# A trapped signal can interrupt wait before the collector exits. Settle only
# this exact group; never match another process by name.
if kill -0 "$cpid" 2>/dev/null; then wait "$cpid"; rc=$?; fi
kill "$wpid" 2>/dev/null || true
wait "$wpid" 2>/dev/null || true
# Leader exit is insufficient: probe the exact outer process group too.
if kill -0 -- "-$cpid" 2>/dev/null; then
  kill -TERM -- "-$cpid" 2>/dev/null || true
  for _ in 1 2 3 4 5; do kill -0 -- "-$cpid" 2>/dev/null || break; sleep 1; done
  if kill -0 -- "-$cpid" 2>/dev/null; then kill -KILL -- "-$cpid" 2>/dev/null || true; fi
  for _ in 1 2 3; do kill -0 -- "-$cpid" 2>/dev/null || break; sleep 1; done
fi
if kill -0 -- "-$cpid" 2>/dev/null; then
  printf '{"group_gone":false}\n' > "$FOOT_RUN/outer-group-state.json"
  rc=96
else
  printf '{"group_gone":true}\n' > "$FOOT_RUN/outer-group-state.json"
fi
[ ! -e "$FOOT_RUN/disk-stop" ] || rc=95
printf '%s\n' "$rc" > "$FOOT_RUN/exit.done.tmp"
mv "$FOOT_RUN/exit.done.tmp" "$FOOT_RUN/exit.done"
printf 'RUN-DONE rc=%s\n' "$rc" >> "$FOOT_RUN/run.log"
exit "$rc"
