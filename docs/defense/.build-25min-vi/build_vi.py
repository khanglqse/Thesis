"""Build the 25-minute Vietnamese defense deck and speaker-notes handout.

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
    "cam_map": ROOT / "results/camera_counts/caurong_20260711_1716/only_car/markov_map_vi_bare.png",
}
AUTHOR = "Lương Quang Khang"
C = dict(asphalt="#16212C", ink="#13202B", body="#34434F", muted="#71808C", rule="#D2D8D5",
         go="#1C9A73", caution="#E39B0B", stop="#D8443A", base="#8B97A1", pressure="#3A74C9",
         pressure2="#8FB1E3", lane="#E9ECE6", white="#FFFFFF", phaseB="#3E6E9A")
CAMERA = [("07", 1255), ("08", 2330), ("09", 1870), ("10", 1770), ("11", 1800), ("12", 1910),
          ("13", 1395), ("14", 1505), ("15", 1400), ("16", 1755), ("17", 2400), ("18", 2490)]


def img(k):
    return IMG[k].as_uri()


def n2(x, d=2):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


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
        o.append(f'<text x="{left-8}" y="{y(v)+4:.1f}" font-size="11.5" text-anchor="end" fill="{C["muted"]}">{n2(v, 0)}</text>')
    pts = " ".join(f"{x:.1f},{y(v):.1f}" for x, (_, v) in zip(xs, CAMERA))
    area = f"{xs[0]:.1f},{top+ph} " + pts + f" {xs[-1]:.1f},{top+ph}"
    o.append(f'<polygon points="{area}" fill="{C["caution"]}" opacity=".12"/>')
    o.append(f'<polyline points="{pts}" fill="none" stroke="{C["ink"]}" stroke-width="3" stroke-linejoin="round"/>')
    for x, (hr, v) in zip(xs, CAMERA):
        col = {"08": C["stop"], "13": C["go"], "17": C["caution"]}.get(hr, C["ink"])
        r = 7 if col != C["ink"] else 4
        o.append(f'<circle cx="{x:.1f}" cy="{y(v):.1f}" r="{r}" fill="{col}" stroke="#fff" stroke-width="2"/>')
        o.append(f'<text x="{x:.1f}" y="{top+ph+18}" font-size="12" text-anchor="middle" fill="{C["muted"]}">{hr}:00</text>')
    for hr, lab, dy in (("08", "AM 2.330", -14), ("13", "normal 1.395", 22), ("17", "PM 2.400", -14)):
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
    o.append(f'<text x="{left}" y="{ty+42}" font-size="13" font-weight="700" fill="{C["ink"]}">Cùng một lịch 103 giây lặp lại cả ngày</text>')
    o.append(f'<text x="{w-right}" y="{ty+42}" font-size="13" text-anchor="end" fill="{C["muted"]}">xe/giờ trên bốn đường đo, 1/4/2025</text>')
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
            o.append(f'<text x="{x+(bw-5)/2:.1f}" y="{top+ph-bh-6:.1f}" font-size="12" font-weight="800" text-anchor="middle" fill="{C["ink"]}">{n2(v, 1)}</text>')
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
    seeds = [("12", 2.36, "chọn, ep 8", True), ("13", 5.62, "tham khảo, ep 12", False),
             ("14", 5.11, "chọn, ep 4", True), ("15", 1.03, "chọn, ep 8", True), ("16", 3.27, "tham khảo, ep 4", False)]
    left, top, bottom, right = 44, 26, 56, 10
    pw, ph = w - left - right, h - top - bottom
    y = lambda v: top + ph - ph * v / 6.5
    o = [svg_open(w, h)]
    for t in range(7):
        o.append(f'<line x1="{left}" x2="{w-right}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#E3E7E4"/>')
        o.append(f'<text x="{left-8}" y="{y(t)+4:.1f}" font-size="12" text-anchor="end" fill="{C["muted"]}">{t}%</text>')
    o.append(f'<line x1="{left}" x2="{w-right}" y1="{y(3.48):.1f}" y2="{y(3.48):.1f}" stroke="{C["caution"]}" stroke-width="2.5" stroke-dasharray="8 5"/>')
    bw = pw / 5
    for i, (s, v, lab, sel) in enumerate(seeds):
        x = left + i * bw + bw * .2
        fill = C["go"] if sel else "#fff"
        dash = "" if sel else ' stroke-dasharray="5 3"'
        o.append(f'<rect x="{x:.1f}" y="{y(v):.1f}" width="{bw*.6:.1f}" height="{y(0)-y(v):.1f}" rx="4" fill="{fill}" stroke="{C["go"] if sel else C["muted"]}" stroke-width="2"{dash}/>')
        o.append(f'<text x="{x+bw*.3:.1f}" y="{y(v)-8:.1f}" font-size="14" font-weight="850" text-anchor="middle" fill="{C["ink"]}">{n2(v, 2)}%</text>')
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
    o.append(f'<text x="{left}" y="18" font-size="14" font-weight="800" fill="{C["ink"]}">Một block 300 giây của lịch gốc (minh họa)</text>')
    for a, b, lab, col in ((0, 100, "Pha A", C["go"]), (100, 110, "", C["caution"]), (110, 210, "Pha B", C["phaseB"]),
                           (210, 220, "", C["caution"]), (220, 300, "Pha A", C["go"])):
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
    o.append(f'<text x="{x(90)-8:.1f}" y="{by-14}" font-size="13" font-weight="800" text-anchor="end" fill="{C["stop"]}">đổi sớm ở giây 90</text>')
    o.append(f'<text x="{x(110)+8:.1f}" y="{by-14}" font-size="13" font-weight="800" fill="#B97A00">đổi muộn ở giây 110</text>')
    o.append(f'<text x="{x(100):.1f}" y="{by+90}" font-size="13" font-weight="800" text-anchor="middle" fill="{C["ink"]}">lịch gốc đổi pha ở giây 100</text>')
    o.append(f'<rect x="{x(300)-5:.1f}" y="{by-12}" width="10" height="58" rx="2" fill="{C["stop"]}"/>')
    o.append(f'<text x="{x(300)-12:.1f}" y="{by+124}" font-size="13.5" font-weight="850" text-anchor="end" fill="{C["stop"]}">Ở giây 300, đèn phải khớp anchor</text>')
    o.append(f'<text x="{left}" y="{by+124}" font-size="13.5" fill="{C["muted"]}">30 step 10 giây. Mỗi nút chọn một macro mỗi block.</text>')
    o.append("</svg>")
    return "".join(o)


def rl_loop():
    return f'''{svg_open(500, 300)}
<defs><marker id="ah" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{C['go']}"/></marker></defs>
<rect x="160" y="10" width="180" height="62" rx="12" fill="{C['asphalt']}"/>
<text x="250" y="37" font-size="17" font-weight="850" fill="#fff" text-anchor="middle">Agent</text>
<text x="250" y="58" font-size="13" fill="#A8B8C4" text-anchor="middle">Q(o, a) rồi lấy argmax</text>
<rect x="160" y="228" width="180" height="62" rx="12" fill="#fff"/>
<text x="250" y="255" font-size="17" font-weight="850" fill="{C['ink']}" text-anchor="middle">Mô phỏng</text>
<text x="250" y="276" font-size="13" fill="{C['muted']}" text-anchor="middle">SUMO hoặc CityFlow</text>
<path d="M340,41 C455,41 455,259 345,259" fill="none" stroke="{C['go']}" stroke-width="3.5" marker-end="url(#ah)"/>
<text x="378" y="155" font-size="15" font-weight="850" fill="{C['go']}" text-anchor="middle">action</text>
<path d="M160,259 C45,259 45,41 155,41" fill="none" stroke="{C['go']}" stroke-width="3.5" marker-end="url(#ah)"/>
<text x="122" y="125" font-size="15" font-weight="850" fill="{C['go']}" text-anchor="middle">observation mới</text>
<text x="122" y="188" font-size="15" font-weight="850" fill="{C['stop']}" text-anchor="middle">reward</text>
<rect x="185" y="124" width="130" height="52" rx="10" fill="#FBEFD3"/>
<text x="250" y="147" font-size="14" font-weight="800" fill="{C['ink']}" text-anchor="middle">Replay buffer</text>
<text x="250" y="165" font-size="12" fill="{C['muted']}" text-anchor="middle">dùng khi train</text>
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
        o.append(f'<text x="464" y="226" font-size="13.5" font-weight="850" fill="{C["go"]}" text-anchor="middle">3 Q-value</text>')
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
SECTIONS = ["Bài toán", "Dữ liệu", "SUMO", "CityFlow", "Kết quả", "Kết luận"]
S: list[dict] = []
B = "Phụ lục"


def slide(section, title, body, *, secs, source="", kind="", notes=None):
    S.append(dict(section=section, title=title, body=body, secs=secs, source=source, kind=kind, notes=notes or {}))


def N(say, keys, avoid=None, qa=None):
    return dict(say=say, keys=keys, avoid=avoid or [], qa=qa or [])


def divider(section, part, title, question, minutes, lit="go"):
    body = f'''
<div style="position:absolute;left:72px;top:150px;font-size:210px;font-weight:900;line-height:.8;color:transparent;-webkit-text-stroke:2px #3C5061;letter-spacing:-.04em">{part:02d}</div>
<div style="position:absolute;left:72px;top:360px;width:860px;font-size:64px;font-weight:850;line-height:1.02;color:#fff;letter-spacing:-.03em">{title}</div>
<div style="position:absolute;left:72px;top:520px;width:820px;font-size:24px;line-height:1.35;color:#AFC0CC">{question}</div>
<div style="position:absolute;left:72px;top:620px;font-size:16px;font-weight:700;color:#6FD3B0">Khoảng {minutes} phút</div>
<div style="position:absolute;right:110px;top:120px">{signal_head(lit, 150, 460)}</div>'''
    slide(section, "", body, secs=10, kind="divider", notes=N(
        f"Câu chuyển: “{question}” Dừng một nhịp, nhìn Hội đồng, rồi nói tiếp.", [f"Phần {part}: {title}", f"≈ {minutes} phút", "Hít một hơi, ngẩng lên"]))


# ================================================================== 01 cover
# ================================================================== 01 cover
slide("Bài toán", "", f'''
<div style="position:absolute;right:0;top:0">{cover_art()}</div>
<div style="position:absolute;left:72px;top:74px;font-size:17px;font-weight:700;color:#6FD3B0">Bảo vệ luận văn thạc sĩ kỹ thuật phần mềm</div>
<div style="position:absolute;left:72px;top:118px;width:660px;font-size:46px;line-height:1.08;font-weight:850;color:#fff;letter-spacing:-.02em">Học tăng cường cho điều khiển đèn giao thông Đà Nẵng, có kiểm soát bằng chứng</div>
<div style="position:absolute;left:72px;top:340px;width:620px;font-size:22px;line-height:1.4;color:#B8C7D2">Từ một nút giao có dữ liệu công bố trong SUMO đến 53 nút có đèn ở Hải Châu trong CityFlow</div>
<div style="position:absolute;left:72px;top:470px;font-size:14px;color:#7E93A3">Học viên</div>
<div style="position:absolute;left:72px;top:492px;font-size:27px;font-weight:850;color:#fff">{AUTHOR}</div>
<div style="position:absolute;left:380px;top:470px;font-size:14px;color:#7E93A3">Giảng viên hướng dẫn</div>
<div style="position:absolute;left:380px;top:492px;font-size:19px;font-weight:650;color:#fff;line-height:1.45">Dr. Le Van Minh</div>
<div style="position:absolute;left:72px;top:640px;font-size:15px;color:#7E93A3">FPT University, Đà Nẵng, 2026</div>
''', secs=20, kind="cover", notes=N(
    "Kính thưa Hội đồng, em là Lương Quang Khang. Em trình bày luận văn về reinforcement learning, gọi tắt là RL, cho điều khiển đèn giao thông ở Đà Nẵng. "
    "Luận văn có hai tầng: một nút giao trong SUMO và mạng 53 nút có đèn ở Hải Châu trong CityFlow. Mỗi con số em đưa ra đều đi kèm nguồn và phạm vi được phép kết luận.",
    ["Hai tầng: 1 nút SUMO, 53 nút CityFlow", "Số nào cũng có nguồn", "Nói chậm, nhìn Hội đồng"],
    ["Không mở đầu bằng lời hứa RL luôn thắng."]))

# ================================================================== 02 roadmap
parts = [("Bài toán", "Vì sao cần adaptive control, ba câu hỏi nghiên cứu, thiết kế hai tầng"),
         ("Dữ liệu", "Paper Đà Nẵng 2025, demand cho hai mô phỏng, thử camera công khai"),
         ("SUMO", "Double DQN + dueling, state 16 số, metric và baseline"),
         ("CityFlow", "Residual theo lịch, một macro, training và checkpoint"),
         ("Kết quả", "Theo regime, so với baseline mạnh, multi-seed"),
         ("Kết luận", "Demo, được nói gì, đóng góp và bước tiếp")]
ROADMAP_SLOT = len(S)
slide("Bài toán", "Nội dung trình bày", "__ROADMAP__", secs=25, notes=N(
    "Bài trình bày có sáu phần: bài toán, dữ liệu, hai mô hình trong SUMO và CityFlow, kết quả, rồi demo và kết luận. "
    "Nếu chỉ nhớ một câu thì đó là: lợi ích của RL phụ thuộc vào regime demand và baseline, và đây là bằng chứng mô phỏng.",
    ["Sáu phần, đi nhanh", "Một câu: phụ thuộc regime và baseline"],
    ["Không đọc thời lượng từng phần."]))

# ================================================================== 03 problem
slide("Bài toán", "Lịch fixed-time lặp cả ngày, demand thì không", f'''
<div class="row" style="gap:34px">
 <div style="width:680px;flex:none">{cycle_vs_demand()}
  <div class="row" style="gap:10px;margin-top:4px">
   <span class="tag go">Xanh 1 · 32 giây</span><span class="tag" style="background:#DCE6F0;color:#2F557A">Xanh 2 · 28 giây</span><span class="tag stop">Xanh 3 · 22 giây</span><span class="tag caution">3 lần vàng 7 giây</span><span class="tag dark">cycle 103 giây</span></div>
 </div>
 <div class="col">
  <p class="lead" style="margin-bottom:18px">Adaptive controller nhìn tình hình giao thông rồi quyết định đèn, để giảm hàng chờ. RL tự học cách quyết định bằng cách <b>thử action trong mô phỏng và xem kết quả</b>.</p>
  <h3>Vì sao khó</h3>
  <div class="rule-l stop" style="margin-bottom:10px"><b class="stop">Kết quả đến chậm.</b> Đổi đèn bây giờ, vài chục giây sau hàng chờ mới thay đổi, rồi ảnh hưởng sang nút bên cạnh.</div>
  <div class="rule-l stop" style="margin-bottom:10px"><b class="stop">Nút này lợi, nút kia thiệt.</b> Cho xe đi nhanh ở một nút có thể đẩy xe vào đoạn đường sau đang kẹt.</div>
  <div class="rule-l stop"><b class="stop">Ít dữ liệu.</b> Số liệu camera công bố chỉ có bốn luồng, tại một nút, trong một ngày.</div>
 </div>
</div>''', secs=70, source="Lịch đèn: Phan, Le và Nguyen (2025), tr. 7 và Hình 4 tr. 8 · tổng camera: datasets/danang_published/phan2025_camera_hourly_digitized.csv", notes=N(
    "Đèn fixed-time chia thời gian xanh theo một cycle lặp lại. Ở nút nghiên cứu, lịch công bố là 32, 28 và 22 giây xanh, cộng ba lần vàng 7 giây, tổng 103 giây. "
    "Biểu đồ cho thấy vấn đề: lưu lượng camera dao động từ khoảng 1.250 đến 2.500 xe mỗi giờ, nhưng cùng một lịch 103 giây cứ lặp lại cả ngày. "
    "Adaptive control thì quyết định đèn theo tình hình giao thông. Bài toán khó vì ba lý do: kết quả của một action đến chậm, nút này lợi có thể làm nút kia thiệt, và có rất ít dữ liệu thật. "
    "Vì vậy câu hỏi đúng không phải “RL có tốt không”, mà là RL có ích lúc nào, so với baseline nào, và bằng chứng mạnh đến đâu.",
    ["103 giây = 32 + 28 + 22 + 3 × 7", "Kết quả chậm · nút này lợi nút kia thiệt · ít dữ liệu", "Khi nào / so với gì / chắc đến đâu"]))

# ================================================================== 04 RQs
rq = [("RQ1", "RL có giảm hàng chờ tại nút giao có dữ liệu công bố không?", "SUMO, ba regime, năm training seed", "Một nút mô phỏng với hình học, demand và giả định đã nêu", C["go"]),
      ("RQ2", "Một policy dùng chung có học được cách chỉnh lịch có ích cho 53 nút không?", "CityFlow, Double DQN residual theo lịch", "Một mạng mô phỏng với demand tổng hợp", C["pressure"]),
      ("RQ3", "Kết quả có còn đúng khi so với baseline mạnh, chạy nhiều seed, tính cả xe pending và kiểm tra lại nguồn không?", "Baseline, nhiều seed, selector, kiểm tra nguồn", "Những gì đã có và những gì còn thiếu", C["stop"])]
rqh = "".join(f'''<div class="col" style="border-top:6px solid {c};padding-top:16px">
 <div class="hero" style="font-size:54px;color:{c}">{k}</div>
 <div style="font-size:21px;font-weight:800;color:{C["ink"]};line-height:1.25;margin:12px 0 18px;min-height:130px">{q}</div>
 <div class="xs muted" style="font-weight:800">Trả lời bằng</div><div class="small" style="margin-bottom:12px">{e}</div>
 <div class="xs muted" style="font-weight:800">Kết luận chỉ đúng cho</div><div class="small">{s}</div></div>''' for k, q, e, s, c in rq)
slide("Bài toán", "Ba câu hỏi nghiên cứu", f'''<div class="row" style="gap:36px">{rqh}</div>
<div class="panel dark" style="margin-top:30px;font-size:19px;line-height:1.45"><b style="color:#6FD3B0">Ý chính.</b> Lợi ích của RL phụ thuộc vào regime demand và baseline. Đây là bằng chứng mô phỏng, chưa phải hiệu quả ngoài đường.</div>''',
      secs=45, notes=N(
    "Luận văn trả lời ba câu. RQ1: tại nút có dữ liệu công bố, RL có giảm hàng chờ không? Em trả lời trong SUMO với ba regime và năm training seed. "
    "RQ2: một policy dùng chung cho 53 nút có học được những chỉnh sửa nhỏ trên lịch đèn không? Em trả lời trong CityFlow. "
    "RQ3 hỏi kết quả chắc đến đâu: sau khi so với baseline mạnh, chạy nhiều seed và kiểm tra lại nguồn dữ liệu, kết quả còn đúng bao nhiêu.",
    ["RQ1 = SUMO, một nút", "RQ2 = CityFlow, 53 nút, policy dùng chung", "RQ3 = kết quả chắc đến đâu"],
    ["Nói “kiểm tra khi nào RL có ích”, không nói “chứng minh RL tốt hơn”."]))

# ================================================================== 05 two tiers
two = table(["", "SUMO: một nút", "CityFlow: mạng Hải Châu"], [
    ["Vai trò", "Nút có nguồn công bố", "Quy mô và tương tác giữa các nút"],
    ["Quy mô", "1 nút, 4 hướng, 3 pha xanh", "<b>53</b> nút có đèn, dựng từ OSM"],
    ["Model", "Dueling <b>Double</b> DQN, 3-step return", "<b>Double</b> DQN residual theo lịch"],
    ["Input → output", "16 số → 3 Q-value", "27 feature mỗi macro → 1 Q-value"],
    ["Decision step", "10 giây", "macro 300 giây"],
    ["Fixed-time baseline", "Lịch công bố 103 giây", "Xanh 25 giây, tune trên validation"],
    ["Test", "15 scenario (3 regime × 5)", "15 scenario (3 regime × 5)"],
], cls="t tight")
slide("Bài toán", "Hai tầng: hai mô phỏng, hai model, hai câu hỏi", f'''
<div class="row" style="gap:30px">
 <div style="flex:1.75">{two}</div>
 <div class="col">
  {vchain(["<b>Paper Đà Nẵng 2025</b><br><span class='xs muted'>lịch đèn, bảng rẽ, biểu đồ camera</span>", "<b>CSV + giả định đã ghi lại</b>",
           "<div style='display:flex;gap:8px'><div style='flex:1;background:#DDF1E9;border-radius:8px;padding:4px'><b>SUMO</b><br><span class='xs'>1 nút</span></div><div style='flex:1;background:#E1EAF7;border-radius:8px;padding:4px'><b>CityFlow</b><br><span class='xs'>53 nút + OSM</span></div></div>",
           "<b>Paired evaluation</b><br><span class='xs muted'>cùng demand, nhiều baseline, nhiều seed</span>", "<b>Kết quả, giới hạn, demo</b>"])}
  <div class="note stop" style="margin-top:14px"><b>Không transfer weight</b> từ SUMO sang CityFlow. Hai tầng chỉ chung câu hỏi nghiên cứu và hình dạng demand.</div>
 </div>
</div>''', secs=50, source="docs/defense/thesis-understanding-guide-vi.md, mục 2", notes=N(
    "Thiết kế có hai tầng. Tầng SUMO là một nút có nguồn công bố; model là dueling Double DQN, đọc 16 số, ra ba Q-value cho ba pha xanh, quyết định mỗi 10 giây. "
    "Tầng CityFlow là mạng 53 nút dựng từ OpenStreetMap với demand tổng hợp; model là Double DQN residual, mỗi 300 giây chọn một chỉnh sửa nhỏ trên lịch. "
    "Lưu ý: không có weight nào được transfer từ SUMO sang CityFlow. Hai tầng chỉ chung câu hỏi nghiên cứu và hình dạng demand.",
    ["SUMO: 16 → 3 Q, mỗi 10 giây", "CityFlow: 27 feature → 1 Q, mỗi 300 giây", "Không transfer weight"],
    ["Không gộp hai model thành một cột “RL”."],
    [("Hai tầng liên hệ thế nào?", "Cùng câu hỏi nghiên cứu và cùng hình dạng demand từ camera; không dùng chung weight.")]))

# ================================================================== DATA
src_rows = [["Hình học, làn 2/2/3/3", "tr. 7", "Dựng nút SUMO"],
            ["Xanh 32/28/22 giây, cycle 103 giây", "tr. 7, Hình 4 tr. 8", "Fixed-time baseline"],
            ["Camera 1/4/2025, 06:00–18:00", "tr. 16", "Ngày quan sát"],
            ["2 camera, 4 đường đo", "Hình 12 tr. 17", "Phần thực sự được quan sát"],
            ["Đếm theo giờ và loại xe", "Hình 17–18 tr. 20", "Digitize thành CSV: 48 dòng, 192 giá trị"],
            ["Dữ liệu gốc không công khai", "tr. 23", "Không có video gốc"]]
slide("Dữ liệu", "Nguồn chính: một paper, một nút giao ở Đà Nẵng", f'''
<div class="row" style="gap:30px">
 <div style="width:380px;flex:none"><img class="fig" src="{img("junction")}" style="width:380px;height:380px;object-fit:contain">
  <div class="cap">Nút Lê Thanh Nghị – Cách Mạng Tháng 8 – 2/9, phía cầu Hòa Xuân. Hai camera đo bốn luồng; mỗi đường vào dài khoảng 300 m trong mô phỏng.</div></div>
 <div class="col">
  <div class="rule-l ink" style="margin-bottom:14px"><div class="small"><b>Phan, Le và Nguyen (2025).</b> <i>Application of Dueling Double Deep Q-Network for Dynamic Traffic Signal Optimization: A Case Study in Danang City, Vietnam.</i> MAKE 7(3):65. doi:10.3390/make7030065</div></div>
  {table(["Nội dung", "Trong PDF", "Dùng để"], src_rows, cls="t tight")}
  <div class="note stop" style="margin-top:12px;font-size:15px">Số camera là <b>đọc xấp xỉ từ biểu đồ</b>, một ngày, bốn luồng. Dung sai ±15 / ±30 xe/giờ là sai số đọc.</div>
 </div>
</div>''', secs=50, source="datasets/danang_published/sources/phan2025_make7030065.pdf (trang PDF 1–24)", notes=N(
    "Nguồn chính là paper của Phan, Le và Nguyen năm 2025 trên tạp chí MAKE. Em chọn paper này vì nó công bố hình học, lịch đèn và số đếm camera của một nút cụ thể ở Đà Nẵng. "
    "Mỗi thông số em dùng đều có trang hoặc hình tương ứng, như trong bảng. Từ Hình 17 và 18, em digitize thành CSV: 48 dòng, 192 giá trị, tất cả trong một ngày. "
    "Giới hạn cần nói ngay: số liệu là đọc xấp xỉ từ biểu đồ, và video gốc không công khai.",
    ["Phan, Le và Nguyen 2025, MAKE", "48 dòng · 192 giá trị · 1 ngày", "Đọc xấp xỉ; không có video gốc"],
    ["Không gọi đây là dữ liệu thực tế đầy đủ."],
    [("Đây có phải dữ liệu thực tế không?", "Phần camera là số đếm đã công bố, đọc xấp xỉ từ biểu đồ: một ngày, bốn luồng. Phần còn lại là giả định mô phỏng đã ghi lại."),
     ("Có tham khảo nghiên cứu địa phương trước đó không?", "Có: Trần Trung Việt và Phan Cao Thọ (2007) về làn sóng xanh trên trục chính Đà Nẵng. Em chỉ kế thừa ý tưởng, không dùng số liệu (slide phụ lục B11).")]))

slide("Dữ liệu", "Từ số liệu nguồn đến demand mô phỏng", f'''
<div class="row" style="gap:30px">
 <div style="width:450px;flex:none">
  <h3>SUMO <span class="sub">một nút</span></h3>
  {vchain(["Lịch và hình học công bố → <b>nút và signal program</b>", "CSV camera, 4 luồng → <b>demand</b>", "Demand seed → route và thời điểm xuất phát", "Simulation seed → ngẫu nhiên bên trong SUMO"])}
  <div class="row" style="gap:10px;margin-top:14px">
   <div class="col">{stat("1.395", "xe/giờ, normal (13:00)", "go", 30)}</div><div class="col">{stat("2.330", "xe/giờ, AM (08:00), dùng để train", "stop", 30)}</div><div class="col">{stat("2.400", "xe/giờ, PM (17:00)", "caution", 30)}</div></div>
  <div class="xs muted" style="margin-top:10px">Tổng trên bốn đường đo, không phải lưu lượng cả nút.</div>
 </div>
 <div class="col">
  <h3>CityFlow <span class="sub">53 nút ở Hải Châu</span></h3>
  {chain([("OSM PBF", "Geofabrik, ODbL"), ("osmium", "cắt khung"), ("netconvert", "mạng SUMO"), ("converter", "roadnet CityFlow"), ("53 đèn", "phase contract")])}
  <div class="xs muted" style="margin:6px 0 10px">Mạng <b>lấy từ OSM</b>, chỉ giữ đường chính; không phải mọi đèn ngoài đường.</div>
  {table(["Thuộc tính", "Giá trị"], [["Route family", "1.290 → train / validation / test = 644 / 323 / 323"], ["Route mỗi scenario", "500, mỗi route phát nhiều xe"],
       ["Cơ cấu xe", "xe máy 0,90, còn lại ô tô (giả định)"], ["Test", "15 scenario = 3 regime × 5 demand seed"]], cls="t tight")}
 </div>
</div>
<div class="note stop" style="margin-top:14px"><b>500 route không phải 500 xe.</b> Demand của mạng chỉ lấy <b>dáng tăng / giảm theo giờ</b> từ camera. Mọi controller chạy trên cùng cặp seed → so sánh <b>paired</b>.</div>''',
      secs=60, source="configs/haichau_network_v2.yaml · src/traffic_rl/network/haichau_dataset.py · datasets/haichau_network_v2/provenance.json", notes=N(
    "Trong SUMO, lịch và hình học công bố dựng nên nút và signal program; CSV camera dựng demand: 1.395 xe mỗi giờ ở normal, 2.330 ở AM, và 2.400 ở PM. Model chỉ được train trên AM. "
    "Trong CityFlow, topology lấy từ OpenStreetMap, qua osmium và netconvert, rồi chuyển sang roadnet của CityFlow, ra 53 nút có đèn. "
    "Demand mạng là tổng hợp: 1.290 route family chia thành train, validation và test; 90 phần trăm xe máy là giả định. "
    "Mọi controller chạy trên cùng demand seed và simulation seed, nên so sánh là paired. Và 500 route không có nghĩa là 500 xe.",
    ["SUMO: 1.395 / 2.330 / 2.400, train chỉ AM", "CityFlow: OSM → 53 đèn, 1.290 route family", "Paired: cùng seed cho mọi controller"],
    ["Không gọi mạng 53 nút là mọi đèn thật của Hải Châu."],
    [("Vì sao 53 nút?", "Đó là số đèn được điều khiển sau pipeline OSM → netconvert → CityFlow, với các bước gộp và lọc ghi trong provenance."),
     ("Có mấy loại seed?", "Ba loại: demand seed, simulation seed và training seed (slide phụ lục B13).")]))

slide("Dữ liệu", "Mở rộng: tự đếm xe từ camera công khai", f'''
<div class="small" style="margin-bottom:8px"><b>Video YouTube công khai</b> → <b>YOLOv8-VisDrone</b> detect từng xe → <b>ByteTrack</b> giữ ID → <b>7 vạch đếm</b> vào / ra theo loại xe → <b>Markov chain</b> P(lối ra | lối vào)</div>
<div class="row" style="gap:20px">
 <div style="width:490px;flex:none"><img class="fig" src="{img("cam_frame")}" style="width:490px;height:262px;object-fit:cover">
  <div class="cap">0511.vn, nút Tây Cầu Rồng, 11/7/2026 17:16–17:31. Khung = xe, số = ID, vệt = đường đi, vạch trắng = vạch đếm.</div></div>
 <div class="col"><img class="fig" src="{img("cam_map")}" style="width:100%;height:262px;object-fit:contain">
  <div class="cap">Ô tô trên nền OpenStreetMap: xác suất rẽ ở J1 (xanh), J2 (cam); đường một chiều trên OSM khớp với số đếm.</div></div>
</div>
<div class="row" style="gap:18px;margin-top:10px;align-items:stretch">
 <div style="width:250px;flex:none">{stat("4.323", "lượt qua vạch / 15 phút", "ink", 28)}<div style="height:6px"></div>{stat("75%", "ô tô trục chính lên Cầu Rồng; lệch vào–ra 4% / 17%", "go", 28)}</div>
 <div class="panel go col" style="padding:10px 14px;font-size:13.5px;line-height:1.38"><b>Realtime, đã đo cho một nút.</b> YOLOv8m (ảnh 1280) + tracking + đếm vạch xử lý <b>180 giây video trong 169 giây</b> trên laptop Apple M4 Pro. Latency khoảng 0,13 giây, rất nhỏ so với decision step 10 giây. <b>Mạng 53 nút:</b> mỗi nút một edge device, chỉ gửi số đếm (<i>chưa thử</i>).</div>
 <div class="note stop" style="width:250px;flex:none;font-size:13.5px;line-height:1.38"><b>Chỉ là feasibility demo:</b> một camera, 15 phút, chưa đếm tay đối chiếu; xe máy ở xa bị đếm thiếu. Không dùng làm demand mô phỏng.</div>
</div>''', secs=50, source="scripts/count_camera_vehicles.py · scripts/analyze_camera_routes.py · results/camera_counts/README.md", notes=N(
    "Vì video gốc của paper không công khai, em thử tự lấy số liệu từ camera công khai ở nút Tây Cầu Rồng. YOLO detect từng xe, ByteTrack giữ ID qua các frame, và bảy vạch đếm ghi xe vào, ra theo loại xe. Từ đó em có Markov chain về hướng rẽ, ví dụ 75 phần trăm ô tô trên trục chính rẽ lên Cầu Rồng. "
    "Một nút chạy được realtime trên laptop. Nhưng đây chỉ là feasibility demo: chưa đếm tay đối chiếu, nên em không dùng nó làm demand mô phỏng.",
    ["YOLO → ByteTrack → vạch đếm → Markov", "Realtime 1 nút: 180 giây video trong 169 giây", "Feasibility demo, không làm input mô phỏng"],
    ["Không nói đây là dữ liệu đã dùng trong SUMO hay CityFlow.", "Không nói “chính xác 95%”: chưa có đếm tay.", "Không nói đã chạy realtime cho cả mạng."],
    [("Độ chính xác của YOLO là bao nhiêu?", "Chưa đo bằng đếm tay. Bằng chứng hiện có là cân bằng vào–ra của ô tô (lệch 4% và 17%) và chiều một chiều khớp OSM. Xe máy ở xa bị đếm thiếu nên em không báo tổng xe máy (B10)."),
     ("Sao không dùng cho mô phỏng?", "Chỉ có 15 phút ở một nút khác nút trong paper và chưa kiểm chứng. Bước tiếp là đếm tay một đoạn, chạy nhiều ngày, rồi mới calibrate demand."),
     ("Vì sao dùng model VisDrone?", "YOLO train trên COCO gần như không thấy xe máy từ góc cao này; VisDrone là ảnh nhìn từ trên xuống nên bắt được xe máy chỉ khoảng 10 pixel.")]))

# ================================================================== SUMO
slide("SUMO", "Nền tảng: DQN, Double DQN và dueling", f'''
<div class="row" style="gap:40px">
 <div class="col">
  <h3>Q-value</h3>
  <div class="eq">return = r<sub>t</sub> + γ r<sub>t+1</sub> + γ² r<sub>t+2</sub> + …
<span class="k">greedy action</span> = argmax<sub>a</sub> Q(s, a)</div>
  <p class="small" style="margin:10px 0 18px">Reward = <b>chi phí âm</b> (hàng chờ), nên ít âm hơn là tốt hơn. Training dùng replay buffer và ε-greedy.</p>
  <h3>Double DQN đổi <span class="go">target</span></h3>
  <div class="eq" style="margin:8px 0"><span class="c"># online network chọn action</span>
a* = argmax<sub>a</sub> Q<sub>online</sub>(s′, a)
<span class="c"># target network chấm điểm</span>
y  = r + (1 − done) · γ · Q<sub>target</sub>(s′, a*)</div>
  <div class="xs muted">Giảm overestimation. van Hasselt, Guez và Silver (2016).</div>
 </div>
 <div class="col">
  <h3>Dueling đổi <span class="pressure">output layer</span></h3>
  <div class="eq" style="margin:4px 0 12px">Q(s, a) = V(s) + A(s, a) − mean<sub>b</sub> A(s, b)</div>
  <ul class="dots pressure small"><li><b>V(s)</b>: state này tốt đến đâu</li><li><b>A(s, a)</b>: mỗi action hơn kém bao nhiêu</li><li>Có ích khi nhiều action có giá trị gần nhau</li></ul>
  <div class="xs muted" style="margin-top:6px">Wang và cộng sự, ICML 2016.</div>
  <div class="panel go" style="margin-top:22px"><b>SUMO</b> dùng <b>cả hai</b>: Double target, dueling head, 3-step return.</div>
  <div class="panel pressure" style="margin-top:12px"><b>CityFlow residual</b> chỉ dùng <b>Double</b>, output một số.</div>
 </div>
</div>''', secs=45, notes=N(
    "Hai model đều dựa trên DQN: Q-value ước lượng tổng reward tương lai của một action, và policy greedy chọn action có Q lớn nhất. Reward ở đây là chi phí âm, nên ít âm hơn là tốt hơn. "
    "Double DQN sửa target: online network chọn action, target network chấm điểm, để giảm overestimation. Dueling sửa output layer: tách V của state khỏi A của từng action. "
    "SUMO dùng cả hai; CityFlow chỉ dùng Double.",
    ["Double = online chọn, target chấm", "Dueling = V + A − mean A", "SUMO cả hai · CityFlow chỉ Double"],
    ["Không nói dueling làm giảm overestimation; đó là việc của Double."],
    [("Dueling có giảm overestimation không?", "Không trực tiếp. Double tách việc chọn và chấm trong target; dueling tách V và A trong kiến trúc (B15).")]))

vec16 = '<div style="display:flex;gap:4px">' + "".join(f'<div style="flex:1;height:40px;border-radius:5px;background:{c};color:#fff;font-weight:850;font-size:14px;display:flex;align-items:center;justify-content:center">{l}</div>'
                                                      for l, c in [("Q", C["go"])] * 4 + [("N", C["phaseB"])] * 4 + [("P", C["stop"])] * 4 + [("φ", C["caution"])] * 3 + [("t", C["base"])]) + "</div>"
slide("SUMO", "Model SUMO: state 16 số, 3 Q-value, mỗi 10 giây", f'''
<div class="row" style="gap:36px">
 <div class="col">
  <h3>State <span class="sub">thứ tự hướng TB, ĐN, ĐB, TN</span></h3>{vec16}
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px 16px;margin-top:10px" class="xs">
   <div><b class="go">1–4</b> hàng chờ / 20</div><div><b style="color:{C["phaseB"]}">5–8</b> số xe / 20</div><div><b class="stop">9–12</b> xe pending / 20</div>
   <div><b class="caution">13–15</b> one-hot pha xanh hiện tại</div><div style="grid-column:span 2"><b class="muted">16</b> thời gian từ lần đổi pha = min(t, 60) / 60</div></div>
  <div class="xs muted" style="margin:6px 0 22px">Pending = xe đã đến giờ xuất phát nhưng chưa vào được mạng.</div>
  <h3>Action và ràng buộc</h3>
  <ul class="dots small"><li>3 action = 3 pha xanh</li><li>Mỗi step <b>10 giây</b>; đổi pha thì <b>7 giây vàng</b> chạy trước</li><li><b>Min green 20 giây</b>: chưa đủ 20 giây thì không đổi pha</li></ul>
  <h3 style="margin-top:14px">Training</h3>
  <div class="small">Chỉ train trên <b>AM</b>: 5 training seed × 30 episode; mỗi 5 episode chạy validation, giữ checkpoint tốt nhất. Test trên cả normal, AM, PM.</div>
 </div>
 <div style="width:540px;flex:none">
  <div class="panel" style="padding:12px 14px">{mlp("16", dueling=True)}
   <div class="eq" style="font-size:14px">(16·64+64)+(64·64+64)+(64·1+1)+(64·3+3)
= <span class="a">5.508</span> tham số, viết bằng NumPy</div></div>
  <div class="panel caution" style="margin-top:14px;padding:12px 18px"><b>Reward.</b> <span class="small">r = −0,01 × (hàng chờ + pending) ở cuối mỗi step 10 giây. γ = 0,99 mỗi step, 3-step return.</span></div>
 </div>
</div>''', secs=70, source="src/traffic_rl/sim/sumo_single_junction.py · src/traffic_rl/agents/dqn.py · scripts/train_danang_sumo.py · configs/danang_pilot.yaml", notes=N(
    "State có 16 số: bốn hàng chờ, bốn số xe, bốn số xe pending, tức là xe đã đến giờ xuất phát nhưng chưa vào được, rồi one-hot của pha hiện tại, và thời gian từ lần đổi pha cuối. "
    "Model ra ba Q-value cho ba pha xanh. Mỗi step là 10 giây; đổi pha thì có 7 giây vàng, và min green là 20 giây. Mạng là hai lớp ẩn 64, tách V và A, tổng 5.508 tham số. "
    "Reward là âm của hàng chờ cộng pending. Model chỉ được train trên AM, năm training seed, mỗi seed 30 episode, checkpoint chọn trên validation, rồi test trên cả ba regime.",
    ["16 = 4 hàng chờ + 4 số xe + 4 pending + 3 one-hot + 1 thời gian", "Step 10 giây · vàng 7 · min green 20", "Train chỉ AM · 5 seed × 30 episode"],
    ["Không mô tả action như đổi đèn tức thì; luôn qua vàng và min green."],
    [("Vì sao đưa pending vào state?", "Để model thấy xe chưa vào được mạng; nếu không, controller có thể trông tốt chỉ nhờ giữ xe ở ngoài."),
     ("30 episode đã hội tụ chưa?", "30 episode là giới hạn em đặt; validation chọn checkpoint tốt nhất trong 30 episode đó, chưa chứng minh model đã hội tụ (B16).")]))

slide("SUMO", "Đo cái gì, và so với ai", f'''
<div class="row" style="gap:36px">
 <div class="col">
  <h3>Metric chính: queue integral</h3>
  <div class="eq">I = Σ<sub>t</sub> [hàng chờ(t) + pending(t)] × Δt     <span class="c">xe-giây</span>
I<sub>xe-giờ</sub> = I<sub>xe-giây</sub> / 3600</div>
  <div style="display:flex;align-items:center;gap:18px;margin:16px 0 8px"><div class="hero" style="font-size:38px">10 xe × 60 giây</div><div class="hero go" style="font-size:38px">= 600 xe-giây</div></div>
  <div class="xs muted" style="margin-bottom:22px">= 1/6 xe-giờ. Queue integral không phải tổng delay.</div>
  <h3>Vì sao cộng pending?</h3>
  <p class="small">Controller chặn cửa vào sẽ giữ xe ở ngoài và trông “tốt” nếu chỉ đếm xe trong mạng. Chỉ tính xe <b>đã đến giờ nhưng bị chặn</b>, không tính xe tương lai.</p>
 </div>
 <div class="col">
  {table(["Controller", "Cách quyết định", "Có học?"], [
      ["<span class='lamp' style='background:#8B97A1'></span><b>Fixed-time công bố</b>", "SUMO: lịch 103 giây", "Không"],
      ["<span class='lamp' style='background:#8B97A1'></span><b>Fixed-time tuned</b>", "CityFlow: xanh chọn từ 20–60 giây trên validation → 25 giây", "Grid search"],
      ["<span class='lamp' style='background:#3A74C9'></span><b>Max-Pressure</b>", "Pha có pressure (vào − ra) lớn nhất", "Không"],
      ["<span class='lamp' style='background:#8FB1E3'></span><b>MP có trễ</b>", "Như Max-Pressure, nhưng phải giữ pha đủ lâu mới được đổi", "Không"],
      ["<span class='lamp' style='background:#1C9A73'></span><b>RL</b>", "Q-value đã học", "Có"]], cls="t tight")}
  <h3 style="margin-top:22px">Metric phụ, luôn đọc cùng nhau</h3>
  <div><span class="tag">completion</span><span class="tag">insertion</span><span class="tag">travel time</span><span class="tag caution">spillback</span><span class="tag">số lần đổi pha</span><span class="tag stop">collision / emergency</span></div>
 </div>
</div>''', secs=50, source="src/traffic_rl/sim/multi_agent_env.py · src/traffic_rl/eval/network_metrics.py · src/traffic_rl/agents/max_pressure.py", notes=N(
    "Metric chính là queue integral: mỗi giây cộng số xe đang chờ và số xe pending. Mười xe chờ sáu mươi giây là 600 xe-giây. "
    "Vì sao cộng pending? Vì một controller chặn cửa vào sẽ giữ xe ở ngoài và trông tốt nếu chỉ đếm xe bên trong. Đây từng là lỗi thật trong dự án và đã được sửa. "
    "Baseline gồm fixed-time, Max-Pressure và Max-Pressure có trễ. Các metric phụ như completion, travel time và spillback luôn được đọc cùng.",
    ["10 xe × 60 giây = 600 xe-giây", "Pending = đến giờ nhưng bị chặn", "Baseline: fixed-time · MP · MP có trễ"],
    ["Không gọi queue integral là “tổng delay”."]))

# ================================================================== CityFlow
steps = ["Đầu block: đọc observation từng nút", "Tạo lịch fixed-time gốc cho block", "Macro 0 = giữ nguyên lịch",
         "Candidate: đổi pha sớm hơn hoặc muộn hơn 10 giây, tại <b>một</b> lần đổi pha", "ShadowSignal chạy thử từng candidate, bỏ cái không hợp lệ", "MLP chấm điểm candidate hợp lệ; mỗi nút chọn một",
         "Chạy 30 step 10 giây", "Cuối block: kiểm tra anchor, lấy reward"]
sth = "".join(f'<div style="display:flex;gap:10px;margin:5px 0;break-inside:avoid"><div class="hero go" style="font-size:22px;width:20px">{i+1}</div><div class="xs" style="padding-top:2px">{s}</div></div>' for i, s in enumerate(steps))
slide("CityFlow", "Ở 53 nút: chỉnh lịch thay vì chọn pha tự do", f'''
<div class="row" style="gap:36px">
 <div style="width:380px;flex:none">
  <h3 class="stop">Chọn pha tự do ở mọi nút</h3>
  <ul class="dots stop small"><li>Action space rất lớn: 53 nút × mọi step</li><li>Dễ làm hỏng lịch đèn đang chạy ổn</li><li>Khó kiểm tra, khó giải thích</li><li>Các bản chọn pha trước (V2, V3A) đều không qua gate</li></ul>
 </div>
 <div class="col">
  <h3 class="go">Residual theo lịch</h3>
  <p class="small" style="margin-bottom:14px">Giữ <b>lịch fixed-time làm gốc</b>; model chỉ được <b>sửa nhỏ</b>, và mỗi lần sửa đều kiểm tra được.</p>
  <div class="row" style="gap:14px">
   <div class="col rule-l go"><div style="font-size:22px;font-weight:850">Lịch</div><div class="xs">lịch fixed-time gốc (xanh 25 giây)</div></div>
   <div class="col rule-l go"><div style="font-size:22px;font-weight:850">Residual</div><div class="xs">action = đổi pha sớm / muộn 10 giây</div></div>
   <div class="col rule-l go"><div style="font-size:22px;font-weight:850">Anchor</div><div class="xs">cuối block, đèn phải về đúng như lịch gốc</div></div>
   <div class="col rule-l go"><div style="font-size:22px;font-weight:850">Shared MLP</div><div class="xs">27 feature → 1 Q, 6.017 tham số, dùng chung 53 nút</div></div>
  </div>
 </div>
</div>
<div class="row" style="gap:20px;margin-top:30px">
 <div class="note col"><b>Trade-off.</b> Model chỉ được sửa nhỏ. Nếu cần đổi lịch nhiều thì residual không làm được.</div>
 <div class="note go col"><b>Macro 0 luôn có sẵn</b> = giữ nguyên lịch. <b>Normal</b> chạy fixed-time theo thiết kế; <b>AM và PM</b> dùng residual.</div>
</div>''', secs=50, source="docs/research/haichau-v3b-residual-protocol.md · src/traffic_rl/agents/schedule_residual.py · src/traffic_rl/agents/phase_ddqn.py", notes=N(
    "Trên mạng, nếu cho mỗi nút chọn pha tự do thì action space rất lớn, dễ làm hỏng lịch đang chạy ổn, và các bản trước của em đều không qua gate. "
    "Nên em chuyển sang residual: giữ lịch fixed-time làm gốc, và model chỉ được cho một lần đổi pha xảy ra sớm hơn hoặc muộn hơn 10 giây. Cuối mỗi block, đèn phải về đúng như lịch gốc; em gọi điểm này là anchor. "
    "Một MLP nhỏ, 27 feature vào, một Q-value ra, 53 nút dùng chung weight. Trade-off: model bị giới hạn, nhưng đổi lại mọi hành vi đều kiểm tra được.",
    ["Lịch · Residual · Anchor · Shared MLP", "Macro 0 = giữ nguyên lịch, luôn có sẵn", "Trade-off: kiểm tra được vs linh hoạt"],
    ["Không gọi đây là multi-agent communication hay GNN."],
    [("27 feature gồm gì?", "12 feature của pha trước lúc đổi, 12 của pha sau, và 3 số mô tả macro; thông tin nút kề chỉ là feature tóm tắt (B17)."),
     ("53 agent có giao tiếp không?", "Không có communication được học. Chúng dùng chung weight, thấy hàng chờ upstream / downstream (tóm tắt), và cùng một reward cho cả mạng.")]))

slide("CityFlow", "Một macro: đổi pha sớm / muộn 10 giây, rồi về anchor", f'''
<div class="panel" style="padding:12px 14px">{macro_timeline()}</div>
<div class="row" style="gap:26px;margin-top:18px">
 <div style="flex:1.2"><h3>Tám bước trong mỗi block 300 giây</h3><div style="columns:2;column-gap:22px">{sth}</div></div>
 <div class="col">
  <div class="panel dark" style="padding:16px 20px"><h3>Anchor không reset giao thông</h3><div class="small">Chỉ <b style="color:#fff">trạng thái đèn</b> (pha, transition, timer) phải khớp lịch gốc; hàng chờ và xe vẫn giữ nguyên, đi tiếp sang block sau.</div></div>
  <div class="row" style="gap:24px;margin-top:16px">{stat("0", "lần đổi pha sai luật hoặc lệch anchor")}{stat("59", "macro tối đa mỗi nút, có mask")}</div>
 </div>
</div>''', secs=60, source="src/traffic_rl/sim/schedule_residual.py (ShadowSignal, macro compiler) · trục thời gian chỉ minh họa ý", notes=N(
    "Đây là một block 300 giây. Giả sử lịch gốc đổi pha ở giây 100. Model có thể chuyển sớm ở giây 90, muộn ở giây 110, hoặc giữ nguyên, tức macro 0. "
    "ShadowSignal chạy thử logic đèn của từng candidate, không có xe, để kiểm tra min green, transition và anchor. Candidate không đạt bị mask. MLP chấm điểm phần còn lại, mỗi nút chọn một. "
    "Điểm quan trọng: anchor chỉ bắt đèn khớp, không reset giao thông. Trong block, mỗi hướng được xanh sớm hoặc muộn hơn, nên lượng xe đi qua khác nhau, và hàng chờ khác nhau; đó là lý do residual có tác dụng.",
    ["±10 giây tại một lần đổi pha mỗi block", "ShadowSignal kiểm tra hợp lệ + anchor", "Anchor khớp đèn, KHÔNG khớp giao thông"],
    ["Ví dụ 90 / 100 / 110 là minh họa."],
    [("Đã về anchor thì sao hàng chờ vẫn đổi?", "Trong block, đèn xanh cho từng hướng đến sớm hoặc muộn hơn, nên lượng xe đi qua khác nhau. Giao thông không bị reset; chỉ đèn được đưa về khớp.")]))

train_rows = [["Dữ liệu train", "chỉ AM (demand 11 / sim 11)", "6 scenario peak: 3 AM + 3 PM"],
              ["Episode × seed", "30 × 5 (seed 11–15)", "12 × 5 (seed 12–16)"],
              ["Reward", "−0,01 × (hàng chờ + pending), mỗi step 10 giây", "−Δ queue integral cả mạng / 100.000, mỗi macro"],
              ["γ", "0,99 mỗi 10 giây, 3-step return", "0,99 mỗi 300 giây"],
              ["Exploration", "ε 1,0 → 0,05 trong 5.000 quyết định", "ε cố định 0,15; output khởi tạo 0 → bắt đầu từ macro 0"],
              ["Chọn checkpoint", "validation AM mỗi 5 episode", "validation ep 4 / 8 / 12, qua selector V1"]]
slide("CityFlow", "Training và chọn checkpoint ở cả hai tầng", f'''
<div class="row" style="gap:30px">
 <div style="flex:1.5">{table(["", "SUMO", "CityFlow residual"], train_rows, cls="t tight")}
  <div class="note" style="margin-top:14px;font-size:15px">Checkpoint luôn được chọn trên <b>validation</b>, không bao giờ trên test.</div></div>
 <div class="col">
  <h3>Selector V1 <span class="sub">CityFlow</span></h3>
  <ul class="dots small"><li>Normal phải khớp fixed-time từng scenario</li><li>Regret ở peak ≤ 0, trung bình ≤ −1%</li><li>Completion / insertion không giảm quá 2 điểm</li><li>0 vi phạm contract</li></ul>
  <div class="row" style="gap:10px;margin-top:12px">{stat("12 · 14 · 15", "seed được chọn", "go", 30)}{stat("13 · 16", "seed bị loại", "stop", 30)}</div>
  <div class="note stop" style="margin-top:12px;font-size:14.5px">Không qua thì <b>fail closed</b>, không lấy bản ít tệ nhất. Strict release: <b>complete = false</b>, còn 14 gate mở.</div>
 </div>
</div>''', secs=60, source="scripts/train_danang_sumo.py · src/traffic_rl/train/schedule_residual_trainer.py · configs/haichau_residual_final_selection_v1.yaml", notes=N(
    "Bảng này tóm tắt training của hai tầng. SUMO train trên AM, năm seed, mỗi seed 30 episode. CityFlow train trên sáu scenario peak, năm seed, mỗi seed 12 episode, với reward là queue integral của cả mạng. "
    "Ở cả hai tầng, checkpoint chỉ được chọn trên validation. Với CityFlow, em thêm selector V1: normal phải khớp fixed-time, regret ở peak phải âm, completion không được giảm quá 2 điểm. Không qua thì fail closed. "
    "Kết quả: seed 12, 14 và 15 được chọn; seed 13 và 16 bị loại. Strict release vẫn chưa hoàn tất.",
    ["Checkpoint chọn trên validation", "Seed 12 / 14 / 15 chọn · 13 / 16 loại", "Fail closed · release chưa xong"],
    ["Không nói mỗi seed SUMO train trên dữ liệu khác nhau."],
    [("Reward toàn cục có hạn chế gì?", "Đúng với mục tiêu chung, nhưng khó biết nút nào làm tốt (credit assignment). Local reward hoặc difference reward là việc làm sau (B18)."),
     ("Seed bị loại mà test vẫn tốt?", "Vẫn giữ quyết định theo validation; kết quả test chỉ báo để tham khảo (post-hoc) (B19).")]))

# ================================================================== Results
sumo_series = [("Fixed-time công bố", C["base"]), ("Dueling DDQN, 5 seed", C["go"]), ("Max-Pressure", C["pressure"]), ("MP có trễ", C["pressure2"])]
sumo_vals = [[9.86, 79.20, 152.67], [41.50, 78.41, 99.97], [140.72, 352.43, 269.02], [126.85, 281.52, 241.40]]
slide("Kết quả", "SUMO: thắng rõ ở PM, hòa ở AM, thua ở normal", f'''
<div class="row" style="gap:0;margin-bottom:14px">
 <div class="col" style="border-left:6px solid {C["stop"]};padding-left:18px"><div class="hero stop" style="font-size:64px">+320,7%</div><div class="small"><b>Normal</b> 9,86 → 41,50 xe-giờ</div></div>
 <div class="col" style="border-left:6px solid {C["caution"]};padding-left:18px"><div class="hero caution" style="font-size:64px">−1,0%</div><div class="small"><b>AM</b> 79,20 → 78,41 xe-giờ</div></div>
 <div class="col" style="border-left:6px solid {C["go"]};padding-left:18px"><div class="hero go" style="font-size:64px">−34,5%</div><div class="small"><b>PM</b> 152,67 → 99,97 xe-giờ</div></div>
</div>
<div class="row" style="gap:30px">
 <div style="width:660px;flex:none">{legend(sumo_series, 13.5)}{grouped_bars(["Normal", "Peak AM", "Peak PM"], sumo_series, sumo_vals, 400, w=660, h=300, unit="hàng chờ + pending, xe-giờ")}</div>
 <div class="col">
  <h3>Cách đọc</h3>
  <ul class="dots small"><li><b class="go">PM:</b> giảm rõ</li><li><b class="caution">AM:</b> ngang fixed-time</li><li><b class="stop">Normal:</b> tệ hơn nhiều → không nên chạy RL ở mọi regime</li><li>Cả hai baseline pressure đều thua fixed-time tại nút này</li><li>120 lượt test: <b>0 collision, 0 emergency</b> (trong mô phỏng)</li></ul>
 </div>
</div>''', secs=90, kind="results", source="SUMO · dueling_n3 · 5 training seed × 15 scenario test · queue integral + pending (xe-giờ) · results/danang_protocol_v1/summary/final-summary.csv", notes=N(
    "Đây là kết quả SUMO trên 15 scenario test, trung bình năm training seed. Ở PM, fixed-time là 152,67 xe-giờ, RL là 99,97: giảm 34,5 phần trăm. "
    "Ở AM, regime mà model được train, kết quả gần như ngang fixed-time. Ở normal, RL tệ hơn rõ: 41,5 so với 9,86, tăng 320,7 phần trăm. "
    "Cả hai baseline Max-Pressure đều thua fixed-time ở cả ba regime. Kết luận: lợi ích phụ thuộc regime; kết quả không ủng hộ chạy RL mọi lúc.",
    ["PM −34,5% · AM −1,0% · Normal +320,7%", "5 training seed × 15 scenario test", "MP thua fixed-time trong SUMO"],
    ["Không chỉ báo PM; luôn nói normal tệ hơn."],
    [("Vì sao normal tệ hơn?", "Model chỉ train trên AM. Distribution shift hoặc thời điểm ra action chỉ là giả thuyết, chưa có ablation để chứng minh (B20)."),
     ("Vì sao Max-Pressure thua ở đây?", "Chỉ thấy bốn luồng, và mỗi lần đổi pha mất 7 giây vàng trong step 10 giây. Điều này không có nghĩa là Max-Pressure sai.")]))

slide("Kết quả", "Thứ hạng baseline có phải may mắn? 1.000 realization, không RL", f'''
<div class="row" style="gap:0;margin-bottom:12px">
 <div class="col" style="border-left:6px solid {C["base"]};padding-left:16px"><div class="hero" style="font-size:44px">3.000 / 3.000</div><div class="small">Fixed-time &lt; <b>Max-Pressure</b> ở mọi cặp</div></div>
 <div class="col" style="border-left:6px solid {C["base"]};padding-left:16px"><div class="hero" style="font-size:44px">2.999 / 3.000</div><div class="small">Fixed-time &lt; <b>MP có trễ</b></div></div>
 <div class="col" style="border-left:6px solid {C["caution"]};padding-left:16px"><div class="hero caution" style="font-size:44px">100 · 76 · 88%</div><div class="small">MP có trễ &lt; MP thường ở normal · AM · PM</div></div>
</div>
<img class="fig" src="{img("mc")}" style="width:1136px;height:400px;object-fit:contain">
<div class="cap">9.000 lượt SUMO = 1.000 paired realization (demand seed, SUMO seed) × 3 regime × 3 baseline, hàng chờ + pending (xe-giờ). Mọi realization dùng cùng số xe từ <b>một</b> ngày camera, không phải 1.000 ngày giao thông. Không gồm RL (chi phí training).</div>''', secs=30, kind="results", source="SUMO · scripts/run_danang_baseline_mc.py · results/danang_baseline_mc/summary.json · parity: tái lập đúng scenario test AM-101", notes=N(
    "Thứ hạng baseline có phải do năm scenario test tình cờ không? Em chạy riêng ba baseline trên 1.000 realization demand mới mỗi regime, tổng 9.000 lượt SUMO. "
    "Fixed-time thắng Max-Pressure ở cả 3.000 cặp. Vậy bảng chính không đến từ scenario may mắn. Lưu ý: đây vẫn là số liệu của một ngày, không phải 1.000 ngày, và không có RL.",
    ["9.000 lượt = 1.000 × 3 regime × 3 baseline", "Fixed-time < MP 3.000/3.000", "Không RL · không phải 1.000 ngày"],
    ["Không nói 1.000 lượt có cả RL."],
    [("Sao không chạy DQN 1.000 lần?", "Chi phí training quá lớn; kết quả RL giữ ở 5 seed × 15 scenario. Thí nghiệm này chỉ kiểm tra thứ hạng baseline có ổn định không."),
     ("Sao MP có trễ phân tán mạnh?", "Vì phải giữ pha đủ lâu, chỉ cần giờ xe đến lệch một chút là chuỗi pha phía sau đổi hẳn, nên kết quả trải rộng ở peak.")]))

cf_rows = [("Fixed-time tuned", 8339.43, C["base"], "mốc, 0%"), ("Max-Pressure", 6347.00, C["pressure"], "−23,89%, tốt nhất"),
           ("MP có trễ", 6739.13, C["pressure2"], "−19,19%"), ("Residual s14", 7829.25, C["go"], "−6,12%")]
slide("Kết quả", "CityFlow: Max-Pressure vẫn tốt nhất; residual giảm 6,12% so với fixed-time", f'''
<div class="row" style="gap:34px">
 <div style="width:660px;flex:none">
  <h3>Tổng queue integral trên 15 scenario <span class="sub">xe-giờ</span></h3>
  {hbars(cf_rows, 8800, w=660, row_h=76, label_w=190)}
 </div>
 <div class="col">
  <div class="row" style="gap:24px;margin-bottom:18px">{stat("−23,89%", "Max-Pressure", "pressure", 44)}{stat("−6,12%", "Residual, một policy", "go", 40)}</div>
  {table(["Pooled reduction", "Normal", "AM", "PM"], [["Max-Pressure", "26,72%", "23,85%", "22,66%"], ["MP có trễ", "<b>35,60%</b>", "9,95%", "17,37%"],
        ["Residual s14", "0% (fixed)", "3,48%", "<b>10,39%</b>"]], cls="t tight", align=["", "r", "r", "r"], rowcls={2: "go"})}
  <div class="note stop" style="margin-top:16px;font-size:15.5px">Đây là <b>một policy</b> (seed 14, episode 4), không phải trung bình năm seed. Giá trị tuyệt đối không so được với SUMO.</div>
 </div>
</div>''', secs=75, kind="results", source="CityFlow · residual seed 14 / episode 4 · 15 paired scenario × 3.600 giây · hàng chờ + pending, xe-giờ · pooled reduction so với fixed-time tuned · final15-controller-matrix-summary.json", notes=N(
    "Trên mạng 53 nút, đây là kết quả 15 scenario của một policy: seed 14, checkpoint episode 4. Fixed-time tuned là 8.339 xe-giờ; residual giảm xuống 7.829, tức giảm 6,12 phần trăm. "
    "Nhưng Max-Pressure giảm 23,89 phần trăm, và Max-Pressure có trễ giảm 19,19 phần trăm. Vậy trên mạng, Max-Pressure là controller tốt nhất. "
    "Theo regime, residual bằng fixed-time ở normal theo thiết kế, giảm 3,48 phần trăm ở AM và 10,39 phần trăm ở PM. Câu đúng là: residual tốt hơn fixed-time, nhưng không thắng baseline pressure.",
    ["Fixed 8.339 · MP 6.347 · MP trễ 6.739 · Residual 7.829", "MP −23,89% thắng residual −6,12%", "Một policy: seed 14, episode 4"],
    ["Không nói “RL tốt nhất” trên mạng."],
    [("Vì sao Max-Pressure thắng?", "Có thể do train chưa đủ lâu, reward chung cho cả mạng nên khó biết nút nào làm tốt (credit assignment), và residual chỉ được sửa nhỏ. Chưa có ablation để biết nguyên nhân nào chính.")]))

slide("Kết quả", "Exploratory: residual chỉ ở PM, trên năm training seed", f'''
<div class="row" style="gap:34px">
 <div style="width:610px;flex:none">
  <h3>Pooled reduction trên 15 scenario <span class="sub">normal → fixed, AM → fixed, PM → residual</span></h3>
  {gate_chart(w=610, h=330)}
  <div class="xs muted">Đặc = được chọn; viền đứt = seed bị loại, chỉ để tham khảo; <b class="caution">nét đứt vàng = trung bình 3,48%</b>.</div>
 </div>
 <div class="col">
  <div class="row" style="gap:24px;margin-bottom:22px">{stat("3,48%", "trung bình năm seed", "caution", 50)}{stat("1,03–5,62%", "seed thấp nhất – cao nhất", "ink", 36)}</div>
  <div class="row" style="gap:24px;margin-bottom:20px">{stat("15 / 25", "ô PM (seed × scenario) tốt hơn", "go", 40)}{stat("10 / 25", "ô PM tệ hơn fixed-time", "stop", 40)}</div>
  <div class="note stop" style="margin-top:14px;font-size:15.5px"><b>Post-hoc.</b> Gate này được chọn <b>sau khi đã thấy kết quả test</b> và có dùng checkpoint của seed bị loại 13 và 16. Trung bình dương <b>không</b> xóa selection bias → cần một test set độc lập mới.</div>
 </div>
</div>''', secs=45, kind="results", source="CityFlow · 5 training seed × 15 scenario · pooled reduction so với fixed-time · final15-regime-gated-direct-multi-seed-summary.json · exploratory", notes=N(
    "Vì residual giúp nhiều nhất ở PM, em phân tích thêm một gate: normal và AM chạy fixed-time, chỉ PM dùng residual, cho cả năm seed. "
    "Mức giảm trung bình là 3,48 phần trăm. Nhưng 10 trên 25 ô PM vẫn tệ hơn fixed-time. "
    "Quan trọng nhất: đây là phân tích post-hoc, làm sau khi đã thấy kết quả test. Muốn thành kết luận, phải freeze gate rồi chạy trên test set mới.",
    ["Trung bình 3,48% · khoảng 1,03–5,62%", "10 / 25 ô PM vẫn tệ hơn", "POST-HOC — cần test mới"],
    ["Không trình bày đây là kết quả chính hay đã xác nhận."],
    [("Trung bình dương mà 10 trên 25 vẫn tệ?", "Phần được ở các scenario tốt nặng hơn phần mất ở các scenario xấu; trung bình dương không bảo đảm từng scenario.")]))

# ================================================================== Wrap-up
demo_steps = [("15 giây", "Cả mạng", "53 đèn từ topology OSM; demand và lịch là mô phỏng."),
              ("20 giây", "Reset góc xem", "Cùng scenario PM, demand 105 / sim 205, đồng bộ thời gian; seed 14, episode 4."),
              ("20 giây", "Khung 1.085 giây (18:05)", "Nút 420249521: fixed-time có 14 xe chờ, residual có 1."),
              ("20 giây", "Play và các nút liên kết", "Hàng chờ và đèn theo thời gian; xem các nút kề."),
              ("15 giây", "Quay lại bảng tổng", "Một khung chỉ minh họa; kết luận dựa trên đánh giá đủ giờ, nhiều scenario.")]
dh = "".join(f'<div style="display:flex;gap:14px;margin:9px 0"><div class="hero go" style="font-size:20px;width:70px;flex:none">{t}</div><div class="small"><b>{a}.</b> {b}</div></div>' for t, a, b in demo_steps)
slide("Kết luận", "Demo: replay scenario PM, demand 105", f'''
<div class="row" style="gap:30px">
 <div style="width:620px;flex:none"><img class="fig" src="{img("demo")}" style="width:620px;height:auto">
  <div class="cap">Demo trên trình duyệt: fixed-time tuned (trái) và residual (phải) tại mốc 18:05 đã trôi. Mở bằng <span class="mono">python3 launch_demo.py --no-browser --port 8766</span>.</div></div>
 <div class="col"><h3>Kịch bản 90 giây</h3>{dh}
  <div class="note" style="margin-top:12px;font-size:14.5px"><b>18:05</b> là 18 phút 5 giây mô phỏng, không phải 6 giờ chiều. Trình duyệt <b>không</b> train và không chạy mô phỏng. “Ít hơn 13 xe chờ” không bằng “thả thêm 13 xe”.</div></div>
</div>''', secs=90, source="results/haichau_network_v2/demo-visual/manifest.json · docs/defense/demo-runbook.md", notes=N(
    "[Chuyển sang trình duyệt nếu demo đã mở; nếu không thì dùng ảnh này.] "
    "Đây là mạng 53 nút dựng từ OSM. Em reset góc xem: hai bên cùng scenario PM, demand 105, simulation seed 205; bên phải là residual seed 14, episode 4. "
    "Ở phút 18 giây 5 của mô phỏng, tại nút 420249521, fixed-time có 14 xe chờ, residual có 1. Em bấm play và xem các nút kề. "
    "Cuối cùng em quay lại bảng tổng: một khung hình chỉ minh họa hành vi; con số kết luận đến từ đánh giá đủ 1 giờ, nhiều scenario. Đây là bản replay; trình duyệt không train và không chạy mô phỏng.",
    ["PM demand 105 / sim 205 · seed 14 ep 4", "Nút 420249521: 14 vs 1 lúc 18:05", "Replay đã ghi; kết bằng bảng tổng"],
    ["Không gọi 18:05 là giờ đồng hồ.", "Không suy ra đã thả thêm 13 xe."],
    [("Demo có chạy RL trực tiếp không?", "Không. Đó là bản replay; metric cuối đến từ một lần đánh giá 3.600 giây riêng.")]))

can = ["RL giảm hàng chờ ở <b>PM</b> trên test set SUMO (−34,5%)", "Lợi ích <b>phụ thuộc regime</b>; normal tệ hơn rõ",
       "Residual 53 nút giảm 6,12% so với fixed-time tuned, <b>cho một policy</b>", "Max-Pressure thắng residual trên mạng",
       "Residual giữ đúng contract: 0 lần đổi pha sai luật, 0 lần lệch anchor", "Truy được từ nguồn đến config, checkpoint và kết quả"]
cannot = ["RL thắng fixed-time ở mọi thời điểm trong ngày", "State of the art, hoặc thắng baseline mạnh trên mạng", "Gate chỉ-PM 3,48% là kết quả đã xác nhận",
          "Hiệu quả ngoài đường hoặc sẵn sàng triển khai", "Một ngày camera đại diện cho nhiều ngày, nhiều mùa"]
slide("Kết luận", "Được kết luận gì, và không được kết luận gì", f'''
<div class="row" style="gap:36px">
 <div class="col"><div style="display:flex;align-items:center;gap:12px;margin-bottom:10px"><span class="lamp" style="width:26px;height:26px;background:{C["go"]}"></span><h3 style="margin:0;font-size:24px">Bằng chứng hiện có hỗ trợ</h3></div><ul class="dots" style="font-size:19px">{"".join(f'<li style="margin:10px 0">{x}</li>' for x in can)}</ul></div>
 <div class="col"><div style="display:flex;align-items:center;gap:12px;margin-bottom:10px"><span class="lamp" style="width:26px;height:26px;background:{C["stop"]}"></span><h3 style="margin:0;font-size:24px">Không kết luận</h3></div><ul class="dots stop" style="font-size:19px">{"".join(f'<li style="margin:10px 0">{x}</li>' for x in cannot)}</ul></div>
</div>
<div class="panel dark" style="margin-top:28px;font-size:19px">Luận văn này là: <b style="color:#6FD3B0">xây dựng hệ thống + đánh giá trong mô phỏng, báo cáo cả kết quả xấu</b>.</div>''', secs=55, notes=N(
    "Để Hội đồng dễ đối chiếu, em tách hai cột. Bên trái là điều bằng chứng hỗ trợ: RL giảm hàng chờ PM trong SUMO; lợi ích phụ thuộc regime; residual giảm 6,12 phần trăm cho một policy; Max-Pressure thắng residual; và residual luôn giữ contract. "
    "Bên phải là điều em không kết luận: RL thắng mọi lúc, thắng baseline mạnh, gate chỉ-PM đã xác nhận, hay hiệu quả ngoài đường. "
    "Em xem luận văn là xây dựng hệ thống và đánh giá trong mô phỏng, có báo cáo cả kết quả xấu.",
    ["Cột xanh = được nói", "Cột đỏ = không được nói", "Luận văn = hệ thống + đánh giá trong mô phỏng"]))

slide("Kết luận", "Đóng góp, giới hạn và bước tiếp", f'''
<div class="row" style="gap:30px">
 <div class="col"><h3 class="go">Đóng góp</h3><ul class="dots small">
  <li><b>Hai tầng thí nghiệm</b>: một nút có nguồn công bố và một mạng OSM 53 nút</li><li>State, action, reward <b>viết rõ trong code</b></li>
  <li>Một <b>residual action kiểm tra được</b>: đổi pha sớm / muộn 10 giây, kiểm tra hợp lệ, về anchor</li><li><b>Paired evaluation</b>, nhiều training seed, tính pending, công bố kết quả xấu</li></ul></div>
 <div class="col"><h3 class="stop">Giới hạn</h3><ul class="dots stop small">
  <li>Camera: một ngày, bốn luồng, đọc xấp xỉ; demand mạng là tổng hợp</li><li>Chưa calibrate với dữ liệu xe chạy thực tế</li>
  <li>Normal tệ hơn trong SUMO; Max-Pressure thắng residual trên mạng</li><li>Test set đã được dùng để sửa mô phỏng và chọn gate post-hoc</li></ul></div>
 <div class="col"><h3 class="caution">Bước tiếp</h3><ul class="dots caution small">
  <li><b>Freeze</b> policy và gate, rồi chạy test set mới</li><li><b>Ablation</b>: dueling, n-step, feature nút kề, reward, giới hạn ±10 giây</li>
  <li>Dữ liệu nhiều ngày (có thể từ camera công khai) và calibrate thực tế</li></ul></div>
</div>
<div class="note ink" style="margin-top:22px;font-size:15.5px">Không nhận là đóng góp: phát minh Double DQN hay dueling, state of the art, hay sẵn sàng điều khiển đèn thật.</div>''',
      secs=55, notes=N(
    "Đóng góp chính gồm: thiết kế hai tầng thí nghiệm; state, action và reward viết rõ trong code; một residual action kiểm tra được; và paired evaluation có tính pending, nhiều seed, công bố cả kết quả xấu. "
    "Giới hạn: dữ liệu camera chỉ một ngày, demand mạng là tổng hợp, chưa calibrate; normal tệ hơn trong SUMO và Max-Pressure thắng trên mạng; gate PM là post-hoc. "
    "Bước tiếp theo thứ tự: freeze policy và gate rồi chạy test mới; làm ablation; sau đó mới đến dữ liệu nhiều ngày và calibrate thực tế.",
    ["4 đóng góp — nhấn residual kiểm tra được + paired evaluation", "Nói giới hạn trước khi bị hỏi", "Ưu tiên: freeze → test mới → ablation"],
    [], [("Em sẽ cải thiện gì trước?", "Freeze policy và gate, chạy test set mới với baseline mạnh và nhiều seed; sau đó mới ablation và calibrate.")]))

slide("Kết luận", "", f'''
<div style="position:absolute;right:120px;top:120px">{signal_head("go", 130, 420)}</div>
<div style="position:absolute;left:72px;top:110px;width:900px;font-size:36px;line-height:1.25;font-weight:800;color:#fff;letter-spacing:-.02em">RL có thể giảm hàng chờ ở một số regime mô phỏng, nhưng lợi ích không đều và chưa thắng baseline mạnh trên mạng.</div>
<div style="position:absolute;left:72px;top:360px;width:860px;font-size:21px;line-height:1.5;color:#AFC0CC">Đóng góp: hai tầng thí nghiệm, một residual controller có hành vi kiểm tra được, và mọi con số đều truy được về nguồn. Bước tiếp: freeze policy và gate, test trên demand mới, rồi calibrate với dữ liệu thực tế.</div>
<div style="position:absolute;left:72px;top:540px;font-size:48px;font-weight:850;color:#fff">Em xin cảm ơn.</div>
''', secs=30, kind="closing", notes=N(
    "Tóm lại, RL có thể giảm hàng chờ ở một số regime mô phỏng, nhưng lợi ích không đều và chưa thắng baseline mạnh trên mạng. "
    "Bước tiếp là freeze policy và gate, test trên demand mới, rồi calibrate với dữ liệu thực tế. Em xin cảm ơn Hội đồng và sẵn sàng nhận câu hỏi.",
    ["Đọc câu kết gần như nguyên văn", "Dừng, nhìn Hội đồng", "Mở slide phụ lục khi được hỏi"]))


# ================================================================== backup
# ================================================================== backup
slide(B, "B1 · Hyperparameter của hai model", table(["Tham số", "SUMO dueling_n3", "Residual CityFlow V3B"], [
    ["Input, hidden, output", "16; 64, 64; V 1 + A 3 → 3 Q", "27 mỗi macro; 64, 64; 1 Q mỗi macro"], ["n-step, số action", "3; 3", "1 transition mỗi macro; tối đa 59, có mask"],
    ["Learning rate, Adam β1 / β2 / ε", "0,0003; 0,9 / 0,999 / 1e−8", "0,0003; 0,9 / 0,999 / 1e−8"], ["Huber δ, gradient clipping (L2)", "1; 10", "1; 10"],
    ["Replay buffer, batch, bắt đầu học sau", "50.000; 64; 256", "20.000; 128; 53"], ["Update, target sync", "1 update mỗi quyết định; mỗi 200 update", "8 update mỗi block; mỗi 64 update"],
    ["γ, reward scale", "0,99 mỗi 10 giây; × 0,01", "0,99 mỗi 300 giây; ÷ 100.000"], ["ε khi train", "1,0 → 0,05 trong 5.000 quyết định", "cố định 0,15"],
    ["Decision step, macro, shift", "10 giây; không; không", "10 giây; 300 giây; ±10 giây tại một lần đổi pha"], ["Min green, vàng, max red", "20 giây; 7 giây; không dùng", "20 giây; 3 giây (theo contract); 180 giây"],
    ["Fixed-time baseline", "32 / 28 / 22 + 3 × 7 = 103 giây", "xanh 25 giây"], ["Episode, validation, seed", "30; mỗi 5; 11–15", "12; mỗi 4; 12–16"],
    ["Output init, warm-start", "init mặc định của SharedDQN; 0", "W3 / b3 = 0; không imitation"]], cls="t tight"), secs=0, kind="backup",
      source="configs/danang_pilot.yaml · seed14-resolved-config.json · seed14-step4-contract.json", notes=N(
          "Dùng khi bị hỏi hyperparameter. Các giá trị có lý do kỹ thuật nhưng chưa chứng minh là tốt nhất. Em chỉ tune thời gian xanh của fixed-time, không tune hyperparameter của model.",
          ["target sync = 64 update, không phải 64 giây", "γ: SUMO mỗi 10 giây, CityFlow mỗi 300 giây", "Chỉ tune fixed-time, không tune hyperparameter"]))

slide(B, "B2 · Replay buffer, ε-greedy, Huber loss và Adam", f'''
{table(["Cơ chế", "Để làm gì", "Trong dự án này"], [["Replay buffer", "Dùng lại dữ liệu cũ; các mẫu liền nhau bớt giống nhau", "Ring buffer, lấy mẫu ngẫu nhiên <b>with replacement</b>"],
    ["ε-greedy", "Thỉnh thoảng thử action ngẫu nhiên, không phải lúc nào cũng chọn action tốt nhất", "Với xác suất ε, chọn ngẫu nhiên một action hợp lệ"], ["Huber loss", "Lỗi nhỏ thì bình phương, lỗi lớn thì tuyến tính", "δ = 1; tránh gradient quá lớn khi TD error lớn"],
    ["Gradient clipping", "Giới hạn độ lớn (L2 norm) của cả gradient", "Ngưỡng 10; không phải giới hạn weight ở ±10"], ["Adam", "Optimizer có momentum", "β1 = 0,9, β2 = 0,999, ε = 1e−8"],
    ["ReLU, He init", "Activation; cách khởi tạo weight hợp với ReLU", "max(0, x); √(2 / fan_in)"]])}
<div class="row" style="gap:20px;margin-top:18px">
 <div class="eq col">Huber(δ) = 0,5 · δ²      nếu |δ| ≤ 1
           |δ| − 0,5    nếu |δ| > 1</div>
 <div class="note col">ε của Adam chỉ để tránh chia cho 0. ε của ε-greedy là xác suất thử ngẫu nhiên. Loss giảm <b>không</b> có nghĩa là policy tốt, nên checkpoint được chọn bằng hàng chờ trên validation.</div>
</div>''', secs=0, kind="backup", notes=N("Dùng khi hỏi về optimizer, hoặc “vì sao loss giảm mà hàng chờ không giảm?”.", ["With replacement → batch 128 từ 53 mẫu vẫn chạy được", "Clip gradient, không clip weight", "Hai ε khác nhau"]))

slide(B, "B3 · Per-scenario mean và pooled", f'''
<div class="row" style="gap:30px">
 <div class="col"><div class="eq" style="font-size:15px"><span class="c"># âm là tốt</span>
regret_c      = 100 · (L − F) / F
<span class="c"># dương là tốt</span>
reduction_c   = 100 · (F − L) / F
pooled        = 100 · (ΣF − ΣL) / ΣF</div>
  <div class="xs muted" style="margin-top:8px">F = fixed-time, L = RL, c = một scenario.</div></div>
 <div class="col"><div class="note" style="font-size:15.5px"><b>Per-scenario mean</b>: tính % cho từng scenario rồi lấy trung bình. <b>Pooled</b>: cộng hết rồi mới tính %, nên scenario lớn nặng ký hơn.</div>
  <div class="note stop" style="margin-top:12px;font-size:15.5px">75 ô (seed × scenario) <b>không</b> phải 75 policy độc lập.</div></div>
</div>''', secs=0, kind="backup", notes=N("Dùng khi hỏi vì sao PM có hai số 8,86% và 10,39%.", ["Pooled: scenario lớn nặng ký hơn", "Đơn vị độc lập = training seed"]))

slide(B, "B4 · Thông số xe trong SUMO và CityFlow", f'''
<div class="row" style="gap:30px">
 <div style="flex:1.3"><h3>SUMO <span class="sub">file route XML, AM train</span></h3>{table(["", "Xe máy", "Ô tô", "Xe tải", "Xe buýt"], [["Dài / rộng, m", "2 / 0,8", "5 / 1,8", "8 / 2,5", "12 / 2,5"], ["Tăng / giảm tốc, m/s²", "3,5 / 5", "2 / 4,5", "1,3 / 4", "1,2 / 4"],
     ["minGap, m", "0,5", "2,5", "3", "3"], ["Tốc độ tối đa, m/s", "13,89 (≈50 km/h)", "11,11 (≈40)", "10", "10"], ["sigma, tau", "0,7; 1,2 giây", "0,5; —", "0,5; —", "0,5; —"]], cls="t tight", align=["", "c", "c", "c", "c"])}</div>
 <div class="col"><h3>CityFlow <span class="sub">haichau_dataset.py</span></h3>{table(["", "Xe máy", "Ô tô"], [["Dài / rộng, m", "2 / 1", "5 / 2"], ["Tăng / giảm tốc tối đa", "3,5 / 5", "2 / 4,5"], ["minGap, m", "0,5", "2,5"], ["Tốc độ tối đa, m/s", "13,89", "11,11"], ["headway, giây", "0,8", "1,5"]], cls="t tight", align=["", "c", "c"])}</div>
</div>
<div class="note" style="margin-top:20px">Chạy chính dùng <b>lane model</b> (xe đi theo làn). Em đã thử sublane model: chạy 300 giây thì ổn, nhưng chạy đủ 1 giờ thì có va chạm, nên bỏ. Tau của xe máy tăng từ 1,0 lên 1,2 sau một va chạm ở một scenario AM trong test set, rồi chạy lại tất cả. Nghĩa là test set đã được dùng để sửa mô phỏng. Thông số xe chưa calibrate với dữ liệu thực tế.</div>''',
      secs=0, kind="backup", notes=N("Dùng khi hỏi về xe máy, sublane, tau.", ["Lane model, không dùng sublane", "tau 1,2 chỉ cho xe máy", "headway CityFlow 0,8 khác tau SUMO 1,2"]))


slide(B, "B5 · Lịch sử thay đổi và bài học", table(["Vấn đề", "Đã đổi gì", "Được kết luận gì"], [
    ["Dữ liệu cũ gọi là “chuyến thật”", "Đổi tên thành dữ liệu synthetic", "Không có nguồn cho “50.500 chuyến thật”"], ["Mạng SUMO lớn bị lỗi", "Chỉ giữ nút có dữ liệu, đường vào khoảng 300 m", "SUMO chỉ còn một nút"],
    ["Thử sublane model", "Bỏ vì có va chạm khi chạy đủ 1 giờ", "Mất phần mô phỏng xe máy đi ngang"], ["Xe pending trên mạng", "Tách xe đã đến giờ nhưng chưa vào được khỏi xe chưa đến giờ", "Metric đúng từ đây; không dùng lại kết quả cũ"],
    ["Fixed-time chạy chưa đúng lịch", "Sửa clock, mask, cách đổi pha cho thống nhất", "So sánh với lịch đã chạy thật"], ["V2 chọn pha / V3A rehearsal", "Thêm feature nút kề, imitation / rehearsal", "Không qua gate, ghi trong decision log"],
    ["Residual V3B", "27 feature, macro 300 giây, ±10 giây", "Đây là bản dùng cho kết quả hiện tại"], ["V3C / V3D", "Đổi giới hạn và cách exploration", "Chỉ để tham khảo; không gộp vào V3B"],
    ["Gate chỉ PM", "Normal / AM chạy fixed-time, PM chạy residual", "Exploratory, cần test mới"], ["Kiểm tra lại ngày 23/9", "Sửa tên tác giả, vị trí trích dẫn, đơn vị số liệu", "Chỉ sửa cách đọc; không có thí nghiệm mới"]], cls="t tight"),
      secs=0, kind="backup", source="docs/research/decision-log.md · docs/research/thesis-evidence-ledger.md", notes=N(
          "Cách nói về thất bại: “Bản này không qua gate, nên em đổi thiết kế hoặc nói kết luận hẹp lại, và vẫn giữ bằng chứng.” Đừng kể như thể bản sau luôn tốt hơn bản trước.",
          ["Thất bại → kết luận hẹp hơn", "V3B là bản được báo cáo", "V3C / V3D chỉ để tham khảo"]))

slide(B, "B6 · Công nghệ và code nằm ở đâu", f'''
<div class="row" style="gap:30px">
 <div class="col">{table(["Công nghệ", "Dùng để"], [["Python, NumPy", "Pipeline; MLP, backprop, Adam, replay buffer"], ["SUMO + TraCI", "Mô phỏng một nút, điều khiển từ Python"], ["CityFlow (C++ và Python)", "Mô phỏng mạng 53 nút"],
     ["OSM, osmium, netconvert", "Lấy bản đồ và đổi format"], ["Docker, Colima", "Chạy CityFlow trong container (NumPy 1.19.5)"], ["Git, SHA-256", "Quản lý version code, kiểm tra file không bị đổi"], ["Matplotlib, LaTeX", "Vẽ hình và PDF luận văn"], ["HTML, JS, Canvas", "Demo replay trên trình duyệt"]], cls="t tight")}
  <div class="xs muted" style="margin-top:6px">PyTorch và SB3 có trong file requirements cũ nhưng <b>không</b> dùng cho hai model chính. Không dùng GPU.</div></div>
 <div class="col">{table(["Cần giải thích", "Mở file (trong src/traffic_rl/)"], [["Observation SUMO và đổi pha", "sim/sumo_single_junction.py"], ["Dueling, Double target, Adam", "agents/dqn.py"], ["Training loop SUMO", "train/trainer.py"], ["12 feature mỗi pha", "sim/phase_encoder.py"],
     ["Shared MLP", "agents/phase_ddqn.py"], ["ShadowSignal, macro, anchor", "sim/schedule_residual.py"], ["Training residual", "train/schedule_residual_trainer.py"], ["Queue integral, pending", "sim/multi_agent_env.py"], ["Selector cho từng seed", "research/final_residual_selector.py"]], cls="t tight")}</div>
</div>''', secs=0, kind="backup", notes=N("Dùng khi hỏi “code ở đâu?”: mở đúng file.", ["Hai model viết bằng NumPy", "Docker cho CityFlow", "Câu hỏi nào mở file nào"]))

slide(B, "B7 · Reproducibility: đã có gì, còn thiếu gì", f'''
<div class="row" style="gap:30px">
 <div class="col"><h3 class="go">Đã có</h3><ul class="dots small"><li>Manifest, resolved config, checkpoint contract, file JSON của selector</li><li>File route SUMO, network, CSV và JSON tổng kết</li><li>Evidence snapshot ngày 23/9 và script kiểm tra (84 / 84 kiểm tra nguồn và số liệu đều pass)</li><li>Entry point: prepare → train → evaluate → summarize; train / chọn residual; campaign; demo</li></ul></div>
 <div class="col"><h3 class="stop">Còn thiếu</h3><ul class="dots stop small"><li>Dữ liệu campaign gốc và checkpoint lớn không nằm trong Git</li><li>Strict release: còn 14 gate chưa qua</li><li>File NPZ không lưu replay buffer, trạng thái Adam và random state, nên không train tiếp đúng chỗ được</li><li>Provenance OSM ghi ngày tải và version tool là <span class="mono">unknown_not_recorded</span></li></ul></div>
</div>
<div class="panel dark" style="margin-top:24px">Nói đúng là: <b style="color:#6FD3B0">phần lớn có thể chạy lại, và những chỗ còn thiếu đã ghi rõ</b>. Không nói “ai clone repo cũng chạy lại được hết”.</div>''',
      secs=0, kind="backup", source="docs/research/thesis-review-verification.md · docs/research/thesis-evidence-audit.json", notes=N("Dùng khi hỏi về reproducibility.", ["84 / 84 kiểm tra pass ≠ strict release", "Strict release: còn 14 gate", "Nói thẳng"]))

slide(B, "B8 · Demand sensitivity trong SUMO", f'''
<div class="row" style="gap:30px">
 <div style="width:720px;flex:none"><img class="fig" src="{img("sensitivity")}" style="width:720px;height:450px;object-fit:contain"></div>
 <div class="col"><h3>Cách đọc</h3><ul class="dots small"><li>120 lượt chạy với demand × 0,75; 1,0; 1,25 và 1,5</li><li>30 lượt ở × 1,0 lặp lại điều kiện AM chính, nên <b>không</b> phải 120 kết quả độc lập mới</li><li>Cách nhân demand là em tự đặt, không phải đo được</li><li>0 collision, 4 emergency braking</li></ul></div>
</div>''', secs=0, kind="backup", source="results/danang_protocol_v1/summary/demand-sensitivity.png", notes=N("Dùng khi hỏi model có ổn khi demand thay đổi không.", ["× 1,0 lặp lại điều kiện chính", "Nhân demand là giả định", "4 emergency, 0 collision"]))

qa = [("Một model hay nhiều?", "Hai model: SUMO dueling Double DQN (16 → 3 Q); CityFlow residual Double DQN (27 mỗi macro → 1 Q), 53 nút dùng chung weight."),
      ("Sao không dùng GNN, PPO hay model lớn hơn?", "Action rời rạc và MLP nhỏ giúp dễ kiểm tra contract. Em chưa so sánh, nên không nói chúng tốt hơn hay kém hơn."),
      ("Reward residual có phải phần hơn fixed-time không?", "Không. Reward là −(hàng chờ + pending) của cả mạng trong block. Phần hơn fixed-time chỉ đo lúc paired evaluation."),
      ("Loss giảm mà hàng chờ không giảm?", "Loss chỉ đo model khớp TD target trong replay buffer, không chứng minh greedy policy tốt. Vì vậy checkpoint được chọn bằng validation."),
      ("Hệ thống có an toàn không?", "Luật pha, đèn vàng và anchor là logic trong mô phỏng. 120 lượt chính và 120 lượt sensitivity trong SUMO có 0 collision (đợt 1.000 realization baseline không ghi collision). Đây không phải chứng nhận an toàn ngoài đời."),
      ("Cùng γ = 0,99 mà khác nhau?", "0,99 mỗi 10 giây khác 0,99 mỗi 300 giây. Muốn so theo thời gian thật thì lũy thừa γ theo số step."),
      ("Seed bị loại mà test vẫn tốt?", "Vẫn giữ quyết định theo validation; kết quả test chỉ báo để tham khảo (post-hoc)."),
      ("Vậy đủ cho một luận văn chưa?", "Đủ cho xây dựng hệ thống và đánh giá trong mô phỏng, có phân tích thất bại; chưa đủ để nói triển khai thật.")]
qah = "".join(f'<div class="panel" style="padding:13px 18px"><div style="font-weight:850;color:{C["ink"]};font-size:19px;margin-bottom:3px">{q}</div><div class="small">{a}</div></div>' for q, a in qa)
slide(B, "B9 · Trả lời nhanh các câu hay gặp", f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">{qah}</div>', secs=0, kind="backup",
      source="docs/defense/thesis-understanding-guide-vi.md mục 22 · docs/defense/committee-questions-evidence-vi.md", notes=N(
          "Slide dự phòng. Mỗi câu trả lời: một câu kết luận, một câu giới hạn, rồi chỉ vào bằng chứng.", ["Trả lời ngắn rồi dừng", "Luôn nói giới hạn", "Mở file nếu cần"]))

cam_rows = [["Trần Phú", "168", "3", "J1: 89% → trục chính · 6% → Trưng Nữ Vương"],
            ["Nguyễn Văn Linh (tây)", "160", "126", "J1: 89% → trục chính · 10% → Trưng Nữ Vương"],
            ["Trưng Nữ Vương", "0", "49", "chỉ có xe ra (OSM: một chiều)"],
            ["2 Tháng 9", "182", "101", "J2: 39% → cầu · 37% → Bạch Đằng · 20% → trục chính"],
            ["Cầu Rồng", "104", "246", "J2: 62% → trục chính · 18% → 2 Tháng 9 · 13% → Bạch Đằng"],
            ["Bạch Đằng (bắc)", "3", "236", "chỉ có xe ra (OSM: một chiều)"]]
slide(B, "B10 · Camera YOLO: số đếm ô tô, kiểm tra và giới hạn", f'''
<div class="row" style="gap:28px">
 <div style="flex:1.35">{table(["Hướng (ô tô / 15 phút)", "Vào", "Ra", "Markov chain từ hướng này"], cam_rows, cls="t tight")}
  <div class="xs muted" style="margin-top:8px">Trục chính giữa J1–J2 (gần camera, đáng tin nhất): ô tô 323 lên / 152 xuống; xe máy 1.010 lên / 517 xuống.</div></div>
 <div class="col">
  <h3>Kiểm tra</h3><ul class="dots small"><li>Cân bằng ô tô: J1 480 vào / 501 ra; J2 612 / 735</li><li>63% xe vào có đường đi đầy đủ (689 route)</li><li>Đường một chiều trên OSM khớp với số đếm</li></ul>
  <h3 class="stop" style="margin-top:14px">Giới hạn</h3><ul class="dots stop small"><li>Chưa đếm tay để đối chiếu; chưa đo độ chính xác của tracking ID</li><li>Xe máy: 174 vào / 703 ra → hướng xa (cầu) bị đếm thiếu</li><li>Một camera, một ngày, 15 phút; máy chạy khoảng 95 phút cho 15 phút video</li></ul>
 </div>
</div>''', secs=0, kind="backup", source="results/camera_counts/caurong_20260711_1716/only_car/*.csv · results/camera_counts/README.md", notes=N(
    "Slide dự phòng cho câu hỏi về camera. Đọc bảng theo hàng: hướng vào, số ô tô vào và ra, rồi xác suất rẽ. Luôn nói giới hạn: chưa đếm tay, xe máy ở xa bị đếm thiếu.",
    ["Ô tô tin được: lệch vào–ra 4% / 17%", "Xe máy: chỉ tin trục chính", "Chưa đếm tay"]))


# ---- slides moved from the 40-minute main deck
slide(B, "B11 · Nghiên cứu trước ở Đà Nẵng: green wave trên trục chính (2007)", f'''
<div class="rule-l ink" style="margin-bottom:18px"><div class="small"><b>Trần Trung Việt & Phan Cao Thọ (2007).</b> <i>Nghiên cứu ứng dụng bài toán điều khiển giao thông bằng “Làn sóng xanh” trên các trục giao thông chính ở thành phố Đà Nẵng.</i> Tạp chí Cầu Đường Việt Nam, số 10/2007, tr. 23–28.</div></div>
{chain([("2007 · trục chính", "đếm xe thực tế → green wave"), ("2025 · một nút", "Phan, Le & Nguyen: lịch đèn, bảng rẽ, camera"), ("Luận văn này", "nút SUMO + mạng 53 đèn trên trục chính")])}
<div class="row" style="gap:30px;margin-top:22px">
 <div class="col panel go"><h3>Ý tưởng em lấy</h3><ul class="small" style="margin-left:18px">
  <li>Ở Đà Nẵng, bài toán đèn bắt đầu từ <b>số xe đếm thực tế</b> trên <b>trục chính có đèn</b>.</li>
  <li>Mạng 53 nút cũng <b>theo trục chính</b>: bỏ đường dân cư (OSM highway.residential).</li>
  <li>Bài 2007 dùng lịch <b>fixed-time có phối hợp</b> (green wave): cycle, thời gian xanh, bandwidth, tính trước từ số đếm.</li></ul></div>
 <div class="col panel stop"><h3>Điều em không lấy</h3><ul class="small" style="margin-left:18px">
  <li><b>Không lấy số liệu.</b> Em mới đọc tên bài và tóm tắt; chưa có bài đầy đủ và dữ liệu đếm xe.</li>
  <li>Fixed-time baseline của luận văn <b>không có offset</b>, nên không phải green wave.</li>
  <li>RL ở đây là <b>adaptive</b>: phản ứng theo hàng chờ thấy được, không theo lịch tính sẵn.</li></ul></div>
</div>''', secs=0, kind="backup", source="https://scv.udn.vn/trantrungviet/BBao/5864 (chỉ tóm tắt; chưa có toàn văn)", notes=N(
    "Trước paper 2025, em nêu một nghiên cứu cũ ở Đà Nẵng. Năm 2007, tác giả Trần Trung Việt và TS. Phan Cao Thọ đăng trên Tạp chí Cầu Đường Việt Nam nghiên cứu điều khiển “làn sóng xanh”, tức green wave, cho các trục chính ở Đà Nẵng. Bài dùng số xe đếm thực tế trên các trục có đèn, và có phần mềm Green Wave Design. "
    "Em lấy ý tưởng, không lấy số liệu: ở Đà Nẵng, bài toán đèn nằm trên trục chính và bắt đầu từ số xe đếm thực tế. Mạng 53 nút của em cũng theo trục chính, vì đã bỏ đường dân cư. Nguồn tiếp theo, paper 2025, là một nút có số đếm công bố. "
    "Hai giới hạn: em mới đọc tên bài và tóm tắt, nên không dùng số nào; và fixed-time baseline của em không có offset, nên không phải green wave. Green wave sẽ là một baseline mạnh hơn mà em chưa thử.",
    ["2007: trục chính + đếm xe + green wave", "Chỉ lấy ý tưởng, không lấy số (mới đọc tóm tắt)", "Fixed-time baseline ≠ green wave"],
    ["Không nói luận văn dùng dữ liệu của bài 2007.", "Không khẳng định liên hệ giữa tác giả bài 2007 và bài 2025."],
    [("Em có so với green wave không?", "Không. Fixed-time baseline là lịch không phối hợp, không có offset (103 giây theo paper trong SUMO, tune trên validation trong CityFlow). Green wave sẽ là baseline mạnh hơn mà em chưa thử; đây là một giới hạn."),
     ("Vì sao trích bài năm 2007?", "Bài cho thấy thực tế ở Đà Nẵng: đèn trên trục chính được tính trước từ số đếm. Luận văn hỏi adaptive controller có làm tốt hơn lịch cố định trong bối cảnh đó không.")]))

tiers = [("Nguồn công bố", "PDF: lịch đèn, bảng rẽ, biểu đồ camera", "“Theo paper, trang / hình / bảng …”", C["ink"]),
         ("Lấy từ nguồn", "Số đọc xấp xỉ, lưu trong CSV", "“Số đếm đọc xấp xỉ từ biểu đồ …”", C["go"]),
         ("Giả định để dựng mô phỏng", "Mở rộng ra cả nút, route, loại xe", "“Giả định dùng để tạo scenario …”", C["caution"]),
         ("Kết quả mô phỏng", "Queue integral, completion, reward", "“Kết quả trong mô phỏng với config …”", C["stop"])]
th = "".join(f'''<div style="display:flex;gap:16px;margin-bottom:14px"><div class="hero" style="font-size:40px;color:{c};width:34px">{i+1}</div>
<div><div style="font-weight:850;font-size:19px;color:{C["ink"]}">{n}</div><div class="xs">{e}</div><div class="xs muted"><i>{s}</i></div></div></div>''' for i, (n, e, s, c) in enumerate(tiers))
slide(B, "B12 · 48 dòng số liệu đọc từ biểu đồ, 4 mức tin cậy", f'''
<div class="row" style="gap:40px">
 <div class="col">
  <div class="row" style="gap:36px;margin-bottom:22px">{stat("48", "dòng = 4 luồng × 12 giờ")}{stat("192", "số xấp xỉ cho ô tô, xe máy, xe tải, xe buýt")}{stat("1 ngày", "1/4/2025, không nói được theo mùa")}</div>
  <div class="row" style="gap:14px;margin-bottom:20px">
   <div class="panel go col" style="padding:14px 18px">{stat("1.395", "xe/giờ lúc 13:00 → test normal", "go", 34)}</div>
   <div class="panel stop col" style="padding:14px 18px">{stat("2.330", "xe/giờ lúc 08:00 → AM, cũng dùng để train", "stop", 34)}</div>
   <div class="panel caution col" style="padding:14px 18px">{stat("2.400", "xe/giờ lúc 17:00 → test PM", "caution", 34)}</div>
  </div>
  <div class="note" style="font-size:15.5px">Dung sai ±15 / ±30 xe/giờ là <b>sai số đọc</b> do em đặt. SHA-256 khớp chỉ chứng minh file không bị đổi, <b>không</b> chứng minh số đếm đúng với giao thông thật.</div>
 </div>
 <div style="width:440px;flex:none"><h3>4 mức tin cậy</h3>{th}</div>
</div>''', secs=0, kind="backup", source="datasets/danang_published/phan2025_camera_hourly_digitized.csv · docs/research/danang-data-claim-audit.md", notes=N(
    "Từ Hình 17 và 18 em đọc ra CSV: 4 luồng nhân 12 giờ là 48 dòng; mỗi dòng có 4 loại xe, nên có 192 số, tất cả trong một ngày. "
    "Ba số màu là ba mức demand: 1.395 lúc 13:00 là normal, 2.330 lúc 08:00 là AM, và 2.400 lúc 17:00 là PM. Đây là tổng trên bốn đường đo, không phải cả nút. "
    "Em chia bốn mức tin cậy: nguồn công bố, số lấy từ nguồn, giả định để dựng mô phỏng, và kết quả mô phỏng. Mỗi mức có cách nói riêng. "
    "Dung sai ±15 và ±30 là sai số đọc, và mã hash chỉ chứng minh file không bị sửa.",
    ["48 dòng · 192 số · 1 ngày", "1.395 / 2.330 / 2.400 = normal / AM / PM", "4 mức: nguồn → lấy từ nguồn → giả định → kết quả"],
    ["Không nói 2.400 là tổng lưu lượng của cả nút."]))

slide(B, "B13 · Chia dữ liệu và ba loại seed", f'''
<div class="row" style="gap:40px">
 <div style="flex:1.2">
  {table(["CityFlow", "Demand seed", "Simulation seed", "Số scenario"], [["Train", "11, 12, 13", "111, 112, 113", "3 regime × 3 = 9"], ["Validation", "31, 32", "131, 132", "3 regime × 2 = 6"], ["Test", "101–105", "201–205", "3 regime × 5 = <b>15</b>"]], align=["", "c", "c", ""])}
  <p class="small" style="margin-top:16px"><b>SUMO:</b> train trên AM (demand 11 / sim 11), validation trên AM (demand 31 / sim 31), <b>giống nhau cho mọi training seed</b>. Test trên 15 scenario.</p>
  <div class="note" style="margin-top:14px;font-size:15.5px">Train / validation / test dùng route family khác nhau, nhưng route vẫn có thể đi qua cùng đường, cùng nút. Đây <b>không</b> phải test trên một thành phố mới.</div>
 </div>
 <div class="col">
  <div class="rule-l go" style="margin-bottom:16px"><b style="font-size:20px">Demand seed</b><div class="small">Chọn route, loại xe, giờ xuất phát.</div></div>
  <div class="rule-l pressure" style="margin-bottom:16px"><b style="font-size:20px">Simulation seed</b><div class="small">Phần ngẫu nhiên bên trong simulator.</div></div>
  <div class="rule-l stop" style="margin-bottom:20px"><b style="font-size:20px">Training seed</b><div class="small">Khởi tạo weight, exploration, lấy mẫu replay buffer.</div></div>
  <div class="panel go small">Mọi controller dùng cùng demand seed và simulation seed → so sánh <b>paired</b>. Nhiều training seed cho biết <b>kết quả train dao động bao nhiêu</b>.</div>
 </div>
</div>''', secs=0, kind="backup", source="results/haichau_network_v2/experiment-manifest.json · results/danang_protocol_v1/experiment-manifest.json", notes=N(
    "Có ba loại seed: demand seed quyết định demand, simulation seed quyết định phần ngẫu nhiên trong simulator, training seed quyết định quá trình train. "
    "Trong CityFlow, train có 9 scenario, validation 6, test 15, mỗi regime 5. Mọi controller chạy trên cùng cặp demand seed và simulation seed, nên so sánh là paired. "
    "Trong SUMO, train và validation đều là AM, giống nhau cho cả năm training seed. "
    "Lưu ý: chạy một checkpoint trên nhiều scenario không phải là nhiều model độc lập, và route family khác nhau không có nghĩa là thành phố mới.",
    ["3 seed: demand · simulation · training", "Test = 15 scenario (3 × 5)", "Paired ≠ model độc lập"]))

clocks = "".join(f'<div style="display:flex;gap:16px;align-items:baseline;margin:8px 0"><div class="hero" style="font-size:34px;width:110px;color:{c}">{t}</div><div class="small"><b>{n}</b><br>{d}</div></div>'
                 for t, n, d, c in [("1 giây", "Simulation step", "metric được cộng mỗi giây", C["base"]), ("10 giây", "Decision step", "SUMO chọn pha; CityFlow chạy một lệnh", C["go"]),
                                    ("300 giây", "Macro", "Residual CityFlow chọn một macro cho cả block", C["stop"])])
slide(B, "B14 · RL học từ kết quả của action", f'''
<div class="row" style="gap:40px">
 <div style="width:500px;flex:none">{rl_loop()}<p class="small" style="margin-top:10px">Không ai chỉ sẵn action nào đúng. Reward là <b>chi phí âm</b>, nên <b>ít âm hơn là tốt hơn</b>.</p></div>
 <div class="col">
  <h3>Q-value</h3>
  <div class="eq">return = r<sub>t</sub> + γ r<sub>t+1</sub> + γ² r<sub>t+2</sub> + …
<span class="k">greedy action</span> = argmax<sub>a</sub> Q(o, a)</div>
  <p class="small" style="margin:10px 0 20px">Q(o, a) dự đoán tổng reward tương lai (có discount) nếu chọn a khi thấy o. Q cao hơn = chi phí dự kiến thấp hơn. Q <b>không</b> phải số xe được đi qua.</p>
  <h3>Ba loại thời gian cần tách riêng</h3>{clocks}
  <div class="xs muted">Một lần update là một lần sửa weight, không phải một giây mô phỏng.</div>
 </div>
</div>''', secs=0, kind="backup", notes=N(
    "Vòng RL: agent nhận observation, chọn action, simulator chạy rồi trả reward và observation mới. Khi train, các transition được lưu vào replay buffer để update model. "
    "Ở đây reward là âm của hàng chờ, nên ít âm hơn là tốt hơn. Q-value dự đoán tổng reward tương lai của một action; greedy policy chọn Q lớn nhất. "
    "Có ba loại thời gian: mô phỏng chạy từng giây và metric cộng mỗi giây; mỗi 10 giây SUMO chọn pha; mỗi 300 giây residual CityFlow quyết định. Tách rõ ba cái này thì đọc tham số không bị nhầm.",
    ["Reward âm = chi phí", "Q = reward tương lai dự kiến, không phải số xe", "1 giây · 10 giây · 300 giây"]))

slide(B, "B15 · Double DQN và dueling sửa hai chỗ khác nhau", f'''
<div class="row" style="gap:40px">
 <div class="col">
  <h3>Double DQN đổi <span class="go">target</span></h3>
  <p class="small">DQN thường dùng cùng một phép max để vừa <b>chọn</b> vừa <b>chấm điểm</b> action kế tiếp, nên Q hay bị ước lượng quá cao (overestimation). Double DQN tách hai việc này ra.</p>
  <div class="eq" style="margin:10px 0"><span class="c"># online network chọn</span>
a* = argmax<sub>a</sub> Q<sub>online</sub>(o′, a)
<span class="c"># target network chấm điểm</span>
y  = r + (1 − done) · γ · Q<sub>target</sub>(o′, a*)</div>
  {table(["Ví dụ", "Action A", "Action B"], [["Q online", "<b>−4</b>, được chọn", "−5"], ["Q target", "<b>−6</b>, được dùng", "−3"]], cls="t tight", align=["", "c", "c"])}
  <div class="xs muted" style="margin-top:6px">Target network được copy từ online network sau một số update. van Hasselt, Guez và Silver (2016).</div>
 </div>
 <div class="col">
  <h3>Dueling đổi <span class="pressure">output layer</span></h3>
  <div class="eq" style="margin:4px 0 12px">Q(o, a) = V(o) + A(o, a) − mean<sub>b</sub> A(o, b)</div>
  <ul class="dots pressure small"><li><b>V(o)</b>: state này tốt đến đâu</li><li><b>A(o, a)</b>: action này hơn hay kém trung bình bao nhiêu</li><li>Trừ mean để V và A tách ra rõ ràng</li><li>Có ích khi nhiều action có giá trị gần nhau; đây là lý do thiết kế, không chắc chắn luôn tốt hơn</li></ul>
  <div class="xs muted" style="margin-top:6px">Wang và cộng sự, ICML 2016.</div>
 </div>
</div>
<div class="row" style="gap:20px;margin-top:22px">
 <div class="panel go col"><b>SUMO</b> dùng <b>cả hai</b>: Double target, dueling head, 3-step return.</div>
 <div class="panel pressure col"><b>Residual CityFlow</b> chỉ dùng <b>Double</b>, output một số.</div>
</div>''', secs=0, kind="backup", notes=N(
    "Double và dueling hay bị nhầm. Double DQN sửa target: online network chọn action tốt nhất kế tiếp, target network chấm điểm action đó. "
    "Ví dụ: online network cho A = −4, B = −5 nên chọn A; target network cho A = −6, B = −3; Double DQN dùng −6 của A, dù target network thích B hơn. Cách này giảm overestimation. "
    "Dueling sửa output layer: tách V của state và A của từng action, rồi ghép lại thành Q = V + A trừ mean của A. "
    "Model SUMO dùng cả hai. Model CityFlow chỉ dùng Double, mỗi macro ra một số.",
    ["Double = online chọn, target chấm", "Dueling = V + A − mean A", "SUMO cả hai · CityFlow chỉ Double"],
    ["Không nói dueling giảm overestimation; đó là việc của Double."],
    [("Dueling có giảm overestimation không?", "Không trực tiếp. Double tách việc chọn và chấm trong target; dueling tách V và A trong kiến trúc.")]))

slide(B, "B16 · Training SUMO: 5 seed × 30 episode, chọn checkpoint trên validation", f'''
<div class="row" style="gap:34px">
 <div class="col">
  <h3>Reward và 3-step target</h3>
  <div class="eq" style="font-size:14.5px">r(t) = −0,01 × [hàng chờ(t<sub>cuối</sub>) + pending(t<sub>cuối</sub>)]
R<sub>3</sub> = r<sub>t</sub> + γ r<sub>t+1</sub> + γ² r<sub>t+2</sub>
y  = R<sub>3</sub> + (1 − done) · γ³ · Q<sub>target</sub>(o<sub>t+3</sub>, a*)</div>
  <p class="xs" style="margin:6px 0 18px">γ = 0,99 <b>cho mỗi step 10 giây</b>. Reward lấy ở cuối mỗi step; metric chính cộng mỗi giây. Hai cái cùng hướng nhưng không giống hệt.</p>
  <div class="row" style="gap:26px;margin-bottom:18px">{stat("360", "quyết định mỗi episode")}{stat("10.800", "quyết định mỗi seed")}{stat("120", "lượt test chính = 75 RL + 45 baseline")}</div>
  <div class="panel small" style="padding:12px 16px"><b>Hyperparameter.</b> learning rate 0,0003, Adam, Huber δ = 1, gradient clipping 10, replay buffer 50.000, batch 64, bắt đầu học sau 256, target sync mỗi 200 update, ε từ 1,0 xuống 0,05 trong 5.000 quyết định (khoảng episode 14).</div>
 </div>
 <div style="width:470px;flex:none">
  <h3>Với mỗi training seed 11–15</h3>
  {vchain(["Khởi tạo online network, copy sang target, tạo replay buffer", "30 episode × 3.600 giây trên <b>AM train</b> (demand 11 / sim 11)", "Mỗi 10 giây: ε-greedy, chạy, lưu 3-step transition, một update",
           "<span style='color:#137257'>Mỗi 5 episode: chạy greedy trên <b>AM validation</b> (demand 31 / sim 31), giữ bản tốt nhất</span>", "<b>Chạy checkpoint tốt nhất trên 15 scenario test</b>, không update weight"])}
  <div class="note" style="margin-top:12px;font-size:15px">Chỉ train trên <b>AM</b>, test trên normal, AM và PM.</div>
 </div>
</div>''', secs=0, kind="backup", source="scripts/train_danang_sumo.py · src/traffic_rl/train/trainer.py · configs/danang_pilot.yaml", notes=N(
    "Reward là âm của hàng chờ cộng pending ở cuối mỗi step 10 giây, nhân 0,01. Target dùng 3-step return: cộng ba reward có discount, rồi cộng giá trị Double từ target network. "
    "Mỗi training seed từ 11 đến 15 train 30 episode, mỗi episode một giờ trên cùng scenario AM: 360 quyết định mỗi episode, 10.800 mỗi seed. ε giảm từ 1 xuống 0,05 trong 5.000 quyết định, khoảng episode 14. "
    "Mỗi 5 episode, model chạy greedy trên AM validation và giữ checkpoint có hàng chờ trung bình thấp nhất. Checkpoint đó chạy trên 15 scenario test: tổng 120 lượt chính, 75 của RL và 45 của baseline.",
    ["30 episode × 5 seed · validation mỗi 5", "Chỉ train AM · test 3 regime", "120 lượt = 75 RL + 45 baseline"],
    ["Không nói mỗi seed train trên dữ liệu khác nhau; train và validation giống nhau."],
    [("30 episode đã hội tụ chưa?", "30 episode là giới hạn em đặt; validation chọn checkpoint tốt nhất trong đó, chưa chứng minh hội tụ.")]))

vec27 = '<div style="display:flex;gap:3px">' + "".join(f'<div style="flex:1;height:34px;border-radius:4px;background:{C["go"]}"></div>' for _ in range(12)) + '<div style="width:10px"></div>' + \
    "".join(f'<div style="flex:1;height:34px;border-radius:4px;background:{C["phaseB"]}"></div>' for _ in range(12)) + '<div style="width:10px"></div>' + \
    "".join(f'<div style="flex:1;height:34px;border-radius:4px;background:{C["stop"]}"></div>' for _ in range(3)) + "</div>"
feats = ["hàng chờ vào, trung bình", "hàng chờ vào, lớn nhất", "xe đang chạy vào, trung bình", "hàng chờ ra, trung bình", "chỗ trống phía ra (40 − số xe)", "pressure (vào − ra, trung bình)",
         "có phải pha đang xanh không", "đã xanh bao lâu (giây / 20)", "hàng chờ upstream, trung bình", "hàng chờ downstream, trung bình", "bao lâu chưa được xanh (giây / 20)", "số movement"]
fh = "".join(f'<div class="xs" style="padding:2px 0"><b class="go">{i+1}</b>&nbsp; {f}</div>' for i, f in enumerate(feats))
slide(B, "B17 · 27 feature mỗi macro, một shared MLP cho 53 nút", f'''
<div class="panel" style="padding:14px 18px"><h3>Một macro candidate = 12 + 12 + 3</h3>{vec27}
 <div style="display:flex;margin-top:7px;font-size:15px;font-weight:800"><div style="flex:12" class="go">12 feature pha trước (source)</div><div style="flex:12;color:{C["phaseB"]}">12 feature pha sau (target)</div><div style="flex:3;text-align:right;white-space:nowrap" class="stop">3 mô tả</div></div></div>
<div class="row" style="gap:30px;margin-top:18px">
 <div class="col"><h3>12 feature của một pha</h3><div style="columns:2;column-gap:18px">{fh}</div>
  <div class="xs muted" style="margin-top:8px">3 mô tả: vị trí lần đổi pha = step / 30, shift = ±1, có phải macro 0. Macro 0 lấy trung bình feature của các pha hợp lệ, với mô tả [0, 0, 1].</div>
  <div class="note go" style="margin-top:12px;font-size:15px"><b>Vì sao output chỉ một số?</b> Số macro hợp lệ khác nhau theo nút và theo block. Dùng một MLP chấm điểm <b>từng candidate</b>, rồi dùng mask, thì chạy được với mọi số lượng action.</div></div>
 <div style="width:540px;flex:none"><div class="panel" style="padding:10px 14px">{mlp("27", w=520, h=200)}
  <div class="eq" style="font-size:14px">(27·64+64)+(64·64+64)+(64·1+1) = <span class="a">6.017</span> tham số</div>
  <div class="xs" style="margin-top:8px">Một MLP chấm mọi macro ở mọi nút, rồi mask và argmax. <b>Không</b> dueling, <b>không</b> GNN, <b>không</b> attention: thông tin nút kề chỉ đi vào dưới dạng feature.</div></div></div>
</div>''', secs=0, kind="backup", source="src/traffic_rl/sim/phase_encoder.py · src/traffic_rl/agents/phase_ddqn.py · src/traffic_rl/agents/schedule_residual.py", notes=N(
    "Mỗi lần sửa liên quan hai pha: pha trước lúc đổi là source, pha sau là target. Mỗi pha có 12 feature: hàng chờ vào trung bình và lớn nhất, xe đang chạy vào, hàng chờ ra, chỗ trống, pressure, có phải pha đang xanh, đã xanh bao lâu, hàng chờ upstream và downstream, bao lâu chưa được xanh, và số movement. "
    "Thêm ba số: lần đổi pha nằm ở đâu trong block, đổi sớm hay muộn, và có phải macro 0 không. Vậy 12 + 12 + 3 = 27. "
    "Một MLP 27 → 64 → 64 → 1, 6.017 tham số, chấm mọi candidate. 53 nút dùng chung weight, nên thêm nút không thêm weight. "
    "Thông tin nút kề chỉ là feature tóm tắt; đây không phải GNN hay communication được học.",
    ["27 = 12 source + 12 target + 3 mô tả", "27 → 64 → 64 → 1 · 6.017 tham số", "Shared weight ≠ GNN"],
    ["Không gọi đây là multi-agent communication hay GNN."],
    [("53 agent có giao tiếp không?", "Chúng thấy hàng chờ upstream/downstream (tóm tắt), dùng chung weight và cùng một reward cho cả mạng; đó không phải communication được học.")]))

slide(B, "B18 · Training residual: reward cả mạng, 12 episode, 6 scenario peak", f'''
<div class="row" style="gap:34px">
 <div class="col">
  <h3>Reward của một macro, tính trên cả mạng</h3>
  <div class="eq" style="font-size:14.5px">r<sub>raw</sub> = −[I(t + 300) − I(t)]      <span class="c">xe-giây, hàng chờ + pending</span>
r     = r<sub>raw</sub> / 100.000</div>
  <p class="xs" style="margin:6px 0 16px">Ví dụ: trung bình 500 xe chờ trong 300 giây = 150.000 xe-giây → r = −1,5. Cùng reward này dùng cho cả 53 transition, và <b>không</b> trừ đi chi phí của fixed-time.</p>
  <h3>Target theo thời gian (SMDP)</h3>
  <div class="eq" style="font-size:14.5px">y = r + (1 − done) · γ<sup>Δt/300</sup> · Q<sub>target</sub>(o′, a*)</div>
  <p class="xs" style="margin:6px 0 16px">γ = 0,99 <b>cho mỗi 300 giây</b>, khác SUMO là 0,99 cho mỗi 10 giây.</p>
  <div class="panel caution small" style="padding:12px 16px"><b>Khởi tạo.</b> Output layer W3 và b3 bắt đầu bằng 0, nên lúc đầu mọi Q bằng nhau và greedy policy chọn macro 0. <b>ε cố định = 0,15</b> để thử các macro khác. Không dùng imitation loss.</div>
 </div>
 <div style="width:480px;flex:none">
  <div class="row" style="gap:22px;margin-bottom:16px">{stat("7.632", "transition mỗi seed, AM 3.816 + PM 3.816", "go")}{stat("1.152", "update = 12 × 12 × 8", "ink")}</div>
  {table(["Mỗi training seed", "Giá trị"], [["Episode", "12 × 3.600 giây"], ["Block mỗi episode", "12"], ["Transition mỗi block", "53"], ["Batch, replay buffer, bắt đầu học", "128; 20.000; ≥ 53"],
       ["Target sync", "mỗi 64 update (8 block)"], ["Validation, checkpoint", "mỗi 4 episode → ep 4, 8, 12"]], cls="t tight")}
  <div class="note stop" style="margin-top:12px;font-size:15px">Có 9 scenario train, nhưng chỉ <b>6 scenario peak</b> (3 AM + 3 PM) dùng để train residual, mỗi cái hai lần. 7.632 transition <b>rất giống nhau</b>, không phải 7.632 thí nghiệm.</div>
 </div>
</div>''', secs=0, kind="backup", source="src/traffic_rl/train/schedule_residual_trainer.py · docs/research/evidence-snapshot-2026-09-23/seed14-resolved-config.json", notes=N(
    "Reward của một macro là âm của phần queue integral cả mạng tăng thêm trong 300 giây, có tính pending, rồi chia cho 100.000 để số không quá lớn. Ví dụ 500 xe chờ trung bình trong 300 giây là 150.000 xe-giây, reward là −1,5. "
    "Reward này là của cả mạng, giống nhau cho cả 53 transition, và không trừ chi phí của fixed-time. Chữ “residual” chỉ nói về action. "
    "Target tính theo thời gian của macro, γ là 0,99 cho mỗi 300 giây. Output bắt đầu bằng 0 nên lúc đầu model chọn macro 0, và ε cố định 0,15 để thử cái khác. "
    "Mỗi seed train 12 episode trên 6 scenario peak: 7.632 transition và 1.152 update. Mỗi 4 episode lưu một checkpoint và chạy validation; “step-4” nghĩa là sau episode 4.",
    ["Reward = −Δ(hàng chờ + pending) cả mạng / 100.000", "12 ep · 7.632 transition · 1.152 update", "step-4 = episode 4"],
    ["Không phải “8 update × 53 nút”: 8 update cho mỗi block của cả mạng."],
    [("Reward chung cho cả mạng có hạn chế gì?", "Đúng với mục tiêu chung, nhưng khó biết nút nào làm tốt (credit assignment). Local reward hoặc difference reward là việc làm sau.")]))

gates = ["Normal khớp fixed-time từng scenario, không lệch pha hay clock", "Regret hàng chờ trung bình của mỗi regime peak ≤ 0", "Regret peak trung bình ≤ −1%",
         "Completion và insertion mỗi scenario không giảm quá 2 điểm %", "Có macro đã học ở cả AM và PM, tại ≥ 2 nút", "0 lần đổi pha sai luật, 0 lệch anchor; ép macro 0 thì phải = fixed-time 25",
         "Checkpoint phản ứng khi feature giao thông thay đổi"]
seedcards = "".join(f'''<div class="col" style="text-align:center;padding:14px 4px;border-radius:12px;background:{"#DDF1E9" if ok else "#F8E1DE"}">
 <div class="xs muted">seed</div><div class="hero" style="font-size:44px;color:{C["go"] if ok else C["stop"]}">{s}</div>
 <div style="font-weight:850;font-size:15px;color:{C["go"] if ok else C["stop"]};margin-top:6px">{st}</div><div class="xs muted">{ep}</div></div>'''
                    for s, st, ep, ok in [("12", "được chọn", "episode 8", True), ("13", "bị loại", "ep 12, tham khảo", False), ("14", "được chọn", "episode 4", True),
                                          ("15", "được chọn", "episode 8", True), ("16", "bị loại", "ep 4, tham khảo", False)])
slide(B, "B19 · Train xong chưa chắc được chọn: selector trên validation", f'''
{chain([("Train xong", "có weight và log"), ("Selector V1 chọn", "một checkpoint đạt yêu cầu của seed đó"), ("Strict release check", "kiểm tra toàn bộ bằng chứng")])}
<div class="row" style="gap:34px;margin-top:22px">
 <div class="col"><h3>Selector V1 kiểm tra trên validation</h3><ul class="dots small">{"".join(f"<li>{g}</li>" for g in gates)}</ul>
  <div class="xs muted" style="margin-top:6px">Xếp theo regret peak trung bình; bằng nhau thì lấy checkpoint sớm hơn. Không cái nào qua thì <b>fail closed</b> (không chọn gì), không lấy cái ít tệ nhất.</div></div>
 <div style="width:560px;flex:none">
  <div class="row" style="gap:8px">{seedcards}</div>
  <div class="note stop" style="margin-top:16px;font-size:15.5px">Seed 13 và 16 bị loại. Kết quả test tốt về sau <b>không</b> đổi quyết định trên validation. Các gate là ngưỡng em tự đặt, không phải kiểm định thống kê.</div>
  <div class="note ink" style="margin-top:10px;font-size:15.5px">Strict check: <b>complete = false</b>, còn 14 release gate chưa qua (kiểm tra ngày 23/9).</div>
 </div>
</div>''', secs=0, kind="backup", source="configs/haichau_residual_final_selection_v1.yaml · docs/research/evidence-snapshot-2026-09-23/seed*-selection.json", notes=N(
    "Em tách ba bước: train xong, selector chọn, và strict release. Selector V1 chạy trên validation và kiểm tra: normal khớp fixed-time từng scenario; regret mỗi regime peak không dương và trung bình giảm ít nhất 1 phần trăm; completion và insertion không giảm quá 2 điểm phần trăm; có macro đã học ở cả AM và PM; và không bao giờ vi phạm contract. "
    "Không cái nào qua thì fail closed. Kết quả: seed 12, 14 và 15 được chọn; 13 và 16 bị loại. Em vẫn báo hai seed đó để tham khảo, nhưng không đổi quyết định. "
    "Strict release chưa xong, còn 14 gate. Em nói thẳng điều này.",
    ["3 bước: train xong → được chọn → release", "Seed 12 / 14 / 15 chọn · 13 / 16 loại", "Fail closed · strict release chưa xong"]))

slide(B, "B20 · Đọc kết quả SUMO: giả thuyết, ablation và an toàn trong mô phỏng", f'''
<div class="row" style="gap:34px">
 <div style="width:600px;flex:none"><img class="fig" src="{img("curves")}" style="width:600px;height:340px;object-fit:contain">
  <div class="cap">Hàng chờ trung bình trên validation theo episode, năm training seed. Checkpoint tốt nhất có thể đến trước episode cuối; seed 13 dao động mạnh.</div></div>
 <div class="col">
  <div class="rule-l stop" style="margin-bottom:14px"><b>Vì sao normal tệ: chỉ là giả thuyết.</b><div class="small">Chỉ train trên AM, nên có thể do distribution shift, overfitting hoặc thời điểm ra action. <b>Chưa</b> có ablation để chứng minh.</div></div>
  <div class="rule-l pressure" style="margin-bottom:14px"><b>Vì sao Max-Pressure thua ở đây.</b><div class="small">Chỉ thấy bốn luồng, và mỗi lần đổi pha mất 7 giây vàng trong step 10 giây. Điều này không có nghĩa là Max-Pressure sai.</div></div>
  <div class="rule-l caution" style="margin-bottom:14px"><b>Ablation seed 11.</b><div class="small">Validation tốt nhất: dqn_base ≈ 81,43, dueling_n3 ≈ 71,71. Dueling và n-step đổi <b>cùng lúc</b>, chỉ một seed, nên không biết cái nào giúp.</div></div>
  <div class="rule-l go"><b>An toàn trong mô phỏng.</b><div class="small">120 lượt chính: <b>0 collision, 0 emergency</b>. 120 lượt sensitivity: 0 collision, 4 emergency. Không phải chứng nhận an toàn ngoài đời.</div></div>
 </div>
</div>''', secs=0, kind="backup", source="results/danang_protocol_v1/summary/validation-learning-curves.png · paper/thesis_danang.tex, phần Kết quả", notes=N(
    "Đường validation cho thấy checkpoint tốt nhất không phải lúc nào cũng ở episode cuối, và seed 13 dao động mạnh. Vì vậy checkpoint được chọn trên validation. "
    "Normal có thể tệ hơn vì model chỉ train trên AM, nhưng đó là giả thuyết, chưa có ablation. Max-Pressure thua vì chỉ thấy bốn luồng và mỗi lần đổi pha mất 7 giây vàng. "
    "Ablation seed 11 cho thấy dueling_n3 tốt hơn model gốc trên validation, nhưng đổi hai thứ cùng lúc trên một seed, nên em không tách được cái nào giúp. "
    "Về an toàn trong mô phỏng: 120 lượt chính không có collision và không có emergency braking.",
    ["Checkpoint tốt nhất ≠ episode cuối", "MP thua: thấy ít + 7 giây vàng", "0 collision / 0 emergency trong 120 lượt"]))

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
        w = (width - 10 * (len(SECTIONS) - 1)) * d[name] / total
        segs.append(f'<div style="position:absolute;left:{x:.1f}px;top:0;width:{w:.1f}px;height:54px;background:{C["go"]};border-radius:4px;opacity:{0.55 + 0.45 * (i % 2)}"></div>')
        segs.append(f'<div style="position:absolute;left:{x:.1f}px;top:0;width:{w:.1f}px;height:54px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:24px;font-weight:850">{i + 1}</div>')
        x += w
        if i < len(SECTIONS) - 1:
            segs.append(f'<div style="position:absolute;left:{x+2:.1f}px;top:0;width:6px;height:54px;background:{C["caution"]};border-radius:2px"></div>')
            x += 10
    desc = "".join(f'<div style="display:flex;gap:14px;padding:7px 0;border-bottom:1px solid {C["rule"]}"><div style="width:150px;font-weight:850;color:{C["ink"]}">{i + 1}. {n}</div><div class="small">{t}</div></div>' for i, (n, t) in enumerate(parts))
    return f'''<div style="position:relative;height:78px">{"".join(segs)}</div>
<div class="row" style="gap:40px;margin-top:6px"><div style="flex:1.4">{desc}</div>
<div class="col"><div class="panel dark" style="font-size:20px;line-height:1.42"><b style="color:#6FD3B0">Một câu cần nhớ.</b> Lợi ích của RL phụ thuộc regime demand và baseline. Đây là bằng chứng mô phỏng, không phải hiệu quả ngoài đường.</div>
<div style="margin-top:16px" class="small"><div><span class="lamp" style="background:{C["go"]}"></span>tốt hơn, RL controller</div><div><span class="lamp" style="background:{C["caution"]}"></span>thận trọng, exploratory, chưa kết luận</div><div><span class="lamp" style="background:{C["stop"]}"></span>xấu hơn, giới hạn</div><div><span class="lamp" style="background:{C["base"]}"></span>fixed-time baseline &nbsp; <span class="lamp" style="background:{C["pressure"]}"></span>pressure baseline</div></div></div></div>'''


def mmss(sec):
    return f"{int(sec) // 60:02d}:{int(sec) % 60:02d}"


def slide_html(n, s):
    kind = s["kind"]
    if kind in ("cover", "divider", "closing"):
        rib = ribbon(s["section"]) if kind == "divider" else ""
        return f'<section class="slide dark">{rib}{s["body"]}</section>'
    cls = "slide backup" if kind == "backup" else "slide"
    rib = ribbon(s["section"]) if s["section"] != B else f'<div class="ribbon"><div class="lbl" style="left:0;top:0;color:{C["muted"]}">Phụ lục, dùng khi được hỏi</div></div>'
    num = s["title"].split(" · ")[0] if s["section"] == B else str(n)
    title = s["title"].split(" · ", 1)[-1] if s["section"] == B else s["title"]
    size = 34 if len(title) <= 46 else 30 if len(title) <= 62 else 26
    return f'''<section class="{cls}">{rib}<div class="title" style="font-size:{size}px">{title}</div><div class="content">{s["body"]}</div>
<div class="footer"><div class="src">{html.escape(s["source"]) if s["source"] else AUTHOR + ", bảo vệ luận văn"}</div><div class="num">{num}</div></div></section>'''


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
    head = '<!doctype html><html lang="vi"><head><meta charset="utf-8"><link rel="stylesheet" href="style.css">'
    (HERE / "deck.html").write_text(head + "<style>@page{size:1280px 720px;margin:0}</style></head><body>" + "".join(s["html"] for s in S) + "</body></html>", encoding="utf-8")

    def label(s):
        if s["kind"] == "cover":
            return "Bìa"
        if s["kind"] == "closing":
            return "Kết và cảm ơn"
        if s["kind"] == "divider":
            return "Slide chuyển phần"
        return s["title"]

    pages, cum, rows = [], 0, []
    for s in main:
        cum += s["secs"]
        s["cum"] = cum
        rows.append(f'<tr><td class="r">{s["n"]}</td><td>{html.escape(label(s))}</td><td class="c">{mmss(s["secs"])}</td><td class="c"><b>{mmss(cum)}</b></td></tr>')
    marks = {name: max(s["cum"] for s in main if s["section"] == name) for name in SECTIONS}
    pages.append(f'''<div class="npage"><h2>Kịch bản nói, bảo vệ 25 phút</h2>
<p style="font-size:14px;margin-bottom:8px">{len(main)} trang chính, nói <b>{mmss(total)}</b> cộng khoảng <b>{mmss(1500 - total)}</b> dự phòng. “Mốc” là thời điểm ở <b>cuối</b> mỗi trang; dùng khi tập.</p>
<table class="t timing"><tr><th class="r">#</th><th>Trang</th><th class="c">Thời lượng</th><th class="c">Mốc</th></tr>{"".join(rows)}</table>
<h4>Mốc khi đang nói</h4><p style="font-size:14.5px">Hết Bài toán ≈ <b>{mmss(marks["Bài toán"])}</b>, hết Dữ liệu ≈ <b>{mmss(marks["Dữ liệu"])}</b>, hết SUMO ≈ <b>{mmss(marks["SUMO"])}</b>, hết CityFlow ≈ <b>{mmss(marks["CityFlow"])}</b>, hết Kết quả ≈ <b>{mmss(marks["Kết quả"])}</b>. Nếu chậm hơn 1 phút: nói lướt slide camera và slide MC baseline (mỗi slide một câu), không cắt các câu giới hạn.</p>
<div class="nfoot"><span>{AUTHOR}, kịch bản nói</span><span>Trang 1</span></div></div>''')
    cheat = [("Nguồn", "Phan, Le và Nguyen (2025), MAKE 7(3):65; camera 1/4/2025; 4 luồng; 48 dòng / 192 giá trị"),
             ("Lịch công bố", "xanh 32 / 28 / 22 + vàng 3 × 7 = 103 giây"), ("Demand SUMO", "normal 1.395; AM 2.330 (train); PM 2.400 xe/giờ trên 4 đường đo"),
             ("Mạng", "53 đèn; 1.290 route family (644 / 323 / 323); 500 route mỗi scenario; xe máy 0,90"),
             ("Chia dữ liệu", "train 9, validation 6, test 15 scenario (3 regime × 5); demand seed 101–105, sim seed 201–205"),
             ("Model SUMO", "16 → 64 → 64 → V/A → 3 Q; 5.508 tham số; step 10 giây; vàng 7 giây; min green 20 giây; 3-step return"),
             ("Train SUMO", "30 episode × 5 seed (11–15); 360 quyết định mỗi episode; ε 1 → 0,05 trong 5.000; validation mỗi 5; 120 lượt test"),
             ("Model residual", "27 = 12 + 12 + 3 → 64 → 64 → 1; 6.017 tham số; dùng chung 53 nút; ±10 giây; macro 300 giây; tối đa 59 macro"),
             ("Train residual", "12 episode; 6 scenario peak; 7.632 transition; 1.152 update; ε 0,15; target sync mỗi 64; validation ep 4 / 8 / 12"),
             ("Selector", "seed 12 (ep 8), 14 (ep 4), 15 (ep 8) được chọn; 13 và 16 bị loại; strict release complete = false (14 gate)"),
             ("Kết quả SUMO", "normal 9,86 → 41,50 (+320,7%); AM 79,20 → 78,41 (−1,0%); PM 152,67 → 99,97 (−34,5%)"),
             ("MC baseline", "9.000 lượt = 1.000 realization × 3 regime × 3 baseline; fixed < MP 3.000/3.000; < MP trễ 2.999/3.000"),
             ("Kết quả mạng", "fixed 8.339,43; MP 6.347,00 (−23,89%); MP trễ 6.739,13 (−19,19%); residual 7.829,25 (−6,12%)"),
             ("Residual theo regime", "normal 0%; AM 3,48%; PM 10,39% pooled (8,86% per-scenario mean)"),
             ("Metric phụ", "completion +1,06 điểm; insertion +0,82 điểm; travel time +5,45 giây; spillback +65,20 làn-giây"),
             ("Gate chỉ PM", "trung bình 3,48%; khoảng 1,03–5,62%; 15 / 25 tốt hơn, 10 / 25 tệ hơn; POST-HOC"),
             ("Demo", "PM demand 105 / sim 205; seed 14 ep 4; nút 420249521; 18:05 = 1.085 giây; 14 vs 1 xe chờ")]
    ch = "".join(f"<tr><td><b>{a}</b></td><td>{b}</td></tr>" for a, b in cheat)
    pages.append(f'''<div class="npage"><h2>Số cần thuộc</h2><table class="t"><tr><th style="width:140px">Chủ đề</th><th>Số</th></tr>{ch}</table>
<h4>Năm câu không được nói</h4><ul style="padding-left:18px;font-size:14.5px"><li>“RL thắng fixed-time” mà không nêu regime và baseline.</li><li>“Mạng 53 nút là mọi đèn thật của Hải Châu.”</li>
<li>“3,48% là kết quả đã xác nhận” — đó là post-hoc.</li><li>“500 route là 500 xe” hoặc “18:05 là 6 giờ chiều”.</li><li>“Model dùng GNN hoặc multi-agent communication.”</li></ul>
<h4>Công thức cho mọi câu trả lời</h4><p style="font-size:14.5px"><b>Một kết luận</b> → <b>một giới hạn</b> → <b>chỉ vào bằng chứng</b> (slide phụ lục, file, số). Nếu chưa chắc: “Em chưa có thí nghiệm tách riêng yếu tố đó; cách kiểm là …”.</p>
<div class="nfoot"><span>{AUTHOR}, kịch bản nói</span><span>Trang 2</span></div></div>''')
    p = 3
    for s in S:
        nt = s["notes"]
        if s["section"] != B:
            head_l = f'Trang {s["n"]} · {html.escape(label(s))}'
            tm = f'⏱ {mmss(s["secs"])} · mốc {mmss(s["cum"])}'
        else:
            head_l = html.escape(s["title"])
            tm = "Phụ lục"
        keys = "".join(f"<div>{k}</div>" for k in nt.get("keys", []))
        avoid = "".join(f"<li>{a}</li>" for a in nt.get("avoid", []))
        qa_ = "".join(f'<div class="qa-item"><span class="q">H: {q}</span><br>Đ: {a}</div>' for q, a in nt.get("qa", []))
        pages.append(f'''<div class="npage"><div class="nhead"><div class="t">{head_l}</div><div class="tm">{tm}</div></div><div class="thumb">{s["html"]}</div>
<div class="nsec"><h5>Nhớ</h5><div class="keys">{keys}</div></div><div class="nsec"><h5>Nói gì</h5><p>{nt.get("say", "")}</p></div>
{f'<div class="nsec avoid"><h5>Tránh</h5><ul>{avoid}</ul></div>' if avoid else ""}{f'<div class="nsec qa"><h5>Nếu được hỏi</h5>{qa_}</div>' if qa_ else ""}
<div class="nfoot"><span>{AUTHOR}, kịch bản nói</span><span>Trang {p}</span></div></div>''')
        p += 1
    (HERE / "notes.html").write_text(head + "<style>@page{size:794px 1123px;margin:0}</style></head><body class=\"notes\">" + "".join(pages) + "</body></html>", encoding="utf-8")
    print(f"main pages: {len(main)}, backup: {len(S) - len(main)}, speaking time: {mmss(total)}")


if __name__ == "__main__":
    build()
