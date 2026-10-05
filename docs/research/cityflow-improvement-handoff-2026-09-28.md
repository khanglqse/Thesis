# Handoff: thử cải thiện RL cho mạng 53 nút CityFlow

> **Dành cho agent nhận việc:** đọc toàn bộ handoff rồi triển khai theo checklist. Có thể dùng `superpowers:executing-plans` để thực hiện tuần tự. Người dùng sẽ giao tài liệu này cho agent khác; phiên soạn handoff chưa sửa thuật toán hay chạy training mới.

**Ngày:** 28/09/2026.  
**Goal:** thử ba giả thuyết nhỏ, đo được, để cải thiện schedule-residual DDQN trên mạng 53 nút; thu được kết luận có bằng chứng kể cả khi không phương án nào thắng.  
**Architecture:** dùng lại environment, macro compiler, reward và model V3B; bổ sung chế độ thí nghiệm riêng, so sánh thay đổi ngân sách train, thời điểm bắt đầu cập nhật và learning rate. Chọn trên validation trước khi chạy đánh giá xác nhận.  
**Tech stack:** Python/NumPy, CityFlow trong Docker, pytest; phần code chạy trong image nghiên cứu cần tương thích Python 3.6.  
**Spec:** brief và ma trận thí nghiệm trong các mục 1–4 của chính tài liệu này.

## 1. Ý định và phạm vi

Người dùng nói: “tôi thấy sumo đã giảm 35% là tốt rồi. giờ thử 1 vài idea để cải thiện đi. viết handoff để tôi giao cho agent khác làm”.

Diễn giải để thực hiện: tập trung CityFlow 53 nút; giữ nguyên thí nghiệm SUMO. Mức giảm SUMO khoảng 34,5% thuộc **PM**, không đại diện mọi regime. Không retrain SUMO trong đợt này.

Đầu ra mong muốn là code chạy được, vài thí nghiệm có đối chứng, bảng số liệu và khuyến nghị tiếp theo. Không cần chứng minh RL phải thắng Max-Pressure; không chạy tìm kiếm tham số vô hạn đến khi có một seed đẹp.

### Global constraints

- Không ghi đè kết quả, checkpoint, manifest, config đã đóng băng hoặc bằng chứng cũ.
- Không sửa paper/demo để thay kết quả chính bằng kết quả thử nghiệm chưa xác nhận.
- Cùng demand, simulator seed, horizon, topology, vehicle parameters và runtime khi so sánh các arm.
- Queue objective vẫn gồm **network queue + due pending**, tích phân từng giây; future unreleased không phải pending.
- Normal vẫn chạy fixed từ reset; AM và PM dùng residual. Không thêm PM-only gate sau khi nhìn kết quả.
- Giữ macro 300 s, dịch một boundary ±10 s, anchor, mask, minimum green và maximum red như V3B.
- Validation/test không exploration, không optimizer update. Case ID/seed/filename/future flow không vào features.
- `quick`/`smoke` chỉ kiểm tra kỹ thuật; kết luận hiệu quả dùng episode đủ 3.600 s.
- Seed bị rejected phải xuất hiện trong báo cáo. Không gộp 53 transitions/block thành 53 quan sát độc lập.

## 2. Bằng chứng hiện có và các điểm dễ hiểu nhầm

### Mốc CityFlow đã báo cáo

Nguồn: [controller matrix](../../results/haichau_network_v2/final15-controller-matrix-summary.json).

| Controller | Tổng queue cost trên 15 case, veh-h | Pooled reduction so với fixed |
|---|---:|---:|
| Tuned fixed | 8.339,43 | 0% |
| Residual seed14, episode4 | 7.829,25 | 6,12% |
| Max-Pressure | 6.347,00 | 23,89% |

Residual giảm 510,18 veh-h tổng cộng, khoảng 34,01 veh-h trung bình/case. Đây là một policy, không phải mean năm learning seeds. Không dùng 6,12% làm ngưỡng thắng của một candidate chạy trên validation hay trên test mới khác demand.

