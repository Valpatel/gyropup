"""Explicit historical integrity; default current-source verification is unchanged."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.evidence.manufacturing.retained_fit_history import verify_archive

if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(verify_archive(), indent=2))
