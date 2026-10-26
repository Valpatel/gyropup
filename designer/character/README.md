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

`react(event)` events: `hit`, `down`, `miss`, `fire`, `fall`, `reload`, `low_battery`, `hello`. Each has its own
cooldown, there is a 3.5 s global gap, a line never interrupts a visible bubble or an answer, and `fire`/`miss` only
speak some of the time. `fall`, `low_battery` and `hello` skip the global gap.

The dock sits at the bottom of the stage column, stopping short of the right-side panel (it reads `--panel-w` from
`kit/hud.css`); below 820 px it sits above the bottom panel. The TALK tab collapses it, and the state is remembered.

## Services and fallbacks

Each service is probed once, on first use (the first `say`/`ask`/`listen`, or when the pointer first enters the
dock), so an idle page does not log refused connections. Nothing needs a key or the internet unless you configure it.

| | Used when reachable | Fallback |
|---|---|---|
| Voice | Moxie's Piper TTS, `GET http://<page host>:8081/tts?text=…` (WAV), played 14% faster and higher | the browser's `speechSynthesis`, high pitch, an English voice |
| Ears | Moxie's Whisper STT, `POST http://<page host>:8082/stt` (webm audio; Deepgram-shaped JSON back), silence auto-stop | Chrome's Web Speech API (sends audio to Google; needs internet). Neither: a clear message, type instead |
| Brain | an OpenAI-compatible `POST <base>/chat/completions`: first `localStorage gyropup.llmBase`, else Ollama at `http://127.0.0.1:11434` (first chat model from `/api/tags`, preferring llama3.2, qwen2.5, gemma, phi, mistral) | a scripted brain: keyword replies (hello, name, dance, shoot/darts, jump, battery, balance, joke, trick, ...) |

The brain uses a Gyropup persona prompt: a playful, kid-safe robot pup on the Tritium team that balances on two
wheels and plays foam-dart target games, 1 to 2 short sentences, a mood tag that drives the eyes. A question about
aiming at faces, people or pets gets a safety line without calling the model, and a model reply that suggests it
is replaced by one.

The Piper and Whisper sidecars are only probed when the page is served from localhost or a LAN address (as in Moxie).
Browsers only allow sound after the first click or key press on the page, so lines before that are silent (the
bubble still shows).

Overrides, in the browser console (then reload):

```js
localStorage['gyropup.ttsBase']  = 'http://192.168.1.20:8081';   // Piper elsewhere
localStorage['gyropup.sttBase']  = 'http://192.168.1.20:8082';   // Whisper elsewhere
localStorage['gyropup.llmBase']  = 'http://127.0.0.1:11434/v1';  // any OpenAI-compatible base URL
localStorage['gyropup.llmModel'] = 'llama3.2:3b';
localStorage['gyropup.llmKey']   = '...';                        // only for an endpoint that needs one; stays in this browser
localStorage['gyropup.probe']    = 'off';                        // never probe: browser voice + scripted brain
```

Moxie's own brain (`MOXIE_LLM_BASE_URL` in the Moxie repo's `mqtt/.env`) is called server-side with a key, so it is
not used from the browser. Point `gyropup.llmBase` at it only if you accept the key living in localStorage.

## Running the local services (from the Moxie repo)

All commands run from `/home/scubasonar/Code/moxie-robot/repo`. The voices are already in `sim/tts/voices/`
(`en_US-amy-medium`, `en_US-lessac-medium`); if not, `python3 sim/ci/fetch_piper_voices.py`.

```sh
# one-time: a venv with Piper and faster-whisper (the servers look for /tmp/piper-venv by default)
python3 -m venv /tmp/piper-venv && /tmp/piper-venv/bin/pip install piper-tts faster-whisper

# voice (Piper) on :8081
python3 sim/tts/server.py 8081                    # GET /tts?text=..., GET /health

# ears (Whisper, base.en; downloads the model on the first request) on :8082
/tmp/piper-venv/bin/python sim/stt/server.py 8082 # POST /stt, GET /health;  MOXIE_STT_MODEL=tiny.en for speed
```

Or with Docker: `docker compose -f sim/docker-compose.yml --profile voice up tts stt`.

Brain, with Ollama:

```sh
ollama serve &              # or: sudo systemctl start ollama
ollama pull llama3.2:3b     # small, quick, good enough for 1–2 sentence replies
```

Ollama accepts browser requests from `http://127.0.0.1:*` and `http://localhost:*` by default. For a page served
from another host, start it with `OLLAMA_ORIGINS=http://<that host>:8642`.

After starting a service, reload the page (or click "Detect services" in the demo). The dock's status line shows
what is in use: `VOICE piper|browser · EARS whisper|browser|none · BRAIN <model>|scripted`; hover it for the URLs.

## Credits

`talk.js` and `talk.css` are adapted from the Moxie simulator in
[mvalancy/moxie-robot-saver](https://github.com/mvalancy/moxie-robot-saver), MIT, © 2026 moxie-robot-parent-app
contributors: `sim/web/moxie/bubble.js` (the projected bubble and typewriter), `sim/web/voice/local.js` (the
Piper-then-browser voice chain), `sim/web/mic.js` (recording, silence auto-stop, the Whisper sidecar),
`sim/web/css/dock.css` and `css/hud.css` (the dock and bubble look), and `mqtt/moxie_sdk/chat.py` (the
OpenAI-compatible brain call). The Piper and Whisper servers are Moxie's `sim/tts/server.py` and `sim/stt/server.py`.
`eyes.js` adapts `sim/web/moxie/face.js` from the same project.