Run hiện có: 12 episode/seed, 12 macro/episode, 144 block toàn mạng, 7.632 transitions có tương quan, 1.152 optimizer updates. Sáu peak train cases được gặp hai lần/case. Đây là ngân sách còn đáng khảo sát, chưa chứng minh thiếu train.

Seed14 trên **validation PM**: queue regret tại episode4/8/12 lần lượt khoảng −0,48% / +3,24% / +5,12%. Episode4 eligible; episode8/12 không eligible. Train dài hơn không bảo đảm tốt hơn.

Nguồn cấu hình và selector:

- [Resolved config seed14](evidence-snapshot-2026-09-23/seed14-resolved-config.json).
- [Selection seed14](evidence-snapshot-2026-09-23/seed14-selection.json).
- [Snapshot manifest](evidence-snapshot-2026-09-23/snapshot-manifest.json).
- [Guide phần 9–13 và 15–16](../defense/thesis-understanding-guide-vi.md).
- [Protocol V3B](haichau-v3b-residual-protocol.md).

### Những bẫy đã kiểm tra trong code

1. `validate_config()` trong `src/traffic_rl/train/schedule_residual_trainer.py` khóa `final` vào 12 episode, seed12–16 và selector binding. Chỉ đổi YAML sang 36 episode sẽ bị từ chối. Phải có mode thí nghiệm mới; không gỡ các kiểm tra của `final`.
2. `_tracked_tree_attestation()` đòi tracked worktree/index sạch. Checkout hiện tại có thay đổi của người dùng và nhiều tài liệu chưa tracked. Tạo checkout/worktree riêng; không stash/reset/commit gộp thay đổi của người dùng để chạy được trainer. Copy đúng các artifact thiếu sang cùng đường dẫn tương đối trong checkout riêng và kiểm tra hash. Commit riêng code/config do agent tạo trước khi chạy; không sửa source trong lúc run.
3. Checkpoint hiện chỉ lưu online/target weights và metadata, thiếu Adam/replay/RNG/sampler state. Load weights rồi chạy tiếp không phải exact resume. Các arm chính bắt đầu từ đầu; một run36 lưu checkpoint12 để so sánh ngân sách. Nếu bị gián đoạn thì ghi partial, hoặc triển khai và kiểm chứng resume đầy đủ trước khi dùng.
4. Reward local `queue_weight/downstream_block_weight/switch_penalty` của environment **bị residual trainer bỏ qua**. Sửa các weight đó không thử được reward mới của V3B.
5. Chế độ final dùng `resolve_frozen_final_residual_config()`; không được nghĩ `--config` tùy ý sẽ thay được frozen final config.
6. `scripts/run_haichau_quick_campaign.py` chọn **test cases**. Không dùng nó để tune các arm, dù tên có chữ quick.
7. Config V3C/V3D và [quick safety-margin seed13](../../results/haichau_network_v2/quick-safety-margin-seed13-summary.json) đã tồn tại. Không xem việc đổi tên config hay áp margin là ý tưởng mới; kiểm tra artifact trước khi tái dùng. Một config tồn tại không chứng minh thí nghiệm đã hoàn tất.
8. Python host và Python trong image khác nhau. `pyproject.toml` yêu cầu host Python >=3.10; runtime CityFlow nghiên cứu dùng Python 3.6. Không thêm cú pháp/thư viện không chạy trong image vào đường thực thi training.

## 3. Ba ý tưởng và đối chứng

Giữ cố định: MLP 27→64→64→1, reward âm global queue+pending integral /100.000, gamma 0,99/macro, ε=0,15, batch128, replay20.000, 8 updates/macro, target sync64, margin0.

