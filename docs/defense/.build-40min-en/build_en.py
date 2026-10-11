"""Build the 40-minute English defense deck and speaker-notes handout.

Design language: a traffic-signal timing diagram. Signal colours carry fixed meaning
(green = better / learned, amber = caution / exploratory, red = worse / limitation,
grey = fixed-time baseline, blue = pressure baselines).
"""
from __future__ import annotations

import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
IMG = {
    "junction": ROOT / "paper/figures/junction-schematic.png",
    "curves": ROOT / "results/danang_protocol_v1/summary/validation-learning-curves.png",
    "sensitivity": ROOT / "results/danang_protocol_v1/summary/demand-sensitivity.png",
    "demo": ROOT / "tmp/thesis-evidence/demo-final-review.png",
    "mc": ROOT / "results/danang_baseline_mc/baseline-mc-boxplot-deck.png",
    "cam_frame": ROOT / "results/camera_counts/caurong_20260711_1716/camera_annotated_frame.jpg",
    "cam_map": ROOT / "results/camera_counts/caurong_20260711_1716/only_car/markov_map_bare.png",
}
AUTHOR = "Luong Quang Khang"
C = dict(asphalt="#16212C", ink="#13202B", body="#34434F", muted="#71808C", rule="#D2D8D5",
         go="#1C9A73", caution="#E39B0B", stop="#D8443A", base="#8B97A1", pressure="#3A74C9",
         pressure2="#8FB1E3", lane="#E9ECE6", white="#FFFFFF", phaseB="#3E6E9A")
CAMERA = [("07", 1255), ("08", 2330), ("09", 1870), ("10", 1770), ("11", 1800), ("12", 1910),
          ("13", 1395), ("14", 1505), ("15", 1400), ("16", 1755), ("17", 2400), ("18", 2490)]


def img(k):
    return IMG[k].as_uri()


def n2(x, d=2):
    return f"{x:,.{d}f}"


def svg_open(w, h):
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" font-family="OP">'


# ------------------------------------------------------------------ visuals
def signal_head(lit="go", w=150, h=400):
    lamps = [("stop", C["stop"]), ("caution", C["caution"]), ("go", C["go"])]
    out = [svg_open(w, h), f'<rect x="{w/2-8}" y="{h-70}" width="16" height="70" fill="#2A3B4A"/>',
           f'<rect x="10" y="10" width="{w-20}" height="{h-90}" rx="30" fill="#0E171F" stroke="#2F4050" stroke-width="3"/>']
    step = (h - 110) / 3
    for i, (k, col) in enumerate(lamps):
        cy = 10 + step * (i + 0.5) + 5
        on = k == lit
        if on:
            out.append(f'<circle cx="{w/2}" cy="{cy:.0f}" r="{w*0.36:.0f}" fill="{col}" opacity=".18"/>')
        out.append(f'<circle cx="{w/2}" cy="{cy:.0f}" r="{w*0.26:.0f}" fill="{col if on else "#24313C"}"/>')
    out.append("</svg>")
    return "".join(out)


def cover_art():
    """Top-down intersection with signal heads and vehicles."""
    w, h = 620, 720
    cx, cy, rw = 330, 360, 150
    o = [svg_open(w, h)]
    o.append(f'<rect x="{cx-rw/2}" y="0" width="{rw}" height="{h}" fill="#1F2D3A"/>')
    o.append(f'<rect x="0" y="{cy-rw/2}" width="{w}" height="{rw}" fill="#1F2D3A"/>')
    for y in range(0, h, 34):
        if abs(y - cy) > rw / 2 + 30:
            o.append(f'<rect x="{cx-2}" y="{y}" width="4" height="18" fill="#4B5D6B"/>')
    for x in range(0, w, 34):
        if abs(x - cx) > rw / 2 + 30:
            o.append(f'<rect x="{x}" y="{cy-2}" width="18" height="4" fill="#4B5D6B"/>')
    for i in range(7):  # zebra crossings
        o.append(f'<rect x="{cx-rw/2+8+i*20}" y="{cy-rw/2-26}" width="11" height="20" fill="#3A4C5B"/>')
        o.append(f'<rect x="{cx-rw/2+8+i*20}" y="{cy+rw/2+6}" width="11" height="20" fill="#3A4C5B"/>')
        o.append(f'<rect x="{cx-rw/2-26}" y="{cy-rw/2+8+i*20}" width="20" height="11" fill="#3A4C5B"/>')
        o.append(f'<rect x="{cx+rw/2+6}" y="{cy-rw/2+8+i*20}" width="20" height="11" fill="#3A4C5B"/>')
    heads = [(cx - rw/2 - 16, cy - rw/2 - 16, C["go"]), (cx + rw/2 + 16, cy + rw/2 + 16, C["go"]),
             (cx + rw/2 + 16, cy - rw/2 - 16, C["stop"]), (cx - rw/2 - 16, cy + rw/2 + 16, C["stop"])]
    for x, y, col in heads:
        o.append(f'<circle cx="{x}" cy="{y}" r="22" fill="{col}" opacity=".2"/><circle cx="{x}" cy="{y}" r="10" fill="{col}"/>')
    # queues: waiting on red approaches, flowing on green
    for i in range(6):
        o.append(f'<rect x="{cx+rw/2+36+i*26}" y="{cy-50}" width="16" height="9" rx="3" fill="#9FB0BC"/>')
        o.append(f'<rect x="{cx-rw/2-52-i*26}" y="{cy+40}" width="16" height="9" rx="3" fill="#9FB0BC"/>')
    for i in range(4):
        o.append(f'<rect x="{cx-42}" y="{cy-rw/2-120-i*70}" width="9" height="16" rx="3" fill="#6FD3B0"/>')
        o.append(f'<rect x="{cx+34}" y="{cy+rw/2+90+i*70}" width="9" height="16" rx="3" fill="#6FD3B0"/>')
    o.append(f'<rect x="{cx-45}" y="{cy-20}" width="9" height="16" rx="3" fill="#6FD3B0"/>')
    o.append("</svg>")
    return "".join(o)


def cycle_vs_demand(w=660, h=300):
    left, right, top = 50, 16, 24
    ph = 170
    pw = w - left - right
    vmin, vmax = 1000, 2600
    xs = [left + pw * (i + .5) / 12 for i in range(12)]
    y = lambda v: top + ph - ph * (v - vmin) / (vmax - vmin)
    o = [svg_open(w, h)]
    for v in (1200, 1600, 2000, 2400):
        o.append(f'<line x1="{left}" x2="{w-right}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#E3E7E4"/>')
        o.append(f'<text x="{left-8}" y="{y(v)+4:.1f}" font-size="11.5" text-anchor="end" fill="{C["muted"]}">{v:,}</text>')
    pts = " ".join(f"{x:.1f},{y(v):.1f}" for x, (_, v) in zip(xs, CAMERA))
    area = f"{xs[0]:.1f},{top+ph} " + pts + f" {xs[-1]:.1f},{top+ph}"
    o.append(f'<polygon points="{area}" fill="{C["caution"]}" opacity=".12"/>')
    o.append(f'<polyline points="{pts}" fill="none" stroke="{C["ink"]}" stroke-width="3" stroke-linejoin="round"/>')
    for x, (hr, v) in zip(xs, CAMERA):
        col = {"08": C["stop"], "13": C["go"], "17": C["caution"]}.get(hr, C["ink"])
        r = 7 if col != C["ink"] else 4
        o.append(f'<circle cx="{x:.1f}" cy="{y(v):.1f}" r="{r}" fill="{col}" stroke="#fff" stroke-width="2"/>')
        o.append(f'<text x="{x:.1f}" y="{top+ph+18}" font-size="12" text-anchor="middle" fill="{C["muted"]}">{hr}:00</text>')
    for hr, lab, dy in (("08", "AM 2,330", -14), ("13", "normal 1,395", 22), ("17", "PM 2,400", -14)):
        i = [c[0] for c in CAMERA].index(hr)
        o.append(f'<text x="{xs[i]:.1f}" y="{y(CAMERA[i][1])+dy:.1f}" font-size="12.5" font-weight="800" text-anchor="middle" fill="{C["ink"]}">{lab}</text>')
    # repeating cycle tiles
    ty = top + ph + 34
    tiles = 12
    tw = pw / tiles
    for t in range(tiles):
        x0 = left + t * tw
        acc = 0
        for v, col in ((32, C["go"]), (7, C["caution"]), (28, C["phaseB"]), (7, C["caution"]), (22, C["stop"]), (7, C["caution"])):
            o.append(f'<rect x="{x0+tw*acc/103:.2f}" y="{ty}" width="{tw*v/103:.2f}" height="22" fill="{col}"/>')
            acc += v
    o.append(f'<text x="{left}" y="{ty+42}" font-size="13" font-weight="700" fill="{C["ink"]}">The same 103 s plan repeats all day</text>')
    o.append(f'<text x="{w-right}" y="{ty+42}" font-size="13" text-anchor="end" fill="{C["muted"]}">veh/h on the four camera movement lines, 1 Apr 2025</text>')
    o.append("</svg>")
    return "".join(o)


def grouped_bars(groups, series, values, vmax, w=640, h=360, unit="", tick=100):
    left, right, top, bottom = 56, 10, 22, 40
    pw, ph = w - left - right, h - top - bottom
    gw = pw / len(groups)
    bw = gw * 0.8 / len(series)
    o = [svg_open(w, h)]
    t = 0
    while t <= vmax:
        yy = top + ph - ph * t / vmax
        o.append(f'<line x1="{left}" x2="{w-right}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="#E3E7E4"/>')
        o.append(f'<text x="{left-8}" y="{yy+4:.1f}" font-size="12" text-anchor="end" fill="{C["muted"]}">{t}</text>')
        t += tick
    o.append(f'<text x="14" y="{top+ph/2}" font-size="12" fill="{C["muted"]}" transform="rotate(-90 14 {top+ph/2})" text-anchor="middle">{unit}</text>')
    for gi, g in enumerate(groups):
        gx = left + gi * gw + gw * .1
        for si, (_, col) in enumerate(series):
            v = values[si][gi]
            bh = ph * v / vmax
            x = gx + si * bw
            o.append(f'<rect x="{x:.1f}" y="{top+ph-bh:.1f}" width="{bw-5:.1f}" height="{bh:.1f}" rx="3" fill="{col}"/>')
            o.append(f'<text x="{x+(bw-5)/2:.1f}" y="{top+ph-bh-6:.1f}" font-size="12" font-weight="800" text-anchor="middle" fill="{C["ink"]}">{v:.1f}</text>')
        o.append(f'<text x="{left+gi*gw+gw/2:.1f}" y="{h-12}" font-size="15" font-weight="800" text-anchor="middle" fill="{C["ink"]}">{g}</text>')
    o.append(f'<line x1="{left}" x2="{w-right}" y1="{top+ph}" y2="{top+ph}" stroke="{C["ink"]}" stroke-width="1.5"/>')
    o.append("</svg>")
    return "".join(o)


def legend(series, size=14):
    return f'<div style="display:flex;gap:18px;flex-wrap:wrap;font-size:{size}px;color:{C["body"]}">' + "".join(
        f'<span><span class="lamp" style="background:{c};border-radius:3px"></span>{n}</span>' for n, c in series) + "</div>"


def hbars(rows, vmax, w=640, row_h=70, label_w=200):
    h = row_h * len(rows)
    pw = w - label_w - 170
    o = [svg_open(w, h)]
    for i, (lab, v, col, sub) in enumerate(rows):
        y = i * row_h
        bw = pw * v / vmax
        o.append(f'<text x="{label_w-14}" y="{y+row_h/2+5}" font-size="16" font-weight="800" text-anchor="end" fill="{C["ink"]}">{lab}</text>')
        o.append(f'<rect x="{label_w}" y="{y+12}" width="{bw:.1f}" height="{row_h-24}" rx="5" fill="{col}"/>')
        o.append(f'<text x="{label_w+bw+12:.1f}" y="{y+row_h/2}" font-size="17" font-weight="850" fill="{C["ink"]}">{n2(v)}</text>')
        o.append(f'<text x="{label_w+bw+12:.1f}" y="{y+row_h/2+18}" font-size="13" font-weight="700" fill="{col if col != C["base"] else C["muted"]}">{sub}</text>')
    o.append("</svg>")
    return "".join(o)


def gate_chart(w=600, h=330):
    seeds = [("12", 2.36, "selected, ep 8", True), ("13", 5.62, "diagnostic, ep 12", False),
             ("14", 5.11, "selected, ep 4", True), ("15", 1.03, "selected, ep 8", True), ("16", 3.27, "diagnostic, ep 4", False)]
    left, top, bottom, right = 44, 26, 56, 10
    pw, ph = w - left - right, h - top - bottom
    y = lambda v: top + ph - ph * v / 6.5
    o = [svg_open(w, h)]
    for t in range(7):
        o.append(f'<line x1="{left}" x2="{w-right}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#E3E7E4"/>')
        o.append(f'<text x="{left-8}" y="{y(t)+4:.1f}" font-size="12" text-anchor="end" fill="{C["muted"]}">{t}%</text>')
    o.append(f'<rect x="{left}" y="{y(4.95):.1f}" width="{pw}" height="{y(2.01)-y(4.95):.1f}" fill="{C["caution"]}" opacity=".14"/>')
    o.append(f'<line x1="{left}" x2="{w-right}" y1="{y(3.48):.1f}" y2="{y(3.48):.1f}" stroke="{C["caution"]}" stroke-width="2.5" stroke-dasharray="8 5"/>')
    bw = pw / 5
    for i, (s, v, lab, sel) in enumerate(seeds):
        x = left + i * bw + bw * .2
        fill = C["go"] if sel else "#fff"
        dash = "" if sel else ' stroke-dasharray="5 3"'
        o.append(f'<rect x="{x:.1f}" y="{y(v):.1f}" width="{bw*.6:.1f}" height="{y(0)-y(v):.1f}" rx="4" fill="{fill}" stroke="{C["go"] if sel else C["muted"]}" stroke-width="2"{dash}/>')
        o.append(f'<text x="{x+bw*.3:.1f}" y="{y(v)-8:.1f}" font-size="14" font-weight="850" text-anchor="middle" fill="{C["ink"]}">{v:.2f}%</text>')
        o.append(f'<text x="{x+bw*.3:.1f}" y="{h-bottom+22}" font-size="15" font-weight="850" text-anchor="middle" fill="{C["ink"]}">seed {s}</text>')
        o.append(f'<text x="{x+bw*.3:.1f}" y="{h-bottom+39}" font-size="12" text-anchor="middle" fill="{C["muted"]}">{lab}</text>')
    o.append(f'<line x1="{left}" x2="{w-right}" y1="{y(0)}" y2="{y(0)}" stroke="{C["ink"]}" stroke-width="1.5"/>')
    o.append("</svg>")
    return "".join(o)


