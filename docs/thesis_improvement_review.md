# Rà soát toàn diện & danh sách cải tiến — Traffic-RL (2026-07-19)

> **Nguồn dữ liệu:** audit trực tiếp repo này (paper LaTeX, `src/`, `scripts/`, `results/`, `tests/`, docs) + research văn liệu TSC-RL 2018–2026 qua Perplexity, **mọi citation đều có link đã kiểm tra**. Không có số liệu nào trong tài liệu này được bịa ra: số nội bộ lấy từ `docs/scenario_regimes.md` / `docs/ablation_honest_plan.md` / `results/multiseed/*.json`; claim bên ngoài đều kèm link.
>
> Tài liệu này **kế tiếp** `thesis_upgrade_roadmap.md` (2026-07-12): Phase 0 (đồng bộ Chapter 4) đã xong ngày 2026-07-15; dưới đây là những điểm **còn lại hoặc mới phát hiện**.

---

## 0. TL;DR — bảng ưu tiên

| # | Việc | Nhóm | Ưu tiên | Công sức | Vì sao |
|---|------|------|:-------:|:--------:|--------|
| ~~A1~~ | ~~Sửa công thức CI (z→t, ddof 0→1) + regen bảng~~ **✅ DONE 2026-07-22** | Thống kê | ~~P0~~ | — | CI giờ rộng đúng chuẩn (Student-t df=4); **không lật kết luận nào** — cả 4 scenario giữ dấu (calib vẫn dương, xem §A1) |
| C1–C3 | Gỡ nốt claim stale trong Ch1/Ch3 (actuated/adaptive, SUMO env, avg travel time, contributions 1–3) | Paper | **P0** | Thấp | Rủi ro tín nhiệm khi hội đồng đối chiếu Ch1 với Ch4 |
| C7 | Xác nhận metadata trang bìa (tên tác giả, bậc học) | Paper | **P0** | Rất thấp | Trang bìa đang ghi thông tin không khớp đồ án |
| ~~B1~~ | ~~Chạy agreement analysis~~ **✅ DONE 2026-07-23** | Thí nghiệm | ~~P1~~ | — | Kết quả: agree ≈25% (≈chance) → DQN đạt hiệu năng cỡ MP bằng **chính sách khác**, không bắt chước. Đã vào Ch4 sec:analysis |
| ~~B2~~ | ~~Hoàn tất ma trận robustness~~ **✅ DONE 2026-07-23** (incident mode + shift + calib noise) | Thí nghiệm | ~~P1~~ | — | Kết quả: incident degrade 1–4% (DQN nhỉnh hơn → **không có lợi thế robustness**); shift bất đối xứng (rush→calib free, calib→rush +45.8%). Đã vào Ch4 sec:robustness (tab:incident, tab:shift) |
| C5 | Thay 4 hình placeholder bằng hình thật | Paper | **P1** | Thấp | Hiện render ra ô trống trong PDF |
| C6 + E2 | Dọn bib (dup key) + thêm citation 2024–2026 (danh sách §7) | Paper | **P1** | Thấp | Bib đang có 0 ref 2025–2026, 42 entry thừa, 1 key trùng |
| D1 | Cho phép tái lập từ fresh clone (data/ đang bị gitignore toàn bộ) | Tái lập | **P2** | Trung bình | Examiner chỉ tái lập được bảng/hình, không tái lập được thí nghiệm |
| D2–D5 | requirements legacy, CI GitHub Actions, dashboard/docs lệch số | Kỹ thuật | **P2** | Thấp | Vệ sinh, giảm câu hỏi khó khi phản biện |
| B3 | 1 run neighbor-encoder (code + test có sẵn) | Thí nghiệm | **P3** | Trung bình | Biến future-work thành preliminary result |
| E4 | Chuẩn bị defense: Q&A dự kiến, video fallback cho demo 3D | Defense | **P3** | Thấp | Giảm rủi ro ngày bảo vệ |

---

## 1. Nhóm A — Tính đúng đắn thống kê (P0)

### A1. Confidence interval đang hẹp hơn chuẩn ~58% — ảnh hưởng kết luận

**Hiện trạng** (`src/traffic_rl/eval/multiseed.py:23-24`, lặp lại trong `emit_ch4_tables.py`, `aggregate_multiseed.py`, `report/strengthened.py`):

```python
std = float(a.std())                       # ddof=0 (population)
ci95 = float(1.96 * std / math.sqrt(n))    # normal-approx
```

Với **n = 5 seeds**, chuẩn thống kê cho CI của mean là **Student-t** với df = 4 và **sample std (ddof=1)**:

- Hệ số t₀.₉₇₅,₄ = 2.776 (thay vì z = 1.96) → rộng thêm ×1.416
- ddof=1 thay vì ddof=0 → std lớn thêm ×√(5/4) = ×1.118
- **Tổng cộng: CI đúng rộng hơn CI đang in ra ×1.583**

> ### ✅ ĐÃ THỰC HIỆN 2026-07-22 (TDD, 83/83 host test pass; regen từ per-seed JSON, không chạy lại sim)
> Sửa `summary_stats` → Student-t (df=n−1) + sample std (ddof=1); regen 4 aggregate + `tab:waiting`/`tab:queue`/`tab:ablation` + 4 PNG; thêm câu Student-t vào Ch4 Evaluation Metrics; mềm câu "dueling CI trên MP".

