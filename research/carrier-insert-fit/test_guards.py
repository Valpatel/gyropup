#!/usr/bin/env python3
"""Receipt corruption controls; only small copied sources/artifacts, no CAD kernel."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from verify import ROOT, check


class Guards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ('cad','catalog','designs'):
            for p in (ROOT/folder).rglob('*'):
                if p.is_file() and p.suffix in ('.py','.json'):
                    dest=self.root/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
        target=self.root/'research/carrier-insert-fit';target.mkdir(parents=True)
        for p in (ROOT/'research/carrier-insert-fit').glob('*.py'):shutil.copyfile(p,target/p.name)
        self.package=self.root/'exports/turret/carrier-insert-fit'
        shutil.copytree(ROOT/'exports/turret/carrier-insert-fit',self.package)
        check(self.root)

    def test_baseline(self):
        self.assertFalse(check(self.root)['physical_fit_verified'])

    def test_changed_mesh(self):
        with (self.package/'carrier-boss.stl').open('ab') as f:f.write(b'corrupt')
        with self.assertRaisesRegex(ValueError,'Changed specimen'):check(self.root)

    def test_extra_artifact(self):
        (self.package/'stale.gcode').write_text('not from this package')
        with self.assertRaisesRegex(ValueError,'membership'):check(self.root)

    def test_changed_geometry_source(self):
        with (self.root/'cad/turret_base_board.py').open('a') as f:f.write('\nINSERT_PILOT=4.1\n')
        with self.assertRaisesRegex(ValueError,'inputs changed'):check(self.root)

    def test_added_generation_dependency(self):
        (self.root/'research/carrier-insert-fit/helper.py').write_text('# new dependency\n')
        with self.assertRaisesRegex(ValueError,'sources changed'):check(self.root)

    def test_optional_parameter_override(self):
        parameters=self.root/'changed-parameters.json';parameters.write_text('{}')
        with patch.dict(os.environ, {'GYROPUP_CAD_PARAMS': str(parameters)}):
            with self.assertRaisesRegex(ValueError, 'Optional CAD parameter'):check(self.root)

    def test_false_qualification(self):
        p=self.package/'receipt.json';d=json.loads(p.read_text());d['physical_fit_verified']=True;p.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,'physical qualification'):check(self.root)


if __name__=='__main__':unittest.main()
