# Thesis Upgrade Roadmap — Traffic RL (Hải Châu / CityFlow)

> **ARCHIVED PLANNING SNAPSHOT.** This July 2026 roadmap predates the current evidence-tier
> and release-gated v2 protocol. Historical claims and task states below are not current thesis
> evidence; use `paper/thesis_danang.tex`, `README.md`, and `docs/defense/demo-runbook.md`.

> **NOTE (2026-07-15):** "+30.8%" below is the old single-seed rush number. Final multi-seed
> headline = **+37.1% ± 3.9** (rush, Student-t); dense −39.9%. Canonical: [scenario_regimes.md](scenario_regimes.md).

> **Ngày:** 2026-07-12 · **Ngữ cảnh:** đánh giá hiện trạng thesis + kế hoạch nâng cấp toàn diện (nghiên cứu + demo + paper).
> **Quỹ thời gian:** > 1 tháng tới buổi bảo vệ. **Phạm vi user chốt:** làm cả 3 hướng (demo, robustness, đánh bóng nghiên cứu).
>
> Tài liệu này là *bản đồ chương trình* — theo dõi tiến độ qua task list (#1–#4). Cập nhật khi mỗi phase xong.

---

## 1. Đánh giá hiện trạng — dự án đang ở đâu

**Kết luận: phần nghiên cứu + thực nghiệm thực sự tốt và trung thực. Vấn đề lớn nhất nằm ở phần *viết* (paper LaTeX lệch với code).**

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Pipeline dữ liệu thật (OSM→SUMO→CityFlow) | ✅ Xong | Mạng Hải Châu, lọc còn ~53–73 nút trục chính (bỏ hẻm) |
| DQN from-scratch (NumPy, Py3.6-safe) | ✅ Xong | multi-agent, parameter-shared; ràng buộc do CityFlow chạy trong container x86 |
| Baselines | ✅ Xong | Fixed-Time (tuned green 25/40s), **Max-Pressure**, Random |
| Ablation nghiêm túc | ✅ Xuất sắc | 5 reward, Dueling, ATS-state (Advanced-XLight), n-step, MP warm-start — **báo cả kết quả âm** |
| Nhiều kịch bản demand | ✅ Xong | haichau / calib / peak / **rush** (DQN **+30.8%** vs Fixed-Time) |
| Charts + báo cáo tự sinh | ✅ Xong | `docs/presentation_results.md`, `docs/model_ablation.md` |
| Viewer replay + dashboard | 🟡 Thô | CityFlow PIXI.js gốc, load file thủ công (rủi ro khi demo live) |
| **Paper (LaTeX)** | 🔴 **Lệch nặng** | Xem §2 — vấn đề #1 |
| Demo "3 hồi" cho bảo vệ | 🟡 Brainstorm WIP | Spec `2026-07-03-rl-demo-experience-brainstorm.md`, chưa build |

---

## 2. Phát hiện quan trọng — paper LaTeX lệch với công trình thật

Đây là rủi ro tín nhiệm lớn nhất và phải sửa trước tiên. Kết quả thật **trung thực và defensible hơn** những gì paper đang viết.

| Chỗ trong paper | Paper đang nói | Thực tế đã build | Hành động |
|---|---|---|---|
| `chapter4_experiments_results.tex` | SUMO, **3 nút linear**, controller **Actuated + Adaptive**, "DQN giảm **48.9%** waiting, thắng mọi baseline"; plot `three_intersections/.../comparison_20251027_191348.png` | CityFlow, mạng Hải Châu, controller **Max-Pressure** (không có Actuated/Adaptive); **DQN KHÔNG vượt Max-Pressure** | **Xóa & viết lại** từ kết quả thật. Số cũ là của prototype 3-nút bị bỏ 10/2025 và **mâu thuẫn** với phát hiện thật |
| `trafic_rf.tex` Methodology | CTDE, QMIX/VDN/MAAC, GNN message-passing, attention broadcasting, PPO/DDPG, "CTDE MARL in **SUMO** via **TraCI**", Ray RLlib | **parameter-shared DQN** (NumPy), state **local** queue+phase, pressure reward, **CityFlow** (không TraCI), không communication | Viết đúng lại phần đã build; chuyển khung tham vọng thành **"proposed framework / future work"** rõ ràng |
| Abstract / Intro | "average travel time" là outcome chính | Headline metric thật = **cumulative waiting time (veh-h)** (travel time của CityFlow tách kém) | Sửa metric cho khớp |
| `chapter4_results.md` (auto-gen cũ) | 53 nút, 60 episodes, +15.6% queue | Bản mới nhất: haichau_rush **+30.8% waiting** | Thống nhất 1 con số nút + scenario headline |
| Limitation | (chưa nêu) | Xe máy = **xấp xỉ** (template ngắn/hẹp, KHÔNG có sub-lane filtering thật); demand **tổng hợp** chưa calibrate từ đếm xe thật | Nêu thẳng như limitation trung thực |

---

## 3. Định hình lại "wow" — quan trọng

**KHÔNG biến "làm wow" thành cuộc đua vượt Max-Pressure.** Ablation (`docs/model_ablation.md`) đã chứng minh kèm lý do lý thuyết: trên mạng arterial nhỏ với quan sát *local*, Max-Pressure gần như tối ưu throughput trên đúng thông tin nó thấy → RL rất khó thắng. Đây là ngõ cụt đã ghi nhận.

**"Wow" thật đã sẵn có — chỉ cần kể đúng:**
> DQN **tự học lại chính sách cỡ Max-Pressure từ số đếm local thô, KHÔNG cần công thức pressure thủ công**, đánh bại Fixed-Time đã tune **+30.8%**, trên **mạng một thành phố VN thật (Hải Châu, có xe máy)** — cộng nghiên cứu **robustness** (RL bền hơn heuristic khi có nhiễu/sự cố) và một **demo trực tiếp bóng bẩy** kể câu chuyện đó.

Con đường trung thực DUY NHẤT để thật sự "thắng heuristic" = **robustness** (Phase 1): Max-Pressure cần đo pressure chính xác; khi cảm biến nhiễu hoặc có sự cố, learned policy có thể bền hơn.

---

## 4. Roadmap 4 phase (thứ tự theo phụ thuộc dữ liệu)

### Phase 0 — Đồng bộ paper (BẮT BUỘC, làm trước) · Task #1
- Viết lại Chapter 4 từ kết quả thật (4 scenario, headline waiting-time, bảng ablation, khung trung thực "DQN ≈ MP, > Fixed-Time").
- Viết đúng lại Methodology cho khớp code; chuyển CTDE/QMIX/GNN → future work.
- Thống nhất metric, số nút, scenario giữa các docs.
- **Rủi ro cao nhất nếu bỏ qua, công sức thấp nhất — dữ liệu đã có.**

### Phase 1 — Robustness study (upside nghiên cứu) · Task #2
- Thêm 3 nhiễu: (a) nhiễu quan sát queue (Gaussian/rơi gói), (b) sự cố lane-closure giữa episode, (c) dịch chuyển demand (train ở regime này, test regime khác).
- So sánh độ suy giảm: DQN vs Max-Pressure vs Fixed-Time.
- Sinh kết quả MỚI cho Chapter 4 + nguyên liệu demo Act 3.
- **Stretch (nếu còn thời gian):** 1 lever thuật toán từ future-work đã nêu — effective-range running-vehicle count, hoặc residual/KL-RL trên MP warm-start.

### Phase 2 — Demo 3 hồi (payoff cao nhất cho defense) · Task #3
- Hạ tầng: preset launcher (bỏ file-picker), HUD luôn hiện, chạy ổn định trên máy chiếu.
- **Act 1** zoom-1-nút: overlay queue/pressure + "RL chọn pha X". → **Dữ liệu phải EXPORT khi eval** (state/action/Q per-nút), KHÔNG dựng lại client-side (đường mong manh — xem brainstorm §8).
- **Act 2** split-screen RL vs Fixed-Time đồng bộ + đồng hồ waiting-time tích lũy.
- **Act 3** heatmap toàn mạng + KPI; khoe được kết quả robustness Phase 1 (RL "dịu" khi có sự cố, Fixed-Time/MP "đỏ rực").
- Phụ thuộc: Act 3 robustness cần Phase 1; hạ tầng viewer làm song song được.

### Phase 3 — Đánh bóng nghiên cứu & tái lập · Task #4
- Deep-research SOTA TSC-RL gần đây (WebSearch / skill `deep-research` — *không có MCP Perplexity*); củng cố trích dẫn khung MP-ceiling.
- Viết lại Contribution/framing thuyết phục; README + hướng dẫn tái lập.
- Cập nhật limitations trung thực.

---

## 5. Quyết định mở cần user chốt (trong Phase 0)

**Khung Methodology:** giữ tầm nhìn lớn (CTDE/MARL/GNN) hay viết đúng cái đã build?
- **(A) Write-down:** thu thesis về đúng param-shared DQN đã build. Trung thực nhất, phạm vi nhỏ hơn, lit-review vẫn giữ.
- **(B) Khuyến nghị — "Proposed framework + validated subset":** giữ chương framework tham vọng NHƯNG demarcate cực rõ phần *đã kiểm chứng* (param-shared DQN local) vs *future work* (coordination/GNN/CTDE). Giữ được chiều sâu lit-review + tầm nhìn, vẫn trung thực. Cần cẩn thận không để đọc nhầm là "đã làm hết".

*(Đang nghiêng (B). Cần user/GVHD xác nhận trước khi viết lại Methodology.)*
