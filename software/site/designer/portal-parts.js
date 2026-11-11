// Product wiring around the shared cad-agent table/tracker modules.
import { createPartTracker } from './kit/part-tracker.js';
import { enhancePartTable, mountProgressTools } from './kit/part-table.js';
export function createPortalParts(host, {revision = 'unavailable'} = {}) {
  const tracker=createPartTracker({project:'gyropup',fields:['ordered','inHand','printed']});
  mountProgressTools(host,tracker);
  const enhanced=new Map();
  const dispose=host=>{for(const [table,api] of enhanced)if(host.contains(table)){api.dispose();enhanced.delete(table);}};
  const enhance=host=>{
    for(const table of host.querySelectorAll('table')) {
      if(enhanced.has(table)||!table.tHead||!table.tBodies.length)continue;
      // Keep the original disclosures in a real source column. A short identity
      // stays in Part; the shared printer can group verbose detail beneath it.
      const partIndex=[...table.tHead.rows[0].cells].findIndex(th=>/^part$/i.test(th.textContent.trim()));
      if(table.dataset.track&&partIndex>=0&&[...table.tBodies[0].rows].some(row=>row.cells[partIndex]?.querySelector(':scope > details'))){
        const index=table.tHead.rows[0].cells.length,heading=document.createElement('th');heading.textContent='Part details';table.tHead.rows[0].append(heading);
        for(const row of table.tBodies[0].rows){const cell=document.createElement('td');cell.append(...row.cells[partIndex].querySelectorAll(':scope > details'));row.append(cell);}
        const group=table.querySelector(':scope > colgroup');if(group){const column=document.createElement('col');column.style.width='200px';group.insertBefore(column,group.children[index]||null);}
      }
      const many=[...table.tBodies[0].rows].filter(row=>!row.hasAttribute('data-fixed')).length>1;
      for(const [index,th] of [...table.tHead.rows[0].cells].entries()) {
        if(!many||!th.textContent.trim()||/^picture$/i.test(th.textContent.trim())){th.removeAttribute('data-sort');continue;}
        th.dataset.sort=[...table.tBodies[0].rows].some(row=>row.cells[index]?.hasAttribute('data-sort-value'))?'number':'text';
      }
      if(!table.parentElement.classList.contains('cad-table-scroll')){const wrap=document.createElement('div');wrap.className='cad-table-scroll';table.before(wrap);wrap.append(table);}
      // Preserve all source text, including collapsed instructions and sourcing
      // disclosures. Only mobile labels duplicate the printed column headings.
      for(const row of table.tBodies[0].rows)for(const [index,cell] of [...row.cells].entries()){
        const plain=cell.cloneNode(true);plain.querySelectorAll('.lbl').forEach(label=>label.remove());
        if(/^design files$/i.test(table.tHead.rows[0].cells[index]?.textContent.trim()))for(const link of plain.querySelectorAll('a[href]')){
          const href=link.getAttribute('href');link.append(document.createTextNode(' ('+href+')'));
        }
        for(const note of plain.querySelectorAll('small,br,.avail,.tag,.key,div,li,p,summary')){note.before(document.createTextNode(' '));note.after(document.createTextNode(' '));}
        cell.dataset.printValue=plain.textContent.replace(/\s+/g,' ').trim();
      }
      if(partIndex>=0){table.tHead.rows[0].cells[partIndex].classList.add('cad-part-identity');for(const row of table.tBodies[0].rows){const cell=row.cells[partIndex];if(cell){cell.classList.add('cad-part-identity');const label=row.dataset.partLabel;if(label&&!cell.dataset.printValue.includes(label))cell.dataset.printValue=label+' — '+cell.dataset.printValue;}}}
      const statuses=table.dataset.track==='print'?[{id:'printed',label:'Printed'}]:table.dataset.track==='buy'?[{id:'ordered',label:'Ordered'},{id:'inHand',label:'In hand'}]:[];
      for(const th of table.tHead.rows[0].cells)if(/^picture$/i.test(th.textContent.trim()))th.dataset.print='omit';
      const api=enhancePartTable(table,{printable: table.dataset.track ? {project:'Gyropup retained prototype workstreams',revision,notice:'Original leg, rig, turret and earlier body planning lists. Current front/rear-pack robot manufacturing plan remains incomplete. Checklist marks track parts, not purchased quantities. This list does not qualify fit, strength or a complete robot.'} : undefined,label:table.dataset.label||table.caption?.textContent||'Parts',tracker,statuses,searchable:many,pageSize:Number(table.dataset.pageSize)||0});
      // Build assigns a column for each source header before the tracker appends its status headers.
      // Reconcile that product colgroup with the final enhanced table, so fixed layout does not
      // squeeze unassigned status columns underneath the sticky phone identity.
      const columns=table.querySelector(':scope > colgroup');
      if(columns)for(let index=columns.children.length;index<table.tHead.rows[0].cells.length;index++){
        const column=document.createElement('col');column.style.width=table.tHead.rows[0].cells[index].classList.contains('cad-status-heading')?'var(--build-status-column, 88px)':'100px';columns.append(column);
      }
      if(columns)table.style.setProperty('--build-columns-width','calc('+[...columns.children].map(column=>column.style.width).join(' + ')+')');
      api.toolbar.hidden=!many&&!table.dataset.track;
      if(many){const hint=document.createElement('span');hint.className='cad-table-hint';hint.textContent='Scroll the table sideways for more columns and status boxes.';api.toolbar.append(hint);}
      enhanced.set(table,api);
    }
  };
  return {dispose,enhance,filter(table,predicate){enhanced.get(table)?.setFilter(predicate);},replace(host,html){dispose(host);host.innerHTML=html;enhance(host);}};
}
