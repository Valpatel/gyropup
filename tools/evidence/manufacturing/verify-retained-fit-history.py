"""Explicit historical integrity; default current-source verification is unchanged."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.evidence.manufacturing.retained_fit_history import verify_archive, crosscheck_matching_snapshot

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root',type=Path,help='Optional exact clean f77 matching-input checkout for CI byte cross-check; never executed')
    args=parser.parse_args()
    if args.input_root is not None:crosscheck_matching_snapshot(args.input_root)
    print(json.dumps(verify_archive(), indent=2))
