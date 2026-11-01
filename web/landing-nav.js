// The landing page's menu. It behaves like the app pages' top bar (designer/kit/appnav.js): the same "Menu" button at
// the top right on phones, opening the same links, so that control is the same on every page of the site.
// Without script the button stays hidden and the links stay visible, wrapping if they must.
const nav = document.querySelector('.landing-nav');
const menu = nav?.querySelector('.menu-toggle');
if (nav && menu) {
  const setMenu = (open) => { nav.classList.toggle('menu-open', open); menu.setAttribute('aria-expanded', String(open)); };
  menu.hidden = false;
  nav.classList.add('has-menu');
  menu.addEventListener('click', () => setMenu(!nav.classList.contains('menu-open')));
  nav.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && nav.classList.contains('menu-open')) { setMenu(false); menu.focus(); }
  });
  nav.querySelectorAll('a').forEach((a) => a.addEventListener('click', () => setMenu(false)));
  document.addEventListener('click', (e) => { if (!nav.contains(e.target)) setMenu(false); });
}
