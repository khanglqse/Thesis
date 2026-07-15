# Demo "Điều khiển nút giao bằng RL" cho Presentation — Ghi chú Brainstorm (WIP)

> **Trạng thái:** Đang brainstorm — **CHƯA chốt thiết kế, CHƯA lập kế hoạch triển khai.**
> File này chụp lại trạng thái đang dang dở để tiếp tục sau. Không phải design đã duyệt.
>
> **Ngày:** 2026-07-03 · **Nhánh:** main · **Ngữ cảnh:** nâng cấp trải nghiệm demo cho buổi bảo vệ luận văn.

---

## 1. Mục tiêu (yêu cầu gốc)

> "Tối ưu thật nhiều phần trải nghiệm để demo khi presentation, liên quan đến việc các nút
> giao thông được điều khiển với RL như thế nào."

Nói cách khác: làm cho buổi demo **thể hiện rõ và thuyết phục** rằng RL đang điều khiển các nút
giao — thay vì chỉ chiếu một replay xe chạy chung chung không rõ controller nào, không rõ RL
đang "nghĩ" gì.

---

## 2. Quyết định đã chốt (từ 3 câu hỏi định khung)

| Câu hỏi | Lựa chọn |
|---|---|
| **Bối cảnh** | **Bảo vệ luận văn trực tiếp** (máy chiếu). ⇒ cần chạy ổn định, dễ thao tác / tự chạy được, nhìn rõ trên màn chiếu, ít rủi ro lỗi live. |
| **Thông điệp chính** | **Cả ba — kể thành câu chuyện 3 hồi.** (xem §5) |
| **Phạm vi build** | **Cả hai + dashboard:** nâng cấp viewer hiện có + guided demo app + gọn dashboard. |

---

## 3. Hiện trạng (kết quả khảo sát code)

| Thành phần | File | Vai trò | Khoảng trống |
|---|---|---|---|
| CityFlow replay viewer | `frontend/` (`index.html`, `script.js` ~781 dòng, `Point.js`, `style.css`, `spinner.css`) | Renderer PIXI.js gốc của CityFlow: vẽ mạng, xe chạy, đèn đỏ/xanh; pan/zoom/pause/tua/tốc độ | Không nhãn controller; không overlay "RL quyết định gì"; không so sánh; không đồng hồ waiting-time; **load file thủ công** (rủi ro khi demo live) |
| Dashboard | `dashboard/app.py` (Streamlit) | Bảng so sánh tĩnh, improvement vs Fixed-Time, hình render sẵn, hướng dẫn mở replay | Chỉ đọc; rời rạc với viewer; không phải "trải nghiệm" |
| Phục vụ replay | `scripts/serve_replay.py` | Serve repo qua HTTP, in ra file cần chọn thủ công | Không tự nạp preset |
| Cắt replay | `scripts/truncate_replay.py` | Cắt replay xuống ~120 step để browser load nổi | — |
| Sinh chart | `scripts/build_presentation.py` | Sinh chart + `docs/presentation_results.md` | — |

### Định dạng replay (QUAN TRỌNG cho thiết kế overlay)
Mỗi dòng = 1 step, dạng `carLogs;tlLogs`:
- **Xe:** `x y góc id_xe laneChange dài rộng` (phân tách bởi dấu phẩy).
- **Đèn:** mỗi edge + trạng thái `r`/`g`/`i` theo từng làn.
- ⇒ **KHÔNG có** queue / pressure / state-vector / action / Q-value của agent trong replay.

### `results/<area>/comparison.json`
Có `table` (mỗi controller: `final_average_travel_time`, `mean_total_queue`, `mean_reward`,
**`queue_series`** = tổng queue theo thời gian), `best_controller`, `improvement_vs_fixed_pct`.
⇒ **đủ** cho đồng hồ realtime tổng & KPI (Act 2/3); **chưa đủ** cho overlay per-nút (Act 1).

---

## 4. Tài nguyên sẵn có để build demo

- **Demo replays** (đã cắt ~120 step, browser load nổi) theo controller `fixed_time`,
  `max_pressure`, `random`, `dqn` tại `results/<area>/demo/replay_<controller>_demo.txt`.
  Có sẵn cho: `full`, `subarea`, `haichau_peak`, `haichau`, và `references/haichau*`.
- **Roadnet replay JSON:** `data/danang/replay_roadnet_<area>.json`.
- **Kịch bản (scenarios):** `haichau`, `haichau_calib`, `haichau_peak`, `haichau_rush`.
- **Kết quả headline** (`docs/presentation_results.md`), % so với Fixed-Time (metric = waiting time, veh-h):
  - `haichau_rush`: **DQN +30.8%**, MaxPressure +40.1% — chênh lệch rõ nhất, kể chuyện tốt nhất.
  - `haichau_calib`: DQN +22.2% (reward_scale=0.5), MaxPressure +31.0%.
  - `haichau_peak`: DQN +5.3–9.0%, MaxPressure +12.9%.
- **Lưu ý từ memory dự án:**
  - Metric headline = **cumulative waiting time (veh-hours)**, không dùng mean travel time của CityFlow.
  - **DQN tiệm cận nhưng không vượt Max-Pressure** (đã thử mọi biến thể reward/dueling) — trình bày trung thực.
  - Mạng Hải Châu đã lọc còn **73 nút** trục chính (bỏ hẻm dân sinh).

---

