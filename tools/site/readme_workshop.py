#!/usr/bin/env python3
"""Original fictional Gyropup proving-ground scene; no engineering verdict.

Render/check with the pinned cad-agent SVG component, not a CAD kernel:
  python tools/site/readme_workshop.py --svg-library <cad-agent>/software/cadagent/publish/anim/svg.py [--check]
The explicit still is selected by README picture markup in the parent page.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[2]
LIBRARY_SHA = "bd1f3965ba4c7d03656bf49878416a47be3626256625fd3ba75fe20d9de17dbb"
OUT = ROOT / "docs/img/navigation/project-map.svg"
TITLE = ROOT / "docs/img/hero/gyropup-title.svg"
# These destinations remain ordinary accessible Markdown links below the scene.
DESTINATIONS = ("https://gyropup.com/designer/sim.html", "https://gyropup.com/designer/build.html", "docs/README.md#design-and-qualification", ".github/CONTRIBUTING.md")


def library(filename):
    if hashlib.sha256(filename.read_bytes()).hexdigest() != LIBRARY_SHA:
        raise ValueError("Use the reviewed cad-agent SVG component bytes")
    spec = importlib.util.spec_from_file_location("gyropup_workshop_svg", filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build(svg, *, still=False):
    body = []
    def rect(x, y, w, h, fill, extra=""):
        body.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" {extra}/>')
    def path(d, fill, extra=""):
        body.append(f'<path d="{d}" fill="{fill}" {extra}/>')
    def g(transform="", cls=""):
        body.append(f'<g transform="{transform}" class="{cls}">')
    def end(): body.append('</g>')
    def line(d, colour, width=2, extra=""):
        path(d, "none", f'stroke="{colour}" stroke-width="{width}" {extra}')
    def lamp(x,y,colour="#95f5e8"):
        rect(x-4,y-4,8,8,colour); rect(x-2,y-2,4,4,"#edfff7")
    def gear(x,y,colour,cls="machine"):
        g(f'translate({x} {y})'); g("",cls)
        path("M-18-8h10v-10H8v10h10V8H8v10H-8V8h-10z",colour)
        rect(-7,-7,14,14,"#10192c"); rect(-3,-3,6,6,"#a0d6d0")
        end();end()
    def wheel(x, y, colour, cls):
        g(f'translate({x} {y}) scale(1.3)')
        # Stepped sidewalls, recessed rim and four rotating spokes.
        path("M-22-14h8v-8h28v8h8v28h-8v8h-28v-8h-8z","#0a1221")
        path("M-18-12h6v-6h24v6h6v24h-6v6h-24v-6h-6z","#304458")
        path("M-17-12h5v-5h24v5h5v6h-5v-6h-24v6h-5z","#789190")
        for xx,yy in [(-22,-8),(-22,6),(18,-8),(18,6),(-8,-22),(6,-22),(-8,18),(6,18)]:
            rect(xx,yy,4,4,"#536375")
        g("",cls)
        path("M-3-16H3v10h3v3h10V3H6v3H3v10H-3V6h-3V3h-10V-3h10v-3h3z",colour)
        end()
        rect(-6,-6,12,12,"#0c1828"); rect(-3,-3,6,6,"#d6f8e8")
        end()
    def pup(x,y,scale,side,colour,cls,spokes="wheel-a",battle=""):
        g(f'translate({x} {y})');g("",cls);g(f'scale({scale})');g(f'scale({side} 1)')
        # Ground contact / soft stepped cast shadow stays beneath the suspension.
        path("M-75 18h136v7h-136z","#0b1727",'opacity=".6"')
        g("","suspension")
        # Far linkage and far tyre, then underbody and foreground linkage.
        line("M-35-61L-50-4L3-39L36-5L32-60","#30465a",12)
        wheel(-45,0,colour,spokes);wheel(45,0,colour,spokes)
        line("M-36-61L-43-16L-2-43L43-16L35-61","#ccdcba",8)
        line("M-31-61L-39-18M-1-43L39-18","#508f91",3)
        for xx,yy in [(-36,-61),(-43,-16),(-2,-43),(43,-16),(35,-61)]:
            rect(xx-5,yy-5,10,10,"#15283c");rect(xx-2,yy-2,4,4,colour)
        g("","body-bob")
        path("M-54-105L35-105L61-89V-59L35-49H-42L-58-65z","#142436")
        path("M-54-105L35-105L61-89H-31z",colour)
        path("M-31-89H61V-59L35-49H-31z","#286a7d" if battle!='b' else "#70436f")
        path("M-54-99L-31-83V-56L-51-66z","#425566")
        path("M-27-84H51V-65L30-57H-27z","#0b192a")
        rect(-20,-80,55,7,"#8ffff2");rect(35,-80,9,7,"#f4fff5")
        rect(-18,-69,8,3,"#d6bd76");rect(-4,-69,21,3,"#528282")
        rect(-45,-94,8,20,"#1a2e42");rect(-43,-92,4,7,"#e6c888")
        line("M-51-103H32L54-90","#fff0b3",3)
        # Turret, optic and foam-ball barrel: unmistakably wheeled Gyropup.
        rect(-11,-117,38,12,"#1b2e3d");rect(-7,-119,29,4,"#94ae9d")
        g("","recoil"+battle)
        path("M-12-135H32L46-124V-111H-12z",colour)
        path("M-10-135H30L42-125H-10z","#f4df9b" if battle!='b' else "#ddabd2")
        rect(28,-127,49,14,"#17394b");rect(43,-125,35,4,"#9bcebe")
        rect(73,-129,10,18,"#0c1929");rect(77,-124,6,8,"#96fff0")
        rect(-23,-130,9,18,"#142335");rect(-21,-128,5,5,"#ffcd70")
        end()
        line("M-39-107V-135H-32","#badad0",3);lamp(-32,-136)
        end();end()
        if battle:
            g('translate(83 -119)',"shot-"+battle)
            path("M0-6H280V6H0z","#46ded5" if battle=='a' else "#ff80d6",'opacity=".18"')
            path("M0-3H280V3H0z","#a8fff0" if battle=='a' else "#ffd0f0")
            path("M0-1H280V1H0z","#ffffff")
            path("M-4-10H4V-4H12V4H4V10H-4V4H-10V-4H-4z","#fff3ae")
            end()
            g('translate(83 -119)',"shield-"+battle)
            path("M-8-32L5-24L12-8V8L5 24L-8 32","none",'stroke="#76fff2" stroke-width="5"')
            for dx,dy in [(10,-17),(20,4),(5,24)]:
                path(f"M{dx} {dy}h6v-6h3v9h-9z","#ffe9a7")
            end()
        end();end();end();end()

    rect(0,0,1280,480,"#101a33")
    rect(0,0,1280,190,"#17213f")
    # Fixed star map, drifting sparse high clouds; no strobing backgrounds.
    for i in range(62):
        x=(i*173+31)%1272;y=(i*53+17)%171
        rect(x,y,2 if i%3 else 4,2 if i%3 else 4,"#7b9ba9" if i%4 else "#dfd5a9")
    g('translate(1096 79)')
    path("M-42-22h12v-12h60v12h12v44H30v12h-60V22h-12z","#45646c")
    path("M-30-26H6V-34H30V-22H42V0H14V10H-4V24H-30V12H-42V-10H-30z","#739286")
    line("M-75 25L-38 5L35-9L77-28","#b7b294",5)
    line("M-78 30L-38 10L35-4L80-23","#4b6b80",3);end()
    for x,y,scale in [(138,63,.8),(923,39,.5)]:
        g(f'translate({x} {y})');g('',"satellite");g(f'scale({scale})')
        rect(-9,-9,18,18,"#d9cda0");rect(-45,-13,28,26,"#357987");rect(17,-13,28,26,"#357987")
        for z in [-39,-30,23,32]:line(f'M{z}-12V12',"#79bfc0",2)
        line('M-17 0H17M0-9V-25',"#bbc1ab",3);lamp(0,-25);end();end();end()
    # The orbital depot has lit docking bays, solar ribs and a little courier.
    g('translate(663 60)')
    path('M-96 0l30-17H35l27 17-27 17H-66z',"#2e455c")
    path('M-66-17H35L62 0H-39z',"#65807c")
    rect(-43,-7,77,14,"#132b42")
    for xx in [-34,-16,2,20]:rect(xx,-3,10,5,"#cbbd81")
    for xx in [-101,75]:
        rect(xx,-23,27,47,"#345a71")
        for yy in [-18,-8,2,12]:line(f'M{xx+3} {yy}h21',"#689b9b",2)
    line('M-75 0h-26M62 0H75',"#b3bb99",3)
    end()
    g('translate(730 109)');g('',"courier-drone")
    path('M-24-4h13v-8H8v8h18V4H8v8H-11V4H-24z',"#718f91")
    rect(-8,-6,15,12,"#d4c799");lamp(16,0)
    path('M-24-2h-12v4h12z',"#69d8d2",'opacity=".6"')
    end();end()
    # Three depth planes of terraced architecture and a luminous test course.
    for i in range(18):
        x=i*77-15;h=30+(i*31)%62
        rect(x,202-h,60,h,"#25344c");rect(x+6,208-h,42,5,"#415366")
        for wy in range(211-h,195,13):rect(x+11,wy,5,4,"#567778")
    for x in [367,762,1016]:
        line(f'M{x} 158v-29m-10 6h20',"#60797f",2)
        rect(x-3,124,6,5,"#d4a87f")
    line('M0 203H1280',"#568081",3)
    rect(0,205,1280,53,"#223747");line('M0 252H1280',"#759a91",3)
    # Left archive and assembly bay, patterned roof and articulated tool arms.
    path('M0 182L45 151H259L287 181V296H0z',"#24394b")
    path('M0 182L45 151H259L287 181z',"#70847b")
    for x in range(26,274,25):line(f'M{x} 178l24-23',"#a2a78a",3)
    rect(14,188,260,8,"#a5af88");rect(24,204,95,84,"#14293b")
    for yy in range(213,283,21):
        rect(29,yy+16,82,3,"#6c807b")
        for k,c in enumerate(["#dcb87a","#689b9d","#97af77","#a38291","#b9bf94"]):
            rect(34+k*15,yy,10,16,c);rect(36+k*15,yy+3,5,2,"#f5e7b0")
    rect(133,203,124,82,"#102436")
    for x in [144,177,210,243]:
        rect(x,211,6,45,"#315665");lamp(x+3,218)
    g('translate(190 218)');g('',"assembler")
    path('M-5-7H5V22H28V32H-5z',"#b7bd96");rect(23,27,16,14,"#477f83")
    line('M31 40v9m-7-9v9',"#d4d9ac",3);end();end()
    gear(151,274,"#8fb79f");gear(241,274,"#aaad7f")
    # Elevated bridge and moving distant pups.
    rect(292,252,803,9,"#688880");rect(292,261,803,10,"#1a293c")
    for x in range(311,1090,36):rect(x,262,16,3,"#ccbf84")
    for x in [355,650,971]:rect(x,270,12,54,"#344c5b")
    pup(465,244,.36,1,"#84b6a0","far-pup","wheel-a")
    pup(883,244,.32,-1,"#bb91a6","far-rival","wheel-b")
    # Gantry, tool trolley, cable trays and workshop indicators.
    for x in [1117,1245]:
        rect(x,185,14,152,"#405a64");rect(x+2,188,3,142,"#8da59b")
    rect(1117,180,142,13,"#a5ab87");rect(1120,194,136,8,"#26364a")
    for x in range(1129,1252,17):path(f'M{x} 181h8l-8 10h-8z',"#374b58")
    g('translate(1160 207)');g('',"trolley")
    rect(-16,-6,32,13,"#c2b17e");line('M0 7v48',"#819b95",3)
    path('M-12 55h24v8h-7v9H-5v-9h-7z',"#c5c5a1");end();end()
    for i in range(5):
        rect(1137+i*20,310,14,20,"#365461");rect(1141+i*20,314,5,5,"#99c6ae")
    # Control console and moving conveyor stock give the workshop its own life.
    rect(1037,272,62,42,"#183142");rect(1041,276,54,23,"#386c72")
    line('M1045 289h9l5-8 6 14 7-10h17',"#aeefd1",2)
    for xx in [1046,1060,1074,1088]:lamp(xx,307,"#b4b285")
    rect(1045,314,7,16,"#7b9385");rect(1086,314,7,16,"#7b9385")
    g('translate(64 304)');g('',"stock")
    path('M0 0l14-8 24 8v22H0z',"#80967e")
    path('M14-8L38 0 24 8 0 0z',"#c6c093")
    line('M6 7v10m6-8v10m6-8v10',"#3a6063",2);end();end()
    for xx in range(20,252,18):
        rect(xx,331,10,5,"#799389");rect(xx+2,332,5,2,"#d2c29a")
    line('M13 337H271',"#182c3b",6)
    for x,y in [(213,264),(1200,290)]:
        g(f'translate({x} {y})');g('',"weld")
        path('M-3-3h6v6h-6zM-12-7h4v3h-4zM9 5h4v3H9zM-5 9h3v5h-3z',"#f4d68c")
        end();end()
    # Ground plane: tiled perspective, amber landing edge, ports and foreground moss.
    path('M0 290H1280V392H0z',"#29434b")
    for y in [303,325,354,385]:line(f'M0 {y}H1280',"#4b6665",2)
    for x in range(-80,1400,96):line(f'M{x} 290l-70 102',"#36525a",2)
    path('M0 384H1280V391H0z',"#b3a578")
    for x in range(0,1280,54):path(f'M{x} 385h26l-6 5h-26z',"#5e6457")
    for x in [88,564,1072]:
        path(f'M{x} 352h65v8h-65z',"#152c3a");rect(x+6,353,48,2,"#7dcac0")
    # Main paired duel. Geometry/action positions intentionally share a 440-unit gap at fire cues.
    pup(360,355,1,1,"#f2c274","runner-a","wheel-a","a")
    pup(920,355,1,-1,"#cb8dd8","runner-b","wheel-b","b")
    # Foreground rail and low foliage frame, without covering wheel contact.
    rect(0,390,1280,90,"#111f31");line('M0 391H1280',"#819882",2)
    for x in [0,46,1210,1255]:
        path(f'M{x} 389v-14h6v7h7v-14h6v20z',"#658466")
        rect(x+3,386,12,3,"#b6ba7b")
    # The complete learning route is visible without animation, with a fixed return arrow.
    line('M112 402H1153',"#759c99",2)
    for x in [145,470,795,1110]:
        lamp(x,402,"#d3bc7b")
    for x in [320,645,970]:path(f'M{x-5} 398l8 4-8 4z',"#99d7c8")
    line('M1110 408V466H57V402H113',"#577e82",2,'stroke-dasharray="5 6"')
    path('M107 398l9 4-9 4z',"#a5d8bd")
    for label,x in [("Sources",145),("Test",470),("Review",795),("Reuse",1110)]:
        body.append(f'<text x="{x}" y="442" text-anchor="middle" fill="#d8e6cb" font-family="monospace" font-weight="700" font-size="31">{label}</text>')
    g('translate(112 402)',"courier")
    rect(-4,-4,8,8,"#fff0b8");end()

    css = """
