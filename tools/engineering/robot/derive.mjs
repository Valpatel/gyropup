// Evaluate a design with the designer's model from the command line (the same code the web page runs).
//   node tools/derive.mjs [designs/default.json] > derived.json
import { readFileSync } from 'node:fs';
import { evaluate, indexCatalog } from '../designer/model.js';

const root = new URL('..', import.meta.url).pathname;
const read = (p) => JSON.parse(readFileSync(root + p, 'utf8'));
const designPath = process.argv[2] ?? 'designs/default.json';
const design = JSON.parse(readFileSync(designPath.startsWith('/') ? designPath : root + designPath, 'utf8'));
const index = read('catalog/index.json');
const catalog = indexCatalog(index.files.map((f) => read(`catalog/${f}`)));
const result = evaluate(design, catalog, read('catalog/materials.json'));
process.stdout.write(JSON.stringify(result, null, 2) + '\n');
