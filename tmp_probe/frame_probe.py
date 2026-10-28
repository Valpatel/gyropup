"""The hip frame's R1 study (as cad/leg_studies.py sets it up) on a chosen frame, printing where its peak is."""
import sys, math
from pathlib import Path
variant = sys.argv[1]          # 'current', 'noback', 'orig'
case = sys.argv[2] if len(sys.argv) > 2 else 'R1'
W = Path(__file__).resolve().parents[1]
root = Path(__file__).resolve().parent / 'orig' if variant == 'orig' else W
sys.path.insert(0, str(root / 'cad'))
import numpy as np
import fivebar as fb
if variant == 'noback':
    fb.STOP_EAR_BACK = 0.0
if variant == 'nocorner':
    fb.STOP_EAR_CORNER = False
if variant == 'roundboss':                      # the new holes and Ø36 bosses only: no lobe, no backing
    fb.STOP_EAR_BACK = 0.0
    _orig_hull = fb._hull
    import inspect
    src = inspect.getsource(fb.hip_frame).replace('        if k < 2:', '        if False:')
    exec(compile(src, 'hip_frame_roundboss', 'exec'), fb.__dict__)
sys.path.insert(0, str(root))
import importlib.util
spec = importlib.util.spec_from_file_location('ls', str(root / 'cad/leg_studies.py'))
ls = importlib.util.module_from_spec(spec); sys.modules['ls'] = ls
ls_fb = fb                                         # leg_studies imports 'fivebar' by name: already this one
spec.loader.exec_module(ls)
import gmi
from cadagent.fea import MATERIALS, Study
C = ls.cases()
SH = {'R1': {'rear': 0.765, 'front': 0.669}, 'E1': {'rear': 0.722, 'front': 0.706}}
frame = fb.leg_parts().parts['hip_frame']
print(variant, 'frame vol', round(frame.val().Volume() / 1000, 1), flush=True)
rad = lambda f, x=0.0, z=0.0: math.hypot(f.center[0] - x, f.center[2] - z)
half = lambda f: max(f.bbox[3] - f.bbox[0], f.bbox[5] - f.bbox[2]) / 2
yc = fb.Y['centre_plane']
flange_inserts = lambda f: f.kind == 'Plane' and abs(f.center[1] - yc) < 0.05
(ax_, _), (bx_, _) = fb.motors()
seat_at = lambda x: (lambda f: f.kind == 'Cylinder' and rad(f, x) < 0.5 and abs(half(f) - gmi.STD['AC-L']['bearing_od'] / 2) < 0.15)
lugs_at = lambda x: (lambda f: f.kind == 'Cylinder' and abs(rad(f, x) - 53.0) < 1.0 and half(f) < 4.6)
c = C[case]; ld = c['loads']
Ff, Fr = ld['F_C_on_upper'], ld['F_D_on_upper']; Mx, Mz = ld['M_B_out']; tf, tr = ld['tau']
sr, sf = SH[case]['rear'], SH[case]['front']; Fy = c['Fw3'][1]
st = Study(frame, MATERIALS['pa6_cf_z'], mesh_mm=float(__import__('os').environ.get('MESH', '4')), name=f'hip_frame {case} {variant}')
st.fix(flange_inserts)
st.force(seat_at(ax_), (Ff[0], sf * Fy, Ff[1]))
st.force(seat_at(bx_), (Fr[0], sr * Fy, Fr[1]), probe=False)
for x_, share in ((bx_, sr), (ax_, sf)):
    ls.couple(st, seat_at(x_), (share * Mx, 0.0, share * Mz))
ls.couple(st, lugs_at(ax_), (0.0, tf, 0.0)); ls.couple(st, lugs_at(bx_), (0.0, tr, 0.0))
r = st.solve()
free = ~st._touches_bc
cc = st.points[st.tets[:, :4]].mean(axis=1)
order = np.argsort(np.where(free, st.vm_elem, -1.0))[::-1][:8]
print(variant, case, 'SF', r['safety_factor'], 'design', r['von_mises_design_mpa'], flush=True)
for i in order:
    print('   %.1f MPa at (%.1f, %.1f, %.1f)' % (st.vm_elem[i], *cc[i]), flush=True)
