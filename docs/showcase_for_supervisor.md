# Có gì để show thầy hướng dẫn — kiểm kê & thứ tự trình bày (2026-07-30)

> Audit trực tiếp repo (branch `demo/replay-3d`). Mọi số trong doc này lấy từ
> `results/multiseed/*.json`, `results/*/agreement/agreement.json`, `results/*/robustness/*.json`,
> `docs/scenario_regimes.md`. Test đã chạy lại: **85 pytest pass** (1.5s, không cần container) +
> **14 node test pass**.
>
> **Cập nhật 2026-07-30 — đã làm xong phần setup Tier 1:**
> - Cả 2 trang demo **đã mở thật trên browser** (Playwright), 0 lỗi console.
> - **Sửa lỗi demo:** cả 2 trang trước đó **không hiển thị xe** ở khung nhìn mặc định —
>   nút zoom nhắm tâm hình học của mạng (đo được: **0/454 xe** trong khung), và xe bản 2D
>   là marker pastel trên nền sáng. Nay zoom theo **ô đông xe nhất của replay**, xe đổi màu
>   đậm; bản 3D được thêm nút **🔍 Điểm đông** (trước đó không có nút zoom nào).
> - Toàn bộ 35 file đang dở **đã commit** thành 5 commit theo nhóm.
> - Thêm [demo_quickstart.md](demo_quickstart.md) — 1 trang cầm đi họp (lệnh chạy +
>   cheat-sheet số liệu + kịch bản 15 phút).

---

## TIER 1 — Gửi/demo được NGAY, không cần sửa gì

| # | Hạng mục | Vì sao show được | Đường dẫn |
|---|----------|------------------|-----------|
| 1 | **Demo 3D A/B (deck.gl)** ⭐ | Hai khung 3D khoá chung camera + chung thời điểm, Cố định vs DQN trên mạng Hải Châu **53 nút thật**; đèn vẽ **theo từng làn** (bản 2D không làm được). Chạy offline hoàn toàn, không cần Docker/CityFlow lúc demo. 6/6 test pass. ⚠️ Caveat trung thực (`demo_replay_3d.md:18-20`): thứ tự thanh đèn theo thứ tự làn trong replay, **chưa đối chiếu danh tính trái/phải với viewer gốc** → thông điệp là *"nhánh nào xanh"*, không phải *"làn số mấy"*. Nói trước câu này nếu thầy chỉ vào một thanh. | `frontend/replay_3d.html` · `docs/demo_replay_3d.md` |
| 2 | **Demo 2D A/B + scoreboard** | Bản nhẹ hơn, có **đổi kịch bản trực tiếp** (rush → danang_peak → peak → haichau) → nhìn thấy tận mắt câu chuyện bão hoà. 5/5 test pass. | `frontend/replay_ab.html` · `docs/demo_replay_ab.md` |
| 3 | **Phổ bão hoà (saturation spectrum)** ⭐ | 4 kịch bản xếp trên **2 trục tải đo được, độc lập controller** (concurrent / peak queue / % stopped) — không phải cherry-pick. Đây là phần "chín" nhất về mặt học thuật. | `docs/scenario_regimes.md` |
| 4 | **Kết quả multi-seed K=5, CI Student-t** ⭐ | rush **+37.1%** [34.9, 39.2] · calib **+21.6%** [13.1, 30.1] · peak **+5.1%** [2.2, 8.1] · dense **−39.9%** [−41.3, −38.5]. Cả 4 giữ dấu, không cái nào cắt 0. Công thức CI đã sửa z→t, ddof 0→1 (2026-07-22). | `results/multiseed/*.json` |
| 5 | **Kết quả âm được báo trung thực** ⭐ | Không variant DQN nào vượt Max-Pressure; dense −39.9% (tệ hơn cả Random) vẫn báo; robustness **không** cho lợi thế. Đây là **điểm mạnh tín nhiệm**, không phải điểm yếu — có nền lý thuyết (Varaiya: MP throughput-optimal với queue local) + benchmark độc lập (RESCO). | `docs/ablation_honest_plan.md` |
| 6 | **Agreement analysis** ⭐ | agree rate **25.1%** (rush) / 26.5% (calib) ≈ mức ngẫu nhiên; chỉ 6–8/53 nút đồng thuận ≥70% → **DQN đạt hiệu năng cỡ MP bằng một chính sách KHÁC hẳn, không bắt chước**. Đây là phát hiện khoa học thú vị nhất, trả lời thẳng câu hỏi hiển nhiên của thầy. | `results/*/agreement/agreement.json` |
| 7 | **Ma trận robustness đầy đủ** | 3 loại nhiễu × 2 kịch bản: sensor noise, **incident** (nút bận nhất kẹt green 1/3 horizon), **demand shift**. Kết quả: incident degrade 1–4% (DQN nhỉnh hơn MP → không có lợi thế); shift **bất đối xứng** — rush→calib gần miễn phí (−1.5%), calib→rush kém (+45.8%). | `results/*/robustness/{noise,incident,shift}.json` |
| 8 | **Chương 4 LaTeX hoàn chỉnh** | 37KB, đủ Setup → Results → Robustness & Generalization → Ablation → Analysis → Limitations; đã wire `tab:incident`, `tab:shift`, đoạn agreement. Đã `\input` vào file chính (dòng 524). | `paper/chapter4_experiments_results.tex` |
| 9 | **Kỹ thuật: DQN NumPy from scratch** | Không dùng torch/SB3 — tự viết forward/backward, replay buffer, target net, param-sharing 53 agent. 85 test chạy trên host **không cần container** (FakeEngine + lazy import). | `src/traffic_rl/` · `tests/` |
| 10 | **Bộ hình đã regen kèm error bar** | 4 × `methods_*.png` (có CI), `multiseed_ci.png`, `robustness_haichau_rush.png`, `demand_sweep.png`, `improvement_vs_demand.png`, `journey.png`. | `results/presentation/` |
| 11 | **Doc tự rà soát** | Tự audit toàn repo + đối chiếu văn liệu 2018–2026, **mọi citation có link đã kiểm tra**, có mục tự sửa lỗi của chính mình. Cho thầy thấy anh tự biết chỗ nào còn yếu. | `docs/thesis_improvement_review.md` |

