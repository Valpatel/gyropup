"""One existing-toolkit, geometry-only hip project; no CAD, slicer or transport."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from robot_data import sha,vertices

ROOT=Path(__file__).resolve().parents[3]
NS='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
TOOLKIT='d0d13ee3b700b20ebec76ddc3e51561e8d7fbdcc'
ORIGINAL='hardware/exports/leg/hip_frame.stl'
RECEIPT='.agents/plans/robot-assembly/hip-prepared-project.json'
BED=(256.,256.)
MARGIN=3.
LIMITATIONS=['Geometry-only WIP project; not a sliced or print-ready job.',
 'Generic 256 x 256 mm rectangle, 3 mm margin, no keepouts; not P1S/X1E or any actual printer/profile fit approval.',
 'Select and verify actual printer, material, orientation, supports and slicing settings manually.',
 'Eight support failures and physical fit/strength/manufacturing limits remain unresolved; no job starts.']


def indexed_mesh(file):
    points=vertices(file);unique=[];ids={};faces=[]
    for i in range(0,len(points),3):
        triangle=[]
        for p in points[i:i+3]:
            if p not in ids:ids[p]=len(unique);unique.append(p)
            triangle.append(ids[p])
        faces.append(tuple(triangle))
    return unique,faces


def volume(points,faces):
    total=0.
    for i,j,k in faces:
        a,b,c=points[i],points[j],points[k]
        total+=a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0])
    return total/6


def placed(points):
    # The existing packer selects this yaw for the recorded generic rectangle.
    c,s=round(math.cos(math.pi/4),12),round(math.sin(math.pi/4),12)
    turned=[(c*x-s*y,s*x+c*y,z) for x,y,z in points]
    lo=[min(p[k] for p in turned) for k in range(3)];hi=[max(p[k] for p in turned) for k in range(3)]
    shift=[BED[0]/2-(lo[0]+hi[0])/2,BED[1]/2-(lo[1]+hi[1])/2,-lo[2]]
    return [tuple(p[k]+shift[k] for k in range(3)) for p in turned],shift


def verify(project,original):
    """Independent strict read-back of the real existing writer's one-object file."""
    source,faces=indexed_mesh(original);expected,shift=placed(source)
    with zipfile.ZipFile(project) as z:
        names=z.namelist()
        if len(names)!=3 or set(names)!={'[Content_Types].xml','_rels/.rels','3D/3dmodel.model'}:
            raise ValueError('Geometry-only package membership changed')
        if any(i.file_size>16*1024*1024 for i in z.infolist()):raise ValueError('Oversized geometry package')
        xml=ET.fromstring(z.read('3D/3dmodel.model'))
    ns={'m':NS}
    if xml.tag!='{'+NS+'}model' or xml.get('unit')!='millimeter':raise ValueError('Millimetres required')
    objects=xml.findall('m:resources/m:object',ns);items=xml.findall('m:build/m:item',ns)
    if (len(objects)!=1 or objects[0].get('id')!='1' or objects[0].get('type')!='model'
        or len(items)!=1 or items[0].attrib!={'objectid':'1'}):raise ValueError('Unexpected object or build transform')
    meshes=objects[0].findall('m:mesh',ns)
    if len(meshes)!=1:raise ValueError('One mesh required')
    mesh=meshes[0]
    actual=[tuple(float(p.get(k)) for k in ('x','y','z')) for p in mesh.findall('m:vertices/m:vertex',ns)]
    saved=[tuple(int(p.get(k)) for k in ('v1','v2','v3')) for p in mesh.findall('m:triangles/m:triangle',ns)]
    if len(actual)!=len(source) or saved!=faces:raise ValueError('Source vertex/triangle identity changed')
    if not all(math.isfinite(x) for p in actual for x in p):raise ValueError('Nonfinite coordinates')
    error=max(abs(a-b) for p,q in zip(actual,expected) for a,b in zip(p,q))
    if error>.000051:raise ValueError('Original-to-project rigid placement changed')
    edges={}
    for face in saved:
        if len(set(face))!=3 or min(face)<0 or max(face)>=len(actual):raise ValueError('Invalid triangle indices')
        for a,b in zip(face,face[1:]+face[:1]):edges[a,b]=edges.get((a,b),0)+1
    if any(n!=1 or edges.get((b,a))!=1 for (a,b),n in edges.items()):raise ValueError('Non-manifold or inconsistent edges')
    lo=[min(p[k] for p in actual) for k in range(3)];hi=[max(p[k] for p in actual) for k in range(3)]
    if any(lo[k]<MARGIN-.0001 or hi[k]>BED[k]-MARGIN+.0001 for k in (0,1)) or abs(lo[2])>.0001:
        raise ValueError('Outside the declared generic rectangle')
    original_volume=volume(source,faces);actual_volume=volume(actual,saved)
    if original_volume<=0 or abs(actual_volume-original_volume)>abs(original_volume)*1e-5:raise ValueError('Signed volume changed')
    return {'vertices':len(actual),'triangles':len(saved),'units':'millimeter','edge_manifold':True,
            'max_coordinate_error_mm':error,'original_volume_mm3':original_volume,'project_volume_mm3':actual_volume,
            'bounds_mm':lo+hi,'yaw_deg':45,'translation_mm':shift,'generic_bed_mm':list(BED),'margin_mm':MARGIN,'keepouts':[],
            'actual_printer_fit_verified':False,'slice_verified':False,'physical_qualification':False}


