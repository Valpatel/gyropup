import assert from 'node:assert/strict';
import {test} from 'node:test';
import {parseHTML} from 'linkedom';
import {addModelPreviews} from '../web/model-links.js';
const base='https://gyropup.com/designer/build.html';
const published=new Set(['/exports/part.step','/exports/different.stl']);
const apply=document=>addModelPreviews(document,{base,published});
const row=()=>'<tr><td><a href="/exports/part.step"><img alt="part"></a></td><td><a href="../exports/part.step">STEP</a></td></tr>';
test('picture and named download share one preview per exact file, idempotently',()=>{
 const {document}=parseHTML('<html><body><table>'+row()+'</table></body></html>');
 apply(document);const preview=document.querySelector('[data-model-preview]');
 assert.equal(document.querySelectorAll('[data-model-preview]').length,1);
 assert.equal(preview.previousElementSibling.textContent,'STEP');
 assert.equal(document.querySelectorAll('a[data-model-original][download]').length,2);
 for(let i=0;i<5;i++)apply(document);
 assert.equal(document.querySelectorAll('[data-model-preview]').length,1);
 assert.equal(document.querySelector('[data-model-preview]'),preview);
});
test('existing duplicates are repaired; cloned rows retain their own independent action',()=>{
 const {document}=parseHTML('<html><body><table>'+row()+'</table></body></html>');apply(document);
 const tr=document.querySelector('tr'),preview=tr.querySelector('[data-model-preview]');
 tr.firstElementChild.append(preview.cloneNode(true));apply(document);
 assert.equal(tr.querySelectorAll('[data-model-preview]').length,1);
 const clone=tr.cloneNode(true);tr.after(clone);apply(document);
 assert.equal(document.querySelectorAll('[data-model-preview]').length,2);
 for(const r of [tr,clone])assert.equal(r.querySelector('[data-model-preview]').previousElementSibling.textContent,'STEP');
});
test('different models and file-directory entries retain their own previews',()=>{
 const {document}=parseHTML('<html><body><table><tr><td><a href="/exports/part.step">Part</a><a href="/exports/different.stl">Different</a></td></tr></table><ul><li><a href="/exports/part.step">Part</a></li><li><a href="/exports/different.stl">Different</a></li></ul></body></html>');
 apply(document);apply(document);assert.equal(document.querySelectorAll('[data-model-preview]').length,4);
 for(const link of document.querySelectorAll('[data-model-original]'))assert.ok(link.nextElementSibling.hasAttribute('data-model-preview'));
});
test('external/unpublished links and viewer pages are not decorated',()=>{
 const {document}=parseHTML('<html><body><a href="https://elsewhere.test/exports/part.step">external</a><a href="/private.step">private</a></body></html>');apply(document);
 assert.equal(document.querySelectorAll('[data-model-preview]').length,0);
 document.body.innerHTML=row();addModelPreviews(document,{base:'https://gyropup.com/designer/kit/file-viewer.html',published});
 assert.equal(document.querySelectorAll('[data-model-preview]').length,0);
});
