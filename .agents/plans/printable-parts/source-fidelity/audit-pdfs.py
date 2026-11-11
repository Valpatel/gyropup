from pathlib import Path
import json,re,subprocess,xml.etree.ElementTree as ET,hashlib,gzip,sys
out=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent
root=Path(__file__).resolve().parents[4]
def read_json(name):
 path=out/name
 return json.loads(path.read_text()) if path.exists() else json.loads(gzip.decompress((out/(name+'.gz')).read_bytes()))
report=read_json('report.json');assert not report['errors']
observations=[row for row in report['observations'] if row.get('case')=='pre-enhancement source fidelity']
producer=read_json('producer-source.json');norm=lambda value:re.sub(r'\s','',value)
def pattern(key):return r'(?<![A-Za-z0-9_/-])'+r'\s*'.join(map(re.escape,key))+r'(?![A-Za-z0-9_/-])'
import importlib.util
spec=importlib.util.spec_from_file_location('ids',str(Path(__file__).with_name('pdf-id-extractor.py')));ids=importlib.util.module_from_spec(spec);spec.loader.exec_module(ids)
maximal_matches=ids.maximal_known_id_matches
def records(host,index,count):
 rows=[r['groups'] for r in observations if r['host']==host and r['index']==index and len(r['groups'])==count];assert rows;return rows[0]
queue=records('queue',0,54);pending_observation=next(r for r in observations if r['host']=='queue' and len(r['groups'])==23);pending=pending_observation['groups'];orders=records('orders',0,279);matched=records('orders',0,1);made=records('made',0,16)
results=[]
for f in sorted(out.glob('*.pdf')):
 if f.name.startswith('orders-matched'):groups=matched
 elif f.name.startswith('orders-all'):groups=orders
 elif f.name.startswith('made-'):groups=made
 elif 'pending' in f.name:groups=pending
 else:groups=queue
 xml=ET.fromstring(subprocess.check_output(['pdftotext','-bbox',str(f),'-']));pages=xml.findall('.//{*}page');raw=subprocess.check_output(['pdftotext','-raw',str(f),'-']).decode();raw_pages=raw.split('\f');locations=[];field_checks=0;long_notes=[]
 for page in pages:
  tokens=[w.text for w in page.findall('.//{*}word')];assert 'ID' in tokens
  for w in page.findall('.//{*}word'):assert 0<=float(w.attrib['xMin'])<=float(w.attrib['xMax'])<=float(page.attrib['width']) and 0<=float(w.attrib['yMin'])<=float(w.attrib['yMax'])<=float(page.attrib['height'])
 positions=[];allocated=maximal_matches([group['id'] for group in groups],raw)
 for group in groups:
  matches=allocated[group['id']];assert len(matches)==1,(f.name,group['id'],'ID occurrence',len(matches));positions.append(matches[0][0])
 assert positions==sorted(positions)
 for index,group in enumerate(groups):
  page=raw[:positions[index]].count('\f');assert page<len(pages);locations.append({'id':group['id'],'page':page+1})
  segment=raw[positions[index]:positions[index+1] if index+1<len(positions) else len(raw)]
  for title,value in group['fields'].items():
   if title in ['Done','Part ID','Ordered','In hand','Printed'] or not value:continue
   assert norm(value) in norm(segment),(f.name,group['id'],title,'missing from its part segment')
   assert norm(value) in norm(raw_pages[page]),(f.name,group['id'],title,'not complete on same page')
   field_checks+=1
   if len(value)>240:long_notes.append({'id':group['id'],'column':title,'characters':len(value),'page':page+1})
 # Explicit independent raw-source sentinels, additional to producer-DOM equality.
 if groups is queue:
  hip=read_json('queue-raw-reference.json')['setup'];page=next(x['page'] for x in locations if x['id']=='print/leg/hip_frame');text=norm(raw_pages[page-1])
  for value in [hip['size_mm'] and ' × '.join(map(str,hip['size_mm']))+' mm',hip['placement'],hip['how'],hip['infill']]:assert norm(value) in text
  tokens=[w.text for p in pages for w in p.findall('.//{*}word')]
  for token in ['1106','72.5','Hours']:assert token in tokens
 if groups in [orders,matched]:
  rig=json.loads((root/'hardware/exports/rig/bom.json').read_text());part=next(row for row in rig['rig'] if row.get('key')=='ballast_shaft');page=next(x['page'] for x in locations if x['id']=='buy/ballast_shaft');assert norm('rig ×'+str(part['qty'])+' '+part['for']) in norm(raw_pages[page-1])
 if groups is made:
  refs=read_json('made-source.json')['references'];page=next(x['page'] for x in locations if x['id']==refs['id']);text=norm(raw_pages[page-1]);assert norm(refs['material']) in text
  for callout in refs['callouts']:assert norm(callout) in text
 if groups is pending:assert len(re.findall(r'Model\s+export\s+pending',raw))==21
 row={'file':f.name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'pages':len(pages),'unique_ids_once':len(groups),'source_order_preserved':True,'repeated_header_pages':len(pages),'out_of_page_words':0,'complete_source_field_segment_and_same_page_checks':field_checks,'part_pages':locations,'long_notes':long_notes,'pending_warnings':21 if groups is pending else 0};results.append(row);print(f.name,'pages',len(pages),'IDs',len(groups),'complete same-part same-page fields',field_checks)
print('PASS all ten PDF source-field, identity, order, page-bound and same-part-page checks')
