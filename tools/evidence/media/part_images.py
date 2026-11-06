#!/usr/bin/env python3
"""A picture of every part on the parts lists: the bought parts' product photos and renders of our printed parts, so
each line can be checked against what arrives and ordered again from somewhere else (catalog/alternates.json).

    .venv/bin/python tools/part_images.py                    # every part the BOMs use; skips what is already here
    .venv/bin/python tools/part_images.py --only bearing_6201 hip_frame
    .venv/bin/python tools/part_images.py --force --only robstride-rs-04
    .venv/bin/python tools/part_images.py --list             # offline: each BOM line, its picture and alternates
    .venv/bin/python tools/part_images.py --renders          # only the printed parts (no web)

Which parts: the leg's bought list (exports/leg/bom.json and cad/build_leg.py BOUGHT), the leg rig's (exports/rig/bom.json,
its print plans exports/rig/ and exports/rig/bench/), the turret's (cad/build_turret.py
TURRET_BOUGHT and BENCH_BOUGHT, and cad/turret.py bought_parts, read from the turret worktree ../gyropup-turret when
it is there: --turret), and the printed parts of both (their print plans, and cad/turret.py MADE; each rendered from
the newest STL of it in either checkout).
A line that names its part in words ("KCD1 rocker switch, 16 A") gets its key from catalog/sourcing.json, which also
holds the parts no catalogue file has yet.

Where the pictures come from:
  McMaster-Carr    the product photo on the part's product page (Chrome through Playwright, one page at a time with a
                   pause, as tools/mcmaster_cad.py reads them; no login, no CAD); the page's delivery line is kept too
  other vendors    the seller's product page (catalogue buy link, or sourcing.json image_pages): og:image, else the
                   largest product photo; read with a plain request, or in Chrome when the site wants a browser (a
                   site that answers with a bot check is not pushed: name another page in image_pages); a photo
                   picked by hand when og:image shows something else (sourcing.json image_urls)
  printed parts    a render of our print-ready STL (pyvista), exports/thumbs/<part>.png, redrawn when the STL changes

Bought parts' pictures go in references/vendor/thumbs/<key>.jpg, which is gitignored (the vendors' photos are not
ours to redistribute); catalog/images.json records each picture: {source_url, image_url, fetched, path, kind, ...}.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import datetime as dt
import html
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

R = Path(__file__).resolve().parents[1]
CAT = R / 'catalog'
IMAGES = CAT / 'images.json'
ALTERNATES = CAT / 'alternates.json'
SOURCING = CAT / 'sourcing.json'
VENDOR_THUMBS = R / 'references' / 'vendor' / 'thumbs'
RENDERS = R / 'exports' / 'thumbs'
TURRET_DEFAULT = R.parent / 'gyropup-turret'
THUMB_PX = 360
UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36')
COLOURS = {'pa6-cf': '#5d6570', 'petg': '#4f86c6', 'tpu95': '#33373d', 'al6061': '#b9c0c8'}      # render colour by material


def today() -> str:
    return dt.date.today().isoformat()


def load(path: Path, default):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default


def rel(p: Path) -> str:
    """A path for the records: relative to this checkout, or to the folder of checkouts for the turret worktree."""
    p = Path(p).resolve()
    for base in (R, R.parent):
        with contextlib.suppress(ValueError):
            return str(p.relative_to(base))
    return str(p)


# ------------------------------------------------------------------------------------------- what the BOMs use

def literal(path: Path, name: str):
    """A top-level ``NAME = <literal>`` from a Python file, without importing it (the builders need CadQuery)."""
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(f'{name} not in {path}')


def catalogue() -> dict:
    """Every catalogue item by key and by id (catalog/index.json's files and hardware.json), and the parts
    catalog/sourcing.json holds that no catalogue file has yet."""
    items = {}
    files = load(CAT / 'index.json', {}).get('files', [])
    for f in dict.fromkeys(['hardware.json', *files, 'rig.json']):           # rig.json: the leg's test rig (its own file)
        for it in load(CAT / f, []):
            for k in (it.get('id'), it.get('key')):
                if k:
                    items.setdefault(k, it)
    for it in load(SOURCING, {}).get('parts', []):
        for k in (it.get('id'), it.get('key')):
            if k:
                items.setdefault(k, {**it, 'pending': True})
    return items


def resolve(text, sourcing: dict, items: dict):
    """The catalogue key(s) a BOM line's text or name means: [key, ...] (several when one line buys several
    products), [] when the text is a part of another line (sourcing 'skip'), None when nothing says."""
    if text in (sourcing.get('skip') or []):
        return []
    if text in items:
        return [text]
    k = (sourcing.get('names') or {}).get(text)
    if k is None:
        return None
    return k if isinstance(k, list) else [k]


def turret_dir(arg) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    return TURRET_DEFAULT if (TURRET_DEFAULT / 'cad' / 'build_turret.py').exists() else R


def bom_lines(tdir: Path) -> list:
    """Every bought line of the leg and the turret: {bom, text, for, keys}. keys None = no key found."""
    items, sourcing = catalogue(), load(SOURCING, {})
    out, seen = [], set()

    def add(bom, text, for_, keys):
        sig = (bom, text, for_)
        if sig not in seen:
            seen.add(sig)
            out.append({'bom': bom, 'text': text, 'for': for_, 'keys': keys})

    # the leg: what the last build wrote, and what cad/build_leg.py lists now (it may have changed since)
    for r in load(R / 'exports' / 'leg' / 'bom.json', {}).get('per_leg', []):
        add('leg', r['key'], r.get('for'), [r['key']])
    with contextlib.suppress(Exception):
        for key, _qty, why in literal(R / 'cad' / 'build_leg.py', 'BOUGHT'):
            if not any(o['bom'] == 'leg' and o['text'] == key for o in out):
                add('leg', key, why, [key])
    # the leg's test rig and its bench (tools/rig_orders.py writes exports/rig/bom.json)
    for lst, rows in load(R / 'exports' / 'rig' / 'bom.json', {}).items():
        if isinstance(rows, list) and lst != 'made_to_order':
            for r in rows:
                add('rig', r['key'], r.get('for'), [r['key']])
    # the turret on its bench stand
    bt = tdir / 'cad' / 'build_turret.py'
    if bt.exists():
        for name, (src, _qty) in literal(bt, 'TURRET_BOUGHT').items():
            k = resolve(src, sourcing, items)
            add('turret', src, name, k if k is not None else resolve(name, sourcing, items))
        for src, _qty in literal(bt, 'BENCH_BOUGHT'):
            add('turret', src, 'bench stand', resolve(src, sourcing, items))
    # bought parts cad/turret.py draws that the bench list leaves out
    tu = tdir / 'cad' / 'turret.py'
    if tu.exists():
        listed = {o['for'] for o in out if o['bom'] == 'turret'}
        body = tu.read_text().split('def bought_parts', 1)[-1].split('\ndef ', 1)[0]
        for name in dict.fromkeys(re.findall(r"out\['(\w+)'\]", body)):
            if name not in listed:
                k = resolve(name, sourcing, items)
                if k != []:
                    add('turret (drawn, not on its list)', name, name, k)
    return out


def printed_parts(tdir: Path) -> dict:
    """{part: {stl, material, bom}} for the leg's and the turret's made parts that have an STL: printed, and the leg's
    parts machined to order (exports/leg/cnc/cnc.json)."""
    out = {}
    leg = load(R / 'exports' / 'leg' / 'print-plan.json', {}).get('parts', {})
    for name, p in leg.items():
        if (R / 'exports' / 'leg' / f'{name}.stl').exists():
            out[name] = {'stl': R / 'exports' / 'leg' / f'{name}.stl', 'material': p.get('material'), 'bom': 'leg'}
    for name, c in load(R / 'exports' / 'leg' / 'cnc' / 'cnc.json', {}).items():
        if (R / c['stl']).exists():
            out[name] = {'stl': R / c['stl'], 'material': 'al6061', 'bom': 'leg'}
    for d in (R / 'exports' / 'rig', R / 'exports' / 'rig' / 'bench'):           # the rig's printed parts and bench fixtures
        for name, p in load(d / 'print-plan.json', {}).get('parts', {}).items():
            if (d / f'{name}.stl').exists() and name not in out:
                out[name] = {'stl': d / f'{name}.stl', 'material': p.get('material'), 'bom': 'rig'}
    plans = [tdir / 'exports' / 'turret' / 'bench' / 'print-plan.json', R / 'exports' / 'turret' / 'bench' / 'print-plan.json']
    tplan = next((load(p, {}) for p in plans if p.exists()), {}).get('parts', {})
    made = {}
    tu = tdir / 'cad' / 'turret.py'
    if tu.exists():                                     # MADE: (name, fn, frame, material, qty, rotation, note)
        for name, mat in re.findall(r"^\s*\('(\w+)',\s*\w+,\s*'\w+',\s*'([\w-]+)',\s*\d+,", tu.read_text(), re.M):
            made[name] = mat
    for name in dict.fromkeys([*tplan, *made]):
        mat = (tplan.get(name) or {}).get('material') or made.get(name)
        stls = [d / f'{name}.stl' for d in (tdir / 'exports' / 'turret', tdir / 'exports' / 'turret' / 'bench',
                                            R / 'exports' / 'turret', R / 'exports' / 'turret' / 'bench')]
        stls = [s for s in stls if s.exists()]
        if stls:                                        # the newest build of the part, from either checkout
            out[name] = {'stl': max(stls, key=lambda s: s.stat().st_mtime), 'material': mat, 'bom': 'turret'}
    return out


# ------------------------------------------------------------------------------------------- saving pictures

def save_thumb(data: bytes, key: str, crop=None) -> Path:
    """Shrink a downloaded picture to a thumbnail, flattened on white, and keep it as
    references/vendor/thumbs/<key>.jpg (a few tens of kB, whatever the source's format). ``crop``: (x0, y0, x1, y1)
    as fractions of the picture, for a banner whose part is a small piece of it."""
    from PIL import Image
    im = Image.open(io.BytesIO(data))
    with contextlib.suppress(EOFError):
        im.seek(0)                                      # an animation: its first frame
    if crop:
        w, h = im.size
        im = im.crop((round(crop[0] * w), round(crop[1] * h), round(crop[2] * w), round(crop[3] * h)))
    im = im.convert('RGBA')
    im = Image.alpha_composite(Image.new('RGBA', im.size, (255, 255, 255, 255)), im).convert('RGB')
    im.thumbnail((THUMB_PX, THUMB_PX), Image.LANCZOS)
    VENDOR_THUMBS.mkdir(parents=True, exist_ok=True)
    for old in VENDOR_THUMBS.glob(f'{key}.*'):
        old.unlink()
    out = VENDOR_THUMBS / f'{key}.jpg'
    im.save(out, quality=88, optimize=True)
    return out


def http_get(url: str, referer: str | None = None, timeout: float = 30.0):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9',
                                               **({'Referer': referer} if referer else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.geturl(), r.read(), r.headers.get('Content-Type', '')


META_IMG = re.compile(r'<meta\b[^>]*>', re.I)
# og:image that is the site's logo or share card, not the part: look for the product photo instead
GENERIC_IMG = re.compile(r'logo|placeholder|default[-_.]|social|share[-_]|/og/|og[-_]image|banner[-_]default', re.I)


def og_image(page_html: str, base: str):
    """og:image (or twitter:image) of a page, absolute; None when it has none."""
    for tag in META_IMG.findall(page_html):
        attrs = dict((a.lower(), html.unescape(v)) for a, _, v in re.findall(r'(\w[\w:-]*)\s*=\s*(["\'])(.*?)\2', tag))
        name = (attrs.get('property') or attrs.get('name') or '').lower()
        if name in ('og:image', 'og:image:secure_url', 'twitter:image') and attrs.get('content') \
                and not GENERIC_IMG.search(attrs['content']):
            return urllib.parse.urljoin(base, attrs['content'].strip())
    return None


PAGE_IMG_JS = """() => {
  const meta = (n) => { const m = document.querySelector(`meta[property="${n}"], meta[name="${n}"]`); return m ? m.content : null; };
  const og = meta('og:image') || meta('og:image:secure_url') || meta('twitter:image');
  const imgs = [...document.querySelectorAll('img')].map((i) => ({src: i.currentSrc || i.src, a: i.naturalWidth * i.naturalHeight,
      vis: i.getBoundingClientRect().width * i.getBoundingClientRect().height}))
    .filter((i) => i.src && !/logo|icon|sprite|badge|flag|avatar/i.test(i.src) && i.vis > 2500);
  imgs.sort((x, y) => y.vis - x.vis);
  return {og, biggest: imgs.length ? imgs[0].src : null, title: document.title};
}"""

MC_JS = """() => {
  const imgs = [...document.querySelectorAll('img')];
  const prod = imgs.filter((i) => /^Image of Product/i.test(i.alt || ''));
  const pick = prod.find((i) => /Front orientation/i.test(i.alt)) || prod[0]
            || imgs.find((i) => /printProductImage/.test(i.className || ''));
  const leaf = [...document.querySelectorAll('div, span, p')].filter((e) => e.childElementCount === 0)
    .map((e) => e.textContent.trim()).filter((t) => t && t.length < 100);
  const delivery = leaf.find((t) => /^(Delivers|Ships|Usually ships|Not available|Discontinued|No longer available)/i.test(t)) || null;
  return {image: pick ? (pick.currentSrc || pick.src) : null, alt: pick ? pick.alt : null, delivery, title: document.title};
}"""


class Browser:
    """System Chrome through Playwright, one tab, started only when a page needs it: the session tools/mcmaster_cad.py
    uses (cadagent.mcmaster.Session), with a pause of at least ``delay`` seconds between pages."""

    def __init__(self, stack: contextlib.ExitStack, delay: float):
        self.stack, self.delay, self.s, self.last = stack, delay, None, 0.0

    def page(self):
        if self.s is None:
            from cadagent import mcmaster as mc
            self.s = self.stack.enter_context(mc.Session(delay_s=self.delay, timeout_s=45))
        wait = self.delay - (time.monotonic() - self.last)
        if self.last and wait > 0:
            time.sleep(wait)
        self.last = time.monotonic()
        return self.s.page

    def mcmaster(self, pn: str) -> dict:
        from cadagent import mcmaster as mc
        url = mc.product_url(mc.validate_pn(pn))            # product pages only
        for attempt in (1, 2):
            pg = self.page()
            pg.goto(url, wait_until='domcontentloaded')
            try:
                pg.wait_for_selector('img[alt^="Image of Product"]', timeout=30000)
                pg.wait_for_timeout(1200)
                break
            except Exception:
                if attempt == 2:
                    raise RuntimeError(f'{pn}: no product picture on {pg.url}')
                time.sleep(15)                              # a slow page: wait, then once more
        d = pg.evaluate(MC_JS)
        if not d.get('image'):
            raise RuntimeError(f'{pn}: no product picture on {pg.url}')
        r = pg.context.request.get(d['image'], headers={'Referer': pg.url})
        if not r.ok:
            raise RuntimeError(f'{pn}: picture {d["image"]} gave HTTP {r.status}')
        return {**d, 'url': url, 'data': r.body()}

    def vendor(self, url: str) -> dict:
        pg = self.page()
        pg.goto(url, wait_until='domcontentloaded')
        pg.wait_for_timeout(4000)
        d = pg.evaluate(PAGE_IMG_JS)
        img = (d.get('og') if d.get('og') and not GENERIC_IMG.search(d['og']) else None) or d.get('biggest')
        if not img:
            raise RuntimeError(f'no product picture found on {pg.url} ({d.get("title")!r})')
        img = urllib.parse.urljoin(pg.url, img)
        r = pg.context.request.get(img, headers={'Referer': pg.url})
        if not r.ok:
            raise RuntimeError(f'picture {img} gave HTTP {r.status}')
        return {'image': img, 'data': r.body(), 'final_url': pg.url}


def vendor_page(key: str, items: dict, sourcing: dict):
    """(page url, seller) where a vendor part's picture is taken from."""
    page = (sourcing.get('image_pages') or {}).get(key)
    it = items.get(key) or {}
    buy = it.get('buy') or []
    if page:
        return page, next((b.get('seller') for b in buy if b.get('url') == page), None) or urllib.parse.urlparse(page).netloc
    if buy:
        return buy[0]['url'], buy[0].get('seller')
    src = it.get('sources') or []
    return (src[0], urllib.parse.urlparse(src[0]).netloc) if src else (None, None)


def fetch_bought(key: str, items: dict, sourcing: dict, browser: Browser) -> dict:
    """Fetch one bought part's picture. Returns its images.json record."""
    it = items.get(key)
    if it is None:
        raise RuntimeError('not in any catalogue file or catalog/sourcing.json')
    if it.get('vendor') == 'McMaster-Carr':
        d = browser.mcmaster(it['model'])
        path = save_thumb(d['data'], key)
        return {'source_url': d['url'], 'image_url': d['image'], 'fetched': today(), 'path': rel(path), 'kind': 'mcmaster',
                'seller': 'McMaster-Carr', 'part_number': it['model'],
                'availability': d.get('delivery')}          # McMaster's delivery line on the day it was read ('fetched')
    page, seller = vendor_page(key, items, sourcing)
    if not page:
        raise RuntimeError('no product page to take a picture from')
    chosen = (sourcing.get('image_urls') or {}).get(key)  # a photo picked by hand: url, or {url, crop}
    crop = chosen.get('crop') if isinstance(chosen, dict) else None
    img, final, how = (chosen.get('url') if isinstance(chosen, dict) else chosen), page, 'request'
    try:                                                    # a plain request first: most shops serve og:image
        if img:
            how = 'chosen'
        else:
            final, body, ctype = http_get(page)
            if 'html' in ctype or body[:200].lstrip().startswith(b'<'):
                img = og_image(body.decode('utf-8', 'replace'), final)
        data = http_get(img, referer=final)[1] if img else None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        data = None
    if data is None:                                        # blocked or no og:image: the page in Chrome
        d = browser.vendor(page)
        img, data, final, how = d['image'], d['data'], d['final_url'], 'chrome'
    path = save_thumb(data, key, crop)
    return {'source_url': page, 'image_url': img, 'fetched': today(), 'path': rel(path), 'kind': 'vendor',
            'seller': seller, 'part_number': it.get('model'), 'read_with': how, **({'crop': crop} if crop else {})}


def stale(key: str, rec: dict, items: dict, sourcing: dict) -> bool:
    """A picture of another part than the catalogue now names: the part number, the product page or the hand-picked
    photo changed since it was fetched."""
    it = items.get(key) or {}
    if rec.get('kind') == 'mcmaster':
        return rec.get('part_number') != it.get('model')
    if rec.get('kind') == 'vendor':
        chosen = (sourcing.get('image_urls') or {}).get(key)
        chosen = chosen.get('url') if isinstance(chosen, dict) else chosen
        return rec.get('source_url') != vendor_page(key, items, sourcing)[0] or bool(chosen and chosen != rec.get('image_url'))
    return False


# ------------------------------------------------------------------------------------------- renders

def render(stl: Path, out: Path, colour: str, size: int = THUMB_PX) -> None:
    """A square thumbnail of one printed part: iso view, parallel projection, crease lines, on white."""
    import numpy as np
    import pyvista as pv
    from PIL import Image
    raw = pv.read(str(stl)).clean()
    edges = raw.extract_feature_edges(feature_angle=35, boundary_edges=False, non_manifold_edges=False, manifold_edges=False)
    m = raw.compute_normals(split_vertices=True, feature_angle=35)
    p = pv.Plotter(off_screen=True, window_size=(size * 2, size * 2), lighting='three lights')
    p.set_background('white')
    p.add_mesh(m, color=colour, smooth_shading=True, specular=0.3, specular_power=18, ambient=0.3, diffuse=0.8)
    if edges.n_points:
        p.add_mesh(edges, color='#1c1f24', line_width=1.4)
    p.enable_parallel_projection()
    b, c = m.bounds, np.array(m.center)
    d = np.array([1.0, -1.25, 0.9])
    d /= np.linalg.norm(d)
    span = max(b[1] - b[0], b[3] - b[2], b[5] - b[4])
    p.camera_position = [tuple(c + d * span * 4), tuple(c), (0, 0, 1)]
    p.reset_camera()
    p.camera.zoom(1.05)
    p.enable_anti_aliasing('ssaa')
    img = p.screenshot(return_img=True)
    p.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).convert('RGB').resize((size, size), Image.LANCZOS).save(out, optimize=True)


