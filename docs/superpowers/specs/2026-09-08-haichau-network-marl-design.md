# Thiết kế nghiên cứu MARL trên mạng 53 nút Hải Châu

- **Ngày:** 2026-09-08
- **Trạng thái:** đã được duyệt về hướng kiến trúc trong hội thoại
- **Phạm vi:** mạng đường trục khu vực Hải Châu, Đà Nẵng
- **Mục tiêu:** train và đánh giá một controller học tăng cường trên nhiều nút giao, không suy giảm ở giao thông bình thường và cải thiện khi tải cao, với quy trình có thể tái lập và demo được khi bảo vệ thesis.

## 1. Vấn đề cần sửa

Pipeline hiện tại có hai nhánh chưa nối thành một nghiên cứu hoàn chỉnh:

1. Nhánh SUMO một nút dùng số liệu công bố tại Nguyễn Thành Nghị – Cách Mạng Tháng 8 – 2/9. DDQN chỉ train và validation trên một AM-peak case, nên kết quả xấu ở normal là distribution shift do protocol.
2. Nhánh CityFlow Hải Châu có 53 nút điều khiển và topology OSM, nhưng demand là random-walk synthetic, policy chỉ chia sẻ tham số giữa các nút, kết quả cũ thiếu manifest đầy đủ và không có split demand độc lập.

Configuration drift đã được tái hiện trực tiếp. Bảng Hải Châu cũ chỉ khớp khi dùng `fixed_green_duration=25` và `count_norm=5`; YAML hiện tại lần lượt là 40 và 40. Checkpoint không lưu preprocessing contract nên cho kết quả khác lớn khi chạy lại. Các kết quả cũ vì vậy chỉ là historical evidence và không được dùng làm kết luận mới.

## 2. Phạm vi và cách diễn giải bằng chứng

Nghiên cứu có hai tầng bằng chứng tách biệt:

- **Empirical anchor:** nút Nguyễn Thành Nghị – Cách Mạng Tháng 8 – 2/9 dùng các đếm camera công bố, signal plan 103 giây và SUMO. Nhánh này kiểm tra tính phù hợp với một địa điểm có dữ liệu quan sát.
- **Network-scale study:** mạng đường trục Hải Châu dùng topology OSM đã chuyển sang CityFlow, gồm 1.107 road segments, 592 intersection records và 53 nút tín hiệu điều khiển. Demand toàn mạng là synthetic nhưng phải được ràng buộc bởi vehicle mix và temporal demand ratios có nguồn từ Đà Nẵng.

Không dùng kết quả 53 nút để tuyên bố cả Hải Châu đã được hiệu chỉnh bằng dữ liệu thực. Kết luận cho nhánh này là khả năng mở rộng, phối hợp và độ bền trên topology địa phương với demand được công bố rõ là synthetic.

## 3. Tiêu chí thành công

Một candidate chỉ được chọn làm model chính khi đồng thời đạt các điều kiện sau trên test set đóng băng:

1. Chạy đủ horizon trên cả 53 nút, không lỗi simulator, không NaN và không thiếu artifact.
2. Ở normal traffic, point estimate của chênh lệch queue integral so với tuned Fixed-Time không lớn hơn 0%; upper bound của paired 95% bootstrap CI không vượt +5%.
3. Ở ít nhất một peak regime, paired 95% bootstrap CI của queue-integral difference nằm hoàn toàn dưới 0.
4. Completion/throughput không giảm để đổi lấy queue đẹp; mọi case có completion thấp hơn baseline quá 2 percentage points bị đánh dấu thất bại.
5. Kết quả được tính từ ít nhất 5 learning seeds và nhiều demand/simulator seeds độc lập, không nhân bản deterministic baseline theo learning seed.
6. Toàn bộ bảng, hình, replay và demo được tái tạo từ manifest bằng một lệnh verify end-to-end.

Nếu không candidate nào qua gate, thesis báo negative result và model tốt nhất theo validation; không chọn lại bằng test set và không sửa nhãn để che thất bại.

## 4. Network và demand dataset

### 4.1 Network contract

Đóng gói một bản network Hải Châu canonical trong thư mục dataset được Git theo dõi hoặc trong release bundle có checksum. Manifest lưu:

- bbox, ngày lấy OSM, nguồn và license;
- lệnh `osmium`, `netconvert` và converter image digest;
- SHA-256 của OSM input, SUMO net và CityFlow roadnet;
- số roads, intersections, controlled signals, green phases, lanes và connected components;
- danh sách 53 agent IDs và adjacency giữa các signal;
- kiểm tra mọi phase có movement hợp lệ, mọi agent có ít nhất hai green phases và mọi lane/road reference tồn tại.

Network verifier fail closed nếu topology/hash khác manifest.

### 4.2 Demand family

