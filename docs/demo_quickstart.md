# Quick-start demo + cheat-sheet số liệu (1 trang, cầm đi họp)

> Cập nhật 2026-07-30. Số trong trang này lấy trực tiếp từ `results/multiseed/*.json`,
> `results/*/agreement/agreement.json`, `results/*/robustness/*.json`.
> Kiểm chứng cùng ngày: **85 pytest** + **14 node test** pass; cả 2 trang demo đã mở
> thật trên browser, 0 lỗi console.

---

## 1. Chạy demo (không cần Docker/CityFlow)

```bash
python3 scripts/serve_replay.py --no-browser
```

| Trang | URL | Bấm ngay khi mở |
|-------|-----|-----------------|
| **3D (deck.gl)** | http://localhost:8080/frontend/replay_3d.html | **🔍 Điểm đông** |
| **2D (canvas)** | http://localhost:8080/frontend/replay_ab.html | **🔍 Zoom cụm nút** |

> ⚠️ **Bắt buộc bấm nút zoom trước khi nói.** Ở khung nhìn toàn mạng (53 nút, ~7×10 km)
> một chiếc xe 2 m chỉ chiếm ~0.1 px → **chỉ thấy đường, không thấy xe**. Nút zoom nhảy
> tới ô đông xe nhất của replay (~300 m ở bản 3D, ~600 m ở bản 2D) — chỗ đó thấy rõ
> hàng chờ và đèn từng làn.

Ảnh dự phòng nếu máy chiếu/WebGL lỗi:
`results/presentation/demo3d_ab_rush.png` · `results/presentation/demo2d_ab_rush.png`

---

## 2. Kịch bản trình bày 10–15 phút

| Phút | Làm gì | Câu chốt |
|:----:|--------|----------|
| 0–2 | Mở **3D**, bấm 🔍 Điểm đông, bấm ▶︎ Chạy | "Trái Cố định, phải DQN, **cùng kịch bản cùng seed**, hai khung khoá chung camera và chung thời điểm. Đây là replay CityFlow thật, không phải suy luận trực tiếp." |
| 2–4 | Sang **2D**, đổi kịch bản rush → peak → haichau | "Lợi thế của RL **teo dần khi mạng bão hoà** — và ở kịch bản quá tải nặng thì RL *thua*. Em báo cả chiều đó." |
| 4–6 | Bảng phổ bão hoà (`docs/scenario_regimes.md`) | "4 kịch bản xếp trên 2 trục tải **đo được, độc lập controller** — không phải chọn kịch bản đẹp." |
| 6–8 | Bảng multi-seed + CI (mục 3 dưới) | "5 seed, CI Student-t df=4. Baseline là replay tất định nên std = 0 đúng bản chất." |
| 8–10 | Agreement 25% | "DQN **không bắt chước** Max-Pressure — chỉ trùng quyết định ~25% (cỡ ngẫu nhiên) mà vẫn đạt hiệu năng xấp xỉ." |
| 10–12 | Robustness (âm) | "Giả thuyết 'thắng MP nhờ bền với nhiễu' — em đã kiểm và **nó sai**. Báo đúng như đo được." |
| 12–15 | Chương 4 PDF + xin ý kiến | 3 câu hỏi ở mục 5. |

---

## 3. Cheat-sheet số liệu

**Mạng:** Hải Châu, Đà Nẵng — OSM → SUMO → CityFlow, lọc còn trục chính, **53 nút có đèn**.
**Metric chính:** thời gian chờ tích luỹ (veh-hours). **Multi-seed:** K = 5, CI Student-t (df = 4, ddof = 1).

| Kịch bản | Fixed-Time | Max-Pressure | **DQN** | Random | DQN vs Fixed |
|----------|----------:|-------------:|--------:|-------:|:---:|
| `haichau_rush` (**headline**, 50.5k chuyến) | 179.9 | 107.8 (+40.1%) | **113.2 ± 3.9** | 196.9 | **+37.1%** [34.9, 39.2] |
| `haichau_calib` (75.5k) | 339.6 | 234.2 (+31.0%) | **266.3 ± 28.9** | 350.6 | **+21.6%** [13.1, 30.1] |
| `haichau_peak` (310.9k) | 1198.3 | 1044.0 (+12.9%) | **1137.2 ± 35.3** | 1228.7 | **+5.1%** [2.2, 8.1] |
| `haichau` (1.2M, quá tải nặng) | 912.1 | 820.1 (+10.1%) | **1276.0 ± 12.4** | 928.5 | **−39.9%** [−41.3, −38.5] |

