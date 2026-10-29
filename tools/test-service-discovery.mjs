/** Exercise the real chat module without contacting any visitor/local services. */
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { chromium, webkit } from '@playwright/test';

const engine = process.env.PLAYWRIGHT_BROWSER === 'webkit' ? webkit : chromium;
const browser = await engine.launch(engine === chromium ? { channel: 'chrome', headless: true } : { headless: true });
const root = new URL('../', import.meta.url);
const html = `<!doctype html><meta charset="utf-8"><title>Chat discovery regression</title>
<script type="importmap">{"imports":{"three":"/designer/kit/vendor/three/three.module.min.js"}}</script>
<script type="module">
import { mountTalk } from '/designer/character/talk.js';
window.talk = mountTalk({stage:{onFrame(){}}, getHead:()=>null});
window.talk.setMuted(true);
</script>`;

async function check({ origin, storage = {}, brain, expected, replySource = 'scripted', failedExplicit = false }) {
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  const page = await context.newPage(), services = [], errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.addInitScript(({ storage, brain }) => {
    for (const [key, value] of Object.entries(storage)) localStorage.setItem('gyropup.' + key, value);
    if (brain) window.GYROPUP_BRAIN = brain;
  }, { storage, brain });
  // All requests are intercepted, including expected discovery, so the harness is safe on any host.
  await page.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin === origin && url.pathname === '/') return route.fulfill({ contentType: 'text/html', body: html });
    if (url.origin === origin && url.pathname.startsWith('/designer/')) {
      const body = await readFile(new URL(url.pathname.slice(1), root));
      return route.fulfill({ contentType: url.pathname.endsWith('.css') ? 'text/css' : 'text/javascript', body });
    }
    services.push(url.href);
    const headers = { 'access-control-allow-origin': '*' };
    if (failedExplicit && url.hostname === 'ai.example.test') return route.fulfill({ status: 503, headers, body: 'Unavailable' });
    if (url.pathname === '/api/tags') return route.fulfill({ headers, json: { models: [{ name: 'llama3.2:test' }] } });
    if (url.pathname.endsWith('/models')) return route.fulfill({ headers, json: { data: [{ id: 'configured-model' }] } });
    if (url.pathname.endsWith('/chat/completions')) return route.fulfill({ headers, json: { choices: [{ message: { content: '[happy] The configured service answered.' } }] } });
    if (url.pathname === '/health') return route.fulfill({ headers, json: { ok: true } });
    throw new Error('Unexpected request: ' + url.href);
  });
  try {
    await page.goto(origin);
    await page.waitForFunction(() => window.talk);
    // A real dock interaction triggers discovery; the second call shares the first promise.
    await page.locator('input[aria-label="Message to Gyropup"]').focus();
    await page.evaluate(() => window.talk.detect());
    assert.deepEqual([...services].sort(), [...expected].sort(), origin);
    assert.equal(await page.evaluate(() => window.talk.services.llm.name), replySource, origin);
    const reply = await page.evaluate(() => window.talk.ask('Hello', { voice: false }));
    assert.ok(reply && await page.evaluate(() => window.talk.conversation.length === 2), 'Chat remains usable');
    const chatRequests = services.filter(url => url.endsWith('/chat/completions'));
    assert.equal(chatRequests.length, replySource === 'scripted' ? 0 : 1);
    assert.deepEqual(errors, [], origin);
    console.log(`PASS ${engine.name()} ${origin} (${replySource})`);
  } finally { await context.close(); }
}

try {
  for (const host of ['gyropup.com', 'www.gyropup.com', 'localhost.example.com', '10.example.com', '127.example.com', '172.32.0.1', '100.128.0.1']) {
    await check({ origin: `https://${host}`, expected: [] });
  }
  for (const host of ['localhost', '127.0.0.1', '192.168.1.20', '10.0.0.2', '172.16.0.2', '100.64.0.2', 'robot.local', 'robot.tailnet.ts.net']) {
    await check({ origin: `http://${host}`, expected: [`http://${host}:8081/health`, `http://${host}:8082/health`, 'http://127.0.0.1:11434/api/tags'], replySource: 'ollama:llama3.2:test' });
  }
  await check({ origin: 'http://localhost', storage: { probe: 'off' }, expected: [] });
  await check({ origin: 'https://gyropup.com', storage: { llmBase: 'https://ai.example.test/v1' }, expected: ['https://ai.example.test/v1/models'], replySource: 'llm:configured-model' });
  await check({ origin: 'https://gyropup.com', brain: { base: 'https://ai.example.test/v1' }, expected: ['https://ai.example.test/v1/models'], replySource: 'llm:configured-model' });
  await check({ origin: 'https://gyropup.com', storage: { llmBase: 'https://ai.example.test/v1' }, failedExplicit: true, expected: ['https://ai.example.test/v1/models'] });
  await check({ origin: 'https://gyropup.com', storage: { ttsBase: 'https://voice.example.test', sttBase: 'https://ears.example.test' }, expected: ['https://voice.example.test/health', 'https://ears.example.test/health'] });
} finally { await browser.close(); }
