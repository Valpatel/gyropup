"""tools/check-hardware.py: the sourced-config check catches a value that drifted from its source, and the skeleton
check catches a folder missing its parts.

    python3 -m unittest tools/test_check_hardware.py
"""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('check_hardware', HERE / 'check-hardware.py')
ch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ch)
CFG = 'firmware/balance/include/gp/gp_config.h'


class Sources(unittest.TestCase):
    def test_the_tree_is_clean(self):
        self.assertEqual(ch.check(), [])

    def test_define_match_and_drift(self):
        good = {'a': {'id': 10}, 'sources': {'a.id': {'c_define': CFG, 'name': 'GP_VESC_ID_LEFT'}}}
        self.assertEqual(ch.source_problems('x', good), [])
        bad = {'a': {'id': 12}, 'sources': {'a.id': {'c_define': CFG, 'name': 'GP_VESC_ID_LEFT'}}}
        self.assertIn('its source says 10', ' '.join(ch.source_problems('x', bad)))

    def test_hex_and_float_defines(self):
        d = {'i2c': {'address': 64, 'r': 0.001}, 'sources': {
            'i2c.address': {'c_define': 'firmware/balance/include/gp/gp_ina228.h', 'name': 'GP_INA228_ADDR'},
            'i2c.r': {'c_define': 'firmware/balance/include/gp/gp_ina228.h', 'name': 'GP_SHUNT_FUSE_BOARD_OHM'}}}
        self.assertEqual(ch.source_problems('x', d), [])

    def test_contains_and_missing(self):
        d = {'boot': {'baud': 'VNWRG,05,921600', 'gone': 'VNWRG,05,9600'}, 'sources': {
            'boot.baud': {'contains': 'firmware/balance/src/mcu/board.c'},
            'boot.gone': {'contains': 'firmware/balance/src/mcu/board.c'},
            'boot.nothing': {'contains': 'firmware/balance/src/mcu/board.c'},
            'boot.nofile': {'c_define': 'no/such.h', 'name': 'X'}}}
        boot = d['boot']
        boot['nofile'] = 1
        out = ' '.join(ch.source_problems('x', d))
        self.assertNotIn('boot.baud', out)
        self.assertIn('boot.gone', out)
        self.assertIn('boot.nothing', out)
        self.assertIn('does not exist', out)

    def test_counts_and_a_dangling_pointer(self):
        d = {'b': {'s': 'VNWRG,75,3,1,01,0028', 'p': 1}, 'sources': {
            'b.s': {'contains': 'firmware/balance/src/mcu/board.c', 'count': 3},
            'b.p': {'json': 'exports/motor-day/derating.json', 'pointer': '/no/such/key'}}}
        out = ' '.join(ch.source_problems('x', d))
        self.assertIn('2 time(s), not 3', out)
        self.assertIn('/no/such/key does not resolve', out)


class Skeleton(unittest.TestCase):
    def test_a_bare_folder_and_a_bad_inventory_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ch.HW, root / 'hardware')
            (root / 'firmware').symlink_to(ch.ROOT / 'firmware')
            (root / 'docs').symlink_to(ch.ROOT / 'docs')
            for top in ('deploy', 'rig', 'designer', 'references', 'catalog', 'exports', 'research', 'cad', 'tools', 'sim'):
                if (ch.ROOT / top).exists():
                    (root / top).symlink_to(ch.ROOT / top)
            (root / 'hardware/sensors/new-thing').mkdir()
            inv = root / 'hardware/actuators/rs04/inventory.json'
            d = json.loads(inv.read_text())
            d['units'].pop()
            inv.write_text(json.dumps(d))
            old_root, old_hw = ch.ROOT, ch.HW
            ch.ROOT, ch.HW = root, root / 'hardware'
            try:
                out = ' '.join(ch.check())
            finally:
                ch.ROOT, ch.HW = old_root, old_hw
            self.assertIn('does not list hardware/sensors/new-thing/', out)
            self.assertIn('new-thing: no README.md', out)
            self.assertIn('3 unit records for 4 arrived or held', out)


if __name__ == '__main__':
    unittest.main()