*Cả 4 khoảng tin cậy đều không cắt 0. Không kịch bản nào DQN vượt Max-Pressure.*

**Tải mạng (đo dưới Fixed-Time, độc lập controller):**

| Kịch bản | Xe đồng thời | Hàng chờ đỉnh | % dừng | Chế độ |
|----------|-----------:|-----------:|------:|--------|
| `rush` | 2 900 | 1 210 | 42% | cao điểm thực (leverage lớn nhất) |
| `calib` | 4 680 | 2 370 | 51% | khá nặng |
| `haichau` | 11 370 | 7 340 | 65% | quá tải nặng |
| `peak` | 12 570 | 8 530 | 68% | đợt tăng quá tải |

**Agreement với Max-Pressure:** 25.1% (rush) · 26.5% (calib) — cỡ mức ngẫu nhiên;
chỉ 6–8 / 53 nút đạt ≥70% → **cùng đẳng cấp hiệu năng, chính sách khác hẳn.**

**Robustness (kết quả âm, báo trung thực):**
- *Incident* (nút bận nhất kẹt green, 1/3 giữa horizon): mọi controller xấu đi 1–4%;
  DQN xấu hơn chút (rush +4.2% vs MP +2.7%, Fixed +1.7%) → **không có lợi thế bền vững**.
- *Demand shift bất đối xứng:* rush→calib gần như miễn phí (−1.5%); calib→rush **+45.8%**
  → train ở regime nhẹ generalize tốt hơn.

**Kỹ thuật:** DQN viết tay bằng NumPy (không torch/SB3), param-sharing 53 agent,
85 pytest + 14 node test, test host chạy không cần container (FakeEngine).

---

## 4. Con số nào đi với chỗ nào (tránh bị hỏi vặn)

| Chỗ | Số | Vì sao khác |
|-----|----|-------------|
| Bảng điểm trên demo | DQN **▼30.8%** rush | 1 seed — chính episode đang phát, đọc từ `comparison.json` |
| Paper / cheat-sheet | DQN **+37.1%** rush | Trung bình **5 seed** ± CI Student-t |

Câu trả lời 1 dòng: *"Demo phát đúng một episode một seed (30.8%); con số trong luận văn
là trung bình 5 seed (37.1% ± 2.2 %-point)."*

---

## 5. Ba câu nên hỏi thầy

1. Khung "báo cả kết quả âm" (không thắng MP, dense −39.9%, robustness không lợi thế)
   — hội đồng chấp nhận được không, hay cần đẩy phần nào lên?
2. Ưu tiên chạy thêm thí nghiệm neighbor-encoder (B3) hay dồn thời gian đánh bóng paper?
3. Contributions 1–3 nên viết lại theo khung "proposed framework" hay gộp thành 1?

---

## 6. Câu hỏi thầy chắc chắn hỏi → trả lời ở đâu

| Câu hỏi | Tài liệu |
|---------|----------|
| Sao không thắng Max-Pressure? | Varaiya 2013 (MP throughput-optimal với queue local) + RESCO + `docs/ablation_honest_plan.md` |
| Sao CityFlow không phải SUMO? | Tốc độ multi-agent 53 nút; SUMO dùng để convert mạng — Ch4 + `README.md` |
| Xe máy mô phỏng thế nào? | Ch4 Limitations + `docs/thesis_improvement_review.md` §E3 (SUMO Sublane Model) |
| 5 seed đủ chưa? | `docs/thesis_improvement_review.md` §A1 (t-CI + Colas 2018) |
| Demand có thật không? | Synthetic, calib theo phổ bão hoà — `docs/demand_calibration_results.md` |
| Đèn từng làn trong demo 3D là làn số mấy? | Thứ tự thanh theo thứ tự làn trong replay; **chưa** đối chiếu trái/phải với viewer gốc → thông điệp là "nhánh nào xanh" (`docs/demo_replay_3d.md`) |

Danh mục đầy đủ những gì nên/chưa nên đưa: [showcase_for_supervisor.md](showcase_for_supervisor.md).