---

## TIER 2 — Sửa nhanh RỒI hãy gửi (xếp theo tỉ lệ lợi ích/công sức)

| Việc | Công sức | Vì sao phải làm trước |
|------|:--------:|------------------------|
| **Build PDF trên Overleaf** 🔴 | ~15 phút | **Blocker lớn nhất.** Máy không có `pdflatex/xelatex/latexmk/tectonic` → hiện **không tồn tại file PDF nào**. Thầy review luận văn là review *bản PDF*. Chỉ cần upload 3 file (`trafic_rf.tex`, `chapter4_experiments_results.tex`, `references.bib`) + thư mục `results/` cho hình. Đừng cài MacTeX (vài GB). |
| **Sửa `requirements.txt`** 🔴 | 5 phút | Đang pin `torch 2.0.1`, `stable-baselines3`, `gymnasium` — **không cái nào được import**. Thầy đọc file này sẽ kết luận DQN xây bằng SB3 → **phá thẳng luận điểm "from-scratch NumPy"** đang là điểm mạnh #9 ở trên. |
| ~~**Commit 35 file đang dở**~~ ✅ **XONG 2026-07-30** | — | Đã commit thành 5 nhóm: stats CI · robustness+agreement · paper/docs · fix demo · run log. |
| **Merge `demo/replay-3d` → `main`** | 15 phút | Branch đang **hơn main 7 commit**. Thầy clone `main` là **không có demo 3D**. |
| **Thống nhất số demo vs paper** 🟡 | 10 phút | Scoreboard demo hiện ghi DQN **−30.8%** (1 seed, đúng theo `comparison.json`), paper ghi **+37.1%** (mean 5 seed). Cả hai đều đúng nhưng thầy xem demo rồi đọc paper sẽ hỏi ngay "rốt cuộc bao nhiêu?" — thêm 1 câu caption: *"clip này = 1 seed; trung bình 5 seed = 37.1%"*. |
| **Dashboard thiếu kịch bản headline** 🟡 | 1 dòng | `dashboard/app.py:26` liệt kê `["haichau","haichau_peak","full","subarea"]` — **thiếu `haichau_rush`** (chính là headline) và `haichau_calib`. Demo dashboard mà thiếu đúng kịch bản chính thì rất phí. |
| **Ch1/Ch3 còn claim cũ (C1–C3)** 🟡 | ~1 giờ | Objective 3 vẫn hứa baseline "actuated + adaptive" (chưa từng build); Ch3 còn ghi môi trường là **SUMO** (thật ra CityFlow); "average travel time" còn nêu là metric chính (thật ra waiting time); contributions 1–3 mô tả thứ chưa build. Đây đúng loại lỗi thầy bắt trong 5 phút đầu. |
| **4 hình placeholder (C5)** | 1–2 giờ | `traffic_visualization.png`, `traffic_gui_simulation.png`, `traffic_phase_0/1.png` **không tồn tại** → render ra ô trống trong PDF. (3 hình còn lại resolve OK.) Thay bằng screenshot demo 3D + sơ đồ phase xuất từ roadnet thật. |
| **Appendix A còn tả SUMO grid 3×3** | 30 phút | Mâu thuẫn trực tiếp với Ch4 (CityFlow, Hải Châu 53 nút). |
| **Xác nhận bậc học trang bìa** | 2 phút | Tên tác giả + năm **đã đúng** (Lương Quang Khang, 2026) — chỗ này review cũ ghi sai, đã fix rồi. Chỉ còn xác nhận dòng "Master of Software Engineering" khớp đúng chương trình anh đang học. |

