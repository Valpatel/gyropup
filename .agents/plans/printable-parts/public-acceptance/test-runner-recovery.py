"""Offline failure controls: no systemd unit, browser, network or public run."""
import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).with_name('run.py')
NODE = next(node for node in ast.parse(SOURCE.read_text()).body
            if isinstance(node, ast.FunctionDef) and node.name == 'execute_owned_unit')
CODE = compile(ast.Module(body=[NODE], type_ignores=[]), str(SOURCE), 'exec')


class RecoveryTests(unittest.TestCase):
    def exercise(self, outcomes, *, query_error=None, live=None):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            packet = Path(directory)
            output = packet / 'output'
            output.mkdir()
            if live is not None:
                (output / 'live-unit.json').write_text(live)

            def run(command, **kwargs):
                calls.append(command)
                value = outcomes[len(calls) - 1]
                if isinstance(value, BaseException):
                    raise value
                return SimpleNamespace(returncode=value)

            def show():
                if query_error:
                    raise query_error
                return {'returncode': 1, 'properties': {'LoadState': 'not-found'}}

            namespace = {
                'P': packet, 'c': {'out': str(output)},
                'unit': 'gy318-public-acceptance-synthetic.service',
                'command': ['systemd-run', 'synthetic-only'],
                'Path': Path, 'json': json, 'sys': sys, 'show': show,
                'subprocess': SimpleNamespace(run=run, STDOUT=subprocess.STDOUT,
                    TimeoutExpired=subprocess.TimeoutExpired,
                    SubprocessError=subprocess.SubprocessError),
            }
            exec(CODE, namespace)
            result = namespace['execute_owned_unit']()
            saved = json.loads((packet / 'terminal-cleanup.json').read_text())
            self.assertEqual(result, saved)
            self.assertFalse(saved['terminal_empty_or_absent'])
            return saved, calls

    def test_launch_error_retains_receipt_without_stopping_an_unlaunched_unit(self):
        saved, calls = self.exercise([OSError('synthetic launch failure')])
        self.assertEqual(len(calls), 1)
        self.assertEqual(saved['exception'], 'OSError')
        self.assertEqual(saved['collector_errors'][0]['stage'], 'launch-or-log')

    def test_timeout_and_failed_stop_still_retain_receipt(self):
        saved, calls = self.exercise([
            subprocess.TimeoutExpired('synthetic-launch', 495),
            subprocess.TimeoutExpired('synthetic-stop', 10),
        ])
        self.assertEqual(calls[1], ['systemctl', '--user', 'stop',
                                  'gy318-public-acceptance-synthetic.service'])
        self.assertEqual(len(calls), 2)
        self.assertEqual(saved['exception'], 'TimeoutExpired')
        self.assertEqual(saved['collector_errors'][0]['stage'], 'stop')

    def test_nonzero_stop_is_not_accepted_as_cleanup(self):
        saved, calls = self.exercise([KeyboardInterrupt(), 5])
        self.assertEqual(len(calls), 2)
        self.assertEqual(saved['exception'], 'KeyboardInterrupt')
        self.assertIn('exited 5', saved['collector_errors'][0]['message'])

    def test_terminal_query_failure_is_recorded(self):
        saved, calls = self.exercise([1], query_error=subprocess.TimeoutExpired('query', 5))
        self.assertEqual(len(calls), 1)
        self.assertEqual(saved['collector_errors'][0]['stage'], 'terminal-query')

    def test_malformed_live_receipt_cannot_supply_cleanup_proof(self):
        saved, _ = self.exercise([0], live='{broken')
        self.assertFalse(saved['live_unit_captured'])
        self.assertEqual(saved['collector_errors'][0]['stage'], 'live-receipt-or-cgroup')

    def test_wrong_unit_cgroup_is_never_used(self):
        live = json.dumps({'properties': {'ControlGroup': '/unowned/another.service'}})
        saved, _ = self.exercise([0], live=live)
        self.assertFalse(saved['owned_cgroup_checked'])
        self.assertEqual(saved['collector_errors'][0]['type'], 'AssertionError')


if __name__ == '__main__':
    unittest.main()
