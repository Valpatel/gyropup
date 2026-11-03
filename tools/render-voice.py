"""Render every fixed line Gyropup says to a small recorded clip, for the public site.

    python3 tools/render-voice.py            # render new or changed lines, drop stale clips, rewrite the manifest
    python3 tools/render-voice.py --check    # CI: the clips match the lines, the key and the voice (no Piper needed)
    python3 tools/render-voice.py --force    # render every line again (a new take of the whole set)

The lines come from designer/character/lines.js (fixedLines(), read with node), the one place they are written. Each
is passed through the pronunciation key (tools/pronunciation.py, designer/character/pronunciation.json), spoken by
tools/tts_server.py's Voice (the same Piper voice and pup settings as the live sidecar, so recorded and live lines
sound alike), trimmed, and encoded to MP3. Clips go to designer/character/voice/<id>.mp3, where <id> is a hash of the
spoken text, the key's version and VOICE_TAG (voice, settings, render version, encoding); manifest.json maps each
written line to its clip. talk.js plays a line's clip and speaks live only when a line has none (an LLM answer).

Rendering needs piper-tts (re-runs itself under a python that has it, like the sidecar), the voice file, ffmpeg with
libmp3lame and node. --check needs only python3 and node: it recomputes the ids from the source and compares hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tts_server  # noqa: E402  (stdlib only at import; Piper is loaded by Voice)
from pronunciation import KEY_PATH, load_key  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LINES = ROOT / 'designer' / 'character' / 'lines.js'
OUT = ROOT / 'designer' / 'character' / 'voice'
MANIFEST = OUT / 'manifest.json'
BUDGET = 3 * 1024 * 1024        # bytes for the whole set (about 125 lines, 1.7 MB at the time of writing)

# The live sidecar's defaults (designer/character/README.md "Why en_US-hfc_female-medium"), spelled out so a change
# to them, here or there, is a deliberate re-render. hfc_female has no high-quality model; medium is its best.
VOICE = {'voice': tts_server.DEFAULT_VOICE, 'pitch': tts_server.DEFAULT_PITCH, 'speed': tts_server.DEFAULT_SPEED,
         'volume': 0.9, 'pause': 0.12}
# MP3 VBR V5 at the voice's 22.05 kHz, mono: about 52 kbit/s, every speech band within 1.6 dB of the WAV; it plays in
# every browser (iOS Safari included) and in the open-source Chromium the tests use, which has no AAC.
ENCODE = ['-ac', '1', '-c:a', 'libmp3lame', '-q:a', '5', '-map_metadata', '-1', '-fflags', '+bitexact', '-flags:a', '+bitexact']
VOICE_TAG = '|'.join([f'{k}={v}' for k, v in VOICE.items()] + [f'render={tts_server.RENDER}', 'mp3-v5-mono'])


def fixed_lines() -> list[str]:
    js = f"const m = await import({json.dumps(LINES.as_uri())}); console.log(JSON.stringify(m.fixedLines()));"
    out = subprocess.run(['node', '--input-type=module', '-e', js], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def plan() -> tuple[int, dict[str, dict]]:
    """For each written line: the text the voice is sent and its clip id."""
    version = load_key(KEY_PATH).get('version', 0)
    lines = {}
    for line in fixed_lines():
        spoken = tts_server.clean(line)              # whitespace, length cap, then the pronunciation key
        cid = hashlib.sha256(json.dumps([spoken, version, VOICE_TAG], ensure_ascii=False).encode()).hexdigest()[:16]
        lines[line] = {'spoken': spoken, 'clip': f'{cid}.mp3'}
    return version, lines


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check() -> int:
    stale = 'run tools/render-voice.py'
    errors = []
    try:
        man = json.loads(MANIFEST.read_text(encoding='utf-8'))
    except FileNotFoundError:
        sys.exit(f'[voice] {MANIFEST.relative_to(ROOT)} is missing: {stale}')
    version, want = plan()
    if man.get('voice_tag') != VOICE_TAG:
        errors.append(f'the voice settings changed ({man.get("voice_tag")} -> {VOICE_TAG})')
    if man.get('key_version') != version:
        errors.append(f'the pronunciation key version changed ({man.get("key_version")} -> {version})')
    have = man.get('lines', {})
    for line, w in want.items():
        h = have.get(line)
        if not h:
            errors.append(f'no clip for {line!r}')
        elif h.get('spoken') != w['spoken'] or h.get('clip') != w['clip']:
            errors.append(f'stale clip for {line!r} (now spoken as {w["spoken"]!r})')
        elif not (OUT / h['clip']).is_file():
            errors.append(f'{h["clip"]} is missing ({line!r})')
        elif sha(OUT / h['clip']) != h.get('sha256'):
            errors.append(f'{h["clip"]} does not match its recorded hash ({line!r})')
    errors += [f'manifest has a line no source says: {line!r}' for line in have if line not in want]
    used = {w['clip'] for w in want.values()}
    errors += [f'{p.name} is not used by any line' for p in OUT.glob('*.mp3') if p.name not in used]
    total = sum((OUT / c).stat().st_size for c in used if (OUT / c).is_file())
    if total != man.get('total_bytes'):
        errors.append(f'total_bytes says {man.get("total_bytes")}, the clips are {total}')
    if total > BUDGET:
        errors.append(f'the clips are {total / 1024:.0f} KiB, over the {BUDGET / 1024:.0f} KiB budget (BUDGET)')
    if errors:
        print('[voice] the recorded voice does not match the lines:\n  ' + '\n  '.join(errors) + f'\n  {stale}', file=sys.stderr)
        return 1
    print(f'[voice] {len(want)} lines, {len(used)} clips, {total / 1024:.0f} KiB of {BUDGET / 1024:.0f} KiB, key v{version}, {VOICE_TAG}')
    return 0


def render(force: bool) -> int:
    for k in [k for k in os.environ if k.startswith('GYROPUP_TTS_') and k not in ('GYROPUP_TTS_REEXEC', 'GYROPUP_TTS_PYTHON', 'GYROPUP_TTS_VOICES')]:
        del os.environ[k]                          # a developer's sidecar settings must not leak into the recorded set
    a = tts_server.settings(['--cache-dir', 'off', '--voice', str(VOICE['voice']), '--pitch', str(VOICE['pitch']),
                             '--speed', str(VOICE['speed']), '--volume', str(VOICE['volume']), '--pause', str(VOICE['pause'])])
    tts_server.need_piper(a)
    version, want = plan()
    old = {}
    if MANIFEST.is_file():
        old = json.loads(MANIFEST.read_text(encoding='utf-8')).get('lines', {})
    voice = None
    OUT.mkdir(parents=True, exist_ok=True)
    rendered = 0
    for line, w in want.items():
        f = OUT / w['clip']
        prev = old.get(line, {})
        if f.is_file() and not force and prev.get('clip') == w['clip'] and 'seconds' in prev:
            w['seconds'] = prev['seconds']
        else:
            voice = voice or tts_server.Voice(a)
            wav = voice.render(w['spoken'])
            with tempfile.NamedTemporaryFile(suffix='.wav') as tmp:
                tmp.write(wav)
                tmp.flush()
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', tmp.name, *ENCODE, str(f)], check=True)
            w['seconds'] = round((len(wav) - 44) / 2 / voice.sr, 2)
            rendered += 1
            print(f'[voice] {w["clip"]} {w["seconds"]:5.2f} s  {w["spoken"]}', flush=True)
        w['bytes'] = f.stat().st_size
        w['sha256'] = sha(f)
    used = {w['clip'] for w in want.values()}
    for p in OUT.glob('*.mp3'):
        if p.name not in used:
            p.unlink()
    total = sum(w['bytes'] for w in {w['clip']: w for w in want.values()}.values())
    if voice:
        engine, name = voice.engine, voice.name
    else:
        prev = json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.is_file() else {}
        engine, name = prev.get('engine'), prev.get('voice', {}).get('voice', VOICE['voice'])
    man = {'generator': 'tools/render-voice.py', 'source': 'designer/character/lines.js',
           'key': 'designer/character/pronunciation.json', 'key_version': version, 'voice_tag': VOICE_TAG,
           'voice': {**VOICE, 'voice': name}, 'engine': engine, 'encoding': 'MP3 VBR V5 (libmp3lame -q:a 5), mono, 22.05 kHz',
           'total_bytes': total, 'seconds': round(sum(w['seconds'] for w in want.values()), 1),
           'lines': {line: {k: w[k] for k in ('clip', 'spoken', 'seconds', 'bytes', 'sha256')} for line, w in want.items()}}
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'[voice] {rendered} rendered, {len(want)} lines, {len(used)} clips, {total / 1024:.0f} KiB, {man["seconds"]} s')
    return check()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true', help='verify only (no Piper): the clips match the lines, key and voice')
    ap.add_argument('--force', action='store_true', help='render every line again')
    a = ap.parse_args()
    if a.check:
        return check()
    # tts_server.need_piper re-runs this script with the same arguments under a python that has Piper
    sys.argv = [sys.argv[0]] + (['--force'] if a.force else [])
    return render(a.force)


if __name__ == '__main__':
    sys.exit(main())