## 5. Ý tưởng trải nghiệm demo — câu chuyện 3 hồi

### Hồi 1 — "RL nghĩ gì ở MỘT nút giao"
- Zoom vào 1 nút giao đại diện.
- Overlay mỗi hướng tiếp cận: độ dài hàng đợi / áp lực (số + màu nhiệt).
- Highlight pha đèn hiện tại; khi RL đổi pha → hiệu ứng + nhãn "RL chọn pha X".
- Panel bên: state (đầu vào) → action (pha) → vì sao (hướng áp lực cao nhất).
- ⚠️ **Dữ liệu Act 1 KHÔNG có sẵn trong replay** — xem §8 (phải tính client-side từ vị trí xe
  quanh nút, hoặc export thêm state/action khi eval).

### Hồi 2 — "RL vs Fixed-Time"
- Split-screen: cùng scenario, cùng seed, 2 controller chạy song song đồng bộ.
- Đồng hồ waiting-time (veh-h) tích lũy mỗi bên, cập nhật realtime (dùng `queue_series`).
- Thanh chênh lệch: "RL đang tiết kiệm X veh-h".
- Chọn scenario (rush/peak/calib) từ preset — **`haichau_rush` cho tương phản mạnh nhất**.

### Hồi 3 — "Toàn mạng Hải Châu"
- Toàn cảnh 73 nút.
- Heatmap tắc nghẽn (queue): Fixed-Time đỏ rực → RL dịu hơn.
- Panel KPI tổng: waiting time, queue, % cải thiện vs Fixed-Time.
- Liên kết sang dashboard chi tiết.

---

## 6. Cải tiến hạ tầng / trải nghiệm (xuyên suốt)

- **Preset launcher:** bỏ file-picker thủ công; chọn scenario + controller từ dropdown → tự nạp
  roadnet + replay (giảm rủi ro khi demo live).
- **HUD luôn hiện:** tên controller, scenario, step, số xe, waiting-time.
- **Story/autoplay mode:** nút "Play story" chạy tuần tự 3 hồi.
- **Nhìn rõ trên máy chiếu:** font lớn, tương phản cao, màu đèn rõ ràng.
- **Loop an toàn** phòng khi lỡ tay.
- Phím tắt sẵn có giữ nguyên: `P` pause, `[`/`]` tua, `1`/`2` tốc độ.

---

## 7. Phương án kiến trúc (CHƯA chốt — bước tiếp theo)

- **A — Sửa tại chỗ `frontend/script.js`:** thêm overlay + HUD + preset loader ngay trong renderer
  gốc. Tái dùng tối đa, ít lệ thuộc; nhưng đây là code vendored, khó mở rộng/bảo trì.
- **B — Lớp "presenter" tách riêng bọc quanh viewer (khuyến nghị sơ bộ):** giữ nguyên `script.js`,
  thêm `demo.js` + panel HUD/overlay điều phối; preset loader nạp file thay người dùng. Sạch, dễ bảo trì.
- **C — App guided riêng** (route Streamlit mới hoặc trang HTML mới) điều phối replay + overlay +
  so sánh, dùng lại renderer.

> Nghiêng về **B**, nhưng cần vẽ mockup bố cục màn hình để chốt. Chưa quyết.

---

## 8. Câu hỏi kỹ thuật mở (cần trả lời trước khi chốt)

1. **Overlay Act 1 (queue/pressure per-nút):** replay không có sẵn. Hai hướng:
   (a) tính client-side từ vị trí xe gần nút giao; (b) export thêm state/action/Q-value khi chạy eval.
   → cần quyết & kiểm tra khả thi.
2. **Split-screen Act 2:** chạy 2 replay đồng bộ trong 1 trang có nặng không? (mỗi demo replay vài
   chục MB, ~120 step) → cần thử nghiệm hiệu năng.
3. **Chọn scenario/controller** đưa vào demo: `haichau_rush` (DQN +30.8%) kể chuyện tốt nhất; có cần thêm không?
4. **Trình bày DQN vs Max-Pressure:** DQN không vượt Max-Pressure — story cần khung trung thực
   (vd. "RL học được chính sách xấp xỉ Max-Pressure mà không cần công thức thủ công").

---

## 9. Việc còn dang dở (theo quy trình brainstorming)

- [ ] Chốt phương án kiến trúc A/B/C — **cần vẽ mockup bố cục** (visual companion đang chạy: http://localhost:57573).
- [ ] Mockup: HUD, overlay nút giao (Act 1), split-screen so sánh (Act 2), heatmap toàn mạng (Act 3).
- [ ] Chốt danh sách scenario/controller.
- [ ] Trả lời câu hỏi kỹ thuật §8 (đặc biệt nguồn dữ liệu Act 1).
- [ ] Trình bày design theo từng phần → user duyệt.
- [ ] Viết spec chính thức → `docs/superpowers/specs/2026-<...>-rl-demo-experience-design.md`.
- [ ] Self-review spec + user review.
- [ ] Chuyển sang `writing-plans` để lập kế hoạch triển khai.

---

## 10. Điểm tiếp tục (resume pointer)

Đang ở **bước "Ask clarifying questions"** của skill brainstorming. Đã có 3 quyết định định khung
(§2). Việc tiếp theo hợp lý: **quyết nguồn dữ liệu cho overlay Act 1** (§8.1) rồi **vẽ mockup bố cục**
để chốt kiến trúc (§7), sau đó mới trình bày design đầy đủ.
