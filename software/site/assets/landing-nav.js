// The landing page's menu. It behaves exactly like the app pages' top bar (designer/kit/appnav.js): the same "Menu"
// button at the top right on phones opens the same links; Escape closes it and returns focus, and choosing a link
// closes it. The CSS lays the phone header out before this runs, so nothing moves when it loads; with scripting off,
// `@media (scripting: none)` hides the button and shows the links.
const nav = document.querySelector('.landing-nav');
const menu = nav?.querySelector('.menu-toggle');
if (nav && menu) {
  const setMenu = (open) => { nav.classList.toggle('menu-open', open); menu.setAttribute('aria-expanded', String(open)); };
  menu.addEventListener('click', () => setMenu(!nav.classList.contains('menu-open')));
  nav.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && nav.classList.contains('menu-open')) { setMenu(false); menu.focus(); }
  });
  nav.querySelectorAll('a').forEach((a) => a.addEventListener('click', () => setMenu(false)));
  nav.classList.add('has-menu'); // ready: tests wait for this before using the button
}