| Run arm | Episodes | Learning rate | Train start, transitions | Giả thuyết |
|---|---:|---:|---:|---|
| `budget36` | 36 | 0,0003 | 53 | Có thêm tương tác thì policy tốt hơn prefix12 của chính run này? |
| `warmup36` | 36 | 0,0003 | **1.272** | Đợi dữ liệu từ 24 block, khoảng hai episode và cả AM/PM, trước khi học có giảm học lệch lúc đầu? |
| `lr36` | 36 | **0,0001** | 53 | Bước cập nhật nhỏ hơn có giảm dao động và cải thiện validation? |

Ba arm dùng **cùng cặp learning seeds 12,13** ở screening; chọn trước khi chạy, không chỉ chọn seed14 đã tốt. Mỗi seed dùng cùng thứ tự case do balanced sampler sinh từ seed. Các hành động/trajectory sau khi trọng số khác nhau đương nhiên có thể khác.

- Ý tưởng 1: so checkpoint12 với36, đồng thời so best eligible trong prefix12 với best eligible trong prefix36. Báo cả hai để không nhầm lợi ích train thêm với lợi ích được chọn trong nhiều checkpoint hơn.
- Ý tưởng 2: so `warmup36` với `budget36`, cùng episode budget. Warmup làm giảm số optimizer updates; báo chính xác số này, không bù thêm updates rồi gọi là ablation một tham số.
- Ý tưởng 3: so `lr36` với `budget36`, cùng budget và các tham số khác.
- Chưa kết hợp warmup + lr; chưa quét thêm epsilon, gamma, kiến trúc hoặc macro trong cùng đợt.

Với 53 nút, horizon3.600, 36 episode: mỗi run có 432 macro toàn mạng và 22.896 transitions thu thập, dù buffer chỉ giữ tối đa20.000. `budget36`/`lr36` có 3.456 updates; `warmup36` bắt đầu ở block24 và có 3.272 updates nếu cập nhật ngay khi đủ ngưỡng. Dùng các số này để đối chiếu log, không dùng làm số mẫu độc lập thống kê.

**Trần screening:** sáu run36, tổng216 training episodes; validation mỗi4 episode trên sáu case. Chạy tuần tự mặc định, đo wall time từ những episode/validation đầu và báo dự toán trước phần còn lại. Không tự mở rộng lên72/120 episode hoặc thuê tài nguyên ngoài. Không bỏ horizon để làm kết quả trông rẻ hơn. Nếu runtime không có, hoàn tất phần code/tests có thể làm và ghi rõ blocker; không thay bằng simulator giả để báo hiệu quả.

## 4. Cách đánh giá và quyết định đi tiếp

### Validation và chọn checkpoint

Giữ sáu case validation đã có; train chỉ sáu peak cases. Checkpoint ở episode4,8,…,36. Baseline fixed25 và Max-Pressure chạy cùng validation để so sánh; cache baseline chỉ khi hash input, runtime và horizon khớp hoàn toàn.

Tạo selector **experiment riêng**, dùng các điều kiện hành vi từ V1:

- Normal khớp fixed theo case và timeline; forced macro0 khớp fixed25.
- Mean queue regret của từng peak regime <=0%; mean của bốn peak case <=−1%.
- Completion/insertion loss so fixed từng case <=0,02, tức2 điểm phần trăm.
- Illegal requests, anchor violations và unlogged divergence bằng0.
- Có nonzero learned macro ở cả AM/PM, ít nhất hai nút; checkpoint phản ứng với traffic features.
- Trong các checkpoint eligible, chọn mean peak queue regret thấp nhất; hòa chọn episode sớm hơn. Không có checkpoint đạt thì ghi rejected.

Các gate trên là tiêu chí lựa chọn thực nghiệm, không phải kiểm định thống kê non-inferiority. Có thể tái sử dụng logic kiểm tra của selector hiện tại nhưng không sửa whitelist/checksum V1 để ép artifact mới thành release cũ.

### Ngưỡng ưu tiên mở rộng

Ngưỡng **2 điểm phần trăm** dưới đây là quy tắc sàng lọc mới được đề xuất, không phải mức ý nghĩa thống kê:

