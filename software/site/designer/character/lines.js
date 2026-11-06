// Every fixed line Gyropup says, in one place. talk.js, sim.js, the landing page and the talk demo take their lines
// from here, and tools/render-voice.py renders each one to a clip (designer/character/voice/), so the public site
// speaks recorded audio instead of a live voice. A line said anywhere else (an LLM answer) is spoken live.
// Adding or changing a line: edit it here, then run tools/render-voice.py (CI fails until the clips match).
//
// Pure data: no DOM, no imports, so Node (the renderer and the tests) can import it.

// ---------------------------------------------------------------------------------------------------------------
// talk.js: reactions, battle banter, safety answers

// Battle banter: Tritium is kids versus robots with foam balls (safety glasses on, legs only).
export const BANTER = ['I promise to aim for the legs!', 'Safety glasses on? Then it is game on!', 'Legs only, I am a good pup!',
  'Ankle-biter mode: engaged!', 'Heads are off-limits. Knees, watch out!', 'I aim low because I am short. Arf!',
  'You can run, but my wheels are faster! Just kidding, mostly.'];

export const REACT = {
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

export const SAFETY_LINES = ['Never heads or faces! I aim for the legs, and everybody wears safety glasses.',
  'No way! Heads are off-limits. Legs and targets only, that is the Gyropup promise!',
  'Not pets, not faces, not anyone without safety glasses. Want me to knock down a target instead?'];

// ---------------------------------------------------------------------------------------------------------------
// talk.js: the scripted brain (used when no LLM is reachable)

// The scripted brain: [pattern, replies, mood]. First match wins; replies rotate without repeats.
export const SCRIPT = [
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
export const FALLBACK = [['Ooh, tell me more!', 'curious'], ['Hmm, my circuits are thinking about that!', 'thinking'],
  ['I do not know that one, but I can do a wiggle!', 'happy'], ['Arf? Can you say that another way?', 'curious']];

// ---------------------------------------------------------------------------------------------------------------
// designer/sim.js: one line as a scenario starts (by scenario name; DEFAULT_INTRO otherwise).
export const INTRO = {
  stand: ['Hi! Watch me balance!', 'Hello! Standing still is harder than it looks!'],
  squat: ['Hi! Squats, here we go!', 'Hello! Down... and up!'],
  push: ['Hi! Go on, give me a shove!', 'Hello! Push me, I dare you!'],
  drive: ['Hi! Zoom zoom, here I go!', 'Hello! Time for a drive!'],
  slope: ['Hi! Uphill, here I come!', 'Hello! A hill? No problem... I hope.'],
  curb: ['Hi! A kerb ahead. Hup!', 'Hello! Watch me hop this step!'],
  recoil: ['Hi! Brace for recoil!', 'Hello! Big burst coming, hold on!'],
  look: ['Hi! What is up there?', 'Hello! Let me look up at the sky!'],
  targets: ['Hi! Target practice time! I promise to aim for the legs!', 'Hello! Five targets? Easy peasy!', 'Hi! Safety glasses on? Let us knock them down!'],
};
export const DEFAULT_INTRO = ['Hi! Watch this!'];

// The landing page (web/landing.js): [line, mood], one every 35 s while the hero is on screen.
export const LANDING = [
  ['Hi! I’m Gyropup. Ready for a backyard adventure?', 'happy'],
  ['Want to see how I work? Take a peek inside!', 'curious'],
  ['My next big idea? A ridiculously good foam-ball battle.', 'happy'],
  ['I’m still taking shape. Come try my playground!', 'curious'],
];

// The talk demo (designer/character/talk-demo.html): its greeting and one line per mood button.
export const DEMO_GREETING = 'Hi! I am Gyropup. Want to play a target game?';
export const DEMO_MOODS = { happy: 'Wheee! That was fun!', curious: 'Ooh, what is that?', sleepy: 'Yawn... charger time?', grumpy: 'Hey! Foam balls at targets only!', surprised: 'Whoa! Did you see that?', focused: 'Locking on to the target...' };

/** Every fixed line, each once, in a stable order: what tools/render-voice.py renders and CI checks. */
export function fixedLines() {
  const all = [
    ...BANTER, ...Object.values(REACT).flatMap(r => r.lines), ...SAFETY_LINES,
    ...SCRIPT.flatMap(rule => rule[1]), ...FALLBACK.map(f => f[0]),
    ...Object.values(INTRO).flat(), ...DEFAULT_INTRO, ...LANDING.map(l => l[0]), DEMO_GREETING, ...Object.values(DEMO_MOODS),
  ];
  return [...new Set(all.map(line => line.trim()))];
}
