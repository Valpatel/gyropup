"""The README banner: the current full assembly (exports/asm_*.step, written by cad/build.py) on a dark stage,
with the title on the left. Writes docs/hero.jpg.

    .venv/bin/python tools/readme_hero.py
"""
from pathlib import Path
import glob, os
import numpy as np, cadquery as cq, pyvista as pv
from PIL import Image, ImageDraw, ImageFont

R = Path(__file__).resolve().parents[1]
src = str(R / 'exports')
ACC = '#e8892b'
def colour(n):
    if any(k in n for k in ('thigh', 'shin', 'pushrod', 'knee_crank')): return ACC, 1.0
    if n.startswith('wheel_l') or n.startswith('wheel_r') or 'tyre' in n: return '#1b1e23', 1.0
    if 'motor_l' in n or 'motor_r' in n or n in ('flywheel', 'lidar'): return '#2b3038', 1.0
    if n in ('barrel',): return '#ff7a1a', 1.0
    if n.startswith('hopper') and 'flap' not in n: return '#9fc4e6', 0.45
    if n in ('face',): return '#e9edf2', 1.0
    if n.startswith('camera') and 'cradle' not in n: return '#111418', 1.0
    if n in ('chassis', 'electronics_bay', 'j501_box', 'battery_1'): return '#5c6673', 1.0
    return '#aeb6c2', 1.0
p = pv.Plotter(off_screen=True, window_size=(2400, 1100), lighting='three lights')
p.set_background('#0b0f14', top='#1d2733')
meshes = []
for f in sorted(glob.glob(os.path.join(src, 'asm_*.step'))):
    n = os.path.basename(f)[4:-5]
    shape = cq.importers.importStep(f).val()
    vs, ts = shape.tessellate(0.25, 0.3)
    if not ts: continue
    v = np.array([(q.x, q.y, q.z) for q in vs]); faces = np.hstack([[3, *t] for t in ts])
    m = pv.PolyData(v, faces).compute_normals(split_vertices=True, feature_angle=35)
    c, o = colour(n)
    p.add_mesh(m, color=c, opacity=o, smooth_shading=True, specular=0.35, specular_power=25, ambient=0.18)
    meshes.append(m)
allm = meshes[0].merge(meshes[1:])
b = allm.bounds; zmin = b[4]
cx, cy, cz = (b[0]+b[1])/2, (b[2]+b[3])/2, (b[4]+b[5])/2
span = max(b[1]-b[0], b[3]-b[2], b[5]-b[4])
floor = pv.Disc(center=(cx, cy, zmin - 0.5), inner=0, outer=span * 1.6, c_res=96, r_res=8)
p.add_mesh(floor, color='#121a22', ambient=0.4, specular=0.0)
grid = pv.Disc(center=(cx, cy, zmin - 0.4), inner=span * 0.2, outer=span * 1.6, c_res=48, r_res=12)
p.add_mesh(grid.extract_all_edges(), color='#1f6f7a', opacity=0.18, line_width=1)
# up axis: guess from bounds (the tallest axis is up for a standing robot)
up = (0, 0, 1)
d = np.array([1.0, -1.3, 0.32]); d /= np.linalg.norm(d)
p.camera_position = [(cx + d[0]*span*3, cy + d[1]*span*3, cz + d[2]*span*3), (cx, cy, cz), up]
p.camera.view_angle = 22
p.reset_camera(bounds=allm.bounds)
p.camera.zoom(1.22)
# slide the robot into the right half: move camera and focal point together, sideways in the view plane
import numpy as _np
fp=_np.array(p.camera.focal_point); pos=_np.array(p.camera.position); vu=_np.array(p.camera.up)
fwd=(fp-pos)/_np.linalg.norm(fp-pos); right=_np.cross(fwd,vu); right/=_np.linalg.norm(right)
shift=-right*span*0.42 - vu*span*0.03
p.camera.focal_point=tuple(fp+shift); p.camera.position=tuple(pos+shift)
p.enable_ssao(radius=span * 0.04) if hasattr(p, 'enable_ssao') else None
p.enable_anti_aliasing('ssaa')
img = p.screenshot(return_img=True)
p.close()

try:
    from cadagent.site import KIT_DIR
    FONTS = KIT_DIR / 'vendor' / 'fonts'
except ImportError:
    FONTS = Path('/nonexistent')


def font(name, size, fallback):
    try:
        f = ImageFont.truetype(str(FONTS / name), size)
        f.getbbox('A')
        return f
    except Exception:
        return ImageFont.truetype(fallback, size)


im = Image.fromarray(img).convert('RGB')
d = ImageDraw.Draw(im)
title = font('inter.woff2', 150, '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
try:
    title.set_variation_by_axes([800])
except Exception:
    pass
mono = font('jetbrains-mono.woff2', 34, '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')
text = font('inter.woff2', 44, '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
x, y = 150, 300
d.text((x, y - 70), 'SELF-BALANCING  ·  WHEEL-LEGGED', font=mono, fill='#e8892b')
d.text((x, y), 'Gyropup', font=title, fill='#f2f5f9')
for i, t in enumerate(['Two five-bar legs, four RS-04 actuators,', 'a foam-ball turret on top,', 'printed in PA6-CF, PETG and TPU.']):
    d.text((x, y + 210 + i * 62), t, font=text, fill='#aab4c2')
d.text((x, y + 430), 'DESIGNED · SIMULATED · CHECKED WITH CAD-AGENT', font=mono, fill='#5fd3e0')
im.save(R / 'docs' / 'hero.jpg', quality=88, optimize=True, progressive=True)
print('docs/hero.jpg', im.size)
