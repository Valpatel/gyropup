"""The pronunciation key, Python side (tools/pronunciation.py, tools/tts_server.py), and its agreement with the browser
side (designer/character/pronounce.js) on the same key file. Needs python3 and node; no Piper.

    python3 tools/test-pronunciation.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import pronunciation as P  # noqa: E402
import tts_server  # noqa: E402

KEY = P.load_key()
FIXTURE = {'version': 9, 'protect': KEY['protect'], 'entries': [
    {'match': 'Gyropup', 'say': 'gyro pup'},
    {'match': ['cad-agent', 'cad agent'], 'say': 'cad agent'},      # a list, a hyphen, a space
    {'match': 'cad', 'say': 'kad'},                                   # shorter than, and inside, the entry above
    {'match': 'cyan', 'say': 'sigh-an'},                              # stress: hyphen-joined, stressed on the first part
]}


def node_pronounce(key: dict | None, texts: list[str]) -> list[str]:
    """The browser implementation, run by node on the same inputs (key None: the repository's key file)."""
    js = ("import { compileKey } from " + json.dumps((ROOT / 'designer/character/pronounce.js').as_uri()) + ";"
          "import { readFileSync } from 'node:fs';"
          "const [key, texts] = JSON.parse(readFileSync(0, 'utf8'));"
          "const k = key ?? JSON.parse(readFileSync(" + json.dumps(str(P.KEY_PATH)) + ", 'utf8'));"
          "const f = compileKey(k); console.log(JSON.stringify(texts.map(f)));")
    out = subprocess.run(['node', '--input-type=module', '-e', js], input=json.dumps([key, texts]), capture_output=True,
                         text=True, check=True).stdout
    return json.loads(out)


class Key(unittest.TestCase):
    def test_examples(self):
        for written, spoken in KEY['examples']:
            self.assertEqual(P.pronounce(written), spoken, written)

    def test_gyropup_forms(self):
        f = P.Pronouncer(FIXTURE)
        cases = {
            'Gyropup': 'gyro pup', 'gyropup': 'gyro pup', 'GyroPup': 'gyro pup', 'GYROPUP!': 'gyro pup!',
            "Gyropup's": "gyro pup's", 'Gyropup’s': 'gyro pup’s', 'Gyropups': 'gyro pups', "Gyropups' legs": "gyro pups' legs",
            'Gyropupper': 'Gyropupper', 'minigyropup': 'minigyropup', 'gyropup2': 'gyropup2', 'gyropup_v2': 'gyropup_v2',
            'Gyropup Gyropup': 'gyro pup gyro pup', '"Gyropup"': '"gyro pup"', 'Gyropup.': 'gyro pup.',
            'https://gyropup.com/Gyropup': 'https://gyropup.com/Gyropup', 'gyropup.com': 'gyropup.com',
            'www.gyropup.com/x Gyropup': 'www.gyropup.com/x gyro pup', 'pup@gyropup.dev': 'pup@gyropup.dev',
            'see https://github.com/Valpatel/gyropup, Gyropup': 'see https://github.com/Valpatel/gyropup, gyro pup',
        }
        for written, spoken in cases.items():
            self.assertEqual(f(written), spoken, written)

    def test_longest_match_and_lists(self):
        f = P.Pronouncer(FIXTURE)
        self.assertEqual(f('Run cad-agent, a CAD AGENT, in cad'), 'Run cad agent, a cad agent, in kad')
        self.assertEqual(f('cadence and decade'), 'cadence and decade')

    def test_emphasis_entry(self):
        # cyan: espeak stresses the second syllable; the hyphenated respelling moves it to the first (README)
        self.assertEqual(P.Pronouncer(FIXTURE)('Cyan eyes, cyanide'), 'sigh-an eyes, cyanide')
        self.assertEqual(P.pronounce('My eyes glow cyan.'), 'My eyes glow sigh-an.')

    def test_idempotent(self):
        texts = [w for w, _ in KEY['examples']]
        for e in KEY['entries'] + FIXTURE['entries']:
            for m in ([e['match']] if isinstance(e['match'], str) else e['match']):
                texts += [m, m + "'s", m + 's', f'A {m}s’ thing', e['say']]
        for f in (P.default(), P.Pronouncer(FIXTURE)):
            for t in texts:
                once = f(t)
                self.assertEqual(f(once), once, t)
        self.assertEqual(P.pronounce('gyro pup'), 'gyro pup')

    def test_entries_are_valid(self):
        for e in KEY['entries']:
            self.assertTrue(e.get('why'), f'{e["match"]}: say why the entry exists')
            self.assertFalse(re.search(r'\b[A-Z]{2,}\b', e['say']), f'{e["say"]}: espeak spells all-caps words')
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / 'key.json'
            bad.write_text(json.dumps({'entries': [{'match': 'x', 'say': ' '}]}))
            with self.assertRaises(ValueError):
                P.load_key(bad)

    def test_sidecar_applies_key_once(self):
        self.assertEqual(tts_server.clean('Hi! I am \n Gyropup!'), 'Hi! I am gyro pup!')
        self.assertEqual(tts_server.clean(tts_server.clean("Gyropup's day")), "gyro pup's day")
        self.assertNotIn('RESPELL', vars(tts_server), 'one key: no second respelling table in the sidecar')


class SameKeyBothSides(unittest.TestCase):
    def test_same_file(self):
        self.assertEqual(P.KEY_PATH, ROOT / 'designer' / 'character' / 'pronunciation.json')
        js = (ROOT / 'designer/character/pronounce.js').read_text()
        self.assertIn("new URL('./pronunciation.json', import.meta.url)", js)
        self.assertIn('from pronunciation import pronounce', (TOOLS / 'tts_server.py').read_text())

    def test_same_results(self):
        lines = json.loads(subprocess.run(['node', '--input-type=module', '-e',
                                           f"const m = await import({json.dumps((ROOT / 'designer/character/lines.js').as_uri())});"
                                           "console.log(JSON.stringify(m.fixedLines()))"],
                                          capture_output=True, text=True, check=True).stdout)
        texts = [w for w, _ in KEY['examples']] + lines + ['GyroPups’ “Gyropup” (gyropup) gyropup.net/x', 'Tritium-cyan aww zzz']
        self.assertEqual(node_pronounce(None, texts), [P.pronounce(t) for t in texts])
        fx = ['Run cad-agent, a CAD AGENT, in cad', 'Cyan eyes, cyanide', "Gyropup's"]
        self.assertEqual(node_pronounce(FIXTURE, fx), [P.Pronouncer(FIXTURE)(t) for t in fx])


if __name__ == '__main__':
    unittest.main(verbosity=1)
