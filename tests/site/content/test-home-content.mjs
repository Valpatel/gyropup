/** Home is an evergreen entrance; full evidence remains discoverable on Progress. */
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import path from 'node:path';
import {test} from 'node:test';
import {parseHTML} from 'linkedom';

const root=path.resolve(import.meta.dirname,'../../..');
const home=readFileSync(path.join(root,'dist/index.html'),'utf8');
const progress=readFileSync(path.join(root,'dist/designer/progress.html'),'utf8');
const doc=html=>parseHTML(html).document;
function checkHome(html,progressHTML=progress){
  const d=doc(html),p=doc(progressHTML),main=d.querySelector('main');
  assert.ok(main,'Home has its main entrance');
  assert.equal(d.querySelectorAll('h1').length,1);
  assert.ok(main.textContent.trim().split(/\s+/).length<=300,'Home copy stays under 300 words, including reel controls');
  assert.equal(main.querySelectorAll('.sb-panel,.sb-meter,.tl-event,.loop-cards,.loop-figure').length,0,'No embedded engineering/history wall, even hidden');
  assert.equal(main.querySelectorAll('img[src*="/exports/body/views/exploded.png"]').length,0,'No obsolete body illustration');
  assert.doesNotMatch(main.textContent,/current CAD \(stage P3\)|37\.5 kg|100 lb|\$10,000/,'No stale or maintenance-heavy target claims');
  for(const id of ['main','meet','play-title','built','loop','board','changes','ecosystem-title'])assert.ok(d.getElementById(id),`Preserve #${id}`);
  for(const route of ['/designer/sim.html','/designer/build.html','/designer/progress.html'])assert.ok(main.querySelector(`.home-door[href="${route}"]`),`Clear entrance to ${route}`);
  for(const id of ['board','changes']){
    assert.equal(d.querySelector(`a#${id}`).getAttribute('href'),`/designer/progress.html#${id}`);
    assert.ok(p.getElementById(id),`Progress resolves #${id}`);
  }
  assert.ok(main.querySelector('a[href="/designer/progress.html#loop"]'));
  assert.ok(p.querySelector('#workshop-stories #loop .loop-cards'),'Dated evidence remains on Progress');
  assert.equal(p.querySelector('#workshop-stories').hasAttribute('open'),false,'Stories stay one deliberate click away');
  assert.match(main.querySelector('.home-prototype').textContent,/prototype.*hardware and build files are experimental/i);
  assert.match(main.querySelector('.hero-copy').textContent,/browser/i);
  assert.match(main.querySelector('.motto-line').textContent.replace(/\s+/g,' ').trim(),/^Strike first, strike fast, strike last$/);
  for(const id of ['robot-preview','hero-loading','hero-loading-message','hero-inspect','hero-sound','hero-volume','highlight-video'])assert.ok(d.getElementById(id),`Existing interactive contract #${id}`);
  assert.ok(d.querySelector('.made-with[href="https://cad-agent.valpatel.com/"]'));
}

test('built Home is short, robot-centered and keeps the evidence entrances',()=>checkHome(home));
test('an obsolete current body illustration is rejected',()=>{
  const d=doc(home);d.querySelector('main').insertAdjacentHTML('beforeend','<img src="/exports/body/views/exploded.png" alt="Current body">');
  assert.throws(()=>checkHome(d.toString()),/obsolete body illustration/);
});
test('a hidden status wall is still rejected',()=>{
  const d=doc(home);d.querySelector('main').insertAdjacentHTML('beforeend','<section class="sb-panel" hidden>status</section>');
  assert.throws(()=>checkHome(d.toString()),/engineering\/history wall/);
});
test('broken legacy anchors and deep destinations are rejected',()=>{
  const d=doc(home);d.getElementById('built').removeAttribute('id');assert.throws(()=>checkHome(d.toString()),/Preserve #built/);
  const wrong=doc(home);wrong.querySelector('a#board').setAttribute('href','#board');assert.throws(()=>checkHome(wrong.toString()));
  const p=doc(progress);p.getElementById('changes').removeAttribute('id');assert.throws(()=>checkHome(home,p.toString()),/Progress resolves #changes/);
});
test('removing a primary route or the concise prototype boundary is rejected',()=>{
  const d=doc(home);d.querySelector('.home-door[href="/designer/build.html"]').remove();assert.throws(()=>checkHome(d.toString()),/Clear entrance/);
  const unsafe=doc(home);unsafe.querySelector('.home-prototype').textContent='Ready for backyard battles.';assert.throws(()=>checkHome(unsafe.toString()),/prototype/i);
});
