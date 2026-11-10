"""Pure mesh corroboration for a narrowly source-proven manufacturing original.

This samples every vertex and triangle centre in both directions. It is not a
continuous Hausdorff proof, a CAD solver or a physical/fabrication qualification.
The complete original producer receipt is still required independently.
"""
from __future__ import annotations
import math
import json
from pathlib import Path
import sys
from robot_data import vertices,sha


def sub(a,b):return (a[0]-b[0],a[1]-b[1],a[2]-b[2])
def dot(a,b):return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]


def point_triangle_distance2(p,triangle):
    a,b,c=triangle;ab=sub(b,a);ac=sub(c,a);ap=sub(p,a)
    d1,d2=dot(ab,ap),dot(ac,ap)
    if d1<=0 and d2<=0:return dot(ap,ap)
    bp=sub(p,b);d3,d4=dot(ab,bp),dot(ac,bp)
    if d3>=0 and d4<=d3:return dot(bp,bp)
    vc=d1*d4-d3*d2
    if vc<=0 and d1>=0 and d3<=0:
        v=d1/(d1-d3);q=tuple(a[i]+v*ab[i] for i in range(3));return dot(sub(p,q),sub(p,q))
    cp=sub(p,c);d5,d6=dot(ab,cp),dot(ac,cp)
    if d6>=0 and d5<=d6:return dot(cp,cp)
    vb=d5*d2-d1*d6
    if vb<=0 and d2>=0 and d6<=0:
        w=d2/(d2-d6);q=tuple(a[i]+w*ac[i] for i in range(3));return dot(sub(p,q),sub(p,q))
    va=d3*d6-d5*d4
    if va<=0 and d4-d3>=0 and d5-d6>=0:
        w=(d4-d3)/((d4-d3)+(d5-d6));q=tuple(b[i]+w*(c[i]-b[i]) for i in range(3));return dot(sub(p,q),sub(p,q))
    total=va+vb+vc
    if abs(total)<1e-24:raise ValueError('Degenerate comparison triangle')
    v,w=vb/total,vc/total;q=tuple(a[i]+ab[i]*v+ac[i]*w for i in range(3))
    return dot(sub(p,q),sub(p,q))


class Surface:
    def __init__(self,triangles):
        def build(items):
            lo=tuple(min(p[k] for t in items for p in t) for k in range(3))
            hi=tuple(max(p[k] for t in items for p in t) for k in range(3))
            if len(items)<=16:return (lo,hi,items,None)
            axis=max(range(3),key=lambda k:hi[k]-lo[k])
            ordered=sorted(items,key=lambda t:sum(p[axis] for p in t));mid=len(items)//2
            return (lo,hi,None,(build(ordered[:mid]),build(ordered[mid:])))
        self.root=build(triangles)

    def distance(self,point,limit):
        best=limit*limit;found=False;stack=[self.root]
        while stack:
            lo,hi,triangles,children=stack.pop()
            if sum(max(lo[k]-point[k],0,point[k]-hi[k])**2 for k in range(3))>best:continue
            if children:stack.extend(children);continue
            for triangle in triangles:
                value=point_triangle_distance2(point,triangle)
                if value<=best:best=value;found=True
        return math.sqrt(best) if found else math.inf


def triangles(file,transform=lambda p:p):
    points=vertices(file)
    return [tuple(transform(p) for p in points[i:i+3]) for i in range(0,len(points),3)]


def correspondence(a,b,limit_mm):
    if not math.isfinite(limit_mm) or limit_mm<=0:raise ValueError('Finite positive comparison limit required')
    def direction(source,target):
        surface=Surface(target)
        points={p for triangle in source for p in triangle}
        points.update(tuple(sum(p[k] for p in triangle)/3 for k in range(3)) for triangle in source)
        maximum=0
        for p in sorted(points):
            distance=surface.distance(p,limit_mm)
            if not math.isfinite(distance):raise ValueError('Manufacturing surface correspondence exceeds bound')
            maximum=max(maximum,distance)
        return {'samples':len(points),'max_distance_mm':maximum}
    return {'a_to_b':direction(a,b),'b_to_a':direction(b,a),'limit_mm':limit_mm,
            'scope':'All tessellated vertices and triangle centres; not a continuous surface-distance proof.'}


