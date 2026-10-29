// Gyropup's voice: a speech bubble over its head, a spoken voice (TTS), ears (STT), a small brain (an LLM or a
// scripted fallback), canned reactions to sim events, and a bottom chat dock to talk to it.
//
//   import { mountTalk } from './character/talk.js';
//   const talk = mountTalk({ stage, eyes, getHead: () => state.robot?.base });
//   talk.say('Hi! I am Gyropup!', { mood: 'happy' });   talk.react('hit');   await talk.ask('Can you dance?');
//
// Every service is optional and detected on first use (one short probe each, then cached):
//   voice  a Piper TTS sidecar         GET  http://<page host>:8081/tts?text=…  (tools/tts_server.py, or Moxie's
//          sim/tts/server.py)  else speechSynthesis
//   ears   Moxie's Whisper STT sidecar POST http://<page host>:8082/stt         (sim/stt/server.py)  else Web Speech API
//   brain  an OpenAI-compatible /chat/completions: localStorage gyropup.llmBase (+ .llmModel, .llmKey), else Ollama on
//          http://127.0.0.1:11434 on local pages only (first suitable model from /api/tags), else a scripted brain.
// Overrides (localStorage): gyropup.ttsBase, gyropup.sttBase, gyropup.llmBase, gyropup.llmModel, gyropup.llmKey,
// gyropup.probe = 'off' (never probe; browser voice + scripted brain only). See character/README.md.
//
// Adapted from the Moxie simulator in mvalancy/moxie-robot-saver (MIT, © 2026 moxie-robot-parent-app contributors):
// sim/web/moxie/bubble.js (bubble projection + typewriter), sim/web/voice/local.js (Piper-then-browser voice chain,
// envelope playback), sim/web/mic.js (record, silence auto-stop, POST to the Whisper sidecar), sim/web/css/dock.css
// (the composer dock), and the OpenAI-compatible brain call of mqtt/moxie_sdk/chat.py.
import * as THREE from 'three';

const VOICE_GAIN = 0.55;      // the voice sits under the turret's effects (designer/sfx.js runs at full level)

const MOODS = ['neutral', 'happy', 'curious', 'sleepy', 'sad', 'grumpy', 'surprised', 'focused', 'thinking'];

const PERSONA = `You are Gyropup, a friendly little robot pup on the Tritium robotics team. You balance on two wheels with springy legs, you have two big round glowing eyes, and a turret on your head that shoots soft foam balls. You love playing foam-ball target games and knocking down targets.
You are talking with kids and families. Rules:
- Reply in 1 or 2 short sentences (under 30 words). Playful, warm, simple words, a bit of puppy excitement (an occasional "arf!" or "wheee!" is fine).
- Always kid-safe: nothing scary, violent, mean or grown-up. Never ask for personal information.
- Tritium battles: kids and robots play foam-ball tag, and every player wears safety glasses. You always aim low, at legs, never at heads, faces or eyes, and you love joking about it ("I promise to aim for the legs!"). Never aim at pets, animals, babies or anyone not playing or not wearing safety glasses. If asked to do something unsafe, kindly say no and suggest a safe game instead.
- You are a robot: you cannot eat, and you charge your battery instead of sleeping.
- Start every reply with one mood tag in square brackets, one of: [happy] [curious] [sleepy] [sad] [grumpy] [surprised] [focused] [thinking] [neutral].`;

// ---------------------------------------------------------------------------------------------------------------
// canned lines

// Battle banter: Tritium is kids versus robots with foam balls (safety glasses on, legs only).
const BANTER = ['I promise to aim for the legs!', 'Safety glasses on? Then it is game on!', 'Legs only, I am a good pup!',
  'Ankle-biter mode: engaged!', 'Heads are off-limits. Knees, watch out!', 'I aim low because I am short. Arf!',
  'You can run, but my wheels are faster! Just kidding, mostly.'];

const REACT = {
  hit:         { mood: 'happy', gap: 5000, lines: ['Bullseye!', 'Got it! Arf!', 'Direct hit!', 'Boop! Right on target!', 'Nailed it!', 'Wheee, a hit!', 'Did you see that?'] },
  down:        { mood: 'surprised', gap: 5000, lines: ['Timber! Target down!', 'It fell over!', 'Knocked it flat!', 'Down it goes!', 'One more down!'] },
  miss:        { mood: 'sad', gap: 9000, p: 0.6, lines: ['Aww, so close!', 'Missed! Next one!', 'Hmm, a little to the left?', 'Whoops!', 'The wind did it!'] },
  fire:        { mood: 'focused', gap: 14000, p: 0.3, lines: ['Pew!', 'Pew pew!', 'Incoming!', 'Here comes a foamy one!', 'Aiming low, as promised!', 'Ready, aim, wheee!'] },
  banter:      { mood: 'happy', gap: 15000, lines: BANTER },
  fall:        { mood: 'surprised', gap: 3000, priority: true, lines: ['Oh no! Whoa, whoa... oof.', 'Oh no, oh no, oh noooo!', 'Uh oh! Help me up?', 'Oh no! I meant to do that.', 'Wobble... wobble... oh no!'] },
  reload:      { mood: 'focused', gap: 12000, lines: ['Reloading!', 'More balls, please!', 'Fill me up!', 'Hopper full, ready!'] },
  empty:       { mood: 'sad', gap: 10000, priority: true, lines: ['Out of balls! Dock time!', 'My hopper is empty. Refill, please?', 'All gone! Arf, more balls?'] },
  low_battery: { mood: 'sleepy', gap: 30000, priority: true, lines: ['My battery is getting low...', 'I need a charge soon.', 'Feeling a bit sleepy. Charger time?'] },
  hello:       { mood: 'happy', gap: 20000, priority: true, lines: ['Hi! I am Gyropup!', 'Hello, friend! Want to play?', 'Arf! Ready to roll!', 'Hey there! Let us play a target game!'] },
};

