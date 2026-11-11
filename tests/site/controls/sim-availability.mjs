/** Public activation controls: use the real page/loader, never a legacy test override. */
import assert from 'node:assert/strict';
export async function checkPublicAvailability({ page, base, out, engine }) {
  const requests = [], cases = [];
  const request = event => requests.push(new URL(event.url()).pathname);
  page.on('request', request);
  const current = async label => {
    await page.waitForFunction(() => document.body.dataset.ready === '1' && window.__sim?.state.modelKey === 'v2' && !window.__sim.state.bench);
    const observed = await page.evaluate(() => {
      const s = window.__sim;
      return { selected: document.querySelector('#design-select').value, presentation: s.state.robot.presentation, replay: !!s.state.replay };
    });
    assert.equal(observed.selected, 'v2', label);
    assert.equal(observed.presentation.mode, 'current', label);
    assert.equal(observed.presentation.nativeSource, '3a40891962b0b0a04625e070700f1d130bea3c7b', label);
    assert.equal(observed.presentation.collectionSha256, '7c2f1905474a8c89bdc477ea472f5c826e57c674aa222f2134f6a0a4138d5a67', label);
    assert.equal(observed.replay, false, label);
    cases.push({ label, ...observed });
  };
  const url = base + '/designer/sim.html?sound=0&demo=0&run=none';
  try {
    await page.goto(url, { waitUntil: 'networkidle' });
    await current('default current robot');
    const legacy = page.locator('#design-select option[value="designs/default.json"]');
    assert.equal(await legacy.isDisabled(), true);
    assert.match(await legacy.textContent(), /v1.*unavailable/);
    // Simulate browser-restored form state: a disabled option is not a loader capability.
    await page.evaluate(() => {
      localStorage.setItem('gyropup-design-v1', JSON.stringify({ name: 'Saved v1', file: 'designs/default.json' }));
      const select = document.querySelector('#design-select');
      select.value = 'designs/default.json'; select.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await current('restored disabled value is rejected');
    const notice = page.locator('#sim-design-unavailable');
    await notice.waitFor({ state: 'visible' });
    assert.match(await notice.textContent(), /v1 is unavailable.*current Gyropup/);
    await notice.getByRole('button', { name: 'Keep playing' }).click();
    await notice.waitFor({ state: 'hidden' });
    await page.reload({ waitUntil: 'networkidle' });
    await current('reload with saved v1 design remains current');
    await page.selectOption('#design-select', 'turret-box');
    await page.waitForFunction(() => window.__sim.state.bench === true);
    assert.equal(await page.locator('#design-select').inputValue(), 'turret-box');
    await page.selectOption('#design-select', 'v2');
    await current('enabled turret and current choices still work');
    // An old v1 recording link must not become a different model’s recorded activity.
    const oldUrl = url.replace('run=none', 'design=designs%2Fdefault.json&run=drive');
    await page.goto(oldUrl, { waitUntil: 'networkidle' });
    await current('direct v1 recording URL falls back to current');
    await notice.waitFor({ state: 'visible' });
    await page.screenshot({ path: `${out}/${engine.name()}-v1-unavailable.png` });
    await page.reload({ waitUntil: 'networkidle' });
    await current('old direct URL remains safe after reload');
    await notice.waitFor({ state: 'visible' });
    await page.goBack({ waitUntil: 'networkidle' });
    await current('back restores current route');
    assert.equal(new URL(page.url()).searchParams.has('design'), false);
    await page.goForward({ waitUntil: 'networkidle' });
    await current('forward cannot activate v1');
    assert.equal(new URL(page.url()).searchParams.get('design'), 'designs/default.json');
    await notice.waitFor({ state: 'visible' });
    assert.equal(requests.some(path => path === '/designs/default.json' || path === '/exports/links/manifest.json' || /^\/exports\/sim\/(default|v2)\/drive\.json$/.test(path)), false,
      'Public rejection does not fetch legacy design/rig or silently substitute a recorded drive');
    return { cases, requests };
  } finally { page.off('request', request); }
}
