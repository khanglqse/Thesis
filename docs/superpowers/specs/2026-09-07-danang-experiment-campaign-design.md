# Thiết kế các đợt thí nghiệm và bàn giao T04–T12

Ngày: 2026-09-07. Trạng thái: protocol đề xuất để dự toán, chưa phải experiment registry đã khóa. Đọc cùng [roadmap](../plans/2026-09-07-danang-thesis-research-roadmap.md) và [foundation spec](2026-09-07-danang-research-foundation-design.md). Giai đoạn planning không chạy các job dưới đây.

## 1. Những gì khóa trước và sau pilot

Khóa ngay về nguyên tắc: dữ liệu có nguồn; baseline mạnh; paired test cases; không dùng test để chọn model; báo xe chưa nhập/chưa hoàn tất; giữ kết quả âm; nguồn bất định tách riêng; không mặc định mọi cải tiến có lợi.

Khóa sau foundation: khu vực thực, ngày dữ liệu, vị trí/nút, simulator/version, coverage observations. Khóa sau pilot: metric thresholds, horizon/warm-up/drain, simulation dt, action interval, calibration criteria, hyperparameter search space, budget và stopping rules. Chỉ sau đó tạo checksum của protocol và test-case registry.

Nếu không đủ dữ liệu/compute cho một câu hỏi nghiên cứu, thay phạm vi câu hỏi công khai trước thí nghiệm cuối. Không giữ câu hỏi trong abstract rồi bỏ thí nghiệm cần thiết mà không giải thích.

## 2. Cohort, time windows và metric

Mỗi case có `warmup_start`, `measurement_start`, `demand_stop`, `drain_stop`. Case registry dùng giây mô phỏng tương đối và mapping ra timestamp thực. Khoảng đo mặc định đề xuất là `[measurement_start, demand_stop)`; xe phát sinh trong khoảng này tạo một cohort cố định theo scheduled departure, không theo controller có cho xe nhập được hay chưa.

- Báo congestion toàn mạng trong cửa sổ đo: tích phân stopped-vehicle count theo từng simulation step, queue theo movement/link và spillback duration. Đơn vị seconds và vehicle-hours phải nhất quán.
- Báo service của cohort: actual travel time cho completed trips, scheduled-to-arrival time bao gồm insertion delay, completion fraction, pending insertions và unfinished trips tại `drain_stop`.
- Xe warm-up có thể còn trong mạng khi đo; chúng thuộc congestion network nhưng không tự thuộc departure cohort. Ghi cả hai định nghĩa, không trộn denominator.
- Không so travel time chỉ của completed trips nếu completion khác rõ. Báo lower bounds/censoring đối với chuyến chưa xong; nếu không drain hết, không trình bày observed completed mean như unbiased mean của mọi trip.
- Chỉ gọi queue-integral là stopped delay sau khi xác minh speed threshold của backend. Nếu chọn time loss so free flow, đó là metric khác và cần định nghĩa riêng.
- Census tối thiểu theo giây gồm `eligible_departures`, `inserted_cumulative`, `arrived_cumulative`, `running`, `pending`, `removed_or_teleported` theo lý do. Với case bắt đầu rỗng, kiểm tra inserted = arrived + running + removed; sau warm-up dùng offset ban đầu. Các hệ đếm phải dùng cùng population và thời điểm.

Tuyệt đối không dùng số xe tại các movement cộng lại làm số unique trips; một xe có thể được đếm tại nhiều nút. Với count chỉ tổng hợp và OD không xác định duy nhất, sinh nhiều demand realization phù hợp observations và nêu đó là route inference.

Tín hiệu: signal timing audit xác nhận green/amber/all-red riêng, pha hợp lệ, elapsed green, maximum red và những movement được phục vụ. Constraints là một tầng chung. Nếu dùng mô hình clearance giản lược, ghi đúng cách thực hiện và giới hạn; không claim triển khai đường phố đã an toàn.

## 3. Split, seeds và không rò rỉ dữ liệu

