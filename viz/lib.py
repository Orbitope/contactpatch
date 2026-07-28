import math, random


def esc(s):
    """XML-escape text for an SVG text node. See viz.diagram.esc."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
BG="#1a1a1c"; FG="#e8e4dd"; MUT="#6f6a63"; GRID="#2e2e31"
AMB="#e0a53c"; COR="#e2614a"; TEAL="#4aa8a0"; VIO="#8a7bd8"; SLATE="#7f8ea3"; GRN="#7fa86a"

def head(w,h,title,sub):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family="Inter, system-ui, sans-serif"><rect width="{w}" height="{h}" fill="{BG}"/>'
            f'<text x="40" y="46" fill="{FG}" font-size="21" font-weight="600">{esc(title)}</text>'
            f'<text x="40" y="70" fill="{MUT}" font-size="13">{esc(sub)}</text>')

def foot(w,h,note="Mockup with synthetic data."):
    return f'<text x="40" y="{h-18}" fill="{MUT}" font-size="11" font-style="italic">{esc(note)}</text></svg>'

def path(p): return "M "+" L ".join(f"{x:.1f},{y:.1f}" for x,y in p)

def ramp(u):
    u=max(0.0,min(1.0,u))
    if u<0.5:
        k=u/0.5; return (int(74+(224-74)*k), int(168+(165-168)*k), int(160+(60-160)*k))
    k=(u-0.5)/0.5; return (int(224+(226-224)*k), int(165+(97-165)*k), int(60+(74-60)*k))

def diverge(u):
    # -1..1  teal <-> coral
    u=max(-1.0,min(1.0,u))
    if u<0:
        k=-u; return (int(46+(74-46)*k), int(46+(168-46)*k), int(49+(160-49)*k))
    k=u; return (int(46+(226-46)*k), int(46+(97-46)*k), int(49+(74-49)*k))

def axes(s,L,R,T,B,xl,yl,xt=None,yt=None,fmtx="{:.2f}",fmty="{:.2f}"):
    s+=f'<line x1="{L}" y1="{B}" x2="{R}" y2="{B}" stroke="{MUT}" stroke-width="1"/>'
    s+=f'<line x1="{L}" y1="{T}" x2="{L}" y2="{B}" stroke="{MUT}" stroke-width="1"/>'
    if xt:
        for v,px in xt:
            s+=f'<text x="{px:.0f}" y="{B+20}" fill="{MUT}" font-size="11" text-anchor="middle">{v}</text>'
    if yt:
        for v,py in yt:
            s+=f'<text x="{L-10}" y="{py+4:.0f}" fill="{MUT}" font-size="11" text-anchor="end">{v}</text>'
    s+=f'<text x="{(L+R)/2}" y="{B+46}" fill="{FG}" font-size="12.5" text-anchor="middle">{xl}</text>'
    s+=f'<text x="{L-58}" y="{(T+B)/2}" fill="{FG}" font-size="12.5" text-anchor="middle" transform="rotate(-90 {L-58} {(T+B)/2})">{yl}</text>'
    return s

def grid(s,L,R,T,B,nx=5,ny=5):
    for i in range(1,nx):
        x=L+(R-L)*i/nx; s+=f'<line x1="{x:.0f}" y1="{T}" x2="{x:.0f}" y2="{B}" stroke="{GRID}" stroke-width="1"/>'
    for j in range(1,ny):
        y=T+(B-T)*j/ny; s+=f'<line x1="{L}" y1="{y:.0f}" x2="{R}" y2="{y:.0f}" stroke="{GRID}" stroke-width="1"/>'
    return s