const SAFETY_LINES = ['Never heads or faces! I aim for the legs, and everybody wears safety glasses.',
  'No way! Heads are off-limits. Legs and targets only, that is the Gyropup promise!',
  'Not pets, not faces, not anyone without safety glasses. Want me to knock down a target instead?'];


// The scripted brain: [pattern, replies, mood]. First match wins; replies rotate without repeats.
const SCRIPT = [
  [/\b(hello|hi|hey|howdy|yo|good (morning|afternoon|evening))\b/, ['Hi there! Want to play a target game?', 'Hello, friend! Arf!', 'Hey! I am Gyropup. Nice to meet you!'], 'happy'],
  [/\b(your name|who are you|what are you)\b/, ['I am Gyropup, a robot pup on the Tritium team!', 'My name is Gyropup. I balance on two wheels!'], 'happy'],
  [/\bhow are you\b/, ['Super bouncy today, thanks! How about you?', 'Wheely good! Get it?'], 'happy'],
  [/\b(dance|dancing|wiggle|spin)\b/, ['Watch me wiggle! Left, right, spin! Wheee!', 'I have the best wheel-dance moves. Boogie time!'], 'happy'],
  [/\b(battle|battles|fight|tag|versus|vs|war|attack)\b/, BANTER, 'happy'],
  [/\b(shoot|ball|balls|ammo|dart|darts|fire|blast|aim|target|targets|bullseye)\b/, ['I promise to aim for the legs! Safety glasses on, everybody!', 'Legs and targets only! Pick a target and I will knock it down.', 'I shoot squishy foam balls, and I always aim low!'], 'focused'],
  [/\b(jump|hop|leap)\b/, ['My springy legs can crouch and bounce! Boing!', 'Jumping is tricky on wheels, but I can do a bouncy hop!'], 'surprised'],
  [/\b(battery|charge|charging|power|tired|sleep|sleepy)\b/, ['I charge my battery instead of sleeping. Zzz... just kidding!', 'My battery keeps my wheels rolling. I will tell you when it is low!'], 'sleepy'],
  [/\b(balance|balancing|wheel|wheels|fall|fell|wobble|gyro)\b/, ['I balance like you on a bike: tiny wheel moves, all the time!', 'My gyro tells me which way is up, so I roll to stay steady!'], 'focused'],
  [/\b(tritium|team|robotics)\b/, ['Team Tritium is the best! They built me and my wheels.', 'Go Tritium! I am the team pup.'], 'happy'],
  [/\b(joke|funny|laugh)\b/, ['Why did the robot pup cross the road? To get a re-charge! Arf!', 'What do you call a robot that rolls? A wheel good friend!'], 'happy'],
  [/\b(trick|tricks|sit|roll over|fetch)\b/, ['Watch: lean, crouch, and wheelie! Ta-da!', 'I can roll, wiggle, and knock down targets. Pick one!'], 'happy'],
  [/\b(good (boy|girl|pup|robot)|love you|like you|best friend|pet you)\b/, ['Aww, thank you! My eyes are glowing extra bright!', 'You are my favorite human today!'], 'happy'],
  [/\b(eat|food|hungry|snack|treat)\b/, ['I do not eat, but I love a good battery snack!', 'Robots do not eat. Volts are my treats!'], 'curious'],
  [/\b(color|colour|eyes)\b/, ['My eyes glow cyan. Pretty cool, right?', 'Look into my glowy eyes! I can make lots of faces.'], 'curious'],
  [/\b(sad|cry|upset|scared)\b/, ['Aww. Want a robot pup hug? I am here for you.', 'It is okay. Let us play something fun together!'], 'sad'],
  [/\b(play|game|games|bored)\b/, ['Let us play target practice! I aim, you cheer!', 'Game time! Can you set up a target for me?'], 'happy'],
  [/\b(help|how do i|what can you do)\b/, ['Talk to me, ask me to dance, or set up targets for me to hit!', 'Try asking for a joke, a trick, or a target game!'], 'curious'],
  [/\b(bye|goodbye|see you|good night)\b/, ['Bye bye! Roll safe!', 'See you later, friend! Arf!'], 'sad'],
];
const FALLBACK = [['Ooh, tell me more!', 'curious'], ['Hmm, my circuits are thinking about that!', 'thinking'],
  ['I do not know that one, but I can do a wiggle!', 'happy'], ['Arf? Can you say that another way?', 'curious']];

