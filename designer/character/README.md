# character/

Gyropup's personality in the browser: its eyes and its voice.

| File | What |
|---|---|
| `eyes.js` | `createEyes()`: two canvas-texture eye screens with eased expressions, blinks and gaze drift |
| `talk.js` | `mountTalk()`: speech bubble over the head, spoken voice (TTS), listening (STT), a small brain, canned reactions to sim events, and a bottom chat dock |
| `talk.css` | The bubble and dock in the HUD skin (loaded by `talk.js` itself via `import.meta.url`) |
| `talk-demo.html` | Try `talk.js` alone: a cube-headed stand-in pup, event and mood buttons. Open `/designer/character/talk-demo.html` |

## talk.js

```js
import { mountTalk } from './character/talk.js';
const talk = mountTalk({ stage, eyes, getHead: () => state.robot?.base });

talk.say('Hi! I am Gyropup!', { mood: 'happy' });   // bubble + eye mood + voice
await talk.ask('Can you dance?');                    // thinking bubble, then the reply, spoken; returns the text
const heard = await talk.listen();                   // transcript or null (calling again stops recording)
talk.react('hit');                                   // canned, varied, rate-limited line
talk.setMuted(true);
talk.dock.collapse(true);                            // also .toggle(), .isCollapsed(), .hint(text)
```

`mountTalk({ stage, getHead, eyes, root, chips, brain, dock })`

- `stage`: the kit stage (`camera`, `renderer.domElement`, `onFrame(cb)`).
- `getHead()`: a `THREE.Object3D` at the head. The bubble sits over the top of its bounding box, projected every
  frame; it moves beside the head when there is no room above, and stays clear of `#topbar`, the right-side `#panel`
  and the dock.
- `eyes`: anything with `set(name)`. Moods: neutral, happy, curious, sleepy, sad, grumpy, surprised, focused,
  thinking. A spoken line sets its mood and returns to neutral when the bubble fades.
- `chips`: three suggestion strings (default: "Hi Gyropup!", "Do a trick!", "How do you balance?").
- `brain`: `{ base, model, key }` to force an OpenAI-compatible endpoint.
- `dock: false` mounts no dock (bubble, voice and brain only).

Returns `{ say, ask, listen, react, setMuted, dock, services, detect, stop }`.

`react(event)` events: `hit`, `down`, `miss`, `fire`, `fall`, `reload`, `empty`, `low_battery`, `hello`. Each has its
own cooldown, there is a 3.5 s global gap, a line never interrupts a visible bubble or an answer, and `fire`/`miss`
only speak some of the time. `fall`, `empty`, `low_battery` and `hello` skip the global gap.

The dock sits at the bottom of the stage column, stopping short of the right-side panel (it reads `--panel-w` from
`kit/hud.css`); below 820 px it sits above the bottom panel. The TALK tab collapses it, and the state is remembered.

## Services and fallbacks

Each service is probed once, on first use (the first `say`/`ask`/`listen`, or when the pointer first enters the
dock), so an idle page does not log refused connections. Nothing needs a key or the internet unless you configure it.

| | Used when reachable | Fallback |
|---|---|---|
| Voice | Gyropup's Piper sidecar ([below](#gyropups-voice-toolstts_serverpy)), `GET http://<page host>:8081/tts?text=…` (WAV), played as `/health`'s `rate` says (1: the sidecar shapes the voice). Moxie's Piper server also works; it says no rate, so it is played 14% faster and higher | the browser's `speechSynthesis`, a little higher, natural English voices first |
| Ears | Moxie's Whisper STT, `POST http://<page host>:8082/stt` (webm audio; Deepgram-shaped JSON back), silence auto-stop | Chrome's Web Speech API (sends audio to Google; needs internet). Neither: a clear message, type instead |
| Brain | an OpenAI-compatible `POST <base>/chat/completions`: first `localStorage gyropup.llmBase`, else, on local pages only, Ollama at `http://127.0.0.1:11434` (first chat model from `/api/tags`, preferring llama3.2, qwen2.5, gemma, phi, mistral) | a scripted brain: keyword replies (hello, name, dance, shoot/balls, jump, battery, balance, joke, trick, ...) |

The brain uses a Gyropup persona prompt: a playful, kid-safe robot pup on the Tritium team that balances on two
wheels and plays foam-ball target games, 1 to 2 short sentences, a mood tag that drives the eyes. A question about
aiming at faces, people or pets gets a safety line without calling the model, and a model reply that suggests it
is replaced by one.

The Piper and Whisper sidecars are only probed when the page is served from localhost or a LAN address (as in Moxie).
Browsers only allow sound after the first click or key press on the page, so lines before that are silent (the
bubble still shows).

Overrides, in the browser console (then reload):

