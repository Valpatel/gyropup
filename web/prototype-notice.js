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
  // Let native focus navigation and button activation work, but keep simulator shortcuts inert.
  for (const type of ['keydown', 'keyup', 'keypress']) dialog.addEventListener(type, event => event.stopPropagation());
  for (const button of footer.querySelectorAll('[data-prototype-notice-open]')) {
    button.hidden = false; button.addEventListener('click', open);
  }
  const fullscreen = !!document.getElementById('hud') && getComputedStyle(document.body).overflowY === 'hidden';
  document.body.dataset.prototypeFullscreen = String(fullscreen);
  // Prefer app navigation; standalone viewers use their existing top bar.
  // Move one button if asynchronous navigation arrives later, never duplicate it.
  if (fullscreen) {
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'prototype-notice-reopen';
    button.dataset.prototypeNoticeOpen = ''; button.title = 'Prototype safety notice';
    button.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8"><path d="m12 3 10 18H2L12 3Z" stroke-linejoin="round"/><path d="M12 9v5" stroke-linecap="round"/><circle cx="12" cy="17.5" r=".8" fill="currentColor" stroke="none"/></svg><span class="prototype-notice-sr">Prototype safety notice</span>';
    button.addEventListener('click', open);
    const attachReopen = () => {
      const nav = document.querySelector('.appnav'), header = nav || document.getElementById('topbar');
      if (!header) return false;
      if (button.parentElement !== header) header.insertBefore(button, nav?.querySelector('.menu-toggle') ?? null);
      document.body.dataset.prototypeEnhanced = 'true';
      return !!nav;
    };
    if (!attachReopen()) {
      const observer = new MutationObserver(() => { if (attachReopen()) observer.disconnect(); });
      observer.observe(document.body, { childList: true });
    }
  }
  if (!acknowledged) open(); else publish();
}
