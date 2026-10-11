"""Build the 40-minute Vietnamese defense deck and speaker-notes handout.

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
    seeds = [("12", 2.36, "chọn, ep 8", True), ("13", 5.62, "chẩn đoán, ep 12", False),
             ("14", 5.11, "chọn, ep 4", True), ("15", 1.03, "chọn, ep 8", True), ("16", 3.27, "chẩn đoán, ep 4", False)]
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
    o.append(f'<text x="{left}" y="18" font-size="14" font-weight="800" fill="{C["ink"]}">Một block 300 giây của lịch tham chiếu (minh họa)</text>')
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
    o.append(f'<text x="{x(90)-8:.1f}" y="{by-14}" font-size="13" font-weight="800" text-anchor="end" fill="{C["stop"]}">sớm về 90 giây</text>')
    o.append(f'<text x="{x(110)+8:.1f}" y="{by-14}" font-size="13" font-weight="800" fill="#B97A00">trễ đến 110 giây</text>')
    o.append(f'<text x="{x(100):.1f}" y="{by+90}" font-size="13" font-weight="800" text-anchor="middle" fill="{C["ink"]}">ranh giới tham chiếu ở giây 100</text>')
    o.append(f'<rect x="{x(300)-5:.1f}" y="{by-12}" width="10" height="58" rx="2" fill="{C["stop"]}"/>')
    o.append(f'<text x="{x(300)-12:.1f}" y="{by+124}" font-size="13.5" font-weight="850" text-anchor="end" fill="{C["stop"]}">Ở giây 300, trạng thái đèn phải khớp neo</text>')
    o.append(f'<text x="{left}" y="{by+124}" font-size="13.5" fill="{C["muted"]}">30 nhịp 10 giây. Mỗi nút chọn một macro mỗi block.</text>')
    o.append("</svg>")
    return "".join(o)


def rl_loop():
    return f'''{svg_open(500, 300)}
<defs><marker id="ah" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{C['go']}"/></marker></defs>
<rect x="160" y="10" width="180" height="62" rx="12" fill="{C['asphalt']}"/>
<text x="250" y="37" font-size="17" font-weight="850" fill="#fff" text-anchor="middle">Tác nhân</text>
<text x="250" y="58" font-size="13" fill="#A8B8C4" text-anchor="middle">Q(o, a) rồi lấy argmax</text>
<rect x="160" y="228" width="180" height="62" rx="12" fill="#fff"/>
<text x="250" y="255" font-size="17" font-weight="850" fill="{C['ink']}" text-anchor="middle">Mô phỏng</text>
<text x="250" y="276" font-size="13" fill="{C['muted']}" text-anchor="middle">SUMO hoặc CityFlow</text>
<path d="M340,41 C455,41 455,259 345,259" fill="none" stroke="{C['go']}" stroke-width="3.5" marker-end="url(#ah)"/>
<text x="378" y="155" font-size="15" font-weight="850" fill="{C['go']}" text-anchor="middle">hành động</text>
<path d="M160,259 C45,259 45,41 155,41" fill="none" stroke="{C['go']}" stroke-width="3.5" marker-end="url(#ah)"/>
<text x="122" y="125" font-size="15" font-weight="850" fill="{C['go']}" text-anchor="middle">quan sát mới</text>
<text x="122" y="188" font-size="15" font-weight="850" fill="{C['stop']}" text-anchor="middle">thưởng</text>
<rect x="185" y="124" width="130" height="52" rx="10" fill="#FBEFD3"/>
<text x="250" y="147" font-size="14" font-weight="800" fill="{C['ink']}" text-anchor="middle">Bộ nhớ phát lại</text>
<text x="250" y="165" font-size="12" fill="{C['muted']}" text-anchor="middle">dùng khi huấn luyện</text>
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
        o.append(f'<text x="464" y="226" font-size="13.5" font-weight="850" fill="{C["go"]}" text-anchor="middle">3 giá trị Q</text>')
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
SECTIONS = ["Vì sao", "Dữ liệu", "Cơ sở RL", "SUMO", "CityFlow", "Kết quả", "Kết luận"]
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
slide("Vì sao", "", f'''
<div style="position:absolute;right:0;top:0">{cover_art()}</div>
<div style="position:absolute;left:72px;top:74px;font-size:17px;font-weight:700;color:#6FD3B0">Bảo vệ luận văn thạc sĩ kỹ thuật phần mềm</div>
<div style="position:absolute;left:72px;top:118px;width:660px;font-size:46px;line-height:1.08;font-weight:850;color:#fff;letter-spacing:-.02em">Học tăng cường cho điều khiển đèn giao thông Đà Nẵng, có kiểm soát bằng chứng</div>
<div style="position:absolute;left:72px;top:340px;width:620px;font-size:22px;line-height:1.4;color:#B8C7D2">Từ một nút có dữ liệu công bố trong SUMO đến 53 nút có đèn ở Hải Châu trong CityFlow</div>
<div style="position:absolute;left:72px;top:470px;font-size:14px;color:#7E93A3">Học viên</div>
<div style="position:absolute;left:72px;top:492px;font-size:27px;font-weight:850;color:#fff">{AUTHOR}</div>
<div style="position:absolute;left:380px;top:470px;font-size:14px;color:#7E93A3">Giảng viên hướng dẫn</div>
<div style="position:absolute;left:380px;top:492px;font-size:19px;font-weight:650;color:#fff;line-height:1.45">Dr. Le Van Minh</div>
<div style="position:absolute;left:72px;top:640px;font-size:15px;color:#7E93A3">FPT University, Đà Nẵng, 2026</div>
''', secs=30, kind="cover", notes=N(
    "Kính thưa Hội đồng, em là Lương Quang Khang. Hôm nay em trình bày luận văn về học tăng cường cho điều khiển đèn giao thông tại Đà Nẵng. "
    "Luận văn có hai tầng thí nghiệm: một nút giao có dữ liệu công bố, mô phỏng bằng SUMO, và một mạng 53 nút có đèn ở Hải Châu, mô phỏng bằng CityFlow. "
    "Chữ “có kiểm soát bằng chứng” là trọng tâm: em báo từng con số cùng với nguồn của nó và mức được phép kết luận.",
    ["Hai tầng: 1 nút SUMO, 53 nút CityFlow", "Trọng tâm: bằng chứng truy được", "Nói chậm, nhìn Hội đồng"],
    ["Không mở đầu bằng lời hứa RL luôn thắng."]))

# ================================================================== 02 roadmap
parts = [("Vì sao", "Bài toán, ba câu hỏi nghiên cứu, thiết kế hai tầng"), ("Dữ liệu", "Điểm xuất phát 2007, nguồn công bố, tầng tin cậy, nhu cầu, seed"),
         ("Cơ sở RL", "Giá trị Q, Double DQN, đầu ra dueling"), ("SUMO", "Trạng thái 16 số, huấn luyện, chỉ số và baseline"),
         ("CityFlow", "Residual lịch, neo, 27 đặc trưng, bộ chọn"), ("Kết quả", "Theo chế độ, baseline mạnh, cổng nhiều seed"),
         ("Kết luận", "Demo, câu được nói, đóng góp, bước tiếp")]
ROADMAP_SLOT = len(S)
slide("Vì sao", "Nội dung em trình bày", "__ROADMAP__", secs=40, notes=N(
    "Em trình bày bảy phần. Em bắt đầu từ bài toán và ba câu hỏi nghiên cứu, rồi dữ liệu đến từ đâu và thành mô phỏng thế nào. "
    "Sau một phần ngắn về cách học, em giải thích hai mô hình: một nút trong SUMO và 53 nút trong CityFlow. "
    "Phần kết quả cho thấy chỗ học có ích và chỗ học gây hại, rồi một đoạn demo và kết luận. "
    "Nếu chỉ nhớ một câu: lợi ích phụ thuộc chế độ nhu cầu và baseline, và đây là bằng chứng mô phỏng.",
    ["Đi qua bảy phần một lần", "Một câu: phụ thuộc chế độ và baseline", "Không giải thích thanh xanh là chu kỳ đèn"],
    ["Không đọc thời lượng, và không nói bài nói giống một chu kỳ đèn."]))

# ================================================================== 03 problem
slide("Vì sao", "Lịch cố định lặp cả ngày, nhu cầu thì không", f'''
<div class="row" style="gap:34px">
 <div style="width:680px;flex:none">{cycle_vs_demand()}
  <div class="row" style="gap:10px;margin-top:4px">
   <span class="tag go">Xanh 1 · 32 giây</span><span class="tag" style="background:#DCE6F0;color:#2F557A">Xanh 2 · 28 giây</span><span class="tag stop">Xanh 3 · 22 giây</span><span class="tag caution">3 lần vàng 7 giây</span><span class="tag dark">chu kỳ 103 giây</span></div>
 </div>
 <div class="col">
  <p class="lead" style="margin-bottom:18px">Bộ điều khiển thích nghi quan sát giao thông và đổi quyết định đèn để giảm tổng hàng chờ. Học tăng cường học quy tắc đó từ <b>hệ quả</b> của hành động trong mô phỏng.</p>
  <h3>Vì sao khó</h3>
  <div class="rule-l stop" style="margin-bottom:10px"><b class="stop">Tác động đến muộn.</b> Đổi đèn lúc này làm hàng xe ngắn lại vài giây sau và lan sang nút kế.</div>
  <div class="rule-l stop" style="margin-bottom:10px"><b class="stop">Lợi ích đối nghịch.</b> Thông một nút có thể đẩy xe vào đoạn đường phía sau đã đầy.</div>
  <div class="rule-l stop"><b class="stop">Bằng chứng mỏng.</b> Camera công bố chỉ có bốn luồng tại một nút, trong một ngày.</div>
 </div>
</div>''', secs=75, source="Lịch đèn: Phan, Le và Nguyen (2025), tr. 7 và Hình 4 tr. 8 · tổng camera: datasets/danang_published/phan2025_camera_hourly_digitized.csv", notes=N(
    "Lịch cố định chia thời gian xanh theo một chu kỳ lặp. Ở nút nghiên cứu, lịch công bố là 32, 28 và 22 giây xanh cộng ba lần vàng 7 giây, tổng 103 giây. "
    "Biểu đồ cho thấy vấn đề: lưu lượng camera đọc được dao động từ khoảng 1.250 đến khoảng 2.500 xe mỗi giờ trong ngày, nhưng cùng một lịch 103 giây cứ lặp ở dưới. "
    "Bộ điều khiển thích nghi quan sát giao thông và đổi quyết định để giảm tổng hàng chờ. Khó ở ba điểm: hiệu quả đến muộn, lợi ích giữa các nút có thể trái nhau, và dữ liệu hiện trường mỏng. "
    "Câu hỏi đúng không phải “học tăng cường có tốt không?”, mà là lúc nào có ích, so với baseline nào, và bằng chứng mạnh đến đâu.",
    ["103 giây = 32 + 28 + 22 + 3 × 7", "Đến muộn · đối nghịch · bằng chứng mỏng", "Khi nào / so với gì / chắc đến đâu"]))

# ================================================================== 04 RQs
rq = [("CH1", "RL có giảm hàng chờ tại nút có dữ liệu công bố không?", "SUMO, ba chế độ, năm seed học", "Một nút mô phỏng với hình học, nhu cầu và giả định đã nêu", C["go"]),
      ("CH2", "Một chính sách dùng chung có học được cách sửa lịch hữu ích cho 53 nút không?", "CityFlow, Double DQN residual theo lịch", "Một mạng mô phỏng với nhu cầu tổng hợp", C["pressure"]),
      ("CH3", "Kết quả còn đứng sau baseline mạnh, nhiều seed, xe chưa vào được và kiểm nguồn không?", "Baseline, thống kê, bộ chọn, kiểm nguồn", "Bằng chứng hiện có và những lỗ còn lại", C["stop"])]
rqh = "".join(f'''<div class="col" style="border-top:6px solid {c};padding-top:16px">
 <div class="hero" style="font-size:54px;color:{c}">{k}</div>
 <div style="font-size:21px;font-weight:800;color:{C["ink"]};line-height:1.25;margin:12px 0 18px;min-height:130px">{q}</div>
 <div class="xs muted" style="font-weight:800">Trả lời bằng</div><div class="small" style="margin-bottom:12px">{e}</div>
 <div class="xs muted" style="font-weight:800">Phạm vi kết luận</div><div class="small">{s}</div></div>''' for k, q, e, s, c in rq)
slide("Vì sao", "Ba câu hỏi nghiên cứu", f'''<div class="row" style="gap:36px">{rqh}</div>
<div class="panel dark" style="margin-top:30px;font-size:19px;line-height:1.45"><b style="color:#6FD3B0">Luận điểm.</b> Luận văn kiểm tra lúc nào điều khiển thích nghi giảm hàng chờ trong các kịch bản mô phỏng đã khống chế. Câu trả lời phụ thuộc chế độ nhu cầu và baseline, và bằng chứng hiện có chưa cho biết hiệu quả ngoài đường.</div>''',
      secs=75, notes=N(
    "Luận văn trả lời ba câu. Câu 1: tại nút có dữ liệu công bố, học tăng cường có giảm hàng chờ không? Em trả lời trong SUMO với ba chế độ và năm seed học. "
    "Câu 2: một chính sách dùng chung trọng số cho 53 nút có học được các sửa nhỏ trên lịch đèn không? Em trả lời trong CityFlow bằng bộ điều khiển residual theo lịch. "
    "Câu 3 là về độ tin: sau baseline mạnh, nhiều seed, tính cả xe chưa vào được, và kiểm nguồn dữ liệu, kết quả còn lại bao nhiêu? "
    "Mỗi câu có phạm vi riêng, và em giữ đúng phạm vi đó đến cuối bài.",
    ["CH1 = SUMO, một nút", "CH2 = CityFlow, chính sách dùng chung, 53 nút", "CH3 = độ mạnh của bằng chứng"],
    ["Nói “kiểm tra lúc nào có ích”, không nói “chứng minh RL tốt hơn”."]))

# ================================================================== 05 two tiers
two = table(["", "SUMO: một nút", "CityFlow: mạng Hải Châu"], [
    ["Vai trò", "Kiểm tra tại nút có nguồn công bố", "Kiểm tra quy mô và tương tác giữa nút"],
    ["Quy mô", "1 nút, 4 hướng, 3 pha xanh", "<b>53</b> nút có đèn, dựng từ OSM"],
    ["Mô hình", "Dueling <b>Double</b> DQN, lợi tức 3 bước", "<b>Double</b> DQN residual theo lịch"],
    ["Vào → ra", "16 số → 3 giá trị Q", "27 số mỗi macro ứng viên → 1 giá trị Q"],
    ["Nhịp quyết định", "10 giây", "macro 300 giây, yêu cầu mỗi 10 giây"],
    ["Thưởng", "−(hàng chờ + xe chưa vào cuối bước 10 giây) × 0,01", "−(hàng chờ mạng + tích phân xe chưa vào) / 100.000"],
    ["Huấn luyện", "30 episode × 3.600 giây, seed 11–15", "12 episode × 3.600 giây, seed 12–16"],
    ["Baseline cố định", "Lịch công bố 103 giây", "Xanh danh định 25 giây, chọn trên kiểm định"],
    ["Kiểm tra", "15 ca (3 chế độ × 5)", "15 ca (3 chế độ × 5)"],
], cls="t tight")
slide("Vì sao", "Hai tầng: hai mô phỏng, hai mô hình, hai câu hỏi", f'''
<div class="row" style="gap:30px">
 <div style="flex:1.75">{two}</div>
 <div class="col">
  {vchain(["<b>Bài báo Đà Nẵng</b><br><span class='xs muted'>lịch đèn, bảng rẽ, biểu đồ camera</span>", "<b>CSV và các giả định đã ghi</b>",
           "<div style='display:flex;gap:8px'><div style='flex:1;background:#DDF1E9;border-radius:8px;padding:4px'><b>SUMO</b><br><span class='xs'>1 nút</span></div><div style='flex:1;background:#E1EAF7;border-radius:8px;padding:4px'><b>CityFlow</b><br><span class='xs'>53 nút + OSM</span></div></div>",
           "<b>Đánh giá ghép cặp</b><br><span class='xs muted'>cùng nhu cầu, các baseline, nhiều seed</span>", "<b>Kết quả, giới hạn, demo phát lại</b>"])}
  <div class="note stop" style="margin-top:14px"><b>Không chuyển trọng số</b> từ SUMO sang CityFlow. Hai tầng chung câu hỏi nghiên cứu và hình dạng nhu cầu, không phải học xong rồi tinh chỉnh tiếp.</div>
 </div>
</div>''', secs=80, source="docs/defense/thesis-understanding-guide-vi.md, mục 2", notes=N(
    "Thiết kế có hai tầng. Tầng SUMO là một nút có nguồn công bố; đó là mốc thực nghiệm. Mô hình là dueling Double DQN, đọc 16 số và ra ba giá trị Q cho ba pha xanh, quyết định mỗi 10 giây. "
    "Tầng CityFlow là mạng 53 nút dựng từ OpenStreetMap với nhu cầu tổng hợp. Mô hình là Double DQN residual theo lịch: mỗi 300 giây mỗi nút chọn một sửa nhỏ trên lịch, và một MLP dùng chung chấm mọi ứng viên. "
    "Điều quan trọng: không có trọng số nào đi từ mô phỏng này sang mô phỏng kia. Hai tầng khác kiến trúc, khác thưởng và khác cách học; chúng chỉ nối với nhau bằng câu hỏi nghiên cứu và hình dạng nhu cầu.",
    ["SUMO: 16 → 3 Q, mỗi 10 giây", "CityFlow: 27 mỗi macro → 1 Q, 300 giây, dùng chung", "Không chuyển trọng số"],
    ["Không vẽ một cột “RL” gộp cả hai mô hình."],
    [("Hai tầng liên hệ thế nào?", "Cùng câu hỏi nghiên cứu và cùng hình dạng nhu cầu camera; không dùng chung trọng số.")]))

# ================================================================== DATA
divider("Dữ liệu", 2, "Dữ liệu đến từ đâu", "Cái gì thực sự được quan sát, và cái gì em phải giả định?", 8)

slide("Dữ liệu", "Điểm xuất phát: trục chính Đà Nẵng, tính đèn từ khảo sát thực tế", f'''
<div class="rule-l ink" style="margin-bottom:18px"><div class="small"><b>Trần Trung Việt & Phan Cao Thọ (2007).</b> <i>Nghiên cứu ứng dụng bài toán điều khiển giao thông bằng “Làn sóng xanh” trên các trục giao thông chính ở thành phố Đà Nẵng.</i> Tạp chí Cầu Đường Việt Nam, số 10/2007, tr. 23–28.</div></div>
{chain([("2007 · trục chính", "khảo sát dòng xe → làn sóng xanh"), ("2025 · một nút", "Phan, Le & Nguyen: lịch, bảng, camera"), ("Luận văn này", "nút SUMO + mạng 53 đèn trên trục chính")])}
<div class="row" style="gap:30px;margin-top:22px">
 <div class="col panel go"><h3>Ý tưởng em kế thừa</h3><ul class="small" style="margin-left:18px">
  <li>Bài toán đèn ở Đà Nẵng bắt đầu từ <b>dòng xe khảo sát</b> trên <b>trục chính có đèn</b>, không phải một thành phố chung chung.</li>
  <li>Tầng mạng <b>bỏ đường dân cư</b> (OSM highway.residential) để bám các trục chính.</li>
  <li>Phương pháp của bài là lịch <b>cố định có phối hợp</b>: chu kỳ, thời gian xanh, băng thời gian tính offline từ số đếm.</li></ul></div>
 <div class="col panel stop"><h3>Điều em không lấy</h3><ul class="small" style="margin-left:18px">
  <li><b>Không lấy số liệu.</b> Em chỉ đọc tên bài và tóm tắt; chưa có toàn văn và dữ liệu khảo sát.</li>
  <li>Baseline cố định của luận văn <b>không có offset</b>, nên không phải làn sóng xanh.</li>
  <li>RL ở đây <b>thích ứng</b>: phản ứng theo hàng chờ quan sát, không theo băng tính sẵn.</li></ul></div>
</div>''', secs=55, source="https://scv.udn.vn/trantrungviet/BBao/5864 (chỉ tóm tắt; chưa có toàn văn)", notes=N(
    "Trước nguồn năm 2025, em xin nêu một điểm xuất phát tại địa phương. Năm 2007, tác giả Trần Trung Việt và TS. Phan Cao Thọ đăng trên Tạp chí Cầu Đường Việt Nam nghiên cứu điều khiển phối hợp “Làn sóng xanh” cho các trục giao thông chính ở Đà Nẵng. Bài toán được xây dựng trên cơ sở bài toán băng thời gian và số liệu khảo sát thực tế dòng xe trên các trục có đèn tín hiệu, kèm phần mềm Green Wave Design. "
    "Em kế thừa ý tưởng, không kế thừa số liệu: ở Đà Nẵng, bài toán đèn nằm trên trục chính và bắt đầu từ dòng xe khảo sát. Vì vậy tầng mạng bỏ đường dân cư và bám trục chính, và nguồn tiếp theo, bài báo 2025, là một nút có số đếm công bố. "
    "Hai giới hạn em nói thẳng: em mới đọc tên bài và tóm tắt nên không trích số nào; và baseline cố định của em không có offset, nên không phải làn sóng xanh. Lịch phối hợp sẽ là một baseline cố định mạnh hơn mà em chưa thử.",
    ["2007: trục chính + khảo sát + làn sóng xanh", "Chỉ ý tưởng, không số liệu (chỉ tóm tắt)", "Baseline cố định ≠ làn sóng xanh"],
    ["Không nói luận văn dùng dữ liệu của bài 2007.", "Không khẳng định liên hệ giữa tác giả bài 2007 và bài 2025."],
    [("Em có so với điều khiển làn sóng xanh không?", "Không. Baseline cố định là lịch không phối hợp (103 giây công bố trong SUMO, chỉnh trên tập kiểm định trong CityFlow), không có offset. Làn sóng xanh sẽ là baseline cố định mạnh hơn mà em chưa thử; em nêu đây là một giới hạn."),
     ("Vì sao trích một bài năm 2007?", "Bài cho thấy thực tiễn địa phương: đèn trên trục chính Đà Nẵng được tính offline từ khảo sát. Luận văn hỏi liệu bộ điều khiển thích ứng có cải thiện được logic cố định trong bối cảnh đó không.")]))

src_rows = [["Hình học, làn 2/2/3/3", "tr. 7", "Dựng nút SUMO"],
            ["Xanh 32/28/22 giây, chu kỳ 103 giây", "tr. 7, Hình 4 tr. 8", "Baseline cố định công bố"],
            ["12 luồng rẽ, 6.171 PCU/giờ", "Bảng 1 tr. 8 (2022)", "Bối cảnh chia luồng"],
            ["Camera 1/4/2025, 06:00–18:00", "tr. 16", "Ngày của nguồn camera"],
            ["2 camera, 4 đường đo", "Hình 12 tr. 17", "Phần thực sự được quan sát"],
            ["PCU: xe máy 0,3; ô tô 1; bus 2; xe tải 2,5", "tr. 19", "Quy đổi đơn vị của nguồn"],
            ["Đếm theo giờ và loại xe", "Hình 17–18 tr. 20", "Đọc xấp xỉ vào CSV"],
            ["Dữ liệu gốc không công khai", "tr. 23", "Giới hạn video gốc"]]
slide("Dữ liệu", "Một bài báo, một nút giao ở Đà Nẵng", f'''
<div class="row" style="gap:30px">
 <div style="width:380px;flex:none"><img class="fig" src="{img("junction")}" style="width:380px;height:380px;object-fit:contain">
  <div class="cap">Nút Lê Thanh Nghị – Cách Mạng Tháng 8 – 2/9, phía cầu Hòa Xuân. Hai camera quan sát bốn đường đo; các hướng vào được mô hình khoảng 300 m.</div></div>
 <div class="col">
  <div class="rule-l ink" style="margin-bottom:14px"><div class="small"><b>Phan, Le và Nguyen (2025).</b> <i>Application of Dueling Double Deep Q-Network for Dynamic Traffic Signal Optimization: A Case Study in Danang City, Vietnam.</i> MAKE 7(3):65. doi:10.3390/make7030065</div></div>
  {table(["Nội dung", "Trong PDF", "Dùng để"], src_rows, cls="t tight")}
  <div class="note stop" style="margin-top:12px;font-size:15px">Nguồn ghi tên đường không nhất quán (tr. 7 ghi “Nguyenthanhnghi”); luận văn theo Bảng 1 và Hình 12. <b>PCU/giờ không phải xe/giờ</b>, nên không cộng hai thứ này với nhau.</div>
 </div>
</div>''', secs=100, source="datasets/danang_published/sources/phan2025_make7030065.pdf (trang PDF 1–24)", notes=N(
    "Nguồn chính là Phan, Le và Nguyen, 2025, trên tạp chí MAKE. Em dùng bài này vì nó công bố hình học, lịch đèn và số đếm camera của một nút cụ thể ở Đà Nẵng. "
    "Mỗi mục em dùng đều có vị trí: hình học trang 7, lịch 103 giây ở trang 7 và Hình 4, mười hai luồng rẽ ở Bảng 1 trang 8, ngày camera ở trang 16, hai camera và bốn đường đo ở Hình 12, hệ số PCU ở trang 19, và đếm theo giờ ở Hình 17 và 18. "
    "Hai lưu ý ngay từ đầu: tên đường trong nguồn không nhất quán, và bảng rẽ tính bằng PCU mỗi giờ, tức xe con quy đổi, nên không cộng với số xe. Video gốc không công khai.",
    ["Phan, Le và Nguyen 2025, MAKE, doi make7030065", "Mỗi số có trang, hình hoặc bảng", "PCU khác số xe; không có video gốc"],
    ["Tên file ghi tran2025; tác giả đã kiểm là Phan và cộng sự."],
    [("Đây có phải dữ liệu hiện trường không?", "Phần camera là số đếm đã công bố, đọc xấp xỉ từ biểu đồ: một ngày, bốn luồng. Phần còn lại là giả định mô phỏng đã ghi lại.")]))

tiers = [("Nguồn công bố", "PDF, lịch đèn, bảng rẽ, biểu đồ camera", "“Theo bài báo, trang / hình / bảng …”", C["ink"]),
         ("Trích từ nguồn", "Giá trị đọc xấp xỉ trong CSV", "“Số đếm xấp xỉ đọc từ biểu đồ …”", C["go"]),
         ("Dựng mô phỏng", "Mở rộng cả nút, lộ trình, mẫu xe", "“Giả định dùng để dựng kịch bản …”", C["caution"]),
         ("Đầu ra mô phỏng", "Tích phân hàng chờ, hoàn thành, thưởng", "“Kết quả trong mô phỏng với cấu hình …”", C["stop"])]
th = "".join(f'''<div style="display:flex;gap:16px;margin-bottom:14px"><div class="hero" style="font-size:40px;color:{c};width:34px">{i+1}</div>
<div><div style="font-weight:850;font-size:19px;color:{C["ink"]}">{n}</div><div class="xs">{e}</div><div class="xs muted"><i>{s}</i></div></div></div>''' for i, (n, e, s, c) in enumerate(tiers))
slide("Dữ liệu", "48 dòng đọc xấp xỉ, bốn tầng độ tin cậy", f'''
<div class="row" style="gap:40px">
 <div class="col">
  <div class="row" style="gap:36px;margin-bottom:22px">{stat("48", "dòng = 4 luồng × 12 nhãn giờ")}{stat("192", "giá trị xấp xỉ của ô tô, xe máy, xe tải, xe buýt")}{stat("1 ngày", "1 tháng 4 năm 2025, không kết luận theo mùa")}</div>
  <div class="row" style="gap:14px;margin-bottom:20px">
   <div class="panel go col" style="padding:14px 18px">{stat("1.395", "xe/giờ lúc 13:00 → kiểm tra normal", "go", 34)}</div>
   <div class="panel stop col" style="padding:14px 18px">{stat("2.330", "xe/giờ lúc 08:00 → AM, đồng thời dùng để học", "stop", 34)}</div>
   <div class="panel caution col" style="padding:14px 18px">{stat("2.400", "xe/giờ lúc 17:00 → kiểm tra PM", "caution", 34)}</div>
  </div>
  <div class="note" style="font-size:15.5px">Dung sai ±15 / ±30 xe/giờ là <b>sai số đọc</b> do dự án đặt, không phải khoảng tin cậy. SHA-256 khớp chỉ chứng minh file không đổi byte, <b>không</b> chứng minh số đếm mô tả đúng giao thông thật.</div>
 </div>
 <div style="width:440px;flex:none"><h3>Bốn tầng độ tin cậy</h3>{th}</div>
</div>''', secs=75, source="datasets/danang_published/phan2025_camera_hourly_digitized.csv · docs/research/danang-data-claim-audit.md", notes=N(
    "Từ Hình 17 và 18 em đọc thành CSV: bốn luồng nhân mười hai nhãn giờ là 48 dòng; mỗi dòng có bốn loại xe, nên 192 giá trị xấp xỉ, tất cả từ một ngày. "
    "Ba số màu là mức kiểm tra: 1.395 lúc 13:00 là normal, 2.330 lúc 08:00 là AM, và 2.400 lúc 17:00 là PM. Đó là tổng trên bốn đường đo, không phải cả nút. "
    "Để nói đúng độ mạnh, em tách bốn tầng: nguồn công bố, giá trị trích xuất, giả định dựng kịch bản, và đầu ra mô phỏng. Mỗi tầng có cách nói riêng. "
    "Dung sai ±15 và ±30 là sai số đọc, không phải khoảng tin cậy, và mã băm chỉ chứng minh file không bị sửa.",
    ["48 dòng · 192 giá trị · 1 ngày", "1.395 / 2.330 / 2.400 = normal / AM / PM", "4 tầng: nguồn → trích → giả định → đầu ra"],
    ["Không nói 2.400 là tổng lưu lượng của cả nút."]))

slide("Dữ liệu", "Từ số nguồn đến nhu cầu mô phỏng", f'''
<div class="row" style="gap:30px">
 <div style="width:450px;flex:none">
  <h3>SUMO <span class="sub">một nút</span></h3>
  {vchain(["Lịch và hình học công bố → <b>nút và chương trình đèn</b>", "CSV camera, 4 luồng → <b>nhu cầu quy trình chính</b>", "Seed nhu cầu → lộ trình và thời điểm xuất phát", "Seed mô phỏng → ngẫu nhiên bên trong SUMO"])}
  <div class="row" style="gap:10px;margin-top:14px">
   <div class="col">{stat("1.395", "xe/giờ, normal", "go", 30)}</div><div class="col">{stat("2.330", "xe/giờ, AM (học)", "stop", 30)}</div><div class="col">{stat("2.400", "xe/giờ, PM", "caution", 30)}</div></div>
  <div class="xs muted" style="margin-top:10px">Mức cả nút khoảng 5.793 / 9.676 / 9.967 là <b>ngoại suy của dự án</b>, không phải quy trình chính.</div>
 </div>
 <div class="col">
  <h3>CityFlow <span class="sub">53 nút ở Hải Châu</span></h3>
  {chain([("OSM PBF", "Geofabrik, ODbL"), ("osmium", "cắt khung"), ("netconvert", "mạng SUMO"), ("bộ chuyển", "roadnet CityFlow"), ("53 đèn", "hợp đồng pha")])}
  <div class="xs muted" style="margin:6px 0 10px">khung 108,1888; 16,0213 – 108,2360; 16,1037. Mạng <b>đã xử lý, dẫn xuất</b>, không phải mọi đèn ngoài đường.</div>
  {table(["Thuộc tính", "Giá trị"], [["Họ lộ trình", "1.290 → học / kiểm định / kiểm tra = 644 / 323 / 323"], ["Dòng lộ trình mỗi ca", "500, mỗi dòng phát nhiều xe"],
       ["Cơ cấu xe", "xe máy với xác suất 0,90, còn lại ô tô (giả định)"], ["Episode", "3.600 giây = ba bin 1.200 giây"]], cls="t tight")}
  <div class="eq" style="margin-top:10px;font-size:14.5px"><span class="c">interval_bin</span> = 240 × <span class="a">1603,33</span> / source_count_bin   <span class="c"># PM 2.400 → 160,3 giây</span></div>
 </div>
</div>
<div class="note stop" style="margin-top:14px"><b>500 lộ trình không phải 500 xe.</b> Hồ sơ chỉ mượn <b>hình dạng tương đối</b> của nhu cầu camera; ba giờ nguồn được nén vào ba bin 20 phút.</div>''',
      secs=100, source="configs/haichau_network_v2.yaml · src/traffic_rl/network/haichau_dataset.py · datasets/haichau_network_v2/provenance.json", notes=N(
    "Trong SUMO, lịch và hình học công bố dựng nút và chương trình đèn; CSV camera dựng nhu cầu chính: 1.395 xe ở normal, 2.330 ở AM và 2.400 ở PM trong một giờ. Seed nhu cầu đặt thời điểm xuất phát, seed mô phỏng đặt ngẫu nhiên bên trong. Các số cả nút gần 9.700 chỉ là ngoại suy. "
    "Trong CityFlow, topology đến từ OpenStreetMap qua osmium, netconvert và bộ chuyển sang roadnet của CityFlow. Kết quả là mạng dẫn xuất với 53 nút có đèn. "
    "Nhu cầu mạng là tổng hợp: 1.290 họ lộ trình chia thành học, kiểm định và kiểm tra, 500 dòng lộ trình mỗi ca, và tỷ lệ xe máy 90 phần trăm là giả định lấy mẫu. Hình dạng camera theo giờ điều chỉnh khoảng phát xe: giờ đông hơn thì khoảng ngắn hơn, ví dụ 2.400 xe cho khoảng 160 giây. "
    "Nhấn mạnh: 500 dòng lộ trình không phải 500 xe, và một ca PM không phát lại ba giờ thật.",
    ["SUMO: 1.395 / 2.330 / 2.400", "CityFlow: OSM → 53 đèn, 1.290 họ lộ trình", "Hồ sơ = hình dạng tương đối, không phải số đếm"],
    ["Không gọi mạng 53 nút là mọi đèn thật của Hải Châu."],
    [("Vì sao 53 nút?", "Đó là số đèn được điều khiển sau đường ống OSM → netconvert → CityFlow, với các bước gộp và lọc ghi trong provenance.")]))

slide("Dữ liệu", "Cách chia dữ liệu và ba loại seed", f'''
<div class="row" style="gap:40px">
 <div style="flex:1.2">
  {table(["Nhóm CityFlow", "Seed nhu cầu", "Seed mô phỏng", "Số ca"], [["Học", "11, 12, 13", "111, 112, 113", "3 chế độ × 3 = 9"], ["Kiểm định", "31, 32", "131, 132", "3 chế độ × 2 = 6"], ["Kiểm tra", "101–105", "201–205", "3 chế độ × 5 = <b>15</b>"]], align=["", "c", "c", ""])}
  <p class="small" style="margin-top:16px"><b>SUMO:</b> học trên AM nhu cầu 11 / mô phỏng 11 và kiểm định trên AM nhu cầu 31 / mô phỏng 31, <b>dùng chung cho mọi seed học</b>. Kiểm tra trên 15 ca.</p>
  <div class="note" style="margin-top:14px;font-size:15.5px">Chia theo họ lộ trình tách các họ, nhưng lộ trình vẫn có thể đi qua cùng đoạn và cùng nút. Đây <b>không</b> phải kiểm tra trên một thành phố chưa thấy.</div>
 </div>
 <div class="col">
  <div class="rule-l go" style="margin-bottom:16px"><b style="font-size:20px">Seed nhu cầu</b><div class="small">Lấy mẫu lộ trình, loại xe, thời điểm xuất phát.</div></div>
  <div class="rule-l pressure" style="margin-bottom:16px"><b style="font-size:20px">Seed mô phỏng</b><div class="small">Ngẫu nhiên bên trong bộ mô phỏng.</div></div>
  <div class="rule-l stop" style="margin-bottom:20px"><b style="font-size:20px">Seed học</b><div class="small">Khởi tạo mạng, khám phá, lấy mẫu bộ nhớ phát lại.</div></div>
  <div class="panel go small">Cùng seed nhu cầu và seed mô phỏng cho mọi bộ điều khiển cho phép so sánh <b>ghép cặp</b>. Nhiều seed học đo <b>học biến động bao nhiêu</b>.</div>
 </div>
</div>''', secs=55, source="results/haichau_network_v2/experiment-manifest.json · results/danang_protocol_v1/experiment-manifest.json", notes=N(
    "Có ba loại seed với nghĩa khác nhau: seed nhu cầu đặt nhu cầu, seed mô phỏng đặt ngẫu nhiên của bộ mô phỏng, và seed học đặt quá trình học. "
    "Trong CityFlow, học có 9 ca, kiểm định 6 và kiểm tra 15, năm ca mỗi chế độ. Mọi bộ điều khiển chạy trên cùng cặp seed nhu cầu và seed mô phỏng, nên chênh lệch là so sánh ghép cặp. "
    "Trong SUMO, học và kiểm định đều là AM và dùng chung cho cả năm seed học. "
    "Lưu ý: nhiều ca nhu cầu của một checkpoint không phải nhiều mô hình độc lập, và chia họ lộ trình không phải một thành phố mới.",
    ["3 seed: nhu cầu · mô phỏng · học", "Kiểm tra = 15 ca (3 × 5)", "Ghép cặp khác mô hình độc lập"]))

slide("Dữ liệu", "Mở rộng: tự trích số xe và hướng đi từ camera công khai", f'''
<div class="small" style="margin-bottom:8px"><b>Video YouTube công khai</b> → <b>YOLOv8-VisDrone</b> nhận dạng từng xe → <b>ByteTrack</b> giữ ID → <b>7 vạch đếm</b> vào / ra theo loại xe → <b>xích Markov</b> P(lối ra | lối vào)</div>
<div class="row" style="gap:20px">
 <div style="width:490px;flex:none"><img class="fig" src="{img("cam_frame")}" style="width:490px;height:262px;object-fit:cover">
  <div class="cap">0511.vn, nút Tây Cầu Rồng, 11/7/2026 17:16–17:31. Khung = xe, số = ID, vệt = đường đi, vạch trắng = vạch đếm.</div></div>
 <div class="col"><img class="fig" src="{img("cam_map")}" style="width:100%;height:262px;object-fit:contain">
  <div class="cap">Ô tô trên nền OpenStreetMap: xác suất rẽ ở J1 (xanh), J2 (cam); chiều một chiều trên OSM khớp số đếm.</div></div>
</div>
<div class="row" style="gap:18px;margin-top:10px;align-items:stretch">
 <div style="width:250px;flex:none">{stat("4.323", "lượt qua vạch / 15 phút", "ink", 28)}<div style="height:6px"></div>{stat("75%", "ô tô trục chính lên Cầu Rồng; lệch vào–ra 4% / 17%", "go", 28)}</div>
 <div class="panel go col" style="padding:10px 14px;font-size:13.5px;line-height:1.38"><b>Realtime, đã đo.</b> <b>Một nút:</b> YOLOv8m (ảnh 1280) + theo vết + đếm vạch xử lý <b>180 giây video trong 169 giây</b> trên một laptop Apple M4 Pro (7,5 khung/giây). Ô tô gần camera lệch +8%, xe máy −10% so với bản chính xác. Độ trễ khoảng 0,13 giây ≪ nhịp quyết định 10 giây của SUMO. <b>Mạng 53 nút:</b> mỗi nút một thiết bị biên như vậy, chỉ gửi số đếm mỗi 10 giây (<i>chưa thử ở quy mô mạng</i>).</div>
 <div class="note stop" style="width:250px;flex:none;font-size:13.5px;line-height:1.38"><b>Minh họa khả thi, chưa phải dữ liệu luận văn:</b> một camera, 15 phút, chưa đếm tay; xe máy ở xa bị đếm thiếu. Không dùng để dựng nhu cầu mô phỏng.</div>
</div>''', secs=60, source="scripts/count_camera_vehicles.py · scripts/analyze_camera_routes.py · results/camera_counts/README.md", notes=N(
    "Một giới hạn của dữ liệu là video gốc của bài báo không công khai. Em thử xem có tự lấy được số liệu từ camera công khai không. "
    "Em dùng camera của trang 0511.vn tại nút Tây Cầu Rồng, 15 phút cao điểm chiều 11 tháng 7. Mô hình YOLO huấn luyện trên ảnh nhìn từ trên cao nhận dạng từng xe, ByteTrack giữ ID của xe qua các khung hình, và bảy vạch đếm ghi xe vào, xe ra và loại xe. "
    "Nối các lần qua vạch của cùng một xe cho ra hành trình, và từ đó là xích Markov: xác suất ra ở lối nào khi biết xe vào từ lối nào. Ví dụ 75 phần trăm ô tô đi trên trục chính rẽ lên Cầu Rồng. "
    "Hai kiểm tra độc lập: số ô tô vào và ra ở mỗi nút lệch 4 và 17 phần trăm, và chiều một chiều trên OpenStreetMap khớp với chiều xe đếm được. "
    "Về realtime, em đã đo: với model nhỏ hơn, cả chuỗi xử lý 180 giây video trong 169 giây trên một laptop, nhanh hơn thời gian thực, trong khi bộ điều khiển chỉ cần trạng thái mỗi 10 giây. Ở mức mạng, mỗi nút cần một thiết bị như vậy và chỉ gửi số đếm; phần này em chưa thử. "
    "Giới hạn: đây là minh họa khả thi, một camera và 15 phút, chưa đếm tay đối chiếu, xe máy ở xa camera bị đếm thiếu, nên em không dùng nó để dựng nhu cầu mô phỏng.",
    ["Camera công khai → YOLO → ByteTrack → vạch đếm → Markov", "4.323 lượt / 15 phút; 75% ô tô trục chính lên cầu", "Realtime 1 nút: 180 giây video trong 169 giây (laptop M4 Pro)", "Mạng: một thiết bị biên mỗi nút — chưa thử", "Minh họa, không phải dữ liệu luận văn"],
    ["Không nói đây là dữ liệu nhu cầu đã dùng trong SUMO hay CityFlow.", "Không đưa tổng số xe máy: lối xa bị đếm thiếu.", "Không nói “chính xác 95%”: chưa có đếm tay.", "Không nói “đã chạy realtime cho cả mạng”: mới đo một camera."],
    [("Độ chính xác của YOLO là bao nhiêu?", "Em chưa đo bằng đếm tay. Bằng chứng hiện có là cân bằng vào–ra của ô tô (lệch 4% và 17%) và chiều một chiều khớp OSM. Xe máy ở xa camera bị đếm thiếu nên em không báo tổng xe máy."),
     ("Sao không dùng nó cho mô phỏng?", "Chỉ có 15 phút ở một nút khác nút trong bài báo và chưa kiểm chứng. Bước tiếp là đếm tay một đoạn, chạy nhiều ngày, rồi mới hiệu chuẩn nhu cầu."),
     ("YOLO có chạy realtime được không?", "Một nút: được, đã đo — YOLOv8m ảnh 1280 cộng theo vết và đếm vạch xử lý 180 giây video trong 169 giây trên laptop M4 Pro; độ trễ khoảng 0,13 giây so với nhịp quyết định 10 giây. Đổi lại, xe máy đếm thấp hơn khoảng 10% so với bản chính xác. Mạng 53 nút: kiến trúc là mỗi nút một thiết bị biên gửi số đếm; em chưa thử ở quy mô đó."),
     ("Vì sao dùng model VisDrone?", "YOLO huấn luyện trên COCO gần như không thấy xe máy từ góc cao này; VisDrone là ảnh nhìn từ trên xuống nên bắt được xe máy chỉ 10 pixel.")]))

# ================================================================== RL
divider("Cơ sở RL", 3, "Học từ hệ quả", "Hai ý nào mà cả hai mô hình đều dựa vào?", 3)

clocks = "".join(f'<div style="display:flex;gap:16px;align-items:baseline;margin:8px 0"><div class="hero" style="font-size:34px;width:110px;color:{c}">{t}</div><div class="small"><b>{n}</b><br>{d}</div></div>'
                 for t, n, d, c in [("1 giây", "Giây mô phỏng", "chỉ số được tích phân mỗi giây", C["base"]), ("10 giây", "Nhịp điều khiển", "SUMO chọn pha; CityFlow chạy một yêu cầu", C["go"]),
                                    ("300 giây", "Macro", "Residual CityFlow chọn kế hoạch cho cả block", C["stop"])])
slide("Cơ sở RL", "Học tăng cường học từ chuyện xảy ra tiếp theo", f'''
<div class="row" style="gap:40px">
 <div style="width:500px;flex:none">{rl_loop()}<p class="small" style="margin-top:10px">Không có nhãn nào chỉ hành động tối ưu. Thưởng là <b>chi phí âm</b>, nên <b>ít âm hơn thì tốt hơn</b>.</p></div>
 <div class="col">
  <h3>Giá trị Q</h3>
  <div class="eq">Lợi tức = r<sub>t</sub> + γ r<sub>t+1</sub> + γ² r<sub>t+2</sub> + …
<span class="k">hành động tham</span> = argmax<sub>a</sub> Q(o, a)</div>
  <p class="small" style="margin:10px 0 20px">Q(o, a) dự đoán lợi tức chiết khấu khi làm a ở o. Q cao hơn nghĩa là chi phí kỳ vọng thấp hơn. Q <b>không</b> phải số xe được thả.</p>
  <h3>Ba đồng hồ cần tách riêng</h3>{clocks}
  <div class="xs muted">Một bước cập nhật bộ tối ưu là một lần sửa trọng số, không phải một giây mô phỏng.</div>
 </div>
</div>''', secs=70, notes=N(
    "Vòng học tăng cường: tác nhân nhận quan sát, chọn hành động, mô phỏng thực hiện rồi trả thưởng và quan sát kế tiếp. Khi huấn luyện, kinh nghiệm vào bộ nhớ phát lại để cập nhật mô hình. "
    "Ở đây thưởng là số âm của hàng chờ, nên ít âm hơn thì tốt hơn. Giá trị Q dự đoán tổng thưởng tương lai đã chiết khấu của một hành động; chính sách tham chọn Q lớn nhất. "
    "Có ba đồng hồ: mô phỏng chạy từng giây và chỉ số được cộng mỗi giây; nhịp 10 giây là lúc SUMO chọn pha; macro 300 giây là lúc residual CityFlow quyết định. Tách ba đồng hồ này tránh đọc sai hầu hết tham số.",
    ["Thưởng âm = chi phí", "Q = lợi tức kỳ vọng, không phải số xe", "1 giây · 10 giây · 300 giây"]))

slide("Cơ sở RL", "Double DQN và dueling sửa hai việc khác nhau", f'''
<div class="row" style="gap:40px">
 <div class="col">
  <h3>Double DQN đổi <span class="go">đích học</span></h3>
  <p class="small">DQN thường dùng một phép max vừa để <b>chọn</b> vừa để <b>chấm</b> hành động sau, nên lỗi lạc quan bị phóng lên. Double DQN tách hai vai.</p>
  <div class="eq" style="margin:10px 0"><span class="c"># mạng đang học chọn</span>
a* = argmax<sub>a</sub> Q<sub>online</sub>(o′, a)
<span class="c"># mạng đích chấm điểm</span>
y  = r + (1 − done) · γ · Q<sub>target</sub>(o′, a*)</div>
  {table(["Ví dụ số", "Hành động A", "Hành động B"], [["Q đang học", "<b>−4</b>, được chọn", "−5"], ["Q đích", "<b>−6</b>, được dùng", "−3"]], cls="t tight", align=["", "c", "c"])}
  <div class="xs muted" style="margin-top:6px">Mạng đích được chép từ mạng đang học theo chu kỳ. van Hasselt, Guez và Silver (2016).</div>
 </div>
 <div class="col">
  <h3>Dueling đổi <span class="pressure">đầu ra</span></h3>
  <div class="eq" style="margin:4px 0 12px">Q(o, a) = V(o) + A(o, a) − trung bình<sub>b</sub> A(o, b)</div>
  <ul class="dots pressure small"><li><b>V(o)</b> nói trạng thái tốt đến đâu</li><li><b>A(o, a)</b> nói mỗi hành động tốt hơn bao nhiêu</li><li>Trừ trung bình để cố định cách tách V và A</li><li>Có ích khi nhiều hành động gần giá trị nhau; đó là động cơ thiết kế, không phải bảo đảm</li></ul>
  <div class="xs muted" style="margin-top:6px">Wang và cộng sự, ICML 2016.</div>
 </div>
</div>
<div class="row" style="gap:20px;margin-top:22px">
 <div class="panel go col"><b>SUMO</b> dùng <b>cả hai</b>: đích Double, đầu dueling, lợi tức 3 bước.</div>
 <div class="panel pressure col"><b>Residual CityFlow</b> chỉ dùng <b>Double</b>, một đầu ra số.</div>
</div>''', secs=85, notes=N(
    "Double và dueling hay bị lẫn. Double DQN là chuyện đích học: mạng đang học chọn hành động tốt nhất kế tiếp, mạng đích chấm hành động đó. "
    "Ví dụ: mạng đang học dự đoán A = −4 và B = −5 nên chọn A; mạng đích dự đoán A = −6 và B = −3; Double DQN dùng −6 tại A, dù mạng đích thích B hơn. Cách này giảm độ lệch lạc quan. "
    "Dueling là chuyện lớp ra: tách giá trị trạng thái V khỏi lợi thế A của từng hành động, rồi ghép lại thành Q = V + A trừ trung bình của A. "
    "Mô hình SUMO dùng cả hai. Mô hình CityFlow chỉ dùng Double, mỗi macro ra một số.",
    ["Double = mạng đang học chọn, mạng đích chấm", "Dueling = V + A − trung bình A", "SUMO cả hai · CityFlow chỉ Double"],
    ["Không nói dueling làm giảm ước lượng quá cao; việc đó là của Double."],
    [("Dueling có giảm ước lượng quá cao không?", "Không trực tiếp. Double lo việc chọn và chấm trong đích học; dueling tách V và A trong kiến trúc.")]))

# ================================================================== SUMO
divider("SUMO", 4, "Một nút trong SUMO", "Mô hình thấy gì, làm gì, và tối ưu gì tại nút đã công bố?", 4.5)

vec16 = '<div style="display:flex;gap:4px">' + "".join(f'<div style="flex:1;height:40px;border-radius:5px;background:{c};color:#fff;font-weight:850;font-size:14px;display:flex;align-items:center;justify-content:center">{l}</div>'
                                                      for l, c in [("Q", C["go"])] * 4 + [("N", C["phaseB"])] * 4 + [("P", C["stop"])] * 4 + [("φ", C["caution"])] * 3 + [("t", C["base"])]) + "</div>"
slide("SUMO", "Mô hình SUMO: 16 số vào, 3 giá trị Q ra, mỗi 10 giây", f'''
<div class="row" style="gap:36px">
 <div class="col">
  <h3>Quan sát <span class="sub">thứ tự hướng TB, ĐN, ĐB, TN</span></h3>{vec16}
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px 16px;margin-top:10px" class="xs">
   <div><b class="go">1–4</b> hàng chờ / 20</div><div><b style="color:{C["phaseB"]}">5–8</b> số xe / 20</div><div><b class="stop">9–12</b> xe đến hạn chưa vào / 20</div>
   <div><b class="caution">13–15</b> one-hot pha xanh hiện tại</div><div style="grid-column:span 2"><b class="muted">16</b> đã trôi = min(t, 60) / 60</div></div>
  <div class="xs muted" style="margin:6px 0 22px">Hàng chờ 10 → 0,5. Không cắt về [0, 1]: hàng chờ 40 → 2.</div>
  <h3>Hành động và cách thực thi</h3>
  <ul class="dots small"><li>3 hành động ánh xạ sang pha xanh SUMO 0 / 2 / 4 (1 / 3 / 5 là vàng)</li><li>Mỗi bước kéo dài <b>10 giây</b>; đổi pha thì <b>7 giây vàng</b> chạy trước</li><li><b>Xanh tối thiểu 20 giây</b>; yêu cầu đổi sớm thì giữ pha hiện tại</li><li>Xanh thực tế có thể dài hơn tối thiểu vì nhịp 10 giây và đèn vàng</li></ul>
 </div>
 <div style="width:540px;flex:none">
  <div class="panel" style="padding:12px 14px">{mlp("16", dueling=True)}
   <div class="eq" style="font-size:14px">(16·64+64)+(64·64+64)+(64·1+1)+(64·3+3)
= <span class="a">5.508</span> tham số mạng đang học, viết bằng NumPy</div></div>
  <div class="panel caution" style="margin-top:14px;padding:12px 18px"><b>Đọc đầu ra (minh họa).</b> <span class="small">Q = [−3,2; <b>−2,7</b>; −4,1] → hành động 1 → pha xanh SUMO 2, trừ khi pha hiện tại chưa giữ đủ 20 giây xanh.</span></div>
 </div>
</div>''', secs=100, source="src/traffic_rl/sim/sumo_single_junction.py · src/traffic_rl/agents/dqn.py · configs/danang_pilot.yaml", notes=N(
    "Quan sát SUMO có 16 số theo thứ tự hướng tây bắc, đông nam, đông bắc, tây nam: bốn hàng chờ, bốn số đếm xe và bốn số xe đến hạn chưa vào, đều chia cho 20; rồi one-hot của pha xanh hiện tại, và một bộ đếm từ lần đổi đèn gần nhất, chia cho 60. "
    "Mô hình ra ba giá trị Q cho ba pha xanh. Mỗi bước là 10 giây; nếu đổi pha thì 7 giây vàng chạy trước. Xanh tối thiểu là 20 giây; yêu cầu đổi sớm thì giữ pha hiện tại. "
    "Mạng có hai lớp ẩn 64 đơn vị ReLU, rồi tách thành đầu V và A: 5.508 tham số mạng đang học, cài bằng NumPy.",
    ["16 = 4 hàng chờ + 4 số đếm + 4 xe chưa vào + 3 one-hot + 1 đồng hồ", "Bước 10 giây · vàng 7 giây · xanh tối thiểu 20 giây", "16 → 64 → 64 → V/A → 3 Q · 5.508 tham số"],
    ["Không mô tả hành động như đổi đèn tức thì; luôn đi qua vàng và xanh tối thiểu."],
    [("Vì sao đưa xe chưa vào vào trạng thái?", "Để mô hình thấy xe bị chặn ở biên; nếu không, bộ điều khiển có thể trông tốt nhờ giữ xe ở ngoài.")]))

slide("SUMO", "Huấn luyện SUMO: 5 seed × 30 episode, chọn checkpoint trên kiểm định", f'''
<div class="row" style="gap:34px">
 <div class="col">
  <h3>Thưởng và đích 3 bước</h3>
  <div class="eq" style="font-size:14.5px">r<sub>học</sub>(t) = −0,01 × [hàng chờ(t<sub>cuối</sub>) + xe chưa vào(t<sub>cuối</sub>)]
R<sub>3</sub> = r<sub>t</sub> + γ r<sub>t+1</sub> + γ² r<sub>t+2</sub>
y  = R<sub>3</sub> + (1 − done) · γ³ · Q<sub>đích</sub>(o<sub>t+3</sub>, a*)</div>
  <p class="xs" style="margin:6px 0 18px">γ = 0,99 <b>cho mỗi quyết định 10 giây</b>. Thưởng lấy ở cuối mỗi bước; chỉ số chính tích phân mỗi giây. Cùng hướng, không trùng nhau.</p>
  <div class="row" style="gap:26px;margin-bottom:18px">{stat("360", "quyết định mỗi episode")}{stat("10.800", "quyết định mỗi seed")}{stat("120", "lượt kiểm tra chính = 75 đã học + 45 baseline")}</div>
  <div class="panel small" style="padding:12px 16px"><b>Siêu tham số.</b> tốc độ học 0,0003, Adam, Huber δ = 1, cắt gradient 10, bộ nhớ 50.000, batch 64, bắt đầu học từ 256, đồng bộ đích mỗi 200 lần cập nhật, ε từ 1,0 xuống 0,05 trong 5.000 quyết định (khoảng episode 14).</div>
 </div>
 <div style="width:470px;flex:none">
  <h3>Với mỗi seed học 11–15</h3>
  {vchain(["Khởi tạo mạng đang học, chép sang đích, tạo bộ nhớ", "30 episode × 3.600 giây trên <b>AM học</b> (nhu cầu 11 / mô phỏng 11)", "Mỗi 10 giây: ε-tham lam, chạy, chuyển tiếp 3 bước, nhớ, một lần cập nhật",
           "<span style='color:#137257'>Mỗi 5 episode: chạy tham lam trên <b>AM kiểm định</b> (nhu cầu 31 / mô phỏng 31), giữ bản tốt nhất</span>", "<b>Đánh giá checkpoint tốt nhất trên 15 ca kiểm tra</b>, không cập nhật trọng số"])}
  <div class="note" style="margin-top:12px;font-size:15px">Chỉ học trên <b>AM</b>, kiểm tra trên normal, AM và PM.</div>
 </div>
</div>''', secs=75, source="scripts/train_danang_sumo.py · src/traffic_rl/train/trainer.py · configs/danang_pilot.yaml", notes=N(
    "Thưởng là số âm của hàng chờ cộng xe chưa vào ở cuối mỗi bước 10 giây, nhân 0,01. Đích dùng lợi tức 3 bước: ba thưởng đã chiết khấu, rồi ước lượng kiểu Double từ mạng đích. "
    "Mỗi seed học từ 11 đến 15 học 30 episode một giờ trên cùng ca AM: 360 quyết định mỗi episode, 10.800 mỗi seed. Epsilon giảm từ 1 xuống 0,05 trong 5.000 quyết định, khoảng episode 14. "
    "Mỗi 5 episode mô hình chạy tham lam trên AM kiểm định và checkpoint có hàng chờ trung bình thấp nhất được giữ. Checkpoint đó được đánh giá trên 15 ca kiểm tra: tổng 120 lượt chính, 75 đã học và 45 baseline.",
    ["30 episode × 5 seed · kiểm định mỗi 5", "Chỉ học AM · kiểm tra 3 chế độ", "120 lượt = 75 đã học + 45 baseline"],
    ["Không nói mỗi seed học trên dữ liệu khác nhau; học và kiểm định dùng chung."],
    [("30 episode đã hội tụ chưa?", "Đó là ngân sách thí nghiệm; kiểm định chọn checkpoint tốt nhất trong ngân sách đó, chưa chứng minh hội tụ.")]))

slide("SUMO", "Đo cái gì, và so với ai", f'''
<div class="row" style="gap:36px">
 <div class="col">
  <h3>Chỉ số chính: tích phân hàng chờ</h3>
  <div class="eq">I = Σ<sub>t</sub> [Q<sub>mạng</sub>(t) + P<sub>đến hạn</sub>(t)] × Δt     <span class="c">xe-giây</span>
I<sub>xe-giờ</sub> = I<sub>xe-giây</sub> / 3600</div>
  <div style="display:flex;align-items:center;gap:18px;margin:16px 0 8px"><div class="hero" style="font-size:38px">10 xe × 60 giây</div><div class="hero go" style="font-size:38px">= 600 xe-giây</div></div>
  <div class="xs muted" style="margin-bottom:22px">= 1/6 xe-giờ. Chỉ đọc giây cuối thì bỏ mất chi phí trước đó. Tích phân hàng chờ không phải tổng trễ di chuyển.</div>
  <h3>Vì sao cộng xe chưa vào?</h3>
  <div class="eq" style="font-size:14.5px">đã lên lịch = đã đến hạn + chưa phát
chưa vào    = đã đến hạn − đã vào</div>
  <p class="small" style="margin-top:8px">Bộ điều khiển chặn cửa vào sẽ giữ xe ở ngoài và trông “tốt” nếu chỉ đếm xe đã vào. Chỉ xe <b>đã đến hạn nhưng bị chặn</b> được tính, không bao giờ tính xe tương lai.</p>
 </div>
 <div class="col">
  {table(["Bộ điều khiển", "Cách quyết định", "Có học?"], [
      ["<span class='lamp' style='background:#8B97A1'></span><b>Cố định công bố</b>", "SUMO: lịch công bố 103 giây", "Không"],
      ["<span class='lamp' style='background:#8B97A1'></span><b>Cố định đã chỉnh</b>", "CityFlow: lịch lặp, xanh chọn từ 20–60 giây trên kiểm định → 25 giây", "Tìm kiếm"],
      ["<span class='lamp' style='background:#3A74C9'></span><b>Max-Pressure</b>", "Pha có tổng chờ vào trừ chờ ra lớn nhất", "Không"],
      ["<span class='lamp' style='background:#8FB1E3'></span><b>MP có trễ</b>", "Áp lực cộng điều kiện giữ và ngưỡng đổi", "Không"],
      ["<span class='lamp' style='background:#1C9A73'></span><b>Đã học</b>", "Lợi tức chiết khấu được dự đoán", "Có"]], cls="t tight")}
  <h3 style="margin-top:22px">Chỉ số phụ, luôn đọc cùng nhau</h3>
  <div><span class="tag">hoàn thành</span><span class="tag">vào được</span><span class="tag">thời gian đi</span><span class="tag caution">chỉ dấu tràn hàng</span><span class="tag">số lần đổi pha</span><span class="tag stop">va chạm / khẩn</span><span class="tag dark">vi phạm neo</span></div>
  <div class="xs muted" style="margin-top:6px">Thời gian đi chỉ tính chuyến đã hoàn thành, nên có lệch do người còn lại; đọc cùng tỷ lệ hoàn thành.</div>
 </div>
</div>''', secs=85, source="src/traffic_rl/sim/multi_agent_env.py · src/traffic_rl/eval/network_metrics.py · src/traffic_rl/agents/max_pressure.py", notes=N(
    "Chỉ số chính là tích phân hàng chờ: mỗi giây cộng số xe đang chờ trong mạng và số xe đã đến hạn nhưng chưa vào được. Mười xe chờ sáu mươi giây là 600 xe-giây, bằng một phần sáu xe-giờ. "
    "Vì sao cộng xe chưa vào? Bộ điều khiển làm tắc cửa vào sẽ giữ xe ngoài mô phỏng; chỉ đếm xe bên trong thì nó trông tốt. Nhưng chỉ xe đã đến hạn được tính, không tính xe tương lai. Đó từng là lỗi thật ở đầu dự án và đã được sửa. "
    "Baseline là lịch cố định, công bố trong SUMO và chỉnh trên kiểm định trong CityFlow, cùng Max-Pressure và Max-Pressure có trễ. Các chỉ số phụ như hoàn thành, vào được, thời gian đi và tràn hàng được đọc cùng nhau để tránh đánh lừa bằng một chỉ số.",
    ["10 xe × 60 giây = 600 xe-giây", "chưa vào = đã đến hạn − đã vào", "Baseline: cố định · MP · MP có trễ"],
    ["Không gọi tích phân hàng chờ là “tổng trễ”."]))

# ================================================================== CityFlow
divider("CityFlow", 5, "53 nút trong CityFlow", "Làm sao một chính sách sửa 53 lịch mà không phá lịch?", 6.5)

slide("CityFlow", "Ở 53 nút, sửa lịch thay vì chọn pha tự do", f'''
<div class="row" style="gap:36px">
 <div style="width:380px;flex:none">
  <h3 class="stop">Chọn pha tự do ở mọi nút</h3>
  <ul class="dots stop small"><li>Không gian hành vi rất lớn: 53 nút × mọi nhịp</li><li>Có thể phá một nhịp phục vụ vốn ổn định</li><li>Khó kiểm và khó giải thích</li><li>Các bản chọn pha trước đó (V2, V3A) đều trượt cổng</li></ul>
 </div>
 <div class="col">
  <h3 class="go">Residual theo lịch</h3>
  <p class="small" style="margin-bottom:14px">Bắt đầu từ một <b>lịch tham chiếu</b>; mô hình chỉ được làm <b>những sửa nhỏ, kiểm được</b>.</p>
  <div class="row" style="gap:14px">
   <div class="col rule-l go"><div style="font-size:22px;font-weight:850">Lịch</div><div class="xs">một kế hoạch tham chiếu cố định (25 giây)</div></div>
   <div class="col rule-l go"><div style="font-size:22px;font-weight:850">Residual</div><div class="xs">hành động dịch một ranh giới ±10 giây</div></div>
   <div class="col rule-l go"><div style="font-size:22px;font-weight:850">Có neo</div><div class="xs">block kết thúc đúng trạng thái đèn tham chiếu</div></div>
   <div class="col rule-l go"><div style="font-size:22px;font-weight:850">Double DQN</div><div class="xs">mạng đang học chọn, mạng đích chấm</div></div>
  </div>
 </div>
</div>
<div class="row" style="gap:20px;margin-top:34px">
 <div class="note col"><b>Đánh đổi.</b> Không gian chính sách bị giới hạn. Nếu kế hoạch tốt hơn cần thay đổi lớn, residual không với tới.</div>
 <div class="note go col"><b>Normal</b> chạy lịch cố định từ lúc đặt lại, theo thiết kế. <b>AM và PM</b> dùng residual tham lam. Mô hình nhận nhãn giờ đã khai báo; nó không tự phân loại giờ cao điểm.</div>
</div>
<div class="panel" style="margin-top:18px;padding:14px 20px"><span class="small"><b>Macro 0 luôn có sẵn</b> và giữ nguyên lịch tham chiếu. Giá trị Q hòa thì chọn baseline; đặc trưng hoặc điểm không hữu hạn thì lùi về. Mã ca, seed, tên file và lưu lượng tương lai không được đưa vào đặc trưng.</span></div>''',
      secs=70, source="docs/research/haichau-v3b-residual-protocol.md · src/traffic_rl/agents/schedule_residual.py", notes=N(
    "Trên mạng, để chính sách chọn pha tự do ở 53 nút tạo ra không gian hành vi rất lớn và có thể phá một nhịp phục vụ ổn định; các bản chọn pha trước đó đều trượt cổng. "
    "Vì vậy em chuyển sang residual: có một lịch tham chiếu, và mô hình chỉ được chọn các sửa nhỏ. Đọc tên từng chữ: Lịch là kế hoạch tham chiếu cố định; Residual là hành động chỉ là một sửa nhỏ; Có neo nghĩa là mỗi block kết thúc đúng trạng thái đèn tham chiếu; Double DQN là cách nó học. "
    "Cái giá là chính sách bị giới hạn. Macro 0, tức giữ nguyên lịch, luôn hợp lệ, nên trường hợp xấu nhất là baseline. Ở nhu cầu normal, bộ điều khiển chạy cố định theo thiết kế.",
    ["Lịch · Residual · Có neo · Double", "Macro 0 = giữ lịch, luôn hợp lệ", "Đánh đổi: hành vi kiểm được với độ linh hoạt"]))

steps = ["Đầu block: đọc quan sát từng nút", "Dựng lịch tham chiếu (xanh tối thiểu, chuyển pha)", "Macro 0 giữ nguyên lịch",
         "Ứng viên dịch <b>một</b> ranh giới sớm hoặc muộn 10 giây", "ShadowSignal phát lại từng ứng viên và loại cái không hợp lệ", "MLP chấm ứng viên hợp lệ; mỗi nút chọn một",
         "Chạy 30 nhịp 10 giây", "Cuối block: kiểm neo, thu thưởng"]
sth = "".join(f'<div style="display:flex;gap:10px;margin:5px 0;break-inside:avoid"><div class="hero go" style="font-size:22px;width:20px">{i+1}</div><div class="xs" style="padding-top:2px">{s}</div></div>' for i, s in enumerate(steps))
slide("CityFlow", "Một macro: dịch một biên 10 giây, rồi về neo", f'''
<div class="panel" style="padding:12px 14px">{macro_timeline()}</div>
<div class="row" style="gap:26px;margin-top:18px">
 <div style="flex:1.2"><h3>Tám bước trong mỗi block</h3><div style="columns:2;column-gap:22px">{sth}</div></div>
 <div class="col">
  <div class="panel dark" style="padding:16px 20px"><h3>Neo không đặt lại giao thông</h3><div class="small">Neo = pha hiện tại + chuyển pha đang chờ + các đồng hồ. Chỉ <b style="color:#fff">trạng thái bộ điều khiển</b> phải khớp tham chiếu; hàng chờ và vị trí xe đi sang block sau.</div></div>
  <div class="row" style="gap:24px;margin-top:16px">{stat("59", "MAX_MACROS = 1 + 2 × (30 − 1), các ô đệm có mặt nạ")}{stat("0", "yêu cầu trái lệ hoặc lệch neo được chấp nhận; chương trình báo lỗi")}</div>
 </div>
</div>''', secs=100, source="src/traffic_rl/sim/schedule_residual.py (ShadowSignal, bộ biên dịch macro) · trục thời gian chỉ minh họa ý", notes=N(
    "Đây là một block 300 giây. Giả sử lịch tham chiếu chuyển từ pha A sang pha B ở giây 100. Mô hình có thể thử hai ứng viên: chuyển sớm 10 giây, ở giây 90, hoặc muộn 10 giây, ở giây 110, cộng macro 0 là giữ nguyên. "
    "Mỗi ứng viên được ShadowSignal phát lại. ShadowSignal mô phỏng logic đèn, không mô phỏng xe, để kiểm xanh tối thiểu, chuyển pha, và quan trọng nhất là block kết thúc đúng trạng thái đèn tham chiếu, kể cả đồng hồ. Ứng viên không đạt thì bị che đi. "
    "MLP chấm phần còn lại, mỗi nút chọn một, và kế hoạch chạy 30 nhịp 10 giây. "
    "Câu then chốt: neo không đặt lại giao thông. Hai lịch có thể phục vụ xe ở những thời điểm khác nhau trong block, nên hàng chờ khác nhau, dù đèn kết thúc cùng trạng thái. Vì vậy residual vẫn có tác dụng.",
    ["±10 giây tại một biên mỗi block", "ShadowSignal kiểm hợp lệ và neo", "Neo khớp đèn, KHÔNG khớp giao thông"],
    ["Ví dụ 90 / 100 / 110 là minh họa, không phải một macro lấy từ hiện vật."],
    [("Đã về neo thì vì sao hàng chờ vẫn đổi?", "Thời điểm phục vụ bên trong block đổi hàng chờ; giao thông không bị đặt lại, chỉ đồng hồ điều khiển được thẳng lại.")]))

vec27 = '<div style="display:flex;gap:3px">' + "".join(f'<div style="flex:1;height:34px;border-radius:4px;background:{C["go"]}"></div>' for _ in range(12)) + '<div style="width:10px"></div>' + \
    "".join(f'<div style="flex:1;height:34px;border-radius:4px;background:{C["phaseB"]}"></div>' for _ in range(12)) + '<div style="width:10px"></div>' + \
    "".join(f'<div style="flex:1;height:34px;border-radius:4px;background:{C["stop"]}"></div>' for _ in range(3)) + "</div>"
feats = ["trung bình hàng chờ vào", "hàng chờ vào lớn nhất", "trung bình xe đang chạy vào", "trung bình hàng chờ ra", "chỗ trống phía ra (40 − số xe)", "áp lực (vào − ra, trung bình)",
         "có phải pha hiện tại", "xanh đã trôi (giây / 20)", "trung bình hàng chờ thượng lưu", "trung bình hàng chờ hạ lưu", "thời gian từ lần phục vụ (giây / 20)", "số luồng"]
fh = "".join(f'<div class="xs" style="padding:2px 0"><b class="go">{i+1}</b>&nbsp; {f}</div>' for i, f in enumerate(feats))
slide("CityFlow", "27 đặc trưng mỗi macro, một MLP dùng chung cho 53 nút", f'''
<div class="panel" style="padding:14px 18px"><h3>Một macro ứng viên = 12 + 12 + 3</h3>{vec27}
 <div style="display:flex;margin-top:7px;font-size:15px;font-weight:800"><div style="flex:12" class="go">12 đặc trưng pha nguồn</div><div style="flex:12;color:{C["phaseB"]}">12 đặc trưng pha đích</div><div style="flex:3;text-align:right;white-space:nowrap" class="stop">3 mô tả</div></div></div>
<div class="row" style="gap:30px;margin-top:18px">
 <div class="col"><h3>Mười hai đặc trưng của một pha</h3><div style="columns:2;column-gap:18px">{fh}</div>
  <div class="xs muted" style="margin-top:8px">Ba mô tả: biên = nhịp / 30, dịch = ±1, có phải baseline. Macro 0 lấy trung bình các hàng pha hợp lệ với mô tả [0, 0, 1].</div>
  <div class="note go" style="margin-top:12px;font-size:15px"><b>Vì sao đầu ra một số?</b> Số macro hợp lệ đổi theo nút và theo block. Chấm <b>từng ứng viên</b> bằng một hàm và một mặt nạ thì xử lý được mọi kích thước tập hành động.</div></div>
 <div style="width:540px;flex:none"><div class="panel" style="padding:10px 14px">{mlp("27", w=520, h=200)}
  <div class="eq" style="font-size:14px">(27·64+64)+(64·64+64)+(64·1+1) = <span class="a">6.017</span> tham số</div>
  <div class="xs" style="margin-top:8px">Một MLP chấm mọi macro ở mọi nút, rồi mặt nạ và argmax. <b>Không</b> dueling, <b>không</b> mạng đồ thị, <b>không</b> attention: thông tin nút kề đi vào dưới dạng đặc trưng số.</div></div></div>
</div>''', secs=75, source="src/traffic_rl/sim/phase_encoder.py · src/traffic_rl/agents/phase_ddqn.py · src/traffic_rl/agents/schedule_residual.py", notes=N(
    "Mỗi lần sửa liên quan hai pha: pha trước biên là pha nguồn, pha sau biên là pha đích. Mỗi pha được mô tả bằng 12 đặc trưng: trung bình và lớn nhất của hàng chờ vào, xe đang chạy, hàng chờ ra, chỗ trống, áp lực, có phải pha hiện tại, xanh đã trôi, hàng chờ thượng lưu và hạ lưu, thời gian từ lần phục vụ, và số luồng. "
    "Ba số nữa mô tả biên nằm ở đâu trong block, dịch sớm hay muộn, và có phải macro 0 không. Vậy 12 + 12 + 3 = 27. "
    "Một MLP, 27 đến 64 đến 64 đến 1, với 6.017 tham số, chấm mọi ứng viên. Cùng trọng số phục vụ cả 53 nút, nên thêm nút không thêm trọng số. "
    "Thông tin nút kề chỉ là đặc trưng đã tóm tắt; đây không phải mạng đồ thị hay giao tiếp được học.",
    ["27 = 12 nguồn + 12 đích + 3 mô tả", "27 → 64 → 64 → 1 · 6.017 tham số", "Trọng số dùng chung khác mạng đồ thị"],
    ["Không gọi đây là giao tiếp đa tác nhân hay mạng nơ-ron đồ thị."],
    [("53 tác nhân có giao tiếp không?", "Chúng thấy tóm tắt hàng chờ thượng lưu và hạ lưu, dùng chung trọng số và một thưởng toàn mạng; đó không phải giao tiếp được học.")]))

slide("CityFlow", "Huấn luyện residual: thưởng toàn mạng, 12 episode, 6 ca cao điểm", f'''
<div class="row" style="gap:34px">
 <div class="col">
  <h3>Thưởng của một macro, trên cả mạng</h3>
  <div class="eq" style="font-size:14.5px">r<sub>thô</sub>    = −[I(t + 300) − I(t)]      <span class="c">xe-giây, hàng chờ + chưa vào</span>
r<sub>chấm</sub> = r<sub>thô</sub> / 100.000</div>
  <p class="xs" style="margin:6px 0 16px">Ví dụ: trung bình 500 xe trong 300 giây = 150.000 xe-giây → r<sub>chấm</sub> = −1,5. Cùng thưởng đó đi vào cả 53 chuyển tiếp, và chi phí của baseline <b>không</b> bị trừ đi.</p>
  <h3>Đích theo thời lượng (SMDP)</h3>
  <div class="eq" style="font-size:14.5px">y = r<sub>chấm</sub> + (1 − done) · γ<sup>Δt/300</sup> · Q<sub>đích</sub>(o′, a*)</div>
  <p class="xs" style="margin:6px 0 16px">γ = 0,99 <b>cho mỗi 300 giây</b>, khác 0,99 cho mỗi 10 giây ở SUMO.</p>
  <div class="panel caution small" style="padding:12px 16px"><b>Khởi tạo.</b> Đầu ra W3 và b3 bắt đầu bằng 0, nên mọi Q ban đầu bằng nhau và chính sách tham chọn macro 0. <b>ε cố định = 0,15</b> để thăm các macro khác. Không có hàm mất mát bắt chước.</div>
 </div>
 <div style="width:480px;flex:none">
  <div class="row" style="gap:22px;margin-bottom:16px">{stat("7.632", "chuyển tiếp mỗi seed, AM 3.816 + PM 3.816", "go")}{stat("1.152", "lần cập nhật = 12 × 12 × 8", "ink")}</div>
  {table(["Mỗi seed học", "Giá trị"], [["Episode", "12 × 3.600 giây"], ["Block mỗi episode", "12"], ["Chuyển tiếp mỗi block", "53"], ["Batch, bộ nhớ, bắt đầu", "128; 20.000; ≥ 53"],
       ["Chép mạng đích", "mỗi 64 lần cập nhật (8 block)"], ["Kiểm định, checkpoint", "mỗi 4 episode → ep 4, 8, 12"]], cls="t tight")}
  <div class="note stop" style="margin-top:12px;font-size:15px">Có chín ca học, nhưng chỉ <b>sáu ca cao điểm</b> (3 AM + 3 PM) được dùng để học residual, mỗi ca hai lần. 7.632 chuyển tiếp <b>tương quan mạnh</b>, không phải 7.632 thí nghiệm.</div>
 </div>
</div>''', secs=75, source="src/traffic_rl/train/schedule_residual_trainer.py · docs/research/evidence-snapshot-2026-09-23/seed14-resolved-config.json", notes=N(
    "Thưởng của một macro là phần tăng âm của tích phân hàng chờ toàn mạng trong 300 giây, gồm xe chưa vào, chia cho 100.000 để đưa về thang dùng được. Ví dụ 500 xe chờ trung bình trong 300 giây là 150.000 xe-giây, thưởng chấm là −1,5. "
    "Thưởng này là của cả mạng, giống nhau cho cả 53 chuyển tiếp, và không trừ chi phí của baseline. Chữ “residual” chỉ mô tả hành động. "
    "Đích được viết theo thời lượng macro, với gamma 0,99 cho mỗi 300 giây. Đầu ra bắt đầu bằng không nên lúc đầu mô hình chọn macro 0, và epsilon cố định 0,15 để khám phá. "
    "Mỗi seed học 12 episode trên 6 ca cao điểm: 7.632 chuyển tiếp và 1.152 lần cập nhật. Mỗi 4 episode một checkpoint được lưu và kiểm định; “step-4” nghĩa là sau episode 4.",
    ["Thưởng = −Δ(hàng chờ + chưa vào) cả mạng / 100.000", "12 ep · 7.632 chuyển tiếp · 1.152 cập nhật", "step-4 = episode 4"],
    ["Không phải “8 cập nhật × 53 nút”: 8 cập nhật cho mỗi block của cả mạng."],
    [("Thưởng toàn cục có gì hạn chế?", "Nó khớp mục tiêu hợp tác nhưng khó gán công; thưởng cục bộ hoặc thưởng chênh lệch là việc sau.")]))

gates = ["Normal khớp cố định từng ca, không lệch pha hay đồng hồ", "Hối tiếc hàng chờ trung bình của mỗi chế độ cao điểm ≤ 0", "Hối tiếc cao điểm trung bình ≤ −1%",
         "Mất hoàn thành và vào được mỗi ca ≤ 2 điểm phần trăm", "Có macro đã học ở cả AM và PM, tại ≥ 2 nút", "0 yêu cầu trái lệ, 0 vi phạm neo, macro 0 ép = cố định 25",
         "Checkpoint phản ứng khi đặc trưng giao thông đổi"]
seedcards = "".join(f'''<div class="col" style="text-align:center;padding:14px 4px;border-radius:12px;background:{"#DDF1E9" if ok else "#F8E1DE"}">
 <div class="xs muted">seed</div><div class="hero" style="font-size:44px;color:{C["go"] if ok else C["stop"]}">{s}</div>
 <div style="font-weight:850;font-size:15px;color:{C["go"] if ok else C["stop"]};margin-top:6px">{st}</div><div class="xs muted">{ep}</div></div>'''
                    for s, st, ep, ok in [("12", "được chọn", "episode 8", True), ("13", "bị loại", "ep 12, chẩn đoán", False), ("14", "được chọn", "episode 4", True),
                                          ("15", "được chọn", "episode 8", True), ("16", "bị loại", "ep 4, chẩn đoán", False)])
slide("CityFlow", "Học xong chưa phải được chấp nhận: bộ chọn trên kiểm định", f'''
{chain([("Học xong", "đã có trọng số và nhật ký"), ("Bộ chọn V1 nhận", "một checkpoint đủ điều kiện của seed đó"), ("Bộ kiểm phát hành chặt", "cả gói bằng chứng")])}
<div class="row" style="gap:34px;margin-top:22px">
 <div class="col"><h3>Bộ chọn V1 kiểm trên tập kiểm định</h3><ul class="dots small">{"".join(f"<li>{g}</li>" for g in gates)}</ul>
  <div class="xs muted" style="margin-top:6px">Xếp theo hối tiếc cao điểm trung bình; hòa thì lấy checkpoint sớm hơn. Nếu không cái nào qua, nó <b>đóng thất bại</b> thay vì lấy cái ít xấu nhất.</div></div>
 <div style="width:560px;flex:none">
  <div class="row" style="gap:8px">{seedcards}</div>
  <div class="note stop" style="margin-top:16px;font-size:15.5px">Seed 13 và 16 bị loại. Số kiểm tra dương về sau <b>không</b> đảo quyết định kiểm định. Các cổng là ngưỡng thực nghiệm, không phải kiểm định không kém hơn.</div>
  <div class="note ink" style="margin-top:10px;font-size:15.5px">Bộ kiểm chặt: <b>complete = false</b>, còn 14 cổng phát hành mở (kiểm ngày 23 tháng 9).</div>
 </div>
</div>''', secs=60, source="configs/haichau_residual_final_selection_v1.yaml · docs/research/evidence-snapshot-2026-09-23/seed*-selection.json", notes=N(
    "Em tách ba trạng thái: đã học xong, bộ chọn đã nhận, và phát hành chặt. Bộ chọn V1 chạy trên kiểm định và kiểm: normal khớp cố định từng ca; hối tiếc mỗi chế độ cao điểm không dương và trung bình giảm ít nhất 1 phần trăm; hoàn thành và vào được không giảm quá 2 điểm phần trăm; macro đã học xuất hiện ở cả AM và PM; và hợp đồng thực thi không bao giờ bị vi phạm. "
    "Nếu không cái nào qua, nó đóng thất bại. Kết quả: seed 12, 14 và 15 được chọn; 13 và 16 bị loại. Em vẫn báo hai seed đó như chẩn đoán, nhưng không đảo quyết định. "
    "Bộ kiểm phát hành chặt chưa hoàn tất, còn 14 cổng mở. Em nói thẳng điều này.",
    ["3 trạng thái: đã học → được chọn → được phát hành", "Seed 12 / 14 / 15 được chọn · 13 / 16 bị loại", "Đóng thất bại · phát hành chặt chưa xong"]))

# ================================================================== Results
divider("Kết quả", 6, "Bằng chứng cho thấy gì", "Học có ích ở đâu, gây hại ở đâu, và ai thắng trên mạng?", 7, lit="caution")

sumo_series = [("Cố định công bố", C["base"]), ("Dueling DDQN, 5 seed", C["go"]), ("Max-Pressure", C["pressure"]), ("MP có trễ", C["pressure2"])]
sumo_vals = [[9.86, 79.20, 152.67], [41.50, 78.41, 99.97], [140.72, 352.43, 269.02], [126.85, 281.52, 241.40]]
slide("Kết quả", "SUMO: thắng rõ ở PM, hòa ở AM, thua ở normal", f'''
<div class="row" style="gap:0;margin-bottom:14px">
 <div class="col" style="border-left:6px solid {C["stop"]};padding-left:18px"><div class="hero stop" style="font-size:64px">+320,7%</div><div class="small"><b>Normal</b> 9,86 → 41,50 xe-giờ, KTC [7,60; 56,14]</div></div>
 <div class="col" style="border-left:6px solid {C["caution"]};padding-left:18px"><div class="hero caution" style="font-size:64px">−1,0%</div><div class="small"><b>AM</b> 79,20 → 78,41 xe-giờ, KTC [−9,47; 8,49]</div></div>
 <div class="col" style="border-left:6px solid {C["go"]};padding-left:18px"><div class="hero go" style="font-size:64px">−34,5%</div><div class="small"><b>PM</b> 152,67 → 99,97 xe-giờ, KTC [−69,55; −35,34]</div></div>
</div>
<div class="row" style="gap:30px">
 <div style="width:660px;flex:none">{legend(sumo_series, 13.5)}{grouped_bars(["Normal", "Cao điểm AM", "Cao điểm PM"], sumo_series, sumo_vals, 400, w=660, h=300, unit="hàng chờ + chưa vào, xe-giờ")}</div>
 <div class="col">
  <h3>Cách đọc</h3>
  <ul class="dots small"><li><b class="go">PM:</b> giảm rõ; khoảng tin cậy không chứa 0</li><li><b class="caution">AM:</b> trung bình bằng cố định; khoảng chứa 0</li><li><b class="stop">Normal:</b> xấu hơn nhiều, nên không có cơ sở chạy RL ở mọi chế độ</li><li>Cả hai baseline áp lực đều thua cố định tại nút này</li></ul>
  <p class="xs muted" style="margin-top:10px">Khoảng tin cậy của (đã học − cố định) theo xe-giờ: bootstrap ghép cặp trên 5 hiệu ứng seed, 20.000 lần lấy lại. Hoàn thành DDQN 93,5 / 91,8 / 89,7% so với cố định 98,1 / 89,6 / 82,8%.</p>
 </div>
</div>''', secs=120, kind="results", source="SUMO · dueling_n3 · 5 seed học × 15 ca kiểm tra · tích phân hàng chờ + chưa vào (xe-giờ) · results/danang_protocol_v1/summary/final-summary.csv", notes=N(
    "Đây là kết quả SUMO trên 15 ca kiểm tra, trung bình trên năm seed học. Ở PM, lịch cố định tích được 152,67 xe-giờ và mô hình 99,97: giảm 34,5 phần trăm, khoảng tin cậy của hiệu số nằm hoàn toàn dưới không. "
    "Ở AM, chế độ mô hình được học, trung bình gần như bằng lịch cố định và khoảng chứa không. Ở normal, mô hình rõ ràng xấu hơn: 41,5 so với 9,86, tăng 320,7 phần trăm. "
    "Cả hai baseline áp lực đều xấu hơn cố định ở cả ba chế độ. Kết luận: lợi ích phụ thuộc chế độ; kết quả không ủng hộ chạy học tăng cường vô điều kiện mọi lúc. "
    "Khoảng tin cậy là bootstrap trên năm hiệu ứng seed, không phải trên 75 ô.",
    ["PM −34,5% · AM −1,0% (khoảng chứa 0) · Normal +320,7%", "KTC = bootstrap trên 5 hiệu ứng seed", "MP và MP có trễ thua cố định trong SUMO"],
    ["Không chỉ báo PM; luôn nói normal xấu hơn."],
    [("Vì sao normal xấu hơn?", "Chính sách chỉ học trên AM; lệch phân phối hoặc thời điểm hành động là giả thuyết, chưa được ablation xác lập.")]))

slide("Kết quả", "Đọc kết quả SUMO: giả thuyết, ablation và an toàn mô phỏng", f'''
<div class="row" style="gap:34px">
 <div style="width:600px;flex:none"><img class="fig" src="{img("curves")}" style="width:600px;height:340px;object-fit:contain">
  <div class="cap">Hàng chờ trung bình trên kiểm định theo episode của năm seed học. Checkpoint tốt nhất có thể đến trước episode cuối; seed 13 dao động mạnh.</div></div>
 <div class="col">
  <div class="rule-l stop" style="margin-bottom:14px"><b>Vì sao normal xấu: chỉ là giả thuyết.</b><div class="small">Chỉ học trên AM gợi ý lệch phân phối, quá khớp hoặc thời điểm hành động. <b>Chưa</b> được ablation xác lập.</div></div>
  <div class="rule-l pressure" style="margin-bottom:14px"><b>Vì sao Max-Pressure chịu ở đây.</b><div class="small">Chỉ quan sát bốn luồng, và mỗi lần đổi mất 7 giây giải tỏa trên nhịp 10 giây. Điều này không bác bỏ lý thuyết áp lực.</div></div>
  <div class="rule-l caution" style="margin-bottom:14px"><b>Ablation seed 11.</b><div class="small">Kiểm định tốt nhất: dqn_base ≈ 81,43, dueling_n3 ≈ 71,71. Dueling và n-step đổi <b>cùng lúc</b>, một seed, nên không tách được đóng góp.</div></div>
  <div class="rule-l go"><b>Sự cố an toàn trong mô phỏng.</b><div class="small">120 lượt chính: <b>0 va chạm, 0 khẩn cấp</b>. 120 lượt nhạy cảm: 0 va chạm, 4 khẩn cấp. Không phải giấy chứng nhận an toàn hiện trường.</div></div>
 </div>
</div>''', secs=60, kind="results", source="results/danang_protocol_v1/summary/validation-learning-curves.png · paper/thesis_danang.tex, phần Kết quả", notes=N(
    "Đường kiểm định cho thấy checkpoint tốt nhất không phải lúc nào cũng là episode cuối, và seed 13 dao động mạnh. Vì vậy checkpoint được chọn trên kiểm định. "
    "Normal có thể xấu hơn vì chính sách chỉ học trên AM, nhưng đó là giả thuyết chưa có ablation phía sau. Max-Pressure chịu vì chỉ quan sát bốn luồng và mỗi lần đổi mất 7 giây giải tỏa. "
    "Ablation seed 11 cho thấy dueling n3 hơn mô hình nền trên kiểm định, nhưng đổi hai thành phần cùng lúc trên một seed, nên em không tách đóng góp của từng cái. "
    "Về an toàn mô phỏng: 120 lượt chính không có va chạm và không có sự kiện khẩn cấp.",
    ["Checkpoint tốt nhất khác episode cuối", "MP chịu: quan sát thiếu + 7 giây giải tỏa", "0 va chạm / 0 khẩn cấp trong 120 lượt"]))

slide("Kết quả", "Thứ hạng baseline có phải may mắn? 1.000 hiện thực nhu cầu, không RL", f'''
<div class="row" style="gap:0;margin-bottom:12px">
 <div class="col" style="border-left:6px solid {C["base"]};padding-left:16px"><div class="hero" style="font-size:44px">3.000 / 3.000</div><div class="small">Cố định &lt; <b>Max-Pressure</b> ở mọi cặp hiện thực</div></div>
 <div class="col" style="border-left:6px solid {C["base"]};padding-left:16px"><div class="hero" style="font-size:44px">2.999 / 3.000</div><div class="small">Cố định &lt; <b>MP có trễ</b></div></div>
 <div class="col" style="border-left:6px solid {C["caution"]};padding-left:16px"><div class="hero caution" style="font-size:44px">100 · 76 · 88%</div><div class="small">MP có trễ &lt; MP thường ở normal · AM · PM; đa đỉnh ở cao điểm</div></div>
</div>
<img class="fig" src="{img("mc")}" style="width:1136px;height:400px;object-fit:contain">
<div class="cap">9.000 lượt SUMO = 1.000 hiện thực ghép cặp (seed nhu cầu, seed SUMO) × 3 chế độ × 3 baseline, hàng chờ + chờ vào (xe-giờ). Giờ xuất phát giữ nguyên số xe của <b>một</b> hồ sơ quan sát, không phải 1.000 ngày giao thông. Seed tách khỏi huấn luyện / kiểm định / kiểm tra. Không gồm mô hình học (chi phí huấn luyện).</div>''', secs=45, kind="results", source="SUMO · scripts/run_danang_baseline_mc.py · results/danang_baseline_mc/summary.json · parity: tái lập đúng ca kiểm tra AM-101", notes=N(
    "Thứ hạng baseline có phải do năm hiện thực kiểm tra tình cờ không? Em chạy lại riêng ba baseline không học trên 1.000 hiện thực nhu cầu mới cho mỗi chế độ: 9.000 lượt SUMO, mỗi bộ điều khiển thấy cùng giờ xuất phát và cùng seed SUMO. "
    "Cố định thắng Max-Pressure thường ở cả 3.000 cặp và thắng MP có trễ ở 2.999 trên 3.000. MP có trễ thắng MP thường mọi lần ở normal, 76 phần trăm ở AM và 88 phần trăm ở PM, nhưng ở cao điểm nó đa đỉnh: mỗi lượt khóa vào một kiểu chu kỳ pha khác nhau. "
    "Trung vị của cố định là 9,9, 78,5 và 149,3 xe-giờ, gần với trung bình 15 ca là 9,9, 79,2 và 152,7, nên bảng chính không đến từ các ca may mắn. "
    "Đây là các hiện thực của một hồ sơ quan sát, không phải 1.000 ngày, và mô hình học không nằm trong thí nghiệm này.",
    ["9.000 lượt = 1.000 × 3 chế độ × 3 baseline", "Cố định < MP 3.000/3.000 · < MP có trễ 2.999/3.000", "Một hồ sơ quan sát, không phải 1.000 ngày · không RL"],
    ["Không nói 1.000 lượt có cả mô hình học.", "Không gọi là 1.000 ngày giao thông độc lập."],
    [("Sao không chạy DQN 1.000 lần?", "Chi phí huấn luyện quá lớn; kết quả mô hình học giữ ở 5 seed × 15 ca. Thí nghiệm này chỉ kiểm tra thứ hạng baseline có ổn định không."),
     ("Sao MP có trễ phân tán mạnh?", "Luật giữ pha làm chuỗi pha phụ thuộc đường đi, nên thay đổi nhỏ về giờ xuất phát khóa nó vào các chu kỳ khác nhau; các dải trên biểu đồ chính là các chu kỳ đó.")]))

cf_rows = [("Cố định chỉnh", 8339.43, C["base"], "mốc, 0%"), ("Max-Pressure", 6347.00, C["pressure"], "−23,89%, tốt nhất"),
           ("MP có trễ", 6739.13, C["pressure2"], "−19,19%"), ("Residual s14", 7829.25, C["go"], "−6,12%")]
slide("Kết quả", "CityFlow: Max-Pressure vẫn tốt nhất; residual giảm 6,12% so với cố định", f'''
<div class="row" style="gap:34px">
 <div style="width:660px;flex:none">
  <h3>Tổng chi phí hàng chờ trên 15 ca <span class="sub">xe-giờ</span></h3>
  {hbars(cf_rows, 8800, w=660, row_h=76, label_w=190)}
 </div>
 <div class="col">
  <div class="row" style="gap:24px;margin-bottom:18px">{stat("−23,89%", "Max-Pressure", "pressure", 44)}{stat("−6,12%", "Residual, một chính sách", "go", 40)}</div>
  {table(["Giảm gộp so với cố định", "Normal", "AM", "PM"], [["Max-Pressure", "26,72%", "23,85%", "22,66%"], ["MP có trễ", "<b>35,60%</b>", "9,95%", "17,37%"],
        ["Residual s14", "0% (cố định)", "3,48%", "<b>10,39%</b>"]], cls="t tight", align=["", "r", "r", "r"], rowcls={2: "go"})}
  <div class="note stop" style="margin-top:16px;font-size:15.5px">Đây là <b>một chính sách</b> (seed 14, episode 4). 6,12% không phải trung bình năm seed, và giá trị tuyệt đối không so được với SUMO.</div>
 </div>
</div>''', secs=100, kind="results", source="CityFlow · residual seed 14 / episode 4 · 15 ca ghép cặp × 3.600 giây · hàng chờ + chưa vào, xe-giờ · giảm gộp so với cố định đã chỉnh · final15-controller-matrix-summary.json", notes=N(
    "Trên mạng 53 nút, đây là ma trận 15 ca của một chính sách: seed 14, checkpoint episode 4. Tổng chi phí hàng chờ của cố định đã chỉnh là 8.339 xe-giờ; residual đưa xuống 7.829, giảm 6,12 phần trăm. "
    "Nhưng Max-Pressure giảm 23,89 phần trăm và Max-Pressure có trễ giảm 19,19 phần trăm. Vậy Max-Pressure là bộ điều khiển tốt nhất theo chi phí hàng chờ trong ma trận này. "
    "Theo chế độ, residual bằng cố định ở normal theo thiết kế, giảm 3,48 phần trăm ở AM và 10,39 phần trăm ở PM. Câu đúng: residual tốt hơn cố định nhưng không thắng các baseline áp lực. "
    "Đó là một chính sách, không phải trung bình năm seed.",
    ["Cố định 8.339 · MP 6.347 · MP trễ 6.739 · Residual 7.829", "MP −23,89% thắng residual −6,12%", "Một chính sách: seed 14, episode 4"],
    ["Không nói “học tăng cường tốt nhất” trên mạng."],
    [("Vì sao Max-Pressure thắng?", "Có thể do ngân sách học, khó gán công khi thưởng toàn cục, và không gian hành động residual bị giới hạn; chưa có ablation xếp hạng các nguyên nhân này.")]))

slide("Kết quả", "Hàng chờ giảm chưa có nghĩa mọi chỉ số đều tốt hơn", f'''
<div class="row" style="gap:36px">
 <div class="col">
  {table(["Trung bình 15 ca", "Cố định", "Residual s14", "Đổi"], [
      ["Hoàn thành", "66,92%", "67,98%", "<b class='go'>+1,06 điểm</b>"], ["Vào được", "97,15%", "97,97%", "<b class='go'>+0,82 điểm</b>"],
      ["Thời gian đi đã xong", "737,81 giây", "743,26 giây", "<b class='stop'>+5,45 giây</b>"], ["Chỉ dấu tràn hàng", "1.432,33 làn-giây", "1.497,53 làn-giây", "<b class='stop'>+65,20 làn-giây</b>"]], cls="t", align=["", "r nw", "r nw", "nw"])}
  <div class="note" style="margin-top:18px">Thời gian đi chỉ đếm chuyến đã hoàn thành. Khi tỷ lệ hoàn thành tăng, tập chuyến đổi, nên một số không thể nói mọi xe đều đi chậm hơn.</div>
 </div>
 <div class="col">
  <h3>Hai phần trăm đúng cho PM, seed 14</h3>
  <div class="eq" style="font-size:14px">trung bình từng ca = TB<sub>c</sub> 100 · (F<sub>c</sub> − L<sub>c</sub>) / F<sub>c</sub>
gộp              = 100 · (ΣF − ΣL) / ΣF</div>
  <div class="row" style="gap:30px;margin:20px 0">{stat("8,86%", "giảm trung bình từng ca", "go", 52)}{stat("10,39%", "giảm gộp", "go", 52)}</div>
  <p class="small">Ví dụ: cố định 100 và 1.000, đã học 90 và 800 → trung bình 15%, gộp 19,09%. <b>Cả hai đều đúng</b>; gộp đặt nặng hơn lên các ca lớn.</p>
 </div>
</div>''', secs=70, kind="results", source="CityFlow · seed 14 / ep 4 · 15 ca · final15-seed14-secondary-summary.json", notes=N(
    "Chỉ số phụ cho thấy một sự đánh đổi. Hoàn thành tăng khoảng một điểm phần trăm và vào được tăng 0,8 điểm, nên hàng chờ không giảm nhờ chặn xe. Nhưng thời gian đi của chuyến đã xong tăng 5,45 giây và chỉ dấu tràn hàng tăng 65 làn-giây. "
    "Thời gian đi có lệch người sống sót: khi nhiều chuyến hoàn thành hơn, tập chuyến đang được lấy trung bình đổi theo. "
    "Câu hay bị hỏi: vì sao PM có hai số, 8,86 và 10,39 phần trăm? 8,86 là trung bình các phần trăm từng ca, mỗi ca nặng như nhau; 10,39 tính trên tổng, nên ca nặng được tính nhiều hơn. Cả hai đều là câu trả lời đúng cho hai câu hỏi khác nhau.",
    ["Hoàn thành +1,06 · vào được +0,82 điểm", "Thời gian đi +5,45 giây · tràn hàng +65 làn-giây", "8,86% trung bình ca với 10,39% gộp"]))

slide("Kết quả", "Thăm dò: residual chỉ ở PM, trên năm seed học", f'''
<div class="row" style="gap:34px">
 <div style="width:610px;flex:none">
  <h3>Giảm gộp trên 15 ca <span class="sub">normal → cố định, AM → cố định, PM → residual</span></h3>
  {gate_chart(w=610, h=330)}
  <div class="xs muted">Đặc = được chọn; viền đứt = checkpoint chẩn đoán sau khi bị loại; <b class="caution">nét đứt vàng = trung bình 3,48%</b>, dải = KTC 95% [2,01; 4,95].</div>
 </div>
 <div class="col">
  <div class="row" style="gap:24px;margin-bottom:22px">{stat("3,48%", "trung bình năm seed", "caution", 50)}{stat("1,03–5,62%", "khoảng các seed", "ink", 36)}</div>
  <div class="row" style="gap:24px;margin-bottom:20px">{stat("15 / 25", "ô PM tốt hơn", "go", 40)}{stat("10 / 25", "ô PM xấu hơn cố định", "stop", 40)}</div>
  <p class="small">KTC bootstrap theo seed 95% là <b>[2,01%; 4,95%]</b>, 10.000 lần lấy lại. 50 ô normal và AM bằng cố định theo thiết kế.</p>
  <div class="note stop" style="margin-top:14px;font-size:15.5px"><b>Hậu nghiệm.</b> Cổng được chọn <b>sau khi đã thấy kết quả kiểm tra</b> và dùng checkpoint chẩn đoán của seed 13 và 16. Khoảng tin cậy dương <b>không</b> xóa lệch chọn, nên cần một kiểm tra độc lập mới.</div>
 </div>
</div>''', secs=75, kind="results", source="CityFlow · 5 seed học × 15 ca · giảm gộp so với cố định · final15-regime-gated-direct-multi-seed-summary.json · thăm dò", notes=N(
    "Vì residual giúp nhiều nhất ở PM, em phân tích thêm một cổng: normal và AM chạy cố định, chỉ PM dùng residual, cho cả năm seed học. "
    "Mức giảm trung bình là 3,48 phần trăm trên 15 ca, từ 1,03 đến 5,62 phần trăm, với khoảng bootstrap theo seed từ 2,01 đến 4,95 phần trăm. Nhưng trong 25 ô PM, 10 ô vẫn xấu hơn cố định. "
    "Quan trọng nhất, đây là phân tích thăm dò làm sau khi đã thấy kết quả kiểm tra, và có cả hai seed bị loại. Khoảng dương không xóa lệch chọn. Để thành kết luận đã xác nhận, cổng phải được đóng băng rồi chạy trên một tập kiểm tra mới.",
    ["Trung bình 3,48% · KTC [2,01; 4,95] · khoảng 1,03–5,62", "10 / 25 ô PM vẫn xấu hơn", "HẬU NGHIỆM — cần kiểm tra mới"],
    ["Không trình bày đây là kết quả chính hay kết quả đã xác nhận."],
    [("Trung bình dương nhưng 10 trên 25 vẫn xấu?", "Phần được ở các ca tốt nặng hơn phần mất ở các ca xấu; trung bình dương không bảo đảm từng ca. Kiểm tra mới cần một ngưỡng từng ca đặt trước.")]))


# ================================================================== Wrap-up
divider("Kết luận", 7, "Demo và kết luận", "Hôm nay em được kết luận gì, và bước tiếp là gì?", 6)

demo_steps = [("15 giây", "Cả mạng", "53 đèn điều khiển từ topology OSM; nhu cầu và lịch là mô phỏng."),
              ("20 giây", "Đặt lại góc xem", "Cùng ca PM, nhu cầu 105 / mô phỏng 205, đồng bộ thời gian; seed 14, episode 4."),
              ("20 giây", "Khung 1.085 giây (18:05)", "Nút 420249521: cố định có 14 xe chờ, residual có 1, nên ít hơn 13 xe tại thời điểm này."),
              ("20 giây", "Phát và các nút liên kết", "Hàng chờ và đèn theo thời gian; xem các nút kề."),
              ("15 giây", "Quay lại bảng tổng", "Một khung chỉ minh họa hành vi; kết luận dựa trên đánh giá đủ giờ, nhiều ca.")]
dh = "".join(f'<div style="display:flex;gap:14px;margin:9px 0"><div class="hero go" style="font-size:20px;width:70px;flex:none">{t}</div><div class="small"><b>{a}.</b> {b}</div></div>' for t, a, b in demo_steps)
slide("Kết luận", "Demo: phát lại có truy vết ca PM nhu cầu 105", f'''
<div class="row" style="gap:30px">
 <div style="width:620px;flex:none"><img class="fig" src="{img("demo")}" style="width:620px;height:auto">
  <div class="cap">Demo trên trình duyệt: cố định đã chỉnh (trái) và residual theo lịch (phải) tại mốc 18:05 đã trôi. Mở bằng <span class="mono">python3 launch_demo.py --no-browser --port 8766</span>.</div></div>
 <div class="col"><h3>Kịch bản 90 giây</h3>{dh}
  <div class="note" style="margin-top:12px;font-size:14.5px"><b>18:05</b> là 18 phút 5 giây đã trôi, không phải 6 giờ chiều. Đo đạc phủ 0–1.200 giây. Trình duyệt <b>không</b> học và không mô phỏng. “Ít hơn 13 xe chờ” không bằng “thả thêm 13 xe”.</div></div>
</div>''', secs=120, source="results/haichau_network_v2/demo-visual/manifest.json · docs/defense/demo-runbook.md", notes=N(
    "[Chuyển sang trình duyệt nếu demo đã mở; nếu không thì dùng ảnh này.] "
    "Đây là mạng 53 nút dựng từ OSM; nhu cầu và lịch là mô phỏng. Em bấm đặt lại góc xem: hai bên cùng ca PM, nhu cầu 105 và seed mô phỏng 205, đồng bộ thời gian; bên phải là residual, seed 14, episode 4. "
    "Tại phút thứ 18 và 5 giây của mô phỏng, ở nút 420249521, cố định có 14 xe chờ và residual có 1, tức ít hơn 13 xe tại thời điểm này. Em bấm phát và các nút liên kết để chỉ nút kề. "
    "Cuối cùng em quay lại bảng tổng: khung này chỉ minh họa hành vi; kết luận định lượng đến từ đánh giá đủ giờ, nhiều ca. Đây là bản ghi phát lại; trình duyệt không huấn luyện và không chạy mô phỏng.",
    ["PM nhu cầu 105 / mô phỏng 205 · seed 14 ep 4", "Nút 420249521: 14 so với 1 lúc 18:05", "Phát lại đã ghi; kết bằng bảng tổng"],
    ["Không gọi 18:05 là giờ đồng hồ.", "Không suy ra đã thả thêm 13 xe."],
    [("Demo có chạy học tăng cường trực tiếp không?", "Không. Đó là bản ghi phát lại; chỉ số cuối đến từ một đánh giá 3.600 giây riêng.")]))

can = ["RL giảm hàng chờ ở <b>PM</b> trên tập kiểm tra SUMO (−34,5%, khoảng không chứa 0)", "Lợi ích <b>phụ thuộc chế độ</b>; normal rõ ràng xấu hơn",
       "Residual 53 nút giảm 6,12% so với cố định đã chỉnh <b>cho một chính sách</b>", "Max-Pressure thắng residual trong ma trận hiện có",
       "Residual giữ hợp đồng thực thi: 0 yêu cầu trái lệ, 0 vi phạm neo", "Một chuỗi truy được từ nguồn đến cấu hình, checkpoint và kết quả"]
cannot = ["RL thắng cố định ở mọi thời điểm trong ngày", "Đỉnh ngành, hoặc thắng baseline mạnh trên mạng", "Cổng chỉ-PM 3,48% là kết quả đã xác nhận",
          "Hiệu quả ngoài đường hoặc sẵn sàng triển khai", "Ngày camera đại diện nhiều ngày hoặc nhiều mùa", "Mã băm khớp hoặc khoảng tin cậy dương nghĩa là triển khai an toàn"]
slide("Kết luận", "Em được kết luận gì, và không được kết luận gì", f'''
<div class="row" style="gap:36px">
 <div class="col"><div style="display:flex;align-items:center;gap:12px;margin-bottom:10px"><span class="lamp" style="width:26px;height:26px;background:{C["go"]}"></span><h3 style="margin:0;font-size:24px">Bằng chứng hiện có nâng đỡ</h3></div><ul class="dots" style="font-size:19px">{"".join(f'<li style="margin:10px 0">{x}</li>' for x in can)}</ul></div>
 <div class="col"><div style="display:flex;align-items:center;gap:12px;margin-bottom:10px"><span class="lamp" style="width:26px;height:26px;background:{C["stop"]}"></span><h3 style="margin:0;font-size:24px">Không kết luận</h3></div><ul class="dots stop" style="font-size:19px">{"".join(f'<li style="margin:10px 0">{x}</li>' for x in cannot)}</ul></div>
</div>
<div class="panel dark" style="margin-top:28px;font-size:19px">Khung đúng: một nghiên cứu <b style="color:#6FD3B0">phát triển hệ thống và đánh giá mô phỏng có phân tích thất bại</b>. Mô hình, cài đặt, thí nghiệm, nguồn và giới hạn đều được đưa ra.</div>''', secs=85, notes=N(
    "Để Hội đồng dễ đối chiếu, em tách hai cột. Được nâng đỡ: học tăng cường giảm hàng chờ PM trong SUMO; lợi ích phụ thuộc chế độ; residual giảm 6,12 phần trăm so với cố định cho một chính sách; Max-Pressure thắng residual; residual giữ hợp đồng; và có chuỗi truy vết. "
    "Không kết luận: RL thắng mọi lúc, thắng baseline mạnh, cổng chỉ-PM đã xác nhận, hiệu quả ngoài đường, hoặc dữ liệu đại diện nhiều ngày. "
    "Em xem luận văn là phát triển hệ thống và đánh giá mô phỏng, trong đó các kết quả xấu cũng được công bố.",
    ["Cột xanh = câu được nói", "Cột đỏ = câu không được nói", "Khung: hệ thống + đánh giá mô phỏng"]))

slide("Kết luận", "Đóng góp, giới hạn và bước tiếp", f'''
<div class="row" style="gap:30px">
 <div class="col"><h3 class="go">Đóng góp</h3><ul class="dots small">
  <li><b>Hai tầng nghiên cứu</b>: một nút đã công bố và một mạng OSM 53 nút</li><li>Các bộ điều khiển có trạng thái, hành động và thưởng <b>viết rõ trong mã</b></li>
  <li>Một <b>hành động residual truy được</b>: dịch một biên, kiểm hợp lệ, về neo</li><li>Đánh giá <b>ghép cặp</b>, tách seed học, tính xe chưa vào, công bố kết quả xấu</li>
  <li>Chuỗi từ nguồn đến dữ liệu, cấu hình, checkpoint, kết quả và demo</li></ul></div>
 <div class="col"><h3 class="stop">Giới hạn</h3><ul class="dots stop small">
  <li>Dữ liệu camera: một ngày, bốn luồng, đọc xấp xỉ; nhu cầu mạng là tổng hợp</li><li>Không hiệu chuẩn quỹ đạo hiện trường; mô hình làn, không có làn phụ</li>
  <li>Normal xấu đi trong SUMO; Max-Pressure thắng residual trên mạng</li><li>Tập kiểm tra đã được dùng để sửa mô phỏng (tau 1,2) và chọn cổng hậu nghiệm</li>
  <li>Phát hành chặt chưa xong; một số hiện vật thô nằm ngoài Git</li></ul></div>
 <div class="col"><h3 class="caution">Bước tiếp</h3><ul class="dots caution small">
  <li><b>Đóng băng</b> chính sách và cổng, rồi chạy một kiểm tra độc lập mới</li><li>Hoàn thiện hiện vật và gắn phiên bản để tái lập</li>
  <li><b>Ablation</b>: dueling, n-step, đặc trưng nút kề, thưởng toàn cục, biên residual</li><li>Nhạy với sai số đọc và với nhu cầu</li>
  <li>Dữ liệu nhiều ngày và hiệu chuẩn hiện trường trước khi kết luận rộng hơn</li></ul></div>
</div>
<div class="note ink" style="margin-top:22px;font-size:15.5px">Không nhận là đóng góp: phát minh Double DQN hay dueling, đỉnh ngành, cải thiện cả thành phố, hoặc sẵn sàng điều khiển đèn thật.</div>''',
      secs=115, notes=N(
    "Luận văn đóng góp năm việc: thiết kế nghiên cứu hai tầng; các bộ điều khiển có trạng thái, hành động và thưởng rõ; một hành động residual truy được; đánh giá ghép cặp có tính xe chưa vào và công bố kết quả xấu; và chuỗi truy vết từ nguồn đến demo. "
    "Giới hạn: camera là một ngày và bốn luồng; mạng dùng nhu cầu tổng hợp; chưa hiệu chuẩn; normal xấu hơn trong SUMO và Max-Pressure thắng trên mạng; tập kiểm tra đã được dùng để sửa mô phỏng và chọn cổng; phát hành chặt chưa xong. "
    "Bước tiếp theo thứ tự ưu tiên: đóng băng chính sách và cổng rồi chạy kiểm tra mới; hoàn thiện hiện vật; tách từng thành phần bằng ablation; chạy phân tích nhạy; và chỉ sau đó mới đến dữ liệu nhiều ngày và hiệu chuẩn hiện trường.",
    ["5 đóng góp — nhấn residual truy được và đánh giá ghép cặp", "Nói giới hạn trước khi bị hỏi", "Ưu tiên: đóng băng → kiểm tra mới → ablation"],
    [], [("Em sẽ cải thiện gì trước?", "Đóng băng chính sách và cổng, rồi chạy một kiểm tra độc lập mới với baseline mạnh và nhiều seed; sau đó mới ablation và hiệu chuẩn.")]))

slide("Kết luận", "", f'''
<div style="position:absolute;right:120px;top:120px">{signal_head("go", 130, 420)}</div>
<div style="position:absolute;left:72px;top:110px;width:900px;font-size:36px;line-height:1.25;font-weight:800;color:#fff;letter-spacing:-.02em">Học tăng cường có thể giảm hàng chờ ở một số chế độ mô phỏng, nhưng lợi ích không đều và chưa thắng các baseline mạnh trên mạng.</div>
<div style="position:absolute;left:72px;top:360px;width:860px;font-size:21px;line-height:1.5;color:#AFC0CC">Đóng góp: hai tầng thí nghiệm, một bộ điều khiển residual có hành vi kiểm được, và một chuỗi truy vết bằng chứng. Bước tiếp: đóng băng chính sách và cổng, kiểm tra trên nhu cầu mới, rồi thêm hiệu chuẩn và dữ liệu hiện trường.</div>
<div style="position:absolute;left:72px;top:540px;font-size:48px;font-weight:850;color:#fff">Em xin cảm ơn.</div>
<div style="position:absolute;left:72px;top:604px;font-size:20px;color:#6FD3B0">Em sẵn sàng nhận câu hỏi và nhận xét của Hội đồng.</div>
''', secs=45, kind="closing", notes=N(
    "Kết quả cho thấy học tăng cường có thể giảm hàng chờ ở một số chế độ mô phỏng, nhưng lợi ích không đều và chưa thắng các baseline mạnh trên mạng hiện tại. "
    "Luận văn đóng góp hai tầng thí nghiệm, một bộ điều khiển residual có hành vi kiểm được, và một quy trình truy vết bằng chứng. "
    "Bước tiếp là đóng băng chính sách và cổng, kiểm tra trên nhu cầu độc lập mới, rồi thêm hiệu chuẩn và dữ liệu hiện trường trước khi mở rộng kết luận. Em xin cảm ơn Hội đồng và sẵn sàng nhận câu hỏi.",
    ["Đọc câu kết gần như nguyên văn", "Dừng, nhìn Hội đồng, chờ câu hỏi", "Mở slide phụ lục khi được hỏi"]))


# ================================================================== backup
slide(B, "B1 · Tham số của hai mô hình được báo cáo", table(["Tham số", "SUMO dueling_n3", "Residual CityFlow V3B"], [
    ["Vào, ẩn, ra", "16; 64, 64; V 1 + A 3 → 3 Q", "27 mỗi macro; 64, 64; một Q mỗi macro"], ["n-step, số ô hành động", "3; 3", "một chuyển tiếp macro; 59 có mặt nạ"],
    ["Tốc độ học, Adam β1 / β2 / ε", "0,0003; 0,9 / 0,999 / 1e−8", "0,0003; 0,9 / 0,999 / 1e−8"], ["Huber δ, cắt gradient (L2)", "1; 10", "1; 10"],
    ["Bộ nhớ, batch, bắt đầu học", "50.000; 64; 256", "20.000; 128; 53"], ["Cập nhật, đồng bộ đích", "1 mỗi quyết định; 200 lần", "8 mỗi macro mạng; 64 lần"],
    ["γ, thang thưởng", "0,99 mỗi 10 giây; × 0,01", "0,99 mỗi 300 giây; ÷ 100.000"], ["ε khi học", "1,0 → 0,05 trong 5.000 quyết định", "cố định 0,15"],
    ["Nhịp, macro, dịch", "10 giây; không; không", "10 giây; 300 giây; ±10 giây một biên"], ["Xanh tối thiểu, vàng, đỏ tối đa", "20 giây; 7 giây; không dùng", "20 giây; 3 giây theo hợp đồng; 180 giây"],
    ["Baseline cố định", "32 / 28 / 22 + 3 × 7 = 103 giây", "xanh danh định 25 giây"], ["Episode, đánh giá, seed", "30; mỗi 5; 11–15", "12; mỗi 4; 12–16"],
    ["Khởi tạo đầu ra, khởi động", "khởi tạo SharedDQN; 0", "W3 / b3 = 0; không bắt chước"]], cls="t tight"), secs=0, kind="backup",
      source="configs/danang_pilot.yaml · seed14-resolved-config.json · seed14-step4-contract.json", notes=N(
          "Dùng khi bị hỏi tham số. Nhấn rằng các giá trị có lý do kỹ thuật nhưng chưa được chứng minh là tối ưu; ngoài việc tìm thời lượng cố định thì không có tìm kiếm siêu tham số.",
          ["đồng bộ đích = 64 lần cập nhật, không phải giây", "γ có đơn vị bước khác nhau", "Không tìm siêu tham số ngoài thời lượng cố định"]))

slide(B, "B2 · Bộ nhớ phát lại, khám phá, hàm mất và bộ tối ưu", f'''
{table(["Cơ chế", "Mục đích", "Trong dự án này"], [["Bộ nhớ phát lại", "Dùng lại kinh nghiệm, giảm tương quan mẫu liên tiếp", "Vòng đệm, lấy mẫu đều <b>có hoàn lại</b>"],
    ["ε-tham lam", "Khám phá thay vì luôn lấy phương án hiện tốt nhất", "Với xác suất ε chọn ngẫu nhiên một hành động hợp lệ"], ["Mất mát Huber", "Bình phương khi lỗi nhỏ, tuyến tính khi lỗi lớn", "δ = 1; hạn chế gradient TD-error lớn"],
    ["Cắt gradient", "Chặn chuẩn L2 toàn cục của gradient", "Ngưỡng 10, không phải kẹp trọng số ở ±10"], ["Adam", "Cập nhật theo moment", "β1 = 0,9, β2 = 0,999, ε số = 1e−8"],
    ["ReLU, khởi tạo He", "Phi tuyến; thang khởi tạo hợp với ReLU", "max(0, x); căn(2 / fan_in)"]])}
<div class="row" style="gap:20px;margin-top:18px">
 <div class="eq col">Huber(δ) = 0,5 · δ²      nếu |δ| ≤ 1
           |δ| − 0,5    nếu |δ| > 1</div>
 <div class="note col">ε của Adam làm ổn định một phép chia; ε-tham lam là xác suất khám phá. Mất mát giảm <b>không</b> chứng minh chính sách tốt, nên checkpoint được chọn bằng chỉ số giao thông trên kiểm định.</div>
</div>''', secs=0, kind="backup", notes=N("Dùng cho câu hỏi về bộ tối ưu hoặc “vì sao mất mát giảm mà hàng chờ không giảm?”.", ["Có hoàn lại → batch 128 từ 53 mẫu vẫn chạy được", "Cắt chuẩn gradient, không cắt trọng số", "Hai epsilon khác nhau"]))

slide(B, "B3 · Trung bình từng ca, gộp và bootstrap: đơn vị độc lập là gì?", f'''
<div class="row" style="gap:30px">
 <div class="col"><div class="eq" style="font-size:15px"><span class="c"># âm là tốt</span>
hối tiếc_ca   = 100 · (L − F) / F
<span class="c"># dương là tốt</span>
giảm_ca       = 100 · (F − L) / F
gộp           = 100 · (ΣF − ΣL) / ΣF</div>
  <div class="panel" style="margin-top:16px"><span class="small">Bảng PM của demo, seed 14: <b>đổi trung bình từng ca −8,86%</b>, KTC <b>[−17,51%; −1,62%]</b> trên 5 ca nhu cầu của <b>một chính sách</b>, không phải khoảng năm seed.</span></div></div>
 <div style="flex:1.2">{table(["Phân tích", "Đơn vị lấy lại", "Số lần", "Khoảng bao phủ"], [["SUMO đã học so với cố định", "5 hiệu ứng seed (ca gộp trong seed)", "20.000", "Biến động seed học"],
     ["Bảng PM demo, s14", "5 ca nhu cầu ghép cặp", "bootstrap theo ca", "Biến động giữa các ca nhu cầu"], ["Cổng chỉ PM", "5 hiệu ứng gộp, một mỗi seed", "10.000", "Thăm dò, mức seed"]], cls="t tight")}
  <div class="note stop" style="margin-top:14px;font-size:15.5px">75 ô seed × ca <b>không</b> phải 75 chính sách độc lập. 7.632 chuyển tiếp không đi vào khoảng tin cậy. Bootstrap không tạo dữ liệu hiện trường mới.</div></div>
</div>''', secs=0, kind="backup", notes=N("Dùng cho câu hỏi thống kê hoặc câu 8,86 so với 10,39.", ["Gộp đặt nặng hơn lên ca lớn", "Đơn vị độc lập = seed học", "Khoảng tin cậy không sửa lệch chọn"]))

slide(B, "B4 · Tham số xe khác nhau giữa SUMO và CityFlow", f'''
<div class="row" style="gap:30px">
 <div style="flex:1.3"><h3>SUMO <span class="sub">XML lộ trình, AM học</span></h3>{table(["", "Xe máy", "Ô tô", "Xe tải", "Xe buýt"], [["Dài / rộng, m", "2 / 0,8", "5 / 1,8", "8 / 2,5", "12 / 2,5"], ["Tăng / giảm tốc, m/s²", "3,5 / 5", "2 / 4,5", "1,3 / 4", "1,2 / 4"],
     ["Khoảng hở tối thiểu, m", "0,5", "2,5", "3", "3"], ["Tốc độ tối đa, m/s", "13,89 (≈50 km/h)", "11,11 (≈40)", "10", "10"], ["Sigma, tau", "0,7; 1,2 giây", "0,5; —", "0,5; —", "0,5; —"]], cls="t tight", align=["", "c", "c", "c", "c"])}</div>
 <div class="col"><h3>CityFlow <span class="sub">haichau_dataset.py</span></h3>{table(["", "Xe máy", "Ô tô"], [["Dài / rộng, m", "2 / 1", "5 / 2"], ["Tăng / giảm tốc tối đa", "3,5 / 5", "2 / 4,5"], ["Khoảng hở tối thiểu, m", "0,5", "2,5"], ["Tốc độ tối đa, m/s", "13,89", "11,11"], ["Thời gian tiến, giây", "0,8", "1,5"]], cls="t tight", align=["", "c", "c"])}</div>
</div>
<div class="note" style="margin-top:20px">Lần chạy chính dùng <b>mô hình theo làn</b>. Một thử nghiệm làn phụ 300 giây thì ổn, nhưng đủ giờ thì va chạm, nên đã bỏ. Tau xe máy từ 1,0 lên 1,2 sau một va chạm ở một ca AM giữ riêng; mọi thứ được chạy lại cho nhất quán, nhưng tập kiểm tra đã bị dùng để sửa mô phỏng. Tham số chưa hiệu chuẩn trên quỹ đạo hiện trường.</div>''',
      secs=0, kind="backup", notes=N("Dùng cho câu hỏi về mô hình xe máy, làn phụ, tau.", ["Mô hình làn, không có làn phụ", "tau 1,2 chỉ đặt cho xe máy", "Thời gian tiến CityFlow 0,8 khác tau SUMO 1,2"]))


slide(B, "B5 · Lịch sử thay đổi và bài học", table(["Giai đoạn / vấn đề", "Thay đổi", "Kết luận được phép"], [
    ["Dữ liệu cũ gọi là “chuyến thật”", "Đổi nhãn thành tổng hợp", "Không có nguồn cho “50.500 chuyến thật”"], ["Mạng SUMO rộng có lỗi", "Tách nút có dữ liệu, hướng vào khoảng 300 m", "SUMO phủ không gian ít hơn"],
    ["Thử làn phụ", "Bỏ sau va chạm đủ giờ", "Mất một phần thực hơn theo bề ngang"], ["Xe chưa vào trên mạng", "Tách xe đến hạn khỏi xe chưa phát", "Chỉ số giờ đã đúng; không dùng lại bộ nhớ cũ"],
    ["Thực thi đèn cố định", "Thống nhất đồng hồ, mặt nạ, chuyển pha", "So lịch đã thực thi"], ["V2 chọn pha / V3A diễn tập", "Đặc trưng nút kề, bắt chước / diễn tập", "Các thử bị bác trong nhật ký quyết định"],
    ["Residual V3B", "27 đặc trưng, macro 300 giây, ±10 giây", "Họ đứng sau kết quả residual hiện tại"], ["V3C / V3D", "Biên và cách khám phá khác", "Chẩn đoán; không gộp vào V3B"],
    ["Cổng chỉ PM", "Normal / AM cố định, PM residual", "Thăm dò, cần kiểm tra mới"], ["Kiểm ngày 23/9", "Sửa tác giả, vị trí, đơn vị khoảng tin cậy", "Sửa cách đọc; không có thí nghiệm mới"]], cls="t tight"),
      secs=0, kind="backup", source="docs/research/decision-log.md · docs/research/thesis-evidence-ledger.md", notes=N(
          "Cách nói về thất bại: “Thí nghiệm này trượt cổng, nên em đổi thiết kế hoặc thu hẹp kết luận và giữ bằng chứng.” Không kể lịch sử như một chuỗi mà bản nào cũng tốt hơn bản trước.",
          ["Thất bại → kết luận hẹp hơn", "V3B là họ được báo cáo", "V3C / V3D chỉ để chẩn đoán"]))

slide(B, "B6 · Công nghệ và bản đồ mã", f'''
<div class="row" style="gap:30px">
 <div class="col">{table(["Công nghệ", "Vai trò"], [["Python, NumPy", "Đường ống; MLP, lan truyền ngược, Adam, bộ nhớ, bootstrap"], ["SUMO + TraCI", "Mô phỏng một nút và giao diện Python"], ["CityFlow (C++ và Python)", "Mô phỏng mạng 53 nút"],
     ["OSM, osmium, netconvert", "Topology và đổi định dạng"], ["Docker, Colima", "Môi trường CityFlow đóng gói (NumPy 1.19.5)"], ["Git, SHA-256", "Phiên bản mã và danh tính hiện vật"], ["Matplotlib, LaTeX", "Hình và PDF luận văn"], ["HTML, JS, Canvas", "Demo phát lại trên trình duyệt"]], cls="t tight")}
  <div class="xs muted" style="margin-top:6px">PyTorch và SB3 trong file yêu cầu cũ <b>không</b> được hai mô hình chính dùng. Không có đường ống GPU.</div></div>
 <div class="col">{table(["Cần giải thích", "Mở (trong src/traffic_rl/)"], [["Quan sát SUMO và đổi pha", "sim/sumo_single_junction.py"], ["Dueling, đích Double, Adam", "agents/dqn.py"], ["Vòng huấn luyện SUMO", "train/trainer.py"], ["12 đặc trưng pha", "sim/phase_encoder.py"],
     ["MLP số dùng chung", "agents/phase_ddqn.py"], ["ShadowSignal, macro, neo", "sim/schedule_residual.py"], ["Huấn luyện residual", "train/schedule_residual_trainer.py"], ["Tích phân hàng chờ, xe chưa vào", "sim/multi_agent_env.py"], ["Bộ chọn từng seed", "research/final_residual_selector.py"]], cls="t tight")}</div>
</div>''', secs=0, kind="backup", notes=N("Dùng khi hỏi “mã ở đâu?” — mở đúng file.", ["Hai mô hình viết bằng NumPy", "Docker cho CityFlow", "Biết câu hỏi nào mở file nào"]))

slide(B, "B7 · Tái lập: cái đã có và cái còn thiếu", f'''
<div class="row" style="gap:30px">
 <div class="col"><h3 class="go">Đã có</h3><ul class="dots small"><li>Manifest, cấu hình đã giải, hợp đồng checkpoint, JSON chọn</li><li>Lộ trình SUMO, mạng, CSV và JSON tổng kết</li><li>Ảnh chụp bằng chứng ngày 23/9 và script kiểm (63 / 63 kiểm nguồn và số học đều qua)</li><li>Điểm vào: chuẩn bị → học → đánh giá → tổng kết; học / chọn residual; chiến dịch; demo</li></ul></div>
 <div class="col"><h3 class="stop">Còn thiếu</h3><ul class="dots stop small"><li>Thiếu <span class="mono">scripts/build_danang_pilot.py</span>, nên bản sao mới không dựng lại được đường ống SUMO</li><li>Chiến dịch thô và checkpoint lớn nằm ngoài Git</li><li>Phát hành chặt: còn 14 cổng mở</li><li>File NPZ không có bộ nhớ, Adam và trạng thái số ngẫu nhiên, nên không học tiếp đúng chỗ</li><li>Provenance OSM ghi ngày tải và phiên bản công cụ là <span class="mono">unknown_not_recorded</span></li></ul></div>
</div>
<div class="panel dark" style="margin-top:24px">Câu đúng: <b style="color:#6FD3B0">nhiều phần hỗ trợ tái lập, và các lỗ còn lại đã được chỉ ra</b>. Không phải “ai sao chép kho cũng tái lập được mọi thứ”.</div>''',
      secs=0, kind="backup", source="docs/research/thesis-review-verification.md · docs/research/thesis-evidence-audit.json", notes=N("Dùng cho câu hỏi tái lập.", ["Kiểm 63 / 63 khác phát hành chặt", "Thiếu build_danang_pilot.py", "Nói thẳng"]))

slide(B, "B8 · Độ nhạy nhu cầu trong SUMO", f'''
<div class="row" style="gap:30px">
 <div style="width:720px;flex:none"><img class="fig" src="{img("sensitivity")}" style="width:720px;height:450px;object-fit:contain"></div>
 <div class="col"><h3>Cách đọc</h3><ul class="dots small"><li>120 lượt ở các tỷ lệ 0,75; 1,0; 1,25 và 1,5</li><li>30 lượt ở tỷ lệ 1,0 lặp lại điều kiện AM chính, nên đây <b>không</b> phải 120 quan sát độc lập thêm</li><li>Cách nhân tỷ lệ là tổng hợp, không phải đo được</li><li>0 va chạm, 4 sự kiện khẩn cấp</li></ul></div>
</div>''', secs=0, kind="backup", source="results/danang_protocol_v1/summary/demand-sensitivity.png", notes=N("Dùng khi hỏi độ bền theo mức nhu cầu.", ["Tỷ lệ 1,0 lặp điều kiện chính", "Nhân tỷ lệ tổng hợp", "4 khẩn cấp, 0 va chạm"]))

qa = [("Một mô hình hay nhiều?", "Hai họ: SUMO dueling Double DQN (16 → 3 Q); CityFlow residual Double DQN (27 mỗi macro → 1 Q), trọng số dùng chung cho 53 nút."),
      ("Vì sao không dùng mạng đồ thị, PPO hay mô hình lớn hơn?", "Hành động rời rạc và MLP nhỏ giúp hợp đồng kiểm được. Chưa có so sánh nào nói chúng tốt hơn hay xấu hơn."),
      ("Thưởng residual có phải phần hơn so với cố định?", "Không. Đó là −(hàng chờ + xe chưa vào) của cả mạng trong block. Phần hơn so với cố định đo ở đánh giá ghép cặp."),
      ("Mất mát giảm mà hàng chờ không giảm?", "Mất mát đo độ khớp với đích TD trên bộ nhớ; nó không chứng minh chính sách tham là tốt, nên việc chọn dùng kiểm định."),
      ("Hệ thống không tai nạn chứ?", "Luật pha, chuyển pha và neo là logic mô phỏng; 120 lượt chính và 120 lượt nhạy cảm SUMO có 0 va chạm (đợt 1.000 hiện thực baseline không ghi va chạm). Không phải giấy chứng nhận an toàn hiện trường."),
      ("Cùng γ mà hành vi khác?", "0,99 mỗi 10 giây khác 0,99 mỗi 300 giây. Muốn so theo thời gian thực thì hãy lũy thừa γ theo số bước."),
      ("Seed bị loại mà kiểm tra vẫn tốt?", "Quyết định kiểm định vẫn giữ; chỉ báo như chẩn đoán hậu nghiệm."),
      ("Thế này đã đủ một luận văn chưa?", "Đủ cho phát triển hệ thống cộng đánh giá mô phỏng có phân tích thất bại; chưa đủ cho kết luận triển khai.")]
qah = "".join(f'<div class="panel" style="padding:13px 18px"><div style="font-weight:850;color:{C["ink"]};font-size:19px;margin-bottom:3px">{q}</div><div class="small">{a}</div></div>' for q, a in qa)
slide(B, "B9 · Trả lời nhanh các câu hay gặp", f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">{qah}</div>', secs=0, kind="backup",
      source="docs/defense/thesis-understanding-guide-vi.md mục 22 · docs/defense/committee-questions-evidence-vi.md", notes=N(
          "Slide cứu trợ. Mỗi câu trả lời: một câu kết luận, một câu giới hạn, rồi chỉ vào bằng chứng.", ["Trả lời ngắn rồi dừng", "Luôn thêm giới hạn", "Mở hiện vật nếu cần"]))

cam_rows = [["Trần Phú", "168", "3", "J1: 89% → trục chính · 6% → Trưng Nữ Vương"],
            ["Nguyễn Văn Linh (tây)", "160", "126", "J1: 89% → trục chính · 10% → Trưng Nữ Vương"],
            ["Trưng Nữ Vương", "0", "49", "chỉ có xe ra (OSM: một chiều)"],
            ["2 Tháng 9", "182", "101", "J2: 39% → cầu · 37% → Bạch Đằng · 20% → trục chính"],
            ["Cầu Rồng", "104", "246", "J2: 62% → trục chính · 18% → 2 Tháng 9 · 13% → Bạch Đằng"],
            ["Bạch Đằng (bắc)", "3", "236", "chỉ có xe ra (OSM: một chiều)"]]
slide(B, "B10 · Camera YOLO: số đếm ô tô, kiểm tra và giới hạn", f'''
<div class="row" style="gap:28px">
 <div style="flex:1.35">{table(["Lối (ô tô / 15 phút)", "Vào", "Ra", "Xích Markov từ lối này"], cam_rows, cls="t tight")}
  <div class="xs muted" style="margin-top:8px">Trục chính giữa J1–J2 (gần camera, tin nhất): ô tô 323 lên / 152 xuống; xe máy 1.010 lên / 517 xuống.</div></div>
 <div class="col">
  <h3>Kiểm tra</h3><ul class="dots small"><li>Cân bằng ô tô: J1 480 vào / 501 ra; J2 612 / 735</li><li>63% lượt vào có hành trình trọn (689 tuyến)</li><li>Chiều một chiều trên OSM khớp số đếm</li></ul>
  <h3 class="stop" style="margin-top:14px">Giới hạn</h3><ul class="dots stop small"><li>Chưa đếm tay đối chiếu; chưa đo độ chính xác ID</li><li>Xe máy: 174 vào / 703 ra → lối xa (cầu) đếm thiếu</li><li>Một camera, một ngày, 15 phút; khoảng 95 phút máy cho 15 phút video</li></ul>
 </div>
</div>''', secs=0, kind="backup", source="results/camera_counts/caurong_20260711_1716/only_car/*.csv · results/camera_counts/README.md", notes=N(
    "Slide cứu trợ cho câu hỏi về camera. Đọc bảng theo hàng: lối vào, số ô tô vào và ra, rồi xác suất rẽ. Luôn nói giới hạn: chưa đếm tay, xe máy ở xa bị đếm thiếu.",
    ["Ô tô tin được: cân bằng 4% / 17%", "Xe máy: chỉ trục chính", "Chưa đếm tay"]))

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
    desc = "".join(f'<div style="display:flex;gap:14px;padding:7px 0;border-bottom:1px solid {C["rule"]}"><div style="width:150px;font-weight:850;color:{C["ink"]}">{i + 1}. {n}</div><div class="small">{t}</div></div>' for i, (n, t) in enumerate(parts))
    return f'''<div style="position:relative;height:78px">{"".join(segs)}</div>
<div class="row" style="gap:40px;margin-top:6px"><div style="flex:1.4">{desc}</div>
<div class="col"><div class="panel dark" style="font-size:20px;line-height:1.42"><b style="color:#6FD3B0">Một câu cần nhớ.</b> Lợi ích của học tăng cường phụ thuộc chế độ nhu cầu và baseline. Đây là bằng chứng mô phỏng, không phải hiệu quả ngoài đường.</div>
<div style="margin-top:16px" class="small"><div><span class="lamp" style="background:{C["go"]}"></span>tốt hơn, bộ điều khiển đã học</div><div><span class="lamp" style="background:{C["caution"]}"></span>thận trọng, thăm dò, chưa kết luận</div><div><span class="lamp" style="background:{C["stop"]}"></span>xấu hơn, giới hạn</div><div><span class="lamp" style="background:{C["base"]}"></span>baseline cố định &nbsp; <span class="lamp" style="background:{C["pressure"]}"></span>baseline áp lực</div></div></div></div>'''


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
    pages.append(f'''<div class="npage"><h2>Kịch bản nói, bảo vệ 40 phút</h2>
<p style="font-size:14px;margin-bottom:8px">{len(main)} trang chính, nói <b>{mmss(total)}</b> cộng khoảng <b>{mmss(2400 - total)}</b> dự phòng. “Mốc” là thời điểm ở <b>cuối</b> mỗi trang; dùng khi tập.</p>
<table class="t timing"><tr><th class="r">#</th><th>Trang</th><th class="c">Thời lượng</th><th class="c">Mốc</th></tr>{"".join(rows)}</table>
<h4>Mốc khi đang nói</h4><p style="font-size:14.5px">Hết Dữ liệu ≈ <b>{mmss(marks["Dữ liệu"])}</b>, hết SUMO ≈ <b>{mmss(marks["SUMO"])}</b>, hết CityFlow ≈ <b>{mmss(marks["CityFlow"])}</b>, hết Kết quả ≈ <b>{mmss(marks["Kết quả"])}</b>. Nếu chậm hơn 2 phút: rút phần cơ sở RL, slide đọc kết quả SUMO và slide chỉ số phụ.</p>
<div class="nfoot"><span>{AUTHOR}, kịch bản nói</span><span>Trang 1</span></div></div>''')
    cheat = [("Nguồn", "Phan, Le và Nguyen (2025), MAKE 7(3):65; camera 1/4/2025; 4 luồng; 48 dòng / 192 giá trị"),
             ("Lịch công bố", "xanh 32 / 28 / 22 + vàng 3 × 7 = 103 giây"), ("Nhu cầu SUMO", "normal 1.395; AM 2.330 (học); PM 2.400 xe/giờ trên 4 đường đo"),
             ("Mạng", "53 đèn; 1.290 họ lộ trình (644 / 323 / 323); 500 dòng lộ trình mỗi ca; xe máy 0,90"),
             ("Chia dữ liệu", "học 9, kiểm định 6, kiểm tra 15 ca (3 chế độ × 5); nhu cầu 101–105, mô phỏng 201–205"),
             ("Mô hình SUMO", "16 → 64 → 64 → V/A → 3 Q; 5.508 tham số; bước 10 giây; vàng 7 giây; xanh tối thiểu 20 giây; lợi tức 3 bước"),
             ("Học SUMO", "30 episode × 5 seed (11–15); 360 quyết định mỗi episode; ε 1 → 0,05 trong 5.000; kiểm định mỗi 5; 120 lượt kiểm tra"),
             ("Mô hình residual", "27 = 12 + 12 + 3 → 64 → 64 → 1; 6.017 tham số; dùng chung 53 nút; ±10 giây; macro 300 giây; MAX_MACROS 59"),
             ("Học residual", "12 episode; 6 ca cao điểm; 7.632 chuyển tiếp; 1.152 cập nhật; ε 0,15; đích mỗi 64; kiểm định ep 4 / 8 / 12"),
             ("Bộ chọn", "seed 12 (ep 8), 14 (ep 4), 15 (ep 8) được chọn; 13 và 16 bị loại; phát hành chặt complete = false (14 cổng)"),
             ("Kết quả SUMO", "normal 9,86 → 41,50 (+320,7%); AM 79,20 → 78,41 (−1,0%); PM 152,67 → 99,97 (−34,5%)"),
             ("KTC SUMO", "normal [7,60; 56,14]; AM [−9,47; 8,49]; PM [−69,55; −35,34] xe-giờ, trên 5 hiệu ứng seed"),
             ("Kết quả mạng", "cố định 8.339,43; MP 6.347,00 (−23,89%); MP trễ 6.739,13 (−19,19%); residual 7.829,25 (−6,12%)"),
             ("Residual theo chế độ", "normal 0%; AM 3,48%; PM 10,39% gộp (8,86% trung bình từng ca)"),
             ("Chỉ số phụ", "hoàn thành +1,06 điểm; vào được +0,82 điểm; thời gian đi +5,45 giây; tràn hàng +65,20 làn-giây"),
             ("Cổng chỉ PM", "trung bình 3,48%; khoảng 1,03–5,62%; KTC [2,01; 4,95]; 15 / 25 tốt hơn, 10 / 25 xấu hơn; HẬU NGHIỆM"),
             ("Demo", "PM nhu cầu 105 / mô phỏng 205; seed 14 ep 4; nút 420249521; 18:05 = 1.085 giây; 14 so với 1 xe chờ")]
    ch = "".join(f"<tr><td><b>{a}</b></td><td>{b}</td></tr>" for a, b in cheat)
    pages.append(f'''<div class="npage"><h2>Số cần thuộc</h2><table class="t"><tr><th style="width:140px">Chủ đề</th><th>Số</th></tr>{ch}</table>
<h4>Năm câu không được nói</h4><ul style="padding-left:18px;font-size:14.5px"><li>“Học tăng cường thắng lịch cố định” mà không nêu chế độ và baseline.</li><li>“Mạng 53 nút là mọi đèn thật của Hải Châu.”</li>
<li>“3,48% là kết quả đã xác nhận” — đó là hậu nghiệm.</li><li>“500 lộ trình là 500 xe” hoặc “18:05 là 6 giờ chiều”.</li><li>“Mô hình dùng mạng đồ thị hoặc giao tiếp đa tác nhân.”</li></ul>
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
