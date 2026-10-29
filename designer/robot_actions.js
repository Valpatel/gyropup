// The full robot's visible play controls. Actions use the existing simulator
// scene and replay lifecycle; this module owns only presentation.
export function createRobotActions({ parent, onDemo, onPlay, onActivity, onFire, onReload, onLayout }) {
  const css = document.createElement('link');
  const cssUrl = new URL('./robot_actions.css', import.meta.url);
  cssUrl.search = new URL(import.meta.url).search;
  css.rel = 'stylesheet'; css.href = cssUrl.href;
  css.onload = onLayout; document.head.append(css);
  const bar = document.createElement('div');
  bar.id = 'robot-actions'; bar.setAttribute('aria-label', 'Robot play controls');
  bar.innerHTML = `<div class="ra-play"><button type="button" data-action="demo">Demo on</button>
    <button type="button" data-action="play">Pause</button>
    <select aria-label="Robot activity"><option value="demo">Demo tour</option><option value="live">Drive & play</option><option value="drive">Watch driving</option><option value="targets">Target practice</option><option value="other" hidden>Physics replay</option></select></div>
    <div class="ra-fire"><button type="button" data-action="fire">FIRE<small>1 foam ball</small></button>
    <button type="button" data-action="burst">BURST<small>8 foam balls</small></button>
    <button type="button" data-action="reload">RELOAD<small data-ammo></small></button></div>`;
  const demo = bar.querySelector('[data-action=demo]'), play = bar.querySelector('[data-action=play]'), activity = bar.querySelector('select');
  const fire = bar.querySelector('[data-action=fire]'), burst = bar.querySelector('[data-action=burst]'), reload = bar.querySelector('[data-action=reload]'), ammo = bar.querySelector('[data-ammo]');
  demo.onclick = onDemo; play.onclick = onPlay; activity.onchange = () => onActivity(activity.value);
  fire.onclick = () => onFire(1); burst.onclick = () => onFire(8); reload.onclick = onReload;
  parent.append(bar);
  new ResizeObserver(() => {
    document.documentElement.style.setProperty('--robot-actions-h', `${Math.ceil(bar.getBoundingClientRect().height)}px`);
    onLayout();
  }).observe(bar);
  let previous = '';
  return { paint({ hidden, demoOn, replay, playing, scenario, mag, capacity, attached }) {
    const key = [hidden,demoOn,replay,playing,scenario,mag,capacity,attached].join('|');
    if (key === previous) return; previous = key;
    bar.hidden = hidden;
    demo.textContent = `Demo ${demoOn ? 'on' : 'off'}`; demo.classList.toggle('on', demoOn); demo.setAttribute('aria-pressed', String(demoOn));
    play.textContent = replay ? (playing ? 'Pause' : 'Play') : 'Live'; play.disabled = !replay;
    activity.value = demoOn ? 'demo' : !replay ? 'live' : ['drive','targets'].includes(scenario) ? scenario : 'other';
    fire.disabled = burst.disabled = !attached || mag <= 0; reload.disabled = !attached;
    ammo.textContent = `${mag} / ${capacity} balls`;
    for (const button of [fire,burst,reload]) button.title = replay ? 'Take control of the robot and play live' : '';
  } };
}
