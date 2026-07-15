# Strengthened Empirical Study — Design Spec

> **Ngày:** 2026-07-13 · **Nhánh:** main · **Trạng thái:** design (chờ user duyệt trước khi writing-plans).
> **Ngữ cảnh:** Nâng "wow" + rigor cho thesis traffic-RL sau khi Chapter 4 đã sync (Phase 0 xong).
> **Quỹ thời gian:** >1 tháng. **Compute:** container CityFlow (Colima, x86 emulation) — Claude chạy toàn bộ job.

## 1. Mục tiêu & phạm vi

Bổ sung 4 thành phần thực nghiệm, tất cả **feed thẳng vào Chapter 4** và mạnh hoá luận điểm cốt lõi
("DQN học lại chính sách kiểu Max-Pressure từ số đếm local; đường trung thực để vượt MP là
coordination + robustness"):

| # | Thành phần | Vai trò | Compute |
|---|---|---|---|
| C1 | **Multi-seed + CI** | Biến điểm số đơn (single-seed) thành claim có khoảng tin cậy (mean±std) | Cao |
| C2 | **Agreement analysis (DQN↔MP)** | Bằng chứng định lượng "DQN ≈ MP" | Thấp |
| C3 | **Robustness** (nhiễu / sự cố / dịch demand) | Đường trung thực để "thắng heuristic" | Vừa |
| C4 | **Neighbor-coord state (beat-MP)** | Thử THẬT vượt MP bằng quan sát láng giềng (CoLight-lite) | Cao |

**Nguyên tắc bất biến:** mọi thứ **config/env-driven, OFF mặc định** → `results/` và
`results/references/` đã đóng băng **không bị đụng**. Output mới đi vào thư mục riêng.

**Demo (Phase 2)** là sub-project riêng (đã có brainstorm `2026-07-03-...`), **spec tách biệt** — không nằm trong tài liệu này.

## 2. Kiến trúc chung

- **Host-first:** toàn bộ *logic* (perturbation, agreement, neighbor-encoder, aggregation) viết +
  unit-test trên host (không cần container). Chỉ *sinh kết quả* mới chạy container.
- **Tái dùng pattern hiện có:** `scripts/exp_*.sh`, `run_comparison.py`, `build_presentation.py`,
  env-var overrides trong `train_dqn.py`.
- **Cô lập output:** `results/<scen>/robustness/`, `results/multiseed/`, `results/<scen>/agreement/`,
  `results/<scen>/exp_neighbor/`. Không ghi đè baseline đóng băng.

## 3. Thiết kế từng thành phần

### C1 — Multi-seed + Confidence Interval
- **Module:** `src/traffic_rl/eval/multiseed.py` — chạy K seed, gom `mean ± std` + 95% CI.
- **Hai tầng (theo ngân sách compute):**
  - **Tầng 1 (bắt buộc):** eval-seed CI cho **cả 4 controller** trên 4 scenario — sinh lại flow với
    K seed (`flow_gen`, K=5), eval các net đã có → bắt variance *hiện thực hoá demand*. Rẻ (eval-only).
  - **Tầng 2 (headline):** train-seed CI cho **DQN** trên `haichau_rush` + 1 scenario nữa — train K net
    (K seed) → bắt variance *huấn luyện*. Đắt hơn.
- **Output:** bảng mean±std thay điểm số trong Chapter 4; biểu đồ error-bar.
- **Interface:** `run_multiseed(scenario, controllers, seeds, retrain=False) -> {ctrl: {mean, std, ci}}`.

### C2 — Agreement analysis (DQN ↔ Max-Pressure)
- **Module:** `src/traffic_rl/eval/agreement.py`.
- **Cách làm:** trong 1 lượt DQN greedy-eval, tại mỗi quyết định tính luôn `argmax` pha mà
  Max-Pressure *sẽ* chọn từ **cùng state** (MP là hàm thuần của queue hiện tại — không áp dụng, chỉ so).
  Log `(dqn_phase, mp_phase)` theo nút & thời gian.
- **Metrics:** % agreement tổng; theo scenario; theo lớp số-pha (4/6/8-phase); agreement theo thời gian;
  tóm tắt phân kỳ (khi khác nhau, mỗi bên chọn gì).
- **Compute:** 1 lượt eval / scenario (rẻ). **Output:** bảng + heatmap/plot agreement.

### C3 — Robustness study
- **Module:** `src/traffic_rl/sim/perturbations.py` + hook trong env/eval (config-driven, off mặc định).
- **(a) Nhiễu quan sát:** thêm nhiễu Gaussian `N(0, σ)` hoặc dropout Bernoulli lên per-lane queue
  **trước khi** agent/MP nhìn thấy (tại biên encode observation). MP đọc pressure sai → suy giảm;
  Fixed-Time/Random bỏ qua obs → miễn nhiễm (đúng chủ đích). Sweep σ ∈ {0, 0.1, 0.2, 0.4, 0.8}·scale.
  → Kỳ vọng: **DQN suy giảm chậm hơn MP** (chính sách học được bền hơn công thức đọc-chính-xác).
- **(b) Sự cố:** giữa episode (step T), **ép 1 nút trục chính giữ pha bất lợi** trong 1 cửa sổ
  (mô phỏng đèn hỏng / tắc), rồi thả — đo phục hồi. *Khả thi vì ta điều khiển pha trực tiếp.*
  **Fallback nếu vướng:** "demand shock" (bơm 1 cụm xe trên 1 corridor giữa episode) — chắc chắn khả thi qua flow.
- **(c) Dịch demand:** eval controller (train/tune ở regime X) trên flow regime Y — đo tổng quát hoá.
  Không cần code mới ngoài trỏ ckpt-X vào flow-Y.
- **Output:** đường "suy giảm theo mức nhiễu" (DQN vs MP vs Fixed); bảng phục hồi sau sự cố;
  ma trận dịch-demand. → section Robustness mới trong Chapter 4.

### C4 — Neighbor-coordinated state (thử thật vượt MP)
- **Module:** mở rộng `src/traffic_rl/sim/encoder.py` với `state_mode="neighbor"`.
- **Cách làm:** bổ sung vào observation mỗi agent các đặc trưng **mean-pool queue/pressure của nút
  thượng nguồn liền kề** (qua đồ thị roadnet: `incoming_lanes`/`next_roads`). Cho agent *dự đoán xe
  sắp tới* — điểm mù của MP. Đây là CoLight-lite (chỉ mean-pool, **không** full attention — YAGNI).
- **Train:** dùng pipeline hiện có với `STATE_MODE=neighbor` (giống cách ATS đã làm), trên các scenario.
- **Kỳ vọng trung thực:** có thể vượt hoặc không vượt MP; **cả hai kết quả đều báo cáo được**
  (vượt = contribution; không vượt = củng cố phân tích "cần coordination sâu hơn").
- **Output:** thêm cột vào bảng ablation Chapter 4 + phân tích.

## 4. Testing (host, không container)
- Perturbation: nhiễu seed-reproducible; off mặc định không đổi observation.
- Agreement: logger đúng trên state đồ chơi (biết trước MP chọn gì).
- Neighbor encoder: đúng shape + pooling đúng trên roadnet nhỏ.
- Multiseed: toán mean/std/CI đúng.
- Regression: hash `results/references/` trước/sau → xác nhận **không đụng** baseline.

## 5. Compute plan (Claude chạy)
> **Sequencing quan trọng (advisor):** số DQN trong Chapter 4 hiện là **provisional single-seed**
> (+30.8% / +21.0% / +9.0% / +6.5%). **C1 multi-seed chạy TRƯỚC** vì nó quyết định các số này có
> dịch không / std rộng không. Chưa gọi Chapter 4 là "final" cho tới khi headline nằm trong CI của nó.

Thứ tự chạy nền + Monitor:
1. **C1 multi-seed CI** (tầng-1 eval-seed cho cả 4 controller; rồi tầng-2 train-seed cho DQN headline) — **gate số Chapter 4** →
2. **C2 agreement** (rẻ, chạy song song được) →
3. **C3 robustness** (nhiễu/dịch trước, sự cố sau) →
4. **C4 neighbor train** (đắt nhất; thêm dòng vào ablation).

Sau C1: cập nhật Chapter 4 sang **mean±std / error-bar**; nếu mean dịch, sửa số + narrative.

## 6. Non-goals (YAGNI)
Không PPO/actor-critic; không full-attention CoLight (chỉ mean-pool); không đụng GUI (Phase 2);
không federated/transfer; không calibrate demand từ đếm xe thật (giữ nguyên limitation đã nêu).

## 7. Success criteria
- Mỗi thành phần cho ≥1 bảng/hình mạnh hoá Chapter 4.
- Toàn bộ host unit-test pass; baseline đóng băng **không đổi** (verified qua hash).
- Chapter 4 có: khoảng tin cậy, agreement %, section robustness, dòng neighbor trong ablation.
