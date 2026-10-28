"""Bent and flat sheet parts for SendCutSend, from one definition: the formed solid (STEP), the flat pattern (DXF with
the bend centrelines on their own layer), and the shop's rules checked (body_params.STOCK, SCS_RULES, PEM).

A part is a flat BASE (OML size W x H, its outer face on z = 0, the material z 0..t) with FLANGES on some of its four
edges, all bent 90 deg the same way (+z); a part whose flanges must point down is placed upside down. Edge names:
'S' (v = 0), 'N' (v = H), 'W' (u = 0), 'E' (u = W). Flange lengths are outside mold lines (OML: from the base's outer
face to the flange's free edge). Flanges on two adjacent edges stop at the other's bend (an open corner) with a round
relief where the two bends meet.

Features (holes, PEM nuts, countersinks, slots, windows) are placed on a panel in that panel's own coordinates:
  base       (u, v)
  N, S       (u, w): u along the edge as on the base, w = OML height above the base's outer face (z in the part frame)
  E, W       (v, w)
The flat pattern keeps the base's flat region where it is and lays each bend (its bend allowance) and flange beyond it.

This is generic (any channel or tray); it may move to cad-agent once the body's parts have been cut.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import cadquery as cq

import body_params as bp

EDGES = ('S', 'N', 'W', 'E')


@dataclass
class Feature:
    kind: str                     # 'hole' | 'pem' | 'csk' | 'slot' | 'relief' | 'cutout'
    panel: str                    # 'base' or an edge name
    at: tuple                     # panel coordinates of the centre
    d: float = 0.0                # hole diameter (pem: drawn at the PEM H size; csk: the through hole)
    size: tuple = ()              # slot: (length along the panel's first axis, width, corner radius)
    spec: str = ''                # pem: 'SS-M5-0'; csk: 'M3'
    note: str = ''
    side: str = 'z0'              # csk: the face the countersink opens on ('z0' the base's outer face, 'z1' the inner)
    make: object = None           # cutout (base panel only): make(t) -> a cq solid in base coordinates through the sheet


@dataclass
class Flange:
    edge: str
    length: float                 # OML
    span: tuple = None            # (a, b) along the edge, OML coordinates of the base; None: as far as the corners allow


@dataclass
class SheetPart:
    name: str
    stock: str
    W: float
    H: float
    flanges: list = field(default_factory=list)
    features: list = field(default_factory=list)
    qty: int = 1
    outline: list = None          # base: a polygon [(u, v)] instead of the W x H rectangle (flat parts only)
    note: str = ''

    # -------------------------------------------------------------------- geometry
    @property
    def s(self):
        return bp.STOCK[self.stock]

    @property
    def t(self):
        return self.s['t']

    def fl(self, edge):
        return next((f for f in self.flanges if f.edge == edge), None)

    def flat_box(self):
        """The base's flat region (u0, u1, v0, v1): the OML box less a setback where a flange is."""
        o = self.s.get('ossb', 0.0)
        return (o if self.fl('W') else 0.0, self.W - (o if self.fl('E') else 0.0),
                o if self.fl('S') else 0.0, self.H - (o if self.fl('N') else 0.0))

    def span(self, f: Flange):
        u0, u1, v0, v1 = self.flat_box()
        if f.span:
            return f.span
        return (u0, u1) if f.edge in ('S', 'N') else (v0, v1)

    def corners(self):
        """The points where two bends meet (relief centres), in base coordinates."""
        u0, u1, v0, v1 = self.flat_box()
        out = []
        for a, b, p in (('S', 'W', (u0, v0)), ('S', 'E', (u1, v0)), ('N', 'W', (u0, v1)), ('N', 'E', (u1, v1))):
            if self.fl(a) and self.fl(b):
                out.append(p)
        return out

    def solid(self) -> cq.Workplane:
        """The formed part in its own frame (base outer face z = 0, flanges towards +z)."""
        t = self.t
        u0, u1, v0, v1 = self.flat_box()
        if self.outline:
            s = cq.Workplane('XY').polyline(self.outline).close().extrude(t)
        else:
            s = cq.Workplane('XY').box(u1 - u0, v1 - v0, t, centered=False).translate((u0, v0, 0))
        for f in self.flanges:
            s = s.union(self._flange_solid(f))
        for c in self.corners():
            s = s.cut(cq.Workplane('XY').center(*c).circle(self.t).extrude(4 * self.s['ossb'] + 2).translate((0, 0, -1)))
        for ft in self.features:
            s = s.cut(self._feature_cut(ft))
        return s

    def _flange_solid(self, f: Flange):
        """The bend (a quarter annulus round the bend axis) and the flange's flat slab, for one edge."""
        t, r, L = self.t, self.s['r'], f.length
        a, b = self.span(f)
        u0, u1, v0, v1 = self.flat_box()
        sgn = {'N': 1, 'E': 1, 'S': -1, 'W': -1}[f.edge]
        c0 = {'N': v1, 'S': v0, 'E': u1, 'W': u0}[f.edge]          # the bend axis, across the edge, at z = t + r
        cz = t + r

        def arc(rad, angles):
            return [(c0 + sgn * rad * math.cos(math.radians(q)), cz + rad * math.sin(math.radians(q))) for q in angles]
        po, pi = arc(r + t, (-90, -45, 0)), arc(r, (0, -45, -90))
        plane = 'YZ' if f.edge in ('N', 'S') else 'XZ'           # sketch across the edge, extrude along it
        w = (cq.Workplane(plane).moveTo(*po[0]).threePointArc(po[1], po[2]).lineTo(*pi[0]).threePointArc(pi[1], pi[2]).close())
        if f.edge in ('N', 'S'):
            bend = w.extrude(b - a).translate((a, 0, 0))
            v_in = c0 + r if sgn > 0 else c0 - r - t                # the flange slab: v from its inner to its outer face
            slab = cq.Workplane('XY').box(b - a, t, L - cz, centered=False).translate((a, v_in, cz))
        else:
            bend = w.extrude(-(b - a)).translate((0, a, 0))          # 'XZ' extrudes along -y: negative = towards +y
            u_in = c0 + r if sgn > 0 else c0 - r - t
            slab = cq.Workplane('XY').box(t, b - a, L - cz, centered=False).translate((u_in, a, cz))
        return bend.union(slab)

    def to3d(self, ft: Feature):
        """(point, normal) of a feature's centre on the formed part's outer face."""
        u0, u1, v0, v1 = self.flat_box()
        if ft.panel == 'base':
            return (ft.at[0], ft.at[1], 0.0), (0, 0, 1)
        p, w = ft.at
        return {'N': ((p, self.H, w), (0, -1, 0)), 'S': ((p, 0.0, w), (0, 1, 0)),
                'E': ((self.W, p, w), (-1, 0, 0)), 'W': ((0.0, p, w), (1, 0, 0))}[ft.panel]

    def _feature_cut(self, ft: Feature):
        t = self.t
        if ft.kind == 'cutout':
            return ft.make(t)
        (x, y, z), n = self.to3d(ft)
        depth = t + 2.0
        if ft.kind == 'slot':
            L, Wd, rc = ft.size
            prof = lambda wp: wp.rect(L, Wd).extrude(depth).edges('|Z').fillet(min(rc, Wd / 2 - 0.01, L / 2 - 0.01)) if rc > 0 else wp.rect(L, Wd).extrude(depth)
            if ft.panel == 'base':
                return prof(cq.Workplane('XY').center(x, y)).translate((0, 0, -1))
            if ft.panel in ('N', 'S'):
                return prof(cq.Workplane('XZ').center(x, z)).translate((0, y + (1 if ft.panel == 'N' else depth - 1), 0))
            return prof(cq.Workplane('YZ').center(y, z)).translate((x - (depth - 1) if ft.panel == 'E' else x - 1, 0, 0))
        d = ft.d
        if ft.panel == 'base':
            c = cq.Workplane('XY').center(x, y).circle(d / 2).extrude(depth).translate((0, 0, -1))
            if ft.kind == 'csk':
                hd = CSK_HEAD[ft.spec]
                if ft.side == 'z0':
                    cone = cq.Solid.makeCone(hd / 2, 0.0, hd / 2, cq.Vector(x, y, -0.001), cq.Vector(0, 0, 1))
                else:
                    cone = cq.Solid.makeCone(hd / 2, 0.0, hd / 2, cq.Vector(x, y, t + 0.001), cq.Vector(0, 0, -1))
                c = c.union(cq.Workplane('XY').add(cone))
            return c
        if ft.panel in ('N', 'S'):
            return cq.Workplane('XZ').center(x, z).circle(d / 2).extrude(depth).translate((0, y + (1 if ft.panel == 'N' else depth - 1), 0))
        return cq.Workplane('YZ').center(y, z).circle(d / 2).extrude(depth).translate((x - (depth - 1) if ft.panel == 'E' else x - 1, 0, 0))

    # -------------------------------------------------------------------- flat pattern
    def to_flat(self, ft: Feature):
        """A feature's centre in the flat pattern."""
        if ft.panel == 'base':
            return ft.at
        u0, u1, v0, v1 = self.flat_box()
        o, ba = self.s['ossb'], self.s['ba']
        p, w = ft.at
        e = w - o                                                  # along the flange's flat, from where its bend ends
        return {'N': (p, v1 + ba + e), 'S': (p, v0 - ba - e), 'E': (u1 + ba + e, p), 'W': (u0 - ba - e, p)}[ft.panel]

    def flat_regions(self):
        """Rectangles (u0, u1, v0, v1) of the flat pattern: the base's flat, each bend allowance, each flange's flat;
        each tagged with its panel."""
        u0, u1, v0, v1 = self.flat_box()
        out = [('base', (u0, u1, v0, v1))]
        if not self.flanges:
            return out
        o, ba = self.s['ossb'], self.s['ba']
        for f in self.flanges:
            a, b = self.span(f)
            e = f.length - o
            if f.edge == 'N':
                out += [('bend_N', (a, b, v1, v1 + ba)), ('N', (a, b, v1 + ba, v1 + ba + e))]
            elif f.edge == 'S':
                out += [('bend_S', (a, b, v0 - ba, v0)), ('S', (a, b, v0 - ba - e, v0 - ba))]
            elif f.edge == 'E':
                out += [('bend_E', (u1, u1 + ba, a, b)), ('E', (u1 + ba, u1 + ba + e, a, b))]
            elif f.edge == 'W':
                out += [('bend_W', (u0 - ba, u0, a, b)), ('W', (u0 - ba - e, u0 - ba, a, b))]
        return out

    def bend_lines(self):
        """Bend centrelines in the flat: [((x0, y0), (x1, y1), edge)]."""
        u0, u1, v0, v1 = self.flat_box()
        ba = self.s.get('ba', 0.0)
        out = []
        for f in self.flanges:
            a, b = self.span(f)
            if f.edge == 'N':
                out.append(((a, v1 + ba / 2), (b, v1 + ba / 2), 'N'))
            elif f.edge == 'S':
                out.append(((a, v0 - ba / 2), (b, v0 - ba / 2), 'S'))
            elif f.edge == 'E':
                out.append(((u1 + ba / 2, a), (u1 + ba / 2, b), 'E'))
            elif f.edge == 'W':
                out.append(((u0 - ba / 2, a), (u0 - ba / 2, b), 'W'))
        return out

    def flat_solid(self) -> cq.Workplane:
        """The flat blank as a solid (t thick): what the laser cuts."""
        t = self.t
        regs = self.flat_regions()
        if self.outline:
            s = cq.Workplane('XY').polyline(self.outline).close().extrude(t)
        else:
            s = None
            for _, (a, b, c, d) in regs:
                bx = cq.Workplane('XY').box(b - a, d - c, t, centered=False).translate((a, c, 0))
                s = bx if s is None else s.union(bx)
        if self.outline and len(regs) > 1:
            raise ValueError('an outline is for flat parts only')
        for c in self.corners():
            s = s.cut(cq.Workplane('XY').center(*c).circle(self.t).extrude(t + 2).translate((0, 0, -1)))
        for ft in self.features:
            if ft.kind == 'cutout':                                 # base-panel cutouts: the flat is the base there
                s = s.cut(ft.make(t))
                continue
            x, y = self.to_flat(ft)
            if ft.kind == 'slot':
                L, Wd, rc = ft.size
                if ft.panel in ('E', 'W'):                          # the slot's long side runs along the edge (v)
                    L, Wd = Wd, L
                if ft.panel in ('N', 'S'):                          # flange slots: along the edge (u) x along the flange
                    pass
                cut = cq.Workplane('XY').center(x, y).rect(L, Wd).extrude(t + 2).translate((0, 0, -1))
                if rc > 0:
                    cut = cut.edges('|Z').fillet(min(rc, Wd / 2 - 0.01, L / 2 - 0.01))
            else:
                cut = cq.Workplane('XY').center(x, y).circle(ft.d / 2).extrude(t + 2).translate((0, 0, -1))
            s = s.cut(cut)
        return s

    def export_dxf(self, path: Path):
        """The flat pattern: CUT layer (outline and holes, from the blank's top face), BEND layer (dashed centrelines).
        Millimetres."""
        import ezdxf
        from cadquery.occ_impl.exporters.dxf import DxfDocument
        top = self.flat_solid().faces('>Z').val()
        doc = DxfDocument(setup=True)
        doc.add_shape(cq.Workplane('XY').add(top).val().translate(cq.Vector(0, 0, -self.t)))
        d = doc.document
        d.header['$INSUNITS'] = 4
        for e in d.modelspace():
            e.dxf.layer = 'CUT'
        if 'DASHED' not in d.linetypes:
            d.linetypes.add('DASHED', pattern=[10.0, 6.0, -4.0], description='bend line')
        d.layers.add('BEND', color=1, linetype='DASHED')
        for (p, q, _) in self.bend_lines():
            d.modelspace().add_line(p, q, dxfattribs={'layer': 'BEND', 'linetype': 'DASHED'})
        d.saveas(str(path))
        return path

    # -------------------------------------------------------------------- rules
    def checks(self) -> list:
        """SendCutSend's rules: [text] of every violation (empty = orderable as drawn)."""
        s, t = self.s, self.t
        bad = []
        regs = self.flat_regions()
        xs = [r[1][0] for r in regs] + [r[1][1] for r in regs]
        ys = [r[1][2] for r in regs] + [r[1][3] for r in regs]
        fw, fh = max(xs) - min(xs), max(ys) - min(ys)
        lo, hi = sorted((fw, fh)), sorted(bp.SCS_RULES['max_flat_in'])
        if lo[0] > hi[0] * bp.IN or lo[1] > hi[1] * bp.IN:
            bad.append(f'flat {fw:.0f} x {fh:.0f} mm is over the instant-price size')
        if self.flanges and not s['bend']:
            bad.append(f'{s["material"]} {s["t_in"]} in is not bent by SendCutSend')
        services = [k for k, on in (('bending', bool(self.flanges)), ('hardware', any(f.kind == 'pem' for f in self.features)),
                                    ('countersinking', any(f.kind == 'csk' for f in self.features)),
                                    ('tapping', any(f.note.startswith('tap ') for f in self.features))) if on]
        narrow = min(self.flat_size())
        if services and narrow < bp.SCS_RULES['min_width_for_services_in'] * bp.IN - 1e-6:
            bad.append(f'{", ".join(services)} on a part {narrow:.1f} mm wide: SendCutSend does no service on a part under '
                       f'{bp.SCS_RULES["min_width_for_services_in"]} in wide')
        for f in self.flanges:
            if f.length < s['min_flange'] - 1e-6:
                bad.append(f'flange {f.edge} {f.length} mm < minimum {s["min_flange"]:.2f}')
        for a, b in (('S', 'N'), ('W', 'E')):
            if self.fl(a) and self.fl(b):
                base = (self.H if a == 'S' else self.W)
                fmax = max(self.fl(a).length, self.fl(b).length)
                if base < bp.SCS_RULES['channel_base_to_flange'] * fmax:
                    bad.append(f'channel base {base} < 2 x flange {fmax} ({a}/{b})')
        lines = self.bend_lines()
        hd = s.get('half_die', 0.0)
        bend_regs = [r for n, r in regs if n.startswith('bend_')]
        bad += self._cutout_checks()
        for ft in self.features:
            if ft.kind in ('relief', 'cutout'):
                continue
            x, y = self.to_flat(ft)
            rad = (max(ft.size[0], ft.size[1]) / 2 if ft.kind == 'slot' else ft.d / 2)
            if ft.kind in ('hole', 'csk', 'pem') and ft.d < bp.SCS_RULES['min_hole_frac_t'] * t - 1e-6:
                bad.append(f'{ft.kind} Ø{ft.d} at {ft.at} on {ft.panel} is smaller than half the thickness')
            if ft.kind == 'csk' and not s['countersink']:
                bad.append(f'countersink at {ft.at}: {s["material"]} {s["t_in"]} in is not countersunk by SendCutSend')
            if ft.kind == 'csk' and (CSK_HEAD[ft.spec] - ft.d) / 2 > CSK_MAX_DEPTH_FRAC * t:
                bad.append(f'countersink {ft.spec} at {ft.at}: {(CSK_HEAD[ft.spec] - ft.d) / 2:.2f} mm deep in a {t:.2f} mm sheet')
            for (p, q, e) in lines:
                dist = _seg_dist((x, y), p, q) - (_slot_half_across((x, y), p, q, ft) if ft.kind == 'slot' else rad)
                if dist < hd - 1e-6:
                    bad.append(f'{ft.kind} at {ft.at} on {ft.panel}: {dist:.2f} mm from bend {e} centreline (< {hd:.2f})')
            # inside the blank, with a web of at least the thickness to the cut edge
            reg = next(r for n, r in regs if n == ft.panel)
            edge = min(x - reg[0], reg[1] - x, y - reg[2], reg[3] - y) if not self.outline else _poly_edge_dist((x, y), self.outline)
            if ft.kind == 'slot' and ft.panel == 'base' and not self.flanges:     # a slot's own outline, not a circle round it
                pts = _slot_outline((x, y), ft.size)
                web = min((_poly_edge_dist(q, self.outline) if self.outline else min(q[0] - reg[0], reg[1] - q[0], q[1] - reg[2], reg[3] - q[1]))
                          for q in pts)
                if web < t - 1e-6:
                    bad.append(f'slot at {ft.at} on base: web to the edge {web:.2f} mm < t')
            elif ft.panel != 'base' or not self.flanges:
                if edge - rad < t - 1e-6:
                    bad.append(f'{ft.kind} at {ft.at} on {ft.panel}: web to the edge {edge - rad:.2f} mm < t')
            else:                                                       # base features: the base's outer cut edges only
                u0, u1, v0, v1 = self.flat_box()
                outer = []
                if not self.fl('W'):
                    outer.append(x - u0)
                if not self.fl('E'):
                    outer.append(u1 - x)
                if not self.fl('S'):
                    outer.append(y - v0)
                if not self.fl('N'):
                    outer.append(v1 - y)
                if outer and min(outer) - rad < t - 1e-6:
                    bad.append(f'{ft.kind} at {ft.at}: web to the edge {min(outer) - rad:.2f} mm < t')
            if ft.kind == 'pem':
                P = bp.PEM[ft.spec]
                if not s['hardware']:
                    bad.append(f'PEM {ft.spec}: no hardware in this stock')
                if t < P['min_sheet_in'] * bp.IN:
                    bad.append(f'PEM {ft.spec}: sheet thinner than {P["min_sheet_in"]} in')
                if edge < P['K'] - 1e-6:
                    bad.append(f'PEM {ft.spec} at {ft.at} on {ft.panel}: {edge:.2f} mm to the edge < K {P["K"]:.2f}')
                for (a, b, c, d) in bend_regs:
                    dd = _box_dist((x, y), (a, b, c, d))
                    if dd < P['N'] - 1e-6:
                        bad.append(f'PEM {ft.spec} at {ft.at} on {ft.panel}: {dd:.2f} mm to the bend area < N {P["N"]:.2f}')
        pem = [(self.to_flat(f), f.spec) for f in self.features if f.kind == 'pem']
        for i in range(len(pem)):
            for j in range(i + 1, len(pem)):
                if pem[i][1] == pem[j][1] and math.dist(pem[i][0], pem[j][0]) < bp.PEM[pem[i][1]]['M'] - 1e-6:
                    bad.append(f'PEM {pem[i][1]} at {pem[i][0]} and {pem[j][0]} closer than M')
        # features apart from each other by at least the thickness
        holes = [(self.to_flat(f), (f.d / 2 if f.kind != 'slot' else None), f) for f in self.features if f.kind in ('hole', 'pem', 'csk')]
        for i in range(len(holes)):
            for j in range(i + 1, len(holes)):
                (p, r1, _), (q, r2, _) = holes[i], holes[j]
                if math.dist(p, q) - r1 - r2 < min(t, 2.0) - 1e-6:
                    bad.append(f'holes at {p} and {q}: web {math.dist(p, q) - r1 - r2:.2f} mm < t')
        return bad

    def _cutout_checks(self) -> list:
        """A cutout keeps a web of at least the thickness to the part's outline and to every hole, PEM and slot."""
        cuts = [f for f in self.features if f.kind == 'cutout']
        if not cuts:
            return []
        t, bad = self.t, []
        u0, u1, v0, v1 = self.flat_box()
        if self.outline:
            prism = cq.Workplane('XY').polyline(self.outline).close().extrude(t)
        else:
            prism = cq.Workplane('XY').box(u1 - u0, v1 - v0, t, centered=False).translate((u0, v0, 0))
        big = cq.Workplane('XY').box(u1 - u0 + 200, v1 - v0 + 200, t, centered=False).translate((u0 - 100, v0 - 100, 0))
        outside = big.cut(prism).val()
        others = [f for f in self.features if f.kind in ('hole', 'pem', 'csk', 'slot')]
        for c in cuts:
            cs = c.make(t).val()
            d = cs.distance(outside)
            if d < t - 1e-6:
                bad.append(f'cutout {c.note!r}: web to the outline {d:.2f} mm < t')
            for o in others:
                do = cs.distance(self._feature_cut(o).val())
                if do < min(t, 2.0) - 1e-6:
                    bad.append(f'cutout {c.note!r}: web to the {o.kind} at {o.at} {do:.2f} mm < t')
                if o.kind == 'pem':                                  # a PEM nut's centre K from any cut edge
                    k = bp.PEM[o.spec]['K']
                    dc = cs.distance(cq.Vertex.makeVertex(o.at[0], o.at[1], t / 2))
                    if dc < k - 1e-6:
                        bad.append(f'PEM {o.spec} at {o.at}: {dc:.2f} mm to the cutout < K {k:.2f}')
        return bad

    def flat_size(self):
        regs = self.flat_regions()
        if self.outline:
            xs = [p[0] for p in self.outline]
            ys = [p[1] for p in self.outline]
            return (max(xs) - min(xs), max(ys) - min(ys))
        xs = [r[1][0] for r in regs] + [r[1][1] for r in regs]
        ys = [r[1][2] for r in regs] + [r[1][3] for r in regs]
        return (max(xs) - min(xs), max(ys) - min(ys))

    def order(self) -> dict:
        """What the SendCutSend cart needs for this part."""
        s = self.s
        pem = {}
        for f in self.features:
            if f.kind == 'pem':
                pem[f.spec] = pem.get(f.spec, 0) + 1
        csk = {}
        for f in self.features:
            if f.kind == 'csk':
                csk[f.spec] = csk.get(f.spec, 0) + 1
        w, h = self.flat_size()
        return {'material': s['material'], 'thickness_in': s['t_in'], 'thickness_mm': round(self.t, 3), 'qty': self.qty,
                'flat_mm': [round(w, 1), round(h, 1)], 'bends': len(self.flanges),
                'bend_spec': ({'inside_radius_in': s['r_in'], 'k_factor': s['k'], 'bend_deduction_in': s['bd_in']} if self.flanges else None),
                'hardware': pem, 'countersinks': csk, 'note': self.note}


