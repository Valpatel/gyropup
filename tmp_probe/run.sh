set -e
cd "$(dirname "$0")/.."
for v in orig current; do for c in R1 E1; do MESH=3 python tmp_probe/frame_probe.py $v $c 2>&1 | grep -v Warn | tail -4 & done; done; wait
