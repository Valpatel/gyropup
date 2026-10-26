#!/bin/sh
# Mirror the overnight design loop's leaderboard from the machine running it (default rtx4090) into this checkout, so
# the Results page shows it (and live-reloads). Usage: tools/mirror_iterate.sh [host] [seconds between copies]
HOST=${1:-rtx4090}; EVERY=${2:-120}
cd "$(dirname "$0")/.." || exit 1
mkdir -p exports/iterate
while true; do
  rsync -q "$HOST:Code/gyropup/exports/iterate/leaderboard.json" exports/iterate/leaderboard.json.part && mv exports/iterate/leaderboard.json.part exports/iterate/leaderboard.json
  sleep "$EVERY"
done
