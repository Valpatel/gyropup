#!/usr/bin/env python3
"""Regenerate the audited reference from pinned rest geometry; requires cad-agent motion_trace.

Do not derive these datums from the display manifest. Review CAD source and
physical ownership before changing any joint, source revision or landmark policy.
"""
import json,struct,subprocess,math,sys
from pathlib import Path
from cadagent.motion_trace import required_poses
R=Path(__file__).resolve().parents[1];ref='4769888bf0334608ff997faeff5e663d96a1a70d';prefix='exports/sim/turret_box/'
def old(name): return subprocess.check_output(['git','show',ref+':'+prefix+name],cwd=R)
m=json.loads(old('manifest.json'))
def joint(parent,pivot,axis,span):return dict(parent=parent,pivot=pivot,axis=axis,range_deg=span)
# D76 (PR 196): the turret sits straight on the box deck, TM face z 145 (turret_box.Z_TM); the tilt axis 140 above it
# (Geo.path_t + Geo.tilt_c); wheels at Geo.wheel_x 73 - Geo.tilt_x 48 = 25, +-Geo.wheel_y 25.81.
joints=dict(pan=joint(None,[0,0,145],[0,0,1],[-170,170]),tilt=joint('pan',[0,0,285],[0,-1,0],[-25,0]),pinion=joint(None,[-52.65,0,145],[0,0,1],[-510,510]),dial=joint('tilt',[-48,0,285],[0,0,1],[0,360]),wheel_l=joint('tilt',[25,25.81,285],[0,0,1],[0,360]),wheel_r=joint('tilt',[25,-25.81,285],[0,0,-1],[0,360]),flap=joint('tilt',[-87,0,376],[0,-1,0],[0,110]))
contract=dict(schema_version=1,length_unit='mm',frame='assembly-home',reference='cad/turret.py Geo + pose_shape, FILL_PORT and GATES at '+ref+'; independently audited physical datums, with assembled rest vertices from the pinned full-build STL (each in its group frame). See docs/validation/turret-motion.md.',joints=joints,components={})
indices={}
def sub(a,b):return [a[i]-b[i] for i in range(3)]
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
for e in m['parts']:
 data=old(e['file']);n=struct.unpack_from('<I',data,80)[0];v=[struct.unpack_from('<3f',data,84+t*50+12+k*12) for t in range(n) for k in range(3)]
 origin=[0,0,0];g=e['group']
 if g in ['pan','tilt','dial','wheel_l','wheel_r','flap']:origin=joints[g]['pivot']   # the audited datums, not the manifest
 if g in ['dial','wheel_l','wheel_r','flap']:   # cross-check: the scene's own frames agree with the audited datums
  assert [a+b for a,b in zip(joints['tilt']['pivot'],m['pivots'][g])]==origin,(g,m['pivots'][g])
 i0=0;i1=max(range(len(v)),key=lambda i:dot(sub(v[i],v[i0]),sub(v[i],v[i0])))
 u=sub(v[i1],v[i0]);i2=max(range(len(v)),key=lambda i:dot(cross(u,sub(v[i],v[i0])),cross(u,sub(v[i],v[i0]))))
 normal=cross(u,sub(v[i2],v[i0]));i3=max(range(len(v)),key=lambda i:abs(dot(normal,sub(v[i],v[i0]))))
 assert abs(dot(normal,sub(v[i3],v[i0])))>1e-6,e['name']
 chosen=[i0,i1,i2,i3];indices[e['name']]=chosen
 contract['components'][e['name']]=dict(joint=g if g in joints else None,points=[[a+b for a,b in zip(v[i],origin)] for i in chosen])
fixture=dict(contract=contract,vertex_indices=indices,poses=required_poses(contract))
(R/'tests/fixtures/turret-motion-reference.json').write_text(json.dumps(fixture,indent=2)+'\n')
print('reference:',len(indices),'components;',len(fixture['poses']),'poses')
