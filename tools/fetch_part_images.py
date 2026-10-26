"""Fetch a product image for every catalog part, for the designer's cards (internal use only).

    python tools/fetch_part_images.py            # parts without an image yet
    python tools/fetch_part_images.py --force    # all parts

For each part it opens the product pages it already cites (buy links first, then sources), takes the page's main
product image (og:image / twitter:image, else the first large image), and saves a 480 px JPEG thumbnail to
catalog/images/<id>.jpg. catalog/images/index.json maps part id -> {file, from}. Parts with no reachable image are
listed there too, so the designer can show a category icon instead. Images are borrowed from the vendors' pages for
internal use; this repository is private.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

R = Path(__file__).resolve().parents[1]
OUT = R / 'catalog' / 'images'
UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36')
SKIP_HOSTS = ('github.com', 'arxiv.org', 'youtube.com', 'reddit.com', 'wiki.', 'docs.')


def get(url: str, timeout=12) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,image/*,*/*;q=0.8', 'Accept-Language': 'en'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(4_000_000), r.headers.get('Content-Type', '')


def image_urls(page_url: str, html: str) -> list[str]:
    found = []
    if 'amazon.' in page_url:
        # Amazon's og:image is often a site-wide promo; the product photo is in hiRes / data-old-hires
        pats = (r'"hiRes"\s*:\s*"(https://[^"]+)"', r'data-old-hires=["\']([^"\']+)', r'"large"\s*:\s*"(https://m\.media-amazon[^"]+)"')
        for pat in pats:
            for m in re.finditer(pat, html):
                if m.group(1) not in found:
                    found.append(m.group(1))
        return found[:4]
    for pat in (r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image',
                r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
                r'"image"\s*:\s*"(https?://[^"]+\.(?:jpe?g|png|webp)[^"]*)"',
                r'<img[^>]+(?:data-src|src)=["\']([^"\']+\.(?:jpe?g|png|webp)(?:\?[^"\']*)?)["\']'):
        for m in re.finditer(pat, html, re.I):
            u = urllib.parse.urljoin(page_url, m.group(1).replace('&amp;', '&'))
            if not re.search(r'logo|icon|sprite|favicon|placeholder|banner|payment', u, re.I) and u not in found:
                found.append(u)
    return found[:6]


def thumb(data: bytes) -> Image.Image | None:
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return None
    if min(im.size) < 120:
        return None
    im = im.convert('RGBA')
    bg = Image.new('RGBA', im.size, (255, 255, 255, 255))      # product shots on white, like the stores show them
    im = Image.alpha_composite(bg, im).convert('RGB')
    im.thumbnail((480, 480))
    return im


def fetch(item: dict) -> dict:
    pages = [b.get('url') for b in item.get('buy') or []] + list(item.get('sources') or [])
    pages = [p for p in pages if p and p.startswith('http') and not p.lower().endswith('.pdf') and not any(h in p for h in SKIP_HOSTS)]
    for page in pages[:4]:
        try:
            body, ctype = get(page)
        except Exception:
            continue
        if ctype.startswith('image/'):
            im = thumb(body)
            if im:
                return {'image': im, 'from': page}
            continue
        html = body.decode('utf-8', 'replace')
        for u in image_urls(page, html):
            try:
                data, _ = get(u)
            except Exception:
                continue
            im = thumb(data)
            if im:
                return {'image': im, 'from': u}
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    index_path = OUT / 'index.json'
    index = json.loads(index_path.read_text()) if index_path.is_file() else {}
    items = []
    for f in json.loads((R / 'catalog/index.json').read_text())['files']:
        items += json.loads((R / 'catalog' / f).read_text())
    todo = [it for it in items if a.force or it['id'] not in index or not index[it['id']].get('file')]
    print(f'{len(todo)} parts to fetch')
    with cf.ThreadPoolExecutor(12) as ex:
        for it, res in zip(todo, ex.map(fetch, todo)):
            if res:
                path = OUT / f"{it['id']}.jpg"
                res['image'].save(path, 'JPEG', quality=82)
                index[it['id']] = {'file': path.name, 'from': res['from']}
            else:
                index[it['id']] = {'file': None, 'from': None}
    # an image shared by several different products is a site banner or promo, not a product photo
    import hashlib
    by_hash = {}
    for pid, v in index.items():
        if v.get('file'):
            by_hash.setdefault(hashlib.sha1((OUT / v['file']).read_bytes()).hexdigest(), []).append(pid)
    models = {it['id']: it.get('model', '') for it in items}

    def names_part(pid):   # the image's address mentions the part's model number (e.g. "gim6010" or "rs-03")
        url = (index[pid].get('from') or '').lower().replace('-', '').replace('_', '')
        toks = [t for t in re.findall(r'[a-z0-9]+', models.get(pid, '').lower().replace('-', '')) if len(t) >= 4 and re.search(r'\d', t)]
        return any(t in url for t in toks)

    for pids in by_hash.values():
        if len(pids) > 1 and not all(names_part(p) for p in pids):
            for pid in pids:
                (OUT / index[pid]['file']).unlink(missing_ok=True)
                index[pid] = {'file': None, 'from': None, 'rejected': 'same image as other products'}
    index_path.write_text(json.dumps(index, indent=1, sort_keys=True) + '\n')
    have = sum(1 for v in index.values() if v.get('file'))
    print(f'{have}/{len(index)} parts have an image; the rest show a category icon')
    return 0


if __name__ == '__main__':
    sys.exit(main())