# ------------------------------------------------------------------------------------------- report

def report(lines: list, printed: dict, images: dict, alternates: dict) -> list:
    """Print each BOM line with its picture and alternates; return the gaps."""
    gaps = []
    print(f"{'bom':34} {'part':38} {'picture':9} alternates")
    for ln in lines:
        keys = ln['keys']
        if keys is None:
            print(f"{ln['bom']:34} {ln['text'][:38]:38} {'NO KEY':9} -")
            gaps.append(f"{ln['bom']}: no catalogue key for {ln['text']!r} (add it to catalog/sourcing.json names)")
            continue
        for k in keys:
            rec = images.get(k)
            pic = rec and (R / rec['path']).exists()
            n = len(alternates.get(k) or [])
            print(f"{ln['bom']:34} {k[:38]:38} {('yes' if pic else 'MISSING'):9} {n if n else 'NONE'}")
            if not pic:
                gaps.append(f'{k}: no picture')
            if not n:
                gaps.append(f'{k}: no alternate')
    missing = [n for n in printed if not (images.get(n) and (R / images[n]['path']).exists())]
    print(f'printed parts: {len(printed) - len(missing)} of {len(printed)} rendered' + (f"; missing {', '.join(missing)}" if missing else ''))
    gaps += [f'{n}: no render' for n in missing]
    return list(dict.fromkeys(gaps))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', nargs='+', metavar='KEY', help='just these catalogue keys or printed part names')
    ap.add_argument('--force', action='store_true', help='fetch or render again even when the picture is here')
    ap.add_argument('--list', action='store_true', help='offline: each BOM line, its picture and alternates, then stop')
    ap.add_argument('--renders', action='store_true', help='only the printed parts (no web)')
    ap.add_argument('--check', action='store_true', help='exit 1 when a BOM line has no picture or no alternate')
    ap.add_argument('--turret', metavar='DIR', help=f'the turret checkout (default {TURRET_DEFAULT} when there)')
    ap.add_argument('--delay', type=float, default=6.0, help='seconds between pages in Chrome (default 6)')
    a = ap.parse_args(argv)
    tdir = turret_dir(a.turret)
    lines, printed = bom_lines(tdir), printed_parts(tdir)
    images = load(IMAGES, {})
    if not a.list:
        items, sourcing = catalogue(), load(SOURCING, {})
        bought = list(dict.fromkeys(k for ln in lines for k in (ln['keys'] or [])))
        want = set(a.only or [])
        rc = 0

        def keep(key, rec):
            images[key] = rec
            IMAGES.write_text(json.dumps(dict(sorted(images.items())), indent=1, ensure_ascii=False) + '\n')

        for name, p in printed.items():                                  # renders: offline, quick
            if want and name not in want:
                continue
            out = RENDERS / f'{name}.png'
            if not a.force and out.exists() and out.stat().st_mtime >= p['stl'].stat().st_mtime and name in images:
                continue
            render(p['stl'], out, COLOURS.get(p['material'], '#8a929c'))
            keep(name, {'source_url': rel(p['stl']), 'image_url': None, 'fetched': today(), 'path': rel(out),
                        'kind': 'render', 'material': p['material'], 'bom': p['bom']})
            print(f'{name}: rendered {rel(out)}')
        if not a.renders:
            with contextlib.ExitStack() as stack:
                browser = Browser(stack, a.delay)
                for key in bought:
                    if want and key not in want:
                        continue
                    rec = images.get(key)
                    if not a.force and rec and (R / rec['path']).exists() and not stale(key, rec, items, sourcing):
                        continue
                    try:
                        rec = fetch_bought(key, items, sourcing, browser)
                    except Exception as exc:                              # one bad page does not stop the others
                        print(f'{key}: FAILED {str(exc).splitlines()[0] if str(exc) else exc!r}', file=sys.stderr)
                        rc = 1
                        continue
                    keep(key, rec)
                    print(f"{key}: {rec['path']} <- {rec['image_url']}" + (f" | {rec['availability']}" if rec.get('availability') else ''))
        if rc and not a.check:
            print('some pictures failed: run again to retry them (what is here is kept)', file=sys.stderr)
    gaps = report(lines, printed, images, load(ALTERNATES, {}))
    if gaps:
        print('\ngaps:', *[f'  {g}' for g in gaps], sep='\n')
    return 1 if a.check and gaps else 0


if __name__ == '__main__':
    sys.exit(main())
