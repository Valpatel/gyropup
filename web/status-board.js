// The status board's motion and its "how long ago" labels (the board itself is static HTML from tools/status-board.mjs).
// Bars fill as the board comes into view; a panel whose records changed in the last three days is marked and pulses.
// Without this script, or with reduced motion, the board is drawn complete and still.
const DAY = 864e5;
export function ago(iso, now = Date.now()) {
  const days = Math.floor((now - Date.parse(iso)) / DAY);
  if (!Number.isFinite(days) || days < 0) return null;
  return { days, text: days === 0 ? 'today' : days === 1 ? 'yesterday' : `${days} days ago` };
}

function mount(board) {
  for (const when of board.querySelectorAll('.sb-when[data-changed]')) {
    const age = when.dataset.changed && ago(when.dataset.changed);
    if (!age) continue;
    when.querySelector('.sb-ago').textContent = ` (${age.text})`;
    when.classList.toggle('is-recent', age.days < 3);
  }
  if (matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) return;
  const parts = [...board.querySelectorAll('.sb-strip, .sb-panel')];
  for (const part of parts) part.querySelectorAll('.sb-bar i, .sb-fill').forEach((bar, j) => bar.style.setProperty('--d', String(200 + j * 70)));
  const observer = new IntersectionObserver(entries => {
    for (const e of entries) if (e.isIntersecting) { e.target.classList.add('is-in'); observer.unobserve(e.target); }
  }, { rootMargin: '0px 0px -8% 0px' });
  board.classList.add('sb-armed');
  parts.forEach(part => observer.observe(part));
  addEventListener('beforeprint', () => parts.forEach(part => part.classList.add('is-in')), { once: true });
}

if (typeof document !== 'undefined') document.querySelectorAll('.status-board').forEach(mount);
