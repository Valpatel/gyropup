#!/usr/bin/env python3
"""Offline audit of the one public run; does not launch any browser or contact a site."""
import hashlib,importlib.util,json,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
packet=Path(__file__).resolve().parent;contract=json.loads((packet/'contract.json').read_text())
assert contract['approved_for_execution'] is True
spec=importlib.util.spec_from_file_location('pdf_id_extractor',str(packet/'pdf-id-extractor.py'));identities=importlib.util.module_from_spec(spec);spec.loader.exec_module(identities)
out=Path(sys.argv[1]);r=json.loads((out/'report.json').read_text());assert r['pass']
assert len(r['pdfs'])==12
required={(table,scope,paper) for table in ['queue','orders'] for scope in ['all','matched'] for paper in ['A4','Letter']}|{(table,'all',paper) for table in ['made','pending'] for paper in ['A4','Letter']}
actual=[(entry['table'],entry['scope'],entry['format']) for entry in r['pdfs']]
assert len(set(actual))==12 and set(actual)==required, 'Missing/duplicated required table/scope/paper combination'
tables={table['name']:table for table in contract['tables']}
for entry in r['pdfs']:
    assert len(entry['ids'])==len(set(entry['ids'])) and entry['ids']
    if entry['scope']=='all':assert sorted(entry['ids'])==sorted(tables[entry['table']]['ids'])
    else:assert entry['ids']==tables[entry['table']]['matchingIds']
    assert entry['file']==entry['table']+'-'+('all' if entry['scope']=='all' else 'matching')+'-'+entry['format']+'.pdf'
    if entry['scope']=='all':assert entry['expectedPages']==tables[entry['table']]['pdfPages'][entry['format']]
    if entry['table']=='pending':assert entry['pendingWarnings']==tables['pending']['pendingWarnings']
results=[]
for entry in r['pdfs']:
    pdf=out/entry['file']
    xml=subprocess.check_output(['pdftotext','-bbox',str(pdf),'-'],timeout=15)
    root=ET.fromstring(xml);pages=root.findall('.//{*}page');assert pages
    page_text=[];bad=[]
    for n,page in enumerate(pages):
        words=page.findall('.//{*}word');texts=[w.text or '' for w in words];page_text.append('\n'.join(texts))
        assert 'ID' in texts and 'Quantity' in texts, (entry['file'],n,'missing repeated header')
        w,h=float(page.attrib['width']),float(page.attrib['height'])
        assert (w>h)==entry['landscape']
        for word in words:
            if float(word.attrib['xMin'])<0 or float(word.attrib['yMin'])<0 or float(word.attrib['xMax'])>w or float(word.attrib['yMax'])>h:bad.append((n,word.text))
    assert not bad,(entry['file'],bad)
    raw=subprocess.check_output(['pdftotext','-raw',str(pdf),'-'],timeout=15).decode()
    raw_pages=raw.split('\f');allocated=identities.unique_known_ids(entry['ids'],raw)
    positions=[allocated[stable_id][0][0] for stable_id in entry['ids']]
    assert positions==sorted(positions), 'Part order across pages changed'
    for index,stable_id in enumerate(entry['ids']):
        start,end=allocated[stable_id][0];part_page=raw[:start].count('\f')
        assert part_page<len(pages) and raw[:end-1].count('\f')==part_page,(entry['file'],stable_id,'ID split across sheets')
        normalized=re.sub(r'\s','',raw_pages[part_page]);segment=re.sub(r'\s','',raw[start:positions[index+1] if index+1<len(positions) else len(raw)])
        for value in tables[entry['table']]['longNotes'].get(stable_id,{}).values():assert re.sub(r'\s','',value) in normalized and re.sub(r'\s','',value) in segment,(entry['file'],stable_id,'supporting note not complete in own part segment and page')
        for column,fragments in tables[entry['table']]['requiredFields'].get(stable_id,{}).items():
            for value in fragments:assert re.sub(r'\s','',value) in normalized and re.sub(r'\s','',value) in segment,(entry['file'],stable_id,column,'required source field not in own part segment and page')
    if entry['expectedPages'] is not None:assert len(pages)==entry['expectedPages'],(entry['file'],len(pages))
    if entry['pendingWarnings'] is not None:assert len(re.findall(r'\bModel\s+export\s+pending\b',raw))==entry['pendingWarnings']
    if entry['table']=='queue' and entry['scope']=='all':
        words=[w.text for p in pages for w in p.findall('.//{*}word')]
        for token in ['1106','72.5','Hours']:assert token in words,(entry['file'],token,'compact token split')
    results.append({'file':entry['file'],'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'pages':len(pages),'unique_ids':len(entry['ids']),'repeated_headers':len(pages),'out_of_page_words':len(bad),'pending_warnings':entry['pendingWarnings']})
(out/'pdf-audit.json').write_text(json.dumps({'pass':True,'results':results,'limits':'Automated text/identity/page-bound audit. Visual PDF review remains required for layout, row continuity and overall readability.'},indent=2))
