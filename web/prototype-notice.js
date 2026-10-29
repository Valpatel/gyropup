// A session acknowledgement, not a hardware-safety assertion or a legal waiver.
const KEY = 'gyropup.prototype-notice';
const VERSION = '2026-10-29-v1';
const dialog = document.getElementById('prototype-notice-dialog');
const footer = document.getElementById('prototype-notice-footer');
if (dialog && footer && typeof dialog.showModal === 'function') {
  let acknowledged = false, opener = null;
  try { acknowledged = sessionStorage.getItem(KEY) === VERSION; } catch { /* still show the notice when storage is unavailable */ }
  let publishedOpen;
  const publish = () => {
    if (publishedOpen === dialog.open) return;
    publishedOpen = dialog.open;
    document.documentElement.dataset.prototypeNoticeOpen = String(dialog.open);
    document.dispatchEvent(new CustomEvent('gyropup:prototype-notice', { detail: { open: dialog.open } }));
  };
  const open = event => {
    opener = event?.currentTarget ?? document.activeElement;
    if (!dialog.open) dialog.showModal();
    publish();
    dialog.querySelector('.prototype-notice-content').scrollTop = 0;
    document.getElementById('prototype-notice-title').focus({ preventScroll: true });
  };
  const close = () => {
    dialog.close();
    publish();
    if (opener?.isConnected && typeof opener.focus === 'function') opener.focus({ preventScroll: true });
  };
  document.getElementById('prototype-notice-ack').addEventListener('click', () => {
    acknowledged = true;
    try { sessionStorage.setItem(KEY, VERSION); } catch { /* acknowledgement still lasts on this page */ }
    close();
  });
  // Same-origin embedded report pages share this tab's session acknowledgement.
  window.addEventListener('storage', event => {
    if (event.key !== KEY || event.newValue !== VERSION) return;
    try { if (sessionStorage.getItem(KEY) !== VERSION) return; } catch { return; }
    acknowledged = true;
    if (dialog.open) close();
  });
  dialog.addEventListener('cancel', event => {
    // First entry needs an explicit acknowledgement or the visible exit link.
    if (!acknowledged) event.preventDefault();
  });
  dialog.addEventListener('close', () => { publish(); });
  // Native dialog focus can reach browser chrome when reverse-tabbing from the first
  // item. Keep both boundaries inside while preserving native Enter/Space/scrolling.
  dialog.addEventListener('keydown', event => {
    if (event.key !== 'Tab' || event.ctrlKey || event.altKey || event.metaKey) return;
    const items = [...dialog.querySelectorAll('button:not(:disabled),a[href],[tabindex]:not([tabindex="-1"])')]
      .filter(element => element.getClientRects().length && getComputedStyle(element).visibility !== 'hidden');
    const first = items[0], last = items.at(-1), active = document.activeElement;
    if (!first) return;
    if (!items.includes(active) || event.shiftKey && active === first || !event.shiftKey && active === last) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus({ preventScroll: true });
    }
  });
  // Keep simulator shortcuts inert without suppressing native button activation.
  for (const type of ['keydown', 'keyup', 'keypress']) dialog.addEventListener(type, event => event.stopPropagation());
  for (const button of footer.querySelectorAll('[data-prototype-notice-open]')) {
    button.hidden = false; button.addEventListener('click', open);
  }
  // FEA creates its HUD only after loading a case. Watch its structural owners,
  // not all descendants: speech typing and per-frame readouts need no notice work.
  const button = document.createElement('button');
  button.type = 'button'; button.className = 'prototype-notice-reopen';
  button.dataset.prototypeNoticeOpen = ''; button.title = 'Prototype safety notice';
  button.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8"><path d="m12 3 10 18H2L12 3Z" stroke-linejoin="round"/><path d="M12 9v5" stroke-linecap="round"/><circle cx="12" cy="17.5" r=".8" fill="currentColor" stroke="none"/></svg><span class="prototype-notice-sr">Prototype safety notice</span>';
  button.addEventListener('click', open);
  const knownOwners = new Set([document.body]);
  const owners = new MutationObserver(syncOwners);
  function syncOwners() {
    // Rebind after every structural change. Moving our button must not feed the observer.
    owners.disconnect();
    const hud = document.getElementById('hud'), fea = document.getElementById('fea');
    const nav = document.querySelector('.appnav'), topbar = document.getElementById('topbar');
    const fileHost=document.getElementById('file-viewer'), fileNav=fileHost?.querySelector('.file-nav');
    const fullscreen = !!(hud||fileHost) && getComputedStyle(document.body).overflowY === 'hidden';
    const header = nav || topbar || fileNav;
    for (const copy of document.querySelectorAll('button.prototype-notice-reopen')) if (copy !== button) copy.remove();
    document.body.dataset.prototypeFullscreen = String(fullscreen);
    if (fullscreen && header) {
      if (button.parentElement !== header) header.insertBefore(button, nav?.querySelector('.menu-toggle') ?? null);
    } else button.remove();
    // A hidden/unfinished viewer header cannot replace the visible footer notice.
    document.body.dataset.prototypeEnhanced=String(fullscreen&&button.isConnected&&button.getClientRects().length>0);
    // The ancestor chain detects replacement of a nested FEA host, HUD or header.
    // Direct child-list observation excludes changing text and canvas/scene children.
    for (const node of [fea, hud, nav, topbar, fileHost, fileNav]) {
      for (let owner = node; owner && owner !== document.body; owner = owner.parentElement) knownOwners.add(owner);
    }
    // Keep connected mount parents through a retry's temporary empty state.
    for (const target of knownOwners) {
      if (target.isConnected) owners.observe(target, { childList: true });
      else knownOwners.delete(target);
    }
  }
  syncOwners();
  window.addEventListener('resize', syncOwners, { passive: true });
  if (!acknowledged) open(); else publish();
}
