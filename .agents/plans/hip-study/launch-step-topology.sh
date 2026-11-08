#!/usr/bin/env bash
# Detached, owned compute-host invocation. Exact private paths come from the
# reviewed operator; this file neither installs nor changes the retained runtime.
set -uo pipefail
umask 077
: "${TOPOLOGY_RUN:?}" "${TOPOLOGY_HEAD:?}" "${TOPOLOGY_CPUS:?}" "${TOPOLOGY_RUNTIME:?}"
[ -d "$TOPOLOGY_RUN/src/.git" ] && [ -d "$TOPOLOGY_RUN/out" ] && [ -f "$TOPOLOGY_RUNTIME" ] || exit 90
cd "$TOPOLOGY_RUN/src" || exit 90
[ "$(git rev-parse HEAD)" = "$TOPOLOGY_HEAD" ] && [ -z "$(git status --porcelain)" ] || exit 91
export FLEET_RUN_OUT="$TOPOLOGY_RUN/out" HOME="$TOPOLOGY_RUN/home" TMPDIR="$TOPOLOGY_RUN/tmp"
export XDG_CACHE_HOME="$HOME/.cache" PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_MAX_THREADS=1
# Timeout's TERM reaches the collector, whose approved phase cleanup reaps its
# independent native group. An interrupted/missing final receipt is incomplete.
setsid timeout --signal=TERM --kill-after=20s 1800s taskset -c "$TOPOLOGY_CPUS" \
  /usr/bin/python3 -B .agents/plans/hip-study/collect-step-topology.py \
  --head "$TOPOLOGY_HEAD" --runtime "$TOPOLOGY_RUNTIME" < /dev/null > "$TOPOLOGY_RUN/run.log" 2>&1 &
cpid=$!
printf '%s\n' "$cpid" > "$TOPOLOGY_RUN/collector-group.pid"
disk_watch() {
  while sleep 5; do
    kill -0 "$cpid" 2>/dev/null || return 0
    used=$(timeout 5s du -sx --block-size=1 -- "$TOPOLOGY_RUN" | cut -f1) || used=unknown
    if [ "$used" = unknown ] || [ "${used:-0}" -gt 8589934592 ]; then
      printf '%s\n' "Owned scratch exceeded 8 GiB or disk measurement failed" > "$TOPOLOGY_RUN/disk-stop"
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
  printf '{"group_gone":false}\n' > "$TOPOLOGY_RUN/outer-group-state.json"
  rc=96
else
  printf '{"group_gone":true}\n' > "$TOPOLOGY_RUN/outer-group-state.json"
fi
[ ! -e "$TOPOLOGY_RUN/disk-stop" ] || rc=95
printf '%s\n' "$rc" > "$TOPOLOGY_RUN/exit.done.tmp"
mv "$TOPOLOGY_RUN/exit.done.tmp" "$TOPOLOGY_RUN/exit.done"
printf 'RUN-DONE rc=%s\n' "$rc" >> "$TOPOLOGY_RUN/run.log"
exit "$rc"