Mẫu dự toán khi có 8 ngày đo đủ ba regime: 3 ngày train/calibration, 2 ngày validation, 3 ngày test. Đây là mẫu phân bổ, không phải thông tin dataset đã có. Nếu ít ngày hơn, dùng số nhóm độc lập thật và thu hẹp kết luận; không chia clip của cùng ngày thành nhiều ngày giả.

- Calibration uses train/calibration observations; validation đo độ khớp và lựa chọn model theo ngân sách định trước. Dữ liệu test giữ nguyên cho đánh giá cuối; nếu test phát hiện calibration sai và phải sửa, bộ test đó trở thành development evidence, cần holdout mới hoặc báo exploratory.
- Điều kiện thời tiết/sự cố đặc biệt được gắn nhãn trước split. Không dùng riêng test peak để suy ra dải randomization cho training.
- Tuning seeds đề xuất `0,1,2`; final training seeds `100,101,102,103,104`. Hai simulator realization test `200,201`; demand seed và simulator seed ghi riêng ngay cả khi dùng cùng giá trị.
- Test set seed là cố định cho so sánh, không cần giữ bí mật; điều quan trọng là không dùng kết quả test để lựa chọn. Mỗi controller nhìn cùng observation contract; ghi riêng thí nghiệm privileged observation nếu có.
- Một baseline deterministic không cần chạy lại cho mỗi training seed, nhưng phải chạy trên mọi case ngày/demand/sim-seed độc lập. Không dùng năm bản sao cùng baseline như năm mẫu dữ liệu mới.
- Khi checkpoint áp dụng cho scenario khác, kiểm tra phase mapping, input dimension, normalization và graph mapping. Không tự load weights nếu schema không tương thích.

## 4. Controller và câu hỏi nghiên cứu

Tập mặc định để dự toán:

| ID | Controller | Cách chọn |
|---|---|---|
| B1 | Tuned Fixed-Time | Cycle/split/offset theo train/validation và thông tin tín hiệu |
| B2 | Actuated | Sensing contract và tuning công bố |
| B3 | Max-Pressure | Đối chiếu công thức và khả năng phục vụ |
| B4 | Advanced-MP hoặc Efficient-MP | Chọn một sau literature audit; không chọn bằng test |
| L1 | Shared local DQN | Tái sử dụng logic cũ qua backend đã chọn |
| L2 | Shared DQN có arrivals, downstream capacity, neighbor context | Phương pháp chính đề xuất; domain randomization để riêng một variant |

Nếu có signal plan thực, thêm B0 vận hành thực như cột thứ bảy; không đổi tên một fixed plan tự đặt thành actual plan. Các con số budget bên dưới chưa tính B0.

L1 và L2 huấn luyện trên mixture của normal/AM/PM trong train split. So L1 vs L2 kiểm tra hiệu quả tổng hợp; ablation tháo từng feature mới kiểm tra đóng góp thành phần. Local DQN phải có baseline implementation hợp lệ, không cố tình giữ bug/preprocessing sai để làm phương pháp mới nổi bật.

RQ3 cần thí nghiệm chuyên biệt: huấn luyện thêm L1 riêng từng regime và so specialist vs mixed L1. Kết luận này chỉ áp cho L1; muốn phát biểu cho L2 cần training specialist tương ứng. Đổi regime chỉ trên một checkpoint không tự chứng minh mixed training tốt hơn specialist training.

## 5. Campaign, số lượt chạy và chi phí

Đây là thiết kế ngân sách tham khảo cho cụm pilot; không tự chạy toàn bộ trên 53 nút. Dự toán chính giả sử 3 regime × 3 test days × 2 simulator/demand realizations = **18 clean cases**. Một case là một demand/time/network realization; một evaluation rollout là một controller/checkpoint chạy case đó.