1. Ưu tiên `budget36` nếu cả hai seed có checkpoint eligible và mean peak reduction của best eligible prefix36 tăng >=2 điểm phần trăm so prefix12. Nếu một hoặc cả hai prefix12 rejected nhưng prefix36 eligible ở cả hai seed, cho phép đi tiếp vì cải thiện eligibility; báo riêng lý do này, không tạo một điểm hiệu quả cho policy rejected.
2. Ưu tiên warmup/lr nếu cả hai seed có checkpoint eligible và mean peak reduction tăng >=2 điểm phần trăm so `budget36`, với so sánh ghép learning seed. Nếu reference có seed rejected nhưng candidate eligible ở cả hai seed, cho phép đi tiếp vì cải thiện eligibility. So queue với checkpoint reference bị loại chỉ mang nhãn diagnostic; không tráo nó thành reference accepted.
3. Nếu nhiều arm đạt: ưu tiên số seed eligible, rồi mean peak queue regret thấp hơn, rồi wall time thấp hơn. Báo mỗi regime và số case regression; không chỉ báo mean.
4. Nếu không arm nào đạt: kết thúc đợt, báo negative result và giả thuyết còn lại. Không tự quét thêm cấu hình để có số đẹp.

Nếu có arm đáng tiếp tục, chốt đúng **một arm** và đối chứng `budget36`, rồi chạy thêm seeds14,15,16 để có năm seed cho mỗi arm (nếu winner là chính `budget36`, chỉ cần arm đó và prefix12 của nó). Screening hai seed không đủ để nhận là kết luận ổn định.

### Test mới và mức độ claim

Sau khi chốt cấu hình, gate và quy tắc checkpoint bằng validation, mới tạo manifest đánh giá riêng: ba regime × năm demand/simulator seed mới chưa dùng. Agent phải kiểm kê seed đã xuất hiện trước khi chọn; ghi danh sách/hashes vào protocol trước khi chạy controller. Giữ cùng generator/topology/calibration và route-family test split; không đổi nhu cầu để giúp candidate thắng.

So candidate, đối chứng V3B12 lấy từ prefix12, đối chứng V3B36 nếu khác candidate, tuned fixed25 và Max-Pressure trên cùng new cases. Thiếu policy eligible ở một seed thì báo tỷ lệ rejected; nếu triển khai fallback fixed cho seed đó, quy tắc phải chốt trước test và báo rõ fallback. Không âm thầm loại seed hoặc dùng diagnostic weights.

Baseline deterministic không nhân thành năm run chỉ để khớp số learning seed. CI qua learning seeds dùng một effect tổng hợp/seed; đây vẫn là độ bất định có điều kiện trên bộ demand đã dùng. Demand mới trên topology/generator cũ không xác nhận hiệu quả ngoài thực địa.

Nếu không hoàn tất được test mới, kết luận tối đa là “cải thiện trên validation”; kết quả test101–105 cũ chỉ được ghi diagnostic, không dùng để chọn tiếp.

## 5. Bản đồ code và task triển khai

### Task A — Chuẩn bị môi trường và protocol

**Read:** `Makefile`, `docker/cityflow-research/Dockerfile`, `scripts/verify_haichau_foundation.py`, `src/traffic_rl/train/network_trainer.py`, các evidence links ở mục2.

- [ ] Ghi git status, commit, runtime/image identity và artifact sẵn có. Đọc các local instructions trong checkout thực thi.
- [ ] Chuẩn bị checkout riêng với source sạch và đúng input hash; giữ nguyên thay đổi của người dùng ở checkout ban đầu. Chỉ commit phần agent tạo.
- [ ] Xác minh CityFlow runtime. Makefile có `haichau-smoke` nhưng target này có thể build image; kiểm tra image hiện có trước, không mặc định tag `latest` tương đương runtime bằng chứng.
- [ ] Lưu `protocol.json` dưới output mới: arm values, seeds, split/case list, metric, checkpoints, gates, budget, source/runtime/input hashes. Ghi trước khi xem kết quả arm mới.

