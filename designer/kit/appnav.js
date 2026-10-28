// The app-wide top bar for a project's own pages: reads site/nav.json (written by `cad-agent site`) and renders the
// same tabs as the project site, so every page of the app shares one navigation.
//   mountAppNav({ root: '../', current: 'simulate' })   // root: path from this page to the project root
const NAV_CSS = `
.appnav{position:fixed;top:0;left:0;right:0;z-index:50;display:flex;align-items:center;gap:8px;padding:0 24px;height:64px;background:rgba(255,250,242,.97);backdrop-filter:blur(12px);border-bottom:1px solid #d9ddcf;font-family:'Inter',system-ui,sans-serif;color:#263e35}
.appnav .brand{font-weight:800;letter-spacing:-.8px;margin-right:auto;white-space:nowrap;display:flex;align-items:center;gap:8px;color:#263e35;text-decoration:none;font-size:22px}
.appnav .brand img{width:28px;height:28px}.appnav .brand small{display:block;font:9px/1.2 'Inter',system-ui,sans-serif;letter-spacing:0;color:#626e64}.appnav .nav-links{display:flex;align-items:center;gap:4px}
.appnav a.tab{font:600 12px 'Inter',system-ui,sans-serif;color:#526457;text-decoration:none;padding:12px 14px;border-radius:30px;white-space:nowrap}
.appnav a.tab:hover{color:#ad421b;background:#f5ead8}.appnav a.tab.on{color:#a93c14;background:#f4e7d3}
.appnav .menu-toggle{display:none;align-items:center;justify-content:center;min-height:44px;border:1px solid #cbd3c1;border-radius:24px;background:#fffaf2;padding:10px 17px;color:#263e35;font:600 12px 'Inter',system-ui,sans-serif;cursor:pointer}
body.has-appnav{--appnav-h:64px}.appnav a:focus-visible,.appnav button:focus-visible{outline:3px solid #187a79;outline-offset:3px}
@media(max-width:760px){.appnav{height:56px;padding-left:max(16px,env(safe-area-inset-left));padding-right:max(16px,env(safe-area-inset-right))}.appnav .brand{font-size:21px}.appnav .menu-toggle{display:flex}.appnav .nav-links{display:none;position:absolute;top:56px;left:0;right:0;background:#fffaf2;box-shadow:0 12px 20px #263e3515;padding:12px 16px 18px;grid-template-columns:repeat(2,minmax(0,1fr));border-bottom:1px solid #d9ddcf}.appnav.menu-open .nav-links{display:grid}.appnav a.tab{min-height:44px}body.has-appnav{--appnav-h:56px}}
`;

// root must be a plain relative path (../../, ./, designer/): it goes into links and the nav.json URL
const ROOT_OK = /^(?:\.\.?\/)*(?:[A-Za-z0-9_-][A-Za-z0-9._-]*\/)*$/;

export async function mountAppNav({ root = '../', current = '' } = {}) {
  if (typeof root !== 'string' || !ROOT_OK.test(root)) return null;
  let cfg;
  try { cfg = await (await fetch(`${root}site/nav.json`, { cache: 'no-cache' })).json(); } catch { return null; }
  if (!cfg?.nav?.length) return null;
  const style = document.createElement('style');
  style.textContent = NAV_CSS;
  document.head.appendChild(style);
  const nav = document.createElement('nav');
  nav.className = 'appnav';
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  // nav.json links: relative to the project root, or absolute http(s)/mailto; anything else (javascript:, data:) is dropped
  const href = (h) => {
    h = String(h ?? '');
    if (/^[a-z][a-z0-9+.-]*:/i.test(h)) return /^(https?:|mailto:)/i.test(h) ? h : null;
    return h.startsWith('//') ? null : root + h;
  };
  nav.setAttribute('aria-label', 'Gyropup navigation');
  nav.innerHTML = `<a class="brand" href="${esc(root)}"><img src="${esc(root)}web/icon.svg" alt=""><span>${esc(cfg.title)}${current === 'simulate' ? '<small>Prototype · demo snapshot</small>' : ''}</span></a>`
    + '<button type="button" class="menu-toggle" aria-expanded="false" aria-controls="portal-nav-links">Menu ☰</button>'
    + '<div class="nav-links" id="portal-nav-links">'
    + cfg.nav.filter((n) => href(n?.href) !== null).map((n) => `<a class="tab${(n.id ?? n.href) === current ? ' on' : ''}" `
      + `${(n.id ?? n.href) === current ? 'aria-current="page" ' : ''}href="${esc(href(n.href))}">${esc(n.title)}</a>`).join('') + '</div>';
  const menu = nav.querySelector('.menu-toggle');
  const setMenu = open => { nav.classList.toggle('menu-open', open); menu.setAttribute('aria-expanded', String(open)); };
  menu.addEventListener('click', () => setMenu(!nav.classList.contains('menu-open')));
  nav.addEventListener('keydown', e => { if (e.key === 'Escape') { setMenu(false); menu.focus(); } });
  nav.querySelectorAll('a').forEach(a => a.addEventListener('click', () => setMenu(false)));
  document.body.prepend(nav);
  document.body.classList.add('has-appnav');
  liveReload();
  return nav;
}

/**
 * Live reload for local work: when the page is served by `cad-agent site --serve` on this machine, it polls the
 * server for the newest change under the project and reloads once changes have settled (2 s quiet), at most every
 * 8 s. `?live=0` turns it off for a page.
 */
export function liveReload({ every = 2000, settle = 2000, minGap = 8000 } = {}) {
  if (!/^(127\.0\.0\.1|localhost|\[::1\])$/.test(location.hostname) || new URLSearchParams(location.search).get('live') === '0') return;
  if (window.__cadagentLive) return;
  window.__cadagentLive = true;
  let first = null, seen = null, changedAt = 0;
  const loadedAt = Date.now();
  const tick = async () => {
    try {
      const r = await fetch('/_cadagent/changes', { cache: 'no-store' });
      if (!r.ok) return;                                   // an older server: no live reload
      const { stamp } = await r.json();
      if (first === null) { first = seen = stamp; }
      else if (stamp !== seen) { seen = stamp; changedAt = Date.now(); }
      if (seen !== first && changedAt && Date.now() - changedAt >= settle && Date.now() - loadedAt >= minGap) location.reload();
    } catch { /* server restarting */ }
  };
  setInterval(tick, every);
  tick();
}