---

## TIER 3 — ĐỪNG đưa cho thầy (số cũ, sẽ gây hiểu nhầm)

- `docs/presentation_results.md` — có banner SUPERSEDED nhưng bảng bên dưới vẫn là **single-seed** (rush +30.8%). Chỉ thầy vào `docs/scenario_regimes.md` (bản canonical).
- `docs/model_ablation.md` — còn số single-seed cũ (+6.5%) mà **chưa có banner SUPERSEDED**.
- `docs/RESULTS.md` — còn mô tả kịch bản `full`/`subarea` đã bỏ.
- **Tái lập từ fresh clone**: `data/` bị gitignore toàn bộ → clone về **không chạy được simulation** (chỉ tái lập được bảng/hình). Nếu thầy hỏi "chạy thử được không" thì phải nói trước.

---

## Thứ tự trình bày đề xuất (10–15 phút)

> Bản đầy đủ kèm lệnh chạy + cheat-sheet số liệu: [demo_quickstart.md](demo_quickstart.md).

1. **Mở bằng demo 3D** (2 phút) — hook thị giác, 2 khung cạnh nhau, thầy tự thấy DQN thoáng hơn Fixed-Time.
2. **Bảng phổ bão hoà** (2 phút) — "em không chọn kịch bản đẹp, em xếp cả 4 lên trục tải đo được".
3. **Bảng multi-seed + CI** (2 phút) — 5 seed, Student-t, dẫn Henderson 2018 / Agarwal 2021 / Colas 2018.
4. **Agreement 25%** (2 phút) — điểm "wow" khoa học: DQN đạt cỡ MP bằng chính sách khác hẳn.
5. **Nói thẳng kết quả âm** (2 phút) — không thắng MP (có lý do lý thuyết Varaiya + benchmark RESCO); dense −39.9%; robustness không cho lợi thế. **Chủ động nói trước khi thầy hỏi.**
6. **Lướt Chương 4 PDF** (3 phút).
7. **Xin ý kiến** — 3 câu nên hỏi thẳng:
   - Khung "báo cả kết quả âm" này hội đồng có chấp nhận không, hay cần đẩy mạnh phần nào lên?
   - Nên ưu tiên chạy thêm thí nghiệm neighbor-encoder (B3) hay dồn thời gian đánh bóng paper?
   - Contributions 1–3 nên viết lại theo khung "proposed framework" hay gộp lại thành 1?

---

## Câu hỏi thầy chắc chắn hỏi — đã có sẵn tài liệu trả lời

| Câu hỏi | Trả lời ở đâu |
|---------|---------------|
| "Sao không thắng được Max-Pressure?" | Varaiya 2013 (MP throughput-optimal với queue local) + RESCO benchmark + `docs/ablation_honest_plan.md` |
| "Sao dùng CityFlow không dùng SUMO?" | Tốc độ multi-agent 53 nút; SUMO vẫn dùng để convert network (Ch4 + `README.md`) |
| "Xe máy mô phỏng thế nào?" | Limitation đã khai trong Ch4; `thesis_improvement_review.md` §E3 (SUMO Sublane Model) |
| "5 seed đủ chưa?" | `thesis_improvement_review.md` §A1 (t-CI + Colas 2018) |
| "Demand có thật không?" | Synthetic, calib theo phổ bão hoà; limitation đã khai — `docs/demand_calibration_results.md` |