| Đợt | Mục đích | Training | Evaluation dự kiến |
|---|---|---:|---:|
| E0 | Kiểm tra kỹ thuật | 0 | Smoke, không đưa vào bảng nghiên cứu |
| E1 | Chọn simulator/calibration pilot | 0 RL | Tối thiểu 2 backend × 3 regime × 3 sim seeds = 18 lượt, chỉ khi đủ dữ liệu so sánh |
| E2 | Tune L1/L2 trên validation | 12 configs × 2 tuning seeds × 2 learners = 48 lượt ngắn; top 3 × 3 seeds × 2 = 18 lượt ngân sách đầy đủ | Validation theo lịch cố định, tính vào compute |
| E3 | Kết quả chính | 2 learners × 5 seeds = 10 models | Learned: 10 × 18 = 180; rule-based: 4 × 18 = 72; tổng **252** |
| E4 | Ablation | 3 feature removals + 1 domain-randomization variant, mỗi loại 5 seeds = 20 models | 20 × 18 = **360**, so với main artifacts E3 |
| E5 | Specialist vs mixed (RQ3) | L1 × 3 regimes × 5 seeds = 15 models | Home regime: 15 × 3 days × 2 realizations = **90**; cross-regime là mở rộng riêng |
| E6 | Robustness không retrain | 0, dùng L1/L2 E3 | 6 perturbations × 3 regimes × 1 held-out day × 2 realizations = 36 cases; 10 learned checkpoints + 4 baselines ⇒ **504** |

Tổng E3–E6 cho phương án đầy đủ: **45 models cuối và 1.206 evaluation rollouts**, chưa tính tuning, pilot calibration, additional actual plan B0, mở rộng network hoặc sensitivity simulator. Baseline reuse chỉ hợp lệ khi case hash, metric version, constraints và simulator hash khớp; không lấy frozen baseline cũ của protocol khác.

E4 feature removals: bỏ arrivals, bỏ downstream capacity, bỏ neighbor context khỏi L2, giữ các thành phần khác. Variant thứ tư thêm domain randomization vào L2. Nếu pipeline mới không thực hiện một feature thì xóa ablation đó và sửa claim trước khi khóa campaign.

E6 mức can thiệp đề xuất để dự toán: count noise 10%, count noise 30%, observation dropout 10%, demand ×1,25, demand ×1,5, một lane/link giảm năng lực trong khoảng thời gian cố định. Định nghĩa noise cụ thể (additive/multiplicative, clipping, tương quan), vị trí incident và durations khóa sau pilot. Định nghĩa là stress test giả lập trừ khi có quan trắc sự kiện tương ứng. Một held-out day cho E6 là giới hạn về độ phủ ngày và phải được báo.

Hyperparameter configuration budget công bằng theo learner và số interaction steps; fixed/MP/actuated có search budget riêng phù hợp tham số, công bố tổng wall time. Episode count không đủ để so nếu số nút/horizon khác nhau. Successive halving phải lưu cả configs bị loại và rule pruning.

Sau profiling, thời gian dự toán:

```text
T_train ≈ tổng trên các job [simulated_seconds / measured_sim_speed
                          + gradient_updates × measured_update_seconds]
T_total ≈ T_train + T_validation + T_test + T_calibration + I/O + dự phòng
```

Benchmark worker count 1, 2 rồi 4 trên host M4 Pro/24 GiB; dừng tăng nếu tổng throughput không cải thiện hoặc thiếu RAM. Đây là worker simulator khi thực thi, không phải yêu cầu spawn AI agents. Khóa concurrency sau profiling; không mặc định 12 workers vì máy có 12 CPU.

## 6. Thu hẹp theo deadline và compute

| Mức | Phạm vi | Claim cho phép |
|---|---|---|
| Core | E3 + ba ablation thành phần; robustness chọn demand shift và một observation failure | RQ1/RQ2, RQ4 trên đúng perturbations đã chạy |
| Standard | E3–E6 như bảng | RQ1–RQ4 trong khu vực và dữ liệu quan trắc đã có |
| Extended | Standard + 53 nút, nhiều test days, model/calibration sensitivity | Scalability và độ nhạy rộng hơn nếu dữ liệu xác thực đủ |

