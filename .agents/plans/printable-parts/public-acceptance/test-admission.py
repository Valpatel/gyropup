"""Offline admission controls. Never launch a unit, Node or browser."""
import ast
import json
from pathlib import Path
import subprocess
import sys
import unittest
import tempfile
import shutil

P = Path(__file__).resolve().parent


class AdmissionTests(unittest.TestCase):
    def invoke(self, *args):
        with tempfile.TemporaryDirectory() as directory:
            packet = Path(directory)
            shutil.copyfile(P / 'run.py', packet / 'run.py')
            contract = json.loads((P / 'contract.TEMPLATE.json').read_text())
            contract['out'] = str(packet / 'output')
            (packet / 'contract.json').write_text(json.dumps(contract))
            command = [str(packet / 'run.py') if a == str(P / 'run.py') else a for a in args]
            before = {f.name for f in packet.iterdir()}
            result = subprocess.run([sys.executable, '-I', '-B', *command], text=True, capture_output=True, timeout=5)
            self.assertEqual(before, {f.name for f in packet.iterdir()})
            self.assertFalse((packet / 'execution-attempt.json').exists())
            self.assertFalse((packet / 'output').exists())
        self.assertNotEqual(result.returncode, 0)
        return result.stdout + result.stderr

    def test_optimized_python_refuses_before_any_admission_or_unit(self):
        self.assertIn('Refusing Python optimization', self.invoke('-O', str(P / 'run.py'), '--execute-reviewed'))

    def test_missing_explicit_invocation_refuses_before_contract(self):
        self.assertIn('Only the explicit reviewed invocation', self.invoke(str(P / 'run.py')))

    def test_disabled_concrete_contract_refuses_before_seal_or_unit(self):
        self.assertIs(json.loads((P / 'contract.TEMPLATE.json').read_text())['approved_for_execution'], False)
        self.assertIn('Prepared packet is not approved', self.invoke(str(P / 'run.py'), '--execute-reviewed'))

    def test_optimization_guard_precedes_contract_and_exclusive_marker(self):
        source = (P / 'run.py').read_text()
        ast.parse(source)
        self.assertLess(source.index('if not __debug__:'), source.index("c=json.loads"))
        self.assertIn("(P/'execution-attempt.json').open('x')", source)
        self.assertLess(source.index("h=c['deployed_html']"), source.index(".open('x')"))
        self.assertLess(source.index("for key in ['node','playwright','chrome','capture_protocol']"), source.index(".open('x')"))


if __name__ == '__main__':
    unittest.main()