def hip_to_print(point):
    # Source-audited hip at this recipe: D/2+ring_r=75+62=137;
    # lower flange z=-(62+1.5+18)=-81.5; outer frame y=-1.
    # export_print_stl rotates -90deg about X, then flattens CAD bbox minima.
    x,y,z=point
    return (x+137,z+81.5,-y-1)


def source_guard(root,collection):
    """Run the existing strict failing-candidate receipt, without loading CAD."""
    root=Path(root)
    sys.path.insert(0,str(root))
    from hardware.cad.legs.rs04_lug_checks import validate_receipt
    directory=root/'hardware/exports/leg/rs04-mounting-fit'
    receipt=json.loads((directory/'checks.json').read_text())
    validate_receipt(receipt,directory,root)
    if any(sha(root/file)!=value for file,value in collection['inputs'].items()):
        raise ValueError('Current collected CAD input changed')
    if any(collection['inputs'].get(file)!=value for file,value in receipt['source_inputs']['project']['files'].items()):
        raise ValueError('Native collection and manufacturing producer use different CAD inputs')
    original=root/'hardware/exports/leg/hip_frame.stl'
    if sha(original)!=receipt['artifacts']['hip_frame']['files']['stl']:
        raise ValueError('Retained default original differs from source-bound hip artifact')
    return receipt


def main():
    import argparse,time
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[3]
    if args.out.exists():raise ValueError('Use a fresh proof output')
    record=root/'.agents/plans/robot-assembly/collection-260.json'
    collection=json.loads(record.read_text());receipt=source_guard(root,collection)
    original=root/'hardware/exports/leg/hip_frame.stl';a=triangles(original)
    start=time.monotonic();yo=collection['datums']['y_off_mm'];parts={p['name']:p for p in collection['parts']}
    proof={'status':'INCOMPLETE','native_source':collection['source_commit'],'collection_sha256':sha(record),
           'cad_inputs':collection['inputs'],'receipt_sha256':sha(root/'hardware/exports/leg/rs04-mounting-fit/checks.json'),
           'original_sha256':sha(original),'sampler_sha256':sha(Path(__file__)),
           'transform':'-90deg X, then CAD bbox origin: print=(x+137,z+81.5,-y-1)',
           'transform_source':'fivebar.py motors/frame_ring_r/HIP; rs04_lug_checks.py geometry_checks; cadagent.geometry export_print_stl/flatten_to_bed',
           'tessellation_allowance_mm':.25+.05+.001+.0001,'sides':{},'negative_controls':{},
           'engineering_status':receipt['status'],'engineering_counts':receipt['counts'],
           'physical_fit_verified':False,'strength_verified':False,'manufacturing_released':False}
    for side in ('L','R'):
        part=parts[side+'.hip_frame'];file=root/'software/site/assets/build-guides/robot-wip-540056ba4e59'/part['file']
        if sha(file)!=part['sha256']:raise ValueError('Actual guide hip mesh changed')
        def transform(p):
            x,y,z=p;return hip_to_print((x,y-yo,z) if side=='L' else (-x,-y-yo,z))
        b=triangles(file,transform);result=correspondence(a,b,proof['tessellation_allowance_mm'])
        result['mesh_sha256']=sha(file);proof['sides'][side]=result
        args.out.write_text(json.dumps(proof,indent=2)+'\n');print(side,result,flush=True)
        if side=='L':
            shifted=[tuple((p[0]+3,p[1],p[2]) for p in t) for t in b]
            try:correspondence(a,shifted,proof['tessellation_allowance_mm'])
            except ValueError:proof['negative_controls']['actual_mesh_shift_3mm']=True
            else:raise ValueError('Wrong current-part transform was accepted')
    proof['status']='SOURCE_MATCH_CORROBORATED';proof['elapsed_seconds']=time.monotonic()-start
    proof['scope']='Complete producer receipt plus source identity and sampled tessellation correspondence only; no physical/fabrication approval.'
    args.out.write_text(json.dumps(proof,indent=2)+'\n');print('Source match corroborated',proof['elapsed_seconds'],flush=True)


if __name__=='__main__':main()
