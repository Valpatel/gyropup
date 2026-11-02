// "What changed": each change slides in as it comes into view. The timeline is static HTML (tools/timeline.mjs);
// without this script, or with reduced motion, every change is simply there.
function mount(timeline) {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) return;
  const events = [...timeline.querySelectorAll('.tl-event')];
  const observer = new IntersectionObserver(entries => {
    for (const e of entries) if (e.isIntersecting) { e.target.classList.add('is-in'); observer.unobserve(e.target); }
  }, { rootMargin: '0px 0px -6% 0px' });
  timeline.classList.add('tl-armed');
  events.forEach(event => observer.observe(event));
  addEventListener('beforeprint', () => events.forEach(event => event.classList.add('is-in')), { once: true });
}
document.querySelectorAll('.timeline').forEach(mount);
