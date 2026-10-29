/** Readable static counterparts of the public HTML; no extra deployment service. */
import { readFile, writeFile, readdir, stat } from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { parseHTML } from 'linkedom';
import TurndownService from 'turndown';
import { gfm } from 'turndown-plugin-gfm';
import { addModelPreviews } from '../web/model-links.js';

const origin = 'https://gyropup.com';
const digest = value => createHash('sha256').update(value).digest('hex');
const markdownPath = file => file.replace(/\.html$/, '.md');
const publicPath = file => '/' + file;
const htmlURL = file => origin + publicPath(file).replace(/index\.html$/, '');

/** This runs only the two trusted, repository-owned renderers, never fetched code.
 * Their fetches read the published bundle, so private/local files cannot enter Markdown.
 * Reusing the browser renderer keeps totals, status, and the order of work identical.
 */
export async function renderPortal(html, file, out) {
  const script = {
    'designer/progress.html': { file: 'designer/progress.js', ready: '#status .card' },
    'designer/build.html': { file: 'designer/build.js', ready: '#grand-usd' },
  }[file];
  if (!script) return html;
  const { document, window } = parseHTML(html);
  const source = await readFile(path.join(out, script.file), 'utf8');
  const imports = source.match(/^import .*$/gm) || [];
  const expectedImports = ["import { mountAppNav } from './kit/appnav.js';", "import { createLoadingStatus } from './kit/loading.js';", "import { createPortalParts } from './portal-parts.js';",
    file === 'designer/build.html' ? "import { createDataReader, isRecord, isMarkdown } from './kit/portal-data.js';"
      : "import { createDataReader, isRecord } from './kit/portal-data.js';"];
  if (imports.length !== expectedImports.length || imports.some((line,i)=>line!==expectedImports[i])) {
    throw new Error(`Update the Markdown renderer for changed imports in ${script.file}`);
  }
  const fetch = async input => {
    const url = new URL(input, origin + '/' + file);
    if (url.origin !== origin) throw new Error(`External request in static renderer: ${url.origin}`);
    let local = path.resolve(out, '.' + decodeURIComponent(url.pathname));
    if (!local.startsWith(path.resolve(out) + path.sep)) throw new Error('Asset escaped published bundle');
    try {
      if ((await stat(local)).isDirectory()) local = path.join(local, 'index.html');
      return new Response(await readFile(local));
    } catch (error) {
      if (error.code === 'ENOENT') return new Response('Not found', { status: 404 });
      throw error;
    }
  };
  // Execute the exact published, pure data reader with this bundle's fetch, never
  // import a checkout-local fallback. UI-only status feedback gets a DOM adapter;
  // failed sections remain a build failure instead of a partial static snapshot.
  const dataSource=await readFile(path.join(out,'designer/kit/portal-data.js'),'utf8');
  if (/^import\s/m.test(dataSource)) throw new Error('Update the Markdown renderer for portal-data imports');
  const dataAPI=new Function(dataSource.replace(/^export /gm,'')+'\nreturn {createDataReader,isRecord,isMarkdown};')();
  const statuses=[];
  const createLoadingStatus=(host)=>{
    const element=document.createElement('p');element.className='gp-loading';element.hidden=true;host.append(element);
    let generation=0;
    const finish=(state,message,token=generation)=>{if(token!==generation)return false;++generation;element.dataset.state=state;element.textContent=message;element.hidden=state==='ready';return true;};
    const api={element,begin(message){const token=++generation;element.hidden=false;element.dataset.state='loading';element.textContent=message;return token;},
      update(message,token=generation){if(token===generation)element.textContent=message;},ready(token){return finish('ready','',token);},
      fail(message,options={}){return finish('error',message,options.token);},unavailable(message,options={}){return finish('unavailable',message,options.token);},
      dismiss(){++generation;element.hidden=true;},dispose(){++generation;element.remove();}};
    statuses.push(api);return api;
  };
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  await new AsyncFunction('document','window','fetch','mountAppNav','createLoadingStatus','createDataReader','isRecord','isMarkdown','createPortalParts',
    imports.reduce((body,line)=>body.replace(line,''),source))(document,window,fetch,async()=>{},createLoadingStatus,dataAPI.createDataReader,dataAPI.isRecord,dataAPI.isMarkdown,()=>({dispose(){},enhance(){},replace(host,html){host.innerHTML=html;}}));
  if (!document.querySelector(script.ready)) throw new Error(`Empty Markdown data snapshot: ${file}`);
  const errors=statuses.filter(status=>status.element.dataset.state==='error');
  if(errors.length)throw new Error(`Incomplete Markdown data snapshot: ${file}: ${errors.map(status=>status.element.textContent).join('; ')}`);
  const inventory=JSON.parse(await readFile(path.join(out,'site/models.json'),'utf8'));
  addModelPreviews(document,{base:origin+'/'+file,published:new Set(inventory.files.map(file=>file.path))});
  return document.toString();
}

