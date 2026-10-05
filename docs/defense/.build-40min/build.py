"""Build the 40-minute Vietnamese defense deck and the speaker-notes handout.

Outputs (HTML, printed to PDF by render.sh):
  deck.html   -> slides/thesis-defense-40min-vi.pdf
  notes.html  -> slides/thesis-defense-40min-speaker-notes-vi.pdf
"""
from __future__ import annotations

import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
IMG = {
    "junction": ROOT / "paper/figures/junction-schematic.png",
    "camera": ROOT / "paper/figures/camera-profile.png",
    "curves": ROOT / "results/danang_protocol_v1/summary/validation-learning-curves.png",
    "sensitivity": ROOT / "results/danang_protocol_v1/summary/demand-sensitivity.png",
    "demo": ROOT / "tmp/thesis-evidence/demo-final-review.png",
}
AUTHOR = "Lương Quang Khang"
SECTIONS = ["Mở đầu", "Dữ liệu", "Nền tảng RL", "SUMO", "CityFlow", "Kết quả", "Kết luận"]

C = dict(navy="#0F2A44", teal="#1F8A84", coral="#D9624B", gold="#C99526", slate="#5B6B7C",
         line="#D5DAD9", muted="#6B7A89", paleTeal="#E2F1EE", paleCoral="#FBE9E4", ink="#1B2F45")


def img(key: str) -> str:
    return IMG[key].as_uri()


def fmt_vn(x: float, d: int = 2) -> str:
    s = f"{x:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------- SVG charts
def grouped_bars(groups, series, values, vmax, w=640, h=350, unit="", tick=100, label_fmt=None):
    """values[series_idx][group_idx]."""
    label_fmt = label_fmt or (lambda v: fmt_vn(v, 1))
    left, right, top, bottom = 58, 12, 26, 44
    pw, ph = w - left - right, h - top - bottom
    ng, ns = len(groups), len(series)
    gw = pw / ng
    bw = gw * 0.78 / ns
    out = [f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" font-family="BVP">']
    t = 0
    while t <= vmax + 1e-9:
        y = top + ph - ph * t / vmax
        out.append(f'<line x1="{left}" x2="{w-right}" y1="{y:.1f}" y2="{y:.1f}" stroke="#E3E6E4" stroke-width="1"/>')
        out.append(f'<text x="{left-8}" y="{y+4:.1f}" font-size="12" text-anchor="end" fill="{C["muted"]}">{int(t)}</text>')
        t += tick
    out.append(f'<text x="14" y="{top+ph/2}" font-size="12" fill="{C["muted"]}" transform="rotate(-90 14 {top+ph/2})" text-anchor="middle">{unit}</text>')
    for gi, g in enumerate(groups):
        gx = left + gi * gw + gw * 0.11
        for si, (name, color) in enumerate(series):
            v = values[si][gi]
            bh = ph * v / vmax
            x = gx + si * bw
            y = top + ph - bh
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw-4:.1f}" height="{bh:.1f}" rx="3" fill="{color}"/>')
            out.append(f'<text x="{x+(bw-4)/2:.1f}" y="{y-5:.1f}" font-size="11.5" font-weight="700" text-anchor="middle" fill="{C["ink"]}">{label_fmt(v)}</text>')
        out.append(f'<text x="{left+gi*gw+gw/2:.1f}" y="{h-bottom+22}" font-size="15" font-weight="700" text-anchor="middle" fill="{C["navy"]}">{g}</text>')
    out.append(f'<line x1="{left}" x2="{w-right}" y1="{top+ph}" y2="{top+ph}" stroke="{C["slate"]}" stroke-width="1.2"/>')
    out.append("</svg>")
    return "".join(out)


def legend(series):
    return '<div style="display:flex;gap:16px;flex-wrap:wrap;font-size:13.5px;">' + "".join(
        f'<span><span style="display:inline-block;width:12px;height:12px;border-radius:3px;background:{c};margin-right:6px;vertical-align:-1px"></span>{n}</span>'
        for n, c in series) + "</div>"


