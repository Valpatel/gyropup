"""Gyropup's pronunciation key, the Python side: what text is sent to a voice.

    from tools.audio.pronunciation import pronounce
    pronounce("Gyropup's turret")          # "gyro pup's turret"

    python3 tools/audio/pronunciation.py "Hi! I am Gyropup!"     # print what a voice is sent
    python3 tools/audio/pronunciation.py --show                  # espeak's phonemes for each entry, as written and as said (needs Piper)

The key is software/site/designer/character/pronunciation.json; software/site/designer/character/pronounce.js applies the same file the same way in
the browser (tests/site/content/test-pronunciation.mjs and tests/software/audio/test-pronunciation.py run the same examples on both). The rules:
an entry's `match` (a string or a list) is found case-insensitively as a whole word, optionally followed by 's, ’s,
s', s’ or s, which are kept; text inside the key's `protect` pattern (URLs, e-mail addresses, domain names) is never
changed; every entry is replaced in one pass, so a replacement is never matched again and applying the key twice
gives the same text as once.
"""
from __future__ import annotations

# Support direct-file CLI execution as well as checkout package imports.
if __package__ in (None, ''):
    import sys as _checkout_sys
    from pathlib import Path as _CheckoutPath
    _checkout_sys.path.insert(0, str(_CheckoutPath(__file__).resolve().parents[2]))


import json
import os
import re
import sys
from functools import lru_cache
from pathlib import Path

KEY_PATH = (Path(__file__).resolve().parents[2] / 'software/site/designer/character/pronunciation.json')
SUFFIX = "'s|’s|s'|s’|s"       # keep in step with pronounce.js
WORD = r'A-Za-z0-9_\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u024F'   # Latin letters too (not × or ÷): never inside another word
SPACE = r'\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff'   # JavaScript's \s, spelled out so both sides split text the same


def load_key(path: Path | str = KEY_PATH) -> dict:
    key = json.loads(Path(path).read_text(encoding='utf-8'))
    for i, e in enumerate(key.get('entries', [])):
        if not e.get('match') or not isinstance(e.get('say'), str) or not e['say'].strip():
            raise ValueError(f'pronunciation entry {i} needs a "match" and a "say"')
    return key


def _norm(s: str) -> str:
    return re.sub(r'\s+', ' ', s.strip().lower())


class Pronouncer:
    """A compiled key: call it on text."""

    def __init__(self, key: dict):
        self.version = key.get('version', 0)
        self.say: dict[str, str] = {}
        for e in key.get('entries', []):
            for m in ([e['match']] if isinstance(e['match'], str) else e['match']):
                self.say[_norm(m)] = e['say']
        alts = sorted(self.say, key=len, reverse=True)
        body = '|'.join(f'[{SPACE}]+'.join(re.escape(w) for w in m.split(' ')) for m in alts)
        self.words = re.compile(rf'(^|[^{WORD}])({body})({SUFFIX})?(?![{WORD}])', re.I | re.A) if alts else None
        # its whitespace is spelled out (SPACE), as in JS, so re.A changes nothing there
        self.protect = re.compile(key['protect'], re.I | re.A) if key.get('protect') else None

    def _words(self, text: str) -> str:
        if not self.words:
            return text
        return self.words.sub(lambda m: m.group(1) + self.say[_norm(m.group(2))] + (m.group(3) or ''), text)

    def __call__(self, text: str) -> str:
        text = str(text)
        if not self.protect:
            return self._words(text)
        out, at = [], 0
        for m in self.protect.finditer(text):
            out += [self._words(text[at:m.start()]), m.group(0)]
            at = m.end()
        out.append(self._words(text[at:]))
        return ''.join(out)


@lru_cache(maxsize=None)
def default() -> Pronouncer:
    return Pronouncer(load_key())


def pronounce(text: str) -> str:
    """Text as a voice should be sent it, with the repository's key."""
    return default()(text)


def _show() -> int:
    """espeak's phonemes for every entry, as written and as said, with the sidecar's voice (its flags and environment)."""
    import tools.audio.tts_server as tts_server                               # here, not at the top: tts_server imports this module
    a = tts_server.settings([])
    tts_server.need_piper(a)                        # or re-run this script under a python that has Piper
    from piper import PiperVoice
    v = PiperVoice.load(str(tts_server.find_voice(a.voice, [Path(d).expanduser() for d in a.voices_dir.split(os.pathsep) if d])))
    ph = lambda t: ' | '.join(''.join(s) for s in v.phonemize(t))   # noqa: E731
    for e in load_key()['entries']:
        for m in ([e['match']] if isinstance(e['match'], str) else e['match']):
            print(f'{m:16} {ph(m):28} -> {e["say"]:16} {ph(e["say"])}')
    return 0


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['--show']:
        sys.exit(_show())
    if not args:
        sys.exit(__doc__)
    print(pronounce(' '.join(args)))