def macro_timeline(w=1136, h=200):
    left, right = 20, 20
    pw = w - left - right
    x = lambda s: left + pw * s / 300
    by = 64
    o = [svg_open(w, h)]
    o.append(f'<text x="{left}" y="18" font-size="14" font-weight="800" fill="{C["ink"]}">One 300 s block of the reference schedule (illustrative)</text>')
    for a, b, lab, col in ((0, 100, "Phase A", C["go"]), (100, 110, "", C["caution"]), (110, 210, "Phase B", C["phaseB"]),
                           (210, 220, "", C["caution"]), (220, 300, "Phase A", C["go"])):
        o.append(f'<rect x="{x(a):.1f}" y="{by}" width="{x(b)-x(a):.1f}" height="34" fill="{col}"/>')
        if lab:
            o.append(f'<text x="{(x(a)+x(b))/2:.1f}" y="{by+22}" font-size="14" font-weight="800" text-anchor="middle" fill="#fff">{lab}</text>')
    for i in range(31):
        xx = x(i * 10)
        o.append(f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{by+36}" y2="{by+36+(16 if i % 5 == 0 else 9)}" stroke="{C["muted"]}"/>')
        if i % 5 == 0:
            o.append(f'<text x="{xx:.1f}" y="{by+66}" font-size="12" text-anchor="middle" fill="{C["muted"]}">{i*10} s</text>')
    for s, col in ((90, C["stop"]), (110, C["caution"])):
        o.append(f'<line x1="{x(s):.1f}" x2="{x(s):.1f}" y1="{by-8}" y2="{by+40}" stroke="{col}" stroke-width="3" stroke-dasharray="4 3"/>')
    o.append(f'<line x1="{x(100):.1f}" x2="{x(100):.1f}" y1="{by-10}" y2="{by+42}" stroke="{C["ink"]}" stroke-width="3.5"/>')
    o.append(f'<text x="{x(90)-8:.1f}" y="{by-14}" font-size="13" font-weight="800" text-anchor="end" fill="{C["stop"]}">advance to 90 s</text>')
    o.append(f'<text x="{x(110)+8:.1f}" y="{by-14}" font-size="13" font-weight="800" fill="#B97A00">delay to 110 s</text>')
    o.append(f'<text x="{x(100):.1f}" y="{by+90}" font-size="13" font-weight="800" text-anchor="middle" fill="{C["ink"]}">reference boundary at 100 s</text>')
    o.append(f'<rect x="{x(300)-5:.1f}" y="{by-12}" width="10" height="58" rx="2" fill="{C["stop"]}"/>')
    o.append(f'<text x="{x(300)-12:.1f}" y="{by+124}" font-size="13.5" font-weight="850" text-anchor="end" fill="{C["stop"]}">At 300 s the signal state must match the anchor</text>')
    o.append(f'<text x="{left}" y="{by+124}" font-size="13.5" fill="{C["muted"]}">30 request ticks of 10 s. Each junction picks one macro per block.</text>')
    o.append("</svg>")
    return "".join(o)


def rl_loop():
    return f'''{svg_open(500, 300)}
<defs><marker id="ah" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{C['go']}"/></marker></defs>
<rect x="160" y="10" width="180" height="62" rx="12" fill="{C['asphalt']}"/>
<text x="250" y="37" font-size="17" font-weight="850" fill="#fff" text-anchor="middle">Agent (policy)</text>
<text x="250" y="58" font-size="13" fill="#A8B8C4" text-anchor="middle">Q(o, a) then argmax</text>
<rect x="160" y="228" width="180" height="62" rx="12" fill="#fff"/>
<text x="250" y="255" font-size="17" font-weight="850" fill="{C['ink']}" text-anchor="middle">Simulator</text>
<text x="250" y="276" font-size="13" fill="{C['muted']}" text-anchor="middle">SUMO or CityFlow</text>
<path d="M340,41 C455,41 455,259 345,259" fill="none" stroke="{C['go']}" stroke-width="3.5" marker-end="url(#ah)"/>
<text x="378" y="155" font-size="15" font-weight="850" fill="{C['go']}" text-anchor="middle">action</text>
<path d="M160,259 C45,259 45,41 155,41" fill="none" stroke="{C['go']}" stroke-width="3.5" marker-end="url(#ah)"/>
<text x="122" y="125" font-size="15" font-weight="850" fill="{C['go']}" text-anchor="middle">next obs</text>
<text x="122" y="188" font-size="15" font-weight="850" fill="{C['stop']}" text-anchor="middle">reward</text>
<rect x="185" y="124" width="130" height="52" rx="10" fill="#FBEFD3"/>
<text x="250" y="147" font-size="14" font-weight="800" fill="{C['ink']}" text-anchor="middle">Replay buffer</text>
<text x="250" y="165" font-size="12" fill="{C['muted']}" text-anchor="middle">used in training</text>
</svg>'''


def mlp(inp, dueling=False, w=520, h=240):
    xs = [30, 160, 290]
    inner = h - 30
    o = [svg_open(w, h)]
    for lab, x, hh in zip((inp, "64", "64"), xs, (inner * .72, inner, inner)):
        y0 = 26 + (inner - hh) / 2
        o.append(f'<rect x="{x}" y="{y0:.1f}" width="72" height="{hh:.1f}" rx="12" fill="{C["lane"]}"/>')
        for k in range(6):
            o.append(f'<circle cx="{x+36}" cy="{y0+20+k*(hh-40)/5:.1f}" r="7.5" fill="{C["go"]}"/>')
        o.append(f'<text x="{x+36}" y="{y0-8:.1f}" font-size="16" font-weight="850" text-anchor="middle" fill="{C["ink"]}">{lab}</text>')
    for x in (102, 232):
        o.append(f'<line x1="{x+6}" x2="{x+54}" y1="{h/2+13}" y2="{h/2+13}" stroke="{C["muted"]}" stroke-width="2"/>')
        o.append(f'<text x="{x+30}" y="{h/2+5}" font-size="11.5" text-anchor="middle" fill="{C["muted"]}">ReLU</text>')
    mid = h / 2 + 13
    if dueling:
        o.append(f'<path d="M362,{mid} C392,{mid} 392,64 418,64" stroke="{C["muted"]}" fill="none" stroke-width="2"/>')
        o.append(f'<path d="M362,{mid} C392,{mid} 392,178 418,178" stroke="{C["muted"]}" fill="none" stroke-width="2"/>')
        o.append(f'<rect x="418" y="42" width="92" height="44" rx="9" fill="{C["asphalt"]}"/><text x="464" y="70" font-size="15" font-weight="850" fill="#fff" text-anchor="middle">V (1)</text>')
        o.append(f'<rect x="418" y="156" width="92" height="44" rx="9" fill="{C["go"]}"/><text x="464" y="184" font-size="15" font-weight="850" fill="#fff" text-anchor="middle">A (3)</text>')
        o.append(f'<text x="464" y="124" font-size="12.5" font-weight="800" fill="{C["ink"]}" text-anchor="middle">V + A − mean A</text>')
        o.append(f'<text x="464" y="226" font-size="13.5" font-weight="850" fill="{C["go"]}" text-anchor="middle">3 Q-values</text>')
    else:
        o.append(f'<line x1="362" x2="418" y1="{mid}" y2="{mid}" stroke="{C["muted"]}" stroke-width="2"/>')
        o.append(f'<rect x="418" y="{mid-24}" width="92" height="48" rx="9" fill="{C["asphalt"]}"/><text x="464" y="{mid+6}" font-size="15" font-weight="850" fill="#fff" text-anchor="middle">1 Q</text>')
    o.append("</svg>")
    return "".join(o)


def table(headers, rows, cls="t", align=None, rowcls=None):
    align = align or [""] * len(headers)
    rowcls = rowcls or {}
    th = "".join(f'<th class="{a}">{h}</th>' for h, a in zip(headers, align))
    body = "".join(f'<tr class="{rowcls.get(i, "")}">' + "".join(f'<td class="{a}">{c}</td>' for c, a in zip(r, align)) + "</tr>"
                   for i, r in enumerate(rows))
    return f'<table class="{cls}"><tr>{th}</tr>{body}</table>'


def chain(items):
    out = []
    for i, (b, t) in enumerate(items):
        if i:
            out.append('<div class="ar"></div>')
        out.append(f'<div class="st"><b>{b}</b>{t}</div>')
    return f'<div class="chain">{"".join(out)}</div>'


def vchain(items):
    return '<div class="vchain">' + '<div class="dn"></div>'.join(f'<div class="st">{x}</div>' for x in items) + "</div>"


def stat(v, label, color="ink", size=40):
    col = {"ink": C["ink"], "go": C["go"], "stop": C["stop"], "caution": "#B97A00", "pressure": C["pressure"], "white": "#fff"}[color]
    return f'<div><div class="stat" style="color:{col};font-size:{size}px">{v}</div><div class="stat-l">{label}</div></div>'


# ------------------------------------------------------------------ slide registry
SECTIONS = ["Why", "Data", "RL basics", "SUMO", "CityFlow", "Results", "Wrap-up"]
S: list[dict] = []
B = "Backup"


def slide(section, title, body, *, secs, source="", kind="", notes=None):
    S.append(dict(section=section, title=title, body=body, secs=secs, source=source, kind=kind, notes=notes or {}))


def N(say, keys, avoid=None, qa=None):
    return dict(say=say, keys=keys, avoid=avoid or [], qa=qa or [])


def divider(section, part, title, question, minutes, lit="go"):
    body = f'''
<div style="position:absolute;left:72px;top:150px;font-size:210px;font-weight:900;line-height:.8;color:transparent;-webkit-text-stroke:2px #3C5061;letter-spacing:-.04em">{part:02d}</div>
<div style="position:absolute;left:72px;top:360px;width:860px;font-size:64px;font-weight:850;line-height:1.02;color:#fff;letter-spacing:-.03em">{title}</div>
<div style="position:absolute;left:72px;top:520px;width:820px;font-size:24px;line-height:1.35;color:#AFC0CC">{question}</div>
<div style="position:absolute;left:72px;top:620px;font-size:16px;font-weight:700;color:#6FD3B0">About {minutes} minutes</div>
<div style="position:absolute;right:110px;top:120px">{signal_head(lit, 150, 460)}</div>'''
    slide(section, "", body, secs=10, kind="divider", notes=N(
        f"Transition line: “{question}” Pause for a breath, then continue.", [f"Part {part}: {title}", f"≈ {minutes} min", "Breathe, look up"]))


# ================================================================== 01 cover
slide("Why", "", f'''
<div style="position:absolute;right:0;top:0">{cover_art()}</div>
<div style="position:absolute;left:72px;top:74px;font-size:17px;font-weight:700;color:#6FD3B0">Master of Software Engineering thesis defence</div>
<div style="position:absolute;left:72px;top:112px;width:640px;font-size:54px;line-height:1.02;font-weight:850;color:#fff;letter-spacing:-.03em">Evidence-aware reinforcement learning for Da Nang traffic signals</div>
<div style="position:absolute;left:72px;top:318px;width:600px;font-size:22px;line-height:1.4;color:#B8C7D2">From one published intersection in SUMO to 53 signalised junctions of Hai Chau district in CityFlow</div>
<div style="position:absolute;left:72px;top:470px;font-size:14px;color:#7E93A3">Candidate</div>
<div style="position:absolute;left:72px;top:492px;font-size:27px;font-weight:850;color:#fff">{AUTHOR}</div>
<div style="position:absolute;left:380px;top:470px;font-size:14px;color:#7E93A3">Supervisor</div>
<div style="position:absolute;left:380px;top:492px;font-size:19px;font-weight:650;color:#fff;line-height:1.45">Dr. Le Van Minh</div>
<div style="position:absolute;left:72px;top:640px;font-size:15px;color:#7E93A3">FPT University, Da Nang, 2026</div>
''', secs=30, kind="cover", notes=N(
    "Good morning, members of the committee. My name is Luong Quang Khang. Today I present my thesis on reinforcement learning for traffic signal control in Da Nang. "
    "The work has two experimental tiers: one intersection with published data, simulated in SUMO, and a network of 53 signalised junctions in Hai Chau, simulated in CityFlow. "
    "The phrase “evidence-aware” in the title is the core of the thesis: I report every number together with where it comes from and how far it can be generalised.",
    ["Two tiers: 1 junction in SUMO, 53 in CityFlow", "Core idea: traceable evidence", "Speak slowly, look at the committee"],
    ["Do not open with a promise that RL always wins."]))

# ================================================================== 02 roadmap
parts = [("Why", "The problem, three research questions, the two-tier design"), ("Data", "2007 starting point, published source, trust levels, demand, seeds"),
         ("RL basics", "Q-values, Double DQN, dueling heads"), ("SUMO", "16-number state, training, metric and baselines"),
         ("CityFlow", "Schedule residual, anchor, 27 features, selector"), ("Results", "Regime effects, strong baselines, multi-seed gate"),
         ("Wrap-up", "Demo, allowed claims, contributions, next steps")]
ROADMAP_SLOT = len(S)
slide("Why", "What I will cover", "__ROADMAP__", secs=40, notes=N(
    "I will cover seven parts. I start with the problem and three research questions, then where the data comes from and how it becomes a simulation. "
    "After a short primer on the learning method, I explain the two models: one junction in SUMO and 53 junctions in CityFlow. "
    "The results show where learning helps and where it does not, then a short demo and the conclusion. "
    "If you remember one sentence: the benefit depends on the demand regime and the baseline, and this is simulation evidence.",
    ["Seven parts, walk them once", "One sentence: depends on regime and baseline", "Do not explain the bar as a signal cycle"],
    ["Do not announce the duration, and do not say the talk runs like a signal cycle."]))

# ================================================================== 03 problem
slide("Why", "A fixed plan repeats all day, while demand does not", f'''
<div class="row" style="gap:34px">
 <div style="width:680px;flex:none">{cycle_vs_demand()}
  <div class="row" style="gap:10px;margin-top:4px">
   <span class="tag go">G1 32 s</span><span class="tag" style="background:#DCE6F0;color:#2F557A">G2 28 s</span><span class="tag stop">G3 22 s</span><span class="tag caution">3 × 7 s yellow</span><span class="tag dark">cycle 103 s</span></div>
 </div>
 <div class="col">
  <p class="lead" style="margin-bottom:18px">An adaptive controller watches traffic and changes the signal decision to cut total queueing. Reinforcement learning learns that rule from the <b>consequences</b> of actions in a simulator.</p>
  <h3>Why it is hard</h3>
  <div class="rule-l stop" style="margin-bottom:10px"><b class="stop">Delayed effects.</b> A switch now shortens a queue seconds later and spreads to the next junction.</div>
  <div class="rule-l stop" style="margin-bottom:10px"><b class="stop">Conflicting benefits.</b> Releasing one junction can push vehicles into a full downstream link.</div>
  <div class="rule-l stop"><b class="stop">Thin evidence.</b> Published cameras cover four movements at one junction on one day.</div>
 </div>
</div>''', secs=75, source="Timing: Phan, Le & Nguyen (2025), p. 7 and Fig. 4 p. 8 · camera totals: datasets/danang_published/phan2025_camera_hourly_digitized.csv", notes=N(
    "A fixed-time plan splits green time in a repeating cycle. At the study junction the published plan is 32, 28 and 22 seconds of green plus three 7-second yellows, 103 seconds in total. "
    "The chart shows the problem: the digitised camera demand moves from about 1,250 to about 2,500 vehicles per hour across the day, but the same 103-second plan repeats underneath. "
    "An adaptive controller observes traffic and changes decisions to reduce total queueing. It is hard for three reasons: effects are delayed, benefits between junctions can conflict, and field data is thin. "
    "So the right question is not “is RL good?”, but when does it help, compared with which baseline, and how strong is the evidence.",
    ["103 s = 32 + 28 + 22 + 3 × 7", "Delayed · conflicting · thin evidence", "When / against what / how sure"]))

# ================================================================== 04 RQs
rq = [("RQ1", "Does RL reduce queueing at the junction with published data?", "SUMO, three regimes, five learning seeds", "A simulated junction with the stated geometry, demand and assumptions", C["go"]),
      ("RQ2", "Can one shared policy learn useful timing edits for 53 junctions?", "CityFlow, schedule-residual Double DQN", "A simulated network with synthetic demand", C["pressure"]),
      ("RQ3", "Does the result survive strong baselines, seeds, pending vehicles and a source audit?", "Baselines, statistics, selector, evidence audit", "Current evidence and the remaining gaps", C["stop"])]
rqh = "".join(f'''<div class="col" style="border-top:6px solid {c};padding-top:16px">
 <div class="hero" style="font-size:54px;color:{c}">{k}</div>
 <div style="font-size:23px;font-weight:800;color:{C["ink"]};line-height:1.25;margin:12px 0 18px;min-height:116px">{q}</div>
 <div class="xs muted" style="font-weight:800">Answered by</div><div class="small" style="margin-bottom:12px">{e}</div>
 <div class="xs muted" style="font-weight:800">Scope of the conclusion</div><div class="small">{s}</div></div>''' for k, q, e, s, c in rq)
slide("Why", "Three research questions", f'''<div class="row" style="gap:36px">{rqh}</div>
<div class="panel dark" style="margin-top:30px;font-size:19px;line-height:1.45"><b style="color:#6FD3B0">Central claim.</b> The thesis tests when adaptive control reduces queueing in controlled simulation scenarios. The answer depends on the demand regime and the baseline, and current evidence does not establish field performance.</div>''',
      secs=75, notes=N(
    "The thesis answers three questions. RQ1: at a junction with published data, does RL reduce queueing? I answer it in SUMO with three regimes and five learning seeds. "
    "RQ2: can one policy that shares weights across 53 junctions learn useful edits to the signal schedule? I answer it in CityFlow with a schedule-residual controller. "
    "RQ3 is about trust: after strong baselines, several seeds, counting vehicles that cannot enter, and checking the data sources, how much of the result still stands? "
    "Each question has its own scope, and I keep to that scope until the end.",
    ["RQ1 = SUMO, one junction", "RQ2 = CityFlow, shared policy, 53 junctions", "RQ3 = strength of evidence"],
    ["Say “tests when it helps”, not “proves RL is better”."]))

# ================================================================== 05 two tiers
two = table(["", "SUMO: one junction", "CityFlow: Hai Chau network"], [
    ["Role", "Test at the junction with a published source", "Test scale and junction interaction"],
    ["Size", "1 junction, 4 approaches, 3 green phases", "<b>53</b> signalised junctions from OSM"],
    ["Model", "Dueling <b>Double</b> DQN, 3-step return", "Schedule-residual <b>Double</b> DQN"],
    ["Input → output", "16 numbers → 3 Q-values", "27 numbers per candidate macro → 1 Q"],
    ["Decision clock", "10 s", "300 s macro, requests every 10 s"],
    ["Reward", "−(queue + pending at end of 10 s step) × 0.01", "−(network queue + pending integral) / 100,000"],
    ["Training", "30 episodes × 3,600 s, seeds 11–15", "12 episodes × 3,600 s, seeds 12–16"],
    ["Fixed baseline", "Published 103 s plan", "25 s nominal green tuned on validation"],
    ["Test", "15 cases (3 regimes × 5)", "15 cases (3 regimes × 5)"],
], cls="t tight")
slide("Why", "Two tiers: two simulators, two models, two questions", f'''
<div class="row" style="gap:30px">
 <div style="flex:1.75">{two}</div>
 <div class="col">
  {vchain(["<b>Da Nang paper</b><br><span class='xs muted'>timing, turning table, camera plots</span>", "<b>CSV + documented assumptions</b>",
           "<div style='display:flex;gap:8px'><div style='flex:1;background:#DDF1E9;border-radius:8px;padding:4px'><b>SUMO</b><br><span class='xs'>1 junction</span></div><div style='flex:1;background:#E1EAF7;border-radius:8px;padding:4px'><b>CityFlow</b><br><span class='xs'>53 junctions + OSM</span></div></div>",
           "<b>Paired evaluation</b><br><span class='xs muted'>same demand, baselines, several seeds</span>", "<b>Results, limits, replay demo</b>"])}
  <div class="note stop" style="margin-top:14px"><b>No weight transfer</b> from SUMO to CityFlow. The tiers share the research question and the demand shape, not a train-then-fine-tune pipeline.</div>
 </div>
</div>''', secs=80, source="docs/defense/thesis-understanding-guide-vi.md, section 2", notes=N(
    "The design has two tiers. The SUMO tier is one junction with a published source; it is the empirical anchor. The model is a dueling Double DQN that reads 16 numbers and outputs three Q-values for three green phases, deciding every 10 seconds. "
    "The CityFlow tier is a 53-junction network built from OpenStreetMap with synthetic demand. The model is a schedule-residual Double DQN: every 300 seconds each junction chooses a small edit to its schedule, and one shared MLP scores every candidate. "
    "Important: no weights move between the simulators. The two tiers have different architectures, rewards and training procedures; they are linked by the research question and the demand shape only.",
    ["SUMO: 16 → 3 Q, every 10 s", "CityFlow: 27 per macro → 1 Q, 300 s, shared", "No weight transfer"],
    ["Never plot one “RL” bar that merges both models."],
    [("How are the two tiers related?", "Same research question and the same camera demand shape; no shared weights.")]))

# ================================================================== DATA
divider("Data", 2, "Where the data comes from", "What was actually observed, and what did I have to assume?", 8)

slide("Data", "Starting point: Da Nang main roads, timed from field surveys", f'''
<div class="rule-l ink" style="margin-bottom:18px"><div class="small"><b>Trần Trung Việt & Phan Cao Thọ (2007).</b> <i>Nghiên cứu ứng dụng bài toán điều khiển giao thông bằng “Làn sóng xanh” trên các trục giao thông chính ở thành phố Đà Nẵng</i> [Applying “green wave” traffic control on the main arterials of Da Nang — my translation]. Tạp chí Cầu Đường Việt Nam, no. 10/2007, pp. 23–28.</div></div>
{chain([("2007: arterials", "field flow surveys → green-wave timing"), ("2025: one junction", "Phan, Le & Nguyen: plan, table, cameras"), ("This thesis", "SUMO junction + 53-signal main-road network")])}
<div class="row" style="gap:30px;margin-top:22px">
 <div class="col panel go"><h3>Idea I take from it</h3><ul class="small" style="margin-left:18px">
  <li>Signal timing in Da Nang starts from <b>surveyed flows</b> on <b>signalised arterials</b>, not from a generic city.</li>
  <li>The network tier <b>drops residential streets</b> (OSM highway.residential) to stay on the main-road corridors.</li>
  <li>Its method is a <b>coordinated fixed-time</b> plan: cycle, green split and time band set offline from counts.</li></ul></div>
 <div class="col panel stop"><h3>What I do not take</h3><ul class="small" style="margin-left:18px">
  <li><b>No numbers.</b> Only the title and abstract were read; the full text and survey data were not obtained.</li>
  <li>The thesis fixed baseline has <b>no offsets</b>, so it is not a green wave.</li>
  <li>RL here is <b>adaptive</b>: it reacts to observed queues instead of a precomputed band.</li></ul></div>
</div>''', secs=55, source="https://scv.udn.vn/trantrungviet/BBao/5864 (abstract only; full text not obtained)", notes=N(
    "Before the 2025 source, one local starting point. In 2007, Tran Trung Viet and Phan Cao Tho published a study in the Vietnam Bridge and Road journal on green-wave coordination for Da Nang's main arterials. They built the timing problem on the time-band method and on field surveys of traffic flow on signalised arterials, and wrote software called Green Wave Design. "
    "I take the idea, not the data: in Da Nang the signal problem lives on arterials and starts from surveyed flows. That is why the network tier drops residential streets and stays on main roads, and why the next source, the 2025 paper, is a junction with published counts. "
    "Two honest limits: I have only read the title and abstract, so I quote no numbers from it. And my fixed baseline has no offsets, so it is not a green wave; a coordinated plan would be a stronger fixed-time baseline that I did not test.",
    ["2007: arterials + field surveys + green wave", "Idea only, no numbers (abstract only)", "Fixed baseline ≠ green wave"],
    ["Never say the thesis uses data from the 2007 study.", "Do not claim any link between the 2007 and 2025 authors."],
    [("Did you compare against green-wave coordination?", "No. The fixed baseline is an uncoordinated plan (published 103 s in SUMO, validation-tuned in CityFlow) with no offsets. Green-wave coordination would be a stronger fixed-time baseline that I did not test; I list it as a limitation."),
     ("Why cite a 2007 paper?", "It shows the local practice: Da Nang arterial signals were timed offline from field surveys. The thesis asks whether an adaptive controller can improve on fixed-time logic for that setting.")]))

src_rows = [["Geometry, lanes 2/2/3/3", "p. 7", "Build the SUMO junction"],
            ["Green 32/28/22 s, cycle 103 s", "p. 7, Fig. 4 p. 8", "Published fixed baseline"],
            ["12 turning movements, 6,171 PCU/h", "Table 1 p. 8 (2022)", "Context for movement split"],
            ["Cameras on 1 Apr 2025, 06:00–18:00", "p. 16", "Date of the camera source"],
            ["2 cameras, 4 movement lines", "Fig. 12 p. 17", "What was really observed"],
            ["PCU: motorcycle 0.3, car 1, bus 2, truck 2.5", "p. 19", "Unit conversion in the source"],
            ["Hourly counts by vehicle class", "Figs. 17–18 p. 20", "Digitised into CSV"],
            ["Raw data not public", "p. 23", "Limit on access to raw video"]]
slide("Data", "One published study of one Da Nang junction", f'''
<div class="row" style="gap:30px">
 <div style="width:380px;flex:none"><img class="fig" src="{img("junction")}" style="width:380px;height:380px;object-fit:contain">
  <div class="cap">Le Thanh Nghi – Cach Mang Thang 8 – 2/9 junction, Hoa Xuan bridge side. Two cameras observe four movement lines; approaches are modelled over about 300 m.</div></div>
 <div class="col">
  <div class="rule-l ink" style="margin-bottom:14px"><div class="small"><b>Phan, Le & Nguyen (2025).</b> <i>Application of Dueling Double Deep Q-Network for Dynamic Traffic Signal Optimization: A Case Study in Danang City, Vietnam.</i> MAKE 7(3):65. doi:10.3390/make7030065</div></div>
  {table(["What", "Where in the PDF", "Used for"], src_rows, cls="t tight")}
  <div class="note stop" style="margin-top:12px;font-size:15px">The source spells the street inconsistently (p. 7 reads “Nguyenthanhnghi”); the thesis follows Table 1 and Fig. 12. <b>PCU/h is not veh/h</b>, so the two are never added together.</div>
 </div>
</div>''', secs=100, source="datasets/danang_published/sources/phan2025_make7030065.pdf (PDF pages 1–24)", notes=N(
    "The main source is Phan, Le and Nguyen, 2025, in the journal MAKE. I use it because it publishes the geometry, the signal plan and camera counts for one specific junction in Da Nang. "
    "Every item I use has a page locator: geometry on page 7, the 103-second plan on page 7 and Figure 4, twelve turning movements in Table 1 on page 8, the camera date on page 16, two cameras and four movement lines in Figure 12, PCU factors on page 19, and hourly counts in Figures 17 and 18. "
    "Two caveats up front: the street name is inconsistent in the source, and the turning table is in PCU per hour — passenger-car equivalents — so it cannot be added to vehicle counts. Raw video is not public.",
    ["Phan, Le & Nguyen 2025, MAKE, doi make7030065", "Every number has a page, figure or table", "PCU ≠ vehicles; no raw video"],
    ["The file name says tran2025; the verified authors are Phan et al."],
    [("Is this field data?", "The camera part is published counts, digitised approximately from plots: one day, four movements. The rest are documented simulation assumptions.")]))

tiers = [("Published source", "PDF, timing, turning table, camera plots", "“According to the paper, page / figure / table …”", C["ink"]),
         ("Extracted from source", "Approximate values read into the CSV", "“Digitised approximate counts …”", C["go"]),
         ("Simulation construction", "Full-junction expansion, routes, vehicle templates", "“Assumption used to build the scenario …”", C["caution"]),
         ("Simulation output", "Queue integral, completion, reward", "“Result in the simulator under configuration …”", C["stop"])]
th = "".join(f'''<div style="display:flex;gap:16px;margin-bottom:14px"><div class="hero" style="font-size:40px;color:{c};width:34px">{i+1}</div>
<div><div style="font-weight:850;font-size:19px;color:{C["ink"]}">{n}</div><div class="xs">{e}</div><div class="xs muted"><i>{s}</i></div></div></div>''' for i, (n, e, s, c) in enumerate(tiers))
slide("Data", "Forty-eight digitised rows, read at four levels of trust", f'''
<div class="row" style="gap:40px">
 <div class="col">
  <div class="row" style="gap:36px;margin-bottom:22px">{stat("48", "rows = 4 movements × 12 hour labels")}{stat("192", "approximate values across car, motorcycle, truck, bus")}{stat("1 day", "1 April 2025, no seasonal claim")}</div>
  <div class="row" style="gap:14px;margin-bottom:20px">
   <div class="panel go col" style="padding:14px 18px">{stat("1,395", "veh/h at 13:00 → normal test", "go", 34)}</div>
   <div class="panel stop col" style="padding:14px 18px">{stat("2,330", "veh/h at 08:00 → AM, also training", "stop", 34)}</div>
   <div class="panel caution col" style="padding:14px 18px">{stat("2,400", "veh/h at 17:00 → PM test", "caution", 34)}</div>
  </div>
  <div class="note" style="font-size:15.5px">The ±15 / ±30 veh/h tolerances are <b>reading errors</b> set by the project, not confidence intervals. A matching SHA-256 proves the file is byte-identical, <b>not</b> that the counts describe real traffic.</div>
 </div>
 <div style="width:440px;flex:none"><h3>Four levels of trust</h3>{th}</div>
</div>''', secs=75, source="datasets/danang_published/phan2025_camera_hourly_digitized.csv · docs/research/danang-data-claim-audit.md", notes=N(
    "From Figures 17 and 18 I digitised a CSV: four movements times twelve hour labels gives 48 rows; each row has four vehicle classes, so 192 approximate values, all from one day. "
    "The three coloured numbers are the test levels: 1,395 at 13:00 is normal, 2,330 at 08:00 is AM, and 2,400 at 17:00 is PM. They are totals over the four observed lines, not the whole junction. "
    "To speak at the right strength I separate four levels: published source, extracted values, construction assumptions and simulation output — each with its own wording. "
    "The ±15 and ±30 tolerances are reading errors, not confidence intervals, and a hash only proves the file is unchanged.",
    ["48 rows · 192 values · 1 day", "1,395 / 2,330 / 2,400 = normal / AM / PM", "4 trust levels: source → extract → assume → output"],
    ["Never say 2,400 is the total flow of the junction."]))

slide("Data", "From source numbers to simulated demand", f'''
<div class="row" style="gap:30px">
 <div style="width:450px;flex:none">
  <h3>SUMO <span class="sub">one junction</span></h3>
  {vchain(["Published timing + geometry → <b>junction and signal program</b>", "Camera CSV, 4 movements → <b>main-protocol demand</b>", "Demand seed → routes and departure times", "Simulator seed → randomness inside SUMO"])}
  <div class="row" style="gap:10px;margin-top:14px">
   <div class="col">{stat("1,395", "veh/h normal", "go", 30)}</div><div class="col">{stat("2,330", "veh/h AM (train)", "stop", 30)}</div><div class="col">{stat("2,400", "veh/h PM", "caution", 30)}</div></div>
  <div class="xs muted" style="margin-top:10px">Full-junction levels near 5,793 / 9,676 / 9,967 are a <b>project extrapolation</b>, not the main protocol.</div>
 </div>
 <div class="col">
  <h3>CityFlow <span class="sub">53 junctions in Hai Chau</span></h3>
  {chain([("OSM PBF", "Geofabrik, ODbL"), ("osmium", "clip bbox"), ("netconvert", "SUMO net"), ("converter", "CityFlow roadnet"), ("53 signals", "phase contract")])}
  <div class="xs muted" style="margin:6px 0 10px">bbox 108.1888, 16.0213 – 108.2360, 16.1037. A <b>processed, derived</b> network, not every field signal.</div>
  {table(["Property", "Value"], [["Route families", "1,290 → train / val / test = 644 / 323 / 323"], ["Route streams per case", "500, each emitting many vehicles"],
       ["Vehicle mix", "motorcycle with probability 0.90, else car (assumption)"], ["Episode", "3,600 s = three 1,200 s bins"]], cls="t tight")}
  <div class="eq" style="margin-top:10px;font-size:14.5px"><span class="c">interval_bin</span> = 240 × <span class="a">1603.33</span> / source_count_bin   <span class="c"># PM 2,400 → 160.3 s</span></div>
 </div>
</div>
<div class="note stop" style="margin-top:14px"><b>500 routes ≠ 500 vehicles.</b> The profile borrows only the <b>relative shape</b> of camera demand; three source hours are compressed into three 20-minute bins.</div>''',
      secs=100, source="configs/haichau_network_v2.yaml · src/traffic_rl/network/haichau_dataset.py · datasets/haichau_network_v2/provenance.json", notes=N(
    "In SUMO, the published timing and geometry build the junction and its signal program; the camera CSV builds the main demand: 1,395 vehicles normal, 2,330 AM and 2,400 PM in one hour. The demand seed sets departure times, the simulator seed sets internal randomness. Full-junction numbers near 9,700 are only an extrapolation. "
    "In CityFlow, the topology comes from OpenStreetMap through osmium, netconvert and a converter to CityFlow's roadnet. The result is a derived network with 53 signalised junctions. "
    "Network demand is synthetic: 1,290 route families split into train, validation and test, 500 route streams per case, and a 90 percent motorcycle share as a sampling assumption. The hourly camera shape modulates the emission interval: busier hours give shorter intervals, for example 2,400 vehicles gives about 160 seconds. "
    "Stress: 500 route streams are not 500 vehicles, and a PM case does not replay three real hours.",
    ["SUMO: 1,395 / 2,330 / 2,400", "CityFlow: OSM → 53 signals, 1,290 route families", "Profile = relative shape, not counts"],
    ["Never call the 53-junction network all real signals of Hai Chau."],
    [("Why 53 junctions?", "That is the number of controlled signals after the OSM → netconvert → CityFlow pipeline, with merge and filter steps recorded in provenance.")]))

slide("Data", "Splits and the three kinds of seed", f'''
<div class="row" style="gap:40px">
 <div style="flex:1.2">
  {table(["CityFlow split", "Demand seeds", "Simulator seeds", "Cases"], [["Train", "11, 12, 13", "111, 112, 113", "3 regimes × 3 = 9"], ["Validation", "31, 32", "131, 132", "3 regimes × 2 = 6"], ["Test", "101–105", "201–205", "3 regimes × 5 = <b>15</b>"]], align=["", "c", "c", ""])}
  <p class="small" style="margin-top:16px"><b>SUMO:</b> train on AM demand 11 / sim 11 and validate on AM demand 31 / sim 31, <b>shared by every learning seed</b>. Test on 15 cases.</p>
  <div class="note" style="margin-top:14px;font-size:15.5px">Route-family splits separate route families, yet routes can still cross the same links and junctions. This is <b>not</b> a test on an unseen city.</div>
 </div>
 <div class="col">
  <div class="rule-l go" style="margin-bottom:16px"><b style="font-size:20px">Demand seed</b><div class="small">Samples routes, vehicle types, departure times.</div></div>
  <div class="rule-l pressure" style="margin-bottom:16px"><b style="font-size:20px">Simulator seed</b><div class="small">Randomness inside the simulator.</div></div>
  <div class="rule-l stop" style="margin-bottom:20px"><b style="font-size:20px">Learning seed</b><div class="small">Network initialisation, exploration, replay sampling.</div></div>
  <div class="panel go small">Same demand and simulator seeds for every controller give a <b>paired</b> comparison. Several learning seeds measure <b>how much learning varies</b>.</div>
 </div>
</div>''', secs=55, source="results/haichau_network_v2/experiment-manifest.json · results/danang_protocol_v1/experiment-manifest.json", notes=N(
    "There are three kinds of seed with different meanings: the demand seed sets demand, the simulator seed sets simulator randomness, and the learning seed sets the learning process. "
    "In CityFlow, training has 9 cases, validation 6 and test 15, five per regime. Every controller runs on the same demand and simulator seed pairs, so differences are paired comparisons. "
    "In SUMO, training and validation are both AM and are shared by all five learning seeds. "
    "Note: many demand cases of one checkpoint are not many independent models, and the route-family split is not a new city.",
    ["3 seeds: demand · simulator · learning", "Test = 15 cases (3 × 5)", "Paired ≠ independent models"]))

slide("Data", "Extension: vehicle counts and turning paths from a public camera", f'''
<div class="small" style="margin-bottom:8px"><b>Public YouTube video</b> → <b>YOLOv8-VisDrone</b> detects every vehicle → <b>ByteTrack</b> keeps its ID → <b>7 count lines</b> log in / out by class → <b>Markov chain</b> P(exit leg | entry leg)</div>
<div class="row" style="gap:20px">
 <div style="width:490px;flex:none"><img class="fig" src="{img("cam_frame")}" style="width:490px;height:262px;object-fit:cover">
  <div class="cap">0511.vn, Tay Cau Rong junction, 11 Jul 2026 17:16–17:31. Box = vehicle, number = ID, trail = path, white line = count line.</div></div>
 <div class="col"><img class="fig" src="{img("cam_map")}" style="width:100%;height:262px;object-fit:contain">
  <div class="cap">Cars on an OpenStreetMap base: turning probability at J1 (blue), J2 (orange); OSM one-way streets agree with the counts.</div></div>
</div>
<div class="row" style="gap:18px;margin-top:10px;align-items:stretch">
 <div style="width:250px;flex:none">{stat("4,323", "line crossings / 15 min", "ink", 28)}<div style="height:6px"></div>{stat("75%", "of main-axis cars go onto the bridge; in–out gap 4% / 17%", "go", 28)}</div>
 <div class="panel go col" style="padding:10px 14px;font-size:13.5px;line-height:1.38"><b>Realtime, measured.</b> <b>One junction:</b> YOLOv8m (1280 input) + tracking + line counting processed <b>180 s of video in 169 s</b> on one Apple M4 Pro laptop (7.5 fps). Near-field cars +8%, motorbikes −10% vs the accurate run. Latency about 0.13 s ≪ the 10 s SUMO decision step. <b>53-junction network:</b> one such edge device per junction, sending only counts every 10 s (<i>not tested at network scale</i>).</div>
 <div class="note stop" style="width:250px;flex:none;font-size:13.5px;line-height:1.38"><b>Feasibility demo, not thesis data:</b> one camera, 15 minutes, no hand count; far-field motorbikes under-counted. Not used to build simulation demand.</div>
</div>''', secs=60, source="scripts/count_camera_vehicles.py · scripts/analyze_camera_routes.py · results/camera_counts/README.md", notes=N(
    "One limit of the data is that the paper's raw video is not public. So I tested whether counts can be extracted automatically from a public camera. "
    "I used the 0511.vn camera at the Tay Cau Rong junction, 15 minutes of the evening peak on 11 July. A YOLO model trained on top-down imagery detects each vehicle, ByteTrack keeps the vehicle's ID across frames, and seven count lines record entries, exits and vehicle class. "
    "Joining one vehicle's crossings gives its route, and from routes a Markov chain: the probability of leaving by each leg given the entry leg. For example, 75 percent of cars on the main axis turn onto the Dragon Bridge. "
    "Two independent checks: car entries and exits at each junction differ by 4 and 17 percent, and the one-way streets in OpenStreetMap match the counted directions. "
    "On realtime, I measured it: with a smaller model the whole chain processed 180 seconds of video in 169 seconds on one laptop, faster than real time, while the controller only needs a new state every 10 seconds. At network level each junction would need one such device sending only counts; I have not tested that. "
    "Limits: it is a feasibility demo, one camera and 15 minutes, with no hand count yet, and motorbikes far from the camera are under-counted, so I do not use it to build simulation demand.",
    ["Public camera → YOLO → ByteTrack → count lines → Markov", "4,323 crossings / 15 min; 75% main-axis cars to the bridge", "Realtime, one junction: 180 s of video in 169 s (M4 Pro laptop)", "Network: one edge device per junction — not tested", "Demo, not thesis data"],
    ["Do not say this demand was used in SUMO or CityFlow.", "Do not quote a motorbike total: far legs are under-counted.", "Do not claim an accuracy figure: there is no hand count yet.", "Do not say it already runs in realtime for the whole network: only one camera was measured."],
    [("How accurate is YOLO here?", "Not measured against a hand count yet. Current evidence is the car in–out balance (4% and 17% gaps) and agreement with OSM one-way streets. Far-field motorbikes are under-counted, so I report no motorbike total."),
     ("Why not use it in the simulation?", "It is 15 minutes at a different junction from the paper, and unverified. The next step is a hand count, several days of video, then demand calibration."),
     ("Can YOLO run in realtime?", "For one junction, yes, measured: YOLOv8m at 1280 input plus tracking and line counting processed 180 s of video in 169 s on an M4 Pro laptop; latency is about 0.13 s against a 10 s decision step. The trade-off is about 10% fewer motorbikes than the accurate run. For the 53-junction network the design is one edge device per junction sending counts; I have not tested that scale."),
     ("Why a VisDrone model?", "COCO-trained YOLO finds almost no motorbikes from this height; VisDrone is top-down imagery, so it picks up 10-pixel motorbikes.")]))

# ================================================================== RL
divider("RL basics", 3, "Learning from consequences", "Which two ideas do both models rely on?", 3)

clocks = "".join(f'<div style="display:flex;gap:16px;align-items:baseline;margin:8px 0"><div class="hero" style="font-size:34px;width:96px;color:{c}">{t}</div><div class="small"><b>{n}</b><br>{d}</div></div>'
                 for t, n, d, c in [("1 s", "Simulator second", "metrics are integrated every second", C["base"]), ("10 s", "Control tick", "SUMO picks a phase; CityFlow executes one request", C["go"]),
                                    ("300 s", "Macro", "CityFlow residual chooses a plan for the block", C["stop"])])
slide("RL basics", "Reinforcement learning learns from what happens next", f'''
<div class="row" style="gap:40px">
 <div style="width:500px;flex:none">{rl_loop()}<p class="small" style="margin-top:10px">No label says which action is optimal. The reward is a <b>negative cost</b>, so <b>less negative is better</b>.</p></div>
 <div class="col">
  <h3>Q-value</h3>
  <div class="eq">Return = r<sub>t</sub> + γ r<sub>t+1</sub> + γ² r<sub>t+2</sub> + …
<span class="k">greedy action</span> = argmax<sub>a</sub> Q(o, a)</div>
  <p class="small" style="margin:10px 0 20px">Q(o, a) predicts the discounted return of taking a at o. Higher Q means lower expected cost. Q is <b>not</b> a count of released vehicles.</p>
  <h3>Three clocks to keep apart</h3>{clocks}
  <div class="xs muted">An optimizer update is one weight update, not a simulated second.</div>
 </div>
</div>''', secs=70, notes=N(
    "The RL loop: the agent receives an observation, chooses an action, the simulator executes it and returns a reward and the next observation; during training the experience goes into a replay buffer used to update the model. "
    "Here the reward is the negative of queueing, so less negative is better. A Q-value predicts the discounted sum of future rewards for an action; the greedy policy picks the largest Q. "
    "There are three clocks: the simulator runs second by second and metrics are integrated each second; the 10-second control tick is when SUMO chooses a phase; and the 300-second macro is when the CityFlow residual decides. Keeping these clocks apart avoids most misreadings of the parameters.",
    ["Negative reward = cost", "Q = expected return, not vehicles", "1 s · 10 s · 300 s"]))

slide("RL basics", "Double DQN and dueling heads fix two different problems", f'''
<div class="row" style="gap:40px">
 <div class="col">
  <h3>Double DQN changes the <span class="go">target</span></h3>
  <p class="small">Plain DQN uses one max to both <b>choose</b> and <b>score</b> the next action, which inflates optimistic errors. Double DQN splits the roles.</p>
  <div class="eq" style="margin:10px 0"><span class="c"># online network chooses</span>
a* = argmax<sub>a</sub> Q<sub>online</sub>(o′, a)
<span class="c"># target network scores</span>
y  = r + (1 − done) · γ · Q<sub>target</sub>(o′, a*)</div>
  {table(["Worked example", "Action A", "Action B"], [["Q online", "<b>−4</b>, chosen", "−5"], ["Q target", "<b>−6</b>, used", "−3"]], cls="t tight", align=["", "c", "c"])}
  <div class="xs muted" style="margin-top:6px">The target network is copied from the online network periodically. van Hasselt, Guez & Silver (2016).</div>
 </div>
 <div class="col">
  <h3>Dueling changes the <span class="pressure">output head</span></h3>
  <div class="eq" style="margin:4px 0 12px">Q(o, a) = V(o) + A(o, a) − mean<sub>b</sub> A(o, b)</div>
  <ul class="dots pressure small"><li><b>V(o)</b> says how good the state is</li><li><b>A(o, a)</b> says how much better each action is</li><li>Subtracting the mean fixes the V/A split</li><li>Helpful when many actions are close in value; a design motive, not a guarantee</li></ul>
  <div class="xs muted" style="margin-top:6px">Wang et al., ICML 2016.</div>
 </div>
</div>
<div class="row" style="gap:20px;margin-top:22px">
 <div class="panel go col"><b>SUMO</b> uses <b>both</b>: Double target, dueling heads, 3-step return.</div>
 <div class="panel pressure col"><b>CityFlow residual</b> uses <b>Double only</b>, with one scalar head.</div>
</div>''', secs=85, notes=N(
    "Double and dueling are often confused. Double DQN is about the target: the online network chooses the best next action, and the target network scores that action. "
    "Example: online predicts A = −4 and B = −5, so it chooses A; target predicts A = −6 and B = −3; Double DQN uses −6 at A, even though the target prefers B. This reduces optimistic bias. "
    "Dueling is about the output layer: it separates the state value V from each action's advantage A and recombines them as Q = V + A minus the mean of A. "
    "The SUMO model uses both. The CityFlow model uses only Double, with one scalar output per macro.",
    ["Double = online chooses, target scores", "Dueling = V + A − mean A", "SUMO both · CityFlow Double only"],
    ["Do not say dueling reduces overestimation; that is Double's job."],
    [("Does dueling reduce overestimation?", "Not directly. Double handles choosing and scoring in the target; dueling splits V and A in the architecture.")]))

# ================================================================== SUMO
divider("SUMO", 4, "One junction in SUMO", "What does the model see, do, and optimise at the published junction?", 4.5)

vec16 = '<div style="display:flex;gap:4px">' + "".join(f'<div style="flex:1;height:40px;border-radius:5px;background:{c};color:#fff;font-weight:850;font-size:14px;display:flex;align-items:center;justify-content:center">{l}</div>'
                                                      for l, c in [("Q", C["go"])] * 4 + [("N", C["phaseB"])] * 4 + [("P", C["stop"])] * 4 + [("φ", C["caution"])] * 3 + [("t", C["base"])]) + "</div>"
slide("SUMO", "SUMO model: 16 numbers in, 3 Q-values out, every 10 seconds", f'''
<div class="row" style="gap:36px">
 <div class="col">
  <h3>Observation <span class="sub">approach order NW, SE, NE, SW</span></h3>{vec16}
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px 16px;margin-top:10px" class="xs">
   <div><b class="go">1–4</b> queue / 20</div><div><b style="color:{C["phaseB"]}">5–8</b> vehicle count / 20</div><div><b class="stop">9–12</b> due pending / 20</div>
   <div><b class="caution">13–15</b> one-hot green phase</div><div style="grid-column:span 2"><b class="muted">16</b> elapsed = min(t, 60) / 60</div></div>
  <div class="xs muted" style="margin:6px 0 22px">Queue of 10 → 0.5. Not clipped to [0, 1]: a queue of 40 → 2.</div>
  <h3>Action and execution</h3>
  <ul class="dots small"><li>3 actions map to SUMO green phases 0 / 2 / 4 (1 / 3 / 5 are yellow)</li><li>Each step lasts <b>10 s</b>; a switch runs <b>7 s yellow</b> first</li><li><b>Minimum green 20 s</b>; an early switch request keeps the current phase</li><li>Actual green can exceed the minimum because of the 10 s tick and yellow</li></ul>
 </div>
 <div style="width:540px;flex:none">
  <div class="panel" style="padding:12px 14px">{mlp("16", dueling=True)}
   <div class="eq" style="font-size:14px">(16·64+64)+(64·64+64)+(64·1+1)+(64·3+3)
= <span class="a">5,508</span> online parameters, written in NumPy</div></div>
  <div class="panel caution" style="margin-top:14px;padding:12px 18px"><b>Reading the output (illustrative).</b> <span class="small">Q = [−3.2, <b>−2.7</b>, −4.1] → action 1 → SUMO green phase 2, unless the current phase has not yet held green for 20 s.</span></div>
 </div>
</div>''', secs=100, source="src/traffic_rl/sim/sumo_single_junction.py · src/traffic_rl/agents/dqn.py · configs/danang_pilot.yaml", notes=N(
    "The SUMO observation has 16 numbers in the approach order NW, SE, NE, SW: four queues, four vehicle counts and four due-pending counts, all divided by 20; then a one-hot of the current green phase, and one timer since the last switch, divided by 60. "
    "The model outputs three Q-values for three green phases. Each step is 10 seconds; if the phase changes, 7 seconds of yellow come first. Minimum green is 20 seconds; an early switch request keeps the current phase. "
    "The network has two hidden layers of 64 ReLU units, then splits into V and A heads: 5,508 online parameters, implemented in NumPy.",
    ["16 = 4 queue + 4 count + 4 pending + 3 one-hot + 1 timer", "10 s step · 7 s yellow · 20 s min green", "16 → 64 → 64 → V/A → 3 Q · 5,508 params"],
    ["Do not describe an action as an instant light change; it always passes yellow and minimum green."],
    [("Why put pending vehicles in the state?", "So the model sees vehicles blocked at the boundary; otherwise a controller can look good by keeping vehicles out.")]))

slide("SUMO", "SUMO training: 5 seeds × 30 episodes, checkpoint chosen on validation", f'''
<div class="row" style="gap:34px">
 <div class="col">
  <h3>Reward and 3-step target</h3>
  <div class="eq" style="font-size:14.5px">r<sub>train</sub>(t) = −0.01 × [queue(t<sub>end</sub>) + pending(t<sub>end</sub>)]
R<sub>3</sub> = r<sub>t</sub> + γ r<sub>t+1</sub> + γ² r<sub>t+2</sub>
y  = R<sub>3</sub> + (1 − done) · γ³ · Q<sub>target</sub>(o<sub>t+3</sub>, a*)</div>
  <p class="xs" style="margin:6px 0 18px">γ = 0.99 <b>per 10 s decision</b>. Reward samples the end of each step; the headline metric integrates every second. Same direction, not identical.</p>
  <div class="row" style="gap:26px;margin-bottom:18px">{stat("360", "decisions per episode")}{stat("10,800", "decisions per seed")}{stat("120", "main test runs = 75 learned + 45 baseline")}</div>
  <div class="panel small" style="padding:12px 16px"><b>Hyperparameters.</b> lr 0.0003, Adam, Huber δ = 1, gradient clip 10, replay 50,000, batch 64, learning starts at 256, target sync every 200 updates, ε from 1.0 to 0.05 over 5,000 decisions (about episode 14).</div>
 </div>
 <div style="width:470px;flex:none">
  <h3>Per learning seed 11–15</h3>
  {vchain(["Initialise online, copy to target, create replay", "30 episodes × 3,600 s on <b>AM train</b> (demand 11 / sim 11)", "Every 10 s: ε-greedy, execute, 3-step transition, replay, one update",
           "<span style='color:#137257'>Every 5 episodes: greedy run on <b>AM validation</b> (demand 31 / sim 31), keep the best</span>", "<b>Evaluate the best checkpoint on 15 test cases</b>, no weight updates"])}
  <div class="note" style="margin-top:12px;font-size:15px">Trained on <b>AM only</b>, tested on normal, AM and PM.</div>
 </div>
</div>''', secs=75, source="scripts/train_danang_sumo.py · src/traffic_rl/train/trainer.py · configs/danang_pilot.yaml", notes=N(
    "The reward is the negative of queue plus pending at the end of each 10-second step, times 0.01. The target uses a 3-step return: three discounted rewards, then a Double-style bootstrap from the target network. "
    "Each learning seed from 11 to 15 trains 30 one-hour episodes on the same AM case: 360 decisions per episode, 10,800 per seed. Epsilon decays from 1 to 0.05 over 5,000 decisions, around episode 14. "
    "Every 5 episodes the model runs greedily on AM validation and the checkpoint with the lowest mean queue is kept. That checkpoint is then evaluated on 15 test cases: 120 main runs in total, 75 learned and 45 baseline.",
    ["30 episodes × 5 seeds · validation every 5", "Train AM only · test 3 regimes", "120 runs = 75 learned + 45 baseline"],
    ["Do not say each seed trains on different data; train and validation are shared."],
    [("Have 30 episodes converged?", "It is the experimental budget; validation picks the best checkpoint within it, which does not prove convergence.")]))

slide("SUMO", "What we measure and whom we compare against", f'''
<div class="row" style="gap:36px">
 <div class="col">
  <h3>Headline metric: queue integral</h3>
  <div class="eq">I = Σ<sub>t</sub> [Q<sub>network</sub>(t) + P<sub>due</sub>(t)] × Δt     <span class="c">veh-s</span>
I<sub>veh-h</sub> = I<sub>veh-s</sub> / 3600</div>
  <div style="display:flex;align-items:center;gap:18px;margin:16px 0 8px"><div class="hero" style="font-size:42px">10 veh × 60 s</div><div class="hero go" style="font-size:42px">= 600 veh-s</div></div>
  <div class="xs muted" style="margin-bottom:22px">= 1/6 veh-h. Reading only the last second misses the cost before it. The queue integral is not total travel delay.</div>
  <h3>Why add pending vehicles?</h3>
  <div class="eq" style="font-size:14.5px">scheduled = due + unreleased
pending   = due − inserted</div>
  <p class="small" style="margin-top:8px">A controller that blocks the entrance keeps vehicles outside and looks “good” if only inserted vehicles count. Only vehicles that are <b>due but blocked</b> count, never future ones.</p>
 </div>
 <div class="col">
  {table(["Controller", "How it decides", "Trained?"], [
      ["<span class='lamp' style='background:#8B97A1'></span><b>Published fixed</b>", "SUMO: the published 103 s plan", "No"],
      ["<span class='lamp' style='background:#8B97A1'></span><b>Tuned fixed</b>", "CityFlow: repeating plan, green picked from 20–60 s on validation → 25 s", "Search"],
      ["<span class='lamp' style='background:#3A74C9'></span><b>Max-Pressure</b>", "Phase with the largest Σ incoming − Σ outgoing waiting", "No"],
      ["<span class='lamp' style='background:#8FB1E3'></span><b>Hysteretic MP</b>", "Pressure plus hold condition and switch threshold", "No"],
      ["<span class='lamp' style='background:#1C9A73'></span><b>Learned</b>", "Predicted discounted return", "Yes"]], cls="t tight")}
  <h3 style="margin-top:22px">Secondary metrics, always read together</h3>
  <div><span class="tag">completion</span><span class="tag">insertion</span><span class="tag">travel time</span><span class="tag caution">spillback proxy</span><span class="tag">phase switches</span><span class="tag stop">collision / emergency</span><span class="tag dark">anchor violations</span></div>
  <div class="xs muted" style="margin-top:6px">Travel time covers completed trips only, so it carries survivor bias; read it with completion.</div>
 </div>
</div>''', secs=85, source="src/traffic_rl/sim/multi_agent_env.py · src/traffic_rl/eval/network_metrics.py · src/traffic_rl/agents/max_pressure.py", notes=N(
    "The headline metric is the queue integral: every second, add the vehicles waiting in the network and the vehicles that are due but cannot yet enter. Ten vehicles waiting sixty seconds is 600 vehicle-seconds, one sixth of a vehicle-hour. "
    "Why add pending vehicles? A controller that jams the entrance keeps vehicles outside the simulator; counting only vehicles inside would make it look good. But only due vehicles count, never future ones — that was a real bug earlier in the project and it has been fixed. "
    "Baselines are the fixed plan — published in SUMO, validation-tuned in CityFlow — Max-Pressure and hysteretic Max-Pressure. Secondary metrics such as completion, insertion, travel time and spillback are read together to avoid metric gaming.",
    ["10 veh × 60 s = 600 veh-s", "pending = due − inserted", "Baselines: fixed · MP · hysteretic MP"],
    ["Do not call the queue integral “total delay”."]))

# ================================================================== CityFlow
divider("CityFlow", 5, "53 junctions in CityFlow", "How do we let one policy edit 53 schedules without breaking them?", 6.5)

slide("CityFlow", "On 53 junctions, edit the schedule instead of picking phases freely", f'''
<div class="row" style="gap:36px">
 <div style="width:380px;flex:none">
  <h3 class="stop">Free phase choice everywhere</h3>
  <ul class="dots stop small"><li>A huge behaviour space: 53 junctions × every tick</li><li>Can break a stable service pattern</li><li>Hard to check and hard to explain</li><li>Earlier phase-based versions (V2, V3A) failed their gates</li></ul>
 </div>
 <div class="col">
  <h3 class="go">Schedule residual</h3>
  <p class="small" style="margin-bottom:14px">Start from a <b>reference schedule</b>; the model may only make <b>small, checkable edits</b>.</p>
  <div class="row" style="gap:14px">
   <div class="col rule-l go"><div style="font-size:22px;font-weight:850">Schedule</div><div class="xs">a fixed reference plan (25 s)</div></div>
   <div class="col rule-l go"><div style="font-size:22px;font-weight:850">Residual</div><div class="xs">the action shifts one boundary by ±10 s</div></div>
   <div class="col rule-l go"><div style="font-size:22px;font-weight:850">Anchored</div><div class="xs">the block ends in the reference signal state</div></div>
   <div class="col rule-l go"><div style="font-size:22px;font-weight:850">Double DQN</div><div class="xs">online chooses, target scores</div></div>
  </div>
 </div>
</div>
<div class="row" style="gap:20px;margin-top:34px">
 <div class="note col"><b>Trade-off.</b> The policy space is bounded. If a better plan needs large changes, the residual cannot reach it.</div>
 <div class="note go col"><b>Normal</b> runs the fixed plan from reset by design. <b>AM and PM</b> use the greedy residual. The model gets a declared time-of-day label; it does not classify peaks itself.</div>
</div>
<div class="panel" style="margin-top:18px;padding:14px 20px"><span class="small"><b>Macro 0 is always available</b> and keeps the reference schedule. Tied Q-values pick the baseline; non-finite features or scores fall back. Case IDs, seeds, file names and future flows are excluded from features.</span></div>''',
      secs=70, source="docs/research/haichau-v3b-residual-protocol.md · src/traffic_rl/agents/schedule_residual.py", notes=N(
    "On the network, letting a policy choose phases freely at 53 junctions creates a huge behaviour space and can break a stable service pattern; the earlier phase-based versions all failed their gates. "
    "So I moved to a residual: there is a reference schedule, and the model may only choose small edits. Read the name word by word: Schedule means a fixed reference plan; Residual means the action is a small edit; Anchored means each block ends in the reference signal state; Double DQN is how it learns. "
    "The price is a bounded policy. Macro 0, keeping the schedule, is always available, so the worst case is the baseline. In normal demand the controller runs fixed by design.",
    ["Schedule · Residual · Anchored · Double", "Macro 0 = keep schedule, always legal", "Trade-off: checkable behaviour vs flexibility"]))

steps = ["Start of block: read each junction's observation", "Build the reference schedule (minimum green, transitions)", "Macro 0 keeps the schedule unchanged",
         "Candidates shift <b>one</b> boundary 10 s earlier or later", "ShadowSignal replays each candidate and drops illegal ones", "The MLP scores legal candidates; one pick per junction",
         "Execute 30 ticks of 10 s", "End of block: check the anchor, collect reward"]
sth = "".join(f'<div style="display:flex;gap:10px;margin:5px 0;break-inside:avoid"><div class="hero go" style="font-size:22px;width:20px">{i+1}</div><div class="xs" style="padding-top:2px">{s}</div></div>' for i, s in enumerate(steps))
slide("CityFlow", "One macro: shift one boundary by 10 seconds, then return to the anchor", f'''
<div class="panel" style="padding:12px 14px">{macro_timeline()}</div>
<div class="row" style="gap:26px;margin-top:18px">
 <div style="flex:1.2"><h3>Eight steps in every block</h3><div style="columns:2;column-gap:22px">{sth}</div></div>
 <div class="col">
  <div class="panel dark" style="padding:16px 20px"><h3>The anchor does not reset traffic</h3><div class="small">Anchor = current phase + pending transition + timers. Only the <b style="color:#fff">controller state</b> must match the reference; queues and vehicle positions carry into the next block.</div></div>
  <div class="row" style="gap:24px;margin-top:16px">{stat("59", "MAX_MACROS = 1 + 2 × (30 − 1), padded slots with a mask")}{stat("0", "illegal requests or anchor mismatches accepted; the runtime raises an error")}</div>
 </div>
</div>''', secs=100, source="src/traffic_rl/sim/schedule_residual.py (ShadowSignal, macro compiler) · the timeline is an illustration of the idea", notes=N(
    "Here is one 300-second block. Suppose the reference schedule switches from phase A to B at second 100. The model can try two candidates: switch 10 seconds earlier, at 90, or 10 seconds later, at 110 — plus macro 0, keep it unchanged. "
    "Each candidate is replayed by ShadowSignal, which simulates signal logic, not vehicles, to check minimum green, transitions and, crucially, that the block ends in exactly the reference signal state, timers included. Candidates that fail are masked out. "
    "The MLP then scores the rest, each junction picks one, and the plan runs for 30 ten-second ticks. "
    "The key line: the anchor does not reset traffic. Two schedules can serve vehicles at different moments inside the block, so queues differ, even though the lights end in the same state. That is why a residual still has an effect.",
    ["±10 s at one boundary per block", "ShadowSignal checks legality and anchor", "Anchor matches the lights, NOT the traffic"],
    ["The 90 / 100 / 110 example is illustrative, not a macro taken from an artifact."],
    [("If it returns to the anchor, why does queueing change?", "Service timing inside the block changes queues; traffic is not reset, only the controller clock realigns.")]))

vec27 = '<div style="display:flex;gap:3px">' + "".join(f'<div style="flex:1;height:34px;border-radius:4px;background:{C["go"]}"></div>' for _ in range(12)) + '<div style="width:10px"></div>' + \
    "".join(f'<div style="flex:1;height:34px;border-radius:4px;background:{C["phaseB"]}"></div>' for _ in range(12)) + '<div style="width:10px"></div>' + \
    "".join(f'<div style="flex:1;height:34px;border-radius:4px;background:{C["stop"]}"></div>' for _ in range(3)) + "</div>"
feats = ["incoming queue mean", "incoming queue max", "incoming running mean", "outgoing queue mean", "outgoing spare capacity (40 − count)", "pressure (in − out, mean)",
         "is current phase", "elapsed green (s / 20)", "upstream queue mean", "downstream queue mean", "time since service (s / 20)", "movement count"]
fh = "".join(f'<div class="xs" style="padding:2px 0"><b class="go">{i+1}</b>&nbsp; {f}</div>' for i, f in enumerate(feats))
slide("CityFlow", "27 features per macro, one MLP shared by all 53 junctions", f'''
<div class="panel" style="padding:14px 18px"><h3>One candidate macro = 12 + 12 + 3</h3>{vec27}
 <div style="display:flex;margin-top:7px;font-size:15px;font-weight:800"><div style="flex:12" class="go">12 source-phase features</div><div style="flex:12;color:{C["phaseB"]}">12 target-phase features</div><div style="flex:3;text-align:right;white-space:nowrap" class="stop">3 descriptors</div></div></div>
<div class="row" style="gap:30px;margin-top:18px">
 <div class="col"><h3>Twelve features of one phase</h3><div style="columns:2;column-gap:18px">{fh}</div>
  <div class="xs muted" style="margin-top:8px">Descriptors: boundary = tick / 30, shift = ±1, is_baseline. Macro 0 averages the valid phase rows with descriptor [0, 0, 1].</div>
  <div class="note go" style="margin-top:12px;font-size:15px"><b>Why a scalar head?</b> The number of legal macros changes by junction and block. Scoring <b>each candidate</b> with one function and a mask handles any action-set size.</div></div>
 <div style="width:540px;flex:none"><div class="panel" style="padding:10px 14px">{mlp("27", w=520, h=200)}
  <div class="eq" style="font-size:14px">(27·64+64)+(64·64+64)+(64·1+1) = <span class="a">6,017</span> parameters</div>
  <div class="xs" style="margin-top:8px">One MLP scores every macro at every junction, then mask and argmax. <b>No</b> dueling, <b>no</b> GNN, <b>no</b> attention: neighbour information enters as scalar features.</div></div></div>
</div>''', secs=75, source="src/traffic_rl/sim/phase_encoder.py · src/traffic_rl/agents/phase_ddqn.py · src/traffic_rl/agents/schedule_residual.py", notes=N(
    "Each edit involves two phases: the phase before the boundary is the source and the phase after is the target. Each phase is described by 12 features: incoming queue mean and max, running vehicles, outgoing queue, spare capacity, pressure, whether it is the current phase, elapsed green, upstream and downstream queues, time since service, and movement count. "
    "Three more numbers describe where the boundary sits in the block, whether the shift is earlier or later, and whether it is macro 0. So 12 + 12 + 3 = 27. "
    "One MLP, 27 to 64 to 64 to 1, with 6,017 parameters, scores every candidate. The same weights serve all 53 junctions, so adding junctions does not add weights. "
    "Neighbour information is only summarised features; this is not a GNN or learned communication.",
    ["27 = 12 source + 12 target + 3 descriptor", "27 → 64 → 64 → 1 · 6,017 params", "Shared weights ≠ GNN"],
    ["Do not call it multi-agent communication or a graph neural network."],
    [("Do the 53 agents communicate?", "They see upstream and downstream queue summaries, share weights and a global reward; that is not learned communication.")]))

slide("CityFlow", "Residual training: network-wide reward, 12 episodes, 6 peak cases", f'''
<div class="row" style="gap:34px">
 <div class="col">
  <h3>Reward of one macro, network-wide</h3>
  <div class="eq" style="font-size:14.5px">r<sub>raw</sub>    = −[I(t + 300) − I(t)]      <span class="c">veh-s, queue + pending</span>
r<sub>critic</sub> = r<sub>raw</sub> / 100,000</div>
  <p class="xs" style="margin:6px 0 16px">Example: 500 vehicles on average over 300 s = 150,000 veh-s → r<sub>critic</sub> = −1.5. The same reward goes to all 53 transitions, and the baseline's cost is <b>not</b> subtracted.</p>
  <h3>Duration-aware target (SMDP)</h3>
  <div class="eq" style="font-size:14.5px">y = r<sub>critic</sub> + (1 − done) · γ<sup>Δt/300</sup> · Q<sub>target</sub>(o′, a*)</div>
  <p class="xs" style="margin:6px 0 16px">γ = 0.99 <b>per 300 s</b>, unlike 0.99 per 10 s in SUMO.</p>
  <div class="panel caution small" style="padding:12px 16px"><b>Initialisation.</b> Output head W3 and b3 start at 0, so every Q starts equal and greedy picks macro 0. A <b>fixed ε = 0.15</b> explores other macros. No imitation loss.</div>
 </div>
 <div style="width:480px;flex:none">
  <div class="row" style="gap:22px;margin-bottom:16px">{stat("7,632", "transitions per seed, AM 3,816 + PM 3,816", "go")}{stat("1,152", "optimizer updates = 12 × 12 × 8", "ink")}</div>
  {table(["Per learning seed", "Value"], [["Episodes", "12 × 3,600 s"], ["Blocks per episode", "12"], ["Transitions per block", "53"], ["Batch, replay, start", "128, 20,000, ≥ 53"],
       ["Target copy", "every 64 updates (8 blocks)"], ["Validation, checkpoints", "every 4 episodes → ep 4, 8, 12"]], cls="t tight")}
  <div class="note stop" style="margin-top:12px;font-size:15px">Nine train cases exist, but only the <b>six peak cases</b> (3 AM + 3 PM) train the residual, twice each. The 7,632 transitions are <b>strongly correlated</b>, not 7,632 experiments.</div>
 </div>
</div>''', secs=75, source="src/traffic_rl/train/schedule_residual_trainer.py · docs/research/evidence-snapshot-2026-09-23/seed14-resolved-config.json", notes=N(
    "The reward of one macro is the negative increase of the network queue integral over 300 seconds, pending included, divided by 100,000 to bring it to a workable scale. For example, 500 vehicles waiting on average for 300 seconds is 150,000 vehicle-seconds, a critic reward of −1.5. "
    "This reward is network-wide, identical for all 53 transitions, and it does not subtract the baseline's cost — “residual” only describes the action. "
    "The target is written by macro duration, with gamma 0.99 per 300 seconds. The output head starts at zero, so the model initially picks macro 0, and a fixed epsilon of 0.15 explores. "
    "Each seed trains 12 episodes on 6 peak cases: 7,632 transitions and 1,152 updates. Every 4 episodes a checkpoint is saved and validated; “step-4” means after episode 4.",
    ["Reward = −Δ(queue + pending) network / 100,000", "12 ep · 7,632 transitions · 1,152 updates", "step-4 = episode 4"],
    ["Not “8 updates × 53 junctions”: 8 updates per network block."],
    [("What is wrong with a global reward?", "It fits the cooperative goal but makes credit assignment hard; local or difference rewards are future work.")]))

gates = ["Normal matches fixed case by case, no phase or timer divergence", "Mean queue regret of each peak regime ≤ 0", "Mean peak queue regret ≤ −1%",
         "Completion and insertion loss per case ≤ 2 percentage points", "Learned macros in AM and PM, at ≥ 2 junctions", "0 illegal requests, 0 anchor violations, forced macro 0 = fixed 25",
         "The checkpoint reacts when traffic features change"]
seedcards = "".join(f'''<div class="col" style="text-align:center;padding:14px 4px;border-radius:12px;background:{"#DDF1E9" if ok else "#F8E1DE"}">
 <div class="xs muted">seed</div><div class="hero" style="font-size:44px;color:{C["go"] if ok else C["stop"]}">{s}</div>
 <div style="font-weight:850;font-size:15px;color:{C["go"] if ok else C["stop"]};margin-top:6px">{st}</div><div class="xs muted">{ep}</div></div>'''
                    for s, st, ep, ok in [("12", "selected", "episode 8", True), ("13", "rejected", "ep 12, diagnostic", False), ("14", "selected", "episode 4", True),
                                          ("15", "selected", "episode 8", True), ("16", "rejected", "ep 4, diagnostic", False)])
slide("CityFlow", "Finishing training is not acceptance: the validation selector", f'''
{chain([("Training finished", "weights and logs exist"), ("Selector V1 accepts", "an eligible checkpoint for that seed"), ("Strict release verifier", "the full evidence package")])}
<div class="row" style="gap:34px;margin-top:22px">
 <div class="col"><h3>Selector V1 checks, on validation</h3><ul class="dots small">{"".join(f"<li>{g}</li>" for g in gates)}</ul>
  <div class="xs muted" style="margin-top:6px">Ranked by mean peak regret; ties pick the earlier checkpoint. If none passes, it <b>fails closed</b> instead of taking the least bad.</div></div>
 <div style="width:560px;flex:none">
  <div class="row" style="gap:8px">{seedcards}</div>
  <div class="note stop" style="margin-top:16px;font-size:15.5px">Seeds 13 and 16 were rejected. Positive test numbers later do <b>not</b> reverse the validation decision. The gates are empirical thresholds, not a non-inferiority test.</div>
  <div class="note ink" style="margin-top:10px;font-size:15.5px">Strict verifier: <b>complete = false</b>, 14 release gates still open (audit of 23 Sep).</div>
 </div>
</div>''', secs=60, source="configs/haichau_residual_final_selection_v1.yaml · docs/research/evidence-snapshot-2026-09-23/seed*-selection.json", notes=N(
    "I separate three states: training finished, selector accepted, and strict release. Selector V1 runs on validation and checks that normal matches fixed exactly; that regret in each peak regime is not positive and the mean falls by at least 1 percent; that completion and insertion do not drop more than 2 percentage points; that learned macros appear in both AM and PM; and that the execution contract is never violated. "
    "If nothing passes, it fails closed. Result: seeds 12, 14 and 15 are selected; 13 and 16 are rejected. I still report those two as diagnostics, but I never reverse the decision. "
    "The strict release verifier is not complete yet, with 14 gates open — I say this directly.",
    ["3 states: trained → selected → released", "Seeds 12 / 14 / 15 selected · 13 / 16 rejected", "Fails closed · strict release incomplete"]))

# ================================================================== Results
divider("Results", 6, "What the evidence shows", "Where does learning help, where does it hurt, and who wins on the network?", 7, lit="caution")

sumo_series = [("Published fixed", C["base"]), ("Dueling DDQN, 5 seeds", C["go"]), ("Max-Pressure", C["pressure"]), ("Hysteretic MP", C["pressure2"])]
sumo_vals = [[9.86, 79.20, 152.67], [41.50, 78.41, 99.97], [140.72, 352.43, 269.02], [126.85, 281.52, 241.40]]
slide("Results", "SUMO: a clear win at PM, a draw at AM, a loss at normal", f'''
<div class="row" style="gap:0;margin-bottom:14px">
 <div class="col" style="border-left:6px solid {C["stop"]};padding-left:18px"><div class="hero stop" style="font-size:64px">+320.7%</div><div class="small"><b>Normal</b> 9.86 → 41.50 veh-h, CI [7.60, 56.14]</div></div>
 <div class="col" style="border-left:6px solid {C["caution"]};padding-left:18px"><div class="hero caution" style="font-size:64px">−1.0%</div><div class="small"><b>AM</b> 79.20 → 78.41 veh-h, CI [−9.47, 8.49]</div></div>
 <div class="col" style="border-left:6px solid {C["go"]};padding-left:18px"><div class="hero go" style="font-size:64px">−34.5%</div><div class="small"><b>PM</b> 152.67 → 99.97 veh-h, CI [−69.55, −35.34]</div></div>
</div>
<div class="row" style="gap:30px">
 <div style="width:660px;flex:none">{legend(sumo_series, 13.5)}{grouped_bars(["Normal", "AM peak", "PM peak"], sumo_series, sumo_vals, 400, w=660, h=300, unit="queue + pending, veh-h")}</div>
 <div class="col">
  <h3>How to read it</h3>
  <ul class="dots small"><li><b class="go">PM:</b> clear reduction; the CI excludes 0</li><li><b class="caution">AM:</b> the mean equals fixed; the CI includes 0</li><li><b class="stop">Normal:</b> much worse, so no case for RL in every regime</li><li>Both pressure baselines lose to fixed at this junction</li></ul>
  <p class="xs muted" style="margin-top:10px">CI of learned − fixed in veh-h: paired bootstrap over 5 seed effects, 20,000 resamples. Completion DDQN 93.5 / 91.8 / 89.7% vs fixed 98.1 / 89.6 / 82.8%.</p>
 </div>
</div>''', secs=120, kind="results", source="SUMO · dueling_n3 · 5 learning seeds × 15 test cases · queue integral + pending (veh-h) · results/danang_protocol_v1/summary/final-summary.csv", notes=N(
    "These are the SUMO results on 15 test cases, averaged over five learning seeds. At PM, the fixed plan accumulates 152.67 vehicle-hours and the model 99.97: a 34.5 percent reduction, with a confidence interval of the difference entirely below zero. "
    "At AM, the regime the model was trained on, the mean is essentially the fixed plan and the interval includes zero. At normal, the model is clearly worse: 41.5 versus 9.86, an increase of 320.7 percent. "
    "Both pressure baselines are worse than fixed in all three regimes. Conclusion: the benefit depends on the regime; the results do not support running RL unconditionally at all times. "
    "The interval is a bootstrap over five seed effects, not over 75 cells.",
    ["PM −34.5% · AM −1.0% (CI includes 0) · Normal +320.7%", "CI = bootstrap over 5 seed effects", "MP and hysteretic MP lose to fixed in SUMO"],
    ["Never report PM alone; always say normal is worse."],
    [("Why is normal worse?", "The policy trained on AM only; distribution shift or action timing are hypotheses, not established by ablation.")]))

slide("Results", "Reading the SUMO result: hypotheses, ablation and simulated safety", f'''
<div class="row" style="gap:34px">
 <div style="width:600px;flex:none"><img class="fig" src="{img("curves")}" style="width:600px;height:340px;object-fit:contain">
  <div class="cap">Validation mean queue by episode for five learning seeds. The best checkpoint can come before the last episode; seed 13 swings widely.</div></div>
 <div class="col">
  <div class="rule-l stop" style="margin-bottom:14px"><b>Why normal is worse: hypotheses only.</b><div class="small">Training on AM alone suggests distribution shift, overfitting or action timing. <b>Not</b> established by ablation.</div></div>
  <div class="rule-l pressure" style="margin-bottom:14px"><b>Why Max-Pressure struggles here.</b><div class="small">Only four movements are observed, and each switch costs 7 s of clearance against a 10 s tick. This does not refute pressure theory.</div></div>
  <div class="rule-l caution" style="margin-bottom:14px"><b>Seed-11 ablation.</b><div class="small">Best validation: dqn_base ≈ 81.43, dueling_n3 ≈ 71.71. Dueling and n-step changed <b>together</b>, one seed, so contributions are not separated.</div></div>
  <div class="rule-l go"><b>Simulator safety events.</b><div class="small">Main 120 runs: <b>0 collisions, 0 emergencies</b>. Sensitivity 120 runs: 0 collisions, 4 emergencies. Not a field safety certificate.</div></div>
 </div>
</div>''', secs=60, kind="results", source="results/danang_protocol_v1/summary/validation-learning-curves.png · paper/thesis_danang.tex, Results", notes=N(
    "The validation curves show that the best checkpoint is not always the last episode, and that seed 13 swings widely — which is why checkpoints are chosen on validation. "
    "Normal may be worse because the policy only trained on AM, but that is a hypothesis without an ablation behind it. Max-Pressure struggles because only four movements are observed and every switch costs 7 seconds of clearance. "
    "The seed-11 ablation shows dueling n3 ahead of the base model on validation, but it changed two components at once on one seed, so I do not separate their contributions. "
    "On simulated safety: 120 main runs had no collisions and no emergency events.",
    ["Best checkpoint ≠ last episode", "MP struggles: partial observation + 7 s clearance", "0 collisions / 0 emergencies in 120 runs"]))

slide("Results", "Is the baseline ranking luck? 1,000 demand realizations, no RL", f'''
<div class="row" style="gap:0;margin-bottom:12px">
 <div class="col" style="border-left:6px solid {C["base"]};padding-left:16px"><div class="hero" style="font-size:44px">3,000 / 3,000</div><div class="small">Fixed &lt; <b>Max-Pressure</b> in every paired realization</div></div>
 <div class="col" style="border-left:6px solid {C["base"]};padding-left:16px"><div class="hero" style="font-size:44px">2,999 / 3,000</div><div class="small">Fixed &lt; <b>Hysteretic MP</b></div></div>
 <div class="col" style="border-left:6px solid {C["caution"]};padding-left:16px"><div class="hero caution" style="font-size:44px">100 · 76 · 88%</div><div class="small">Hysteretic &lt; raw MP at normal · AM · PM; multimodal at peaks</div></div>
</div>
<img class="fig" src="{img("mc")}" style="width:1136px;height:400px;object-fit:contain">
<div class="cap">9,000 SUMO runs = 1,000 paired (demand seed, SUMO seed) realizations × 3 regimes × 3 baselines, queue + pending (veh-h). Count-preserving departure times of <b>one</b> observed profile, not 1,000 traffic days. Seeds disjoint from train / validation / test. The learned controller is not included (training cost).</div>''', secs=45, kind="results", source="SUMO · scripts/run_danang_baseline_mc.py · results/danang_baseline_mc/summary.json · parity: reproduces test case AM-101 exactly", notes=N(
    "Is the baseline ranking an accident of the five test realizations? I re-ran only the three non-learning baselines on 1,000 fresh demand realizations per regime: 9,000 SUMO runs, each controller seeing the same departures and the same SUMO seed. "
    "Fixed beats raw Max-Pressure in all 3,000 pairs and hysteretic Max-Pressure in 2,999 of 3,000. Hysteretic beats raw MP always at normal, 76 percent at AM and 88 percent at PM, but at the peaks it is multimodal: it locks into different phase patterns from run to run. "
    "The medians, 9.9, 78.5 and 149.3 vehicle-hours for fixed, are close to the 15-case means of 9.9, 79.2 and 152.7, so the main table was not drawn from lucky cases. "
    "These are realizations of one observed profile, not 1,000 days, and the learned model is not in this experiment.",
    ["9,000 runs = 1,000 × 3 regimes × 3 baselines", "Fixed < MP 3,000/3,000 · < hysteretic 2,999/3,000", "One observed profile, not 1,000 days · no RL"],
    ["Do not say the 1,000 runs include the learned model.", "Do not call them 1,000 independent traffic days."],
    [("Why not run the DQN 1,000 times too?", "Training costs dominate; the learned result stays at 5 seeds × 15 cases. This experiment only tests whether the baseline ranking is stable."),
     ("Why is hysteretic MP so spread out?", "Its hold rule makes the phase sequence path-dependent, so small departure changes lock it into different cycles; the bands in the plot are those cycles.")]))

cf_rows = [("Tuned fixed", 8339.43, C["base"], "baseline, 0%"), ("Max-Pressure", 6347.00, C["pressure"], "−23.89% vs fixed, best"),
           ("Hysteretic MP", 6739.13, C["pressure2"], "−19.19% vs fixed"), ("Residual DDQN s14", 7829.25, C["go"], "−6.12% vs fixed")]
slide("Results", "CityFlow: Max-Pressure is still best; the residual cuts 6.12% versus fixed", f'''
<div class="row" style="gap:34px">
 <div style="width:660px;flex:none">
  <h3>Total queue cost over 15 cases <span class="sub">veh-h</span></h3>
  {hbars(cf_rows, 8800, w=660, row_h=76, label_w=190)}
 </div>
 <div class="col">
  <div class="row" style="gap:24px;margin-bottom:18px">{stat("−23.89%", "Max-Pressure", "pressure", 44)}{stat("−6.12%", "Residual, one policy", "go", 44)}</div>
  {table(["Pooled reduction vs fixed", "Normal", "AM", "PM"], [["Max-Pressure", "26.72%", "23.85%", "22.66%"], ["Hysteretic MP", "<b>35.60%</b>", "9.95%", "17.37%"],
        ["Residual s14", "0% (fixed)", "3.48%", "<b>10.39%</b>"]], cls="t tight", align=["", "r", "r", "r"], rowcls={2: "go"})}
  <div class="note stop" style="margin-top:16px;font-size:15.5px">This is <b>one policy</b> (seed 14, episode 4). 6.12% is not a five-seed mean, and absolute values are not comparable with SUMO.</div>
 </div>
</div>''', secs=100, kind="results", source="CityFlow · residual seed14 / episode4 · 15 matched cases × 3,600 s · queue + pending, veh-h · pooled reduction vs tuned fixed · final15-controller-matrix-summary.json", notes=N(
    "On the 53-junction network, this is the 15-case matrix for one policy: seed 14, checkpoint episode 4. Total queue cost for tuned fixed is 8,339 vehicle-hours; the residual brings it to 7,829, a 6.12 percent reduction. "
    "But Max-Pressure cuts 23.89 percent and hysteretic Max-Pressure 19.19 percent. So Max-Pressure is the best controller by queue cost in this matrix. "
    "By regime, the residual equals fixed at normal by design, cuts 3.48 percent at AM and 10.39 percent at PM. The correct statement: the residual improves on fixed but does not beat the pressure baselines. "
    "It is one policy, not a five-seed average.",
    ["Fixed 8,339 · MP 6,347 · HMP 6,739 · Residual 7,829", "MP −23.89% beats residual −6.12%", "One policy: seed 14, episode 4"],
    ["Never say “RL is best” on the network."],
    [("Why does Max-Pressure win?", "Possibly the learning budget, credit assignment under a global reward, and the bounded residual action space; no ablation ranks these causes yet.")]))

slide("Results", "Less queueing does not mean every metric improves", f'''
<div class="row" style="gap:36px">
 <div class="col">
  {table(["Mean over 15 cases", "Fixed", "Residual s14", "Change"], [
      ["Completion", "66.92%", "67.98%", "<b class='go'>+1.06 pp</b>"], ["Insertion", "97.15%", "97.97%", "<b class='go'>+0.82 pp</b>"],
      ["Completed travel time", "737.81 s", "743.26 s", "<b class='stop'>+5.45 s</b>"], ["Spillback proxy", "1,432.33 lane-s", "1,497.53 lane-s", "<b class='stop'>+65.20 lane-s</b>"]], cls="t", align=["", "r nw", "r nw", "nw"])}
  <div class="note" style="margin-top:18px">Travel time counts completed trips only. When completion rises, the set of trips changes, so one number cannot say every vehicle got slower.</div>
 </div>
 <div class="col">
  <h3>Two correct percentages for PM, seed 14</h3>
  <div class="eq" style="font-size:14px">mean per-case = mean<sub>c</sub> 100 · (F<sub>c</sub> − L<sub>c</sub>) / F<sub>c</sub>
pooled        = 100 · (ΣF − ΣL) / ΣF</div>
  <div class="row" style="gap:30px;margin:20px 0">{stat("8.86%", "mean per-case reduction", "go", 56)}{stat("10.39%", "pooled reduction", "go", 56)}</div>
  <p class="small">Example: fixed 100 and 1,000, learned 90 and 800 → mean 15%, pooled 19.09%. <b>Both are correct</b>; pooled weights heavy cases more.</p>
 </div>
</div>''', secs=70, kind="results", source="CityFlow · seed14 / ep4 · 15 cases · final15-seed14-secondary-summary.json", notes=N(
    "Secondary metrics show a trade-off. Completion rises by about one percentage point and insertion by 0.8 points, so the queue did not fall by blocking vehicles. But completed travel time rises by 5.45 seconds and the spillback proxy by 65 lane-seconds. "
    "Travel time has survivor bias: when more trips complete, the set of trips being averaged changes. "
    "A likely question: why two PM numbers, 8.86 and 10.39 percent? 8.86 is the average of per-case percentages, each case weighted equally; 10.39 is on the totals, so heavy cases weigh more. Both are correct answers to different questions.",
    ["Completion +1.06 · insertion +0.82 pp", "Travel time +5.45 s · spillback +65 lane-s", "8.86% mean-case vs 10.39% pooled"]))

slide("Results", "Exploratory: residual at PM only, across five learning seeds", f'''
<div class="row" style="gap:34px">
 <div style="width:610px;flex:none">
  <h3>Pooled reduction over 15 cases <span class="sub">normal → fixed, AM → fixed, PM → residual</span></h3>
  {gate_chart(w=610, h=330)}
  <div class="xs muted">Solid = selected; dashed outline = diagnostic checkpoint after rejection; <b class="caution">amber dashed line = mean 3.48%</b>, band = 95% CI [2.01, 4.95].</div>
 </div>
 <div class="col">
  <div class="row" style="gap:24px;margin-bottom:22px">{stat("3.48%", "mean of five seeds", "caution", 50)}{stat("1.03–5.62%", "seed range", "ink", 36)}</div>
  <div class="row" style="gap:24px;margin-bottom:20px">{stat("15 / 25", "PM cells improved", "go", 40)}{stat("10 / 25", "PM cells worse than fixed", "stop", 40)}</div>
  <p class="small">Seed-bootstrap 95% CI <b>[2.01%, 4.95%]</b>, 10,000 resamples. The 50 normal and AM cells equal fixed by design.</p>
  <div class="note stop" style="margin-top:14px;font-size:15.5px"><b>Post hoc.</b> The gate was chosen <b>after seeing test results</b> and uses diagnostic checkpoints of seeds 13 and 16. A positive CI does <b>not</b> remove selection bias, so a fresh independent test is required.</div>
 </div>
</div>''', secs=75, kind="results", source="CityFlow · 5 learning seeds × 15 cases · pooled reduction vs fixed · final15-regime-gated-direct-multi-seed-summary.json · exploratory", notes=N(
    "Because the residual helped most at PM, I analysed one more gate: normal and AM run fixed, only PM uses the residual, for all five learning seeds. "
    "The mean reduction is 3.48 percent over 15 cases, ranging from 1.03 to 5.62 percent, with a seed-level bootstrap interval of 2.01 to 4.95 percent. But of 25 PM cells, 10 are still worse than fixed. "
    "Most importantly, this is an exploratory analysis done after seeing the test results, and it includes the two rejected seeds. A positive interval does not remove selection bias. To become a confirmed claim, the gate must be frozen and run on a fresh test.",
    ["Mean 3.48% · CI [2.01, 4.95] · range 1.03–5.62", "10 / 25 PM cells still worse", "POST HOC — needs a fresh test"],
    ["Never present this as the main or a confirmed result."],
    [("The mean is positive but 10 of 25 are worse?", "Gains in the good cases outweigh losses in the bad ones; a positive mean is no per-case guarantee. A fresh test needs a pre-set per-case threshold.")]))

# ================================================================== Wrap-up
divider("Wrap-up", 7, "Demo and conclusions", "What can I claim today, and what comes next?", 6)

demo_steps = [("15 s", "Whole network", "53 controlled signals from OSM topology; demand and schedules are simulated."),
              ("20 s", "Reset to guided view", "Same PM case, demand 105 / sim 205, time-synchronised; seed 14, episode 4."),
              ("20 s", "Frame 1,085 s (18:05)", "Junction 420249521: fixed has 14 queued, residual 1, so 13 fewer at this moment."),
              ("20 s", "Play and Linked junctions", "Queues and signals over time; inspect neighbouring junctions."),
              ("15 s", "Back to the aggregate", "A frame illustrates behaviour; conclusions rest on full-hour, multi-case evaluation.")]
dh = "".join(f'<div style="display:flex;gap:14px;margin:9px 0"><div class="hero go" style="font-size:20px;width:52px;flex:none">{t}</div><div class="small"><b>{a}.</b> {b}</div></div>' for t, a, b in demo_steps)
slide("Wrap-up", "Demo: a traceable recorded replay of PM demand 105", f'''
<div class="row" style="gap:30px">
 <div style="width:620px;flex:none"><img class="fig" src="{img("demo")}" style="width:620px;height:auto">
  <div class="cap">Browser demo: tuned fixed (left) and schedule residual (right) at 18:05 elapsed. Launch with <span class="mono">python3 launch_demo.py --no-browser --port 8766</span>.</div></div>
 <div class="col"><h3>A 90-second script</h3>{dh}
  <div class="note" style="margin-top:12px;font-size:14.5px"><b>18:05</b> is 18 minutes 5 seconds elapsed, not 6:05 pm. Telemetry covers 0–1,200 s. The browser does <b>not</b> train or simulate. “13 fewer queued” ≠ “13 more released”.</div></div>
</div>''', secs=120, source="results/haichau_network_v2/demo-visual/manifest.json · docs/defense/demo-runbook.md", notes=N(
    "[Switch to the browser if the demo is already open; otherwise use this screenshot.] "
    "This is the 53-junction network built from OSM; demand and schedules are simulated. I press Reset to guided view: both sides are the same PM case, demand 105 and simulator seed 205, time-synchronised; the right side is the residual, seed 14, episode 4. "
    "At 18 minutes 5 seconds of simulation, at junction 420249521, fixed has 14 queued vehicles and the residual has 1 — 13 fewer at this moment. I press Play and Linked junctions to show the neighbours. "
    "Finally I return to the aggregate table: this frame only illustrates behaviour; the quantitative conclusion comes from full-hour, multi-case evaluation. This is a recorded replay; the browser does not train or run a simulator.",
    ["PM demand 105 / sim 205 · seed 14 ep 4", "Junction 420249521: 14 vs 1 at 18:05", "Recorded replay; end on the aggregate"],
    ["Do not call 18:05 a clock time.", "Do not infer 13 extra vehicles released."],
    [("Does the demo run RL live?", "No. It is a recorded replay; final metrics come from a separate 3,600 s evaluation.")]))

can = ["RL cuts queueing at <b>PM</b> on the SUMO test set (−34.5%, CI excludes 0)", "The benefit <b>depends on the regime</b>; normal is clearly worse",
       "The 53-junction residual cuts 6.12% versus tuned fixed <b>for one policy</b>", "Max-Pressure beats the residual in the current matrix",
       "The residual keeps its execution contract: 0 illegal requests, 0 anchor violations", "A traceable chain from source to configuration, checkpoint and result"]
cannot = ["RL beats fixed at all times of day", "State of the art, or beating strong baselines on the network", "The 3.48% PM-only gate is a confirmed result",
          "Field performance or readiness to deploy", "The camera day represents many days or seasons", "A matching hash or a positive CI means safe deployment"]
slide("Wrap-up", "What I can claim, and what I cannot", f'''
<div class="row" style="gap:36px">
 <div class="col"><div style="display:flex;align-items:center;gap:12px;margin-bottom:10px"><span class="lamp" style="width:26px;height:26px;background:{C["go"]}"></span><h3 style="margin:0;font-size:24px">Supported by current evidence</h3></div><ul class="dots" style="font-size:19px">{"".join(f'<li style="margin:10px 0">{x}</li>' for x in can)}</ul></div>
 <div class="col"><div style="display:flex;align-items:center;gap:12px;margin-bottom:10px"><span class="lamp" style="width:26px;height:26px;background:{C["stop"]}"></span><h3 style="margin:0;font-size:24px">Not claimed</h3></div><ul class="dots stop" style="font-size:19px">{"".join(f'<li style="margin:10px 0">{x}</li>' for x in cannot)}</ul></div>
</div>
<div class="panel dark" style="margin-top:28px;font-size:19px">The right frame: a study of <b style="color:#6FD3B0">system development and simulation evaluation with failure analysis</b>. Models, implementation, experiments, sources and limits are all on the table.</div>''', secs=85, notes=N(
    "To make the committee's job easy, I separate two columns. Supported: RL reduces PM queueing in SUMO; the benefit depends on the regime; the residual cuts 6.12 percent versus fixed for one policy; Max-Pressure beats the residual; the residual keeps its contract; and there is a traceable chain. "
    "Not claimed: RL wins at all times, beats strong baselines, a confirmed PM-only gate, field performance, or data that represents many days. "
    "I see the thesis as system development and simulation evaluation that also publishes its negative results.",
    ["Green column = allowed claims", "Red column = forbidden claims", "Frame: system + simulation evaluation"]))

slide("Wrap-up", "Contributions, limits and next steps", f'''
<div class="row" style="gap:30px">
 <div class="col"><h3 class="go">Contributions</h3><ul class="dots small">
  <li><b>Two research tiers</b>: a published junction and a 53-junction OSM network</li><li>Controllers with <b>explicit, coded</b> state, action and reward</li>
  <li>A <b>traceable residual action</b>: shift one boundary, check legality, return to the anchor</li><li><b>Paired</b> evaluation, separated learning seeds, pending counted, negative results published</li>
  <li>A chain from source to data, configuration, checkpoint, result and demo</li></ul></div>
 <div class="col"><h3 class="stop">Limits</h3><ul class="dots stop small">
  <li>Camera data: one day, four movements, approximate digitisation; synthetic network demand</li><li>No field trajectory calibration; lane model, no sublane</li>
  <li>Normal regression in SUMO; Max-Pressure beats the residual on the network</li><li>The test set was used to fix the simulator (tau 1.2) and to pick a post hoc gate</li>
  <li>Strict release incomplete; some raw artifacts live outside Git</li></ul></div>
 <div class="col"><h3 class="caution">Next steps</h3><ul class="dots caution small">
  <li><b>Freeze</b> policy and gate, then run a fresh independent test</li><li>Complete artifacts and runtime bindings for reproduction</li>
  <li><b>Ablations</b>: dueling, n-step, neighbour features, global reward, residual bounds</li><li>Sensitivity to digitisation error and demand</li>
  <li>Multi-day data and field calibration before any wider claim</li></ul></div>
</div>
<div class="note ink" style="margin-top:22px;font-size:15.5px">Not claimed as contributions: inventing Double DQN or dueling, industry-wide state of the art, citywide improvement, or readiness to control real signals.</div>''',
      secs=115, notes=N(
    "The thesis contributes five things: a two-tier research design; controllers with explicit state, action and reward; a traceable residual action; a paired evaluation that counts pending vehicles and publishes bad results; and a trace chain from source to demo. "
    "Limits: camera data is one day and four movements; the network uses synthetic demand; there is no calibration; normal is worse in SUMO and Max-Pressure wins on the network; the test set was used to fix the simulator and choose the gate; strict release is incomplete. "
    "Next steps in priority order: freeze policy and gate and run a fresh test; complete the artifacts; ablate each component; run sensitivity analyses; and only then multi-day data and field calibration.",
    ["5 contributions — stress traceable residual + paired evaluation", "State the limits before being asked", "Priority: freeze → fresh test → ablations"],
    [], [("What would you improve first?", "Freeze policy and gate, and run a fresh independent test with strong baselines and several seeds; then ablations and calibration.")]))

slide("Wrap-up", "", f'''
<div style="position:absolute;right:120px;top:120px">{signal_head("go", 130, 420)}</div>
<div style="position:absolute;left:72px;top:110px;width:900px;font-size:40px;line-height:1.22;font-weight:800;color:#fff;letter-spacing:-.02em">Reinforcement learning can reduce queueing in some simulated regimes, but the benefit is uneven and does not yet beat strong baselines on the network.</div>
<div style="position:absolute;left:72px;top:352px;width:860px;font-size:21px;line-height:1.5;color:#AFC0CC">Contributions: two experimental tiers, a residual controller with checkable behaviour, and an evidence trace. Next: freeze policy and gate, test on fresh demand, then add calibration and field data.</div>
<div style="position:absolute;left:72px;top:540px;font-size:48px;font-weight:850;color:#fff">Thank you.</div>
<div style="position:absolute;left:72px;top:604px;font-size:20px;color:#6FD3B0">I welcome your questions and comments.</div>
''', secs=45, kind="closing", notes=N(
    "The results show that reinforcement learning can reduce queueing in some simulated regimes, but the benefit is uneven and does not yet beat strong baselines on the current network. "
    "The thesis contributes two experimental tiers, a residual controller whose behaviour can be checked, and an evidence-tracing workflow. "
    "The next step is to freeze the policy and gate, test on fresh independent demand, and add calibration and field data before widening any claim. Thank you, and I welcome your questions.",
    ["Deliver the closing almost word for word", "Stop, smile, wait for questions", "Open backup slides when asked"]))

# ================================================================== backup
slide(B, "B1 · Parameters of the two reported models", table(["Parameter", "SUMO dueling_n3", "CityFlow residual V3B"], [
    ["Input, hidden, output", "16; 64, 64; V 1 + A 3 → 3 Q", "27 per macro; 64, 64; scalar Q per macro"], ["n-step, action slots", "3; 3", "one macro transition; 59 with mask"],
    ["Learning rate, Adam β1 / β2 / ε", "0.0003; 0.9 / 0.999 / 1e−8", "0.0003; 0.9 / 0.999 / 1e−8"], ["Huber δ, gradient clip (L2)", "1; 10", "1; 10"],
    ["Replay, batch, learning starts", "50,000; 64; 256", "20,000; 128; 53"], ["Updates, target sync", "1 per decision; 200 updates", "8 per network macro; 64 updates"],
    ["γ, reward scale", "0.99 per 10 s; × 0.01", "0.99 per 300 s; ÷ 100,000"], ["ε in training", "1.0 → 0.05 over 5,000 decisions", "fixed 0.15"],
    ["Tick, macro, shift", "10 s; none; none", "10 s; 300 s; ±10 s at one boundary"], ["Min green, yellow, max red", "20 s; 7 s; not applied", "20 s; 3 s by contract; 180 s"],
    ["Fixed baseline", "32 / 28 / 22 + 3 × 7 = 103 s", "25 s nominal green"], ["Episodes, eval, seeds", "30; every 5; 11–15", "12; every 4; 12–16"],
    ["Output-head init, warm start", "SharedDQN init; 0", "W3 / b3 = 0; no imitation"]], cls="t tight"), secs=0, kind="backup",
      source="configs/danang_pilot.yaml · seed14-resolved-config.json · seed14-step4-contract.json", notes=N(
          "Use when asked about parameters. Stress that the values have engineering motives but are not proven optimal; apart from the fixed-duration search there was no hyperparameter search.",
          ["target_sync = 64 updates, not seconds", "γ has different step units", "No hyperparameter search beyond fixed duration"]))

slide(B, "B2 · Replay, exploration, loss and optimizer", f'''
{table(["Mechanism", "Purpose", "In this project"], [["Replay buffer", "Reuse experience, weaken correlation of consecutive samples", "Ring buffer, uniform sampling <b>with replacement</b>"],
    ["ε-greedy", "Explore instead of always taking the current best", "With probability ε pick a random legal action"], ["Huber loss", "Quadratic for small errors, linear for large", "δ = 1; limits large TD-error gradients"],
    ["Gradient clipping", "Cap the global L2 norm of the gradient", "Threshold 10, not a weight clamp at ±10"], ["Adam", "Moment-based updates", "β1 = 0.9, β2 = 0.999, numerical ε = 1e−8"],
    ["ReLU, He init", "Non-linearity; initial scale suited to ReLU", "max(0, x); sqrt(2 / fan_in)"]])}
<div class="row" style="gap:20px;margin-top:18px">
 <div class="eq col">Huber(δ) = 0.5 · δ²      if |δ| ≤ 1
           |δ| − 0.5    if |δ| > 1</div>
 <div class="note col">Adam's ε stabilises a division; ε-greedy is an exploration probability. A falling loss does <b>not</b> prove a good policy, so checkpoints are chosen by validation traffic metrics.</div>
</div>''', secs=0, kind="backup", notes=N("Use for optimizer questions or “why did loss fall but queueing did not?”.", ["With replacement → batch 128 from 53 samples works", "Clip the gradient norm, not weights", "Two different epsilons"]))

slide(B, "B3 · Mean per-case, pooled and bootstrap: what is the independent unit?", f'''
<div class="row" style="gap:30px">
 <div class="col"><div class="eq" style="font-size:15px"><span class="c"># negative is good</span>
regret_case    = 100 · (L − F) / F
<span class="c"># positive is good</span>
reduction_case = 100 · (F − L) / F
pooled         = 100 · (ΣF − ΣL) / ΣF</div>
  <div class="panel" style="margin-top:16px"><span class="small">Demo PM panel, seed 14: mean per-case <b>change −8.86%</b>, CI <b>[−17.51%, −1.62%]</b> over 5 demand cases for <b>one policy</b>, not a five-seed CI.</span></div></div>
 <div style="flex:1.2">{table(["Analysis", "Resampled unit", "Resamples", "What the CI covers"], [["SUMO learned vs fixed", "5 seed effects (cases pooled within seed)", "20,000", "Learning-seed variation"],
     ["PM demo panel, s14", "5 matched demand cases", "case bootstrap", "Variation across demand cases"], ["PM-only gate", "5 pooled effects, one per seed", "10,000", "Exploratory, seed level"]], cls="t tight")}
  <div class="note stop" style="margin-top:14px;font-size:15.5px">75 seed × case cells are <b>not</b> 75 independent policies. The 7,632 transitions never enter a CI. Bootstrap creates no new field data.</div></div>
</div>''', secs=0, kind="backup", notes=N("Use for statistics questions or the 8.86 vs 10.39 question.", ["Pooled weights heavy cases more", "Independent unit = learning seed", "A CI does not fix selection bias"]))

slide(B, "B4 · Vehicle parameters differ between SUMO and CityFlow", f'''
<div class="row" style="gap:30px">
 <div style="flex:1.3"><h3>SUMO <span class="sub">route XML, AM train</span></h3>{table(["", "Motorcycle", "Car", "Truck", "Bus"], [["Length / width, m", "2 / 0.8", "5 / 1.8", "8 / 2.5", "12 / 2.5"], ["Accel / decel, m/s²", "3.5 / 5", "2 / 4.5", "1.3 / 4", "1.2 / 4"],
     ["Min gap, m", "0.5", "2.5", "3", "3"], ["Max speed, m/s", "13.89 (≈50 km/h)", "11.11 (≈40)", "10", "10"], ["Sigma, tau", "0.7, 1.2 s", "0.5, —", "0.5, —", "0.5, —"]], cls="t tight", align=["", "c", "c", "c", "c"])}</div>
 <div class="col"><h3>CityFlow <span class="sub">haichau_dataset.py</span></h3>{table(["", "Motorcycle", "Car"], [["Length / width, m", "2 / 1", "5 / 2"], ["Max accel / decel", "3.5 / 5", "2 / 4.5"], ["Min gap, m", "0.5", "2.5"], ["Max speed, m/s", "13.89", "11.11"], ["Headway time, s", "0.8", "1.5"]], cls="t tight", align=["", "c", "c"])}</div>
</div>
<div class="note" style="margin-top:20px">The main launch uses the <b>lane-based model</b>. A 300 s sublane pilot was stable but the full hour produced collisions, so it was dropped. Motorcycle tau went from 1.0 to 1.2 after a collision in one held-out AM case; everything was rerun for consistency, but the test set had been used to fix the simulator. Parameters are not calibrated on field trajectories.</div>''',
      secs=0, kind="backup", notes=N("Use for questions on motorcycle modelling, sublane, tau.", ["Lane model, no sublane", "tau 1.2 is set only for motorcycles", "CityFlow headway 0.8 ≠ SUMO tau 1.2"]))

slide(B, "B5 · History of changes and lessons", table(["Stage / issue", "Change", "Allowed conclusion"], [
    ["Legacy data called “real trips”", "Relabelled synthetic", "No source for “50,500 real trips”"], ["Wide SUMO network had faults", "Isolated the data-backed junction, ≈300 m approaches", "Less spatial coverage in SUMO"],
    ["Sublane pilot", "Dropped after full-hour collisions", "Some lateral realism lost"], ["Pending on the network", "Separated due from future unreleased", "Metric now correct; old caches not reused"],
    ["Fixed-time execution", "Unified clock, mask, transitions", "Compare executed schedules"], ["V2 phase-based / V3A rehearsal", "Neighbour features, imitation / rehearsal", "Pilots rejected in the decision log"],
    ["V3B residual", "27 features, 300 s macro, ±10 s", "The family behind current residual results"], ["V3C / V3D", "Other margin and exploration settings", "Diagnostic; not merged into V3B"],
    ["PM-only gate", "Fixed normal / AM, residual PM", "Exploratory, needs a fresh test"], ["Audit of 23 Sep", "Fixed authors, locators, CI units", "Interpretation fixed; no new experiments"]], cls="t tight"),
      secs=0, kind="backup", source="docs/research/decision-log.md · docs/research/thesis-evidence-ledger.md", notes=N(
          "How to talk about failure: “This experiment failed its gate, so I changed the design or narrowed the claim and kept the evidence.” Never tell the history as a series where every version was better.",
          ["Failure → narrower claim", "V3B is the reported family", "V3C / V3D are diagnostic only"]))

slide(B, "B6 · Technology stack and code map", f'''
<div class="row" style="gap:30px">
 <div class="col">{table(["Technology", "Role"], [["Python, NumPy", "Pipeline; MLP, backprop, Adam, replay, bootstrap"], ["SUMO + TraCI", "Single-junction simulator and Python interface"], ["CityFlow (C++ + Python)", "53-junction network simulator"],
     ["OSM, osmium, netconvert", "Topology and format conversion"], ["Docker, Colima", "Packaged CityFlow runtime (NumPy 1.19.5)"], ["Git, SHA-256", "Code versions and artifact identity"], ["Matplotlib, LaTeX", "Figures and thesis PDF"], ["HTML, JS, Canvas", "Browser replay demo"]], cls="t tight")}
  <div class="xs muted" style="margin-top:6px">PyTorch and SB3 in the historical requirements are <b>not</b> used by the two main models. No GPU pipeline.</div></div>
 <div class="col">{table(["To explain", "Open (under src/traffic_rl/)"], [["SUMO observation and switching", "sim/sumo_single_junction.py"], ["Dueling, Double target, Adam", "agents/dqn.py"], ["SUMO training loop", "train/trainer.py"], ["12 phase features", "sim/phase_encoder.py"],
     ["Shared scalar MLP", "agents/phase_ddqn.py"], ["ShadowSignal, macros, anchor", "sim/schedule_residual.py"], ["Residual training", "train/schedule_residual_trainer.py"], ["Queue integral, pending", "sim/multi_agent_env.py"], ["Per-seed selector", "research/final_residual_selector.py"]], cls="t tight")}</div>
</div>''', secs=0, kind="backup", notes=N("Use for “where is the code?” — open the right file.", ["Models are written in NumPy", "Docker for CityFlow", "Know which file answers which question"]))

slide(B, "B7 · Reproducibility: what exists and what is missing", f'''
<div class="row" style="gap:30px">
 <div class="col"><h3 class="go">Available</h3><ul class="dots small"><li>Manifests, resolved configs, checkpoint contracts, selection JSON</li><li>SUMO routes, network, summary CSV and JSON</li><li>Evidence snapshot of 23 Sep and the audit script (63 / 63 source and arithmetic checks pass)</li><li>Entry points: prepare → train → evaluate → summarise; train / select residual; campaign; demo</li></ul></div>
 <div class="col"><h3 class="stop">Gaps</h3><ul class="dots stop small"><li><span class="mono">scripts/build_danang_pilot.py</span> is missing, so a fresh clone cannot rebuild the SUMO pipeline</li><li>Large raw campaigns and checkpoints live outside Git</li><li>Strict release: 14 gates open</li><li>NPZ files lack replay, Adam and RNG state, so training cannot resume exactly</li><li>OSM provenance records download date and tool versions as <span class="mono">unknown_not_recorded</span></li></ul></div>
</div>
<div class="panel dark" style="margin-top:24px">The correct statement: <b style="color:#6FD3B0">many parts support reproduction, and the remaining gaps are identified</b>. Not “anyone who clones the repo can reproduce everything”.</div>''',
      secs=0, kind="backup", source="docs/research/thesis-review-verification.md · docs/research/thesis-evidence-audit.json", notes=N("Use for reproducibility questions.", ["Audit 63 / 63 ≠ strict release", "build_danang_pilot.py missing", "Say it plainly"]))

slide(B, "B8 · SUMO demand sensitivity", f'''
<div class="row" style="gap:30px">
 <div style="width:720px;flex:none"><img class="fig" src="{img("sensitivity")}" style="width:720px;height:450px;object-fit:contain"></div>
 <div class="col"><h3>How to read it</h3><ul class="dots small"><li>120 runs at scales 0.75, 1.0, 1.25 and 1.5</li><li>The 30 runs at scale 1.0 repeat the main AM condition, so these are <b>not</b> 120 extra independent observations</li><li>The scaling is synthetic, not measured</li><li>0 collisions, 4 emergency events</li></ul></div>
</div>''', secs=0, kind="backup", source="results/danang_protocol_v1/summary/demand-sensitivity.png", notes=N("Use for robustness-to-demand questions.", ["Scale 1.0 repeats the main condition", "Synthetic scaling", "4 emergencies, 0 collisions"]))

qa = [("One model or several?", "Two families: SUMO dueling Double DQN (16 → 3 Q); CityFlow residual Double DQN (27 per macro → 1 Q), weights shared across 53 junctions."),
      ("Why not a GNN, PPO or a bigger model?", "Discrete actions and a small MLP keep the contract checkable. No comparison yet says they would be better or worse."),
      ("Is the residual reward the gain over fixed?", "No. It is −(queue + pending) over the network in the block. Gains over fixed are measured in paired evaluation."),
      ("Loss fell but queueing did not?", "Loss measures fit to TD targets on replay; it does not prove the greedy policy is good, so selection uses validation."),
      ("Is the system accident-free?", "Phase, transition and anchor rules are simulator logic; 0 collisions in the 120 main and 120 sensitivity SUMO runs (the 1,000-realization baseline batch did not record collisions). Not a field safety certificate."),
      ("Same γ, different behaviour?", "0.99 per 10 s ≠ 0.99 per 300 s. To compare in physical time, raise γ to the number of steps."),
      ("A rejected seed tests well?", "The validation decision stands; it is reported only as a post hoc diagnostic."),
      ("Is this enough for a thesis?", "Enough for system development plus simulation evaluation with failure analysis; not for a deployment claim.")]
qah = "".join(f'<div class="panel" style="padding:13px 18px"><div style="font-weight:850;color:{C["ink"]};font-size:19px;margin-bottom:3px">{q}</div><div class="small">{a}</div></div>' for q, a in qa)
slide(B, "B9 · Quick answers to common questions", f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">{qah}</div>', secs=0, kind="backup",
      source="docs/defense/thesis-understanding-guide-vi.md §22 · docs/defense/committee-questions-evidence-vi.md", notes=N(
          "The lifeline slide. Each answer: one conclusion sentence, one limit sentence, then point to the evidence.", ["Answer briefly, then stop", "Always add the limit", "Open the artifact if needed"]))


cam_rows = [["Tran Phu", "168", "3", "J1: 89% → main axis · 6% → Trung Nu Vuong"],
            ["Nguyen Van Linh (west)", "160", "126", "J1: 89% → main axis · 10% → Trung Nu Vuong"],
            ["Trung Nu Vuong", "0", "49", "exit only (OSM: one-way)"],
            ["2 Thang 9", "182", "101", "J2: 39% → bridge · 37% → Bach Dang · 20% → main axis"],
            ["Dragon Bridge", "104", "246", "J2: 62% → main axis · 18% → 2 Thang 9 · 13% → Bach Dang"],
            ["Bach Dang (north)", "3", "236", "exit only (OSM: one-way)"]]
slide(B, "B10 · Camera YOLO: car counts, checks and limits", f'''
<div class="row" style="gap:28px">
 <div style="flex:1.35">{table(["Leg (cars / 15 min)", "In", "Out", "Markov chain from this leg"], cam_rows, cls="t tight")}
  <div class="xs muted" style="margin-top:8px">Main axis between J1 and J2 (near field, most reliable): cars 323 north / 152 south; motorbikes 1,010 north / 517 south.</div></div>
 <div class="col">
  <h3>Checks</h3><ul class="dots small"><li>Car balance: J1 480 in / 501 out; J2 612 / 735</li><li>63% of entries have a completed route (689 routes)</li><li>OSM one-way streets match the counted directions</li></ul>
  <h3 class="stop" style="margin-top:14px">Limits</h3><ul class="dots stop small"><li>No hand count yet; ID accuracy not measured</li><li>Motorbikes: 174 in / 703 out → far legs (bridge) under-counted</li><li>One camera, one day, 15 min; about 95 machine-minutes per 15 video-minutes</li></ul>
 </div>
</div>''', secs=0, kind="backup", source="results/camera_counts/caurong_20260711_1716/only_car/*.csv · results/camera_counts/README.md", notes=N(
    "Backup for camera questions. Read the table by row: entry leg, cars in and out, then turning probabilities. Always state the limits: no hand count, far-field motorbikes under-counted.",
    ["Cars are trustworthy: balance 4% / 17%", "Motorbikes: main axis only", "No hand count yet"]))

# ================================================================== render
def section_secs():
    d = {s: 0 for s in SECTIONS}
    for s in S:
        if s["section"] in d:
            d[s["section"]] += s["secs"]
    return d


def ribbon(section):
    d = section_secs()
    total = sum(d.values())
    width = 1136
    gap = 7
    out, x = [], 0.0
    idx = SECTIONS.index(section)
    for i, name in enumerate(SECTIONS):
        w = (width - gap * (len(SECTIONS) - 1)) * d[name] / total
        cls = "now" if i == idx else ("past" if i < idx else "")
        out.append(f'<div class="seg {cls}" style="left:{x:.1f}px;width:{w:.1f}px"></div>')
        if i == idx:
            out.append(f'<div class="lbl" style="left:{x:.1f}px">{name}</div>')
        x += w
        if i < len(SECTIONS) - 1:
            out.append(f'<div class="amb" style="left:{x+1:.1f}px"></div>')
            x += gap
    return f'<div class="ribbon">{"".join(out)}</div>'


def roadmap_body():
    d = section_secs()
    total = sum(d.values())
    width = 1136
    x, segs = 0.0, []
    for i, name in enumerate(SECTIONS):
        w = (width - 10 * 6) * d[name] / total
        segs.append(f'<div style="position:absolute;left:{x:.1f}px;top:0;width:{w:.1f}px;height:54px;background:{C["go"]};border-radius:4px;opacity:{0.55 + 0.45 * (i % 2)}"></div>')
        segs.append(f'<div style="position:absolute;left:{x:.1f}px;top:0;width:{w:.1f}px;height:54px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:24px;font-weight:850">{i + 1}</div>')
        x += w
        if i < 6:
            segs.append(f'<div style="position:absolute;left:{x+2:.1f}px;top:0;width:6px;height:54px;background:{C["caution"]};border-radius:2px"></div>')
            x += 10
    desc = "".join(f'<div style="display:flex;gap:14px;padding:7px 0;border-bottom:1px solid {C["rule"]}"><div style="width:120px;font-weight:850;color:{C["ink"]}">{i + 1}. {n}</div><div class="small">{t}</div></div>' for i, (n, t) in enumerate(parts))
    return f'''<div style="position:relative;height:78px">{"".join(segs)}</div>
<div class="row" style="gap:40px;margin-top:6px"><div style="flex:1.4">{desc}</div>
<div class="col"><div class="panel dark" style="font-size:20px;line-height:1.42"><b style="color:#6FD3B0">One sentence to remember.</b> The benefit of RL depends on the demand regime and the baseline. This is simulation evidence, not field performance.</div>
<div style="margin-top:16px" class="small"><div><span class="lamp" style="background:{C["go"]}"></span>better, learned controller</div><div><span class="lamp" style="background:{C["caution"]}"></span>caution, exploratory, inconclusive</div><div><span class="lamp" style="background:{C["stop"]}"></span>worse, limitation</div><div><span class="lamp" style="background:{C["base"]}"></span>fixed-time baseline &nbsp; <span class="lamp" style="background:{C["pressure"]}"></span>pressure baselines</div></div></div></div>'''


def mmss(sec):
    return f"{int(sec) // 60:02d}:{int(sec) % 60:02d}"


def slide_html(n, s):
    kind = s["kind"]
    if kind in ("cover", "divider", "closing"):
        rib = ribbon(s["section"]) if kind == "divider" else ""
        return f'<section class="slide dark">{rib}{s["body"]}</section>'
    cls = "slide backup" if kind == "backup" else "slide"
    rib = ribbon(s["section"]) if s["section"] != B else f'<div class="ribbon"><div class="lbl" style="left:0;top:0;color:{C["muted"]}">Backup, for questions</div></div>'
    num = s["title"].split(" · ")[0] if s["section"] == B else str(n)
    title = s["title"].split(" · ", 1)[-1] if s["section"] == B else s["title"]
    size = 38 if len(title) <= 58 else 33 if len(title) <= 70 else 29
    return f'''<section class="{cls}">{rib}<div class="title" style="font-size:{size}px">{title}</div><div class="content">{s["body"]}</div>
<div class="footer"><div class="src">{html.escape(s["source"]) if s["source"] else AUTHOR + ", thesis defence"}</div><div class="num">{num}</div></div></section>'''


def build():
    S[ROADMAP_SLOT]["body"] = roadmap_body()
    main = [s for s in S if s["section"] != B]
    total = sum(s["secs"] for s in main)
    n = 0
    for s in S:
        if s["section"] != B:
            n += 1
        s["n"] = n
        s["html"] = slide_html(n, s)
    head = '<!doctype html><html lang="en"><head><meta charset="utf-8"><link rel="stylesheet" href="style.css">'
    (HERE / "deck.html").write_text(head + "<style>@page{size:1280px 720px;margin:0}</style></head><body>" + "".join(s["html"] for s in S) + "</body></html>", encoding="utf-8")

    def label(s):
        if s["kind"] == "cover":
            return "Cover"
        if s["kind"] == "closing":
            return "Closing and thanks"
        if s["kind"] == "divider":
            return "Section divider"
        return s["title"]

    pages, cum, rows = [], 0, []
    for s in main:
        cum += s["secs"]
        s["cum"] = cum
        rows.append(f'<tr><td class="r">{s["n"]}</td><td>{html.escape(label(s))}</td><td class="c">{mmss(s["secs"])}</td><td class="c"><b>{mmss(cum)}</b></td></tr>')
    marks = {name: max(s["cum"] for s in main if s["section"] == name) for name in SECTIONS}
    pages.append(f'''<div class="npage"><h2>Speaker script, 40-minute defence</h2>
<p style="font-size:14px;margin-bottom:8px">{len(main)} main pages, <b>{mmss(total)}</b> of speaking plus about <b>{mmss(2400 - total)}</b> of buffer. “Mark” is the time at the <b>end</b> of each page; use it while rehearsing.</p>
<table class="t timing"><tr><th class="r">#</th><th>Page</th><th class="c">Duration</th><th class="c">Mark</th></tr>{"".join(rows)}</table>
<h4>Checkpoints while speaking</h4><p style="font-size:14.5px">End of Data ≈ <b>{mmss(marks["Data"])}</b>, end of SUMO ≈ <b>{mmss(marks["SUMO"])}</b>, end of CityFlow ≈ <b>{mmss(marks["CityFlow"])}</b>, end of Results ≈ <b>{mmss(marks["Results"])}</b>. Running more than 2 minutes late: shorten the RL basics part and the “Reading the SUMO result” and secondary-metric slides.</p>
<div class="nfoot"><span>{AUTHOR}, speaker notes</span><span>Page 1</span></div></div>''')
    cheat = [("Source", "Phan, Le & Nguyen (2025), MAKE 7(3):65; cameras 1 Apr 2025; 4 movements; 48 rows / 192 values"),
             ("Published plan", "32 / 28 / 22 green + 3 × 7 yellow = 103 s"), ("SUMO demand", "normal 1,395; AM 2,330 (train); PM 2,400 veh/h over the 4 camera movements"),
             ("Network", "53 signals; 1,290 route families (644 / 323 / 323); 500 route streams per case; motorcycle 0.90"),
             ("Splits", "train 9, val 6, test 15 cases (3 regimes × 5); demand 101–105, sim 201–205"),
             ("SUMO model", "16 → 64 → 64 → V/A → 3 Q; 5,508 params; 10 s step; 7 s yellow; 20 s min green; 3-step return"),
             ("SUMO training", "30 episodes × 5 seeds (11–15); 360 decisions per episode; ε 1 → 0.05 over 5,000; validation every 5; 120 test runs"),
             ("Residual model", "27 = 12 + 12 + 3 → 64 → 64 → 1; 6,017 params; shared by 53 junctions; ±10 s; 300 s macro; MAX_MACROS 59"),
             ("Residual training", "12 episodes; 6 peak cases; 7,632 transitions; 1,152 updates; ε 0.15; target every 64; validation ep 4 / 8 / 12"),
             ("Selector", "seeds 12 (ep 8), 14 (ep 4), 15 (ep 8) selected; 13 and 16 rejected; strict release complete = false (14 gates)"),
             ("SUMO results", "normal 9.86 → 41.50 (+320.7%); AM 79.20 → 78.41 (−1.0%); PM 152.67 → 99.97 (−34.5%)"),
             ("SUMO CIs", "normal [7.60, 56.14]; AM [−9.47, 8.49]; PM [−69.55, −35.34] veh-h, over 5 seed effects"),
             ("Network results", "fixed 8,339.43; MP 6,347.00 (−23.89%); HMP 6,739.13 (−19.19%); residual 7,829.25 (−6.12%)"),
             ("Residual by regime", "normal 0%; AM 3.48%; PM 10.39% pooled (8.86% mean per case)"),
             ("Secondary", "completion +1.06 pp; insertion +0.82 pp; travel time +5.45 s; spillback +65.20 lane-s"),
             ("PM-only gate", "mean 3.48%; range 1.03–5.62%; CI [2.01, 4.95]; 15 / 25 better, 10 / 25 worse; POST HOC"),
             ("Demo", "PM demand 105 / sim 205; seed 14 ep 4; junction 420249521; 18:05 = 1,085 s; 14 vs 1 queued")]
    ch = "".join(f"<tr><td><b>{a}</b></td><td>{b}</td></tr>" for a, b in cheat)
    pages.append(f'''<div class="npage"><h2>Numbers to know by heart</h2><table class="t"><tr><th style="width:140px">Topic</th><th>Numbers</th></tr>{ch}</table>
<h4>Five sentences never to say</h4><ul style="padding-left:18px;font-size:14.5px"><li>“RL beats the fixed plan” without naming the regime and the baseline.</li><li>“The 53-junction network is every real signal in Hai Chau.”</li>
<li>“3.48% is a confirmed result” — it is post hoc.</li><li>“500 routes are 500 vehicles” or “18:05 is 6 pm”.</li><li>“The model uses a GNN or multi-agent communication.”</li></ul>
<h4>A formula for every answer</h4><p style="font-size:14.5px"><b>One conclusion</b> → <b>one limit</b> → <b>point to the evidence</b> (backup slide, file, number). If unsure: “I do not yet have an experiment that isolates that factor; the way to test it would be …”.</p>
<div class="nfoot"><span>{AUTHOR}, speaker notes</span><span>Page 2</span></div></div>''')
    p = 3
    for s in S:
        nt = s["notes"]
        if s["section"] != B:
            head_l = f'Page {s["n"]} · {html.escape(label(s))}'
            tm = f'⏱ {mmss(s["secs"])} · mark {mmss(s["cum"])}'
        else:
            head_l = html.escape(s["title"])
            tm = "Backup"
        keys = "".join(f"<div>{k}</div>" for k in nt.get("keys", []))
        avoid = "".join(f"<li>{a}</li>" for a in nt.get("avoid", []))
        qa_ = "".join(f'<div class="qa-item"><span class="q">Q: {q}</span><br>A: {a}</div>' for q, a in nt.get("qa", []))
        pages.append(f'''<div class="npage"><div class="nhead"><div class="t">{head_l}</div><div class="tm">{tm}</div></div><div class="thumb">{s["html"]}</div>
<div class="nsec"><h5>Remember</h5><div class="keys">{keys}</div></div><div class="nsec"><h5>What to say</h5><p>{nt.get("say", "")}</p></div>
{f'<div class="nsec avoid"><h5>Avoid</h5><ul>{avoid}</ul></div>' if avoid else ""}{f'<div class="nsec qa"><h5>If asked</h5>{qa_}</div>' if qa_ else ""}
<div class="nfoot"><span>{AUTHOR}, speaker notes</span><span>Page {p}</span></div></div>''')
        p += 1
    (HERE / "notes.html").write_text(head + "<style>@page{size:794px 1123px;margin:0}</style></head><body class=\"notes\">" + "".join(pages) + "</body></html>", encoding="utf-8")
    print(f"main pages: {len(main)}, backup: {len(S) - len(main)}, speaking time: {mmss(total)}")


if __name__ == "__main__":
    build()
