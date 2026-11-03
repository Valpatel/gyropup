// The site's theme: the reader's system setting (prefers-color-scheme, web/theme.css) until they press a theme button
// (.theme-toggle, in the page header or the app bar). The choice is kept in this browser's localStorage only, and
// nothing is sent anywhere. A choice that matches the system again is forgotten, so the page follows the system again.
// A classic script in <head>, before the stylesheets, so the first paint already has the chosen theme.
// Scenes and diagrams that draw their own colours listen for `gyropup:themechange` on document; a press changes no
// media query they could watch.
(() => {
  const KEY = 'gyropup-theme', root = document.documentElement, system = matchMedia('(prefers-color-scheme: dark)');
  const load = () => { try { return localStorage.getItem(KEY); } catch { return null; } };
  const save = value => { try { value ? localStorage.setItem(KEY, value) : localStorage.removeItem(KEY); } catch { /* storage off: this page only */ } };
  const apply = value => { if (value === 'light' || value === 'dark') root.dataset.theme = value; else delete root.dataset.theme; };
  apply(load());
  const current = () => root.dataset.theme || (system.matches ? 'dark' : 'light');
  const sync = () => {
    const dark = current() === 'dark';
    for (const button of document.querySelectorAll('.theme-toggle')) {
      button.hidden = false;
      button.setAttribute('aria-pressed', String(dark));
      button.title = dark ? 'Use the light theme' : 'Use the dark theme';
    }
  };
  const tell = () => document.dispatchEvent(new CustomEvent('gyropup:themechange', { detail: { theme: current() } }));
  const press = () => {
    const next = current() === 'dark' ? 'light' : 'dark';
    if (next === (system.matches ? 'dark' : 'light')) { delete root.dataset.theme; save(null); }
    else { root.dataset.theme = next; save(next); }
    sync(); tell();
  };
  system.addEventListener?.('change', () => { sync(); if (!root.dataset.theme) tell(); });
  // a choice made in another tab, or kept while this page sat in the back/forward cache
  const reload = () => { const before = current(); apply(load()); sync(); if (current() !== before) tell(); };
  addEventListener('storage', e => { if (e.key === KEY || e.key === null) reload(); });
  addEventListener('pageshow', e => { if (e.persisted) reload(); });
  // Buttons can arrive later (the app bar is drawn by a module), so one listener serves them all.
  document.addEventListener('click', e => { if (e.target.closest?.('.theme-toggle')) press(); });
  window.gyropupTheme = Object.freeze({ current, sync });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', sync); else sync();
})();