**Produces:** runtime/preflight record và protocol đã chốt để các task sau dùng; không thay đổi experiment manifest cũ.

### Task B — Mode experiment, config và logging

**Modify:**

- `src/traffic_rl/train/schedule_residual_trainer.py`: `validate_config()`, `train_residual()` và logging/status.
- `scripts/train_haichau_residual.py`: argparse và cách truyền mode experiment.
- `tests/train/test_schedule_residual_trainer.py`, `tests/scripts/test_train_haichau_residual.py`.

**Create:**

- `configs/experiments/haichau_residual_budget36.yaml`.
- `configs/experiments/haichau_residual_warmup36.yaml`.
- `configs/experiments/haichau_residual_lr36.yaml`.

**Interface:** giữ `train_residual(env_factory, manifest, config, output_dir, foundation_root, baseline_tuning_artifact, foundation_verifier=None)`. Thêm mode `experiment` qua `tiers.experiment={episodes:36,horizon_seconds:3600,eval_every:4}`. Giữ controller family/schema/features/reward V3B. Gắn metadata experiment và config hash vào run/checkpoint; status phải ghi exploratory và chưa eligible cho frozen release.

- [ ] Viết test mode mới chạy được trên fixture; mode final vẫn từ chối36 episode và thiếu selection binding. Mode experiment xác thực horizon3.600, budget12 hoặc36, eval4, seed12–16, optimizer values hợp lệ và không nhận selected-pilot arguments của final.
- [ ] Thêm mode và ba YAML; không sao chép pilot selection binding từ resolved config lịch sử sang experiment.
- [ ] Test train-start1272: chưa update sau23 block đủ53 nút, bắt đầu update sau block24; cập nhật chỉ sau khi nhận đủ transitions của block. Dùng fake env/unit fixture phù hợp, không chạy CityFlow dài chỉ để test số học này.
- [ ] Ghi từng episode: epsilon thực dùng, case/regime, số transitions thu thập/buffer, cumulative updates, loss và wall time. Mỗi validation ghi queue network/pending/total, completion, insertion, chọn macro0/nonzero và các violation counters. Việc logging không được tiêu thụ thêm RNG của policy/sampler.
- [ ] Test prefix12 của cấu hình36 có cùng hành vi như run12 cùng config/seed trong fixture deterministic; thay tổng episode không được âm thầm đổi epsilon schedule hoặc case ordering.
- [ ] Test nguyên trạng: reward components cộng đúng; terminal không bootstrap; reload Q/action giống nhau; normal/forced macro0 vẫn fixed; training/validation không đọc test cases; experiment status không tự đánh dấu eligible cho frozen release.
- [ ] Lưu ý smoke2×600 chỉ tạo212 transitions trên53 nút, không đủ warmup1272 và trainer sẽ báo không có optimizer update. Smoke runtime dùng arm reference; kiểm tra warmup bằng unit fixture và run full-hour. Không âm thầm giảm warmup trong arm chính để smoke qua.
- [ ] Chạy test liên quan, sửa lỗi thuộc thay đổi. CLI help test hiện có assertion cũ không bao gồm `quick`; cập nhật để kiểm tra đúng mode được hỗ trợ, không xóa test fail-closed.

**Produces:** ba config cùng đường thực thi, khác đúng tham số trong ma trận; lệnh CLI mode experiment có hiệu lực, input/status có provenance.

### Task C — Tổng hợp validation và chọn candidate

**Read/reuse:** `src/traffic_rl/research/final_residual_selector.py`, `src/traffic_rl/research/pilot_residual_selector.py`, `configs/haichau_residual_final_selection_v1.yaml`.

**Create:** `src/traffic_rl/research/residual_experiment_summary.py`, `scripts/summarize_haichau_residual_experiments.py`, `tests/research/test_residual_experiment_summary.py`.

