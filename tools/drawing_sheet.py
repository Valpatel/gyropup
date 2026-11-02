"""Assembly drawing sheets from the CAD: hidden-line views, balloons keyed to BOM item numbers, dimensions, a parts
list and a title block, written as PDF pages and PNGs (tools/motor_day.py, issue #156).

    from drawing_sheet import Sheet, Part
    s = Sheet('Hip module', number='MD-01', revision='abc1234')
    s.view('front', parts, direction=(0, -1, 0), up=(0, 0, 1), box=(0.02, 0.30, 0.56, 0.66))
    s.dim('front', (x0, y, z), (x1, y, z), offset=-25)            # a dimension between two 3D points, in mm
    s.parts_list(rows)                                            # [(item, qty, name, source)]
    s.save(pdf_pages, png_path)

Why not an existing tool: cad-agent has no 2D drawing code; the vendored build123d-mcp drawing skill and text-to-cad's
cadgen draw dimensioned single parts (no balloons, no parts list) and need build123d, which this environment does not
have. This module uses OCP's hidden-line removal on the cadquery shapes directly and matplotlib for the sheet.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Rectangle  # noqa: E402
from OCP.BRep import BRep_Tool  # noqa: E402
from OCP.BRepAdaptor import BRepAdaptor_Curve  # noqa: E402
from OCP.GCPnts import GCPnts_QuasiUniformDeflection  # noqa: E402
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt  # noqa: E402
from OCP.HLRAlgo import HLRAlgo_Projector  # noqa: E402
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape  # noqa: E402
from OCP.TopAbs import TopAbs_EDGE  # noqa: E402
from OCP.TopExp import TopExp_Explorer  # noqa: E402
from OCP.TopoDS import TopoDS  # noqa: E402

A3 = (420.0, 297.0)          # mm, landscape
INK, HIDDEN, DIM, BALLOON = '#1d2025', '#9aa0a8', '#b75a18', '#142b38'
MM = 1 / 25.4


@dataclass
class Part:
    """One part (or a group of identical parts) in a view: its shape(s) and the BOM item its balloon shows."""
    shapes: Sequence
    item: Optional[int] = None
    label: str = ''


@dataclass
class _View:
    name: str
    box: tuple                   # (x0, y0, w, h) as fractions of the drawable area
    proj: HLRAlgo_Projector
    vis: list = field(default_factory=list)
    hid: list = field(default_factory=list)
    anchors: list = field(default_factory=list)      # (item, (u, v))
    dims: list = field(default_factory=list)
    title: str = ''
    scale: float = 1.0
    origin: tuple = (0.0, 0.0)


def _wrapped(s):
    s = s.val() if hasattr(s, 'val') else s
    return s.wrapped if hasattr(s, 'wrapped') else s


def _polylines(compound, deflection: float) -> list:
    out = []
    if compound is None or compound.IsNull():
        return out
    ex = TopExp_Explorer(compound, TopAbs_EDGE)
    while ex.More():
        e = TopoDS.Edge_s(ex.Current())
        try:
            c = BRepAdaptor_Curve(e)
            d = GCPnts_QuasiUniformDeflection(c, deflection)
            if d.IsDone() and d.NbPoints() > 1:
                pts = [d.Value(i) for i in range(1, d.NbPoints() + 1)]
                out.append([(p.X(), p.Y()) for p in pts])
        except Exception:                      # an edge with no curve: skip it
            pass
        ex.Next()
    return out


def projector(direction, up) -> HLRAlgo_Projector:
    """Looking along `direction` (from the viewer into the part), `up` pointing up on the sheet."""
    d = gp_Dir(*[-c for c in direction])       # gp_Ax2's main direction points at the viewer
    u = gp_Dir(*up)
    xdir = gp_Dir(*_cross(up, [-c for c in direction]))
    del u
    return HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), d, xdir))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def project_point(proj: HLRAlgo_Projector, p) -> tuple:
    from OCP.gp import gp_Pnt2d
    q = gp_Pnt2d()
    proj.Project(gp_Pnt(*p), q)
    return (q.X(), q.Y())


def hidden_lines(shapes, proj: HLRAlgo_Projector, deflection: float = 0.3, hidden: bool = True):
    algo = HLRBRep_Algo()
    for s in shapes:
        algo.Add(_wrapped(s))
    algo.Projector(proj)
    algo.Update()
    algo.Hide()
    h = HLRBRep_HLRToShape(algo)
    vis = []
    for c in (h.VCompound(), h.OutLineVCompound(), h.Rg1LineVCompound()):
        vis += _polylines(c, deflection)
    hid = _polylines(h.HCompound(), deflection) if hidden else []
    return vis, hid


def _size(shape) -> float:
    s = shape.val() if hasattr(shape, 'val') else shape
    bb = s.BoundingBox()
    return bb.xlen * bb.ylen * bb.zlen


def _anchor(part: 'Part', proj, taken, gap: float):
    """Where a balloon's leader ends: a vertex of the part (so it lands on a drawn line) near the middle of its
    projected outline, kept `gap` away from the anchors already placed."""
    s = part.shapes[0]
    s = s.val() if hasattr(s, 'val') else s
    c = project_point(proj, _centre(s))
    vs = s.Vertices()
    step = max(1, len(vs) // 300)
    cands = [project_point(proj, (v.X, v.Y, v.Z)) for v in vs[::step]] or [c]
    def cost(q):
        near = min((math.dist(q, t) for t in taken), default=1e9)
        return math.dist(q, c) + (1e6 if near < gap else 0.0)
    return min(cands, key=cost)


def _centre(shape):
    s = shape.val() if hasattr(shape, 'val') else shape
    try:
        c = s.Center()
        return (c.x, c.y, c.z)
    except Exception:
        bb = s.BoundingBox()
        return ((bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2, (bb.zmin + bb.zmax) / 2)


class Sheet:
    def __init__(self, title: str, number: str, revision: str, subtitle: str = '', project: str = 'GYROPUP',
                 notes: Sequence[str] = ()):
        self.title, self.number, self.revision, self.subtitle, self.project = title, number, revision, subtitle, project
        self.notes = list(notes)
        self.views: list[_View] = []
        self.rows: list = []

    def view(self, name: str, parts: Sequence[Part], direction, up, box, title: str = '', hidden: bool = True,
             deflection: float = 0.3, balloons: bool = True):
        proj = projector(direction, up)
        shapes = [s for p in parts for s in p.shapes]
        vis, hid = hidden_lines(shapes, proj, deflection, hidden)
        v = _View(name, box, proj, vis, hid, title=title or name)
        if balloons:
            pts = [q for pl in vis for q in pl[::4]]
            span = max(max(q[0] for q in pts) - min(q[0] for q in pts), max(q[1] for q in pts) - min(q[1] for q in pts)) if pts else 1.0
            for p in sorted((p for p in parts if p.item is not None), key=lambda p: -_size(p.shapes[0])):
                v.anchors.append((p.item, _anchor(p, proj, [a for _, a in v.anchors], 0.04 * span)))
        self.views.append(v)
        return v

    def dim(self, view: str, p1, p2, offset: float = 15.0, text: Optional[str] = None, fmt: str = '{:.0f}'):
        v = next(x for x in self.views if x.name == view)
        a, b = project_point(v.proj, p1), project_point(v.proj, p2)
        v.dims.append((a, b, offset, text if text is not None else fmt.format(math.dist(a, b))))

    def parts_list(self, rows):
        self.rows = list(rows)

    # ------------------------------------------------------------------------------------------- drawing

    def _layout(self, area):
        ax0, ay0, aw, ah = area
        for v in self.views:
            pts = [p for pl in v.vis + v.hid for p in pl] + [a for _, a in v.anchors]
            for a, b, off, _ in v.dims:
                pts += [a, b]
            if not pts:
                continue
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            w, h = max(xs) - min(xs) or 1.0, max(ys) - min(ys) or 1.0
            bx, by, bw, bh = v.box
            bw_mm, bh_mm = bw * aw * 0.78, bh * ah * 0.72            # room for the balloons round it
            v.scale = min(bw_mm / w, bh_mm / h)
            cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
            v.origin = (ax0 + (bx + bw / 2) * aw - cx * v.scale, ay0 + (by + bh / 2) * ah - cy * v.scale)

    def _xy(self, v, p):
        return (v.origin[0] + p[0] * v.scale, v.origin[1] + p[1] * v.scale)

    def render(self):
        fig = plt.figure(figsize=(A3[0] * MM, A3[1] * MM))
        ax = fig.add_axes((0, 0, 1, 1))
        ax.set_xlim(0, A3[0])
        ax.set_ylim(0, A3[1])
        ax.set_aspect('equal')
        ax.axis('off')
        ax.add_patch(Rectangle((8, 8), A3[0] - 16, A3[1] - 16, fill=False, lw=0.9, ec=INK))
        table_w = 128.0
        area = (12.0, 52.0, A3[0] - 24.0 - table_w, A3[1] - 64.0)
        self._area = area
        self._layout(area)
        for v in self.views:
            for pl in v.hid:
                xy = [self._xy(v, p) for p in pl]
                ax.plot(*zip(*xy), color=HIDDEN, lw=0.35, ls=(0, (2.5, 1.5)))
            for pl in v.vis:
                xy = [self._xy(v, p) for p in pl]
                ax.plot(*zip(*xy), color=INK, lw=0.55)
            bx, by, bw, bh = v.box
            ax.text(area[0] + (bx + bw / 2) * area[2], area[1] + by * area[3] + 1, f'{v.title.upper()}   scale 1:{1 / v.scale:.1f}',
                    ha='center', va='bottom', fontsize=6.5, color=INK, family='DejaVu Sans')
            for a, b, off, text in v.dims:
                self._draw_dim(ax, v, a, b, off, text)
            self._balloons(ax, v)
        self._table(ax, table_w)
        self._title_block(ax, table_w)
        return fig

    def _draw_dim(self, ax, v, a, b, off, text):
        A, B = self._xy(v, a), self._xy(v, b)
        dx, dy = B[0] - A[0], B[1] - A[1]
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        o = off * v.scale if abs(off * v.scale) > 6 else math.copysign(6, off)
        A2, B2 = (A[0] + nx * o, A[1] + ny * o), (B[0] + nx * o, B[1] + ny * o)
        for P, P2 in ((A, A2), (B, B2)):
            ax.plot([P[0] + nx * math.copysign(1, o), P2[0] + nx * math.copysign(1.5, o)],
                    [P[1] + ny * math.copysign(1, o), P2[1] + ny * math.copysign(1.5, o)], color=DIM, lw=0.35)
        ax.annotate('', xy=B2, xytext=A2, arrowprops=dict(arrowstyle='<|-|>', color=DIM, lw=0.45, mutation_scale=5,
                                                          shrinkA=0, shrinkB=0))
        ang = math.degrees(math.atan2(dy, dx))
        if ang > 90 or ang < -90:
            ang += 180
        mx, my = (A2[0] + B2[0]) / 2 + nx * 1.6 * math.copysign(1, o), (A2[1] + B2[1]) / 2 + ny * 1.6 * math.copysign(1, o)
        ax.text(mx, my, text, rotation=ang, ha='center', va='center', fontsize=6.2, color=DIM,
                bbox=dict(fc='white', ec='none', pad=0.3))

    def _balloons(self, ax, v):
        """Balloons on the edge of the view's own box, where a ray from the drawing's centre through the anchor meets
        it, spread along that edge so none overlap (in the order round the box, so leaders do not cross)."""
        if not v.anchors:
            return
        pts = [self._xy(v, a) for _, a in v.anchors]
        allp = [self._xy(v, p) for pl in v.vis for p in pl[::3]] or pts
        x0, x1 = min(p[0] for p in allp) - 7, max(p[0] for p in allp) + 7
        y0, y1 = min(p[1] for p in allp) - 7, max(p[1] for p in allp) + 7
        A = self._area
        bx, by, bw, bh = v.box
        X0, Y0 = A[0] + bx * A[2] + 5, A[1] + by * A[3] + 7
        X1, Y1 = A[0] + (bx + bw) * A[2] - 5, A[1] + (by + bh) * A[3] - 5
        x0, x1, y0, y1 = max(X0, min(x0, X1)), min(X1, max(x1, X0)), max(Y0, min(y0, Y1)), min(Y1, max(y1, Y0))
        # the ring the balloons sit on: half-way between the drawing and the box edge
        rx0, rx1, ry0, ry1 = (X0 + x0) / 2, (X1 + x1) / 2, (Y0 + y0) / 2, (Y1 + y1) / 2
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        W, H = rx1 - rx0, ry1 - ry0
        per = 2 * (W + H)

        def to_t(P):                                 # where the ray from the centre through P meets the ring
            dx, dy = P[0] - cx, P[1] - cy
            if abs(dx) < 1e-9 and abs(dy) < 1e-9:
                dx = 1.0
            k = min((W / 2) / abs(dx) if dx else 1e9, (H / 2) / abs(dy) if dy else 1e9)
            qx, qy = cx + dx * k, cy + dy * k
            if abs(qy - ry1) < 1e-6:
                return qx - rx0
            if abs(qx - rx1) < 1e-6:
                return W + (ry1 - qy)
            if abs(qy - ry0) < 1e-6:
                return W + H + (rx1 - qx)
            return 2 * W + H + (qy - ry0)

        def at(t):
            t %= per
            if t < W:
                return (rx0 + t, ry1)
            if t < W + H:
                return (rx1, ry1 - (t - W))
            if t < 2 * W + H:
                return (rx1 - (t - W - H), ry0)
            return (rx0, ry0 + (t - 2 * W - H))
        order = sorted(range(len(pts)), key=lambda i: to_t(pts[i]))
        ts = [to_t(pts[i]) for i in order]
        gap = min(9.0, per / max(1, len(ts)))
        for k in range(1, len(ts)):
            ts[k] = max(ts[k], ts[k - 1] + gap)
        over = ts[-1] - (ts[0] + per - gap) if ts else 0
        if over > 0:                                 # wrapped onto the first: shift them all back
            ts = [t - over for t in ts]
        for k, i in enumerate(order):
            item, _ = v.anchors[i]
            P = pts[i]
            Q = at(ts[k])
            ax.plot([P[0], Q[0]], [P[1], Q[1]], color=BALLOON, lw=0.4)
            ax.add_patch(Circle(P, 0.7, color=BALLOON))
            ax.add_patch(Circle(Q, 3.6, fc='white', ec=BALLOON, lw=0.7, zorder=5))
            ax.text(Q[0], Q[1], str(item), ha='center', va='center', fontsize=6.5, color=BALLOON, zorder=6, weight='bold')

    def _table(self, ax, w):
        x0, y_top = A3[0] - 8 - w, A3[1] - 8
        cols = (11, 14, w - 11 - 14 - 40, 40)
        heads = ('ITEM', 'QTY/LEG', 'PART', 'SOURCE')
        rh = 4.6
        y = y_top - rh
        ax.add_patch(Rectangle((x0, y), w, rh, fc='#142b38', ec=INK, lw=0.5))
        x = x0
        for c, h in zip(cols, heads):
            ax.text(x + 1.2, y + rh / 2, h, va='center', fontsize=5.6, color='white', weight='bold')
            x += c
        for r in self.rows:
            y -= rh
            if y < 56:
                ax.text(x0 + 1.2, y + rh / 2, '... (the full list is in bom.csv)', va='center', fontsize=5.2, color=INK)
                break
            ax.add_patch(Rectangle((x0, y), w, rh, fill=False, ec='#c9ced6', lw=0.3))
            x = x0
            for c, t in zip(cols, r):
                t = str(t)
                lim = int(c / 1.3)
                ax.text(x + 1.2, y + rh / 2, t if len(t) <= lim else t[:lim - 1] + '…', va='center', fontsize=5.2, color=INK)
                x += c
        ny = y - 3
        for n in self.notes:
            words, line, lines = n.split(), '', []
            for wd in words:
                if len(line) + len(wd) + 1 > 92:
                    lines.append(line)
                    line = wd
                else:
                    line = (line + ' ' + wd).strip()
            lines.append(line)
            for ln in lines:
                if ny < 56:
                    break
                ax.text(x0 + 1.2, ny, ln, va='top', fontsize=5.0, color=INK)
                ny -= 3.0
            ny -= 1.0

    def _title_block(self, ax, w):
        x0, y0, h = A3[0] - 8 - w, 8.0, 44.0
        ax.add_patch(Rectangle((x0, y0), w, h, fill=False, ec=INK, lw=0.8))
        ax.add_patch(Rectangle((x0, y0 + h - 10), w, 10, fc='#e8892b', ec=INK, lw=0.5))
        ax.text(x0 + 3, y0 + h - 5, self.project, va='center', fontsize=9, weight='bold', color='#1d2025')
        ax.text(x0 + w - 3, y0 + h - 5, self.number, va='center', ha='right', fontsize=9, weight='bold', color='#1d2025')
        ax.text(x0 + 3, y0 + h - 16, self.title, va='center', fontsize=10, weight='bold', color=INK)
        if self.subtitle:
            ax.text(x0 + 3, y0 + h - 23, self.subtitle, va='center', fontsize=6.2, color=INK)
        rows = [('UNITS', 'mm'), ('SOURCE', self.revision), ('FROM', 'tools/motor_day.py'), ('STATUS', 'unqualified: not a release')]
        for k, (a, b) in enumerate(rows):
            yy = y0 + 15 - k * 3.6
            ax.text(x0 + 3, yy, a, fontsize=5.4, color='#5a5f68')
            ax.text(x0 + 22, yy, b, fontsize=5.6, color=INK)

    def save(self, pdf=None, png=None, dpi: int = 150):
        fig = self.render()
        if pdf is not None:
            pdf.savefig(fig)
        if png is not None:
            fig.savefig(png, dpi=dpi, facecolor='white')
        plt.close(fig)