def hbars(rows, vmax, w=620, row_h=58, label_w=210):
    """rows: (label, value, color, right_text)."""
    h = row_h * len(rows) + 10
    pw = w - label_w - 150
    out = [f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" font-family="BVP">']
    for i, (lab, v, col, rt) in enumerate(rows):
        y = 6 + i * row_h
        bw = pw * v / vmax
        out.append(f'<text x="{label_w-12}" y="{y+row_h/2}" font-size="15" font-weight="700" text-anchor="end" fill="{C["navy"]}">{lab}</text>')
        out.append(f'<rect x="{label_w}" y="{y+10}" width="{bw:.1f}" height="{row_h-22}" rx="4" fill="{col}"/>')
        out.append(f'<text x="{label_w+bw+10:.1f}" y="{y+row_h/2-2}" font-size="15" font-weight="800" fill="{C["ink"]}">{fmt_vn(v)}</text>')
        out.append(f'<text x="{label_w+bw+10:.1f}" y="{y+row_h/2+15}" font-size="12.5" font-weight="600" fill="{col}">{rt}</text>')
    out.append("</svg>")
    return "".join(out)


def gate_chart(w=560, h=330):
    seeds = [("12", 2.36, "Selected · ep 8", True), ("13", 5.62, "Diagnostic · ep 12", False),
             ("14", 5.11, "Selected · ep 4", True), ("15", 1.03, "Selected · ep 8", True),
             ("16", 3.27, "Diagnostic · ep 4", False)]
    left, top, bottom, right = 48, 20, 58, 16
    pw, ph = w - left - right, h - top - bottom
    vmax = 6.5
    y = lambda v: top + ph - ph * v / vmax
    out = [f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" font-family="BVP">']
    for t in range(0, 7):
        out.append(f'<line x1="{left}" x2="{w-right}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#E3E6E4"/>')
        out.append(f'<text x="{left-8}" y="{y(t)+4:.1f}" font-size="12" text-anchor="end" fill="{C["muted"]}">{t}%</text>')
    out.append(f'<rect x="{left}" y="{y(4.95):.1f}" width="{pw}" height="{y(2.01)-y(4.95):.1f}" fill="{C["gold"]}" opacity="0.13"/>')
    out.append(f'<line x1="{left}" x2="{w-right}" y1="{y(3.48):.1f}" y2="{y(3.48):.1f}" stroke="{C["gold"]}" stroke-width="2.2" stroke-dasharray="7 5"/>')
    bw = pw / 5
    for i, (s, v, lab, sel) in enumerate(seeds):
        x = left + i * bw + bw * 0.2
        col = C["teal"] if sel else "#FFFFFF"
        stroke = C["teal"] if sel else C["slate"]
        dash = "" if sel else ' stroke-dasharray="5 3"'
        out.append(f'<rect x="{x:.1f}" y="{y(v):.1f}" width="{bw*0.6:.1f}" height="{y(0)-y(v):.1f}" rx="3" fill="{col}" stroke="{stroke}" stroke-width="2"{dash}/>')
        out.append(f'<text x="{x+bw*0.3:.1f}" y="{y(v)-6:.1f}" font-size="13" font-weight="800" text-anchor="middle" fill="{C["ink"]}">{fmt_vn(v)}%</text>')
        out.append(f'<text x="{x+bw*0.3:.1f}" y="{h-bottom+20}" font-size="14" font-weight="800" text-anchor="middle" fill="{C["navy"]}">seed {s}</text>')
        out.append(f'<text x="{x+bw*0.3:.1f}" y="{h-bottom+37}" font-size="11" text-anchor="middle" fill="{C["muted"]}">{lab}</text>')
    out.append(f'<line x1="{left}" x2="{w-right}" y1="{y(0)}" y2="{y(0)}" stroke="{C["slate"]}" stroke-width="1.2"/>')
    out.append("</svg>")
    return "".join(out)


def macro_timeline(w=1150, h=200):
    left, right = 30, 30
    pw = w - left - right
    x = lambda s: left + pw * s / 300
    out = [f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" font-family="BVP">']
    base_y = 62
    # reference schedule segments (illustrative)
    segs = [(0, 100, "Phase A", C["teal"]), (100, 110, "", "#E7B94A"), (110, 210, "Phase B", "#3E6E9A"),
            (210, 220, "", "#E7B94A"), (220, 300, "Phase A", C["teal"])]
    out.append(f'<text x="{left}" y="16" font-size="13" font-weight="700" fill="{C["navy"]}">Lịch tham chiếu (minh họa) — một block 300 giây</text>')
    for a, b, lab, col in segs:
        out.append(f'<rect x="{x(a):.1f}" y="{base_y}" width="{x(b)-x(a):.1f}" height="30" fill="{col}"/>')
        if lab:
            out.append(f'<text x="{(x(a)+x(b))/2:.1f}" y="{base_y+20}" font-size="13" font-weight="700" text-anchor="middle" fill="#fff">{lab}</text>')
    for i in range(31):
        xx = x(i * 10)
        hh = 10 if i % 5 else 16
        out.append(f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{base_y+32}" y2="{base_y+32+hh}" stroke="{C["slate"]}" stroke-width="1"/>')
        if i % 5 == 0:
            out.append(f'<text x="{xx:.1f}" y="{base_y+62}" font-size="11.5" text-anchor="middle" fill="{C["muted"]}">{i*10}s</text>')
    # candidate shifts
    for s, lab, col in [(90, "advance −10 s", C["coral"]), (110, "delay +10 s", C["gold"])]:
        out.append(f'<line x1="{x(s):.1f}" x2="{x(s):.1f}" y1="{base_y-6}" y2="{base_y+36}" stroke="{col}" stroke-width="3" stroke-dasharray="4 3"/>')
    out.append(f'<line x1="{x(100):.1f}" x2="{x(100):.1f}" y1="{base_y-8}" y2="{base_y+38}" stroke="{C["navy"]}" stroke-width="3"/>')
    out.append(f'<text x="{x(100):.1f}" y="{base_y+86}" font-size="12.5" font-weight="800" text-anchor="middle" fill="{C["navy"]}">boundary tham chiếu ở giây 100</text>')
    out.append(f'<text x="{x(90)-6:.1f}" y="{base_y-12}" font-size="12.5" font-weight="700" text-anchor="end" fill="{C["coral"]}">ứng viên advance: giây 90</text>')
    out.append(f'<text x="{x(110)+6:.1f}" y="{base_y-12}" font-size="12.5" font-weight="700" fill="{C["gold"]}">ứng viên delay: giây 110</text>')
    out.append(f'<rect x="{x(300)-4:.1f}" y="{base_y-10}" width="8" height="50" fill="{C["coral"]}"/>')
    out.append(f'<text x="{x(300)-10:.1f}" y="{base_y+122}" font-size="12.5" font-weight="800" text-anchor="end" fill="{C["coral"]}">giây 300: signal state phải khớp ANCHOR</text>')
    out.append(f'<text x="{left}" y="{base_y+122}" font-size="12.5" fill="{C["muted"]}">30 request ticks × 10 s · mỗi nút chọn 1 macro / block</text>')
    out.append("</svg>")
    return "".join(out)


def rl_loop():
    return f'''<svg width="520" height="300" viewBox="0 0 520 300" xmlns="http://www.w3.org/2000/svg" font-family="BVP">
<defs><marker id="ah" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{C['teal']}"/></marker></defs>
<rect x="170" y="10" width="180" height="60" rx="10" fill="{C['navy']}"/>
<text x="260" y="36" font-size="16" font-weight="800" fill="#fff" text-anchor="middle">Agent / policy</text>
<text x="260" y="56" font-size="12.5" fill="#BFD3E2" text-anchor="middle">Q(o,a) → argmax</text>
<rect x="170" y="225" width="180" height="60" rx="10" fill="#fff" stroke="{C['line']}"/>
<text x="260" y="251" font-size="16" font-weight="800" fill="{C['navy']}" text-anchor="middle">Simulator</text>
<text x="260" y="271" font-size="12.5" fill="{C['muted']}" text-anchor="middle">SUMO · CityFlow</text>
<path d="M350,40 C470,40 470,255 355,255" fill="none" stroke="{C['teal']}" stroke-width="3" marker-end="url(#ah)"/>
<text x="385" y="150" font-size="14" font-weight="800" fill="{C['teal']}" text-anchor="middle">action a(t)</text>
<path d="M170,255 C50,255 50,40 165,40" fill="none" stroke="{C['teal']}" stroke-width="3" marker-end="url(#ah)"/>
<text x="135" y="120" font-size="14" font-weight="800" fill="{C['teal']}" text-anchor="middle">o(t+1)</text>
<text x="135" y="185" font-size="14" font-weight="800" fill="{C['coral']}" text-anchor="middle">reward r(t)</text>
<rect x="190" y="118" width="140" height="50" rx="8" fill="#F7EFD9" stroke="#EAD9A8"/>
<text x="260" y="140" font-size="13.5" font-weight="700" fill="{C['ink']}" text-anchor="middle">Replay buffer</text>
<text x="260" y="157" font-size="12" fill="{C['muted']}" text-anchor="middle">cập nhật khi training</text>
</svg>'''


def mlp_svg(inp: str, outs: list[str], w=520, h=250, dueling=False):
    cols = [(inp, 1), ("64", 2), ("64", 3)]
    xs = [40, 170, 300]
    out = [f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" font-family="BVP">']
    inner = h - 30
    heights = [inner * 0.75, inner, inner]
    for (lab, _), x, hh in zip(cols, xs, heights):
        y0 = 26 + (inner - hh) / 2
        out.append(f'<rect x="{x}" y="{y0}" width="70" height="{hh}" rx="10" fill="{C["paleTeal"]}" stroke="#BFDDD7"/>')
        for k in range(6):
            cy = y0 + 20 + k * (hh - 40) / 5
            out.append(f'<circle cx="{x+35}" cy="{cy:.1f}" r="7" fill="{C["teal"]}" opacity="0.75"/>')
        out.append(f'<text x="{x+35}" y="{y0-8}" font-size="15" font-weight="800" text-anchor="middle" fill="{C["navy"]}">{lab}</text>')
    for x in (110, 240):
        out.append(f'<path d="M{x+4},{h/2} L{x+56},{h/2}" stroke="{C["slate"]}" stroke-width="2"/>')
        out.append(f'<text x="{x+30}" y="{h/2-8}" font-size="11" text-anchor="middle" fill="{C["muted"]}">ReLU</text>')
    if dueling:
        out.append(f'<path d="M370,{h/2} C400,{h/2} 400,60 425,60" stroke="{C["slate"]}" fill="none" stroke-width="2"/>')
        out.append(f'<path d="M370,{h/2} C400,{h/2} 400,170 425,170" stroke="{C["slate"]}" fill="none" stroke-width="2"/>')
        out.append(f'<rect x="425" y="40" width="85" height="40" rx="8" fill="{C["navy"]}"/><text x="467" y="66" font-size="14" font-weight="800" fill="#fff" text-anchor="middle">V (1)</text>')
        out.append(f'<rect x="425" y="150" width="85" height="40" rx="8" fill="{C["coral"]}"/><text x="467" y="176" font-size="14" font-weight="800" fill="#fff" text-anchor="middle">A (3)</text>')
        out.append(f'<text x="467" y="118" font-size="12" font-weight="700" fill="{C["ink"]}" text-anchor="middle">V + A − mean(A)</text>')
        out.append(f'<text x="467" y="222" font-size="13" font-weight="800" fill="{C["teal"]}" text-anchor="middle">→ 3 Q-values</text>')
    else:
        out.append(f'<path d="M370,{h/2} L425,{h/2}" stroke="{C["slate"]}" stroke-width="2"/>')
        out.append(f'<rect x="425" y="{h/2-22}" width="85" height="44" rx="8" fill="{C["navy"]}"/><text x="467" y="{h/2+5}" font-size="14" font-weight="800" fill="#fff" text-anchor="middle">{outs[0]}</text>')
    out.append("</svg>")
    return "".join(out)


def flow(items, arrow="→"):
    parts = []
    for i, it in enumerate(items):
        if i:
            parts.append(f'<div class="arrow">{arrow}</div>')
        cls, b, t = it if len(it) == 3 else ("", it[0], it[1])
        parts.append(f'<div class="box {cls}"><b>{b}</b>{t}</div>')
    return f'<div class="flow">{"".join(parts)}</div>'


def table(headers, rows, cls="t", align=None, hl=None, hlc=None):
    align = align or [""] * len(headers)
    th = "".join(f'<th class="{a}">{h}</th>' for h, a in zip(headers, align))
    body = []
    for i, r in enumerate(rows):
        rc = ' class="hl"' if hl and i in hl else (' class="hlc"' if hlc and i in hlc else "")
        body.append(f"<tr{rc}>" + "".join(f'<td class="{a}">{c}</td>' for c, a in zip(r, align)) + "</tr>")
    return f'<table class="{cls}"><tr>{th}</tr>{"".join(body)}</table>'


# ---------------------------------------------------------------- slides
S: list[dict] = []


def slide(section, title, body, *, secs, source="", kind="", notes=None, kicker=None):
    S.append(dict(section=section, title=title, body=body, secs=secs, source=source,
                  kind=kind, notes=notes or {}, kicker=kicker))


def N(say, keys, avoid=None, qa=None):
    return dict(say=say, keys=keys, avoid=avoid or [], qa=qa or [])


# 01 — Cover -----------------------------------------------------------------
cover = f'''
<svg width="1280" height="720" style="position:absolute;left:0;top:0" xmlns="http://www.w3.org/2000/svg">
  <g opacity="0.16" stroke="#7FD1C7" stroke-width="2" fill="none">
    <path d="M820 0 L900 720"/><path d="M980 0 L1010 720"/><path d="M1130 0 L1100 720"/>
    <path d="M760 160 L1280 120"/><path d="M740 360 L1280 390"/><path d="M800 560 L1280 600"/>
  </g>
  <g fill="#7FD1C7">
    <circle cx="842" cy="155" r="6"/><circle cx="990" cy="143" r="6"/><circle cx="1123" cy="131" r="6"/>
    <circle cx="870" cy="366" r="6"/><circle cx="998" cy="372" r="6"/><circle cx="1110" cy="381" r="6"/>
    <circle cx="890" cy="567" r="6"/><circle cx="1005" cy="577" r="6"/><circle cx="1102" cy="585" r="6"/>
  </g>
  <g fill="#E07A62"><circle cx="998" cy="372" r="15" opacity=".9"/></g>
</svg>
<div style="position:absolute;left:84px;top:70px;font-size:15px;font-weight:700;letter-spacing:.16em;color:#7FD1C7">BẢO VỆ LUẬN VĂN THẠC SĨ · KỸ THUẬT PHẦN MỀM</div>
<div style="position:absolute;left:84px;top:118px;width:780px;font-size:43px;line-height:1.14;font-weight:800;color:#fff">Học tăng cường cho điều khiển đèn giao thông Đà Nẵng, có kiểm soát bằng chứng</div>
<div style="position:absolute;left:84px;top:300px;width:720px;font-size:21px;line-height:1.4;color:#C9D8E4">Từ một nút giao có dữ liệu công bố (SUMO) đến thí nghiệm 53 nút có đèn tại quận Hải Châu (CityFlow)</div>
<div style="position:absolute;left:84px;top:392px;width:720px;font-size:15px;line-height:1.4;color:#8FA9BE;font-style:italic">Evidence-Aware Reinforcement Learning for Da Nang Traffic Signal Control: From an Empirical Intersection Anchor to a District-Scale Experiment</div>
<div style="position:absolute;left:84px;top:500px;font-size:15px;color:#8FA9BE;letter-spacing:.08em">HỌC VIÊN</div>
<div style="position:absolute;left:84px;top:522px;font-size:25px;font-weight:800;color:#fff">{AUTHOR}</div>
<div style="position:absolute;left:420px;top:500px;font-size:15px;color:#8FA9BE;letter-spacing:.08em">GIẢNG VIÊN HƯỚNG DẪN</div>
<div style="position:absolute;left:420px;top:522px;font-size:19px;font-weight:600;color:#fff;line-height:1.4">Dr. Le Van Minh</div>
<div style="position:absolute;left:84px;top:640px;font-size:15px;color:#8FA9BE">FPT University · Đà Nẵng, 2026</div>
'''
slide("Mở đầu", "", cover, secs=30, kind="cover", notes=N(
    "Kính thưa Hội đồng, em là Lương Quang Khang. Hôm nay em trình bày luận văn về học tăng cường cho điều khiển đèn giao thông tại Đà Nẵng. "
    "Luận văn có hai tầng thí nghiệm: một nút giao có dữ liệu công bố, mô phỏng bằng SUMO, và một mạng 53 nút có đèn ở Hải Châu, mô phỏng bằng CityFlow. "
    "Chữ “có kiểm soát bằng chứng” trong tên đề tài là trọng tâm: em không chỉ báo con số, mà luôn nói con số đó đến từ đâu và được phép kết luận tới mức nào.",
    ["Hai tầng: 1 nút SUMO + 53 nút CityFlow", "Trọng tâm: bằng chứng có truy vết", "Nói chậm, nhìn Hội đồng"],
    ["Không mở đầu bằng lời hứa “RL luôn tốt hơn”."]))

# 02 — Roadmap ---------------------------------------------------------------
agenda_items = [
    ("1", "Bài toán & câu hỏi nghiên cứu", "Vì sao cần điều khiển thích nghi · 3 RQ · thiết kế hai tầng", "05:15"),
    ("2", "Dữ liệu & mô phỏng", "Nguồn công bố · độ tin cậy · dựng demand · seeds", "05:45"),
    ("3", "Nền tảng RL", "Q-value · Double DQN · Dueling", "02:45"),
    ("4", "Tầng SUMO — 1 nút giao", "State 16 chiều · training · metric & baseline", "04:30"),
    ("5", "Tầng CityFlow — 53 nút", "Residual theo lịch · anchor · 27 features · selector", "06:30"),
    ("6", "Kết quả", "SUMO theo regime · baseline mạnh · gate nhiều seed", "07:15"),
    ("7", "Demo & kết luận", "Replay có truy vết · đóng góp · giới hạn · bước tiếp", "06:15"),
]
ag = "".join(
    f'<div style="display:flex;align-items:center;gap:18px;padding:11px 0;border-bottom:1px solid {C["line"]}">'
    f'<span class="num-badge teal">{n}</span><div style="flex:1"><div style="font-size:21px;font-weight:700;color:{C["navy"]}">{t}</div>'
    f'<div class="small muted">{d}</div></div><div class="mono" style="font-size:15px;color:{C["teal"]};font-weight:700">{m}</div></div>'
    for n, t, d, m in agenda_items)
slide("Mở đầu", "Lộ trình trình bày · khoảng 38 phút + dự phòng", f'''
<div class="row" style="gap:40px">
 <div style="flex:1.6">{ag}</div>
 <div style="flex:1">
  <div class="card navy" style="margin-top:6px"><h4>Một câu cần nhớ</h4>
   <div style="font-size:21px;line-height:1.4;font-weight:600;color:#fff">Lợi ích của RL <span style="color:#F2C66D">phụ thuộc chế độ nhu cầu và baseline</span>. Kết quả là bằng chứng mô phỏng, chưa phải hiệu quả ngoài hiện trường.</div></div>
  <div class="card" style="margin-top:16px"><h4>Quy ước trên slide</h4>
   <ul class="clean small"><li><b>Regime</b>: normal · AM peak · PM peak</li><li><b>veh-h</b>: vehicle-hours của queue + pending</li><li>Số âm của “change” = tốt; số dương của “reduction” = tốt</li><li>Mỗi kết quả ghi rõ simulator, seed, số case</li></ul></div>
 </div>
</div>''', secs=45, notes=N(
    "Bài trình bày đi theo bảy phần. Em bắt đầu bằng bài toán và ba câu hỏi nghiên cứu, rồi nói dữ liệu đến từ đâu và được biến thành mô phỏng thế nào. "
    "Sau phần nền tảng RL ngắn, em giải thích hai model: SUMO cho một nút và CityFlow cho mạng 53 nút. Phần kết quả trình bày cả kết quả tốt và kết quả xấu, sau đó là demo và kết luận. "
    "Câu em muốn Hội đồng nhớ: lợi ích phụ thuộc regime và baseline, và đây là bằng chứng mô phỏng.",
    ["7 phần, cột phải là thời lượng", "Câu cần nhớ = luận điểm trung tâm", "Nhắc quy ước dấu của % change/reduction"]))

# 03 — Problem ---------------------------------------------------------------
cyc = [("G1", 32, C["teal"]), ("Y", 7, "#E7B94A"), ("G2", 28, "#3E6E9A"), ("Y", 7, "#E7B94A"), ("G3", 22, C["coral"]), ("Y", 7, "#E7B94A")]
cycbar = '<div style="display:flex;height:46px;border-radius:8px;overflow:hidden">' + "".join(
    f'<div style="flex:{v};background:{c};color:#fff;font-weight:800;font-size:14px;display:flex;align-items:center;justify-content:center">{n} {v}s</div>' if v > 7 else
    f'<div style="flex:{v};background:{c};color:#5A4300;font-weight:800;font-size:11px;display:flex;align-items:center;justify-content:center">{v}</div>'
    for n, v, c in cyc) + "</div>"
slide("Mở đầu", "Lịch đèn cố định không đổi theo nhu cầu — hàng chờ thì thay đổi", f'''
<div class="row" style="gap:28px">
 <div style="flex:1.05">
  <div class="card"><h4>Lịch công bố tại nút nghiên cứu · chu kỳ 103 giây</h4>{cycbar}
   <div class="small" style="margin-top:10px">Green 32 / 28 / 22 giây + 3 lần yellow 7 giây. Lịch lặp lại dù lưu lượng từng hướng thay đổi theo giờ.</div></div>
  <div class="card tealfill" style="margin-top:16px"><h4>Điều khiển thích nghi</h4>
   <div style="font-size:19px">Quan sát giao thông → thay đổi quyết định đèn → <b>giảm tổng hàng chờ</b>.<br>Học tăng cường (RL) học quy tắc đó từ <b>hậu quả</b> của hành động trong simulator, không cần nhãn “hành động đúng”.</div></div>
  <div class="callout gold" style="margin-top:16px">Câu hỏi thực tế: <b>khi nào</b> điều khiển học được giúp, so với <b>baseline nào</b>, và bằng chứng <b>chắc đến đâu</b>?</div>
 </div>
 <div style="flex:1">
  <div style="font-size:15px;font-weight:700;letter-spacing:.1em;color:{C["coral"]};margin-bottom:8px">BA KHÓ KHĂN</div>
  <div class="card" style="display:flex;gap:14px;margin-bottom:12px"><span class="num-badge coral">1</span><div><b class="navyc">Tác động xuất hiện trễ</b><div class="small">Đổi đèn bây giờ làm hàng xe giảm sau nhiều giây và lan sang các nút kế tiếp.</div></div></div>
  <div class="card" style="display:flex;gap:14px;margin-bottom:12px"><span class="num-badge coral">2</span><div><b class="navyc">Lợi ích có thể xung đột</b><div class="small">Giải phóng một nút có thể đẩy xe vào đoạn phía sau đã đầy (spillback).</div></div></div>
  <div class="card" style="display:flex;gap:14px"><span class="num-badge coral">3</span><div><b class="navyc">Bằng chứng có giới hạn</b><div class="small">Camera công bố chỉ bao phủ 4 movement của một nút, một ngày. Toàn mạng cần giả định về routes, flows và lịch đèn.</div></div></div>
 </div>
</div>''', secs=75, source="Nguồn timing: Phan, Le & Nguyen (2025), trang 7 và Hình 4 trang 8", notes=N(
    "Một lịch đèn cố định chia thời gian xanh theo chu kỳ lặp. Ở nút nghiên cứu, lịch công bố là 32, 28 và 22 giây xanh cùng ba lần vàng 7 giây, tổng 103 giây. "
    "Khi lưu lượng giữa các hướng thay đổi, lịch này có thể cấp xanh cho hướng ít xe trong khi hướng khác đang ùn. Điều khiển thích nghi quan sát giao thông và thay đổi quyết định để giảm tổng hàng chờ. "
    "Bài toán khó vì ba lý do: tác động đến trễ, lợi ích giữa các nút có thể xung đột, và dữ liệu thực tế rất hạn chế. Vì vậy câu hỏi đúng không phải “RL có tốt không”, mà là khi nào, so với baseline nào và chắc đến đâu.",
    ["103 s = 32+28+22 + 3×7", "3 khó khăn: trễ · xung đột · dữ liệu", "Câu hỏi: khi nào / so với gì / chắc đến đâu"]))

# 04 — Research questions ------------------------------------------------------
rq = [
    ("RQ1", "RL có giảm hàng chờ tại nút giao có dữ liệu công bố không?", "SUMO · 3 regime · 5 learning seeds", "Nút mô phỏng với hình học, demand và giả định đã mô tả", C["teal"]),
    ("RQ2", "Một policy dùng chung cho 53 nút có học được các chỉnh sửa lịch hữu ích không?", "CityFlow · schedule-residual Double DQN", "Mạng mô phỏng, nhu cầu tổng hợp", "#3E6E9A"),
    ("RQ3", "Kết quả còn đáng tin sau khi xét baseline mạnh, seed, pending và nguồn dữ liệu?", "Baseline · thống kê · selector · evidence audit", "Bằng chứng hiện có và các khoảng trống còn lại", C["coral"]),
]
rqh = "".join(f'''<div class="card" style="flex:1;border-top:6px solid {c};display:flex;flex-direction:column">
 <div style="font-size:30px;font-weight:800;color:{c}">{k}</div>
 <div style="font-size:19.5px;font-weight:700;color:{C["navy"]};line-height:1.32;margin:6px 0 14px;min-height:104px">{q}</div>
 <div class="xsmall muted" style="letter-spacing:.08em;font-weight:700">THÍ NGHIỆM TRẢ LỜI</div><div class="small" style="margin-bottom:10px">{e}</div>
 <div class="xsmall muted" style="letter-spacing:.08em;font-weight:700">PHẠM VI KẾT LUẬN</div><div class="small">{s}</div></div>''' for k, q, e, s, c in rq)
slide("Mở đầu", "Ba câu hỏi nghiên cứu", f'''
<div class="row" style="gap:20px">{rqh}</div>
<div class="callout navy" style="margin-top:22px;font-size:18px"><b>Luận điểm trung tâm:</b> thesis kiểm tra <b>khi nào</b> điều khiển thích nghi giảm hàng chờ trong các kịch bản mô phỏng có kiểm soát. Kết quả phụ thuộc chế độ nhu cầu và baseline; bằng chứng hiện có <b>chưa xác nhận hiệu quả vận hành thực địa</b>.</div>
''', secs=75, notes=N(
    "Luận văn trả lời ba câu hỏi. RQ1: tại một nút có dữ liệu công bố, RL có giảm hàng chờ không — trả lời bằng SUMO với ba regime và năm learning seed. "
    "RQ2: một policy dùng chung trọng số cho 53 nút có học được các chỉnh sửa lịch đèn hữu ích không — trả lời bằng CityFlow và controller schedule-residual. "
    "RQ3 là câu hỏi về độ tin cậy: sau khi so với baseline mạnh, xét nhiều seed, tính cả xe chưa vào được mạng và kiểm tra nguồn dữ liệu, kết quả còn đứng vững đến đâu. "
    "Mỗi câu có phạm vi kết luận riêng, và em sẽ giữ đúng phạm vi đó đến cuối.",
    ["RQ1 = SUMO 1 nút", "RQ2 = CityFlow 53 nút, shared policy", "RQ3 = độ tin cậy của bằng chứng"],
    ["Không nói “chứng minh RL tốt hơn”; nói “kiểm tra khi nào giúp”."]))

# 05 — Two-tier design -------------------------------------------------------
two = table(["", "SUMO · một nút giao", "CityFlow · mạng Hải Châu"], [
    ["Vai trò", "Kiểm tra tại nút có nguồn công bố", "Khả năng mở rộng & tương tác giữa nút"],
    ["Quy mô", "1 nút · 4 approach · 3 green phase", "<b>53</b> nút có đèn, topology OSM"],
    ["Model", "Dueling <b>Double</b> DQN, n-step = 3", "Schedule-residual <b>Double</b> DQN"],
    ["Input → output", "Vector 16 số → 3 Q-value", "27 số / macro ứng viên → 1 Q"],
    ["Nhịp quyết định", "10 giây", "Macro 300 giây (request mỗi 10 s)"],
    ["Reward", "−queue cuối bước 10 s × 0,01", "−(queue + pending) tích phân toàn mạng / 100.000"],
    ["Train", "30 episode × 3.600 s · seeds 11–15", "12 episode × 3.600 s · seeds 12–16"],
    ["Baseline fixed", "Lịch công bố 103 s", "Fixed nominal green 25 s, chọn trên validation"],
    ["Test", "15 case (3 regime × 5)", "15 case (3 regime × 5)"],
], cls="t compact", align=["", "", ""])
slide("Mở đầu", "Thiết kế hai tầng: hai simulator, hai model, hai câu hỏi", f'''
<div class="row" style="gap:24px">
 <div style="flex:1.7">{two}</div>
 <div style="flex:1">
  <div class="vflow">
   <div class="box" style="background:#F7EFD9;border-color:#EAD9A8"><b>Bài báo Đà Nẵng</b><br><span class="xsmall">timing · turning table · camera plots</span></div><div class="down">↓</div>
   <div class="box"><b>CSV + giả định có ghi nguồn</b></div><div class="down">↓</div>
   <div style="display:flex;gap:8px"><div class="box" style="flex:1;background:{C["paleTeal"]}"><b>SUMO</b><br><span class="xsmall">1 nút</span></div><div class="box" style="flex:1;background:#E3EAF2"><b>CityFlow</b><br><span class="xsmall">53 nút + OSM</span></div></div><div class="down">↓</div>
   <div class="box"><b>Đánh giá ghép cặp</b><br><span class="xsmall">cùng demand · baseline · nhiều seed</span></div><div class="down">↓</div>
   <div class="box" style="background:{C["navy"]};color:#fff;border-color:{C["navy"]}"><b>Bảng kết quả · giới hạn · demo</b></div>
  </div>
  <div class="callout" style="margin-top:14px;font-size:15.5px"><b>Không chuyển trọng số</b> từ SUMO sang CityFlow. Hai tầng nối nhau qua câu hỏi nghiên cứu và hình dạng nhu cầu, không phải train rồi fine-tune.</div>
 </div>
</div>''', secs=90, source="docs/defense/thesis-understanding-guide-vi.md, mục 2", notes=N(
    "Thiết kế có hai tầng. Tầng SUMO là một nút giao có nguồn công bố — đây là neo thực nghiệm. Model là dueling Double DQN, nhận 16 số và trả 3 Q-value cho 3 green phase, quyết định mỗi 10 giây. "
    "Tầng CityFlow là mạng 53 nút có đèn dựng từ OpenStreetMap với nhu cầu tổng hợp. Model là schedule-residual Double DQN: mỗi 300 giây, mỗi nút chọn một chỉnh sửa nhỏ của lịch đèn; một MLP dùng chung chấm điểm từng ứng viên. "
    "Điểm quan trọng: không có chuyển trọng số giữa hai simulator. Hai phần có kiến trúc, reward và quy trình train khác nhau; chúng chỉ nối với nhau qua câu hỏi nghiên cứu và nguồn hình dạng nhu cầu.",
    ["SUMO: 16 → 3 Q, 10 s", "CityFlow: 27/macro → 1 Q, 300 s, shared 53 nút", "Không transfer weights"],
    ["Không vẽ một cột “RL” gộp hai model."],
    [("Hai phần liên quan gì nhau?", "Cùng câu hỏi nghiên cứu và cùng nguồn hình dạng nhu cầu camera; không chung trọng số.")]))

# 06 — Published source --------------------------------------------------------
src_rows = [
    ["Hình học, số làn 2/2/3/3", "Trang 7", "Dựng nút SUMO"],
    ["Green 32/28/22 s, chu kỳ 103 s", "Trang 7 · Hình 4 tr. 8", "Baseline published fixed"],
    ["12 turning movements, 6.171 PCU/h", "Bảng 1 tr. 8 (volume 2022)", "Bối cảnh phân bổ movement"],
    ["Camera 01/04/2025, 06:00–18:00", "Trang 16", "Thời điểm nguồn camera"],
    ["2 camera, 4 đường đo movement", "Hình 12 tr. 17", "Phạm vi thực sự quan sát"],
    ["PCU: xe máy 0,3 · ô tô 1 · bus 2 · truck 2,5", "Trang 19", "Hiểu quy đổi của bài nguồn"],
    ["Số xe theo giờ và loại xe", "Hình 17–18 tr. 20", "Số hóa xấp xỉ thành CSV"],
    ["Raw data không công khai", "Trang 23", "Giới hạn tiếp cận dữ liệu gốc"],
]
slide("Dữ liệu", "Dữ liệu nguồn: một bài báo công bố về một nút giao Đà Nẵng", f'''
<div class="row" style="gap:24px">
 <div style="width:390px;flex:none">
  <img class="fig" src="{img("junction")}" style="width:390px;height:390px;object-fit:contain">
  <div class="cap">Nút Lê Thanh Nghị – Cách Mạng Tháng 8 – 2/9, phía cầu Hòa Xuân. Bốn đường movement được hai camera quan sát; approach mô hình hóa dài khoảng 300 m.</div>
 </div>
 <div style="flex:1">
  <div class="card goldfill" style="padding:12px 16px;margin-bottom:12px"><div class="small"><b>Phan, Le & Nguyen (2025).</b> <i>Application of Dueling Double Deep Q-Network for Dynamic Traffic Signal Optimization: A Case Study in Danang City, Vietnam.</i> MAKE 7(3):65 · DOI 10.3390/make7030065</div></div>
  {table(["Nội dung", "Vị trí trong PDF", "Dự án dùng để"], src_rows, cls="t compact")}
  <div class="callout" style="margin-top:12px;font-size:15px">Tên đường trong nguồn không nhất quán (trang 7 ghi “Nguyenthanhnghi”); thesis theo Bảng 1/Hình 12. <b>PCU/h khác veh/h</b> — không cộng lẫn hai đơn vị.</div>
 </div>
</div>''', secs=105, source="datasets/danang_published/sources/phan2025_make7030065.pdf · số trang PDF 1–24", notes=N(
    "Nguồn chính là bài báo của Phan, Le và Nguyen năm 2025 trên tạp chí MAKE. Em dùng bài này vì nó công bố hình học, lịch đèn và số liệu camera của đúng một nút giao Đà Nẵng. "
    "Mỗi thông tin em dùng đều có vị trí trang: hình học ở trang 7, lịch 103 giây ở trang 7 và Hình 4, bảng 12 turning movements ở Bảng 1 trang 8, camera ngày 1/4/2025 ở trang 16, hai camera và bốn đường đo ở Hình 12, hệ số PCU ở trang 19, và biểu đồ số xe theo giờ ở Hình 17–18. "
    "Hai điều cần nói trước: bài nguồn ghi tên đường không nhất quán, và bảng turning dùng đơn vị PCU/h — xe con tương đương — nên không được cộng với số phương tiện. Raw video không được công bố.",
    ["Phan, Le & Nguyen 2025 · MAKE · DOI make7030065", "Mỗi số có trang/hình/bảng", "PCU ≠ số xe; raw data không có"],
    ["Không gọi file tran2025 là tác giả Tran — nguồn đã xác minh là Phan et al."],
    [("Dữ liệu có phải thực địa không?", "Phần camera là số công bố, được số hóa xấp xỉ từ biểu đồ; một ngày, bốn movement. Phần còn lại là giả định mô phỏng có ghi nguồn.")]))

# 07 — CSV & trust tiers -----------------------------------------------------
tiers = [
    ("Nguồn công bố", "PDF, timing, turning table, biểu đồ camera", "“Theo bài báo tại trang/hình/bảng…”", C["navy"]),
    ("Trích xuất từ nguồn", "Số đọc xấp xỉ trong CSV", "“Digitized approximate counts…”", C["teal"]),
    ("Dựng mô phỏng", "Mở rộng toàn nút, routes, vehicle templates", "“Giả định/ước lượng để dựng kịch bản…”", C["gold"]),
    ("Đầu ra mô phỏng", "Queue integral, completion, reward", "“Kết quả trong simulator với cấu hình…”", C["coral"]),
]
tier_html = "".join(f'''<div style="display:flex;gap:12px;align-items:stretch;margin-bottom:8px">
 <div style="width:8px;border-radius:4px;background:{c}"></div>
 <div style="flex:1"><div style="font-weight:800;color:{c};font-size:17px">{i+1}. {n}</div><div class="xsmall">{e}</div><div class="xsmall muted"><i>{s}</i></div></div></div>''' for i, (n, e, s, c) in enumerate(tiers))
slide("Dữ liệu", "Camera CSV: 48 dòng số hóa từ biểu đồ — và bốn tầng độ tin cậy", f'''
<div class="row" style="gap:24px">
 <div style="flex:1.35">
  <img class="fig" src="{img("camera")}" style="width:100%;height:300px;object-fit:contain">
  <div class="cap">Tổng số hóa trên bốn đường movement của camera, ngày 01/04/2025. Ba điểm tô màu là ba mức nhu cầu dùng cho test SUMO.</div>
  <div class="row" style="gap:12px;margin-top:12px">
   <div class="card" style="flex:1;padding:10px 14px"><div class="mid">48</div><div class="xsmall">dòng = 4 movement × 12 nhãn giờ (07:00–18:00)</div></div>
   <div class="card" style="flex:1;padding:10px 14px"><div class="mid">192</div><div class="xsmall">giá trị xấp xỉ: car, motorcycle, truck, bus</div></div>
   <div class="card" style="flex:1;padding:10px 14px"><div class="mid">1 ngày</div><div class="xsmall">không suy ra tính đại diện nhiều mùa</div></div>
  </div>
 </div>
 <div style="flex:1">
  <div class="card"><h4>Bốn tầng độ tin cậy</h4>{tier_html}</div>
  <div class="callout gold" style="margin-top:12px;font-size:14.5px">Dung sai đọc ±15/±30 veh/h là <b>sai số đọc</b> do dự án đặt, không phải confidence interval. SHA-256 chứng minh file đúng byte, <b>không</b> chứng minh số đúng ngoài đời.</div>
 </div>
</div>''', secs=75, source="datasets/danang_published/phan2025_camera_hourly_digitized.csv · docs/research/danang-data-claim-audit.md", notes=N(
    "Từ biểu đồ Hình 17–18, em số hóa thành CSV: 4 movement nhân 12 nhãn giờ là 48 dòng, mỗi dòng 4 loại xe, tổng 192 giá trị xấp xỉ, của một ngày duy nhất. "
    "Ba điểm được tô là ba mức dùng cho test: 13 giờ 1.395 xe là normal, 8 giờ 2.330 xe là AM, 17 giờ 2.400 xe là PM. Đây là tổng trên bốn đường đo, không phải toàn nút. "
    "Để nói đúng mức độ, em chia bằng chứng thành bốn tầng: nguồn công bố, số trích xuất, giả định dựng mô phỏng và đầu ra mô phỏng. Mỗi tầng có cách nói riêng. "
    "Dung sai đọc ±15/±30 là sai số đọc biểu đồ, chưa phải khoảng tin cậy; và hash SHA-256 chỉ chứng minh file không bị thay đổi.",
    ["48 dòng · 192 giá trị · 1 ngày", "1.395 / 2.330 / 2.400 = normal / AM / PM", "4 tầng: nguồn → trích xuất → giả định → đầu ra"],
    ["Không nói “2.400 xe là tổng lưu lượng cả nút”."]))

# 08 — Data to simulation --------------------------------------------------------
slide("Dữ liệu", "Từ dữ liệu nguồn đến nhu cầu mô phỏng", f'''
<div class="row" style="gap:22px">
 <div class="card" style="flex:1"><h4>Tầng SUMO · một nút</h4>
  <div class="vflow small">
   <div class="box">Timing + hình học công bố → <b>nút & chương trình đèn</b></div><div class="down">↓</div>
   <div class="box">Camera CSV, 4 movement → <b>demand protocol chính</b></div><div class="down">↓</div>
   <div class="box">Demand seed → routes & giờ khởi hành (.rou.xml)</div><div class="down">↓</div>
   <div class="box">Simulator seed → ngẫu nhiên trong SUMO</div>
  </div>
  <div class="row" style="gap:8px;margin-top:12px;text-align:center">
   <div class="card tealfill" style="flex:1;padding:8px"><div class="mid">1.395</div><div class="xsmall">xe/h · normal</div></div>
   <div class="card tealfill" style="flex:1;padding:8px"><div class="mid">2.330</div><div class="xsmall">xe/h · AM (train)</div></div>
   <div class="card tealfill" style="flex:1;padding:8px"><div class="mid">2.400</div><div class="xsmall">xe/h · PM</div></div>
  </div>
  <div class="xsmall muted" style="margin-top:8px">Mức toàn nút ~5.793/9.676/9.967 là <b>ước lượng mở rộng</b>, không phải số protocol chính.</div>
 </div>
 <div class="card" style="flex:1.25"><h4>Tầng CityFlow · 53 nút Hải Châu</h4>
  <div class="formula" style="font-size:13.5px">Vietnam OSM PBF <span class="c">→</span> osmium extract <span class="c">→</span> SUMO netconvert
            <span class="c">→</span> CityFlow roadnet <span class="c">→</span> kiểm tra phase contract</div>
  <div class="xsmall muted" style="margin:4px 0 8px">Geofabrik · ODbL · bbox 108.1888, 16.0213 – 108.2360, 16.1037 · mạng <b>suy dẫn đã xử lý</b>, không phải toàn bộ đèn hiện trường.</div>
  {table(["Thuộc tính", "Giá trị"], [
      ["Controlled intersections", "<b>53</b>"],
      ["Route families", "1.290 → train/val/test = 644/323/323"],
      ["Route streams mỗi case", "500 (mỗi stream phát nhiều xe)"],
      ["Vehicle mix", "motorcycle 0,90 · car còn lại (giả định)"],
      ["Episode", "3.600 s = 3 bin × 1.200 s"],
  ], cls="t compact")}
  <div class="formula" style="font-size:13.5px;margin-top:8px"><span class="m">interval_bin =</span> 240 × <span class="g">1603,33</span> / source_count_bin   <span class="m"># PM 2.400 → 160,3 s</span></div>
 </div>
</div>
<div class="callout" style="margin-top:12px;font-size:15.5px"><b>500 routes ≠ 500 xe.</b> Profile chỉ mượn <b>hình dạng tương đối</b> của nhu cầu camera; ba giờ nguồn được nén thành ba đoạn 20 phút.</div>
''', secs=105, source="configs/haichau_network_v2.yaml · src/traffic_rl/network/haichau_dataset.py · datasets/haichau_network_v2/provenance.json", notes=N(
    "Ở SUMO, timing và hình học tạo nút giao và chương trình đèn; camera CSV tạo nhu cầu cho protocol chính: 1.395 xe normal, 2.330 xe AM và 2.400 xe PM trong một giờ. Demand seed quyết định lịch khởi hành, simulator seed quyết định phần ngẫu nhiên. Các con số toàn nút khoảng 9.700 xe chỉ là ước lượng mở rộng. "
    "Ở CityFlow, topology lấy từ OpenStreetMap qua osmium, netconvert và converter sang roadnet của CityFlow. Kết quả là mạng suy dẫn có 53 nút có đèn. "
    "Nhu cầu mạng là tổng hợp: 1.290 route families chia train/validation/test, mỗi case 500 route streams, 90% xe máy là giả định lấy mẫu. Hình dạng theo giờ của camera điều biến interval phát xe: giờ đông hơn thì interval ngắn hơn, ví dụ 2.400 xe cho interval khoảng 160 giây. "
    "Nhấn mạnh: 500 route streams không phải 500 xe, và case PM không phát lại nguyên ba giờ thực địa.",
    ["SUMO: 1.395 / 2.330 / 2.400", "CityFlow: OSM → 53 signals, 1.290 route families", "Profile = hình dạng tương đối, không phải số đếm"],
    ["Không nói mạng 53 nút là toàn bộ đèn thực tế Hải Châu."],
    [("Tại sao 53 nút?", "Là số controlled signals sau pipeline OSM → netconvert → CityFlow với các bước gộp/lọc có ghi lại trong provenance.")]))

# 09 — Splits & seeds -----------------------------------------------------------
slide("Dữ liệu", "Chia dữ liệu và ba loại seed", f'''
<div class="row" style="gap:26px">
 <div style="flex:1.2">
  {table(["Split (CityFlow)", "Demand seeds", "Simulator seeds", "Cases"], [
      ["Train", "11, 12, 13", "111, 112, 113", "3 regime × 3 = 9"],
      ["Validation", "31, 32", "131, 132", "3 regime × 2 = 6"],
      ["Test", "101–105", "201–205", "3 regime × 5 = <b>15</b>"],
  ], align=["", "c", "c", ""])}
  <div class="card" style="margin-top:14px"><h4>SUMO</h4><div class="small">Train AM demand11/sim11 · validation AM demand31/sim31 — <b>giữ chung</b> cho mọi learning seed. Test: 15 case (3 regime × 5).</div></div>
  <div class="callout gold" style="margin-top:14px;font-size:15px">Route-family split tách họ tuyến, nhưng tuyến vẫn có thể đi qua cùng đoạn đường và cùng nút. Đây <b>không</b> phải đánh giá trên thành phố chưa thấy.</div>
 </div>
 <div style="flex:1">
  <div class="card" style="margin-bottom:12px;border-left:6px solid {C["teal"]}"><b class="navyc">Demand seed</b><div class="small">Lấy mẫu route, loại xe, thời điểm khởi hành.</div></div>
  <div class="card" style="margin-bottom:12px;border-left:6px solid #3E6E9A"><b class="navyc">Simulator seed</b><div class="small">Phần ngẫu nhiên bên trong simulator.</div></div>
  <div class="card" style="margin-bottom:12px;border-left:6px solid {C["coral"]}"><b class="navyc">Learning seed</b><div class="small">Khởi tạo mạng neural, exploration, lấy mẫu replay.</div></div>
  <div class="card tealfill"><div class="small"><b>Cùng demand/simulator seed</b> cho mọi controller → so sánh <b>ghép cặp</b>, giảm nhiễu đầu vào.<br><b>Nhiều learning seed</b> → đo độ biến thiên của việc học.</div></div>
 </div>
</div>''', secs=60, source="results/haichau_network_v2/experiment-manifest.json · results/danang_protocol_v1/experiment-manifest.json", notes=N(
    "Có ba loại seed với ý nghĩa khác nhau. Demand seed quyết định nhu cầu, simulator seed quyết định ngẫu nhiên trong simulator, learning seed quyết định quá trình học. "
    "Trên CityFlow, train có 9 case, validation 6 case và test 15 case, mỗi regime 5 case test. Mọi controller chạy trên cùng các cặp demand/simulator seed, nên chênh lệch là so sánh ghép cặp. "
    "Ở SUMO, train và validation đều là AM và giữ chung cho cả năm learning seed. "
    "Lưu ý: nhiều demand case của cùng một checkpoint không phải là nhiều model độc lập, và route-family split không phải một thành phố mới.",
    ["3 seed: demand · simulator · learning", "Test = 15 case (3 × 5)", "Ghép cặp ≠ nhiều model độc lập"]))

# 10 — RL basics -----------------------------------------------------------------
clocks = "".join(f'''<div style="display:flex;align-items:center;gap:12px;margin:7px 0"><div class="mono" style="width:70px;font-weight:800;font-size:19px;color:{c}">{t}</div><div class="small"><b>{n}</b> — {d}</div></div>'''
                 for t, n, d, c in [("1 s", "Simulator second", "tích phân metric mỗi giây", C["slate"]),
                                    ("10 s", "Control tick", "SUMO chọn phase; CityFlow thực thi 1 request", C["teal"]),
                                    ("300 s", "Macro", "CityFlow residual chọn kế hoạch cho block", C["coral"])])
slide("Nền tảng RL", "Học tăng cường: học từ hậu quả của hành động", f'''
<div class="row" style="gap:26px">
 <div style="width:520px;flex:none">{rl_loop()}
  <div class="small" style="margin-top:6px">Không cần nhãn “action tối ưu”. Reward <b>âm</b> biểu diễn chi phí: <b>ít âm hơn là tốt hơn</b>.</div></div>
 <div style="flex:1">
  <div class="card"><h4>Q-value</h4>
   <div class="formula">Return = r<sub>t</sub> + γ r<sub>t+1</sub> + γ² r<sub>t+2</sub> + …
<span class="c">Greedy action</span> = argmax<sub>a</sub> Q(o, a)</div>
   <div class="small" style="margin-top:8px">Q(o,a) dự đoán tổng reward có chiết khấu khi chọn a tại observation o. Q cao hơn ⇒ chi phí kỳ vọng thấp hơn. Q <b>không</b> phải “số xe giải phóng”.</div></div>
  <div class="card" style="margin-top:14px"><h4>Ba đồng hồ cần phân biệt</h4>{clocks}
   <div class="xsmall muted">Optimizer update là một lần cập nhật trọng số — không phải giây mô phỏng.</div></div>
 </div>
</div>''', secs=75, notes=N(
    "Vòng lặp RL: agent nhận observation, chọn action, simulator thực thi và trả reward cùng observation mới; khi train, kinh nghiệm được lưu vào replay buffer để cập nhật model. "
    "Reward ở đây là âm của hàng chờ, nên ít âm hơn là tốt hơn. Q-value là dự đoán tổng reward có chiết khấu nếu chọn action đó; policy greedy chọn action có Q lớn nhất. "
    "Có ba đồng hồ: simulator chạy từng giây và metric được cộng mỗi giây; control tick 10 giây là lúc SUMO chọn phase; và macro 300 giây là lúc CityFlow residual ra quyết định. Nhớ ba đồng hồ này sẽ tránh nhầm khi đọc tham số.",
    ["Reward âm = chi phí", "Q = return kỳ vọng, không phải số xe", "1 s · 10 s · 300 s"]))

# 11 — Double vs Dueling ------------------------------------------------------
slide("Nền tảng RL", "Double DQN và Dueling giải quyết hai vấn đề khác nhau", f'''
<div class="row" style="gap:24px">
 <div class="card" style="flex:1"><h4>Double DQN = cách dựng target</h4>
  <div class="small">DQN thường dùng cùng một phép max để <b>chọn</b> và <b>đánh giá</b> → khuếch đại sai số lạc quan. Double DQN tách hai vai trò:</div>
  <div class="formula" style="margin:8px 0">a* = argmax<sub>a</sub> Q<sub>online</sub>(o', a)      <span class="m"># online chọn</span>
y  = r + (1 − done)·γ·Q<sub>target</sub>(o', a*) <span class="m"># target đánh giá</span></div>
  {table(["Ví dụ minh họa", "Action A", "Action B"], [["Q online", "<b>−4</b> ✓ chọn", "−5"], ["Q target", "<b>−6</b> → dùng", "−3"]], cls="t compact", align=["", "c", "c"])}
  <div class="xsmall muted" style="margin-top:6px">Target network được copy định kỳ từ online để mục tiêu thay đổi chậm. (van Hasselt et al., 2016)</div>
 </div>
 <div class="card" style="flex:1"><h4>Dueling = cách chia đầu ra mạng</h4>
  <div class="formula" style="margin:4px 0 10px">Q(o,a) = V(o) + A(o,a) − mean<sub>b</sub> A(o,b)</div>
  <ul class="clean small"><li><b>V(o)</b>: trạng thái hiện tại tốt hay xấu</li><li><b>A(o,a)</b>: lợi thế tương đối của từng action</li><li>Trừ mean để cố định cách phân rã V/A</li><li>Hữu ích khi nhiều action có giá trị gần nhau — là <b>động cơ thiết kế</b>, không bảo đảm cải thiện</li></ul>
  <div class="xsmall muted" style="margin-top:6px">(Wang et al., ICML 2016)</div>
 </div>
</div>
<div class="row" style="gap:16px;margin-top:16px">
 <div class="callout teal" style="flex:1"><b>SUMO:</b> dùng <b>cả hai</b> — Double target + Dueling heads, n-step = 3.</div>
 <div class="callout navy" style="flex:1"><b>CityFlow residual:</b> chỉ <b>Double</b> + một scalar head, không dueling.</div>
</div>''', secs=90, notes=N(
    "Double và Dueling thường bị nhầm là một. Double DQN là cách dựng target: online network chọn action tốt nhất ở trạng thái kế tiếp, còn target network đánh giá action đó. "
    "Ví dụ: online dự đoán A = −4, B = −5 nên chọn A; target dự đoán A = −6, B = −3; Double DQN lấy −6 tại A, dù target thích B hơn. Điều này giảm thiên lệch lạc quan. "
    "Dueling là cách thiết kế đầu ra: tách giá trị trạng thái V và lợi thế của từng action A, rồi ghép Q = V + A trừ trung bình A. "
    "Model SUMO dùng cả hai. Model CityFlow chỉ dùng Double với một đầu ra vô hướng cho mỗi macro.",
    ["Double = online chọn, target đánh giá", "Dueling = V + A − mean A", "SUMO: cả hai · CityFlow: chỉ Double"],
    ["Không nói Dueling giảm overestimation — đó là việc của Double."],
    [("Dueling có làm giảm overestimation không?", "Không trực tiếp. Double xử lý chọn/đánh giá target; Dueling chia V/A trong kiến trúc. Hai khía cạnh khác nhau.")]))

# 12 — SUMO model ---------------------------------------------------------------
vec16 = '<div class="vec">' + "".join(
    f'<div class="cell" style="background:{c}">{l}</div>' for l, c in
    [("Q", C["teal"])] * 4 + [("N", "#3E6E9A")] * 4 + [("P", C["coral"])] * 4 + [("φ", C["gold"])] * 3 + [("t", C["slate"])]) + "</div>"
slide("SUMO", "Model SUMO: 16 số vào, 3 Q-value ra, quyết định mỗi 10 giây", f'''
<div class="row" style="gap:24px">
 <div style="flex:1.05">
  <div class="card"><h4>Observation 16 chiều · thứ tự approach NW, SE, NE, SW</h4>{vec16}
   <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:3px 14px;margin-top:8px" class="xsmall">
    <div><b class="teal">1–4</b> queue / 20</div><div><b style="color:#3E6E9A">5–8</b> vehicle count / 20</div><div><b class="coral">9–12</b> pending due / 20</div>
    <div><b class="gold">13–15</b> one-hot green phase</div><div style="grid-column:span 2"><b style="color:{C["slate"]}">16</b> elapsed = min(t, 60) / 60</div></div>
   <div class="xsmall muted" style="margin-top:6px">Ví dụ: queue 10 xe → 0,5. Không bị cắt vào [0,1]: queue 40 xe → 2.</div></div>
  <div class="card" style="margin-top:14px"><h4>Action & thực thi</h4>
   <ul class="clean small"><li>3 action → green phase 0/2/4 của SUMO (1/3/5 là yellow)</li><li>Mỗi <span class="mono">step</span> = <b>10 s</b>; nếu chuyển: <b>7 s yellow</b> rồi green mới</li><li><b>Minimum green 20 s</b>; chuyển quá sớm → giữ phase hiện tại</li><li>Green thực tế có thể dài hơn ngưỡng do tick 10 s + yellow</li></ul></div>
 </div>
 <div style="flex:1">
  <div class="card" style="padding:12px 14px"><h4>Dueling Double DQN</h4>{mlp_svg("16", [], dueling=True)}
   <div class="formula" style="font-size:13.5px">(16×64+64)+(64×64+64)+(64×1+1)+(64×3+3)
= <span class="g">5.508</span> tham số online</div>
   <div class="xsmall muted" style="margin-top:6px">Target network giữ thêm một bản trọng số. Implementation bằng NumPy.</div></div>
  <div class="card goldfill" style="margin-top:14px;padding:10px 14px"><h4 style="color:{C["gold"]}">Minh họa đọc đầu ra</h4>
   <div class="small">Q = [−3,2; <b>−2,7</b>; −4,1] → argmax = action 1 → green phase 2 của SUMO. Nếu phase hiện tại chưa xanh đủ 20 s, environment giữ phase hiện tại.</div></div>
 </div>
</div>''', secs=105, source="src/traffic_rl/sim/sumo_single_junction.py · src/traffic_rl/agents/dqn.py · configs/danang_pilot.yaml", notes=N(
    "Observation của SUMO có 16 số theo thứ tự bốn approach NW, SE, NE, SW: bốn giá trị queue, bốn số xe trên approach, bốn số pending đã đến hạn — đều chia 20 — rồi ba số one-hot cho phase đang xanh và một số thời gian kể từ lần chuyển, chia 60. "
    "Model trả ba Q-value tương ứng ba green phase. Mỗi bước là 10 giây; nếu đổi phase thì có 7 giây vàng rồi mới sang xanh mới. Minimum green 20 giây; nếu yêu cầu đổi quá sớm, environment giữ nguyên phase. "
    "Mạng có hai lớp ẩn 64 nơ-ron ReLU, sau đó tách hai đầu V và A. Tổng 5.508 tham số online, cài đặt bằng NumPy.",
    ["16 = 4 queue + 4 count + 4 pending + 3 one-hot + 1 timer", "10 s step · 7 s yellow · 20 s min green", "16→64→64→V/A→3Q · 5.508 tham số"],
    ["Không nói action là “bật đèn ngay” — luôn qua yellow và min green."],
    [("Vì sao đưa pending vào state?", "Để model thấy xe bị chặn ở biên mạng; nếu không, controller có thể trông tốt nhờ giữ xe ngoài mạng.")]))

# 13 — SUMO training -----------------------------------------------------------
slide("SUMO", "Huấn luyện SUMO: 5 seeds × 30 episode, chọn checkpoint bằng validation", f'''
<div class="row" style="gap:22px">
 <div style="flex:1">
  <div class="card"><h4>Reward & n-step target</h4>
   <div class="formula" style="font-size:14.5px">r<sub>train</sub>(t) = −0,01 × [queue(t<sub>end</sub>) + pending(t<sub>end</sub>)]
R<sub>3</sub> = r<sub>t</sub> + γ r<sub>t+1</sub> + γ² r<sub>t+2</sub>
y  = R<sub>3</sub> + (1−done)·γ³·Q<sub>target</sub>(o<sub>t+3</sub>, a*)</div>
   <div class="xsmall" style="margin-top:6px">γ = 0,99 <b>mỗi decision 10 s</b>. Reward lấy mẫu cuối bước; metric chính tích phân mỗi giây — cùng hướng, không giống hệt.</div></div>
  <div class="row" style="gap:10px;margin-top:12px;text-align:center">
   <div class="card" style="flex:1;padding:10px"><div class="mid">360</div><div class="xsmall">decisions / episode</div></div>
   <div class="card" style="flex:1;padding:10px"><div class="mid">10.800</div><div class="xsmall">decisions / seed</div></div>
   <div class="card" style="flex:1;padding:10px"><div class="mid">120</div><div class="xsmall">lượt test chính = 75 + 45</div></div>
  </div>
  <div class="card" style="margin-top:12px"><h4>Siêu tham số chính</h4>
   <div class="small">lr 0,0003 · Adam · Huber δ=1 · grad clip 10 · replay 50.000 · batch 64 · bắt đầu học khi ≥ 256 mẫu · target sync mỗi 200 updates · ε: 1,0 → 0,05 trong 5.000 decisions (~episode 14)</div></div>
 </div>
 <div style="flex:1">
  <div class="card"><h4>Quy trình cho mỗi learning seed 11–15</h4>
   <div class="vflow small">
    <div class="box">Khởi tạo online → copy target → replay buffer</div><div class="down">↓</div>
    <div class="box">30 episode × 3.600 s trên <b>train AM</b> (demand11/sim11)</div><div class="down">↓</div>
    <div class="box">Mỗi 10 s: ε-greedy → thực thi → transition n-step → replay → 1 update</div><div class="down">↓</div>
    <div class="box" style="background:{C["paleTeal"]}">Mỗi 5 episode: greedy trên <b>validation AM</b> (demand31/sim31) → lưu best</div><div class="down">↓</div>
    <div class="box" style="background:{C["navy"]};color:#fff">Đánh giá best checkpoint trên 15 test case, không cập nhật trọng số</div>
   </div></div>
  <div class="callout gold" style="margin-top:12px;font-size:14.5px">Train chỉ trên <b>AM</b>, test cả normal/AM/PM. 5 policy × 15 = 75 lượt learned; 3 baseline × 15 = 45 lượt.</div>
 </div>
</div>''', secs=75, source="scripts/train_danang_sumo.py · src/traffic_rl/train/trainer.py · configs/danang_pilot.yaml", notes=N(
    "Reward là âm của queue cộng pending tại cuối bước 10 giây, nhân 0,01. Target dùng 3-step return: cộng ba reward có chiết khấu rồi bootstrap bằng target network theo kiểu Double. "
    "Mỗi learning seed từ 11 đến 15 train 30 episode một giờ trên cùng case AM. Mỗi episode có 360 quyết định, tổng 10.800 quyết định mỗi seed. Epsilon giảm từ 1 xuống 0,05 trong 5.000 quyết định, tức khoảng episode 14. "
    "Cứ 5 episode, model chạy greedy trên validation AM; checkpoint có mean queue thấp nhất được giữ. Sau đó checkpoint này được đánh giá trên 15 test case. Tổng cộng 120 lượt chính: 75 lượt learned và 45 lượt baseline.",
    ["30 ep × 5 seeds · validation mỗi 5 ep", "Train chỉ AM · test 3 regime", "120 lượt = 75 learned + 45 baseline"],
    ["Không nói mỗi seed train trên dữ liệu khác nhau — train/val chung."],
    [("30 episode đã hội tụ chưa?", "Đó là budget thực nghiệm; validation chọn checkpoint tốt trong budget, chưa chứng minh hội tụ tối ưu.")]))

# 14 — Metric & baselines -------------------------------------------------------
slide("SUMO", "Đo cái gì và so với ai: queue integral + pending, bốn loại baseline", f'''
<div class="row" style="gap:24px">
 <div style="flex:1">
  <div class="card"><h4>Metric chính · queue integral</h4>
   <div class="formula">I = Σ<sub>t</sub> [Q<sub>network</sub>(t) + P<sub>due</sub>(t)] × Δt   <span class="m">veh-s</span>
I<sub>veh-h</sub> = I<sub>veh-s</sub> / 3600</div>
   <div class="row" style="gap:10px;margin-top:10px;align-items:center">
    <div class="card tealfill" style="padding:8px 12px;text-align:center"><div class="mid">10 xe × 60 s</div></div><div style="font-size:22px;color:{C["teal"]};font-weight:800">=</div>
    <div class="card tealfill" style="padding:8px 12px;text-align:center"><div class="mid">600 veh-s</div><div class="xsmall">= 1/6 veh-h</div></div></div>
   <div class="xsmall muted" style="margin-top:6px">Chỉ nhìn queue giây cuối sẽ bỏ mất chi phí trước đó. Queue integral ≠ toàn bộ travel delay.</div></div>
  <div class="card coralfill" style="margin-top:14px"><h4>Vì sao cộng pending?</h4>
   <div class="formula" style="font-size:14.5px">scheduled = due + unreleased
pending   = due − inserted</div>
   <div class="small" style="margin-top:6px">Controller làm nghẽn cửa vào sẽ giữ xe ngoài mạng và trông “tốt” nếu chỉ đếm xe đã vào. Chỉ tính xe <b>đã đến giờ nhưng bị chặn</b>, không tính xe tương lai.</div></div>
 </div>
 <div style="flex:1">
  {table(["Controller", "Cách quyết định", "Train?"], [
      ["<b>Published fixed</b> (SUMO)", "Chạy lịch công bố 103 s", "Không"],
      ["<b>Tuned fixed</b> (CityFlow)", "Lịch lặp, green chọn trong {20…60} trên validation → 25 s", "Search"],
      ["<b>Max-Pressure</b>", "Chọn phase có Σ incoming − Σ outgoing waiting lớn nhất", "Không"],
      ["<b>Hysteretic MP</b>", "Pressure + điều kiện giữ phase / ngưỡng đổi", "Không"],
      ["<b>Learned</b>", "Dự đoán discounted return bằng model", "Có"],
  ], cls="t compact")}
  <div class="card" style="margin-top:12px"><h4>Metric bổ sung — đọc cùng nhau</h4>
   <div><span class="pill">completion</span><span class="pill">insertion</span><span class="pill">travel time</span><span class="pill gold">spillback proxy</span><span class="pill slate">phase switches</span><span class="pill coral">collision / emergency</span><span class="pill navy">anchor violations</span></div>
   <div class="xsmall muted" style="margin-top:8px">Travel time chỉ tính chuyến hoàn thành → có survivor bias; phải đọc cùng completion.</div></div>
 </div>
</div>''', secs=90, source="src/traffic_rl/sim/multi_agent_env.py · src/traffic_rl/eval/network_metrics.py · src/traffic_rl/agents/max_pressure.py", notes=N(
    "Metric chính là queue integral: cộng mỗi giây số xe đang chờ trong mạng và số xe đã đến giờ nhưng chưa vào được mạng. Ví dụ 10 xe chờ 60 giây là 600 xe-giây, tức một phần sáu xe-giờ. "
    "Vì sao cộng pending? Nếu một controller làm nghẽn cửa vào, xe không vào được simulator; chỉ đếm xe trong mạng sẽ khiến controller đó trông tốt. Nhưng chỉ tính xe đã đến giờ, không tính xe tương lai — đây là lỗi từng có trong lịch sử và đã được sửa. "
    "Baseline gồm lịch cố định — published ở SUMO, tuned trên validation ở CityFlow — Max-Pressure và hysteretic Max-Pressure. Metric phụ như completion, insertion, travel time, spillback phải đọc cùng nhau để tránh metric gaming.",
    ["10 xe × 60 s = 600 veh-s", "pending = due − inserted", "Baseline: fixed · MP · hysteretic MP"],
    ["Không gọi queue integral là “tổng delay”."]))

# 15 — Why residual --------------------------------------------------------------
slide("CityFlow", "Trên mạng 53 nút: chỉnh lịch đèn thay vì chọn phase tự do", f'''
<div class="row" style="gap:24px">
 <div class="card" style="flex:1"><h4 class="coral" style="color:{C["coral"]}">Chọn phase tự do ở mọi nút</h4>
  <ul class="clean coralb small"><li>Không gian hành vi rất lớn: 53 nút × mọi tick</li><li>Có thể phá lịch phục vụ ổn định</li><li>Khó kiểm tra, khó giải thích hành vi</li><li>Các phiên bản phase-based (V2/V3A) không đạt gate</li></ul>
 </div>
 <div class="card tealfill" style="flex:1.2"><h4>Schedule-residual</h4>
  <div class="small">Đặt một <b>lịch tham chiếu</b> trước, cho model chọn <b>chỉnh sửa nhỏ</b>, dễ kiểm tra và giải thích.</div>
  <div class="row" style="gap:8px;margin-top:12px">
   <div class="card" style="flex:1;padding:8px 10px"><b class="navyc">Schedule</b><div class="xsmall">có lịch fixed tham chiếu (25 s)</div></div>
   <div class="card" style="flex:1;padding:8px 10px"><b class="navyc">Residual</b><div class="xsmall">action = dịch 1 boundary ±10 s</div></div>
   <div class="card" style="flex:1;padding:8px 10px"><b class="navyc">Anchored</b><div class="xsmall">cuối block về đúng signal state tham chiếu</div></div>
   <div class="card" style="flex:1;padding:8px 10px"><b class="navyc">Double DQN</b><div class="xsmall">online chọn, target đánh giá macro</div></div>
  </div>
 </div>
</div>
<div class="row" style="gap:16px;margin-top:18px">
 <div class="callout gold" style="flex:1"><b>Đánh đổi:</b> không gian policy bị giới hạn. Nếu một lịch tốt hơn đòi hỏi điều chỉnh lớn, residual không thể thực hiện được.</div>
 <div class="callout teal" style="flex:1"><b>Normal</b> chạy fixed từ đầu (fallback theo thiết kế). <b>AM & PM</b> dùng residual greedy. Model được cho nhãn giờ khai báo, không tự phân loại giờ cao điểm.</div>
</div>
<div class="card" style="margin-top:16px;padding:12px 18px"><div class="small"><b>Macro 0 luôn có sẵn</b> = giữ nguyên lịch tham chiếu. Q bằng nhau → baseline thắng. Feature/score không hữu hạn → fallback. Case ID, seed, filename, future flow bị loại khỏi features.</div></div>
''', secs=75, source="docs/research/haichau-v3b-residual-protocol.md · src/traffic_rl/agents/schedule_residual.py", notes=N(
    "Trên mạng, cho policy tự chọn phase liên tục ở 53 nút tạo không gian hành vi rất lớn và có thể phá lịch phục vụ ổn định; các phiên bản phase-based trước đó đều không đạt gate. "
    "Vì vậy em chuyển sang residual: có một lịch tham chiếu, model chỉ được chọn chỉnh sửa nhỏ. Tên model đọc từng chữ: Schedule là có lịch fixed; Residual là action là chỉnh sửa nhỏ; Anchored là cuối block phải về đúng trạng thái tín hiệu tham chiếu; Double DQN là cách học. "
    "Đổi lại, policy bị giới hạn. Macro 0 — giữ nguyên lịch — luôn có sẵn, nên trường hợp xấu nhất model có thể quay về baseline. Ở normal, controller chạy fixed theo thiết kế.",
    ["Schedule · Residual · Anchored · Double", "Macro 0 = giữ lịch, luôn hợp lệ", "Đánh đổi: an toàn hành vi ↔ độ linh hoạt"]))

# 16 — Macro, shadow, anchor ----------------------------------------------------
steps = ["Đầu block 300 s: lấy observation từng nút", "Dựng lịch tham chiếu (min green, transition)", "Macro 0 = giữ nguyên lịch",
         "Ứng viên: dịch <b>một</b> boundary sớm/muộn 10 s", "ShadowSignal thử từng ứng viên → loại cái không hợp lệ", "MLP chấm điểm ứng viên hợp lệ → chọn 1/nút",
         "Thực thi 30 tick × 10 s", "Cuối block: kiểm tra anchor, lấy reward"]
st = "".join(f'<div style="display:flex;gap:8px;align-items:flex-start;margin:3px 0"><span class="num-badge teal" style="width:24px;height:24px;font-size:12px">{i+1}</span><div class="xsmall" style="padding-top:3px">{s}</div></div>' for i, s in enumerate(steps))
slide("CityFlow", "Một macro: dịch một ranh giới 10 giây, rồi quay về anchor", f'''
<div class="card" style="padding:10px 12px">{macro_timeline()}</div>
<div class="row" style="gap:18px;margin-top:14px">
 <div class="card" style="flex:1.15;padding:12px 16px"><h4>8 bước của một block</h4><div style="columns:2;column-gap:18px">{st}</div></div>
 <div style="flex:1">
  <div class="card navy" style="padding:12px 16px"><h4>Anchor không reset xe</h4><div class="small" style="color:#E7EEF4">Anchor = phase hiện tại + transition đang chờ + các timer. Chỉ <b>trạng thái bộ điều khiển</b> buộc khớp tham chiếu; queue và vị trí xe vẫn mang sang block sau.</div></div>
  <div class="row" style="gap:10px;margin-top:10px">
   <div class="card" style="flex:1;padding:8px 12px"><div class="mid">59</div><div class="xsmall">MAX_MACROS = 1 + 2×(30−1) · slot tối đa, có mask</div></div>
   <div class="card" style="flex:1;padding:8px 12px"><div class="mid">0</div><div class="xsmall">illegal request / anchor mismatch được chấp nhận — runtime báo lỗi</div></div>
  </div>
 </div>
</div>''', secs=105, source="src/traffic_rl/sim/schedule_residual.py (ShadowSignal, macro compiler) · ví dụ trên là minh họa ý tưởng", notes=N(
    "Đây là một block 300 giây. Giả sử lịch tham chiếu có một ranh giới chuyển từ phase A sang B ở giây 100. Model được thử hai ứng viên: chuyển sớm hơn 10 giây, ở giây 90, hoặc muộn hơn 10 giây, ở giây 110. Cùng với macro 0 là giữ nguyên. "
    "Mỗi ứng viên được chạy qua ShadowSignal — mô phỏng logic đèn chứ không mô phỏng xe — để kiểm tra minimum green, transition, và quan trọng nhất là cuối block tín hiệu phải về đúng trạng thái tham chiếu, gồm cả timer. Ứng viên không đạt bị loại khỏi action mask. "
    "Sau đó MLP chấm điểm các ứng viên còn lại, mỗi nút chọn một, thực thi qua 30 tick 10 giây. "
    "Câu then chốt: anchor không reset xe. Hai lịch có thể phục vụ xe ở thời điểm khác nhau trong block, nên hàng chờ khác nhau, dù cuối block đèn về cùng trạng thái. Đó là lý do residual vẫn có tác động.",
    ["±10 s ở một boundary / block", "ShadowSignal kiểm tra hợp lệ + anchor", "Anchor khớp đèn, KHÔNG reset xe"],
    ["Ví dụ giây 90/100/110 là minh họa, không phải macro lấy từ artifact."],
    [("Quay về anchor thì sao vẫn giảm queue?", "Thời điểm phục vụ trong block thay đổi hàng xe; traffic state không bị reset, chỉ controller clock khớp lại.")]))

# 17 — 27 features & shared MLP ---------------------------------------------------
vec27 = '<div class="vec">' + "".join(f'<div class="cell" style="background:{C["teal"]};height:30px"></div>' for _ in range(12)) + \
    '<div style="width:6px"></div>' + "".join(f'<div class="cell" style="background:#3E6E9A;height:30px"></div>' for _ in range(12)) + \
    '<div style="width:6px"></div>' + "".join(f'<div class="cell" style="background:{C["coral"]};height:30px"></div>' for _ in range(3)) + "</div>"
feat12 = ["incoming queue mean", "incoming queue max", "incoming running mean", "outgoing queue mean", "outgoing capacity (40 − count)",
          "pressure (in − out, mean)", "is current phase", "elapsed green (s/20)", "upstream queue mean", "downstream queue mean",
          "time since service (s/20)", "movement count"]
fg = "".join(f'<div class="xsmall" style="padding:2px 0"><b class="teal">{i+1}.</b> {f}</div>' for i, f in enumerate(feat12))
slide("CityFlow", "27 features cho mỗi macro, một MLP dùng chung cho cả 53 nút", f'''
<div class="card" style="padding:12px 16px"><h4>Vector của một macro ứng viên = 12 + 12 + 3</h4>{vec27}
 <div style="display:flex;margin-top:6px;font-size:14px;font-weight:700"><div style="flex:12;color:{C["teal"]}">12 features của source phase</div><div style="flex:12;color:#3E6E9A">12 features của target phase</div><div style="flex:3;color:{C["coral"]};text-align:right">boundary · shift · is_baseline</div></div>
</div>
<div class="row" style="gap:18px;margin-top:14px">
 <div class="card" style="flex:1;padding:12px 16px"><h4>12 features của một phase (scale /20, capacity /40)</h4><div style="columns:2;column-gap:14px">{fg}</div>
  <div class="xsmall muted" style="margin-top:6px">boundary = tick/30 · shift = ±1 · macro 0: trung bình phase rows, descriptor [0,0,1].</div>
  <div class="callout teal" style="margin-top:12px;font-size:14.5px"><b>Vì sao scalar head?</b> Số macro hợp lệ khác nhau theo nút và block. Chấm <b>từng ứng viên</b> bằng cùng một hàm rồi dùng mask giúp xử lý mọi kích thước tập action.</div></div>
 <div class="card" style="flex:1;padding:10px 14px"><h4>PhaseScoringDDQN · scalar Q / macro</h4>{mlp_svg("27", ["1 Q"], w=520, h=190)}
  <div class="formula" style="font-size:13px">(27×64+64)+(64×64+64)+(64×1+1) = <span class="g">6.017</span> tham số</div>
  <div class="xsmall" style="margin-top:6px">Cùng MLP chấm mọi macro ở mọi nút → mask → argmax. <b>Không</b> dueling, <b>không</b> GNN, <b>không</b> attention — neighbor info là scalar features.</div></div>
</div>''', secs=75, source="src/traffic_rl/sim/phase_encoder.py · src/traffic_rl/agents/phase_ddqn.py · src/traffic_rl/agents/schedule_residual.py", notes=N(
    "Mỗi chỉnh sửa liên quan đến hai phase: phase trước ranh giới là source, phase sau là target. Mỗi phase mô tả bằng 12 features: hàng chờ vào trung bình và lớn nhất, xe đang chạy, hàng chờ ra, sức chứa còn lại, pressure, phase có đang xanh không, thời gian xanh đã qua, hàng chờ upstream và downstream, thời gian từ lần phục vụ và số movement. "
    "Thêm ba số mô tả vị trí boundary trong block, hướng dịch sớm hay muộn và có phải macro 0 không. Tổng 12 + 12 + 3 = 27. "
    "Một MLP 27 → 64 → 64 → 1, tổng 6.017 tham số, chấm điểm từng ứng viên. Cùng bộ trọng số dùng cho cả 53 nút, nên số nút tăng không làm tăng số trọng số. "
    "Thông tin lân cận chỉ là features tổng hợp; đây không phải GNN hay learned communication.",
    ["27 = 12 source + 12 target + 3 descriptor", "27→64→64→1 · 6.017 tham số", "Shared weights ≠ GNN"],
    ["Không gọi là “multi-agent communication” hay “graph neural network”."],
    [("53 agent có giao tiếp không?", "Có summary queue upstream/downstream trong observation, chung trọng số và global reward; chưa phải learned communication.")]))

# 18 — Reward & training residual ------------------------------------------------
slide("CityFlow", "Huấn luyện residual: reward toàn mạng, 12 episode, 6 case cao điểm", f'''
<div class="row" style="gap:22px">
 <div style="flex:1.05">
  <div class="card"><h4>Reward của một macro (toàn mạng)</h4>
   <div class="formula" style="font-size:14.5px">r<sub>raw</sub>    = −[I(t+300) − I(t)]     <span class="m">veh-s, queue + pending</span>
r<sub>critic</sub> = r<sub>raw</sub> / 100.000</div>
   <div class="xsmall" style="margin-top:6px">Ví dụ: trung bình 500 xe × 300 s = 150.000 veh-s → r<sub>critic</sub> = −1,5. Cùng reward gán cho 53 transitions. <b>Không</b> trừ cost của baseline.</div></div>
  <div class="card" style="margin-top:12px"><h4>Target theo thời lượng (SMDP)</h4>
   <div class="formula" style="font-size:14px">y = r<sub>critic</sub> + (1−done)·γ<sup>Δt/300</sup>·Q<sub>target</sub>(o', a*)</div>
   <div class="xsmall" style="margin-top:6px">γ = 0,99 <b>mỗi 300 s</b> — khác γ = 0,99 mỗi 10 s của SUMO.</div></div>
  <div class="card goldfill" style="margin-top:12px"><div class="small"><b>Khởi tạo:</b> output head W3, b3 = 0 → mọi Q ban đầu bằng 0 → greedy chọn macro 0. <b>ε = 0,15 cố định</b> tạo cơ hội thử macro khác. Không có imitation loss.</div></div>
 </div>
 <div style="flex:1">
  {table(["Đơn vị (mỗi learning seed)", "Giá trị"], [
      ["Episode", "12 × 3.600 s"],
      ["Block / episode", "12"],
      ["Transitions / block", "53"],
      ["Transitions toàn run", "<b>7.632</b> (AM 3.816 · PM 3.816)"],
      ["Optimizer updates", "12 × 12 × 8 = <b>1.152</b>"],
      ["Batch · replay · bắt đầu", "128 · 20.000 · ≥ 53"],
      ["Target copy", "mỗi 64 updates (= 8 block)"],
      ["Validation · checkpoint", "mỗi 4 episode → ep 4 / 8 / 12"],
  ], cls="t compact", align=["", ""])}
  <div class="callout" style="margin-top:12px;font-size:14.5px">9 train case nhưng chỉ dùng <b>6 case peak</b> (3 AM + 3 PM), mỗi case 2 lần. 7.632 transitions <b>tương quan mạnh</b> — không phải 7.632 thí nghiệm độc lập.</div>
 </div>
</div>''', secs=75, source="src/traffic_rl/train/schedule_residual_trainer.py · docs/research/evidence-snapshot-2026-09-23/seed14-resolved-config.json", notes=N(
    "Reward của một macro là âm phần tăng của queue integral toàn mạng trong 300 giây, gồm cả pending; chia 100.000 để đưa về thang số phù hợp. Ví dụ trung bình 500 xe chờ trong 300 giây là 150.000 xe-giây, reward critic −1,5. "
    "Reward này là toàn mạng, gán giống nhau cho 53 transitions, và không trừ chi phí của baseline — chữ residual chỉ nói về dạng action. "
    "Target viết theo thời lượng macro, gamma 0,99 cho mỗi 300 giây. Output head khởi tạo bằng 0 nên ban đầu model chọn macro 0, epsilon 0,15 để khám phá. "
    "Mỗi seed train 12 episode trên 6 case cao điểm, 7.632 transitions và 1.152 lần cập nhật. Cứ 4 episode lưu checkpoint và chạy validation. Step-4 nghĩa là sau 4 episode.",
    ["Reward = −Δ(queue+pending) toàn mạng / 100.000", "12 ep · 7.632 transitions · 1.152 updates", "step-4 = episode 4"],
    ["Không nói “8 updates × 53 nút” — 8 updates cho cả block toàn mạng."],
    [("Global reward có vấn đề gì?", "Phù hợp mục tiêu hợp tác nhưng khó credit assignment; có thể nghiên cứu local/difference reward.")]))

# 19 — Selector ----------------------------------------------------------------
gates = ["Normal khớp fixed từng case, không divergence phase/timer", "Queue regret trung bình mỗi peak regime ≤ 0", "Mean peak queue regret ≤ −1%",
         "Completion & insertion loss mỗi case ≤ 2 điểm %", "Có learned macro ở AM và PM, ≥ 2 nút khác nhau", "0 illegal request · 0 anchor violation · forced macro 0 = fixed25",
         "Checkpoint phản ứng khi traffic features thay đổi"]
gl = "".join(f'<li>{g}</li>' for g in gates)
seedst = [("12", "Selected", "ep 8", True), ("13", "Rejected", "ep 12 · chẩn đoán", False), ("14", "Selected", "ep 4", True), ("15", "Selected", "ep 8", True), ("16", "Rejected", "ep 4 · chẩn đoán", False)]
sh = "".join(f'''<div class="card" style="flex:1;padding:10px;text-align:center;border-top:5px solid {C["teal"] if ok else C["coral"]}">
 <div style="font-size:15px;font-weight:700;color:{C["muted"]}">seed</div><div class="mid">{s}</div>
 <div style="font-weight:800;color:{C["teal"] if ok else C["coral"]};font-size:15px">{"✓ " if ok else "✗ "}{st}</div><div class="xsmall muted">{ep}</div></div>''' for s, st, ep, ok in seedst)
slide("CityFlow", "Train xong chưa chắc được chấp nhận: selector trên validation", f'''
{flow([("", "Train hoàn tất", "có weights & logs"), ("teal", "Selector V1 chấp nhận", "checkpoint eligible cho seed"), ("navy", "Strict release verifier", "đủ bộ bằng chứng release")])}
<div class="row" style="gap:22px;margin-top:16px">
 <div class="card" style="flex:1.1"><h4>Selector V1 kiểm tra (trên validation)</h4><ul class="clean small">{gl}</ul>
  <div class="xsmall muted" style="margin-top:6px">Xếp theo mean peak regret; hòa → checkpoint sớm hơn. Không ai đạt → <b>fail closed</b>, không lấy “ít xấu nhất”.</div></div>
 <div style="flex:1">
  <div class="row" style="gap:8px">{sh}</div>
  <div class="callout" style="margin-top:14px;font-size:15px">Seed 13 và 16 bị từ chối. Kết quả test dương sau này <b>không đảo ngược</b> quyết định validation. Gate dùng ngưỡng thực nghiệm, chưa phải kiểm định non-inferiority.</div>
  <div class="callout navy" style="margin-top:10px;font-size:15px">Strict verifier: <b>complete = false</b>, còn 14 release gates chưa đạt (rà soát 23/09).</div>
 </div>
</div>''', secs=60, source="configs/haichau_residual_final_selection_v1.yaml · docs/research/evidence-snapshot-2026-09-23/seed*-selection.json", notes=N(
    "Em phân biệt ba trạng thái: train xong, selector chấp nhận, và strict release. Selector V1 chạy trên validation và kiểm tra: normal phải khớp fixed chính xác; regret ở mỗi peak regime không dương và trung bình giảm ít nhất 1%; completion và insertion không giảm quá 2 điểm phần trăm; phải có macro học được ở cả AM và PM; và không vi phạm execution contract. "
    "Nếu không checkpoint nào đạt thì fail closed. Kết quả: seed 12, 14, 15 được chọn; seed 13 và 16 bị từ chối. Em vẫn báo checkpoint của hai seed này trong phân tích chẩn đoán, nhưng không đảo ngược quyết định. "
    "Strict release verifier hiện vẫn chưa hoàn tất, còn 14 gates — em nói thẳng điều này.",
    ["3 trạng thái: trained → selected → released", "Seeds 12/14/15 selected · 13/16 rejected", "Fail closed · strict release chưa complete"]))

# 20 — SUMO results ------------------------------------------------------------
sumo_series = [("Published fixed", C["slate"]), ("Dueling DDQN (5 seeds)", C["teal"]), ("Max-Pressure", "#E89A86"), ("Hysteretic MP", "#E3C06F")]
sumo_vals = [[9.86, 79.20, 152.67], [41.50, 78.41, 99.97], [140.72, 352.43, 269.02], [126.85, 281.52, 241.40]]
slide("Kết quả", "SUMO: PM giảm 34,5%, AM gần bằng fixed, Normal xấu hơn rõ", f'''
<div class="row" style="gap:22px">
 <div style="flex:1.12">
  <div class="card" style="padding:12px 14px">{legend(sumo_series)}{grouped_bars(["Normal", "AM peak", "PM peak"], sumo_series, sumo_vals, 400, w=660, h=400, unit="queue + pending, veh-h (mean)")}</div>
 </div>
 <div style="flex:1">
  {table(["Regime", "Fixed", "DDQN", "Change", "CI 95% (L−F)"], [
      ["Normal", "9,86", "41,50", '<b class="coral">+320,7%</b>', "[7,60; 56,14]"],
      ["AM", "79,20", "78,41", "−1,0%", "[−9,47; 8,49]"],
      ["PM", "152,67", "99,97", '<b class="teal">−34,5%</b>', "[−69,55; −35,34]"],
  ], cls="t compact", align=["", "r", "r", "r nw", "c nw"], hl=[2], hlc=[0])}
  <div class="xsmall muted" style="margin:6px 0 10px">Đơn vị veh-h. CI: paired bootstrap trên 5 seed effects, 20.000 resamples.</div>
  <div class="card" style="padding:10px 14px"><h4>Cách đọc</h4><ul class="clean small">
   <li><b>PM</b>: giảm rõ, CI không chứa 0</li><li><b>AM</b>: trung bình ≈ fixed, CI chứa 0</li><li><b>Normal</b>: xấu hơn đáng kể — không hỗ trợ áp RL cho mọi regime</li>
   <li>Completion DDQN: 93,5 / 91,8 / 89,7% vs fixed 98,1 / 89,6 / 82,8%</li></ul></div>
 </div>
</div>''', secs=120, kind="results", source="SUMO · dueling_n3 · 5 learning seeds × 15 test cases · queue integral + pending (veh-h) · results/danang_protocol_v1/summary/final-summary.csv", notes=N(
    "Đây là kết quả SUMO trên 15 test case, trung bình năm learning seed. Ở PM, lịch cố định tích lũy 152,67 xe-giờ, model còn 99,97 — giảm 34,5%, khoảng tin cậy của chênh lệch hoàn toàn âm. "
    "Ở AM, là regime model được train, trung bình gần như bằng fixed và khoảng tin cậy chứa 0. Ở normal, model xấu hơn rõ: 41,5 so với 9,86, tăng 320,7%. "
    "Hai baseline pressure đều kém hơn fixed ở cả ba regime. Kết luận: lợi ích phụ thuộc regime; kết quả không ủng hộ áp RL vô điều kiện cho mọi thời điểm. "
    "Khoảng tin cậy ở đây là bootstrap trên năm hiệu ứng của learning seed, không phải trên 75 ô.",
    ["PM −34,5% · AM −1,0% (CI chứa 0) · Normal +320,7%", "CI = bootstrap 5 seed effects", "MP & hysteretic MP kém fixed ở SUMO"],
    ["Không chỉ báo PM; luôn nói cả normal xấu hơn."],
    [("Vì sao normal xấu?", "Policy chỉ train trên AM; distribution shift / action timing là giả thuyết, chưa xác lập bằng ablation.")]))

# 21 — SUMO interpretation --------------------------------------------------
slide("Kết quả", "Đọc kết quả SUMO: giả thuyết, ablation và an toàn mô phỏng", f'''
<div class="row" style="gap:22px">
 <div style="flex:1.05">
  <img class="fig" src="{img("curves")}" style="width:100%;height:320px;object-fit:contain">
  <div class="cap">Validation mean queue theo episode cho 5 learning seeds. Checkpoint tốt nhất có thể xuất hiện trước episode cuối; seed 13 dao động mạnh.</div>
 </div>
 <div style="flex:1">
  <div class="card" style="padding:10px 14px;margin-bottom:10px"><h4>Normal xấu hơn — giả thuyết</h4><div class="small">Train chỉ trên AM → distribution shift, overfitting, action timing. <b>Chưa</b> xác lập nguyên nhân bằng ablation.</div></div>
  <div class="card" style="padding:10px 14px;margin-bottom:10px"><h4>Max-Pressure kém ở nút này</h4><div class="small">Chỉ 4 movement được quan sát; mỗi lần đổi mất 7 s clearance so với nhịp 10 s. Không bác bỏ lý thuyết MP.</div></div>
  <div class="card" style="padding:10px 14px;margin-bottom:10px"><h4>Ablation seed 11</h4><div class="small">Validation best: dqn_base ≈ 81,43 · dueling_n3 ≈ 71,71. Thay <b>đồng thời</b> dueling và n-step, 1 seed → chưa tách đóng góp.</div></div>
  <div class="card tealfill" style="padding:10px 14px"><h4>Sự kiện an toàn trong simulator</h4><div class="small">120 lượt chính: <b>0 collision, 0 emergency</b>. Sensitivity 120 lượt: 0 collision, 4 emergency. Không phải chứng nhận an toàn ngoài đời.</div></div>
 </div>
</div>''', secs=60, kind="results", source="results/danang_protocol_v1/summary/validation-learning-curves.png · paper/thesis_danang.tex §Results", notes=N(
    "Đường cong validation cho thấy checkpoint tốt nhất không nhất thiết ở episode cuối, và seed 13 dao động mạnh — đó là lý do phải chọn checkpoint bằng validation. "
    "Normal xấu hơn có thể do policy chỉ được train ở AM, nhưng đây là giả thuyết chưa được ablation xác lập. Max-Pressure kém vì chỉ bốn movement được quan sát và mỗi lần đổi mất 7 giây clearance. "
    "Ablation seed 11 cho thấy dueling n3 tốt hơn base trên validation, nhưng thay đồng thời hai thành phần và chỉ một seed, nên em không tách được đóng góp. "
    "Về an toàn trong simulator: 120 lượt chính không có collision hay emergency.",
    ["Best checkpoint ≠ episode cuối", "MP kém: quan sát một phần + 7 s clearance", "0 collision / 0 emergency trong 120 lượt"]))

# 22 — CityFlow matrix -----------------------------------------------------------
cf_rows = [("Tuned fixed", 8339.43, C["slate"], "baseline · 0%"), ("Max-Pressure", 6347.00, C["coral"], "−23,89% so với fixed · tốt nhất"),
           ("Hysteretic MP", 6739.13, "#E3A94F", "−19,19% so với fixed"), ("Residual DDQN s14", 7829.25, C["teal"], "−6,12% so với fixed")]
slide("Kết quả", "CityFlow: Max-Pressure tốt nhất; residual giảm 6,12% so với fixed", f'''
<div class="row" style="gap:22px">
 <div style="flex:1.1">
  <div class="card" style="padding:12px 14px"><h4>Tổng queue cost trên 15 case, veh-h</h4>{hbars(cf_rows, 8800, w=640, row_h=66, label_w=190)}</div>
 </div>
 <div style="flex:1">
  {table(["Pooled reduction vs fixed", "Normal", "AM", "PM"], [
      ["Max-Pressure", "26,72%", "23,85%", "22,66%"],
      ["Hysteretic MP", "<b>35,60%</b>", "9,95%", "17,37%"],
      ["Residual DDQN s14", "0% <span class='xsmall muted'>(fixed)</span>", "3,48%", "<b>10,39%</b>"],
  ], cls="t compact", align=["", "r", "r", "r"], hl=[2])}
  <div class="card" style="margin-top:12px;padding:10px 14px"><h4>Cách nói</h4><div class="small">“Residual có lợi ích so với fixed nhưng <b>chưa vượt baseline pressure</b> trong ma trận này.”</div></div>
  <div class="callout" style="margin-top:12px;font-size:15px">Đây là <b>một policy</b> (seed 14, checkpoint episode 4). Không gọi 6,12% là trung bình của năm learning seeds. Không so trị số tuyệt đối với SUMO.</div>
 </div>
</div>''', secs=105, kind="results", source="CityFlow · residual seed14/episode4 · 15 matched cases × 3.600 s · queue + pending, veh-h · pooled reduction vs tuned fixed · final15-controller-matrix-summary.json", notes=N(
    "Trên mạng 53 nút, đây là ma trận 15 case của một policy: seed 14, checkpoint episode 4. Tổng queue cost của tuned fixed là 8.339 xe-giờ. Residual giảm còn 7.829, tức 6,12%. "
    "Nhưng Max-Pressure giảm 23,89% và hysteretic Max-Pressure giảm 19,19%. Vậy Max-Pressure là controller tốt nhất theo queue cost trong ma trận này. "
    "Theo regime, residual bằng fixed ở normal do fallback, giảm 3,48% ở AM và 10,39% ở PM. Kết luận đúng: residual có lợi ích so với fixed nhưng chưa vượt baseline pressure. "
    "Đây là kết quả của một policy, không phải trung bình năm seed.",
    ["Fixed 8.339 · MP 6.347 · HMP 6.739 · Residual 7.829", "MP −23,89% > Residual −6,12%", "Một policy seed 14 / ep 4"],
    ["Không nói “RL tốt nhất” ở mạng."],
    [("Vì sao Max-Pressure thắng?", "Có thể do budget học, credit assignment của global reward, và không gian action residual bị giới hạn; chưa có ablation xếp hạng nguyên nhân.")]))

# 23 — Secondary metrics & mean vs pooled ------------------------------------------
slide("Kết quả", "Queue giảm không có nghĩa mọi metric đều tốt hơn", f'''
<div class="row" style="gap:22px">
 <div style="flex:1.1">
  {table(["Metric (trung bình 15 case)", "Fixed", "Residual s14", "Diễn giải"], [
      ["Completion", "66,92%", "67,98%", '<span class="teal">+1,06 điểm %</span>'],
      ["Insertion", "97,15%", "97,97%", '<span class="teal">+0,82 điểm %</span>'],
      ["Completed travel time", "737,81 s", "743,26 s", '<span class="coral">+5,45 s</span>'],
      ["Spillback proxy", "1.432,33 lane-s", "1.497,53 lane-s", '<span class="coral">+65,20 lane-s</span>'],
  ], cls="t", align=["", "r nw", "r nw", "nw"])}
  <div class="callout gold" style="margin-top:14px;font-size:15.5px">Travel time chỉ tính chuyến hoàn thành: khi completion tăng, tập chuyến thay đổi. Không kết luận từ một con số rằng mọi xe đi chậm hơn.</div>
 </div>
 <div class="card" style="flex:1"><h4>Hai cách tính % cho PM seed 14</h4>
  <div class="formula" style="font-size:13.5px">Mean per-case = mean<sub>c</sub> 100·(F<sub>c</sub>−L<sub>c</sub>)/F<sub>c</sub>
Pooled        = 100·(ΣF − ΣL)/ΣF</div>
  <div class="row" style="gap:10px;margin-top:12px;text-align:center">
   <div class="card tealfill" style="flex:1;padding:10px"><div class="big" style="font-size:38px">8,86%</div><div class="xsmall">mean per-case reduction</div></div>
   <div class="card tealfill" style="flex:1;padding:10px"><div class="big" style="font-size:38px">10,39%</div><div class="xsmall">pooled reduction</div></div>
  </div>
  <div class="small" style="margin-top:12px">Ví dụ: fixed 100 / 1.000, learned 90 / 800 → mean 15%, pooled 19,09%. <b>Cả hai đúng</b> cho hai câu hỏi khác nhau: pooled cho case nặng trọng số lớn hơn.</div>
 </div>
</div>''', secs=75, kind="results", source="CityFlow · seed14/ep4 · 15 cases · final15-seed14-secondary-summary.json", notes=N(
    "Metric phụ cho thấy trade-off. Completion tăng khoảng 1 điểm phần trăm và insertion tăng 0,8 điểm, tức là không giảm queue bằng cách chặn xe. Nhưng travel time của chuyến hoàn thành tăng 5,45 giây và spillback proxy tăng 65 lane-giây. "
    "Travel time có survivor bias: khi nhiều chuyến hoàn thành hơn, tập chuyến được tính thay đổi. "
    "Một điểm dễ bị hỏi: vì sao PM có hai con số 8,86% và 10,39%? 8,86% là trung bình phần trăm từng case, mỗi case trọng số bằng nhau; 10,39% là trên tổng, case nặng có trọng số lớn hơn. Cả hai đúng, trả lời hai câu hỏi khác nhau.",
    ["Completion +1,06 · insertion +0,82 điểm %", "Travel time +5,45 s · spillback +65 lane-s", "8,86% mean-case vs 10,39% pooled"]))

# 24 — PM-only gate --------------------------------------------------------------
slide("Kết quả", "Phân tích thăm dò: chỉ dùng residual ở PM, trên năm learning seeds", f'''
<div class="row" style="gap:22px">
 <div style="flex:1.05">
  <div class="card" style="padding:12px 14px"><h4>Pooled reduction trên 15 case (normal → fixed · AM → fixed · PM → residual)</h4>{gate_chart(w=600, h=320)}
   <div class="xsmall muted">Cột đặc = selected · viền đứt = checkpoint chẩn đoán sau khi bị từ chối · <b class="gold">đường vàng đứt = mean 3,48%</b>, dải vàng = 95% CI [2,01; 4,95].</div></div>
 </div>
 <div style="flex:1">
  <div class="row" style="gap:10px;text-align:center">
   <div class="card" style="flex:1;padding:10px"><div class="mid">3,48%</div><div class="xsmall">trung bình 5 seeds</div></div>
   <div class="card" style="flex:1;padding:10px"><div class="mid">1,03–5,62%</div><div class="xsmall">khoảng giữa các seed</div></div>
  </div>
  <div class="row" style="gap:10px;text-align:center;margin-top:10px">
   <div class="card tealfill" style="flex:1;padding:10px"><div class="mid">15 / 25</div><div class="xsmall">ô PM cải thiện</div></div>
   <div class="card coralfill" style="flex:1;padding:10px"><div class="mid">10 / 25</div><div class="xsmall">ô PM xấu hơn fixed</div></div>
  </div>
  <div class="small" style="margin-top:10px">Seed-bootstrap 95% CI <b>[2,01%; 4,95%]</b>, 10.000 resamples. 50 ô normal/AM bằng fixed do thiết kế.</div>
  <div class="callout" style="margin-top:12px;font-size:15px"><b>Post hoc:</b> gate được chọn <b>sau khi xem test</b>, dùng checkpoint chẩn đoán của seed 13/16. CI dương <b>không xóa</b> selection bias → cần test mới độc lập.</div>
 </div>
</div>''', secs=75, kind="results", source="CityFlow · 5 learning seeds × 15 cases · pooled reduction vs fixed · final15-regime-gated-direct-multi-seed-summary.json · exploratory", notes=N(
    "Vì residual có lợi rõ nhất ở PM, em phân tích thêm một gate: normal và AM chạy fixed, chỉ PM dùng residual, với cả năm learning seed. "
    "Trung bình giảm 3,48% trên 15 case, dao động từ 1,03% đến 5,62%, khoảng tin cậy bootstrap theo seed từ 2,01% đến 4,95%. Nhưng trong 25 ô PM, 10 ô vẫn xấu hơn fixed. "
    "Quan trọng nhất: đây là phân tích thăm dò sau khi đã xem test, và dùng cả hai seed đã bị từ chối. CI dương không xóa được selection bias. Muốn thành claim xác nhận phải đóng băng gate và chạy trên test mới.",
    ["Mean 3,48% · CI [2,01; 4,95] · range 1,03–5,62", "10/25 ô PM vẫn xấu hơn", "POST HOC — cần test mới"],
    ["Không gọi đây là kết quả chính hay kết quả đã xác nhận."],
    [("Mean dương nhưng 10/25 xấu hơn thì sao?", "Lợi ích ở case tốt lớn hơn thiệt hại ở case xấu; mean dương không phải bảo đảm từng case. Cần ngưỡng per-case định trước trên test mới.")]))

# 25 — Demo ---------------------------------------------------------------------
demo_steps = [("15 s", "Whole network", "53 controlled signals từ topology OSM; nhu cầu và lịch đèn là mô phỏng."),
              ("20 s", "Reset to guided view", "Cùng case PM demand105/sim205, đồng bộ thời gian; seed 14, checkpoint episode 4."),
              ("20 s", "Frame 1.085 s (18:05)", "Nút 420249521: fixed 14 xe chờ, residual 1 → ít hơn 13 xe tại thời điểm này."),
              ("20 s", "Play + Linked junctions", "Queue và tín hiệu theo thời gian; xem nút lân cận."),
              ("15 s", "Về bảng aggregate", "Frame minh họa hành vi; kết luận dựa trên evaluation đủ giờ, nhiều case.")]
dsh = "".join(f'<div style="display:flex;gap:10px;margin:6px 0"><div class="mono" style="width:48px;flex:none;white-space:nowrap;font-weight:800;color:{C["teal"]};font-size:14px">{t}</div><div class="small"><b class="navyc">{a}</b> — {b}</div></div>' for t, a, b in demo_steps)
slide("Kết luận", "Demo: recorded replay có truy vết, PM demand105", f'''
<div class="row" style="gap:22px">
 <div style="flex:1.1"><img class="fig" src="{img("demo")}" style="width:100%;height:auto">
  <div class="cap">Ảnh chụp demo trình duyệt: fixed (trái) và schedule-residual (phải) cùng thời điểm 18:05 elapsed. Launch: <span class="mono">python3 launch_demo.py --no-browser --port 8766</span></div></div>
 <div style="flex:1">
  <div class="card" style="padding:10px 14px"><h4>Kịch bản ~90 giây</h4>{dsh}</div>
  <div class="callout gold" style="margin-top:10px;font-size:13.8px"><b>18:05</b> = 18 phút 05 giây đã trôi qua, không phải 18 giờ 05. Telemetry chỉ 0–1.200 s. Browser <b>không</b> train hay chạy simulator. “13 xe ít hơn” ≠ “13 xe được giải phóng thêm”.</div>
 </div>
</div>''', secs=120, source="results/haichau_network_v2/demo-visual/manifest.json · docs/defense/demo-runbook.md", notes=N(
    "[Chuyển sang trình duyệt nếu demo đã mở sẵn; nếu không, dùng ảnh này.] "
    "Đây là mạng 53 nút có đèn dựng từ OSM; nhu cầu và lịch đèn là mô phỏng. Em bấm Reset to guided view: hai bên là cùng case PM demand 105, simulator seed 205, đồng bộ thời gian; bên phải là residual seed 14, checkpoint episode 4. "
    "Tại 18 phút 05 giây mô phỏng, ở nút 420249521, fixed có 14 xe chờ còn residual có 1 xe — ít hơn 13 xe tại thời điểm này. Em bấm Play và Linked junctions để xem các nút lân cận. "
    "Cuối cùng em quay lại bảng aggregate: frame này chỉ minh họa hành vi, còn kết luận định lượng dựa trên evaluation đủ một giờ và nhiều case. Đây là recorded replay, trình duyệt không train hay chạy simulator.",
    ["PM demand105/sim205 · seed14 ep4", "Nút 420249521: 14 vs 1 xe tại 18:05", "Recorded replay — quay về aggregate"],
    ["Không nói 18:05 là giờ trong ngày.", "Không suy ra 13 xe được giải phóng thêm."],
    [("Demo có chạy RL live không?", "Không. Đây là replay đã ghi; metric cuối lấy từ evaluation 3.600 s riêng.")]))

# 26 — Evidence ladder -------------------------------------------------------------
can = ["RL giảm hàng chờ ở <b>PM</b> trên bộ test SUMO (−34,5%, CI không chứa 0)", "Lợi ích <b>phụ thuộc regime</b>; normal xấu hơn rõ",
       "Residual 53 nút giảm 6,12% so với tuned fixed <b>cho một policy</b>", "Max-Pressure tốt hơn residual trong ma trận hiện có",
       "Residual tuân thủ execution contract: 0 illegal request, 0 anchor violation", "Có chuỗi truy vết nguồn → cấu hình → checkpoint → kết quả"]
cannot = ["RL tốt hơn fixed ở mọi thời điểm", "Đạt state of the art hoặc vượt baseline mạnh trên mạng", "Gate PM-only 3,48% là kết quả đã xác nhận",
          "Hiệu quả ngoài hiện trường / sẵn sàng triển khai", "Dữ liệu camera đại diện nhiều ngày, nhiều mùa", "Hash khớp hoặc CI dương = an toàn khi deploy"]
slide("Kết luận", "Được phép nói gì — và chưa được nói gì", f'''
<div class="row" style="gap:24px">
 <div class="card tealfill" style="flex:1"><h4>✓ Bằng chứng hiện có hỗ trợ</h4><ul class="clean small">{"".join(f"<li>{x}</li>" for x in can)}</ul></div>
 <div class="card coralfill" style="flex:1"><h4 style="color:{C["coral"]}">✗ Chưa được claim</h4><ul class="clean coralb small">{"".join(f"<li>{x}</li>" for x in cannot)}</ul></div>
</div>
<div class="callout navy" style="margin-top:18px;font-size:17px">Mức độ phù hợp: một nghiên cứu <b>phát triển hệ thống và đánh giá mô phỏng có phân tích thất bại</b> — mô hình, implementation, thí nghiệm, nguồn và giới hạn đều được công khai.</div>
''', secs=90, notes=N(
    "Để Hội đồng dễ đánh giá, em tách rõ hai cột. Bằng chứng hiện có hỗ trợ: RL giảm hàng chờ ở PM trong SUMO; lợi ích phụ thuộc regime; residual giảm 6,12% so với fixed cho một policy; Max-Pressure tốt hơn residual; residual tuân thủ contract; và có chuỗi truy vết. "
    "Chưa được claim: RL tốt hơn ở mọi thời điểm, vượt baseline mạnh, gate PM-only đã xác nhận, hiệu quả ngoài hiện trường, hay dữ liệu đại diện nhiều ngày. "
    "Em xem luận văn là nghiên cứu phát triển hệ thống và đánh giá mô phỏng, có công khai cả kết quả xấu.",
    ["Cột trái = claim được phép", "Cột phải = claim bị cấm", "Định vị: system + simulation evaluation"]))

# 27 — Contributions, limits, next ----------------------------------------------------
slide("Kết luận", "Đóng góp, giới hạn và bước tiếp theo", f'''
<div class="row" style="gap:18px">
 <div class="card" style="flex:1"><h4>Đóng góp</h4><ul class="clean small">
  <li><b>Hai tầng nghiên cứu</b>: một nút có nguồn công bố + mạng 53 nút từ OSM</li>
  <li>Controllers với state/action/reward <b>rõ ràng, có code</b></li>
  <li><b>Residual action truy vết được</b>: dịch 1 boundary, kiểm tra hợp lệ, về anchor</li>
  <li>Đánh giá <b>ghép cặp</b>, tách learning seed, cộng pending, công khai kết quả xấu</li>
  <li>Chuỗi truy vết nguồn → dữ liệu → cấu hình → checkpoint → kết quả → demo</li></ul></div>
 <div class="card" style="flex:1"><h4 style="color:{C["coral"]}">Giới hạn</h4><ul class="clean coralb small">
  <li>Camera: 1 ngày, 4 movement, số hóa xấp xỉ; mạng dùng demand tổng hợp</li>
  <li>Chưa calibration bằng trajectory thực địa; lane model, không sublane</li>
  <li>Normal regression (SUMO); Max-Pressure thắng residual (mạng)</li>
  <li>Test đã dùng để sửa simulator (tau 1,2) và chọn gate post hoc</li>
  <li>Strict release chưa complete; một số raw artifacts ngoài Git</li></ul></div>
 <div class="card" style="flex:1"><h4 style="color:{C["gold"]}">Bước tiếp theo</h4><ul class="clean goldb small">
  <li><b>Đóng băng</b> policy và gate → test độc lập mới</li>
  <li>Hoàn thiện artifact & runtime bindings để tái lập</li>
  <li><b>Ablation</b>: dueling, n-step, neighbor features, global reward, biên residual</li>
  <li>Độ nhạy sai số số hóa và demand</li>
  <li>Dữ liệu nhiều ngày + calibration thực địa trước khi mở rộng claim</li></ul></div>
</div>
<div class="callout teal" style="margin-top:16px;font-size:15.5px">Không nhận là đóng góp: phát minh Double DQN/dueling, state of the art toàn ngành, cải thiện toàn thành phố, sẵn sàng điều khiển đèn ngoài đường.</div>
''', secs=120, notes=N(
    "Đóng góp của luận văn gồm năm điểm: tổ chức hai tầng nghiên cứu; controllers có state, action, reward rõ ràng; residual action có thể truy vết; quy trình đánh giá ghép cặp có cộng pending và công khai kết quả xấu; và chuỗi truy vết từ nguồn đến demo. "
    "Giới hạn: dữ liệu camera chỉ một ngày, bốn movement; mạng dùng nhu cầu tổng hợp; chưa calibration; normal bị xấu hơn ở SUMO và Max-Pressure thắng ở mạng; test đã được dùng để sửa simulator và chọn gate; strict release chưa hoàn tất. "
    "Bước tiếp theo theo thứ tự ưu tiên: đóng băng policy và gate rồi chạy test mới; hoàn thiện artifact; ablation từng thành phần; phân tích độ nhạy; và cuối cùng là dữ liệu nhiều ngày cùng calibration thực địa.",
    ["5 đóng góp — nhấn residual truy vết + đánh giá ghép cặp", "Giới hạn nói trước khi bị hỏi", "Ưu tiên: freeze → test mới → ablation"],
    [], [("Nếu cải thiện tiếp, ưu tiên gì?", "Freeze policy/gate, test độc lập mới với baseline mạnh và nhiều seed; sau đó ablation và calibration.")]))

# 28 — Closing -----------------------------------------------------------------
slide("Kết luận", "", f'''
<div style="position:absolute;left:84px;top:96px;font-size:15px;font-weight:700;letter-spacing:.16em;color:#7FD1C7">KẾT LUẬN</div>
<div style="position:absolute;left:84px;top:140px;width:1080px;font-size:31px;line-height:1.42;font-weight:600;color:#fff">
Học tăng cường <span style="color:#7FD1C7">có thể giảm hàng chờ</span> trong một số chế độ mô phỏng, nhưng lợi ích <span style="color:#F2C66D">không đồng đều</span> và <span style="color:#F2C66D">chưa vượt baseline mạnh</span> ở mạng hiện có.</div>
<div style="position:absolute;left:84px;top:330px;width:1080px;font-size:21px;line-height:1.5;color:#C9D8E4">Đóng góp: hai tầng thí nghiệm, một controller residual có hành vi kiểm tra được, và quy trình truy vết bằng chứng. Bước tiếp theo: đóng băng policy và gate, kiểm tra trên demand độc lập mới, bổ sung calibration và dữ liệu thực địa.</div>
<div style="position:absolute;left:84px;top:520px;font-size:40px;font-weight:800;color:#fff">Em xin cảm ơn Hội đồng.</div>
<div style="position:absolute;left:84px;top:580px;font-size:19px;color:#8FA9BE">Em xin lắng nghe câu hỏi và góp ý.</div>
<div style="position:absolute;left:84px;top:650px;font-size:14px;color:#8FA9BE">{AUTHOR} · FPT University · 2026</div>
''', secs=45, kind="cover", notes=N(
    "Kết quả cho thấy học tăng cường có thể giảm hàng chờ trong một số chế độ mô phỏng, nhưng lợi ích không đồng đều và chưa vượt baseline mạnh ở mạng hiện có. "
    "Luận văn đóng góp hai tầng thí nghiệm, một controller residual có hành vi kiểm tra được, và quy trình truy vết bằng chứng. "
    "Bước tiếp theo là đóng băng policy và gate, kiểm tra trên demand độc lập mới, rồi bổ sung calibration và dữ liệu thực địa trước khi mở rộng claim. Em xin cảm ơn Hội đồng và xin lắng nghe câu hỏi.",
    ["Câu kết đọc gần như thuộc lòng", "Dừng, mỉm cười, chờ câu hỏi", "Mở slide backup khi được hỏi"]))

# ================================================================ BACKUP
B = "Backup"
slide(B, "B1 · Bảng tham số của hai model đã báo cáo", table(["Tham số", "SUMO dueling_n3", "CityFlow residual V3B"], [
    ["Input · hidden · output", "16 · 64, 64 · V:1 + A:3 → 3 Q", "27/macro · 64, 64 · scalar Q/macro"],
    ["n-step · action slots", "3 · 3", "1 macro transition · 59 (mask)"],
    ["Learning rate · Adam β1/β2/ε", "0,0003 · 0,9/0,999/1e−8", "0,0003 · 0,9/0,999/1e−8"],
    ["Huber δ · grad clip (L2)", "1 · 10", "1 · 10"],
    ["Replay · batch · train starts", "50.000 · 64 · 256", "20.000 · 128 · 53"],
    ["Updates · target sync", "1/decision · 200 updates", "8/network macro · 64 updates"],
    ["γ · reward scale", "0,99 / 10 s · ×0,01", "0,99 / 300 s · ÷100.000"],
    ["ε train · decay", "1,0 → 0,05 · 5.000 decisions", "0,15 cố định"],
    ["Tick · macro · shift", "10 s · — · —", "10 s · 300 s · ±10 s một boundary"],
    ["Min green · yellow · max red", "20 s · 7 s · không áp dụng", "20 s · 3 s (theo contract) · 180 s"],
    ["Baseline fixed", "32/28/22 + 3×7 = 103 s", "nominal green 25 s"],
    ["Episodes · eval · seeds", "30 · mỗi 5 · 11–15", "12 · mỗi 4 · 12–16"],
    ["Output head init · warmstart", "SharedDQN init · 0", "W3/b3 = 0 · không imitation"],
], cls="t compact"), secs=0, kind="backup", source="configs/danang_pilot.yaml · seed14-resolved-config.json · seed14-step4-contract.json", notes=N(
    "Dùng khi bị hỏi về tham số. Nhấn: các giá trị là động cơ kỹ thuật, không chứng minh tối ưu toàn cục; ngoài search fixed duration, chưa có hyperparameter search.",
    ["target_sync = 64 updates, không phải giây", "γ khác đơn vị bước", "Chưa có hyperparameter search ngoài fixed duration"]))

slide(B, "B2 · Replay, exploration, loss và optimizer", f'''
{table(["Cơ chế", "Để làm gì?", "Trong dự án"], [
    ["Replay buffer", "Tái sử dụng kinh nghiệm, giảm phụ thuộc chuỗi mẫu liên tiếp", "Ring buffer, lấy mẫu ngẫu nhiên <b>có hoàn lại</b>"],
    ["ε-greedy", "Khám phá thay vì luôn chọn action đang tốt nhất", "Xác suất ε chọn ngẫu nhiên trong action hợp lệ"],
    ["Huber loss", "Bình phương lỗi nhỏ, tuyến tính lỗi lớn", "δ = 1; hạn chế gradient lớn do TD error"],
    ["Gradient clipping", "Chặn chuẩn L2 toàn bộ gradient", "Ngưỡng 10 — không phải chặn trọng số ±10"],
    ["Adam", "Cập nhật theo moment của gradient", "β1 = 0,9 · β2 = 0,999 · ε số học = 1e−8"],
    ["ReLU · He init", "Phi tuyến · scale khởi tạo phù hợp ReLU", "max(0,x) · sqrt(2/fan_in)"],
])}
<div class="row" style="gap:16px;margin-top:14px">
 <div class="formula" style="flex:1">Huber(δ<sub>t</sub>) = 0,5·δ<sub>t</sub>²        nếu |δ<sub>t</sub>| ≤ 1
            |δ<sub>t</sub>| − 0,5      nếu |δ<sub>t</sub>| > 1</div>
 <div class="callout gold" style="flex:1">Adam ε (ổn định phép chia) ≠ ε-greedy (xác suất khám phá). Loss giảm <b>không</b> chứng minh policy tốt → chọn checkpoint bằng validation traffic metric.</div>
</div>''', secs=0, kind="backup", notes=N("Dùng khi bị hỏi về chi tiết optimizer hoặc vì sao loss giảm mà queue không giảm.", ["Có hoàn lại → batch 128 với 53 mẫu vẫn lấy được", "Clip chuẩn gradient, không clip trọng số", "Hai loại epsilon khác nhau"]))

slide(B, "B3 · Mean per-case, pooled và bootstrap: đơn vị độc lập là gì?", f'''
<div class="row" style="gap:22px">
 <div style="flex:1">
  <div class="formula">Regret<sub>case</sub> (%)    = 100·(L<sub>c</sub> − F<sub>c</sub>)/F<sub>c</sub>   <span class="m">âm là tốt</span>
Reduction<sub>case</sub> (%) = 100·(F<sub>c</sub> − L<sub>c</sub>)/F<sub>c</sub>   <span class="m">dương là tốt</span>
Pooled reduction   = 100·(ΣF − ΣL)/ΣF</div>
  <div class="card" style="margin-top:14px"><div class="small">Panel demo PM seed 14: mean per-case <b>change −8,86%</b>, CI <b>[−17,51%; −1,62%]</b> trên 5 demand cases của <b>một policy</b> — không phải CI 5 learning seeds.</div></div>
 </div>
 <div style="flex:1.2">{table(["Phân tích", "Đơn vị lấy mẫu lại", "Resamples", "Phạm vi CI"], [
    ["SUMO learned vs fixed", "5 seed effects (gộp case trong seed)", "20.000", "Biến thiên learning seed"],
    ["PM panel demo s14", "5 matched demand cases", "case bootstrap", "Biến thiên giữa demand case"],
    ["Gate PM-only", "5 pooled effects / seed", "10.000", "Exploratory seed-level"],
 ], cls="t compact")}
 <div class="callout" style="margin-top:12px;font-size:15px">75 ô seed × case <b>không</b> phải 75 policy độc lập. 7.632 transitions không dùng để tính CI. Bootstrap không tạo dữ liệu thực địa mới.</div></div>
</div>''', secs=0, kind="backup", notes=N("Dùng khi bị hỏi về thống kê hoặc hai con số 8,86 và 10,39.", ["Pooled: case nặng trọng số lớn", "Đơn vị độc lập = learning seed", "CI không sửa selection bias"]))

slide(B, "B4 · Tham số phương tiện: SUMO và CityFlow khác nhau", f'''
<div class="row" style="gap:22px">
 <div style="flex:1.3"><h4 class="teal" style="font-size:15px;margin-bottom:6px">SUMO (route XML train AM)</h4>{table(["", "Motorcycle", "Car", "Truck", "Bus"], [
    ["Length / width, m", "2 / 0,8", "5 / 1,8", "8 / 2,5", "12 / 2,5"], ["Accel / decel, m/s²", "3,5 / 5", "2 / 4,5", "1,3 / 4", "1,2 / 4"],
    ["Min gap, m", "0,5", "2,5", "3", "3"], ["Max speed, m/s", "13,89 (~50 km/h)", "11,11 (~40)", "10", "10"], ["Sigma · tau", "0,7 · 1,2 s", "0,5 · —", "0,5 · —", "0,5 · —"],
 ], cls="t compact", align=["", "c", "c", "c", "c"])}</div>
 <div style="flex:1"><h4 class="teal" style="font-size:15px;margin-bottom:6px">CityFlow (haichau_dataset.py)</h4>{table(["", "Motorcycle", "Car"], [
    ["Length / width, m", "2 / 1", "5 / 2"], ["Max accel / decel", "3,5 / 5", "2 / 4,5"], ["Min gap, m", "0,5", "2,5"], ["Max speed, m/s", "13,89", "11,11"], ["Headway time, s", "0,8", "1,5"],
 ], cls="t compact", align=["", "c", "c"])}</div>
</div>
<div class="callout gold" style="margin-top:16px;font-size:15.5px">Launch chính dùng <b>lane-based model</b>. Sublane pilot 300 s ổn nhưng full-hour có collision → không giữ. Tau xe máy 1,0 → 1,2 sau collision ở một held-out AM case; chạy lại toàn bộ để nhất quán, nhưng test đã bị dùng để sửa simulator. Tham số chưa hiệu chỉnh bằng trajectory thực địa.</div>
''', secs=0, kind="backup", notes=N("Dùng khi bị hỏi về mô hình xe máy, sublane, tau.", ["Lane model, không sublane", "tau 1,2 chỉ ghi cho motorcycle", "headway CityFlow 0,8 ≠ tau SUMO 1,2"]))

slide(B, "B5 · Lịch sử thay đổi và bài học", table(["Giai đoạn / vấn đề", "Thay đổi", "Kết luận được phép rút"], [
    ["Dữ liệu legacy gọi “real trips”", "Gắn nhãn synthetic", "Không có nguồn cho “50.500 real trips”"],
    ["Network SUMO rộng có lỗi", "Cô lập nút có dữ liệu, approach ~300 m", "Giảm độ bao phủ không gian của SUMO"],
    ["Sublane pilot", "Bỏ sau collision full-hour", "Mất một phần chân thực chuyển động ngang"],
    ["Pending trên mạng", "Tách due và future unreleased", "Metric đúng khái niệm; cache cũ không dùng"],
    ["Fixed-time execution", "Thống nhất clock, mask, transition", "So sánh dựa trên executed schedule"],
    ["V2 phase-based / V3A rehearsal", "Neighbor features, imitation/rehearsal", "Pilot bị từ chối theo decision log"],
    ["V3B residual", "27 features, macro 300 s, ±10 s", "Family của kết quả residual hiện tại"],
    ["V3C / V3D", "Thử margin & exploration khác", "Chẩn đoán; không nhập tham số vào V3B"],
    ["PM-only gate", "Fixed normal/AM, residual PM", "Exploratory, cần test mới"],
    ["Rà soát 23/09", "Sửa tác giả, locator, CI units", "Sửa diễn giải; không tạo thí nghiệm mới"],
], cls="t compact"), secs=0, kind="backup", source="docs/research/decision-log.md · docs/research/thesis-evidence-ledger.md", notes=N(
    "Cách nói về thất bại: “Thử nghiệm này không đạt gate, nên em thay đổi thiết kế/thu hẹp claim và giữ lại bằng chứng.” Không kể lịch sử như chuỗi cải tiến mà phiên bản nào cũng tốt hơn.",
    ["Thất bại → thu hẹp claim", "V3B là family được báo cáo", "V3C/V3D chỉ chẩn đoán"]))

slide(B, "B6 · Technology stack và bản đồ mã nguồn", f'''
<div class="row" style="gap:22px">
 <div style="flex:1">{table(["Công nghệ", "Vai trò"], [
    ["Python · NumPy", "Pipeline; MLP, backprop, Adam, replay, bootstrap"], ["SUMO + TraCI", "Simulator 1 nút, giao tiếp Python"],
    ["CityFlow (C++ + Python)", "Simulator mạng 53 nút"], ["OSM · osmium · netconvert", "Topology, chuyển định dạng"],
    ["Docker · Colima", "Runtime CityFlow đóng gói (NumPy 1.19.5)"], ["Git · SHA-256", "Phiên bản code, định danh artifact"],
    ["Matplotlib · LaTeX", "Hình kết quả, thesis PDF"], ["HTML/JS/Canvas", "Demo replay trên trình duyệt"],
 ], cls="t compact")}
 <div class="xsmall muted" style="margin-top:6px">PyTorch/SB3 trong requirements lịch sử <b>không</b> dùng cho hai model chính. Không có pipeline GPU.</div></div>
 <div style="flex:1">{table(["Muốn giải thích", "File"], [
    ["Observation / chuyển đèn SUMO", "sim/sumo_single_junction.py"], ["Dueling, Double target, Adam", "agents/dqn.py"],
    ["Training loop SUMO", "train/trainer.py"], ["12 phase features", "sim/phase_encoder.py"],
    ["Scalar MLP dùng chung", "agents/phase_ddqn.py"], ["ShadowSignal, macro, anchor", "sim/schedule_residual.py"],
    ["Train residual", "train/schedule_residual_trainer.py"], ["Queue integral, pending", "sim/multi_agent_env.py"],
    ["Selector mỗi seed", "research/final_residual_selector.py"],
 ], cls="t compact")}<div class="xsmall muted" style="margin-top:6px">Tất cả dưới src/traffic_rl/</div></div>
</div>''', secs=0, kind="backup", notes=N("Dùng khi bị hỏi “code ở đâu?” — mở đúng file.", ["Model viết bằng NumPy", "Docker cho CityFlow", "Biết mở file nào cho mỗi câu hỏi"]))

slide(B, "B7 · Tái lập: những gì có và khoảng trống còn lại", f'''
<div class="row" style="gap:22px">
 <div class="card tealfill" style="flex:1"><h4>Có sẵn</h4><ul class="clean small">
  <li>Manifest, resolved config, checkpoint contract, selection JSON</li><li>Routes, network, summary CSV/JSON của SUMO</li><li>Evidence snapshot 23/09 và audit script (63/63 kiểm tra nguồn/số học đạt)</li><li>Entry points: prepare → train → evaluate → summarize; train/select residual; campaign; demo</li></ul></div>
 <div class="card coralfill" style="flex:1"><h4 style="color:{C["coral"]}">Khoảng trống</h4><ul class="clean coralb small">
  <li><span class="mono">scripts/build_danang_pilot.py</span> không có trong checkout → fresh clone chưa tự tái tạo toàn pipeline SUMO</li>
  <li>Raw campaigns / checkpoints lớn nằm ngoài Git</li><li>Strict release: 14 gates chưa đạt</li><li>NPZ không giữ replay/Adam/RNG → không resume chính xác</li><li>Provenance OSM: ngày tải, version tool ghi <span class="mono">unknown_not_recorded</span></li></ul></div>
</div>
<div class="callout navy" style="margin-top:16px">Kết luận đúng: <b>có nhiều thành phần phục vụ tái lập, còn các khoảng trống đã nhận diện</b>. Không nói “ai clone repo cũng tái tạo đầy đủ ngay”.</div>
''', secs=0, kind="backup", source="docs/research/thesis-review-verification.md · docs/research/thesis-evidence-audit.json", notes=N("Dùng khi bị hỏi về reproducibility.", ["Audit 63/63 ≠ strict release", "Thiếu build_danang_pilot.py", "Nói thẳng, không né"]))

slide(B, "B8 · Độ nhạy nhu cầu SUMO", f'''
<div class="row" style="gap:22px">
 <div style="flex:1.4"><img class="fig" src="{img("sensitivity")}" style="width:100%;height:440px;object-fit:contain"></div>
 <div style="flex:1"><div class="card"><h4>Cách đọc</h4><ul class="clean small">
  <li>120 lượt ở scale 0,75 / 1,0 / 1,25 / 1,5</li><li>30 lượt scale 1,0 lặp lại điều kiện AM chính → <b>không</b> phải 120 quan sát độc lập bổ sung</li>
  <li>Scaling là tổng hợp (synthetic), không phải đo thực địa</li><li>0 collision · 4 emergency events</li></ul></div></div>
</div>''', secs=0, kind="backup", source="results/danang_protocol_v1/summary/demand-sensitivity.png", notes=N("Dùng khi bị hỏi về robustness theo mức nhu cầu.", ["Scale 1,0 trùng điều kiện chính", "Synthetic scaling", "4 emergency, 0 collision"]))

qa = [("Một model hay nhiều model?", "Hai family: SUMO dueling Double DQN (16 → 3 Q); CityFlow residual Double DQN (27/macro → 1 Q), 53 nút chung trọng số."),
      ("Vì sao không GNN, PPO, model lớn hơn?", "Action rời rạc + MLP nhỏ giữ contract dễ kiểm tra. Chưa có so sánh để kết luận tốt hơn hay kém các hướng đó."),
      ("Reward residual là phần cải thiện so với fixed?", "Không. Là −(queue + pending) toàn mạng trong block. Lợi ích so với fixed đo ở evaluation ghép cặp."),
      ("Loss giảm mà queue chưa giảm?", "Loss đo khớp Q với TD target trên replay; không chứng minh greedy policy tốt → chọn bằng validation."),
      ("Hệ thống bảo đảm không tai nạn?", "Ràng buộc phase/transition/anchor là logic simulator; 0 collision trong run. Chưa chứng nhận an toàn ngoài đời."),
      ("γ giống nhau mà hành vi khác?", "0,99/10 s ≠ 0,99/300 s. Muốn so theo thời gian vật lý phải lũy thừa theo số bước."),
      ("Seed rejected nhưng test tốt?", "Không đảo ngược quyết định validation; chỉ báo như chẩn đoán post hoc."),
      ("Đủ cho một thesis?", "Đủ cho nghiên cứu phát triển hệ thống + đánh giá mô phỏng có phân tích thất bại; chưa đủ cho claim triển khai.")]
qah = "".join(f'<div class="card" style="padding:9px 13px"><div style="font-weight:800;color:{C["navy"]};font-size:15px">{q}</div><div class="xsmall">{a}</div></div>' for q, a in qa)
slide(B, "B9 · Trả lời nhanh các câu hỏi thường gặp", f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">{qah}</div>', secs=0, kind="backup",
      source="docs/defense/thesis-understanding-guide-vi.md §22 · docs/defense/committee-questions-evidence-vi.md", notes=N(
          "Slide phao cứu sinh. Mỗi câu trả lời: 1 câu kết luận + 1 câu giới hạn + chỉ vào bằng chứng.", ["Trả lời ngắn, rồi dừng", "Luôn kèm giới hạn", "Mở artifact nếu cần"]))


# ================================================================ render
def progress(section):
    if section == B:
        return ""
    i = SECTIONS.index(section)
    return '<div class="progress">' + "".join(
        f'<span class="{"on" if j == i else ("done" if j < i else "")}">{s}</span>' for j, s in enumerate(SECTIONS)) + "</div>"


def mmss(sec):
    return f"{sec // 60:02d}:{sec % 60:02d}"


def slide_html(idx, total_main, s):
    kind = s["kind"]
    num = f"{idx:02d} / {total_main:02d}" if s["section"] != B else s["title"].split(" · ")[0]
    if kind == "cover":
        return f'<section class="slide cover"><div class="band"></div>{s["body"]}</section>'
    cls = "slide " + ("results" if kind == "results" else "backup" if kind == "backup" else "")
    kicker = s["kicker"] or (s["section"] if s["section"] != B else "Backup · dùng khi được hỏi")
    return f'''<section class="{cls}"><div class="band"></div><div class="kicker">{kicker}</div>{progress(s["section"])}
<div class="title" style="font-size:{34 if len(s["title"]) <= 56 else 30 if len(s["title"]) <= 68 else 27}px">{s["title"]}</div><div class="content">{s["body"].replace("~", "≈")}</div>
<div class="footer"><div class="src">{html.escape(s["source"]) if s["source"] else AUTHOR + " · Bảo vệ luận văn thạc sĩ"}</div><div class="num">{num}</div></div></section>'''


def build():
    main = [s for s in S if s["section"] != B]
    total_main = len(main)
    total_secs = sum(s["secs"] for s in main)
    slides_html = []
    i_main = 0
    for s in S:
        if s["section"] != B:
            i_main += 1
        s["html"] = slide_html(i_main, total_main, s)
        slides_html.append(s["html"])
    head = '<!doctype html><html lang="vi"><head><meta charset="utf-8"><link rel="stylesheet" href="style.css">'
    deck = head + '<style>@page{size:1280px 720px;margin:0}</style></head><body>' + "".join(slides_html) + "</body></html>"
    (HERE / "deck.html").write_text(deck, encoding="utf-8")

    # ---------- notes
    pages = []
    cum = 0
    timing_rows = []
    for s in main:
        cum += s["secs"]
        timing_rows.append((s, cum))
    # cover page of notes: timing plan + cheat sheet
    tp = "".join(
        f'<tr><td class="r">{k+1:02d}</td><td>{html.escape(s["title"] or ("Trang bìa" if k == 0 else "Kết luận & cảm ơn"))}</td><td class="c">{mmss(s["secs"])}</td><td class="c"><b>{mmss(c)}</b></td></tr>'
        for k, (s, c) in enumerate(timing_rows))
    pages.append(f'''<div class="npage"><h2>Kịch bản người nói · bảo vệ 40 phút</h2>
<div style="font-size:13px;margin-bottom:8px">Deck chính có {total_main} slide, tổng <b>{mmss(total_secs)}</b> nói + khoảng <b>{mmss(2400 - total_secs)}</b> dự phòng cho chuyển demo, câu hỏi chen ngang hoặc nói chậm. Cột “Mốc” là thời điểm <b>kết thúc</b> slide — dùng để tự kiểm tra khi tập.</div>
<table class="t"><tr><th class="r">#</th><th>Slide</th><th class="c">Thời lượng</th><th class="c">Mốc</th></tr>{tp}</table>
<div class="nsec" style="margin-top:10px"><h5>Mốc kiểm tra khi đang nói</h5><p>Hết phần Dữ liệu (slide 9) ≈ <b>11:00</b> · hết SUMO (slide 14) ≈ <b>18:15</b> · hết CityFlow (slide 19) ≈ <b>24:45</b> · hết Kết quả (slide 24) ≈ <b>32:00</b>. Nếu chậm hơn 2 phút: rút gọn slide 10–11 (nền tảng RL) và slide 21, 23.</p></div>
<div class="nfoot"><span>{AUTHOR} · Speaker notes</span><span>Trang 1</span></div></div>''')
    cheat = [
        ("Nguồn", "Phan, Le & Nguyen (2025), MAKE 7(3):65 · camera 01/04/2025 · 4 movement · 48 dòng / 192 giá trị"),
        ("Lịch công bố", "32 / 28 / 22 green + 3 × 7 yellow = 103 s"),
        ("Demand SUMO", "normal 1.395 · AM 2.330 (train) · PM 2.400 xe/h (tổng 4 movement camera)"),
        ("Mạng", "53 signals · 1.290 route families (644/323/323) · 500 route streams/case · motorcycle 0,90"),
        ("Splits", "train 9 · val 6 · test 15 case (3 regime × 5) · demand 101–105 / sim 201–205"),
        ("SUMO model", "16 → 64 → 64 → V/A → 3 Q · 5.508 tham số · 10 s step · 7 s yellow · 20 s min green · n-step 3"),
        ("SUMO train", "30 ep × 5 seeds (11–15) · 360 decisions/ep · ε 1→0,05 / 5.000 · val mỗi 5 ep · 120 lượt test"),
        ("Residual model", "27 = 12 + 12 + 3 → 64 → 64 → 1 · 6.017 tham số · shared 53 nút · ±10 s · macro 300 s · MAX_MACROS 59"),
        ("Residual train", "12 ep · 6 peak case · 7.632 transitions · 1.152 updates · ε 0,15 · target 64 · val ep 4/8/12"),
        ("Selector", "seeds 12 (ep8) · 14 (ep4) · 15 (ep8) selected · 13, 16 rejected · strict release complete=false (14 gates)"),
        ("SUMO kết quả", "Normal 9,86 → 41,50 (+320,7%) · AM 79,20 → 78,41 (−1,0%) · PM 152,67 → 99,97 (−34,5%)"),
        ("SUMO CI", "Normal [7,60; 56,14] · AM [−9,47; 8,49] · PM [−69,55; −35,34] veh-h (5 seed effects)"),
        ("Mạng kết quả", "Fixed 8.339,43 · MP 6.347,00 (−23,89%) · HMP 6.739,13 (−19,19%) · Residual 7.829,25 (−6,12%)"),
        ("Residual theo regime", "normal 0% · AM 3,48% · PM 10,39% pooled (8,86% mean per-case)"),
        ("Metric phụ", "completion +1,06 điểm % · insertion +0,82 · travel time +5,45 s · spillback +65,20 lane-s"),
        ("PM-only gate", "mean 3,48% · range 1,03–5,62% · CI [2,01; 4,95] · 15/25 tốt · 10/25 xấu · POST HOC"),
        ("Demo", "PM demand105/sim205 · seed14 ep4 · nút 420249521 · 18:05 = 1.085 s · 14 vs 1 xe"),
    ]
    ch = "".join(f"<tr><td><b>{a}</b></td><td>{b}</td></tr>" for a, b in cheat)
    pages.append(f'''<div class="npage"><h2>Bảng con số phải thuộc</h2>
<table class="t"><tr><th style="width:130px">Chủ đề</th><th>Con số</th></tr>{ch}</table>
<h3>Năm câu không bao giờ nói</h3><ul style="padding-left:18px">
<li>“RL tốt hơn lịch cố định” — không kèm regime và baseline.</li><li>“Mạng 53 nút là toàn bộ đèn thực tế Hải Châu.”</li>
<li>“3,48% là kết quả đã xác nhận.” — đó là phân tích post hoc.</li><li>“500 routes là 500 xe” / “18:05 là 6 giờ chiều”.</li><li>“Model dùng GNN / multi-agent communication.”</li></ul>
<h3>Công thức trả lời mọi câu hỏi</h3><p><b>1 câu kết luận</b> → <b>1 câu giới hạn</b> → <b>chỉ vào bằng chứng</b> (slide backup, file, số). Nếu không biết: “Hiện em chưa có thí nghiệm tách riêng yếu tố đó; hướng kiểm tra sẽ là …”.</p>
<div class="nfoot"><span>{AUTHOR} · Speaker notes</span><span>Trang 2</span></div></div>''')

    pno = 3
    i_main = 0
    for s in S:
        n = s["notes"]
        if s["section"] != B:
            i_main += 1
            cum_s = [c for (x, c) in timing_rows if x is s][0]
            label = f"Slide {i_main:02d}"
            tm = f"⏱ {mmss(s['secs'])} · mốc {mmss(cum_s)}"
        else:
            label = s["title"].split(" · ")[0]
            tm = "Backup"
        title = s["title"] or ("Trang bìa" if i_main == 1 else "Kết luận & cảm ơn")
        keys = "".join(f"<div>{k}</div>" for k in n.get("keys", []))
        avoid = "".join(f"<li>{a}</li>" for a in n.get("avoid", []))
        qa_ = "".join(f'<div class="qa-item"><span class="q">H: {q}</span><br>Đ: {a}</div>' for q, a in n.get("qa", []))
        pages.append(f'''<div class="npage"><div class="nhead"><div class="t">{label} · {html.escape(title.split(" · ", 1)[-1] if s["section"] == B else title)}</div><div class="tm">{tm}</div></div>
<div class="thumb">{s["html"]}</div>
<div class="nsec"><h5>Ý phải nhớ</h5><div class="keys">{keys}</div></div>
<div class="nsec"><h5>Lời nói gợi ý</h5><p>{n.get("say", "")}</p></div>
{f'<div class="nsec avoid"><h5>Tránh nói</h5><ul>{avoid}</ul></div>' if avoid else ""}
{f'<div class="nsec qa"><h5>Nếu bị hỏi</h5>{qa_}</div>' if qa_ else ""}
<div class="nfoot"><span>{AUTHOR} · Speaker notes</span><span>Trang {pno}</span></div></div>''')
        pno += 1
    notes = head + '<style>@page{size:794px 1123px;margin:0}</style></head><body>' + "".join(pages) + "</body></html>"
    (HERE / "notes.html").write_text(notes, encoding="utf-8")
    print(f"main slides: {total_main}, backup: {len(S) - total_main}, spoken time: {mmss(total_secs)}")


if __name__ == "__main__":
    build()
