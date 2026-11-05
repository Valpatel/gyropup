"""hardware/deploy/jetson/install.sh without a Jetson: a dry run changes nothing, a staged install writes the expected files, a
second run changes nothing (idempotent), the owner's settings are never overwritten, stable names are generated and
checked, LAN mode is opt-in with a token, and shellcheck has nothing to say (when it is installed).

    python3 hardware/deploy/jetson/test_install.py
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCRIPT = HERE / 'install.sh'


def run(*args, ok=True):
    p = subprocess.run(['bash', str(SCRIPT), *args], capture_output=True, text=True)
    if ok and p.returncode != 0:
        raise AssertionError(f'install.sh {args} failed ({p.returncode}): {p.stdout}{p.stderr}')
    return p


def files(root: Path):
    return sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file())


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='gyropup-deploy-'))

    def tearDown(self):
        shutil.rmtree(self.root)

    def stage(self, *extra):
        return run('--root', str(self.root), '--checkout', str(REPO), *extra)

    def test_dry_run_writes_nothing(self):
        p = run('--dry-run', '--root', str(self.root), '--checkout', str(REPO))
        self.assertEqual(files(self.root), [])
        self.assertIn('would install    /etc/systemd/system/gyropup-rs04-bridge.service', p.stdout)
        self.assertRegex(p.stdout, r'dry run: \d+ change\(s\) would be made')

    def test_dry_run_on_this_system_needs_no_root_and_changes_nothing(self):
        p = run('--dry-run')                         # the real / : read only
        self.assertIn('dry run:', p.stdout)

    def test_live_install_refuses_without_root(self):
        if os.geteuid() == 0:
            self.skipTest('running as root')
        p = run(ok=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn('needs root', p.stderr)

    def test_staged_install_and_idempotence(self):
        # The default checkout must follow the installed script's new source location.
        p = run('--root', str(self.root))
        want = ['etc/gyropup/can.env', 'etc/gyropup/rs04-bridge.env', 'etc/modules-load.d/gyropup-can.conf',
                'etc/systemd/system/gyropup-can@.service', 'etc/systemd/system/gyropup-rs04-bridge.service',
                'etc/sysusers.d/gyropup.conf', 'etc/udev/rules.d/70-gyropup-can-names.rules',
                'etc/udev/rules.d/80-gyropup-can.rules']
        self.assertEqual(files(self.root), want)
        self.assertIn('done: 8 change(s)', p.stdout)
        unit = (self.root / 'etc/systemd/system/gyropup-rs04-bridge.service').read_text()
        self.assertIn(f'WorkingDirectory={REPO}\n', unit)
        self.assertIn('ExecStart=/usr/bin/python3 -m rig.rs04_bridge --iface ${IFACE} --profile ${PROFILE} --port ${PORT} $BRIDGE_LAN', unit)
        self.assertIn('User=gyropup-bridge', unit)
        self.assertNotIn('--lan', unit.split('ExecStart=')[1].split('\n')[0])
        self.assertIn('bitrate "$BITRATE"', (self.root / 'etc/systemd/system/gyropup-can@.service').read_text())
        self.assertIn('BITRATE=1000000', (self.root / 'etc/gyropup/can.env').read_text())
        rules = (self.root / 'etc/udev/rules.d/80-gyropup-can.rules').read_text()
        self.assertIn('DRIVERS=="peak_usb|gs_usb"', rules)
        self.assertIn('gyropup-can@$name.service', rules)
        modules = (self.root / 'etc/modules-load.d/gyropup-can.conf').read_text().split()
        for m in ('can', 'can_raw', 'peak_usb', 'gs_usb'):
            self.assertIn(m, modules)
        again = self.stage()
        self.assertIn('done: 0 change(s)', again.stdout)
        self.assertNotRegex(again.stdout, r'^(install|update) ', 'a second run changes nothing')

    def test_owner_settings_are_never_overwritten(self):
        self.stage()
        env = self.root / 'etc/gyropup/rs04-bridge.env'
        env.write_text('IFACE=can_legs_a\nPROFILE=final\nPORT=8765\n')
        p = self.stage()
        self.assertIn('kept       /etc/gyropup/rs04-bridge.env', p.stdout)
        self.assertEqual(env.read_text(), 'IFACE=can_legs_a\nPROFILE=final\nPORT=8765\n')

    def test_a_changed_unit_is_updated(self):
        self.stage()
        unit = self.root / 'etc/systemd/system/gyropup-can@.service'
        unit.write_text('edited\n')
        p = self.stage()
        self.assertIn('update     /etc/systemd/system/gyropup-can@.service', p.stdout)
        self.assertIn('done: 1 change(s)', p.stdout)

    def test_help_is_the_header_only(self):
        p = run('--help')
        self.assertIn('What it installs', p.stdout)
        self.assertNotIn('set -euo', p.stdout)

    def test_stable_names(self):
        conf = self.root / 'names.conf'
        conf.write_text('# the leg buses\ncan_legs_a  path=platform-3610000.usb-usb-0:1.2:1.0\ncan_legs_b serial=0000ABCD\n')
        self.stage('--names', str(conf))
        rules = (self.root / 'etc/udev/rules.d/70-gyropup-can-names.rules').read_text()
        self.assertIn('ENV{ID_PATH}=="platform-3610000.usb-usb-0:1.2:1.0", NAME="can_legs_a"', rules)
        self.assertIn('ENV{ID_SERIAL_SHORT}=="0000ABCD", NAME="can_legs_b"', rules)
        conf.write_text('rs04 serial=00001234')               # no newline at the end: the line still counts
        self.stage('--names', str(conf))
        rules = (self.root / 'etc/udev/rules.d/70-gyropup-can-names.rules').read_text()
        self.assertIn('ENV{ID_SERIAL_SHORT}=="00001234", NAME="rs04"', rules)
        for bad in ('can0 path=x', 'a_name_that_is_far_too_long path=x', 'legs path=x"; RUN+="/bin/sh', 'legs mac=x',
                    'legs path=x\nlegs path=y', 'legs-a path=x', 'legs path=x\nlegs_b path=x'):
            conf.write_text(bad + '\n')
            p = run('--root', str(self.root), '--checkout', str(REPO), '--names', str(conf), ok=False)
            self.assertEqual(p.returncode, 2, bad)

    def test_lan_mode_is_opt_in_with_a_token(self):
        self.stage()
        dropin = self.root / 'etc/systemd/system/gyropup-rs04-bridge.service.d/lan.conf'
        token = self.root / 'etc/gyropup/bridge-token'
        self.assertFalse(dropin.exists())
        self.stage('--lan')
        self.assertIn('BRIDGE_LAN=--lan --token-file /etc/gyropup/bridge-token', dropin.read_text())
        self.assertGreaterEqual(len(token.read_text().strip()), 16)
        self.assertEqual(oct(token.stat().st_mode & 0o777), '0o640')
        first = token.read_text()
        self.assertIn('done: 0 change(s)', self.stage('--lan').stdout)
        self.assertEqual(token.read_text(), first, 'the token is kept')
        self.stage('--local')
        self.assertFalse(dropin.exists())

    def test_not_a_checkout(self):
        p = run('--root', str(self.root), '--checkout', str(self.root), ok=False)
        self.assertEqual(p.returncode, 2)

    def test_bridge_unit_runs_the_module_that_exists(self):
        unit = (HERE / 'files' / 'gyropup-rs04-bridge.service').read_text()
        module = re.search(r'-m (rig\.\w+)', unit).group(1)
        self.assertTrue((REPO / (module.replace('.', '/') + '.py')).is_file())

    def test_shellcheck(self):
        if not shutil.which('shellcheck'):
            self.skipTest('shellcheck is not installed')
        p = subprocess.run(['shellcheck', '-S', 'warning', str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout)


if __name__ == '__main__':
    unittest.main()
