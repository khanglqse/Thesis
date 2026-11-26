# thesis_data — dữ liệu quan trọng của luận văn (bản sao)

Tất cả file ở đây là **bản sao**. File gốc vẫn ở nguyên chỗ cũ, code vẫn đọc từ chỗ cũ.

| Tiền tố | Nội dung | Nguồn gốc |
|---|---|---|
| `input_tran2025_*`, `input_phan2025_*` | Lưu lượng Đà Nẵng từ bài báo đã công bố | `datasets/danang_published/` |
| `input_sumo_junction.net.xml` | Mạng SUMO nút giao đơn | `results/research_pilot/generated/danang_isolated_published.net.xml` |
| `input_demand_observed_*.json` | Demand quan sát (normal / am_peak / pm_peak) | `results/danang_protocol_v1/demands/` |
| `protocol_experiment_manifest.json` | Manifest thí nghiệm protocol v1 | `results/danang_protocol_v1/` |
| `result_final_summary.*`, `result_sensitivity_summary.*` | Bảng kết quả chính và độ nhạy | `results/danang_protocol_v1/summary/` |
| `eval_*.json` | Kết quả đánh giá từng controller (DQN 5 seed, Max-Pressure, Hysteretic MP, Fixed-Time) | `results/danang_protocol_v1/evaluation/` |
| `mc_baseline_*` | Monte-Carlo baseline 1000 lần chạy | `results/danang_baseline_mc/` |
| `camera_caurong_*` | Đếm xe YOLO camera Cầu Rồng (2026-07-11) | `results/camera_counts/caurong_20260711_1716/` |

Không đưa vào (lớn hoặc tái tạo được): video camera, OSM thô, file `.rou.xml` sinh theo seed,
trọng số mô hình `.npz`, dữ liệu CityFlow cũ (`data/danang/`, `datasets/haichau_network_v2/`).

## Hình ảnh và tài liệu phục vụ bảo vệ

| File | Nội dung | Nguồn gốc |
|---|---|---|
| `fig_junction-schematic.*` | Sơ đồ nút giao NTP–CMT8 (Hình luận văn) | `paper/figures/` |
| `fig_camera-profile.*` | Profile lưu lượng camera theo giờ (Phan 2025) | `paper/figures/` |
| `fig_validation-learning-curves.*` | Đường cong học trên tập validation | `results/danang_protocol_v1/summary/` |
| `fig_training-curves.png` | Đường cong huấn luyện | `results/danang_protocol_v1/summary/` |
| `fig_controller-comparison.*` | So sánh controller (hình kết quả chính) | `results/danang_protocol_v1/summary/` |
| `fig_demand-sensitivity.*` | Độ nhạy theo hệ số demand | `results/danang_protocol_v1/summary/` |
| `fig_mc-baseline-boxplot.*` | Boxplot Monte-Carlo 1000 lần (§6.3) | `results/danang_baseline_mc/` |
| `fig_haichau-final15-seed-sensitivity.png` | Độ nhạy seed, mạng Hải Châu 53 nút | `results/haichau_network_v2/` |
| `fig_camera_annotated_frame.jpg` | Khung hình camera Cầu Rồng có bounding box YOLO | `results/camera_counts/caurong_20260711_1716/` |
| `fig_camera_markov_map.pdf` | Bản đồ chuyển hướng (Markov), chỉ ô tô | như trên, `only_car/` |
| `fig_camera_counts.png`, `fig_camera_turning_matrix.png`, `fig_camera_markov_chain.png` | Đếm theo vạch, ma trận rẽ, chuỗi Markov | như trên |
| `fig_camera_count_lines.jpg`, `fig_camera_route_check_sheet.jpg` | Vị trí vạch đếm; bảng kiểm tra quỹ đạo thủ công | như trên |
| `fig_defense_jitter_boxplot_vi.png` | Boxplot jitter dùng trong slide bảo vệ | `docs/defense/figures/` |
| `source_phan2025_paper.pdf` | Bài báo gốc Phan 2025 (nguồn dữ liệu) | `datasets/danang_published/sources/` |
| `committee_questions_evidence_vi.md` | Câu hỏi hội đồng dự kiến + bằng chứng | `docs/defense/` |
