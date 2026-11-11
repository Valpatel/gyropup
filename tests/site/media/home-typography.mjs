/** Actual rendered text, including CSS-collapsed line breaks; never source HTML. */
import assert from 'node:assert/strict';
export function readPlayHeading(node){
  return {renderedText:node.innerText,breakDisplay:getComputedStyle(node.querySelector('br')).display};
}
export function assertReadablePlayHeading(observation){
  assert.equal(typeof observation?.renderedText,'string','Rendered heading observation is synchronous text');
  assert.equal(observation.renderedText.replace(/\s+/g,' ').trim(),'Less scrolling. More robot.','Rendered play heading preserves the word separator');
}
export async function checkPlayHeading(page,collapsed){
  const value=await page.locator('#play-title').evaluate(readPlayHeading);
  assertReadablePlayHeading(value);
  assert.equal(value.breakDisplay==='none',collapsed,'The real responsive line-break state is exercised');
  return value;
}
export async function rejectMissingPlaySeparator(page){
  const heading=page.locator('#play-title');
  const original=await heading.evaluate(node=>{
    if(node.firstChild.nodeType!==Node.TEXT_NODE)throw Error('Expected the actual heading text node');
    const text=node.firstChild.nodeValue;node.firstChild.nodeValue=text.trimEnd();return text;
  });
  let faulty;
  try{
    faulty=await heading.evaluate(readPlayHeading);
    assert.equal(faulty.breakDisplay,'none','Negative uses the actual collapsed mobile break');
    assert.equal(faulty.renderedText.replace(/\s+/g,' ').trim(),'Less scrolling.More robot.');
    assert.throws(()=>assertReadablePlayHeading(faulty),/preserves the word separator/);
  }finally{await heading.evaluate((node,text)=>{node.firstChild.nodeValue=text;},original);}
  assertReadablePlayHeading(await heading.evaluate(readPlayHeading));
  return faulty;
}
