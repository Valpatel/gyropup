"""Prior-run evidence binding controls; no CAD or fetched native archive required."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / '.agents/plans/assembly-staging'
AUDIT = BASE / 'native-265/independent-audit.py'
spec = importlib.util.spec_from_file_location('native265_audit', AUDIT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class PriorBinding(unittest.TestCase):
    def setUp(self):
        self.full = json.loads((BASE / 'pair-study/plan.json').read_bytes())
        self.prior = json.loads((BASE / 'native-264/report.json').read_bytes())

    def test_real_retained_report_matches_seal_and_exact_prefix(self):
        member = json.loads((BASE / 'native-264/members.json').read_bytes())['report.json']
        self.assertEqual(member['sha256'], audit.PRIOR_REPORT_SHA256)
        self.assertEqual(member['bytes'], audit.PRIOR_REPORT_BYTES)
        self.assertEqual(audit.validate_prior_report(BASE / 'native-264/report.json', self.full), self.prior)
        self.assertEqual(hashlib.sha256((BASE / 'pair-study/plan.json').read_bytes()).hexdigest(), audit.FULL_PLAN_SHA256)

    def test_order_membership_states_and_completion_are_independent_checks(self):
        mutations = {
            'wrong member': lambda p: p['queries'][0].update(id='a' * 64),
            'duplicate': lambda p: p['queries'].__setitem__(1, copy.deepcopy(p['queries'][0])),
            'reordered': lambda p: p['queries'].reverse(),
            'deleted': lambda p: p['queries'].pop(),
            'wrong state': lambda p: p['queries'][0]['result'].update(state='seat'),
            'false transient': lambda p: p['queries'][0].update(transient_path_complete=False),
            'false complete': lambda p: p.update(complete=True),
            'wrong fixed': lambda p: p['queries'][0]['result'].update(part='unrelated'),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                bad = copy.deepcopy(self.prior)
                mutate(bad)
                with self.assertRaises(AssertionError):
                    audit.validate_prior_queries(bad, self.full)

    def test_changed_bytes_and_review_counterexample_cannot_write_cli_receipt(self):
        bad = BASE / 'native-265/review-counterexample/wrong-prior-42.json'
        self.assertEqual(len(json.loads(bad.read_bytes())['queries']), 42)
        with self.assertRaisesRegex(AssertionError, 'byte seal'):
            audit.validate_prior_report(bad, self.full)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            changed = root / 'changed.json'
            changed.write_bytes((BASE / 'native-264/report.json').read_bytes() + b'\n')
            with self.assertRaisesRegex(AssertionError, 'byte seal'):
                audit.validate_prior_report(changed, self.full)
            receipt = root / 'must-not-exist.json'
            result = subprocess.run([sys.executable, '-B', str(AUDIT), str(root / 'no-fetch-needed'),
                str(BASE / 'native-263/frame-members.json'), str(BASE / 'pair-study/plan.json'),
                str(bad), str(receipt)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Prior report byte seal', result.stderr)
            self.assertEqual(result.stdout, '')
            self.assertFalse(receipt.exists())


if __name__ == '__main__':
    unittest.main()
