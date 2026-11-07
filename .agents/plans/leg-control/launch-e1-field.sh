#!/usr/bin/env bash
# Detached, owned compute-host invocation. Exact private paths come from the
# reviewed operator; this file neither installs nor changes the retained runtime.
set -uo pipefail
umask 077
: "${E1_RUN:?}" "${E1_HEAD:?}" "${E1_CPUS:?}" "${E1_RUNTIME:?}"
[ -d "$E1_RUN/src/.git" ] && [ -d "$E1_RUN/out" ] && [ -f "$E1_RUNTIME" ] || exit 90
cd "$E1_RUN/src" || exit 90
[ "$(git rev-parse HEAD)" = "$E1_HEAD" ] && [ -z "$(git status --porcelain)" ] || exit 91
export FLEET_RUN_OUT="$E1_RUN/out" HOME="$E1_RUN/home" TMPDIR="$E1_RUN/tmp"
export XDG_CACHE_HOME="$HOME/.cache" PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_MAX_THREADS=1
# Timeout's TERM reaches the collector, whose approved phase cleanup reaps its
# independent native group. An interrupted/missing final receipt is incomplete.
setsid timeout --signal=TERM --kill-after=20s 1800s taskset -c "$E1_CPUS" \
  /usr/bin/python3 -B .agents/plans/leg-control/regenerate-e1-field.py \
  --head "$E1_HEAD" --runtime "$E1_RUNTIME" < /dev/null > "$E1_RUN/run.log" 2>&1 &
cpid=$!
printf '%s\n' "$cpid" > "$E1_RUN/collector-group.pid"
disk_watch() {
  while sleep 5; do
    kill -0 "$cpid" 2>/dev/null || return 0
    used=$(timeout 5s du -sx --block-size=1 -- "$E1_RUN" | cut -f1) || used=unknown
    if [ "$used" = unknown ] || [ "${used:-0}" -gt 8589934592 ]; then
      printf '%s\n' "Owned scratch exceeded 8 GiB or disk measurement failed" > "$E1_RUN/disk-stop"
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
[ ! -e "$E1_RUN/disk-stop" ] || rc=95
printf '%s\n' "$rc" > "$E1_RUN/exit.done.tmp"
mv "$E1_RUN/exit.done.tmp" "$E1_RUN/exit.done"
printf 'RUN-DONE rc=%s\n' "$rc" >> "$E1_RUN/run.log"
exit "$rc"