**Tác động THỰC TẾ sau regen** (số đo từ chính scripts, không phải ước lượng tay):

| Scenario | CI cũ (veh-h) | CI mới (veh-h) | Reduction% ± CI%pt → khoảng | Kết luận |
|----------|--------:|--------:|:---|----------|
| `haichau_rush` | ± 2.5 | **± 3.9** | +37.1% ± 2.2 → **[34.9, 39.2]** | ✅ dương rõ — headline an toàn |
| `haichau_calib` | ± 18.3 | **± 28.9** | +21.6% ± 8.5 → **[13.1, 30.1]** | ✅ **vẫn dương rõ, KHÔNG cắt 0** |
| `haichau_peak` | ± 22.3 | **± 35.3** | +5.1% ± 2.9 → **[2.2, 8.1]** | ✅ vẫn dương (sát 0 nhưng không cắt) |
| `haichau` (dense) | ± 7.9 | **± 12.4** | −39.9% ± 1.4 → **[−41.3, −38.5]** | ✅ âm rõ — kết quả trung thực giữ nguyên |

> **⚠️ SỬA LỖI trong bản nháp trước của chính doc này:** bản đầu ghi "calib CI → ±29.0, cắt 0, mất ý nghĩa".
> Đó là **nhầm đơn vị của tôi**: ±18.3/±28.9 là CI *tuyệt đối theo veh-h* trên giá trị DQN (266.3 veh-h),
> KHÔNG phải CI của % reduction. Fixed-Time là deterministic (không CI), nên CI của *reduction%* =
> ci(DQN)/Fixed = 28.9/339.6 = **8.5 %-point**, cho khoảng [13.1, 30.1] — **không cắt 0**. Bài học: chạy
> số thật thay vì nhân tay. **Kết cục tốt hơn:** việc sửa CI *không lật* kết luận nào — cả 4 scenario giữ dấu.

Ablation: dueling queue 416.8 ± 20.0 → **± 31.7** (Student-t), lower bound 385.1 < MP 388.2. Nên câu "toàn bộ
CI dueling trên MP → bulletproof" đã được mềm thành: *mean 416.8 rõ trên (tệ hơn) MP, chỉ đuôi dưới của CI
chạm MP → "không variant nào thắng MP" vẫn đứng, chỉ bỏ chữ "bulletproof"*. Main-config rush 407.7 ± 8.8 →
**± 14.0**, lower bound 393.6 vẫn > MP 388.2 → "DQN không vượt MP ở rush" vững.

