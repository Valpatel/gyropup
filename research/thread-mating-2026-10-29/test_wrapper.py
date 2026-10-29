"""Bounded wrapper controls with mocked tools; never runs CAD or substitutes its results."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT=Path(__file__).with_name('run-clocked-probe.sh')
SHA='2ad426943ce2c7232875e105e50810849f9a3e5e'

class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.output=self.root/'result'
        (self.root/'cad-agent-v042-thread-probe').mkdir();(self.root/'.venv/bin').mkdir(parents=True)
        bins=self.root/'mock-bin';bins.mkdir()
        def executable(path,text):path.write_text(text);path.chmod(0o755)
        executable(bins/'git', '#!/bin/bash\nif [ "$1" = rev-parse ]; then printf "%s\\n" "$MOCK_COMMIT"; elif [ "$1" = status ]; then printf "%s" "$MOCK_DIRTY"; else exit 9; fi\n')
        # Bypass private-input hashing ONLY in this control-flow fixture. The
        # published wrapper still asserts both exact STEP hashes with real Python.
        executable(bins/'python3','#!/bin/bash\ncat >/dev/null\nexit 0\n')
        executable(self.root/'.venv/bin/python','#!/usr/bin/python3\nimport json,os,sys\nwith open(os.environ["MOCK_CALLS"],"a") as f:f.write(json.dumps(sys.argv[1:])+"\\n")\n')
        self.calls=self.root/'calls.jsonl'
        self.env={**os.environ,'PATH':str(bins)+os.pathsep+os.environ['PATH'],
                  'CAD_RUN_ROOT':str(self.root),'CAD_PHASE_RUN':str(self.output),
                  'MOCK_COMMIT':SHA,'MOCK_DIRTY':'','MOCK_CALLS':str(self.calls)}
    def run_wrapper(self):return subprocess.run(['bash',str(SCRIPT)],env=self.env,capture_output=True,text=True)
    def test_existing_output_preserves_evidence(self):
        self.output.mkdir();log=self.output/'run.log';log.write_text('original evidence\n')
        self.assertNotEqual(self.run_wrapper().returncode,0)
        self.assertEqual(log.read_text(),'original evidence\n');self.assertFalse((self.output/'done').exists());self.assertFalse(self.calls.exists())
    def test_wrong_revision_never_reaches_cad(self):
        self.env['MOCK_COMMIT']='0'*40
        self.assertNotEqual(self.run_wrapper().returncode,0)
        self.assertFalse(self.calls.exists());self.assertEqual((self.output/'done').read_text(),'2\n')
    def test_dirty_checkout_never_reaches_cad(self):
        self.env['MOCK_DIRTY']=' M src/cadagent/gates/relations.py'
        self.assertNotEqual(self.run_wrapper().returncode,0);self.assertFalse(self.calls.exists())
    def test_fresh_reviewed_checkout_runs_both_mock_stages(self):
        result=self.run_wrapper();self.assertEqual(result.returncode,0,result.stderr)
        calls=[json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual([c[1] for c in calls],['prepare','measure'])
        for option in ['--location-a','--location-b']:
            matrix=json.loads(calls[0][calls[0].index(option)+1]);self.assertEqual(len(matrix),3);self.assertTrue(all(len(row)==4 for row in matrix))
        self.assertEqual((self.output/'done').read_text(),'0\n')
        self.assertIn('RUN-DONE rc=0',(self.output/'run.log').read_text())

if __name__=='__main__':unittest.main(verbosity=2)