def prepared(root,original_sha):
    root=Path(root);record=root/RECEIPT
    if not record.is_file():return []
    try:
        data=json.loads(record.read_text());row=data['project'];file=row['source_file']
        if (row['source_original_sha256']!=original_sha or sha(root/ORIGINAL)!=original_sha
            or row['kind']!='geometry-only' or row['immutable'] is not True
            or row['limitations']!=LIMITATIONS or data['original_file']!=ORIGINAL
            or data['producer_sha256']!=sha(Path(__file__)) or data['toolkit_revision']!=TOOLKIT
            or file!=f"software/site/assets/build-guides/prepared-projects/{row['sha256']}/hip-frame.geometry.3mf"
            or row['public_file']!='/web/'+file.removeprefix('software/site/assets/')
            or sha(root/file)!=row['sha256']):return []
        verify(root/file,root/ORIGINAL)
        return [row]
    except (ValueError,KeyError,TypeError,OSError,zipfile.BadZipFile,ET.ParseError):return []


def main():
    import argparse,importlib
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--toolkit',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();toolkit=args.toolkit.resolve()
    if args.out.exists():raise ValueError('Use a fresh output directory')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=toolkit,text=True).strip()!=TOOLKIT:raise ValueError('Use the recorded toolkit revision')
    helpers=['software/cadagent/manufacturing/mesh3mf.py','software/cadagent/manufacturing/plates.py','software/cadagent/_deps.py']
    helper_hashes={f:sha(toolkit/f) for f in helpers}
    for f in helpers:
        if (toolkit/f).read_bytes()!=subprocess.check_output(['git','show',TOOLKIT+':'+f],cwd=toolkit):raise ValueError('Toolkit helper differs from Git')
    if any(k=='cadagent' or k.startswith('cadagent.') for k in sys.modules):raise ValueError('Fresh toolkit process required')
    sys.path.insert(0,str(toolkit/'software'))
    from cadagent.manufacturing import mesh3mf,plates
    if Path(mesh3mf.__file__).resolve()!=toolkit/helpers[0] or Path(plates.__file__).resolve()!=toolkit/helpers[1]:raise ValueError('Wrong toolkit origin')
    from robot_manufacturing import hip_geometry_match
    collection=json.loads((ROOT/'.agents/plans/robot-assembly/collection-260.json').read_text())
    if hip_geometry_match(ROOT,collection,'L.hip_frame') is None:raise ValueError('Accepted hip source correspondence required')
    original=ROOT/ORIGINAL;original_sha=sha(original);v,f=indexed_mesh(original);np=mesh3mf.np
    layout=plates.pack([plates.Copy('hip_frame',1,plates.footprint(v))],BED,gap=5,margin=MARGIN)
    if plates.check_plates(layout,BED,gap=5,margin=MARGIN,quantities={'hip_frame':1}) or len(layout)!=1 or layout[0].placements[0].angle!=45:
        raise ValueError('Expected generic single-part placement changed')
    c,s=plates.rotation(45);turned=np.asarray([(c*x-s*y,s*x+c*y,z) for x,y,z in v]);args.out.mkdir()
    file=args.out/'hip-frame.geometry.3mf'
    report=mesh3mf.write_3mf(file,turned,np.asarray(f),'Hip frame - geometry only; manually select printer and slice settings',BED)
    back_v,back_f=mesh3mf.read_3mf(file)
    if len(back_v)!=len(v) or not np.array_equal(back_f,np.asarray(f)):raise ValueError('Toolkit read-back identity changed')
    checks=verify(file,original);digest=sha(file)
    source=f'software/site/assets/build-guides/prepared-projects/{digest}/hip-frame.geometry.3mf'
    row={'source_file':source,'public_file':'/web/'+source.removeprefix('software/site/assets/'),'sha256':digest,
         'source_original_sha256':original_sha,'kind':'geometry-only','immutable':True,'limitations':LIMITATIONS}
    if sha(original)!=original_sha or {f:sha(toolkit/f) for f in helpers}!=helper_hashes:raise ValueError('Source/tool changed during generation')
    record={'schema':'gyropup.geometry-only-project/1','project':row,'original_file':ORIGINAL,'producer_sha256':sha(Path(__file__)),
            'toolkit_revision':TOOLKIT,'toolkit_helpers':helper_hashes,'numpy_version':np.__version__,
            'packing':{'angle_deg':45,'margin_mm':MARGIN,'bed_mm':list(BED),'keepouts':[],'actual_printer_profile':None},
            'checks':checks,'original_preserved':True,'retained_3mf_sha256':sha(ROOT/'hardware/exports/leg/hip_frame.3mf')}
    (args.out/'receipt.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({'project_sha256':digest,'checks':checks}))


if __name__=='__main__':main()