CSK_HEAD = {'M3': 6.72, 'M4': 8.96, 'M5': 11.2}       # ISO 10642 flat heads, max head diameter (90 deg)
CSK_MAX_DEPTH_FRAC = 0.75                              # a countersink no deeper than this share of the sheet


def _seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    k = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + k * dx), py - (ay + k * dy))


def _slot_half_across(p, a, b, ft):
    """A slot's half-extent towards a bend line (its size across that direction)."""
    L, Wd, _ = ft.size
    horizontal_line = abs(b[1] - a[1]) < 1e-9
    if ft.panel in ('E', 'W'):
        L, Wd = Wd, L
    return Wd / 2 if horizontal_line else L / 2


def _box_dist(p, box):
    a, b, c, d = box
    dx = max(a - p[0], 0.0, p[0] - b)
    dy = max(c - p[1], 0.0, p[1] - d)
    return math.hypot(dx, dy)


def _slot_outline(c, size, n=8):
    """Points on a base slot's rounded-rectangle outline (its corners' arcs sampled), centre c, size (L, W, r)."""
    L, Wd, rc = size
    rc = max(0.0, min(rc, Wd / 2 - 0.01, L / 2 - 0.01))
    out = []
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        cx, cy = c[0] + sx * (L / 2 - rc), c[1] + sy * (Wd / 2 - rc)
        a0 = math.atan2(sy, sx)
        for k in range(n + 1):
            a = a0 - math.pi / 4 + (math.pi / 2) * k / n
            out.append((cx + rc * math.cos(a), cy + rc * math.sin(a)))
    return out


def _poly_edge_dist(p, poly):
    return min(_seg_dist(p, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))