Thay random walk đơn lẻ bằng case generator có version và seed. Mỗi trip đi theo route hợp lệ giữa các boundary/OD zone và phải báo số signal mà route đi qua. Bộ route cần có tỷ lệ đáng kể trip đi qua từ hai signal trở lên để đánh giá coordination.

Các regime:

- normal;
- AM peak;
- PM peak;
- demand scale 0,75×; 1,00×; 1,25×; 1,50×;
- incident giảm capacity một lane/link;
- sensor noise và observation dropout.

Normal/AM/PM dùng chung topology và OD family nhưng khác temporal loading profile. Vehicle mix, profile ratios và mọi phép suy diễn từ dữ liệu công bố phải được lưu trong provenance. Không gắn nhãn `observed` cho flow toàn mạng.

### 4.3 Split

Split theo demand seed và route family trước khi train:

- train: nhiều normal/AM/PM cases, cân bằng regime khi lấy episode;
- validation: route/demand seeds chưa xuất hiện ở train, dùng cho tuning và checkpoint selection;
- test: khóa hash trước khi tuning, chỉ mở khi candidate và rule chọn model đã đóng băng.

Learning seed, demand seed, simulator seed, network hash và case ID là các trục riêng.

## 5. Controller và môi trường

### 5.1 Baselines

Mỗi test case chạy lại tất cả baseline bằng cùng network, demand seed, simulator seed và horizon:

- published/default Fixed-Time nếu timing tồn tại;
- validation-tuned Fixed-Time với search space công bố trước;
- Max-Pressure;
- Hysteretic Max-Pressure;
- current shared DDQN làm ablation.

Không trộn row mới với baseline JSON cũ.

### 5.2 Observation có ngữ nghĩa theo phase

Padding lane theo thứ tự converter hiện tại không có cùng ngữ nghĩa giữa các nút. Encoder mới biểu diễn mỗi candidate phase bằng các feature tổng hợp từ movement mà phase phục vụ:

- incoming queue và approaching/running vehicles;
- outgoing queue, occupancy và remaining capacity;
- phase pressure;
- phase đang active hay không;
- elapsed green và time since last service;
- số lane/movement được phục vụ;
- mean/max features từ upstream và downstream signal neighbors.

Mọi feature được chuẩn hóa bằng hằng số nằm trong checkpoint contract. Action mask đi cùng tensor phase feature nên model làm việc được với số phase khác nhau.

### 5.3 Neighbor-aware phase-scoring DDQN

Một mạng dùng chung chấm `Q(s, a)` cho từng phase hợp lệ thay vì gán ý nghĩa cố định cho output index. Node context kết hợp local features với mean-pooled upstream/downstream context. Đây là neighbor-aware shared DDQN, không được gọi là full CoLight vì chưa dùng graph attention học được.

Thiết kế này giữ chi phí phù hợp với CityFlow/NumPy hiện tại, loại bỏ lỗi positional padding và tạo đường nâng cấp rõ ràng sang attention nếu ablation chứng minh mean pooling chưa đủ.

### 5.4 Signal constraints và reward

Môi trường áp dụng thống nhất:

- minimum green;
- explicit intergreen/clearance;
- optional maximum red safety bound;
- action hold không phát sinh switch giả;
- switch counter và lost-time metrics.

Reward chính là âm của local queue/pressure objective, cộng downstream-blocking penalty và switch cost nhỏ. Hệ số reward được khóa bằng validation. Queue integral, delay và completion là evaluation metrics độc lập với reward.

## 6. Training và chọn checkpoint

Mỗi episode lấy một case từ train manifest bằng sampler cân bằng normal/AM/PM. Replay buffer chứa dữ liệu từ cả 53 agent và ghi case regime để audit coverage. Training log lưu:

- toàn bộ hyperparameters và preprocessing constants;
- network, demand-manifest và runtime hashes;
- learning seed, episode case ID và simulator seed;
- loss, reward, queue, throughput/completion, switches và wall time;
- checkpoint evaluations trên từng validation regime, với queue, completion và
  insertion rate của candidate và validation-tuned Fixed-Time trên cùng case.

Checkpoint selection tối thiểu hóa worst-case normalized regret so với tuned Fixed-Time trên validation, sau đó dùng mean regret làm tie-breaker. Validation phải bao phủ đúng ba regime normal/AM/PM; mean regret của từng regime phải <= 0. Completion degradation và insertion-rate degradation của từng matched case đều phải <= 0.02, với đầy đủ evidence khớp exact case từ baseline-tuning artifact. Candidate không đạt gate này không được đưa vào final test. Contract policy schema version 2 làm checkpoint cũ thiếu insertion evidence không hợp lệ. Đây là điều kiện chọn checkpoint bằng point estimate; statistical acceptance trên held-out test vẫn được đánh giá riêng.

Chiến dịch theo tầng:

1. technical smoke: 2 episodes × horizon ngắn;
2. pilot: 1 seed trên full horizon để đo runtime và phát hiện lỗi;
3. tuning budget hữu hạn trên validation;
4. frozen final: tối thiểu 5 learning seeds;
5. test và robustness chỉ sau khi config/model-selection rule đã khóa.