**Interface đề xuất:** `summarize_experiments(protocol, run_records)` trả object JSON gồm arm/seed/checkpoint rows, gate decisions, best eligible prefix12/prefix36, paired effects và incomplete/rejected records. CLI nhận `--protocol`, `--output`; tất cả run paths lấy từ protocol, không glob lẫn campaign cũ. Nếu cần ghi danh sách path trước khi chạy, protocol giữ run ID/path dự kiến và trạng thái pending riêng.

- [ ] Test công thức regret/reduction, mean-per-case khác pooled, đổi veh-s sang veh-h đúng; completion loss dùng tỷ lệ0–1.
- [ ] Test rejected/incomplete không bị loại âm thầm; không chọn checkpoint vi phạm một gate dù mean queue tốt hơn.
- [ ] Test ghép arm theo learning seed và case ID; thiếu case/hash/horizon không được coi là so sánh hợp lệ. Prefix12 chỉ nhận checkpoint <=12.
- [ ] Triển khai summary và gate evaluation; xác nhận lại winner bằng reloaded deterministic validation rollout, không chỉ tin summary JSON.
- [ ] Vẽ queue validation theo episode và từng regime; đánh dấu eligible/rejected. Dùng plot xuất file PNG/PDF cho báo cáo, không dùng training loss làm tiêu chí thắng.

**Produces:** CSV/JSON có thể truy về source rows và báo cáo chọn/loại candidate đúng mục4; không cập nhật trạng thái accepted của frozen release.

### Task D — Chạy screening, xác nhận nếu có tín hiệu, báo cáo

- [ ] Chạy reference smoke và tests trước các full-hour runs; ghi wall time để ước lượng toàn campaign. Nếu foundation/runtime/hashes lỗi, sửa nguyên nhân hoặc báo blocker; không bypass verifier.
- [ ] Chạy sáu run theo ma trận, mặc định tuần tự. Dùng output directory mới cho mỗi run; failed run được giữ lại và retry có ID mới. Không chạy đồng thời trong lúc chỉnh source.
- [ ] Thu thập fixed25/Max-Pressure trên validation ghép cặp và đủ metadata; tái dùng cache chỉ khi binding hoàn toàn trùng.
- [ ] Tổng hợp cả kết quả cuối episode và checkpoint được chọn. Áp dụng tiêu chí tiếp tục/dừng ở mục4.
- [ ] Nếu đạt, triển khai thêm seeds và test mới theo mục4; nếu không, hoàn tất báo cáo âm tính. Việc xác nhận mới có thể cần mở rộng runner/generator theo cùng contract, không lách runner final cũ.
- [ ] Báo cáo mỗi arm/seed/regime: queue veh-h, pooled reduction và mean-case reduction, completion/insertion, số cases regression, tỷ lệ seed eligible, thời gian chạy. Báo spillback và completed travel time nếu observer ghi đủ; thiếu thì ghi unavailable, không điền0.

## 6. Lệnh và kiểm chứng

Các lệnh dưới chạy tại root checkout thực thi. Lệnh `--mode experiment` là **interface cần triển khai ở Task B**, chưa tồn tại ở thời điểm viết handoff.

```bash
python3 -m pytest -q tests/train/test_schedule_residual_trainer.py tests/agents/test_schedule_residual.py tests/sim/test_schedule_residual.py tests/train/test_network_replay.py tests/train/test_case_sampler.py tests/scripts/test_train_haichau_residual.py

python3 -m pytest -q tests/research/test_residual_experiment_summary.py tests/research/test_final_residual_selector.py tests/research/test_pilot_residual_selector.py

PYTHONPATH=src python3 scripts/train_haichau_residual.py --help
```

Sau khi image/input bindings đã được xác minh, chạy bên trong CityFlow runtime có checkout mount tại `/work` và `PYTHONPATH=/work/src`:

```bash
python3 scripts/train_haichau_residual.py \
  --mode experiment --learning-seed 12 \
  --manifest results/haichau_network_v2/experiment-manifest.json \
  --config configs/experiments/haichau_residual_budget36.yaml \
  --baseline-tuning-artifact results/haichau_network_v2/training/final-baseline-tuning.json \
  --output results/haichau_network_v2/experiments/2026-09-28-training-study/budget36-seed12
```

Thay config/seed/output theo ma trận; không truyền `--selected-config` hoặc `--selection-spec` của final vào experiment. Agent lưu lệnh Docker đầy đủ thực tế, image ID/digest, env bindings, exit codes và elapsed time trong campaign report.

### Review focus

- Unit thời gian: episode một giờ, macro300 s, optimizer updates là lần cập nhật; không nhập nhằng budget.
- Data split: quick runner dùng test; summary tuyệt đối không chọn model bằng test rows.
- Artifact isolation: mode experiment và checkpoint36 không được tự mang nhãn selected/final cũ.
- Replay: warmup đúng ngưỡng và đủ block; batch có hoàn lại không tạo thêm trải nghiệm độc lập.
- Failure accounting: missing/rejected seeds không biến mất khỏi mẫu; fallback và diagnostic được ghi riêng.

## 7. Khi ba ý tưởng trên không giúp

Trước khi đề xuất tăng model, đọc phân bố số macro hợp lệ, tỷ lệ macro0 và cải thiện theo block/regime. Có thể nguyên nhân nằm ở:

1. **Credit assignment:** reward toàn mạng giống nhau cho53 nút, observations cục bộ; cân nhắc critic có thông tin toàn mạng hoặc reward giúp phân biệt đóng góp trong một đợt riêng.
2. **Giới hạn action:** chỉ một boundary ±10 s/300 s. Thay macro duration/shift phải sửa cả compiler, features, padding, discount theo thời gian, contract và tests; không chỉ sửa YAML.
3. **Đa dạng nhu cầu:** nhiều episode vẫn lặp sáu train cases; mở rộng train/validation demand cần manifest mới và đối chứng cùng budget.

Đây là hướng tiếp theo có cơ sở để khảo sát, **chưa phải nguyên nhân đã chứng minh**. Không tự triển khai cả ba trong đợt này, và không giả định reward local cũ đã tác động đến residual trainer.

## 8. Deliverables và điều kiện hoàn tất

Lưu kết quả mới dưới `results/haichau_network_v2/experiments/2026-09-28-training-study/`, và báo cáo tiếng Việt tại `docs/research/cityflow-training-study-2026-09-28.md`.

- [ ] Code/config/tests cho experiment mode và summary; lệnh tái lập được ghi đầy đủ.
- [ ] Protocol có các quyết định trước run; resolved configs, manifests, checkpoint hashes, learning/validation logs, runtime identity.
- [ ] Bảng CSV/JSON, learning curves và quyết định giữ/loại từng arm; có cả thất bại.
- [ ] Nếu có candidate được chọn: năm learning seeds và kết quả test mới, hoặc nêu chính xác phần xác nhận chưa hoàn tất/blocker.
- [ ] Báo cáo trả lời: thêm training giúp không; warmup giúp không; lr nhỏ giúp không; tiết kiệm bao nhiêu veh-h so đối chứng trên cùng cases; còn cách Max-Pressure bao xa; mất bao nhiêu wall time.
- [ ] SUMO, paper/demo và các kết quả công bố cũ vẫn giữ đúng phạm vi. Không có con số mới được gọi là thesis result đã xác nhận chỉ vì thư mục mang tên final.

Có thể hoàn tất đợt nghiên cứu bằng kết luận “chưa tìm thấy cải thiện trong ba thử nghiệm này” nếu các run và phân tích đã đầy đủ. Nếu chưa chạy đủ vì runtime/tài nguyên, ghi rõ trạng thái còn thiếu; không coi chỉ viết code là đã hoàn tất thí nghiệm.