Ưu tiên cắt số variants/cross-regime/network mở rộng trước khi cắt sạch independent test hoặc calibration. Pilot có thể 3 seeds để debug; nếu ablation chỉ có 3 seeds thì báo exploratory và không gọi bằng chứng chắc chắn. Không biến một run đẹp thành headline.

Mốc 4 tuần trở xuống: ưu tiên dữ liệu một hành lang, baseline mạnh và một phương pháp rõ; nếu chưa có data, không hứa hoàn thành full calibrated-city thesis trong mốc đó. Mốc 8–12 tuần: dùng Standard làm dự toán, điều chỉnh từ profiling và tiến độ dữ liệu.

## 7. Phân tích thống kê và lựa chọn model

- Metric chính và chiều tốt hơn khóa trước E2. Validation chọn checkpoint theo metric chính với ràng buộc coverage/completion đã định; tie-break dùng thứ tự deterministic công bố.
- Báo absolute difference và relative change: `(baseline - method) / baseline × 100%` cho cost. Nếu baseline bằng 0 hoặc quá nhỏ thì dùng absolute difference; không thổi phồng phần trăm.
- Unit resampling gồm ngày, training run và stochastic realization theo cấu trúc crossed/nested thực tế. Cùng checkpoint trên nhiều ngày không tạo training runs độc lập; cùng ngày với nhiều synthetic seeds không tạo nhiều ngày quan trắc.
- Main comparison ưu tiên L2 vs L1 và L2 vs baseline rule-based mạnh được xác định từ văn liệu/validation; giữ báo cáo đủ mọi controller. CIs và phân tích multiple comparisons phù hợp so sánh chính/exploratory.
- Report per-day/per-seed values cùng mean, median, CI; test cases ít phải nêu giới hạn. Không dùng bootstrap lặp nhiều lần để tạo cảm giác có nhiều independent observations.
- Failure do invalid route, simulation crash, NaN, hoặc manifest mismatch ghi riêng là invalid run; fix rồi rerun theo rule công bố. Gridlock hay poor score với cấu hình hợp lệ là kết quả khoa học, không được loại như lỗi kỹ thuật.
- Giữ return, loss, queue và validation curves. Không diễn giải reward cao là giao thông tốt nếu metric vật lý không cải thiện.