svg{max-width:100%;height:auto} g{transform-box:view-box}
.runner-a{transform:translateX(80px);animation:chase-a 24s linear infinite}
.runner-b{transform:translateX(-40px);animation:chase-b 24s linear infinite}
.wheel-a{animation:wheel-a 24s linear infinite}.wheel-b{animation:wheel-b 24s linear infinite}
.suspension{animation:suspension .8s steps(2,end) infinite}.body-bob{animation:bob 1.6s steps(2,end) infinite}
.recoila{animation:recoil-a 24s linear infinite}.recoilb{animation:recoil-b 24s linear infinite}
.shot-a{opacity:.65;animation:shot-a 24s linear infinite}.shot-b{opacity:0;animation:shot-b 24s linear infinite}
.shield-a{opacity:0;animation:hit-a 24s linear infinite}.shield-b{opacity:.7;animation:hit-b 24s linear infinite}
.far-pup{animation:far-a 24s linear infinite}.far-rival{animation:far-b 30s linear infinite}
.satellite{animation:orbit 24s ease-in-out infinite}.machine{animation:gear 8s steps(16,end) infinite}
.assembler{animation:tool 6s ease-in-out infinite}.trolley{animation:trolley 14s ease-in-out infinite}
.courier{animation:courier 18s linear infinite}.courier-drone{animation:drone 20s ease-in-out infinite}
.stock{animation:stock 9s linear infinite}.weld{animation:weld 4s steps(2,end) infinite}
@keyframes chase-a{0%,100%{transform:translateX(0) rotate(0deg)}4%{transform:translateX(40px) rotate(-4deg)}8%,32%{transform:translateX(80px) rotate(0deg)}40%{transform:translateX(140px) rotate(-5deg)}48%,70%{transform:translateX(200px) rotate(0deg)}80%{transform:translateX(120px) rotate(4deg)}90%{transform:translateX(40px) rotate(0deg)}}
@keyframes chase-b{0%,100%{transform:translateX(0) rotate(0deg)}4%{transform:translateX(-20px) rotate(4deg)}8%,32%{transform:translateX(-40px) rotate(0deg)}40%{transform:translateX(20px) rotate(-5deg)}48%,70%{transform:translateX(80px) rotate(0deg)}80%{transform:translateX(30px) rotate(4deg)}90%{transform:translateX(-20px) rotate(0deg)}}
@keyframes wheel-a{0%,100%{transform:rotate(0deg)}8%,32%{transform:rotate(208deg)}48%,70%{transform:rotate(521deg)}90%{transform:rotate(104deg)}}
@keyframes wheel-b{0%,100%{transform:rotate(0deg)}8%,32%{transform:rotate(-104deg)}48%,70%{transform:rotate(208deg)}90%{transform:rotate(-52deg)}}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-2px)}}
@keyframes suspension{0%,100%{transform:translateY(0)}50%{transform:translateY(1px)}}
@keyframes recoil-a{0%,17%,24%,57%,64%,100%{transform:translateX(0)}19%,59%{transform:translateX(-5px)}}
@keyframes recoil-b{0%,25%,32%,65%,70%,100%{transform:translateX(0)}27%,67%{transform:translateX(-5px)}}
@keyframes shot-a{0%,17%,24%,57%,64%,100%{opacity:0}18%,23%,58%,63%{opacity:.8}}
@keyframes shot-b{0%,25%,32%,65%,70%,100%{opacity:0}26%,31%,66%,69%{opacity:.8}}
@keyframes hit-a{0%,25%,32%,65%,70%,100%{opacity:0}26%,31%,66%,69%{opacity:.85}}
@keyframes hit-b{0%,17%,24%,57%,64%,100%{opacity:0}18%,23%,58%,63%{opacity:.85}}
@keyframes far-a{0%,100%{transform:translateX(0)}50%{transform:translateX(200px)}}
@keyframes far-b{0%,100%{transform:translateX(0)}50%{transform:translateX(-180px)}}
@keyframes orbit{0%,100%{transform:translate(0,0)}50%{transform:translate(18px,6px)}}
@keyframes gear{to{transform:rotate(360deg)}}
@keyframes tool{0%,100%{transform:rotate(-12deg)}50%{transform:rotate(18deg)}}
@keyframes trolley{0%,100%{transform:translateX(0)}50%{transform:translateX(50px)}}
@keyframes courier{0%,100%{transform:translate(0,0)}60%{transform:translate(998px,0)}65%{transform:translate(998px,64px)}95%{transform:translate(-55px,64px)}99%{transform:translate(-55px,0)}}
@keyframes drone{0%,100%{transform:translate(0,0)}50%{transform:translate(-180px,14px)}}
@keyframes stock{0%,100%{transform:translateX(0)}90%{transform:translateX(150px)}91%,99%{opacity:0;transform:translateX(150px)}}
@keyframes weld{0%,40%,80%,100%{opacity:.15;transform:translateY(0)}45%,65%{opacity:.85;transform:translateY(3px)}}
""" + svg.REDUCED_MOTION
    if still:
        css += "\n*{animation:none!important}\n"
    return svg.document(640,240,"Gyropup — a pixel proving ground"+(" (still)" if still else ""),
        "Original fictional robot playground: wheeled leg robots chase, fire light pulses and test shields amid a working archive and factory. Sources, test, review and reuse form a complete return loop. This illustration does not depict a verified physical capability.",css,body,background=False)


def wordmark(svg, *, still=False):
    """A quiet, sharp title above the unchanged moving proving ground."""
    body = [
        '<defs><linearGradient id="pup-metal" x1="0" y1="0" x2="0" y2="1">'
        '<stop stop-color="#fff8d7"/><stop offset=".40" stop-color="#f1d291"/>'
        '<stop offset=".43" stop-color="#84f5dd"/><stop offset="1" stop-color="#3a9cab"/>'
        '</linearGradient><linearGradient id="pup-trail"><stop stop-color="#418f99" stop-opacity="0"/>'
        '<stop offset=".5" stop-color="#78d6c2"/><stop offset="1" stop-color="#418f99" stop-opacity="0"/>'
        '</linearGradient></defs>',
        '<g fill="none" stroke="#477e89" stroke-width="3">'
        '<path d="M12 112h105l26-26h64m1066 26h-105l-26-26h-64"/>'
        '<path d="M56 133h90l20-20h34m1024 20h-90l-20-20h-34"/>'
        '<path d="M180 160h920" stroke="url(#pup-trail)"/>'
        '</g>',
        '<g fill="#e9cd8b" stroke="#163344" stroke-width="3">'
        '<path d="M126 78l8 8-8 8-8-8zM1154 78l8 8-8 8-8-8z"/>'
        '</g>',
    ]
    face = ('text-anchor="middle" font-family="Arial Black,Arial,Helvetica,sans-serif" '
            'font-size="166" font-weight="900" letter-spacing="-5" '
            'stroke-linejoin="round" paint-order="stroke fill"')
    body += [
        f'<text x="645" y="137" {face} fill="#173d50" stroke="#102437" stroke-width="14">Gyropup</text>',
        f'<text x="640" y="128" {face} fill="url(#pup-metal)" stroke="#133143" stroke-width="6">Gyropup</text>',
        '<path d="M265 149h59m693 0h-59" fill="none" stroke="#efcf8a" stroke-width="3"/>',
        '<text x="640" y="192" text-anchor="middle" font-family="monospace" font-size="22" '
        'font-weight="700" letter-spacing="8" fill="#558a8e">ROLL · LEARN · REPEAT</text>',
        f'<defs><clipPath id="pup-face"><text x="640" y="128" {face}>Gyropup</text></clipPath></defs>',
        '<g clip-path="url(#pup-face)"><path class="title-glint" d="M-120-30h50l-60 190h-50z" fill="#fffce8" opacity=".5"/></g>',
        '<path class="title-spark" d="M180 157h8v6h-8z" fill="#f1cf87"/>',
    ]
    css = """svg{max-width:100%;height:auto}
