/** Cache migration for a static site, without bundling or rewriting module source. */
import { createHash } from 'node:crypto';
import { readdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { parseHTML } from 'linkedom';

export const SITE_CACHE_CONTROL = 'public, no-cache, max-age=0, must-revalidate';
const origin = 'https://gyropup.invalid';
async function filesIn(root, dir = '') {
  const files = [];
  for (const entry of await readdir(path.join(root, dir), { withFileTypes: true })) {
    const file = path.posix.join(dir, entry.name);
    if (entry.isDirectory()) files.push(...await filesIn(root, file));
    else if (entry.isFile()) files.push(file);
  }
  return files.sort();
}

export async function versionSiteAssets(root) {
  const files = (await filesIn(root)).filter(f => !['_headers', 'version.json'].includes(f));
  // Hash actual build bytes: editing locally must work even before a new commit.
  const hash = createHash('sha256');
  for (const file of files) hash.update(file).update('\0').update(await readFile(path.join(root, file))).update('\0');
  const key = hash.digest('hex').slice(0, 20);
  const modules = files.filter(f => /\.(?:m?js)$/.test(f));
  const version = (value, file) => {
    if (!value || /^(?:[a-z][a-z\d+.-]*:|\/\/|#)/i.test(value)) return value;
    const url = new URL(value, `${origin}/${file}`);
    if (!files.includes(url.pathname.slice(1))) return value;
    url.searchParams.set('v', key);
    return url.pathname + url.search + url.hash;
  };
  for (const file of files.filter(f => f.endsWith('.html'))) {
    const { document } = parseHTML(await readFile(path.join(root, file), 'utf8'));
    const imports = Object.fromEntries(modules.map(f => ['/' + f, version('/' + f, file)]));
    for (const old of document.querySelectorAll('script[type="importmap"]')) {
      const map = JSON.parse(old.textContent);
      if (map.scopes || map.integrity) throw new Error(`Unsupported scoped/integrity import map: ${file}`);
      for (const [name, target] of Object.entries(map.imports || {})) {
        imports[name] = version(target, file);
        // Prefix targets cannot contain a query; retain the alias and add exact
        // entries for its shipped modules (e.g. three/addons/controls/…).
        if (name.endsWith('/') && typeof target === 'string' && target.endsWith('/')) {
          const base = new URL(target, `${origin}/${file}`);
          if (base.origin === origin) for (const module of modules) {
            if (('/' + module).startsWith(base.pathname)) {
              imports[name + ('/' + module).slice(base.pathname.length)] = version('/' + module, file);
            }
          }
        }
      }
      old.remove();
    }
    const map = document.createElement('script');
    map.type = 'importmap';
    map.textContent = JSON.stringify({ imports }).replace(/</g, '\\u003c');
    // An import map must precede even inline modules in generated notebook pages.
    const firstModule = document.head.querySelector('script[type="module"]');
    if (firstModule) firstModule.before(map);
    else document.head.append(map);
    for (const element of document.querySelectorAll('link[rel="stylesheet"], link[rel="modulepreload"]')) {
      element.setAttribute('href', version(element.getAttribute('href'), file));
    }
    for (const element of document.querySelectorAll('script[src], img[src], source[src], video[src]')) {
      element.setAttribute('src', version(element.getAttribute('src'), file));
    }
    for (const element of document.querySelectorAll('[poster]')) element.setAttribute('poster', version(element.getAttribute('poster'), file));
    await writeFile(path.join(root, file), document.toString());
  }
  // Relative imports do not inherit the parent's query. Include font and nested
  // stylesheet URLs as well as the HTML's first stylesheet.
  for (const file of files.filter(f => f.endsWith('.css'))) {
    const css = await readFile(path.join(root, file), 'utf8');
    await writeFile(path.join(root, file), css.replace(/url\(\s*(['"]?)([^)'"\s]+)\1\s*\)/g,
      (match, quote, url) => `url(${quote}${version(url, file)}${quote})`));
  }
  return key;
}