Tham chiếu thiết kế bất định: [Agarwal et al., NeurIPS 2021](https://arxiv.org/abs/2108.13264). Đây là áp dụng nguyên tắc vào case Đà Nẵng; không khẳng định paper quy định chính xác ma trận 5×3×2 trên.

## 8. Các hợp đồng phần mềm cần hiện thực ở T04–T10

Đây là yêu cầu cho implementation plan sau pilot; chưa thêm các file dưới vào repo.

| Gói | Existing files cần xem | Đầu ra/điều kiện cụ thể |
|---|---|---|
| T04 Network | `network/osm_to_sumo.py`, `network/sumo_to_cityflow.py`, `network/roadnet.py` | Mapping physical signal IDs, phase/movement conflict matrix, không giả làn/đèn; nguồn và checksum |
| T05 Calibration | `network/flow_gen.py`, `scripts/build_network.py`, network/data pilot | File calibration parameters có source/range; fit và validation plots; backend decision record |
| T06 Runner/metrics | `sim/engine.py`, `sim/multi_agent_env.py`, `eval/runner.py`, `eval/compare.py` | Run metadata đầy đủ, simulator-step metrics, vehicle conservation, output isolation và failure handling |
| T07 Baselines | `agents/fixed_time.py`, `agents/max_pressure.py`, `agents/base.py` | Kiểm tra timing/công thức; actuated và baseline mạnh chạy cùng case registry |
| T08 Learning | `agents/dqn.py`, `sim/encoder.py`, `train/trainer.py` | Train/validation factories tách biệt, elapsed time/masks đúng, lưu đủ preprocessing/config/checkpoint |
| T09/E3 Training | `scripts/train_dqn.py`, `scripts/run_experiment_eval.py`, batch scripts | Schedule từ registry, resume chỉ khi hash inputs/protocol khớp, final test không chọn checkpoint |
| T10 Analysis | `eval/multiseed.py`, report scripts | Missing/NaN không thành 0; dt đúng; paired effect và uncertainty theo đúng tầng |

Khi đổi backend, không mở rộng giao diện vượt nhu cầu đã xác nhận. New adapter chỉ có những chức năng cần để control và đo census/metrics; không đồng thời xây platform dashboard mới.

Test cases cần có ở kế hoạch code sau này:

- Một flow toy có lịch xe biết trước nhưng insertion bị chặn: scheduled/pending không biến mất, controller không được cải thiện metric chỉ nhờ chặn nhập.
- Queue 2 xe trong 3 giây rồi 0 trong 2 giây: stopped delay đúng 6 vehicle-seconds; đổi action interval không đổi tích phân.
- Simulation dt 0,5 giây: 20 engine steps phải là 10 giây; env horizon và clearance dùng thời gian thật.
- Có/không chuyển pha: amber/all-red/green và min-green/max-red khớp signal contract.
- Hai validation env khác train/test: chọn checkpoint không gọi test factory; normalization load từ checkpoint giữ nguyên.
- Network có unsignalized junction giữa hai tín hiệu: adjacency theo hành lang tìm đúng neighbor thay vì chỉ nối trực tiếp một edge.
- Một run thiếu metrics hoặc n=1: không xuất CI=0 như đã biết chắc; aggregate báo thiếu/không ước lượng được.
- Manifest đổi flow hash nhưng cùng tên file: resume phải từ chối reuse metrics cũ.

## 9. T11–T12: Bài viết, artifacts và tái lập

Viết literature/method khi protocol ổn định; phần results và abstract chỉ khóa sau raw outputs và thống kê. Mỗi bảng/hình có script sinh, input hash và caption ghi số seed/ngày/đơn vị. Làm một bảng trace `claim → table/figure → run IDs → config/data/code` trước nộp.

Thesis acceptance: build LaTeX thành PDF, kiểm tra undefined citations/references, render và xem layout/hình; không có placeholder, số liệu copy tay lệch raw metrics hoặc hình demo từ scenario khác được gán cho kết quả chính. Kiểm tra TeX engine/font theo template hiện có; tool TeX không thấy trong PATH là một nhiệm vụ setup sau, không phải lý do sửa template ngẫu nhiên.

Reproduction acceptance: môi trường mới có recipe/version lock, lấy được dữ liệu theo quyền, chạy một minimal case có output giống trong tolerance đã định; full campaign có manifest và hướng dẫn compute. Nếu dữ liệu restricted, cung cấp schema + synthetic reproducibility sample và quy trình xin truy cập, nêu rõ không thể công khai full measured dataset.

Demo acceptance là bắt buộc theo [defense demo spec](2026-09-07-danang-defense-demo-design.md): replay tạo từ checkpoint và test scenario đã báo cáo, so controller cùng camera/time window; hiển thị đúng scheduled/active/completed nếu có. Kiểm tra viewer từ pilot, exporter khi chọn backend, offline bundle và fallback MP4 trước bảo vệ. Demo là minh họa, không thay cho bảng thống kê.

## 10. Quy tắc chuyển task cho Sol

Hoàn tất foundation trước. Sau đó viết kế hoạch T04–T06 đủ file/interface/tests dựa trên dataset/backend thật; chạy pilot và ghi decision record. Khi protocol đã khóa, Sol viết batch plan T07–T10 có số job và wall-time budget từ profiling. Chỉ mở rộng campaign khi các prerequisite đạt; điều kiện thiếu dữ liệu không ngăn literature hoặc sửa bug độc lập.

Kết thúc mỗi đợt: báo completed/failed jobs, tổng compute, artifact paths, thay đổi protocol và ảnh hưởng claim. Không dừng chỉ vì kết quả RL thấp; phân tích nguyên nhân theo đúng evidence, giữ negative result trong thesis.