.title-glint{animation:title-glint 8s linear infinite}.title-spark{animation:title-spark 8s linear infinite}
@keyframes title-glint{0%{transform:translateX(0)}45%,100%{transform:translateX(1600px)}}
@keyframes title-spark{0%,100%{transform:translateX(0)}50%{transform:translateX(912px)}}
""" + svg.REDUCED_MOTION
    if still:
        css += "\n*{animation:none!important}\n"
    return svg.document(640, 104, "Gyropup" + (" (still)" if still else ""),
                        "Gyropup. Roll, learn, repeat. A vector arcade title above the moving robot playground.",
                        css, body, background=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg-library",type=Path,required=True)
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    svg=library(args.svg_library)
    for output,content in [(OUT,build(svg)),(OUT.with_name("project-map-still.svg"),build(svg,still=True)),
                           (TITLE,wordmark(svg)),(TITLE.with_name("gyropup-title-still.svg"),wordmark(svg,still=True))]:
        problems=svg.problems(content)
        if problems: raise ValueError(problems)
        if args.check:
            if not output.is_file() or output.read_text()!=content:
                raise ValueError(f"{output.name} differs; run the documented generator")
        else: output.write_text(content)
    print("Arcade title, unchanged pixel scene and explicit still: deterministic parity and shared SVG safety passed")

if __name__=="__main__": main()