```js
localStorage['gyropup.ttsBase']  = 'http://192.0.2.20:8081';     // Piper elsewhere
localStorage['gyropup.sttBase']  = 'http://192.0.2.20:8082';     // Whisper elsewhere
localStorage['gyropup.llmBase']  = 'http://127.0.0.1:11434/v1';  // any OpenAI-compatible base URL
localStorage['gyropup.llmModel'] = 'llama3.2:3b';
localStorage['gyropup.llmKey']   = '...';                        // only for an endpoint that needs one; stays in this browser
localStorage['gyropup.probe']    = 'off';                        // never probe: browser voice + scripted brain
```

Moxie's own brain (`MOXIE_LLM_BASE_URL` in the Moxie repo's `mqtt/.env`) is called server-side with a key, so it is
not used from the browser. Point `gyropup.llmBase` at it only if you accept the key living in localStorage.

## Gyropup's voice: tools/tts_server.py

A small Piper sidecar in this repo: the Python standard library plus `piper-tts` (which brings numpy and
onnxruntime). It speaks the protocol `talk.js` probes for, `GET /health` (JSON: `ok`, `voice`, `label`, `rate`, ...)
and `GET /tts?text=…` (a 16-bit mono WAV), answers CORS for pages served from this machine or the LAN, and keeps
every line it has said in memory and in `~/.cache/gyropup-tts/`, so a repeated line comes back at once.

```sh
# start it in the background from the repo root (it keeps running when the terminal closes)
mkdir -p ~/.cache/gyropup-tts
nohup python3 tools/tts_server.py > ~/.cache/gyropup-tts/server.log 2>&1 &
curl -s http://127.0.0.1:8081/health      # {"ok": true, "voice": "en_US-hfc_female-medium", "label": "hfc_female", ...}

# stop it
pkill -f tools/tts_server.py

# hear a line or a setting without the server
python3 tools/tts_server.py --say "Hi! I am Gyropup!" --out /tmp/hi.wav --pitch 3
```

If `python3` cannot import Piper (on this machine it is installed for python3.10 only), the server re-runs itself
under a python that can. Voices live in `~/.local/share/piper-voices`; fetch another (two files from
[rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices)) with
`python3.10 -m piper.download_voices <name> --download-dir ~/.local/share/piper-voices`. `GET /voices` lists them.

The pup character is made in the sidecar, so every client hears the same voice and `talk.js` plays it as it is: Piper
first speaks slower by the pitch factor, then a band-limited resample lifts the pitch and the formants (a smaller,
younger voice, not just a higher one) and brings the pace back. Names espeak says wrongly are respelled before Piper
sees them: Gyropup is "JYE-roh-pup" and Tritium "TRIT-ee-um" (`RESPELL` in the script).

| Flag | Environment | Default | |
|---|---|---|---|
| `--voice` | `GYROPUP_TTS_VOICE` | `en_US-hfc_female-medium` | a voice name in the voice folders, or a `.onnx` path |
| `--speaker` | `GYROPUP_TTS_SPEAKER` | | speaker name or id, for multi-speaker voices |
| `--pitch` | `GYROPUP_TTS_PITCH` | `2` | semitones up (negative: down); 0 is the voice as recorded |
| `--speed` | `GYROPUP_TTS_SPEED` | `0.95` | pace; 1 is Piper's own |
| `--volume` | `GYROPUP_TTS_VOLUME` | `0.9` | peak level, 0 to 1 |
| `--pause` | `GYROPUP_TTS_PAUSE` | `0.12` | seconds between sentences |
| `--noise-scale`, `--noise-w` | `GYROPUP_TTS_NOISE_SCALE`, `GYROPUP_TTS_NOISE_W` | the voice's | Piper's expressiveness and rhythm variation |
| `--voices-dir` | `GYROPUP_TTS_VOICES` | `~/.local/share/piper-voices` | voice folders, `:`-separated |
| `--cache-dir` | `GYROPUP_TTS_CACHE` | `~/.cache/gyropup-tts` | rendered lines (`off`: memory only); new settings start a new subfolder |
| `--host`, `--port` | `GYROPUP_TTS_HOST`, `GYROPUP_TTS_PORT` | `127.0.0.1`, `8081` | `--host 0.0.0.0` lets other machines' pages use it |
| `--origins` | `GYROPUP_TTS_ORIGINS` | `local` | CORS: pages from this machine or the LAN; `*`; or a comma list of origins |
| `--python` | `GYROPUP_TTS_PYTHON` | found | a python that can import Piper |

### Why en_US-hfc_female-medium

All 17 single-speaker medium-quality English voices installed here, and en_US-sam-medium, said the same eight
Gyropup lines (a greeting, battle banter, hit and miss reactions, a fall, a joke, a question, a reload); the 1,047
speakers of the multi-speaker voices (LibriTTS-R, VCTK, CMU Arctic, ARU, SEMAINE) were screened on two of them, and
the best five said all eight. Each was measured for pitch, intonation (the spread of its pitch in semitones: flat
voices sound robotic), pace and cleanliness (YIN aperiodicity, creak, and the noise between words), and weighed with
what the voice is known for. As Piper makes them, before the sidecar's lift:

