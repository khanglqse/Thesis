"""English slides with Vietnamese speaker notes.

Pairs each English slide with the Vietnamese script for the same page.
"""
import html
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AUTHOR = "Luong Quang Khang"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def mmss(sec):
    return f"{int(sec) // 60:02d}:{int(sec) % 60:02d}"


def en_label(s):
    if s["kind"] == "cover":
        return "Cover"
    if s["kind"] == "closing":
        return "Closing and thanks"
    if s["kind"] == "divider":
        return "Section divider"
    return s["title"]


def main():
    en = load(ROOT / "docs/defense/.build-40min-en/build_en.py", "deck_en")
    vi = load(ROOT / "docs/defense/.build-40min-vi/build_vi.py", "deck_vi")
    en.build()
    vi.build()
    if len(en.S) != len(vi.S):
        raise SystemExit(f"slide count differs: en {len(en.S)} vi {len(vi.S)}")
    for i, (a, b) in enumerate(zip(en.S, vi.S)):
        if a["kind"] != b["kind"] or a["secs"] != b["secs"]:
            raise SystemExit(f"slide {i} mismatch: {a['kind']}/{a['secs']} vs {b['kind']}/{b['secs']}")

    main_slides = [s for s in en.S if s["section"] != en.B]
    total = sum(s["secs"] for s in main_slides)
    pages, cum, rows = [], 0, []
    for s in main_slides:
        cum += s["secs"]
        s["cum"] = cum
        rows.append(
            f'<tr><td class="r">{s["n"]}</td><td>{html.escape(en_label(s))}</td>'
            f'<td class="c">{mmss(s["secs"])}</td><td class="c"><b>{mmss(cum)}</b></td></tr>'
        )
    marks = {name: max(s["cum"] for s in main_slides if s["section"] == name) for name in en.SECTIONS}
    pages.append(f'''<div class="npage"><h2>Kịch bản tiếng Việt cho slide tiếng Anh</h2>
<p style="font-size:14px;margin-bottom:8px">{len(main_slides)} trang chính, nói <b>{mmss(total)}</b> cộng khoảng <b>{mmss(2400 - total)}</b> dự phòng. Tên trang bên dưới là tiêu đề slide tiếng Anh. “Mốc” là thời điểm ở <b>cuối</b> mỗi trang.</p>
<table class="t timing"><tr><th class="r">#</th><th>Trang tiếng Anh</th><th class="c">Thời lượng</th><th class="c">Mốc</th></tr>{"".join(rows)}</table>
<h4>Mốc khi đang nói</h4><p style="font-size:14.5px">Hết Data ≈ <b>{mmss(marks["Data"])}</b>, hết SUMO ≈ <b>{mmss(marks["SUMO"])}</b>, hết CityFlow ≈ <b>{mmss(marks["CityFlow"])}</b>, hết Results ≈ <b>{mmss(marks["Results"])}</b>. Nếu chậm hơn 2 phút: rút phần RL basics, slide đọc kết quả SUMO và slide chỉ số phụ.</p>
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
    for a, b in zip(en.S, vi.S):
        nt = b["notes"]
        if a["section"] != en.B:
            head_l = f'Trang {a["n"]} · {html.escape(en_label(a))}'
            tm = f'⏱ {mmss(a["secs"])} · mốc {mmss(a["cum"])}'
        else:
            head_l = html.escape(a["title"])
            tm = "Phụ lục"
        keys = "".join(f"<div>{k}</div>" for k in nt.get("keys", []))
        avoid = "".join(f"<li>{x}</li>" for x in nt.get("avoid", []))
        qa_ = "".join(f'<div class="qa-item"><span class="q">H: {q}</span><br>Đ: {ans}</div>' for q, ans in nt.get("qa", []))
        pages.append(f'''<div class="npage"><div class="nhead"><div class="t">{head_l}</div><div class="tm">{tm}</div></div><div class="thumb">{a["html"]}</div>
<div class="nsec"><h5>Nhớ</h5><div class="keys">{keys}</div></div><div class="nsec"><h5>Nói gì</h5><p>{nt.get("say", "")}</p></div>
{f'<div class="nsec avoid"><h5>Tránh</h5><ul>{avoid}</ul></div>' if avoid else ""}{f'<div class="nsec qa"><h5>Nếu được hỏi</h5>{qa_}</div>' if qa_ else ""}
<div class="nfoot"><span>{AUTHOR}, slide tiếng Anh, lời thoại tiếng Việt</span><span>Trang {p}</span></div></div>''')
        p += 1

    head = '<!doctype html><html lang="vi"><head><meta charset="utf-8"><link rel="stylesheet" href="../.build-40min-vi/style.css">'
    (HERE / "notes.html").write_text(
        head + "<style>@page{size:794px 1123px;margin:0}</style></head><body class=\"notes\">" + "".join(pages) + "</body></html>",
        encoding="utf-8",
    )
    print(f"notes pages: {len(pages)}, slides: {len(en.S)}, speaking time: {mmss(total)}")


if __name__ == "__main__":
    main()