export function htmlToMarkdown(html, file) {
  const { document } = parseHTML(html);
  const title = document.querySelector('title')?.textContent || file;
  const interactive = !!document.querySelector('canvas, script[type="module"]');
  document.querySelectorAll('script, style, head, svg, canvas, template, nav, dialog, button, select, input, textarea, label.inc, [aria-hidden="true"], [hidden]').forEach(el => el.remove());
  // CSS provides spacing and columns in the browser. Preserve that structure in text.
  for (const node of document.querySelectorAll('span, strong, b')) { node.before(' '); node.after(' '); }
  for (const grid of document.querySelectorAll('.glist, .olist, .plist')) {
    const rows = [...grid.children];
    if (!rows[0]?.classList.contains('head')) continue;
    const table = document.createElement('table');
    rows.forEach((row, i) => {
      const group = document.createElement(i === 0 ? 'thead' : 'tbody');
      const tr = document.createElement('tr');
      const cells = [...row.children].flatMap(cell => cell.classList.contains('stats') ? [...cell.children] : [cell]);
      for (const cell of cells) {
        const td = document.createElement(i === 0 ? 'th' : 'td');
        td.innerHTML = cell.innerHTML;
        tr.append(td);
      }
      group.append(tr); table.append(group);
    });
    grid.replaceWith(table);
  }
  for (const node of document.querySelectorAll('[href], [src]')) {
    for (const attr of ['href', 'src']) {
      const value = node.getAttribute(attr);
      if (value && !/^(?:javascript|data):/i.test(value)) node.setAttribute(attr, new URL(value, origin + '/' + file).href);
      else if (value) node.removeAttribute(attr);
    }
  }
  const converter = new TurndownService({ headingStyle: 'atx', codeBlockStyle: 'fenced', bulletListMarker: '-' });
  converter.use(gfm);
  converter.addRule('readableTableCells', {
    filter: ['th', 'td'],
    replacement: (content, node) => `${node === node.parentNode.firstChild ? '| ' : ' '}${content.trim().replace(/\n+/g, '<br>').replace(/(?<!\\)\|/g, '\\|')} |`,
  });
  converter.addRule('sectionLabels', {
    filter: node => node.nodeName === 'DIV' && node.classList.contains('sec'),
    replacement: content => '\n\n## ' + content.trim() + '\n\n',
  });
  converter.addRule('videoLinks', {
    filter: ['video'],
    replacement: (_content, node) => node.getAttribute('src') ? `[Video](${node.getAttribute('src')})` : '',
  });
  const body = converter.turndown(document.body?.innerHTML || document.toString());
  return `${document.querySelector('h1') ? '' : '# ' + title + '\n\n'}> [HTML view](${htmlURL(file)}) · [Markdown index](${origin}/llms.txt). Generated from the same published content.${interactive ? ' Interactive controls and 3D scenes are available in the HTML view.' : ''}\n\n${body}\n`;
}

async function htmlFiles(dir, prefix = '') {
  const files = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const relative = path.posix.join(prefix, entry.name);
    if (entry.isDirectory()) files.push(...await htmlFiles(path.join(dir, entry.name), relative));
    else if (entry.name.endsWith('.html') && relative !== '404.html') files.push(relative);
  }
  return files.sort();
}

export async function writeMarkdownSite(out) {
  const pages = [];
  for (const file of await htmlFiles(out)) {
    const source = await readFile(path.join(out, file), 'utf8');
    const target = markdownPath(file);
    // Do not silently overwrite a published authored Markdown source.
    try { await stat(path.join(out, target)); throw new Error(`Markdown route collision: ${target}`); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
    const rendered = await renderPortal(source, file, out);
    const markdown = htmlToMarkdown(rendered, file);
    const alternate = `<link rel="alternate" type="text/markdown" href="${publicPath(target)}" title="Markdown">`;
    const html = source.replace('</head>', alternate + '</head>');
    if (html === source) throw new Error(`Missing HTML head in ${file}`);
    await writeFile(path.join(out, file), html);
    await writeFile(path.join(out, target), markdown);
    pages.push({ html: publicPath(file), markdown: publicPath(target), htmlSha256: digest(html), markdownSha256: digest(markdown) });
  }
  await writeFile(path.join(out, 'markdown-pages.json'), JSON.stringify({ pages }, null, 2) + '\n');
  const primary = new Set(['/index.md', '/designer/progress.md', '/designer/build.md', '/designer/sim.md', '/site/index.md']);
  const line = page => `- [${page.markdown}](${origin}${page.markdown})`;
  await writeFile(path.join(out, 'llms.txt'), `# Gyropup\n\n> Autonomous battlefield robots for kids: a Valpatel Software LLC prototype for foam-ball play.\n\nPublic Markdown is generated on every site build from the same HTML, documents, and published design data. Progress and Build include their rendered data; these are development records, not finished product specifications.\n\nUse the explicit URLs below with any HTTP client. HTML pages advertise their counterpart with a text/markdown alternate link. No account or JavaScript is needed. CAD, media, JSON, and other downloads retain their original URLs.\n\n## Start here\n\n${pages.filter(p => primary.has(p.markdown)).map(line).join('\n')}\n\n## All public pages\n\n${pages.filter(p => !primary.has(p.markdown)).map(line).join('\n')}\n\n## Source and publisher\n\n- [Repository](https://github.com/Valpatel/gyropup)\n- [Valpatel Software LLC](https://valpatel.com)\n`);
  return pages;
}
