"""Gyropup's voice: a small Piper TTS sidecar for designer/character/talk.js.

    python3 tools/tts_server.py                                   # http://127.0.0.1:8081 with the default voice
    python3 tools/tts_server.py --voice en_US-amy-medium --pitch 0
    python3 tools/tts_server.py --say "Hi! I am Gyropup!" --out hi.wav     # one line to a WAV file, no server

    GET /health        {"ok": true, "voice": ..., "label": ..., "rate": 1, ...}  (talk.js probes this first)
    GET /tts?text=...  audio/wav, 16-bit mono; every line is cached in memory and on disk
    GET /voices        the voices in the voice folders

The pup character is made here, not in the browser: Piper speaks with longer phonemes, then a resample lifts the pitch
(and the formants, so it sounds smaller and younger) and brings the pace back, so every client hears the same voice.
/health says `rate: 1` so talk.js plays it as it is. CORS answers pages from this machine or the LAN (--origins).

Settings are flags or GYROPUP_TTS_* environment variables (a flag wins); see designer/character/README.md. Piper
(`pip install piper-tts`) runs in-process with the voice loaded once; if this python cannot import it, the server
re-runs itself under one that can (GYROPUP_TTS_PYTHON, else a python3.x on PATH). Nothing else is needed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import wave
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DEFAULT_VOICE = 'en_US-hfc_female-medium'
DEFAULT_PITCH = 2.0          # semitones up: a pup, not a newsreader
DEFAULT_SPEED = 0.95         # a touch slower than Piper's pace once lifted: easy for kids to follow
DATA = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
CACHE = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache')
MAX_CHARS = 1000
RENDER = 2                   # bump when render() changes, so lines cached by the old one are not served
# names espeak says wrongly: Gyropup is "JYE-roh-pup", Tritium "TRIT-ee-um"
RESPELL = {'gyropup': 'Gyro-pup', 'tritium': 'Trittium'}
LOCAL = re.compile(r'^https?://(localhost|127(\.\d+){3}|\[::1\]|0\.0\.0\.0|10(\.\d+){3}|192\.168(\.\d+){2}'
                   r'|172\.(1[6-9]|2\d|3[01])(\.\d+){2}|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])(\.\d+){2}'   # + Tailscale
                   r'|[\w.-]+\.(local|lan|ts\.net))(:\d+)?$', re.I)


def settings(argv=None) -> argparse.Namespace:
    env = lambda k, d=None: os.environ.get('GYROPUP_TTS_' + k, d)   # noqa: E731
    ap = argparse.ArgumentParser(description="Gyropup's Piper TTS sidecar for designer/character/talk.js")
    ap.add_argument('--voice', default=env('VOICE', DEFAULT_VOICE), help='voice name in a voice folder, or a .onnx path')
    ap.add_argument('--speaker', default=env('SPEAKER'), help='speaker name or id, for multi-speaker voices')
    ap.add_argument('--pitch', type=float, default=float(env('PITCH', DEFAULT_PITCH)), help='semitones up (or down)')
    ap.add_argument('--speed', type=float, default=float(env('SPEED', DEFAULT_SPEED)), help='pace, 1 = Piper\'s own')
    ap.add_argument('--volume', type=float, default=float(env('VOLUME', 0.9)), help='peak level, 0..1')
    ap.add_argument('--pause', type=float, default=float(env('PAUSE', 0.12)), help='seconds between sentences')
    ap.add_argument('--noise-scale', type=float, default=env('NOISE_SCALE'), help='Piper expressiveness (voice default)')
    ap.add_argument('--noise-w', type=float, default=env('NOISE_W'), help='Piper rhythm variation (voice default)')
    ap.add_argument('--voices-dir', default=env('VOICES', str(DATA / 'piper-voices')), help=f'voice folders, {os.pathsep}-separated')
    ap.add_argument('--cache-dir', default=env('CACHE', str(CACHE / 'gyropup-tts')), help="rendered lines; 'off' for memory only")
    ap.add_argument('--host', default=env('HOST', '127.0.0.1'), help='0.0.0.0 to serve the LAN')
    ap.add_argument('--port', type=int, default=int(env('PORT', 8081)))
    ap.add_argument('--origins', default=env('ORIGINS', 'local'), help="CORS: 'local' (this machine and the LAN), '*', or a comma list")
    ap.add_argument('--python', default=env('PYTHON'), help='a python that can import piper (found automatically)')
    ap.add_argument('--say', help='speak this line to --out (or stdout) and exit')
    ap.add_argument('--out', help='WAV file for --say')
    return ap.parse_args(argv)


def need_piper(a: argparse.Namespace):
    """Import Piper here, or re-run this script under a python that has it."""
    try:
        import piper  # noqa: F401
        return
    except ImportError:
        pass
    if not os.environ.get('GYROPUP_TTS_REEXEC'):
        here = os.path.realpath(sys.executable)
        for c in ([a.python] if a.python else [f'python3.{m}' for m in range(14, 8, -1)] + ['python3']):
            exe = c if os.sep in c else shutil.which(c)
            if not exe or os.path.realpath(exe) == here:
                continue
            if subprocess.run([exe, '-c', 'import piper'], capture_output=True).returncode == 0:
                print(f'[tts] {sys.executable} has no piper; running under {exe}', file=sys.stderr, flush=True)
                os.environ['GYROPUP_TTS_REEXEC'] = '1'
                os.execv(exe, [exe, os.path.abspath(__file__), *sys.argv[1:]])
    sys.exit('[tts] Piper is not installed for any python3 on PATH: python3 -m pip install --user piper-tts '
             '(or point GYROPUP_TTS_PYTHON at a venv that has it)')


def find_voice(name: str, dirs: list[Path]) -> Path:
    p = Path(name).expanduser()
    if p.suffix == '.onnx' and p.is_file():
        return p
    for d in dirs:
        if (d / f'{name}.onnx').is_file():
            return d / f'{name}.onnx'
    sys.exit(f'[tts] voice {name!r} is not in {", ".join(map(str, dirs))}. Fetch it (two files, from rhasspy/piper-voices):\n'
             f'  {Path(sys.executable).name} -m piper.download_voices {name} --download-dir {dirs[0]}')


def clean(text: str) -> str:
    text = re.sub(r'[\x00-\x1f\x7f]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()[:MAX_CHARS]
    return re.sub(r'\b(' + '|'.join(RESPELL) + r')\b', lambda m: RESPELL[m.group(1).lower()], text, flags=re.I)


class Voice:
    """A Piper voice with Gyropup's settings: speak, shape (pitch, pace, level), cache."""

    def __init__(self, a: argparse.Namespace):
        import numpy as np
        from importlib.metadata import version
        from piper import PiperVoice, SynthesisConfig
        self.np, self.a = np, a
        self.path = find_voice(a.voice, [Path(d).expanduser() for d in a.voices_dir.split(os.pathsep) if d])
        self.piper = PiperVoice.load(str(self.path))
        cfg = self.piper.config
        self.sr = cfg.sample_rate
        self.name = self.path.name[:-len('.onnx')]
        self.speaker = None
        if cfg.num_speakers > 1:
            spk = a.speaker or '0'
            self.speaker = cfg.speaker_id_map.get(spk, int(spk) if spk.isdigit() else None)
            if self.speaker is None:
                sys.exit(f'[tts] {self.name} has no speaker {spk!r} (it has {cfg.num_speakers}: ids 0..{cfg.num_speakers - 1} or names)')
        short = re.sub(r'^[a-z]{2,3}_[A-Z]{2}-|-(x_low|low|medium|high)$', '', self.name)
        self.label = short + (f'#{a.speaker}' if self.speaker is not None and a.speaker else '')
        self.engine = f'piper-tts {version("piper-tts")}'
        # Lifting the pitch by resampling also speeds it up by the same factor, so Piper first speaks that much slower.
        self.lift = 2 ** (a.pitch / 12)
        self.syn = SynthesisConfig(speaker_id=self.speaker, length_scale=cfg.length_scale * self.lift / a.speed,
                                   noise_scale=a.noise_scale, noise_w_scale=a.noise_w)
        st = self.path.stat()
        key = json.dumps([self.name, st.st_size, int(st.st_mtime), self.speaker, a.pitch, a.speed, a.volume, a.pause,
                          a.noise_scale, a.noise_w, RENDER])
        tag = hashlib.sha1(key.encode()).hexdigest()[:10]
        self.disk = None if a.cache_dir in ('', 'off') else Path(a.cache_dir).expanduser() / f'{self.name}-{tag}'
        self.mem: OrderedDict[str, bytes] = OrderedDict()
        self.lock = threading.Lock()

    def info(self) -> dict:
        return {'ok': True, 'voice': self.name, 'label': self.label, 'speaker': self.a.speaker if self.speaker is not None else None,
                'sample_rate': self.sr, 'pitch_st': self.a.pitch, 'speed': self.a.speed, 'rate': 1, 'engine': self.engine,
                'cached': len(self.mem)}

    def wav(self, text: str) -> tuple[bytes, str]:
        """WAV bytes for a line, and where they came from: memory, disk or piper."""
        text = clean(text)
        h = hashlib.sha1(text.encode()).hexdigest()[:24]
        with self.lock:                                   # one synthesis at a time; a repeat waits, then hits the cache
            if h in self.mem:
                self.mem.move_to_end(h)
                return self.mem[h], 'memory'
            f = self.disk / f'{h}.wav' if self.disk else None
            if f and f.is_file():
                data, src = f.read_bytes(), 'disk'
            else:
                data, src = self.render(text), 'piper'
                if f:
                    f.parent.mkdir(parents=True, exist_ok=True)
                    f.with_suffix('.tmp').write_bytes(data)
                    f.with_suffix('.tmp').replace(f)
            self.mem[h] = data
            while len(self.mem) > 300:
                self.mem.popitem(last=False)
            return data, src

    def render(self, text: str) -> bytes:
        np, sr = self.np, self.sr
        gap = np.zeros(int(self.a.pause * self.lift * sr), dtype=np.float32)
        parts = []
        for chunk in self.piper.synthesize(text, syn_config=self.syn):    # one chunk per sentence
            parts += [gap, chunk.audio_float_array] if parts else [chunk.audio_float_array]
        x = np.concatenate(parts).astype(np.float64) if parts else np.zeros(sr // 10)
        loud = np.flatnonzero(np.abs(x) > 0.02 * (np.abs(x).max() or 1))    # trim the silence at the ends: it starts sooner
        if loud.size:
            x = x[max(0, loud[0] - sr // 40):loud[-1] + sr // 20]
        if self.lift != 1:
            # band-limited resample to len/lift samples at the same rate: every frequency moves up by `lift`
            n = max(1, int(round(len(x) / self.lift)))
            x = np.fft.irfft(np.fft.rfft(x)[:n // 2 + 1], n) * (n / len(x))
        x *= self.a.volume / (np.abs(x).max() or 1)
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((np.clip(x, -1, 1) * 32767).astype('<i2').tobytes())
        return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    server_version = 'GyropupTTS/1'
    voice: Voice
    origins = 'local'

    def cors(self):
        o, rule = self.headers.get('Origin'), self.origins
        if o and (rule == '*' or (rule == 'local' and LOCAL.match(o)) or o in [s.strip() for s in rule.split(',')]):
            self.send_header('Access-Control-Allow-Origin', '*' if rule == '*' else o)
        self.send_header('Vary', 'Origin')

    def reply(self, code: int, body: bytes, ctype: str, note: str = ''):
        self.note = note                                  # for the log line send_response writes
        self.send_response(code)
        self.cors()
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def json(self, code: int, obj: dict):
        self.reply(code, (json.dumps(obj) + '\n').encode(), 'application/json')

    def do_OPTIONS(self):                                 # preflight (a plain GET needs none; private-network checks do)
        self.note = ''
        self.send_response(204)
        self.cors()
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', self.headers.get('Access-Control-Request-Headers') or 'Content-Type')
        if self.headers.get('Access-Control-Request-Private-Network'):
            self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.send_header('Access-Control-Max-Age', '600')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == '/health':
            return self.json(200, self.voice.info())
        if u.path == '/tts':
            text = (parse_qs(u.query).get('text') or [''])[0]
            if not text.strip():
                return self.json(400, {'error': 'missing text'})
            t0 = time.time()
            try:
                data, src = self.voice.wav(text)
            except Exception as e:                        # a line Piper cannot speak: say so, keep serving
                return self.json(500, {'error': 'synthesis failed', 'detail': str(e)[-300:]})
            return self.reply(200, data, 'audio/wav', f'{src} {(time.time() - t0) * 1000:.0f} ms "{clean(text)[:50]}"')
        if u.path == '/voices':
            dirs = [Path(d).expanduser() for d in self.voice.a.voices_dir.split(os.pathsep) if d]
            names = sorted({p.name[:-len('.onnx')] for d in dirs if d.is_dir() for p in d.glob('*.onnx')})
            return self.json(200, {'current': self.voice.name, 'voices': names})
        if u.path == '/':
            return self.reply(200, __doc__.encode(), 'text/plain; charset=utf-8')
        return self.json(404, {'error': 'not found'})

    def log_request(self, code='-', size='-'):
        path = urlparse(self.path).path
        print(f'[tts] {time.strftime("%H:%M:%S")} {self.command} {path} {getattr(code, "value", code)} {getattr(self, "note", "")}'.rstrip(),
              flush=True)

    def log_message(self, fmt, *args):
        print(f'[tts] {fmt % args}', file=sys.stderr, flush=True)


def main() -> int:
    a = settings()
    need_piper(a)
    t0 = time.time()
    voice = Voice(a)
    if a.say is not None:
        data, _ = voice.wav(a.say)
        (Path(a.out).write_bytes(data) if a.out else sys.stdout.buffer.write(data))
        return 0
    voice.render('Hi!')                                   # warm up the model before the first real line
    Handler.voice, Handler.origins = voice, a.origins
    try:
        srv = ThreadingHTTPServer((a.host, a.port), Handler)
    except OSError as e:
        sys.exit(f'[tts] cannot listen on {a.host}:{a.port}: {e.strerror} (another sidecar running? --port to move)')
    srv.daemon_threads = True
    print(f'[tts] {voice.name}{f" speaker {a.speaker}" if voice.speaker is not None else ""}, pitch {a.pitch:+g} st, '
          f'speed {a.speed:g}, {voice.engine}, cache {voice.disk or "memory only"} ({time.time() - t0:.1f} s to load)', flush=True)
    print(f'[tts] http://{a.host}:{a.port}/tts?text=Hello  (health: /health)', flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