| Voice | Pitch | Intonation | Syllables/s | Between words | Character | Data licence |
|---|---|---|---|---|---|---|
| **en_US-hfc_female-medium** | 240 Hz | 4.0 st | 4.3 | -40 dB | the liveliest; bright and warm; a studio corpus (Hi-Fi-CAPTAIN) | CC BY-NC-SA 4.0 |
| en_US-libritts_r-medium, speaker 8329 | 267 Hz | 3.4 st | 4.3 | -28 dB | naturally bright, questions rise; a little room noise; needs no lift (`--pitch 0`) | CC BY 4.0 |
| en_US-lessac-medium | 216 Hz | 3.7 st | 4.7 | -71 dB | Piper's reference voice, very clear; an audiobook narrator's creak at phrase ends | Blizzard 2013 (research) |
| en_GB-cori-medium | 210 Hz | 2.8 st | 4.2 | -45 dB | clean, and its questions rise; British | public domain |
| en_US-ljspeech-medium | 220 Hz | 3.4 st | 4.0 | -30 dB | lively and unhurried; noisier between words | public domain |
| en_US-amy-medium (Moxie's) | 207 Hz | 1.8 st | 3.7 | -50 dB | clear but flat | Mycroft mimic3 |

With the default lift hfc_female speaks at 273 Hz and 4.4 syllables a second, its intonation unchanged. Passed over:
the male voices (a lifted man's voice turns into a cartoon), en_US-sam-medium (gender-neutral and Apache-2.0, but the
flattest of all, 1.5 st), and the low-quality 16 kHz voices. hfc_female's data is non-commercial: fine for this
private robot, but a commercial Gyropup would switch (`GYROPUP_TTS_VOICE=en_US-libritts_r-medium
GYROPUP_TTS_SPEAKER=8329 GYROPUP_TTS_PITCH=0`, or cori, or ljspeech).

## Ears and brain (Moxie's Whisper, Ollama)

Whisper runs from a checkout of the Moxie simulator
([mvalancy/moxie-robot-saver](https://github.com/mvalancy/moxie-robot-saver)):

```sh
# one-time: a venv with faster-whisper (the server looks for /tmp/piper-venv by default)
python3 -m venv /tmp/piper-venv && /tmp/piper-venv/bin/pip install piper-tts faster-whisper

# ears (Whisper, base.en; downloads the model on the first request) on :8082
/tmp/piper-venv/bin/python sim/stt/server.py 8082 # POST /stt, GET /health;  MOXIE_STT_MODEL=tiny.en for speed
```

Or with Docker: `docker compose -f sim/docker-compose.yml --profile voice up stt`. Moxie's own Piper server
(`sim/tts/server.py 8081`) still works as the voice, unshaped and played 14% faster.

Brain, with Ollama:

```sh
ollama serve &              # or: sudo systemctl start ollama
ollama pull llama3.2:3b     # small, quick, good enough for 1–2 sentence replies
```

Ollama accepts browser requests from `http://127.0.0.1:*` and `http://localhost:*` by default. For a page served
from another host, start it with `OLLAMA_ORIGINS=http://<that host>:8642`.

After starting a service, reload the page (or click "Detect services" in the demo). The dock's status line shows
what is in use: `VOICE piper (<voice>)|browser · EARS whisper|browser|none · BRAIN <model>|scripted`; hover it for
the URLs.

## Credits

`talk.js` and `talk.css` are adapted from the Moxie simulator in
[mvalancy/moxie-robot-saver](https://github.com/mvalancy/moxie-robot-saver), MIT, © 2026 moxie-robot-parent-app
contributors: `sim/web/moxie/bubble.js` (the projected bubble and typewriter), `sim/web/voice/local.js` (the
Piper-then-browser voice chain), `sim/web/mic.js` (recording, silence auto-stop, the Whisper sidecar),
`sim/web/css/dock.css` and `css/hud.css` (the dock and bubble look), and `mqtt/moxie_sdk/chat.py` (the
OpenAI-compatible brain call). The Whisper server is Moxie's `sim/stt/server.py`; `tools/tts_server.py` keeps the
protocol of Moxie's `sim/tts/server.py`. `eyes.js` adapts `sim/web/moxie/face.js` from the same project.

Public pages (including gyropup.com) never automatically discover a visitor’s local AI or voice servers. Browser voice and the scripted brain are the default. Explicit `gyropup.llmBase`, `gyropup.ttsBase`, `gyropup.sttBase`, or `GYROPUP_BRAIN` configuration remains opt-in; the endpoint must meet the browser’s HTTPS, CORS and local-network permission requirements.
