/** One static bundle for local development and Cloudflare Pages. No CAD runtime required. */
import { readFile, writeFile, mkdir, cp, rm, stat } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { marked } from 'marked';
import YAML from 'yaml';
const root = path.resolve(import.meta.dirname, '..');
const out = path.join(root, 'dist');
const read = (p) => readFile(path.join(root, p), 'utf8');
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const config = YAML.parse(await read('cad-agent.yaml')).cad.site;
await rm(out, { recursive: true, force: true });
await mkdir(out, { recursive: true });
// Only repository assets, never local credentials, untracked runs or vendor downloads.
// New web source is copied explicitly; all evidence and downloadable files must be committed.
const tracked = execFileSync('git', ['ls-files', '-z'], { cwd: root }).toString().split('\0').filter(Boolean);
const roots = ['designer/', 'exports/', 'catalog/', 'designs/', 'docs/', 'research/', 'cad/', 'sim/', 'hardware/', 'firmware/'];
for (const file of tracked) {
  if (!roots.some(r => file.startsWith(r)) || file === 'docs/handoff.md' || /(?:^|\/)(?:AGENTS|CLAUDE)\.md$/.test(file)) continue;
  const dest = path.join(out, file); await mkdir(path.dirname(dest), { recursive: true });
  if ((await stat(path.join(root, file))).size > 25 * 1024 * 1024) throw new Error(`Cloudflare file limit: ${file}`);
  await cp(path.join(root, file), dest);
}
for (const file of ['index.html', 'LICENSE', 'README.md']) await cp(path.join(root, file), path.join(out, file));
await cp(path.join(root, 'web'), path.join(out, 'web'), { recursive: true });
await mkdir(path.join(out, 'site/pages'), { recursive: true });
const nav = [
  {id:'home', title:'Home', href:''}, {id:'simulate',title:'Play',href:'designer/sim.html'},
  {id:'progress',title:'Progress',href:'designer/progress.html'}, {id:'build',title:'Build',href:'designer/build.html'},
  {id:'docs',title:'Design notes',href:'site/'}, {id:'repo',title:'GitHub ↗',href:'https://github.com/Valpatel/gyropup'},
];
await writeFile(path.join(out, 'site/nav.json'), JSON.stringify({title:'Gyropup',nav},null,2));
const slug = p => p.toLowerCase().replace(/[^a-z0-9]+/g,'-');
const documents = tracked.filter(p => /^(docs|research)\/.*\.md$/.test(p) && p !== 'docs/handoff.md');
documents.push('README.md', 'catalog/SCHEMA.md');
const pagePath = p => `/site/pages/${slug(p)}.html`;
function frame(title, body) {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${esc(title)} · Gyropup</title><link rel="icon" href="/web/icon.svg"><link rel="stylesheet" href="/web/portal.css"></head><body class="docs-page"><main class="document"><a class="back" href="/site/">← Design notebook</a><p class="portal-label">BUILT BY AUTONOMOUS SYSTEMS · WORK IN PROGRESS</p>${body}<footer>Created by <a href="https://valpatel.com">Valpatel Software LLC</a>. © 2026. All rights reserved. Repository materials retain their stated licenses.</footer></main><script type="module">import {mountAppNav} from '/designer/kit/appnav.js'; mountAppNav({root:'../../',current:'docs'});</script></body></html>`;
}
const docs = [];
for (const file of documents) {
  const source = await read(file);
  const title = source.match(/^#\s+(.+)$/m)?.[1] || file;
  // Preserve source-relative links, route published Markdown to its HTML view.
  const headingIds = new Map();
  const renderer = new marked.Renderer();
  renderer.heading = function({tokens, depth}) {
    const text = this.parser.parseInline(tokens);
    const base = text.replace(/<[^>]*>/g, '').normalize('NFKD').replace(/[^\x00-\x7f]/g,'').replace(/[^\w\s-]/g,'').trim().toLowerCase().replace(/[-\s]+/g,'-');
    const n = headingIds.get(base) || 0; headingIds.set(base, n+1);
    return `<h${depth} id="${base}${n ? '-'+n : ''}">${text}</h${depth}>`;
  };
  let html = await marked.parse(source, {renderer});
  html = html.replace(/(href|src)="([^"#][^"]*)"/g, (all, attr, url) => {
    if (/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(url)) return all;
    const [pathname, ...hash] = url.split('#');
    const resolved = pathname.startsWith('/') ? pathname.slice(1) : path.posix.normalize(path.posix.join(path.posix.dirname(file), pathname));
    const published = roots.some(r => resolved.startsWith(r)) && resolved !== 'docs/handoff.md';
    const target = documents.includes(resolved) ? pagePath(resolved) : (published && (tracked.includes(resolved) || tracked.some(f => f.startsWith(resolved.replace(/\/$/, '')+'/'))) ? '/' + resolved : `https://github.com/Valpatel/gyropup/blob/main/${resolved}`;
    return `${attr}="${esc(target)}${hash.length ? '#'+esc(hash.join('#')) : ''}"`;
  });
  html = html.replace(/<table>/g,'<div class="table-scroll"><table>').replace(/<\/table>/g,'</table></div>');
  await writeFile(path.join(out, pagePath(file)), frame(title, `<article>${html}</article>`));
  docs.push({title,file});
}
const decisions = YAML.parse(await read(config.decisions));
const notebook = `<h1>The design notebook.</h1><p class="doc-lede">Follow the decisions, research, and work behind Gyropup. These are evolving engineering notes, not finished product specifications.</p><div class="notebook-links"><a href="/designer/progress.html">Progress & test reports ↗</a><a href="/designer/build.html">Parts & build files ↗</a><a href="#decisions">Decisions ↓</a></div><h2 id="documents">Documents</h2><ul class="document-list">${docs.map(d=>`<li><a href="${pagePath(d.file)}">${esc(d.title)}</a><small>${esc(d.file)}</small></li>`).join('')}</ul><h2 id="decisions">Design decisions</h2>${decisions.slice().reverse().map(d=>`<details class="decision"><summary><span>${esc(d.id)}</span> ${esc(d.title)}</summary><p>${esc(d.decision)}</p><p>${esc(d.why)}</p><small>${esc(d.date)} · ${esc(d.status)}</small></details>`).join('')}`;
await writeFile(path.join(out,'site/index.html'), frame('Design notebook', notebook).replace("root:'../../'", "root:'../'"));
// Static equivalents of local file listings keep the existing Build page's file links working.
const directories = new Map();
for (const file of tracked.filter(f => roots.some(r => f.startsWith(r)) && f !== 'docs/handoff.md')) {
  let parent = path.posix.dirname(file), entry = path.posix.basename(file);
  while (parent !== '.') {
    if (!directories.has(parent)) directories.set(parent, []);
    if (!directories.get(parent).includes(entry)) directories.get(parent).push(entry);
    entry = path.posix.basename(parent) + '/'; parent = path.posix.dirname(parent);
  }
}
for (const [dir, files] of directories) {
  if (files.includes('index.html')) continue;
  const body = `<h1>${esc(dir)}</h1><p>Published design artifacts. Return to <a href="/designer/build.html">Build</a> or <a href="/designer/progress.html">Progress</a> for context.</p><ul>${files.sort().map(f => `<li><a href="${esc(f)}">${esc(f)}</a></li>`).join('')}</ul>`;
  const depth = '../'.repeat(dir.split('/').length);
  await writeFile(path.join(out,dir,'index.html'), frame('Design files',body).replace("root:'../../'", `root:'${depth}'`));
}
await writeFile(path.join(out,'404.html'), frame('Page not found', '<h1>This part is still taking shape.</h1><p>The page or file could not be found.</p><a href="/">Back to Gyropup →</a>').replace("root:'../../'", "root:'./'"));
await writeFile(path.join(out,'_headers'), '/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n');
await writeFile(path.join(out,'robots.txt'),'User-agent: *\nAllow: /\nSitemap: https://gyropup.com/sitemap.xml\n');
await writeFile(path.join(out,'sitemap.xml'), '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+['/','/designer/sim.html','/designer/progress.html','/designer/build.html','/site/'].map(p=>`<url><loc>https://gyropup.com${p}</loc></url>`).join('')+'</urlset>');
const revision = execFileSync('git',['rev-parse','HEAD'],{cwd:root}).toString().trim();
await writeFile(path.join(out,'version.json'),JSON.stringify({revision,built:new Date().toISOString()},null,2));
console.log(`Built dist: landing page, simulator, portal, ${documents.length} documents and committed design assets. Revision ${revision.slice(0,12)}`);