## 7. Metrics và thống kê

Primary metric là network queue integral theo từng simulation step, đơn vị vehicle-hours. Secondary metrics:

- mean/median/p95 travel time và waiting time;
- arrived throughput, active vehicles và completion rate;
- average/max queue theo node và approach;
- spillback duration;
- phase switches, intergreen lost time và maximum red;
- inference latency, simulator speed và training wall time.

Travel time chỉ trên completed vehicles luôn đi cùng completion/pending để tránh survivorship bias. So sánh controller dùng matched demand/simulator cases. RL được tổng hợp ở cấp learning seed sau khi average các matched demand cases; CI không coi mỗi agent hoặc mỗi timestep là independent sample.

## 8. Artifact và chống configuration drift

Mỗi run nằm trong thư mục immutable có:

- `run-manifest.json`;
- exact resolved config, không tham chiếu mutable YAML để evaluate;
- network/flow/runtime/code hashes;
- checkpoint và preprocessing contract;
- raw per-run metrics, aggregate summary và logs;
- status `complete` chỉ khi verifier xác nhận đủ horizon và artifacts.

Checkpoint loader từ chối chạy nếu `obs_schema_version`, feature order, normalization constants, hidden size, action contract hoặc network compatibility không khớp. Không suy ra các giá trị này từ config hiện tại.

## 9. End-to-end verification

Một command cấp project thực hiện tuần tự:

1. validate environment và pinned CityFlow image;
2. verify dataset/network/demand hashes;
3. chạy unit tests cho encoder, action constraints, replay buffer, DDQN target và statistics;
4. chạy engine integration smoke trên 53 nút;
5. train smoke checkpoint;
6. evaluate fresh Fixed-Time, Max-Pressure và DDQN trên một matched case;
7. verify metric conservation, horizon, seed independence và artifact completeness;
8. build figures, thesis tables và replay;
9. launch offline demo và kiểm tra browser không có remote dependency.

Clean-checkout verification phải lấy được versioned dataset hoặc checksum-verified release bundle, không phụ thuộc `data/` local bị Git ignore.

## 10. Demo bảo vệ

Demo chính là offline replay, không train trong lúc trình bày. Viewer có:

- overview toàn mạng 53 nút Hải Châu;
- synchronized Fixed-Time/DDQN playback trên cùng case;
- normal, AM và PM selector;
- màu/độ lớn node theo queue và trạng thái phase;
- click/zoom một intersection để xem local queues và neighbor context;
- aggregate result tách rõ khỏi representative replay;
- nhãn `synthetic network demand constrained by Da Nang evidence`;
- fallback MP4, PDF và PNG được đóng gói cùng manifest.

Presentation bắt đầu bằng normal non-inferiority, sau đó peak improvement, ablation coordination và limitations. Không dùng một replay đẹp thay thế cho aggregate statistics.

## 11. Thành phần dự kiến thay đổi

- dataset/manifest builder cho Hải Châu;
- flow/case generator và split validator;
- `RoadNet` adjacency, movement và capacity helpers;
- phase-centric neighbor encoder;
- phase-scoring DDQN và checkpoint contract;
- multi-case trainer và multi-regime checkpoint selector;
- fresh matched-controller evaluator và statistical summarizer;
- project-level end-to-end verifier;
- network replay exporter/viewer;
- Chapter 3/4, limitations, defense deck và runbook.

Kết quả lịch sử dưới `results/haichau*` được giữ immutable và relabel là legacy. Campaign mới dùng namespace/version mới để không ghi đè bằng chứng cũ.

## 12. Nguồn phương pháp chính

- Wei et al., **PressLight: Learning Max Pressure Control to Coordinate Traffic Signals in Arterial Network**, KDD 2019.
- Wei et al., **CoLight: Learning Network-level Cooperation for Traffic Signal Control**, CIKM 2019, https://arxiv.org/abs/1905.05717.
- Oroojlooy et al., **AttendLight: Universal Attention-Based Reinforcement Learning Model for Traffic Signal Control**, NeurIPS 2020, https://proceedings.neurips.cc/paper/2020/hash/29e48b79ae6fc68e9b6480b677453586-Abstract.html.
- Wu et al., **Efficient Pressure: Improving Efficiency for Signalized Intersections**, 2021, https://arxiv.org/abs/2112.02336.
- Jayawardana et al., **The Impact of Task Underspecification in Evaluating Deep Reinforcement Learning**, NeurIPS 2022, https://proceedings.neurips.cc/paper/2022/hash/96ca792fddef7c1e3366c405022463cb-Abstract-Conference.html.

Các paper định hướng representation, coordination và evaluation protocol; implementation mới phải được đánh giá bằng ablation thay vì giả định mọi thành phần đều cải thiện kết quả.