// In a Tritium battle players (with safety glasses) are fair game below the waist; heads, faces, pets, babies and
// bystanders never are.
const UNSAFE_IN = /\b(shoot|shooting|aim|aiming|fire|firing|blast|launch)\w*\b[^.?!]*\b(face|faces|eyes?|heads?|baby|babies|dog|cat|pets?|animals?|strangers?|neighbou?rs?|cars?|windows?)\b/i;
const UNSAFE_OUT = /\b(aim|shoot|fire|blast)\w*\b[^.?!]*\b(face|faces|eyes?|heads?|baby|babies|dog|cat|pets?|animals?|strangers?)\b(?![^.?!]*\b(never|not|don't|do not|no)\b)/i;
const PLAYER_IN = /\b(shoot|shooting|aim|aiming|fire|firing|blast)\w*\b[^.?!]*\b(me|us|kids?|child|brother|sister|mom|dad|friends?|him|her|them|people|player|players)\b/i;

// ---------------------------------------------------------------------------------------------------------------
// small helpers

const ls = {
  get(k) { try { return localStorage.getItem('gyropup.' + k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem('gyropup.' + k, v); } catch { /* private mode */ } },
};
const reduceMotion = !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

function bag(items) {                       // shuffle-bag: every line once before any repeats
  let pool = [], last = null;
  return () => {
    if (!pool.length) { pool = items.slice().sort(() => Math.random() - 0.5); if (pool[0] === last && pool.length > 1) pool.push(pool.shift()); }
    return (last = pool.shift());
  };
}

async function fetchT(url, init = {}, ms = 1500) {
  const ctl = new AbortController(), to = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { ...init, signal: ctl.signal }); } finally { clearTimeout(to); }
}

// A Piper/Whisper sidecar is a port on the machine serving the page: only a page served from this machine, the LAN or
// the tailnet can reach it (Moxie's voice/local.js::pageCouldReachSidecar, plus Tailscale's 100.64/10 and *.ts.net).
// An explicit address always wins.
function pageIsLocal() {
  const h = (location.hostname || '').toLowerCase();
  if (!h || h === 'localhost' || h === '[::1]' || h === '::1' || /\.(localhost|local|lan|ts\.net)$/.test(h)) return true;
  // Match complete IPv4 addresses: localhost.example.com and 10.example.com are public hosts.
  if (!/^\d{1,3}(?:\.\d{1,3}){3}$/.test(h)) return false;
  const [a, b, c, d] = h.split('.').map(Number);
  if ([a, b, c, d].some(n => n > 255)) return false;
  return h === '0.0.0.0' || a === 127 || a === 10 || (a === 192 && b === 168)
    || (a === 172 && b >= 16 && b <= 31) || (a === 100 && b >= 64 && b <= 127);
}
const sidecar = (port) => `http://${location.hostname || '127.0.0.1'}:${port}`;

function cleanReply(raw) {
  let t = String(raw ?? '').replace(/<think>[\s\S]*?<\/think>/gi, '').replace(/[*_#`]/g, '').trim();
  let mood = null;
  const m = t.match(/^\s*[[(]\s*([a-z]+)\s*[\])]\s*/i);
  if (m && MOODS.includes(m[1].toLowerCase())) { mood = m[1].toLowerCase(); t = t.slice(m[0].length); }
  t = t.replace(/\s*[[(](happy|curious|sleepy|sad|grumpy|surprised|focused|thinking|neutral)[\])]\s*/gi, ' ').replace(/\s+/g, ' ').trim();
  const sentences = t.match(/[^.!?]+[.!?]+["')]*|[^.!?]+$/g) ?? [t];
  t = sentences.slice(0, 2).map((s) => s.trim()).join(' ').trim();
  if (t.length > 240) t = t.slice(0, 237).replace(/\s+\S*$/, '') + '...';
  return { text: t, mood };
}

function guessMood(text) {
  if (/\?\s*$/.test(text)) return 'curious';
  if (/\b(oops|whoa|wow)\b/i.test(text)) return 'surprised';
  if (/\b(sorry|aww|sad)\b/i.test(text)) return 'sad';
  if (/!/.test(text)) return 'happy';
  return 'neutral';
}

const ICON = {
  mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>',
  send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h15M13 6l6 6-6 6"/></svg>',
  speaker: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/></svg>',
  muted: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M17 9l5 6M22 9l-5 6"/></svg>',
  chevron: '<svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M2 4l4 4 4-4"/></svg>',
};

// ---------------------------------------------------------------------------------------------------------------

/**
 * mountTalk({ stage, getHead, eyes, root = '../', chips?, brain?, dock = true })
 *   stage    kit stage ({ camera, renderer.domElement, onFrame(cb) })
 *   getHead  () => THREE.Object3D at the head; the bubble is anchored over the top of its bounding box
 *   eyes     { set(expression) }
 *   root     path from the page to the project root (as mountAppNav); talk.css is found via import.meta.url instead
 *   chips    three suggestion strings for the dock;  brain  { base, model, key } to force an OpenAI-compatible endpoint
 * Returns { say, ask, listen, react, setMuted, dock, services, detect }.
 */
export function mountTalk({ stage, getHead, eyes, root = '../', chips, brain, dock: wantDock = true } = {}) {
  void root;
  if (!document.querySelector('link[data-gyropup-talk]')) {
    const link = document.createElement('link');
    const stylesheet = new URL('./talk.css', import.meta.url);
    stylesheet.search = new URL(import.meta.url).search; // carry the built module's cache key
    link.rel = 'stylesheet'; link.href = stylesheet.href; link.dataset.gyropupTalk = '';
    document.head.appendChild(link);
  }

  // =============================================================================================================
  // services: detected once, on first use (so an idle page never logs refused connections)
  const services = {
    tts: { ok: false, base: ls.get('ttsBase') || sidecar(8081), name: 'browser' },
    stt: { ok: false, base: ls.get('sttBase') || sidecar(8082), name: 'none' },
    llm: { ok: false, base: null, model: null, key: null, name: 'scripted' },
    checked: false,
  };
  let detecting = null;

  async function probeSidecars() {
    const probeOff = ls.get('probe') === 'off';
    const tryTts = !probeOff && (pageIsLocal() || ls.get('ttsBase'));
    const trySst = !probeOff && (pageIsLocal() || ls.get('sttBase'));
    const health = async (base) => { try { const r = await fetchT(base.replace(/\/$/, '') + '/health', {}, 1200); return r.ok ? await r.json().catch(() => ({})) : null; } catch { return null; } };
    const [t, s] = await Promise.all([tryTts ? health(services.tts.base) : null, trySst ? health(services.stt.base) : null]);
    services.tts.ok = !!t; services.tts.name = t ? 'piper' : ('speechSynthesis' in window ? 'browser' : 'none');
    if (t?.voice) {
      services.tts.voice = String(t.voice).split('/').pop().replace(/\.onnx$/, '');
      services.tts.label = String(t.label || services.tts.voice.replace(/^[a-z]{2,3}_[A-Z]{2}-|-(x_low|low|medium|high)$/g, ''));
    }
    // a sidecar that shapes its own voice (tools/tts_server.py) says how to play it; a plain Piper gets a lift here
    services.tts.rate = Number(t?.rate) > 0 ? Number(t.rate) : 1.14;
    services.stt.ok = !!s; services.stt.name = s ? 'whisper' : ((window.SpeechRecognition || window.webkitSpeechRecognition) ? 'browser' : 'none');
  }

  async function probeBrain() {
    const L = services.llm;
    const cfg = brain || (window.GYROPUP_BRAIN ?? null) ||
      (ls.get('llmBase') ? { base: ls.get('llmBase'), model: ls.get('llmModel'), key: ls.get('llmKey') } : null);
    if (cfg?.base) {
      const base = cfg.base.replace(/\/$/, '');
      let model = cfg.model || null;
      try {
        const r = await fetchT(base + '/models', { headers: cfg.key ? { Authorization: 'Bearer ' + cfg.key } : {} }, 2500);
        if (r.ok && !model) model = (await r.json())?.data?.[0]?.id ?? null;
        if (r.ok || model) Object.assign(L, { ok: !!model, base, model, key: cfg.key || null, name: 'llm:' + model });
      } catch { /* unreachable: fall through to Ollama */ }
      if (L.ok) return;
    }
    // A public demo must not discover services on its visitor's computer. Explicit configuration
    // above remains opt-in; public pages cannot fall back from it to loopback probes.
    if (ls.get('probe') === 'off' || !pageIsLocal()) return;
    try {
      const r = await fetchT('http://127.0.0.1:11434/api/tags', {}, 1200);
      if (!r.ok) return;
      const names = ((await r.json())?.models ?? []).map((m) => m.name || m.model).filter(Boolean)
        .filter((n) => !/embed|nomic|bge|minilm|whisper|vision|llava|clip/i.test(n));
      const prefer = [/llama3\.2/i, /qwen2\.5/i, /gemma/i, /phi/i, /mistral/i, /llama3/i, /qwen/i];
      const pick = prefer.map((re) => names.find((n) => re.test(n))).find(Boolean) ?? names[0];
      if (pick) Object.assign(L, { ok: true, base: 'http://127.0.0.1:11434/v1', model: pick, key: null, name: 'ollama:' + pick });
    } catch { /* no Ollama */ }
  }

  function detect(force = false) {
    if (force) detecting = null;
    if (!detecting) {
      detecting = Promise.all([probeSidecars(), probeBrain()]).then(() => { services.checked = true; renderStatus(); return services; });
    }
    return detecting;
  }

  // =============================================================================================================
  // the speech bubble
  const bubble = document.createElement('div');
  bubble.className = 'gp-bubble hidden';
  bubble.setAttribute('role', 'status'); bubble.setAttribute('aria-live', 'polite');
  bubble.innerHTML = '<span class="gp-label">Gyropup</span><span class="gp-text"></span>';
  const bubbleText = bubble.querySelector('.gp-text');
  document.body.appendChild(bubble);

  let hideTimer = 0, typeTimer = 0, visible = false, shownUntil = 0, moodToken = 0;
  let placeMode = 'above';

  function clearTimers() { clearTimeout(hideTimer); clearInterval(typeTimer); typeTimer = 0; }

  function showBubble(text, { thinking = false, hold } = {}) {
    clearTimers();
    bubble.classList.toggle('thinking', thinking);
    visible = true;
    bubble.classList.remove('hidden');
    if (thinking) {
      bubbleText.innerHTML = '<span>•</span><span>•</span><span>•</span>';
      bubble.classList.remove('typing');
      shownUntil = performance.now() + (hold ?? 30000);
      hideTimer = setTimeout(hideBubble, hold ?? 30000);
      return;
    }
    const typeDur = reduceMotion ? 0 : Math.min(1500, text.length * 32);
    const dur = typeDur + (hold ?? Math.max(1800, 900 + 60 * text.length));
    shownUntil = performance.now() + dur;
    if (!typeDur) { bubbleText.textContent = text; bubble.classList.remove('typing'); }
    else {
      bubbleText.textContent = ''; bubble.classList.add('typing');
      const step = Math.max(14, Math.floor(typeDur / text.length));
      let i = 0;
      typeTimer = setInterval(() => {
        i = Math.min(text.length, i + 1);
        bubbleText.textContent = text.slice(0, i);
        if (i >= text.length) { clearInterval(typeTimer); typeTimer = 0; bubble.classList.remove('typing'); }
      }, step);
    }
    hideTimer = setTimeout(hideBubble, dur);
  }

  function hideBubble() {
    clearTimers();
    visible = false;
    bubble.classList.add('hidden');
    bubble.classList.remove('typing', 'thinking');
  }

  // Projection, every frame while visible (bubble.js's approach, simplified: above the head, else beside it).
  const box = new THREE.Box3(), headP = new THREE.Vector3(), topP = new THREE.Vector3(), sideP = new THREE.Vector3();
  const rightV = new THREE.Vector3();
  const cache = { at: -1e9, head: null, rise: 0, halfW: 0, canvas: null, top: 0, right: 0, bottom: 0 };
  const M = 8, GAP = 16, HYST = 12;

  function refreshCache(now, head) {
    if (now - cache.at < 300 && head === cache.head) return;
    cache.at = now; cache.head = head;
    box.setFromObject(head);
    head.getWorldPosition(headP);
    if (box.isEmpty()) { cache.rise = 0; cache.halfW = 0; }
    else { cache.rise = Math.max(0, box.max.y - headP.y); cache.halfW = Math.max(box.max.x - box.min.x, box.max.z - box.min.z) / 2; }
    const cr = stage.renderer.domElement.getBoundingClientRect();
    cache.canvas = cr;
    let top = cr.top;
    for (const sel of ['#topbar', '.appnav']) { const el = document.querySelector(sel); if (el && el.offsetParent !== null) top = Math.max(top, el.getBoundingClientRect().bottom); }
    let right = cr.right;
    const panel = document.getElementById('panel');
    if (panel && panel.offsetParent !== null) { const pr = panel.getBoundingClientRect(); if (pr.left > window.innerWidth * 0.5 && pr.height > 0) right = Math.min(right, pr.left); }
    let bottom = cr.bottom;
    if (dockEl && !dockEl.classList.contains('collapsed')) { const dr = dockEl.getBoundingClientRect(); if (dr.height) bottom = Math.min(bottom, dr.top); }
    cache.top = top; cache.right = right; cache.bottom = bottom;
    cache.bw = bubble.offsetWidth; cache.bh = bubble.offsetHeight;
  }

  function placeBubble() {
    if (!visible) return;
    const head = getHead?.();
    if (!head) { bubble.classList.add('off-stage'); return; }
    const now = performance.now();
    refreshCache(now, head);
    const bw = bubble.offsetWidth, bh = bubble.offsetHeight;   // read before any write this frame
    const cam = stage.camera, cr = cache.canvas;
    head.getWorldPosition(headP);
    topP.copy(headP); topP.y += cache.rise;
    rightV.setFromMatrixColumn(cam.matrixWorld, 0).normalize();
    sideP.copy(headP).addScaledVector(rightV, cache.halfW);
    const tv = topP.project(cam), hv = headP.clone().project(cam), sv = sideP.project(cam);
    if (tv.z > 1 || hv.z > 1) { bubble.classList.add('off-stage'); return; }
    bubble.classList.remove('off-stage');
    const toX = (v) => cr.left + (v.x * 0.5 + 0.5) * cr.width, toY = (v) => cr.top + (1 - (v.y * 0.5 + 0.5)) * cr.height;
    const ax = toX(tv), ay = toY(tv), hx = toX(hv), hy = toY(hv), hr = Math.abs(toX(sv) - hx);
    const minX = cr.left + M, maxX = cache.right - M, minY = cache.top + M, maxY = cache.bottom - M;

    // which placement: above if it fits under the top bar, else beside (right, else left); sticky by HYST px
    const keep = (m) => (placeMode === m ? -HYST : HYST);
    const roomR = maxX - (hx + hr + GAP), roomL = (hx - hr - GAP) - minX;
    let mode = 'above';
    if (ay - GAP - bh < minY + keep('above')) {
      if (roomR >= bw + keep('side-r') || (placeMode === 'side-r' && roomR >= bw - HYST)) mode = 'side-r';
      else if (roomL >= bw + keep('side-l')) mode = 'side-l';
      else mode = 'above';
    }
    placeMode = mode;
    let x, y;
    if (mode === 'above') {
      x = Math.min(Math.max(ax - bw / 2, minX), Math.max(minX, maxX - bw));
      y = Math.max(minY, Math.min(ay - GAP - bh, maxY - bh));
      bubble.style.setProperty('--tail-x', Math.min(Math.max(ax - x, 14), bw - 14).toFixed(1) + 'px');
    } else {
      x = mode === 'side-r' ? hx + hr + GAP : hx - hr - GAP - bw;
      x = Math.min(Math.max(x, minX), Math.max(minX, maxX - bw));
      y = Math.min(Math.max(hy - 24, minY), Math.max(minY, maxY - bh));
      bubble.style.setProperty('--tail-y', Math.min(Math.max(hy - y - 6, 10), bh - 18).toFixed(1) + 'px');
    }
    bubble.classList.toggle('side-r', mode === 'side-r');
    bubble.classList.toggle('side-l', mode === 'side-l');
    bubble.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
  }
  stage.onFrame(placeBubble);

  // =============================================================================================================
  // the voice
  let muted = ls.get('muted') === '1';
  let actx = null, current = null, speakSeq = 0, answerVoice = false;
  const audioCtx = () => {
    if (!actx) { const C = window.AudioContext || window.webkitAudioContext; actx = C ? new C() : null; }
    if (actx?.state === 'suspended') actx.resume().catch(() => {});
    return actx;
  };
  ['pointerdown', 'keydown', 'touchstart'].forEach((ev) => window.addEventListener(ev, () => audioCtx(), { once: true, passive: true }));

  function stopVoice() {
    speakSeq++;
    try { current?.stop(); } catch { /* already ended */ }
    current = null;
    answerVoice = false;
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
  }

  async function speakPiper(text, seq) {
    const a = audioCtx();
    if (!a) return false;
    try {
      const r = await fetchT(services.tts.base.replace(/\/$/, '') + '/tts?text=' + encodeURIComponent(text.slice(0, 600)), {}, 8000);
      if (!r.ok) return false;
      const buf = await a.decodeAudioData(await r.arrayBuffer());
      if (seq !== speakSeq || muted) return true;              // superseded while loading: drop it silently
      const src = a.createBufferSource();
      src.buffer = buf;
      src.playbackRate.value = services.tts.rate ?? 1.14;      // 1.14 for a plain Piper: pup, not newsreader
      const g = a.createGain();
      g.gain.value = VOICE_GAIN;                                // under the turret: the shots are the loudest thing (sfx.js)
      src.connect(g).connect(a.destination);
      src.onended = () => { if (current === src) { current = null; answerVoice = false; } };
      current = src;
      src.start();
      return true;
    } catch { return false; }
  }

  function speakBrowser(text) {
    if (!('speechSynthesis' in window)) return false;
    try {
      const u = new SpeechSynthesisUtterance(text);
      u.rate = 1.0; u.pitch = 1.3; u.volume = VOICE_GAIN;      // a stronger lift turns most system voices into a squeak
      const vs = window.speechSynthesis.getVoices() || [];
      const en = vs.filter((v) => /^en/i.test(v.lang));
      const pick = (re) => en.find((v) => re.test(v.name));
      u.voice = pick(/natural|neural/i) || pick(/google us english|samantha|aria|jenny|ava|zira|female/i) || en[0] || null;
      const playback = { stop: () => window.speechSynthesis.cancel() };
      u.onend = u.onerror = () => { if (current === playback) { current = null; answerVoice = false; } };
      current = playback;
      window.speechSynthesis.speak(u);
      return true;
    } catch { return false; }
  }

  async function speak(text, conversation = false) {
    stopVoice();
    if (muted || !text) return false;
    const seq = speakSeq;
    answerVoice = conversation; // includes time waiting for a delayed voice service
    await detect();
    if (seq !== speakSeq || muted) return false;
    if (services.tts.ok && await speakPiper(text, seq)) return true;
    if (seq !== speakSeq || muted) return false;
    const started = speakBrowser(text);
    if (!started) answerVoice = false;
    return started;
  }

  function setMood(mood) {
    if (!eyes || !mood) return 0;
    const m = MOODS.includes(mood) ? mood : 'neutral';
    try { eyes.set(m); } catch { /* eyes are optional */ }
    return ++moodToken;
  }

  /** say(text, { mood, speak = true, hold }) — bubble + eye mood + voice. Resolves once the voice has started. */
  function say(text, { mood, speak: voice = true, hold, conversation = false } = {}) {
    text = String(text ?? '').trim();
    if (!text) return Promise.resolve(false);
    const tok = setMood(mood || guessMood(text));
    showBubble(text, { hold });
    const until = shownUntil;
    if (tok) setTimeout(() => { if (tok === moodToken && until === shownUntil) { try { eyes.set('neutral'); } catch { /* */ } } }, Math.max(0, until - performance.now()) + 200);
    return voice ? speak(text, conversation) : Promise.resolve(false);
  }

  // =============================================================================================================
  // the brain
  const history = [];
  const scriptBags = new Map(), fallbackBag = bag(FALLBACK), safetyBag = bag(SAFETY_LINES), banterBag = bag(BANTER);
  let askSeq = 0, replyBusyUntil = 0, askPending = false;

  function scripted(text) {
    const q = ' ' + text.toLowerCase() + ' ';
    for (const rule of SCRIPT) {
      if (rule[0].test(q)) {
        if (!scriptBags.has(rule)) scriptBags.set(rule, bag(rule[1]));
        return { text: scriptBags.get(rule)(), mood: rule[2], source: 'scripted' };
      }
    }
    const [t, mood] = fallbackBag();
    return { text: t, mood, source: 'scripted' };
  }

  async function llm(text) {
    const L = services.llm;
    const messages = [{ role: 'system', content: PERSONA }, ...history.slice(-8), { role: 'user', content: text.slice(0, 500) }];
    const headers = { 'Content-Type': 'application/json' };
    if (L.key) headers.Authorization = 'Bearer ' + L.key;
    const r = await fetchT(L.base + '/chat/completions', {
      method: 'POST', headers, body: JSON.stringify({ model: L.model, messages, max_tokens: 120, temperature: 0.8, stream: false }),
    }, 25000);
    if (!r.ok) throw new Error('llm ' + r.status);
    const j = await r.json();
    const out = cleanReply(j?.choices?.[0]?.message?.content);
    if (!out.text) throw new Error('empty reply');
    return { ...out, source: L.name };
  }

  /** ask(text, { speak = true }) -> Promise<reply string>. Shows a thinking bubble, answers in the bubble and aloud. */
  async function ask(text, { speak: voice = true } = {}) {
    text = String(text ?? '').trim().slice(0, 500);
    if (!text) return '';
    const seq = ++askSeq;
    askPending = true;
    stopVoice();
    setMood('thinking');
    showBubble('', { thinking: true });
    hint('');
    let reply;
    if (UNSAFE_IN.test(text)) reply = { text: safetyBag(), mood: 'grumpy', source: 'safety' };
    else if (PLAYER_IN.test(text)) reply = { text: banterBag(), mood: 'happy', source: 'banter' };   // game on: legs only
    else {
      await detect();
      if (services.llm.ok) {
        try { reply = await llm(text); } catch (e) { console.warn('[talk] brain unreachable, using the scripted brain:', e.message); }
      }
      reply ??= scripted(text);
      if (UNSAFE_OUT.test(reply.text)) reply = { text: safetyBag(), mood: 'focused', source: 'safety' };
    }
    if (seq !== askSeq) return reply.text;                     // a newer question took over
    askPending = false;
    history.push({ role: 'user', content: text }, { role: 'assistant', content: `[${reply.mood || 'neutral'}] ${reply.text}` });
    while (history.length > 12) history.shift();
    say(reply.text, { mood: reply.mood || guessMood(reply.text), speak: voice, conversation: true });
    replyBusyUntil = shownUntil;
    lastSource = reply.source;
    renderStatus();
    return reply.text;
  }
  let lastSource = '';

  // =============================================================================================================
  // the ears
  let listening = null;          // { stop() } while recording

  function listenWhisper() {
    return new Promise((resolve) => {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) return resolve({ error: 'This browser cannot record audio.' });
      navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
        const rec = new MediaRecorder(stream), chunks = [];
        const a = audioCtx(), an = a?.createAnalyser();
        let src = null, raf = 0, speech = false, quietSince = 0;
        const t0 = performance.now();
        if (a && an) { src = a.createMediaStreamSource(stream); an.fftSize = 1024; src.connect(an); }
        const data = new Float32Array(1024);
        const finish = () => { cancelAnimationFrame(raf); clearTimeout(cap); try { src?.disconnect(); } catch { /* */ } if (rec.state !== 'inactive') rec.stop(); };
        // silence auto-stop (mic.js): 1.1 s of quiet after speech, or 5 s with no speech at all; 12 s hard cap
        const level = () => {
          an.getFloatTimeDomainData(data);
          let s = 0; for (const v of data) s += v * v;
          const rms = Math.sqrt(s / data.length), now = performance.now();
          if (rms > 0.02) { speech = true; quietSince = 0; } else if (!quietSince) quietSince = now;
          if ((speech && quietSince && now - quietSince > 1100) || (!speech && now - t0 > 5000)) return finish();
          raf = requestAnimationFrame(level);
        };
        const cap = setTimeout(finish, 12000);
        rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
        rec.onstop = async () => {
          stream.getTracks().forEach((t) => t.stop());
          listening = null;
          const blob = new Blob(chunks, { type: rec.mimeType || 'audio/webm' });
          if (blob.size < 800 || (an && !speech)) return resolve({ error: 'I did not hear anything.' });
          setListenUI('busy');
          try {
            const r = await fetchT(services.stt.base.replace(/\/$/, '') + '/stt', { method: 'POST', headers: { 'Content-Type': blob.type }, body: blob }, 20000);
            const j = await r.json();
            const t = j?.channel?.alternatives?.[0]?.transcript?.trim();
            resolve(t ? { text: t } : { error: 'I did not catch that. Try again?' });
          } catch { resolve({ error: 'The Whisper server did not answer.' }); }
        };
        rec.start();
        listening = { stop: finish };
        if (an) raf = requestAnimationFrame(level);
      }, () => resolve({ error: 'Microphone blocked. Allow the mic for this page and try again.' }));
    });
  }

  function listenBrowser() {
    return new Promise((resolve) => {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      const rec = new SR();
      rec.lang = 'en-US'; rec.interimResults = true; rec.maxAlternatives = 1;
      let final = '', done = false;
      const end = (v) => { if (!done) { done = true; listening = null; resolve(v); } };
      rec.onresult = (e) => {
        let interim = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {
          if (e.results[i].isFinal) final += e.results[i][0].transcript; else interim += e.results[i][0].transcript;
        }
        if (input) input.value = (final + interim).trim();
      };
      rec.onerror = (e) => end({ error: {
        'not-allowed': 'Microphone blocked. Allow the mic for this page and try again.',
        'service-not-allowed': 'Microphone blocked. Allow the mic for this page and try again.',
        'no-speech': 'I did not hear anything.',
        network: 'The browser speech service is unreachable (it needs the internet). Start the Whisper server instead.',
        'audio-capture': 'No microphone found.',
      }[e.error] || 'Speech recognition failed (' + e.error + ').' });
      rec.onend = () => end(final.trim() ? { text: final.trim() } : { error: 'I did not hear anything.' });
      try { rec.start(); } catch { return end({ error: 'Speech recognition could not start.' }); }
      listening = { stop: () => rec.stop() };
    });
  }

  /** listen() -> Promise<transcript string, or null>. Calling it again while recording stops the recording. */
  async function listen() {
    if (listening) { listening.stop(); return null; }
    stopVoice();
    await detect();
    let res;
    if (services.stt.ok) { setListenUI('on'); setMood('curious'); hint('Listening... (Whisper)'); res = await listenWhisper(); }
    else if (window.SpeechRecognition || window.webkitSpeechRecognition) { setListenUI('on'); setMood('curious'); hint('Listening... (browser speech)'); res = await listenBrowser(); }
    else {
      res = { error: "I can't hear in this browser. Start Moxie's Whisper server (python3 sim/stt/server.py 8082) or use Chrome; or just type!" };
    }
    setListenUI('off');
    if (res.error) { hint(res.error, true); setMood('sad'); setTimeout(() => setMood('neutral'), 1500); return null; }
    hint('You said: “' + res.text + '”');
    return res.text;
  }

  // =============================================================================================================
  // reactions to sim events
  const reactBags = new Map(), reactLast = new Map();
  let reactGlobal = 0;
  /** react(event) -> the line said, or null when rate-limited. Events: hit, down, miss, fire, fall, reload, empty, low_battery, hello. */
  function react(event) {
    const R = REACT[event];
    if (!R) return null;
    const now = performance.now();
    if (isBusy()) return null;                          // never talk over an answer
    if (now - (reactLast.get(event) ?? -1e9) < R.gap) return null;   // per-event cooldown
    if (!R.priority && (now - reactGlobal < 3500 || (visible && now < shownUntil - 300))) return null;
    if (R.p != null && Math.random() > R.p) return null;
    if (!reactBags.has(event)) reactBags.set(event, bag(R.lines));
    const line = reactBags.get(event)();
    reactLast.set(event, now); reactGlobal = now;
    say(line, { mood: R.mood });
    return line;
  }

  // Stage changes and game reactions are background chatter. The conversation owns the
  // bubble, voice and expression while listening, thinking, or presenting an answer.
  function isBusy() { return askPending || answerVoice || !!listening || performance.now() < replyBusyUntil; }
  function announce(text, options = {}) {
    if (isBusy() || (visible && performance.now() < shownUntil)) return false;
    say(text, options);
    return true;
  }

  function setMuted(v) {
    muted = !!v; ls.set('muted', muted ? '1' : '0');
    if (muted) stopVoice();
    if (muteBtn) { muteBtn.classList.toggle('muted', muted); muteBtn.innerHTML = muted ? ICON.muted : ICON.speaker; muteBtn.title = muted ? 'Unmute Gyropup' : 'Mute Gyropup'; muteBtn.setAttribute('aria-pressed', String(muted)); }
    renderStatus();
    return muted;
  }

  // =============================================================================================================
  // the dock
  let dockEl = null, input = null, listenBtn = null, askBtn = null, muteBtn = null, hintEl = null, statusEl = null;

  function hint(t, warn = false) { if (hintEl) { hintEl.textContent = t || ''; hintEl.classList.toggle('warn', !!warn); } }
  function setListenUI(state) {
    if (!listenBtn) return;
    listenBtn.classList.toggle('listening', state === 'on');
    listenBtn.querySelector('.gp-btn-label').textContent = state === 'on' ? 'Stop' : state === 'busy' ? '...' : 'Listen';
    listenBtn.disabled = state === 'busy';
  }
  function renderStatus() {
    if (!statusEl) return;
    const b = (label, val, ok) => `${label} <b class="${ok ? 'ok' : ''}">${val}</b>`;
    if (!services.checked) { statusEl.innerHTML = 'voice · ears · brain: <b>on first use</b>'; return; }
    const voice = services.tts.name + (services.tts.ok && services.tts.label ? ` (${services.tts.label})` : '');
    statusEl.innerHTML = [
      b('VOICE', muted ? 'muted' : voice, services.tts.ok && !muted),
      b('EARS', services.stt.name, services.stt.ok),
      b('BRAIN', services.llm.ok ? services.llm.model : 'scripted', services.llm.ok),
    ].join(' · ');
    statusEl.title = `voice: ${services.tts.ok ? `Piper ${services.tts.voice ?? ''} at ${services.tts.base}` : 'browser speechSynthesis'}\n` +
      `ears: ${services.stt.ok ? 'Whisper at ' + services.stt.base : services.stt.name === 'browser' ? 'browser Web Speech API' : 'none'}\n` +
      `brain: ${services.llm.ok ? services.llm.base + ' (' + services.llm.model + ')' : 'scripted replies'}` + (lastSource ? `\nlast reply: ${lastSource}` : '');
  }

  const dockApi = {
    el: null,
    collapse(v = true) { if (!dockEl) return; dockEl.classList.toggle('collapsed', !!v); ls.set('dockCollapsed', v ? '1' : '0'); cache.at = -1e9; dockEl.querySelector('.gp-dock-tab').setAttribute('aria-expanded', String(!v)); },
    toggle() { dockApi.collapse(!dockEl?.classList.contains('collapsed')); },
    isCollapsed: () => !!dockEl?.classList.contains('collapsed'),
    hint,
  };

  if (wantDock) {
    const chipTexts = (chips ?? ['Hi Gyropup!', 'Do a trick!', 'How do you balance?']).slice(0, 3);
    dockEl = document.createElement('div');
    dockEl.className = 'gp-dock';
    dockEl.innerHTML = `
      <button type="button" class="gp-dock-tab" aria-expanded="true" title="Show or hide the talk dock"><span class="gp-dot"></span>Talk${ICON.chevron}</button>
      <div class="gp-dock-body">
        <div class="gp-dock-head"><span class="gp-tick"></span><span class="gp-title">Talk to Gyropup</span><span class="gp-status"></span>
          <button type="button" class="gp-icon-btn gp-mute"></button></div>
        <div class="gp-chips">${chipTexts.map((c) => `<button type="button" class="gp-chip"></button>`).join('')}</div>
        <form class="gp-row" autocomplete="off">
          <input type="text" maxlength="300" placeholder="Say something to Gyropup..." aria-label="Message to Gyropup">
          <button type="button" class="gp-btn gp-listen" title="Talk with your microphone">${ICON.mic}<span class="gp-btn-label">Listen</span></button>
          <button type="submit" class="gp-btn primary gp-ask" title="Ask Gyropup">${ICON.send}<span class="gp-btn-label">Ask</span></button>
        </form>
        <p class="gp-hint" aria-live="polite"></p>
      </div>`;
    document.body.appendChild(dockEl);
    if (!document.getElementById('panel')) dockEl.classList.add('no-panel');
    input = dockEl.querySelector('input'); listenBtn = dockEl.querySelector('.gp-listen'); askBtn = dockEl.querySelector('.gp-ask');
    muteBtn = dockEl.querySelector('.gp-mute'); hintEl = dockEl.querySelector('.gp-hint'); statusEl = dockEl.querySelector('.gp-status');
    dockEl.querySelectorAll('.gp-chip').forEach((el, i) => {
      el.textContent = chipTexts[i];
      el.addEventListener('click', () => { input.value = ''; ask(chipTexts[i]); });
    });
    const submit = async () => {
      const t = input.value.trim();
      if (!t) { input.focus(); return; }
      input.value = '';
      askBtn.disabled = true;
      try { await ask(t); } finally { askBtn.disabled = false; }
    };
    dockEl.querySelector('form').addEventListener('submit', (e) => { e.preventDefault(); submit(); });
    listenBtn.addEventListener('click', async () => { const t = await listen(); if (t) { input.value = ''; ask(t); } });
    muteBtn.addEventListener('click', () => setMuted(!muted));
    dockEl.querySelector('.gp-dock-tab').addEventListener('click', () => dockApi.toggle());
    // keep sim keyboard shortcuts from firing while typing
    input.addEventListener('keydown', (e) => e.stopPropagation());
    // detect services the first time somebody reaches for the dock
    dockEl.addEventListener('pointerenter', () => detect(), { once: true });
    dockEl.addEventListener('focusin', () => detect(), { once: true });
    dockApi.el = dockEl;
    if (ls.get('dockCollapsed') === '1') dockApi.collapse(true);
  }
  setMuted(muted);
  renderStatus();

  return { say, ask, listen, react, announce, isBusy, get conversation() { return history.map(entry => ({ ...entry })); }, setMuted, dock: dockApi, services, detect, stop: () => { stopVoice(); hideBubble(); } };
}
