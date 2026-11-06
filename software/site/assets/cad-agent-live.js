// Live facts from cad-agent's own site, under the landing page's "Explore cad-agent" link.
// The section is complete without them: no script, a blocked request, a slow network or an
// unexpected reply all keep the static line already in the HTML, in the same reserved space.
export const SOURCE = 'https://cad-agent.gyropup.com/version.json';
const COMMITS = 'https://github.com/Valpatel/cad-agent/commit/';
const TIMEOUT_MS = 6000;

/** The fields cad-agent's tools/build-site.mjs writes to version.json, checked; null when anything is off. */
export function describe(data) {
  if (!data || typeof data !== 'object') return null;
  const { revision, built, pages, items } = data;
  const when = typeof built === 'string' ? new Date(built) : null;
  if (typeof revision !== 'string' || !/^[0-9a-f]{40}$/.test(revision)) return null;
  if (!when || Number.isNaN(when.getTime())) return null;
  if (![pages, items].every(n => Number.isInteger(n) && n > 0 && n < 1e6)) return null;
  const date = when.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
  return { revision, date, pages, items };
}

function render(line, live) {
  const text = line.querySelector('.loop-live-text');
  const link = document.createElement('a');
  link.href = COMMITS + live.revision;
  link.textContent = live.date;
  link.setAttribute('aria-label', `cad-agent commit ${live.revision.slice(0, 7)}, built ${live.date}`);
  text.replaceChildren(`Live: ${live.items.toLocaleString('en-US')} catalogue entries · ${live.pages.toLocaleString('en-US')} pages · updated `, link);
  line.dataset.state = 'live';
}

export async function showLive(line = document.querySelector('.loop-live'), fetcher = globalThis.fetch) {
  if (!line || typeof fetcher !== 'function') return false;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetcher(SOURCE, { mode: 'cors', credentials: 'omit', referrerPolicy: 'no-referrer', signal: controller.signal });
    if (!response.ok) return false;
    const live = describe(await response.json());
    if (!live) return false;
    render(line, live);
    return true;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

/** Ask only when the section comes near the viewport; the line's space is already reserved. */
export function showLiveWhenNear(section = document.querySelector('#loop')) {
  if (!section || typeof IntersectionObserver !== 'function') return showLive();
  const observer = new IntersectionObserver(entries => {
    if (!entries.some(entry => entry.isIntersecting)) return;
    observer.disconnect();
    showLive();
  }, { rootMargin: '600px 0px' });
  observer.observe(section);
}

if (typeof document !== 'undefined') showLiveWhenNear();