**Vì sao đáng tin:** đây chính là loại lỗi mà văn liệu đánh giá RL cảnh báo nhiều nhất — so sánh bằng point estimate hoặc CI sai với số seed nhỏ:
- Henderson et al., *Deep Reinforcement Learning that Matters*, AAAI 2018 — [arXiv:1709.06560](https://arxiv.org/abs/1709.06560)
- Agarwal et al., *Deep RL at the Edge of the Statistical Precipice*, NeurIPS 2021 (Outstanding Paper) — [arXiv:2108.13264](https://arxiv.org/abs/2108.13264) (khuyến nghị interval estimates + IQM; thư viện `rliable`)
- Colas, Sigaud & Oudeyer, *How Many Random Seeds? Statistical Power Analysis in Deep RL Experiments* — [arXiv:1806.08295](https://arxiv.org/abs/1806.08295) (t-test/bootstrap với n seed nhỏ)

### A2. Nâng cấp nhẹ (tuỳ chọn, sau A1)

- **Bootstrap percentile CI** trên 5 giá trị per-seed làm sanity-check song song với t-CI (~20 dòng NumPy).
- **Báo per-seed values** trong appendix (bảng 5 dòng × 4 scenario) — minh bạch tuyệt đối, hội đồng tự kiểm tra được.
- Nếu muốn theo chuẩn Agarwal et al.: báo thêm **IQM** bên cạnh mean. Không bắt buộc với K=5.
- Baseline (Fixed-Time/MP) là deterministic replay → std=0 là đúng bản chất; ghi 1 câu giải thích trong caption để tránh bị hỏi "sao baseline không có CI".

---

## 2. Nhóm B — Thí nghiệm đã code sẵn nhưng chưa chạy / chưa trọn (P1)

Audit code cho thấy 3 mảng đã có code + unit test nhưng **chưa có artifact kết quả nào trên đĩa** — tức là công sức đã bỏ ra mà chưa thu hoạch:

### B1. Agreement analysis — ✅ ĐÃ CHẠY 2026-07-23

> **Kết quả (khác dự đoán ban đầu):** agree rate = **25.1% rush / 26.5% calib**, ≈ mức ngẫu nhiên;
> chỉ 6–8/53 nút đồng thuận ≥70%. Tức nhánh "if low → đạt hiệu năng tương đương bằng chính sách khác"
> là đúng: **DQN KHÔNG bắt chước Max-Pressure**, đạt hiệu năng cỡ MP bằng chính sách khác hẳn. Đã viết
> vào Ch4 sec:analysis ("The learned policy is not an imitation of Max-Pressure"). Claim hiệu-năng-parity
> của paper không bị ảnh hưởng. Số liệu: `results/<area>/agreement/agreement.json`; tổng hợp:
> `scripts/summarize_strengthen.py`.

*(Ghi chú thiết kế ban đầu, giữ lại làm bối cảnh:)*

`src/traffic_rl/eval/agreement.py` + `scripts/run_agreement.py` hoàn chỉnh, có test, nhưng không tồn tại `results/*/agreement/` nào. Đây là **bằng chứng định lượng trực tiếp** cho luận điểm trung tâm của thesis ("DQN học lại chính sách cỡ Max-Pressure từ số đếm local thô"): đo % số quyết định trùng giữa DQN và MP trên cùng trajectory.

- Chạy trên `rush` (headline) + 1 regime nữa; đưa con số vào Ch4 §analysis và slide defense.
- Nếu agreement cao (ví dụ >70%): "DQN hội tụ về hành vi MP mà không cần công thức pressure" — câu chuyện wow có số đo. Nếu thấp: cũng thú vị — "đạt hiệu năng tương đương bằng chính sách *khác* MP" — either way đều có nội dung để viết.

### B2. Ma trận robustness — ✅ ĐÃ HOÀN TẤT 2026-07-23

> **Đã làm:** thêm `pick_incident` (`sim/perturbations.py`) + mode `incident` vào `run_robustness.py`
> (TDD, 2 test); chạy detached batch `scripts/run_strengthen_batch.sh` cho incident (rush+calib),
> shift (2 chiều), calib noise (rush noise đã có). **Kết quả:**
> - **Incident** (nút bận nhất kẹt green, 1/3 giữa horizon): mọi controller degrade 1–4%; DQN nhỉnh
>   hơn MP/Fixed (rush +4.2% vs +2.7%/+1.7%). → **không có lợi thế robustness** (đồng nhất với noise).
> - **Demand shift bất đối xứng:** rush→calib gần miễn phí (944.6 vs native 958.6, −1.5%); calib→rush
>   kém (594.3 vs native 407.7, +45.8%). Train ở regime nhẹ generalize tốt hơn.
> - Vào Ch4 sec:robustness (đổi tên "Robustness and Generalization" + tab:incident + tab:shift).
> **Lưu ý trung thực:** đây đóng lại giả thuyết "thắng MP bằng robustness" của roadmap — nhưng đóng
> một cách thành thật (negative result), đúng tinh thần đồ án.

*(Bảng kế hoạch ban đầu, giữ lại làm bối cảnh:)*

| Nhiễu | Engine hỗ trợ? | Runner? | Kết quả trên đĩa |
|-------|:---:|:---:|---|
| Sensor noise | ✅ `sim/perturbations.py` | ✅ mode `noise` | ✅ nhưng chỉ `rush` + `calib` (thiếu 2 scenario) |
| Demand shift | ✅ | ✅ mode `shift` | ❌ chưa chạy bao giờ |
| Incident / lane-closure | ✅ `PerturbedEngine(incident=…)` | ❌ `run_robustness.py` **chưa có mode `incident`** | ❌ |

Việc cần làm: thêm nhánh `incident` vào `run_robustness.py` (engine đã hỗ trợ — chỉ là wiring), chạy đủ lưới {noise, shift, incident} × {rush, calib} (2 scenario chính là đủ, không cần cả 4), cập nhật `plot_robustness.py` + Ch4. Đây là **con đường trung thực duy nhất để "thắng" MP** mà roadmap đã xác định: MP cần đo pressure chính xác, RL có thể suy giảm "dịu" hơn khi cảm biến nhiễu/sự cố.

Văn liệu định vị (đưa vào related work + so sánh thiết kế thí nghiệm):
- Rodrigues & Azevedo, *Towards Robust Deep Reinforcement Learning for Traffic Signal Control: Demand Surges, Incidents and Sensor Failures*, IEEE ITSC 2019 — [arXiv:1904.08353](https://arxiv.org/abs/1904.08353). **Đúng taxonomy 3 nhiễu mà repo đang làm** — cite để cho thấy thiết kế robustness có tiền lệ học thuật.
- *Robustness of RL-Based Traffic Signal Control under Incidents: A Comparative Study* (T-REX benchmark), 2025 — [arXiv:2506.13836](https://arxiv.org/abs/2506.13836). Chứng minh chủ đề này đang **nóng đúng năm 2025** — thesis đi đúng hướng thời sự.

### B3. Neighbor encoder — 1 run để nâng cấp future-work (P3)

`encoder.py` mode `neighbor` (CoLight-lite, mean-pooled upstream features) + `roadnet.upstream_neighbors` + `scripts/exp_neighbor.sh` đều sẵn, có test, chưa chạy. Ch4 hiện *dự đoán* "downstream-aware state là chìa khoá vượt MP" — 1 run neighbor trên `rush` sẽ biến dự đoán thành **preliminary evidence** (dù kết quả âm cũng đáng báo — repo có truyền thống báo kết quả âm). Nếu không đủ thời gian: ghi rõ trong paper "implementation available, evaluation left as future work" — vẫn hơn là future work suông.

---

## 3. Nhóm C — Paper LaTeX: những chỗ còn lệch sau Phase 0 (P0/P1)

Chapter 4 đã đồng bộ tốt (audit xác nhận: CityFlow, 53 nút, multi-seed CI, +37.1%, MP không bị vượt, limitations đầy đủ). Còn sót:

### C1. Chapter 1 — 3 chỗ stale (P0, sửa vài phút)
- `trafic_rf.tex:168` — objective 3 vẫn hứa benchmark với "**actuated, and conventional adaptive control methods**" (chưa bao giờ build). Sửa thành "tuned fixed-time and Max-Pressure baselines".
- `trafic_rf.tex:171` (và các chỗ tương tự ~L142, L296, L536) — "**average travel time**" vẫn được nêu như outcome chính; headline metric thật là **cumulative waiting time (veh-hours)** (lý do: xem `waiting_time_analysis.md`). Đồng bộ hết về waiting time.
- Research question L161 nêu "robust to real-world variability and noise" — hợp lệ *nếu* B2 hoàn tất; nếu không, hạ tông.

### C2. Contributions 1–3 overclaim (P0)
`trafic_rf.tex:179-186`: contribution 1 ("hierarchical, communication-enabled RL structure"), 2 ("reward tích hợp queue + delay + throughput; state có contextual data từ nút lân cận"), 3 ("hybrid model-free + rule-based") mô tả những thứ **chưa build hoặc chỉ build một phần** — trong khi contributions 4–5 (L188-192) đã viết rất chuẩn theo kết quả thật. Cách sửa ít đau nhất: viết lại 1–3 theo khung "**proposed framework**" với câu demarcation rõ ("contributions 1–3 constitute the proposed design space; the validated subset is described in contributions 4–5"), hoặc gộp 1–3 thành 1 contribution "framework design" duy nhất. Nhất quán với đoạn "Scope: validated vs proposed" đã có ở L267.

### C3. Chapter 3 — 2 chỗ (P1)
- `trafic_rf.tex:225` — Environment Layer nói "simulated using a microscopic simulator **such as SUMO**" → đổi thành CityFlow (SUMO chỉ dùng convert network — L323 đã viết đúng, lấy câu đó làm chuẩn).
- `trafic_rf.tex:451` — "For actuated-style baselines, extension actions … are supported" → xoá hoặc chuyển future work.

### C4. Appendix A stale hoàn toàn (P1)
`trafic_rf.tex:558-559` mô tả "canonical **SUMO** scenarios … synthetic **3×3 and 4×4 grids** … `.net.xml`, `.rou.xml`, `.sumocfg`" — di sản của prototype đã bỏ, mâu thuẫn trực tiếp với Ch4. Thay bằng appendix tái lập thật: pipeline OSM→SUMO→CityFlow, 4 file flow, config seeds, lệnh chạy (nội dung lấy từ README — đã viết sẵn rồi, chỉ cần chuyển vào).

### C5. 4 hình đang render placeholder box (P1)
Các `\IfFileExists` fallback đang kích hoạt vì file không tồn tại:
- `fig:framework` (L207-217, thiếu `traffic_visualization.png`) → vẽ sơ đồ param-shared DQN + CityFlow loop thật.
- `fig:sumo_gui` (L377-386, thiếu ảnh; caption còn ghi "SUMO GUI") → thay bằng screenshot demo 3D/2D CityFlow của chính repo (đẹp hơn nhiều) + đổi caption.
- `fig:phases` (L388-411, thiếu 2 ảnh phase) → xuất phase diagram thật từ roadnet Hải Châu.
Bonus: thêm **bản đồ mạng Hải Châu 53 nút** (từ dữ liệu OSM đã có) — hình "đắt" nhất cho cả paper lẫn slide mà chưa có.

### C6. Bibliography (P1)
- **Bug compile:** key `Wei_2019` bị định nghĩa 2 lần (PressLight + CoLight, `references.bib:54,56`) — BibTeX sẽ chỉ giữ 1 + warning. Đổi key.
- **Trùng bản ghi cùng paper:** PressLight ×3 (`PressLight_2019`, `Wei_2019`, `Lite_2021` — entry `Lite_2021` sai cả tên lẫn năm), CoLight ×3, Varaiya Max-Pressure ×2 (`MaxPressure_2013` + `Varaiya_2013`). Hợp nhất, giữ 1 key/paper.
- 42/115 entry **không được cite** — cân nhắc cite (IntelliLight `Wei_2018` rất nên cite trong related work) hoặc xoá bớt.
- **0 citation năm 2025–2026** trong khi bảo vệ giữa 2026 → thêm các ref ở §7 dưới đây.

### C7. Metadata trang bìa (P0 — cần bạn xác nhận)
Audit phát hiện title page (`trafic_rf.tex:55-58`) ghi tác giả "**Dinh Quoc Toan**", bậc "**Master of Software Engineering**", năm **2025**. Nếu đây là template mượn thì phải thay đúng tên tác giả đồ án / bậc học / năm bảo vệ — chi tiết nhỏ nhưng là thứ hội đồng nhìn thấy **đầu tiên**.

### C8. Vệ sinh nhỏ
5 dòng `---` markdown sót trong `trafic_rf.tex` (L299, L312, L328, L343, L413) sẽ render thành gạch ngang lỗi trong PDF — xoá hoặc thay `\medskip\hrule\medskip`.

---

## 4. Nhóm D — Tái lập & kỹ thuật (P2)

- **D1. Fresh clone không chạy được simulation:** `data/` bị gitignore **toàn bộ** (0 file tracked) — mọi entry point simulator (train/eval/robustness/demo) đều fail cho tới khi tự regen OSM→SUMO→CityFlow (cần SUMO + tải OSM). Trong khi đó 489 file kết quả (JSON/npz) *có* được track nên phần bảng/hình tái lập tốt. Đề xuất: commit `roadnet_*.json` + 4 file `flow_*.json` của các scenario chính (hoặc GitHub Release artifact + target `make data`), để examiner chạy được ít nhất 1 lệnh eval end-to-end.
- **D2. `requirements.txt` gây hiểu nhầm nghiêm trọng:** pin torch 2.0.1, stable-baselines3, gymnasium, scipy, tensorboard — **không cái nào được import** (grep toàn repo xác nhận). Nguy hiểm ở chỗ: hội đồng đọc requirements sẽ nghĩ DQN xây bằng torch/SB3, **phá luận điểm "from-scratch NumPy DQN"**. Dọn về đúng runtime thật (numpy+pyyaml container; streamlit/pandas/matplotlib host — đã có `requirements-host.txt`).
- **D3. Chưa có CI:** không có `.github/`. 82/83 pytest chạy được trên host không cần container (FakeEngine + lazy import đã thiết kế sẵn cho việc này) — 1 file workflow ~15 dòng là có badge "tests passing" cho README.
- **D4. Lệch số nhỏ:** README ghi "33 test files" (thực tế 25 file / 83 test); comment trong `configs/training.yaml` nói "40 episodes, epsilon_decay 1800" nhưng giá trị thật `episodes: 60`, `epsilon_decay_steps: 3000`; 2 test JS (`node --test`) không nằm trong `make test`.
- **D5. Docs/dashboard lệch kết quả cuối:** `dashboard/app.py:24` liệt kê scenario `["haichau","haichau_peak","full","subarea"]` — **thiếu `haichau_rush` (headline!) và `haichau_calib`**; `docs/RESULTS.md` vẫn mô tả `full`/`subarea`; `docs/model_ablation.md` còn số single-seed cũ (+6.5%) mà không có banner SUPERSEDED (các doc khác có). Nếu demo dashboard ngày bảo vệ mà thiếu đúng scenario headline thì rất phí.

---

## 5. Nhóm E — Nội dung nghiên cứu nên bổ sung vào paper

### E1. Định vị "DQN ≈ MP" trong văn liệu benchmark — biến điểm yếu thành điểm mạnh

Phát hiện trung tâm của thesis (không variant DQN local nào vượt Max-Pressure) **khớp với văn liệu benchmark độc lập** — đây là chỗ nên cite mạnh để cho thấy kết quả không phải "thất bại cá nhân" mà là hiện tượng có hệ thống:

- **Ault & Sharon, NeurIPS 2021 (Datasets & Benchmarks)** — RESCO benchmark: so sánh chuẩn hoá các RL controller với baseline cổ điển trên scenario thực tế; Max-Pressure là baseline mạnh trong suite. [Paper](https://people.engr.tamu.edu/guni/papers/NeurIPS-signals.pdf) · [Proceedings](https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/hash/f0935e4cd5920aa6c7c996a5ee53a70f-Abstract-round1.html)
- **Varaiya 2013** — nền tảng lý thuyết: MP là throughput-optimal với thông tin queue local → giải thích *vì sao* RL local-observation khó vượt. (Đã có trong bib: `MaxPressure_2013`; dùng làm xương sống cho luận điểm "MP-ceiling".)
- **Wei, Zheng, Gayah & Li**, *Recent Advances in RL for Traffic Signal Control: A Survey of Models and Evaluation*, SIGKDD Explorations 22(2) — survey chuẩn về đánh giá TSC-RL. [PDF](https://www.kdd.org/exploration_files/5._CR._30._Recent_Advances_in_Reinforcement_Learning_for_Traffic_Signal_Control_A_Survey_of_Models_and_Evaluation-2.pdf) · [arXiv:1904.08117](https://arxiv.org/abs/1904.08117)

### E2. Related work 2024–2026 (bib đang có 0 ref sau 2024)

| Hướng | Paper | Link | Dùng ở đâu trong thesis |
|-------|-------|------|------------------------|
| Survey mới nhất | *Advances in RL for traffic signal control: a review of recent progress*, Intelligent Transportation Infrastructure (OUP), 2025 | [DOI 10.1093/iti/liaf009](https://academic.oup.com/iti/article/doi/10.1093/iti/liaf009/8125227) | Ch2 mở đầu — chứng tỏ lit-review cập nhật |
| Robustness benchmark | T-REX: *Robustness of RL-Based TSC under Incidents*, 2025 | [arXiv:2506.13836](https://arxiv.org/abs/2506.13836) | Ch2 + động lực cho robustness study (B2) |
| Generalization cross-scenario | GESA: *A GEneral Scenario-Agnostic RL for TSC* (Jiang et al., IEEE T-ITS 2024) | [Trang tác giả](https://bonaldli.github.io/publication/gesa-tits24/) · [PDF](https://ceur-ws.org/Vol-3827/short1.pdf) | Ch2 + future work (demand-shift generalization) |
| Generalization đa cấu trúc nút | UniTSA: *A Universal RL Framework for V2X TSC* (Wang, Xiong, Kan, Xu, Pun; IEEE TVT 2024) | [arXiv:2312.05090](https://arxiv.org/abs/2312.05090) | Ch2 — đối chiếu param-shared across heterogeneous intersections (nội dung rất gần thiết kế shared-DQN của thesis) |
| LLM-based TSC | LLMLight: *Large Language Models as Traffic Signal Control Agents* (Lai et al., KDD 2025) | [arXiv:2312.16044](https://arxiv.org/abs/2312.16044) | Ch2 1 câu "hướng mới nổi" + future work |
| Deployment thực tế | *First steps towards real-world traffic signal control optimisation by RL*, Journal of Simulation 18(6):957-972, 2024 | [DOI 10.1080/17477778.2024.2364715](https://www.tandfonline.com/doi/full/10.1080/17477778.2024.2364715) | Ch5 Discussion — khoảng cách sim-to-real, action definition an toàn |
| Deployment / benchmark thực tế | Müller et al., *Towards Real-World Deployment of RL for TSC*, 2021 + LemgoRL | [arXiv:2103.16223](https://arxiv.org/abs/2103.16223) | Ch5 — safety constraints khi triển khai |
| Reality gap tổng quan | Chen et al., *The Real Deal: A Review of Challenges & Opportunities in Moving RL-Based TSC Towards Reality*, 2022 | [arXiv:2206.11996](https://arxiv.org/abs/2206.11996) | Ch5 + Limitations |
| Robustness taxonomy gốc | Rodrigues & Azevedo, ITSC 2019 | [arXiv:1904.08353](https://arxiv.org/abs/1904.08353) | Ch4 robustness (B2) |
| Đánh giá thống kê RL | Henderson 2018 / Agarwal 2021 / Colas 2018 (link ở §1) | — | Ch4 methodology — biện minh multi-seed + t-CI |

### E3. Limitation xe máy — cite cho chuẩn

Ch4 limitations đã thừa nhận CityFlow lane-based chỉ *xấp xỉ* hành vi xe máy (không có lane-filtering thật). Nên cite để cho thấy đây là hạn chế **của cả simulator ecosystem**, không riêng thesis:
- SUMO **Sublane Model** (tài liệu chính thức — mô hình chuẩn để mô phỏng 2-wheeler chạy song song trong 1 làn): https://sumo.dlr.de/docs/Simulation/SublaneModel.html
- *Powered Two-Wheelers Extensive Simulation Study in SUMO* (EURECOM) — [PDF](https://www.eurecom.fr/en/publication/5891/download/comsys-publi-5891.pdf)
- Câu khuyến nghị cho paper: "Modelling motorcycle-dominated flow requires sub-lane lateral dynamics (cf. SUMO's sublane model); CityFlow's lane-discipline assumption therefore under-represents filtering behaviour, which we mitigate by short-narrow vehicle templates and flag as a limitation."

### E4. Chuẩn bị defense (không thuộc paper nhưng quyết định điểm số)

1. **Chạy trước và quay video** demo 3D (branch `demo/replay-3d` — hiện **chưa merge vào main**; caveat "per-lane bar chưa đối chiếu viewer gốc" trong `demo_replay_3d.md` cần đóng trước khi demo live).
2. **1 trang cheat-sheet số liệu**: 53 nút · 4 regime · +37.1%±4.0 rush · −39.9% dense (trung thực) · MP không bị vượt & lý do lý thuyết · agreement % (sau B1) · robustness delta (sau B2).
3. **Q&A dự kiến** (mỗi câu đã có sẵn tài liệu trả lời trong repo): "Sao không thắng Max-Pressure?" (→ Varaiya + RESCO + ablation); "Sao dùng CityFlow không phải SUMO?" (→ tốc độ multi-agent, SUMO dùng convert; cite CityFlow WWW'19 đã có trong bib); "Xe máy mô phỏng thế nào?" (→ E3); "5 seeds đủ chưa?" (→ A1: t-CI + Colas 2018); "Demand có thật không?" (→ synthetic, calibrated theo saturation spectrum — limitation đã khai).

---

## 6. Đoạn văn gợi ý chèn vào paper (English, ready-to-adapt)

**(a) Ch4, sau khi trình bày kết quả DQN vs MP** — định vị benchmark:

> Our finding that no locally-observing DQN variant surpasses Max-Pressure is consistent with independent benchmark evidence. In the RESCO benchmark, Ault and Sharon [RESCO] report that well-tuned classical controllers remain highly competitive with state-of-the-art deep RL methods across realistic scenarios. This is theoretically grounded: Max-Pressure is provably throughput-optimal given exact local queue information [Varaiya 2013], so a learned controller restricted to the same local observations primarily has room to *match*, not exceed, its decisions. Consequently, we frame the contribution of the learned controller as (i) recovering Max-Pressure-level performance without a hand-crafted pressure formula, and (ii) the potential for greater robustness when sensing degrades — which we evaluate in Section [robustness].

**(b) Ch4, methodology của đánh giá** — biện minh thống kê:

> Following recommendations for statistically sound RL evaluation [Henderson 2018; Agarwal 2021; Colas 2018], we report means with 95% confidence intervals computed with the Student-t distribution (df = K−1) over K = 5 independent training seeds, and we refrain from ranking variants whose intervals overlap. Rule-based baselines are deterministic replays and therefore carry no seed variance.

**(c) Ch2, đoạn kết related work** — cập nhật 2024–2026:

> Recent work has shifted from single-scenario training toward generalisation and deployability: scenario-agnostic co-training (GESA) [Jiang 2024], universal agents across heterogeneous intersections (UniTSA) [Wang 2024], LLM-based controllers (LLMLight) [Lai 2025], and explicit robustness benchmarks under incidents (T-REX) [2025]. In parallel, field-oriented studies stress safe action definitions and the sim-to-real gap [Müller 2021; Meess 2024; Chen 2022]. This thesis contributes to the evaluation-rigour strand of this literature: an honest, multi-seed comparison against a provably strong classical baseline on a real motorcycle-dominated network.

---

## 7. BibTeX bổ sung (đã kiểm tra link; ⚠ = tự đối chiếu tên tác giả đầy đủ trên trang link trước khi dùng)

> **✅ CẬP NHẬT 2026-07-20 — ĐÃ THỰC HIỆN VÀO `references.bib` (bib là nguồn chuẩn, không copy từ đây nữa):**
> - Đã gộp/xoá 4 entry trùng (`Varaiya_2013`≡`MaxPressure_2013` — cùng book chapter Springer; 2×`Wei_2019`; `Lite_2021`; `CoLight_2022`) và sửa các `\cite` tương ứng.
> - Đã wire cite `Mnih_2015` (DQN gốc) + `Wei_2018` (IntelliLight) vào Ch2.
> - Đã thêm 11 entry mới với **tác giả xác minh đầy đủ** (khác bản nháp dưới): Henderson_2018, Agarwal_2021, Colas_2018, Rodrigues_2019, **Nguyen_TREX_2025** (tác giả đầu: Dang Viet Anh Nguyen — DTU, cùng nhóm Rodrigues/Azevedo), Xiao_2025 (survey OUP: Xiao, Lu, Li, Tu, Li), Jiang_GESA_2024 (Jiang, Li, Bai, Zhao), Tran_TSLib_2021 (Tran, Doan, Sartipi — IEEE Big Data 2021), + 3 paper bối cảnh Việt Nam: Minh_2005 (xe máy Hà Nội, JEASTS), Ngoc_2021 (mode share 5 TP Việt Nam, IJITSR 20(1):157–169), NguyenHo_2014 (mô phỏng giao thông Hà Nội, ICCASA/Springer).
> - Đã thêm subsection "Urban Traffic Context in Vietnam" vào Ch2 + câu benchmark/statistics/robustness ở Ch2 và Ch4.
> - Kết quả: **83 references được cite** (trước: 72 render nhưng chỉ ~70 paper distinct), 0 key thiếu, 0 key trùng. GESA/UniTSA/LLMLight/Meess/Müller/Chen còn lại dưới đây vẫn dùng được nếu muốn mở rộng thêm.

```bibtex
@inproceedings{Ault2021RESCO,
  author    = {Ault, James and Sharon, Guni},
  title     = {Reinforcement Learning Benchmarks for Traffic Signal Control},
  booktitle = {NeurIPS Datasets and Benchmarks Track},
  year      = {2021},
  url       = {https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/hash/f0935e4cd5920aa6c7c996a5ee53a70f-Abstract-round1.html}
}

@inproceedings{Henderson2018Matters,
  author    = {Henderson, Peter and Islam, Riashat and Bachman, Philip and Pineau, Joelle and Precup, Doina and Meger, David},
  title     = {Deep Reinforcement Learning that Matters},
  booktitle = {AAAI Conference on Artificial Intelligence},
  year      = {2018},
  url       = {https://arxiv.org/abs/1709.06560}
}

@inproceedings{Agarwal2021Precipice,
  author    = {Agarwal, Rishabh and Schwarzer, Max and Castro, Pablo Samuel and Courville, Aaron and Bellemare, Marc G.},
  title     = {Deep Reinforcement Learning at the Edge of the Statistical Precipice},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS)},
  year      = {2021},
  url       = {https://arxiv.org/abs/2108.13264}
}

@article{Colas2018Seeds,
  author  = {Colas, C{\'e}dric and Sigaud, Olivier and Oudeyer, Pierre-Yves},
  title   = {How Many Random Seeds? Statistical Power Analysis in Deep Reinforcement Learning Experiments},
  journal = {arXiv preprint arXiv:1806.08295},
  year    = {2018},
  url     = {https://arxiv.org/abs/1806.08295}
}

@inproceedings{Rodrigues2019Robust,
  author    = {Rodrigues, Filipe and Azevedo, Carlos Lima},
  title     = {Towards Robust Deep Reinforcement Learning for Traffic Signal Control: Demand Surges, Incidents and Sensor Failures},
  booktitle = {IEEE Intelligent Transportation Systems Conference (ITSC)},
  year      = {2019},
  url       = {https://arxiv.org/abs/1904.08353}
}

% ⚠ điền tên tác giả từ https://arxiv.org/abs/2506.13836
@article{TREX2025Robustness,
  title   = {Robustness of Reinforcement Learning-Based Traffic Signal Control under Incidents: A Comparative Study},
  journal = {arXiv preprint arXiv:2506.13836},
  year    = {2025},
  url     = {https://arxiv.org/abs/2506.13836}
}

@article{Wang2024UniTSA,
  author  = {Wang, Maonan and Xiong, Xi and Kan, Yuheng and Xu, Chengcheng and Pun, Man-On},
  title   = {UniTSA: A Universal Reinforcement Learning Framework for V2X Traffic Signal Control},
  journal = {IEEE Transactions on Vehicular Technology},
  year    = {2024},
  url     = {https://arxiv.org/abs/2312.05090}
}

% ⚠ điền danh sách tác giả đầy đủ từ https://bonaldli.github.io/publication/gesa-tits24/
@article{Jiang2024GESA,
  author  = {Jiang, Haoyuan and others},
  title   = {A General Scenario-Agnostic Reinforcement Learning for Traffic Signal Control},
  journal = {IEEE Transactions on Intelligent Transportation Systems},
  year    = {2024},
  url     = {https://ceur-ws.org/Vol-3827/short1.pdf}
}

% ⚠ điền danh sách tác giả đầy đủ từ https://arxiv.org/abs/2312.16044
@inproceedings{Lai2025LLMLight,
  author    = {Lai, Siqi and others},
  title     = {LLMLight: Large Language Models as Traffic Signal Control Agents},
  booktitle = {ACM SIGKDD Conference on Knowledge Discovery and Data Mining (KDD)},
  year      = {2025},
  url       = {https://arxiv.org/abs/2312.16044}
}

% ⚠ điền tên tác giả từ https://www.tandfonline.com/doi/full/10.1080/17477778.2024.2364715
@article{Meess2024FirstSteps,
  title   = {First steps towards real-world traffic signal control optimisation by reinforcement learning},
  journal = {Journal of Simulation},
  volume  = {18}, number = {6}, pages = {957--972},
  year    = {2024},
  doi     = {10.1080/17477778.2024.2364715}
}

% ⚠ điền tên tác giả từ https://arxiv.org/abs/2103.16223
@inproceedings{Mueller2021Deployment,
  author    = {M{\"u}ller, Arthur and others},
  title     = {Towards Real-World Deployment of Reinforcement Learning for Traffic Signal Control},
  booktitle = {IEEE International Conference on Machine Learning and Applications (ICMLA)},
  year      = {2021},
  url       = {https://arxiv.org/abs/2103.16223}
}

% ⚠ điền tên tác giả từ https://arxiv.org/abs/2206.11996 (nhóm CMU)
@article{Chen2022RealDeal,
  author  = {Chen, Rex and others},
  title   = {The Real Deal: A Review of Challenges and Opportunities in Moving Reinforcement Learning-Based Traffic Signal Control Systems Towards Reality},
  journal = {arXiv preprint arXiv:2206.11996},
  year    = {2022},
  url     = {https://arxiv.org/abs/2206.11996}
}

@article{Wei2021SurveyKDD,
  author  = {Wei, Hua and Zheng, Guanjie and Gayah, Vikash and Li, Zhenhui},
  title   = {Recent Advances in Reinforcement Learning for Traffic Signal Control: A Survey of Models and Evaluation},
  journal = {ACM SIGKDD Explorations Newsletter},
  volume  = {22}, number = {2},
  year    = {2021},
  url     = {https://arxiv.org/abs/1904.08117}
}

% ⚠ điền tác giả từ trang DOI
@article{OUP2025Advances,
  title   = {Advances in reinforcement learning for traffic signal control: a review of recent progress},
  journal = {Intelligent Transportation Infrastructure},
  year    = {2025},
  doi     = {10.1093/iti/liaf009},
  url     = {https://academic.oup.com/iti/article/doi/10.1093/iti/liaf009/8125227}
}
```

---

## 8. Thứ tự thực hiện đề xuất (từ nay tới bảo vệ)

1. **Tuần này:** A1 (sửa CI + regen bảng — *làm trước mọi thứ khác vì đổi số trong paper*), C1–C3 + C7–C8 (sửa text), C6 (dọn bib + paste §7).
2. **Kế tiếp:** B1 (agreement — 1 lệnh), B2 (thêm mode incident + chạy lưới robustness), C4–C5 (appendix + hình).
3. **Sau đó:** D1–D5 (tái lập + vệ sinh), E4 (defense pack), B3 nếu còn thời gian.
4. **Nguyên tắc compute:** không chạy song song nhiều job trong container CityFlow (x86 emulation — bài học đã ghi trong `ablation_honest_plan.md`).

*Sinh bởi phiên rà soát 2026-07-19: 2 audit agent (paper + code) + xác minh citation qua Perplexity. Mọi file:line đều trỏ vào trạng thái repo tại commit `70723b8` (branch `demo/replay-3d`).*
