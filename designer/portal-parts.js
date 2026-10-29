// Product wiring around the unchanged cad-agent table/tracker modules.
import { createPartTracker } from './kit/part-tracker.js';
import { enhancePartTable, mountProgressTools } from './kit/part-table.js';
export function createPortalParts(host) {
  const tracker=createPartTracker({project:'gyropup',fields:['ordered','inHand','printed']});
  mountProgressTools(host,tracker);
  const enhanced=new Map();
  const dispose=host=>{for(const [table,api] of enhanced)if(host.contains(table)){api.dispose();enhanced.delete(table);}};
  const enhance=host=>{
    for(const table of host.querySelectorAll('table')) {
      if(enhanced.has(table)||!table.tHead||!table.tBodies.length)continue;
      const many=[...table.tBodies[0].rows].filter(row=>!row.hasAttribute('data-fixed')).length>1;
      for(const [index,th] of [...table.tHead.rows[0].cells].entries()) {
        if(!many||!th.textContent.trim())continue;
        th.dataset.sort=[...table.tBodies[0].rows].some(row=>row.cells[index]?.hasAttribute('data-sort-value'))?'number':'text';
      }
      if(!table.parentElement.classList.contains('cad-table-scroll')){const wrap=document.createElement('div');wrap.className='cad-table-scroll';table.before(wrap);wrap.append(table);}
      const statuses=table.dataset.track==='print'?[{id:'printed',label:'Printed'}]:table.dataset.track==='buy'?[{id:'ordered',label:'Ordered'},{id:'inHand',label:'In hand'}]:[];
      const api=enhancePartTable(table,{label:table.dataset.label||table.caption?.textContent||'Parts',tracker,statuses,searchable:many});
      api.toolbar.hidden=!many;
      if(many){const hint=document.createElement('span');hint.className='cad-table-hint';hint.textContent='Scroll the table sideways for more columns and status boxes.';api.toolbar.append(hint);}
      enhanced.set(table,api);
    }
  };
  return {dispose,enhance,replace(host,html){dispose(host);host.innerHTML=html;enhance(host);}};
}
