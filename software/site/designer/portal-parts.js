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
      const many=[...table.tBodies[0].rows].filter(row=>!row.hasAttribute('data-fixed')).length>1;
      for(const [index,th] of [...table.tHead.rows[0].cells].entries()) {
        if(!many||!th.textContent.trim()||/^picture$/i.test(th.textContent.trim())){th.removeAttribute('data-sort');continue;}
        th.dataset.sort=[...table.tBodies[0].rows].some(row=>row.cells[index]?.hasAttribute('data-sort-value'))?'number':'text';
      }
      if(!table.parentElement.classList.contains('cad-table-scroll')){const wrap=document.createElement('div');wrap.className='cad-table-scroll';table.before(wrap);wrap.append(table);}
      // Mobile-only labels repeat the printed headers. Preserve the actual value
      // and every pack/cut/price note with explicit boundaries in the plain snapshot.
      for(const cell of table.querySelectorAll('td[data-sort-value]'))if(cell.querySelector('.lbl')){
        const plain=cell.cloneNode(true);plain.querySelectorAll('.lbl').forEach(label=>label.remove());
        cell.dataset.printValue=[...plain.childNodes].map(node=>node.textContent.trim()).filter(Boolean).join(' — ');
      }
      // Seller/availability notes are separate UI spans, often adjacent in HTML.
      // Supply those boundaries explicitly instead of concatenating their words.
      for(const cell of table.querySelectorAll('td'))if(!cell.hasAttribute('data-print-value')&&cell.querySelector('small,br,.avail,.tag')){
        const plain=cell.cloneNode(true);plain.querySelectorAll('[hidden],[aria-hidden="true"]').forEach(node=>node.remove());
        for(const note of plain.querySelectorAll('small,br,.avail,.tag')){note.before(document.createTextNode(' '));note.after(document.createTextNode(' '));}
        cell.dataset.printValue=plain.textContent.replace(/\s+/g,' ').trim();
      }
      const identity=[...table.tHead.rows[0].cells].findIndex(th=>/^part$/i.test(th.textContent.trim()));
      if(table.dataset.track&&identity>=0){table.tHead.rows[0].cells[identity].classList.add('cad-part-identity');for(const row of table.tBodies[0].rows){const cell=row.cells[identity];if(cell){cell.classList.add('cad-part-identity');const notes=[...cell.querySelectorAll('small,.tag.warn,.tag.fail'),...row.querySelectorAll('[data-print-note]')].map(note=>note.textContent.trim()).filter(Boolean);cell.dataset.printValue=[row.dataset.partLabel||cell.textContent.trim(),...new Set(notes)].join(' — ');}}}
      const statuses=table.dataset.track==='print'?[{id:'printed',label:'Printed'}]:table.dataset.track==='buy'?[{id:'ordered',label:'Ordered'},{id:'inHand',label:'In hand'}]:[];
      for(const th of table.tHead.rows[0].cells)if(/^(picture|print setup)$/i.test(th.textContent.trim()))th.dataset.print='omit';
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
