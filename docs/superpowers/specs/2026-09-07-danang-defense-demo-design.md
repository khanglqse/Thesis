# Demo bảo vệ thesis: thiết kế và tiêu chí sẵn sàng

Ngày: 2026-09-07. Yêu cầu bổ sung của người dùng: “hãy đảm bảo khả năng demo lúc presentation cho thesis”. Trạng thái: kế hoạch; chưa chạy browser QA hoặc tạo bundle/video trong phiên này.

Demo là một đầu ra bắt buộc xuyên suốt nghiên cứu. Phiên bảo vệ phải có đường trình diễn hoạt động khi không có Internet, không phải cài dependency hay chờ training. Dùng khả năng 2D/3D hiện có, chuẩn hóa nguồn dữ liệu và chuẩn bị fallback trước ngày bảo vệ.

## 1. Khảo sát demo hiện có

- `frontend/replay_ab.html`, `replay_ab.js`, `replay_ab_core.js`: replay 2D A/B, scenario/controller selection, play/pause/seek, camera và scoreboard.
- `frontend/replay_3d.html`, `replay_3d.js`, `replay_3d_core.js`: replay 3D A/B với `frontend/vendor/deck.min.js` đã có trong repo.
- `scripts/serve_replay.py`: server hiện in link A/B nhưng mặc định mở `frontend/index.html`; trang index đó có CDN Bootstrap/PIXI/Chartist. Cần thay đường launch của bản defense và kiểm tra offline thực tế.
- Replay/truncated data có thể nằm trong thư mục bị gitignore (`data/`, `results/*/demo/`). Fresh clone không tự có tất cả files mà demo cần; phải đóng gói artifacts được chọn.
- Tài liệu hiện yêu cầu bấm zoom vì full-network view khó nhìn thấy xe. Bản defense cần mở sẵn đúng nút và timestamp; không để người trình bày tìm khung hình đông bằng thao tác mò.
- Scoreboard cũ có thể khác aggregate thesis vì một episode/seed khác với trung bình nhiều seed; phải ghi rõ thay vì cố ép các số bằng nhau.
- Tests và screenshots được tài liệu cũ báo thành công không thay cho kiểm tra mới. Một số claim cũ về dữ liệu thật, saturation và tính tối ưu MP phải theo audit mới, không chép vào lời thoại bảo vệ.

## 2. Ba đường trình diễn

| Đường | Vai trò | Phụ thuộc khi bảo vệ |
|---|---|---|
| Replay 2D A/B offline | Đường chính ổn định, tương tác được | Browser + localhost server + bundle local |
| Replay 3D A/B offline | Góc nhìn bổ sung khi cần chỉ xe/đèn | Như 2D, thêm WebGL hoạt động |
| MP4 và ảnh/PDF | Fallback khi browser, server, WebGL hoặc máy chiếu có vấn đề | Trình phát video/PDF local |

Live inference là phần bổ sung, không phải điều kiện duy nhất để demo thành công. Nếu cần chứng minh model thực sự quyết định, có thể chạy một episode ngắn với checkpoint đã khóa ở rehearsal và hiển thị decision trace. Trong buổi bảo vệ chỉ bật live mode sau khi simulator/latency được kiểm tra, không training trước hội đồng.

UI và lời nói phải ghi “replay từ lần mô phỏng đã ghi” hoặc “live inference” đúng mode. Việc đổi tham số trên replay chỉ được chọn một run đã có đúng tham số; không để người dùng tưởng slider đang tạo thí nghiệm mới tức thời.

## 3. Nội dung demo bắt buộc

- Phạm vi Đà Nẵng hiển thị đúng khu vực đã nghiên cứu, mạng/nguồn/năm rõ ràng.
- Preset giờ thường, cao điểm sáng, cao điểm chiều; chỉ gọi observed/calibrated khi data registry hỗ trợ. Synthetic stress có nhãn riêng.
- Hai panel cùng case/demand seed, timestamp và camera. Cho chọn Fixed-Time, MP và RL tối thiểu; không giấu MP nếu MP tốt hơn RL.
- Thấy xe, hàng chờ và pha đèn ở default view ngay sau load; có reset camera và nút trở lại preset ban đầu.
- Play/pause, seek và tốc độ phát; timeline hiển thị simulation time, không nhầm với wall time.
- Scoreboard có đơn vị; phân biệt metric tích lũy tới thời điểm đang phát, metric cả episode và aggregate nhiều run. Nếu không có metric theo timestamp, chỉ hiển thị whole-episode metric được dán nhãn đúng.
- Case provenance: regime, data source label, controller/checkpoint ID, seed, simulator và measurement window. Chi tiết kỹ thuật mở trong panel riêng để màn hình chính dễ đọc.
- Có một preset cho thấy giới hạn hoặc trường hợp RL không tốt hơn baseline nếu đó là kết quả nghiên cứu. Không dùng demo như bằng chứng thống kê từ một khung hình.

## 4. Replay contract không phụ thuộc backend

Chốt contract này khi làm T06. Nếu chuyển SUMO, viết exporter từ simulator outputs về replay contract để tiếp tục dùng viewer; không lấy quỹ đạo CityFlow gắn nhãn SUMO. Chưa cần viết lại frontend framework.

Bundle manifest version 1 chứa:

```text
bundle_version, created_at, git_commit, protocol_hash,
network: {path, sha256, crs, coordinate_units},
cases: [{case_id, scenario_label, demand_hash, data_source_label,
         measurement_window, replay_window, selection_rule,
         runs: [{controller_id, run_id, checkpoint_hash,
                 train_seed, demand_seed, sim_seed,
                 simulator_version, replay_path, replay_sha256,
                 metrics_path, metrics_sha256}]}],
aggregate_results: {path, sha256},
initial_view: {case_id, controller_left, controller_right,
               simulation_time, camera},
fallbacks: [{kind, path, sha256}]
```

Field không áp dụng như checkpoint của MP có giá trị null. Case/run bắt buộc có identity và checksum; manifest không tự tạo actual source label từ tên folder `rush`.

Frame contract: simulation time theo giây; vehicle ID, x/y bằng mét trong hệ tọa độ local đã khai, heading/unit, length/width, vehicle class; signal state theo movement/lane ID có mapping sang network. Kiểm tra quy ước heading, left/right lane, origin và axes bằng vài frame đối chiếu simulator gốc. Không chỉ đo bounding box mesh rồi kết luận đúng vị trí đèn/làn.

Metrics là raw evaluation outputs từ đúng run. Nếu rerun để ghi replay, giữ cùng seed/config/version, so metric với run gốc trong tolerance công bố; nếu khác thì giữ identity riêng và không gọi cùng episode. Sampling/drop frames để nhẹ file không đổi metrics hoặc kéo giãn thời gian bất đối xứng giữa hai panel.

Chọn episode/preset trước khi xem chênh lệch controller: ví dụ case của ngày có tổng observed demand gần median, tie-break theo case ID, training seed final đầu tiên. Chọn camera theo junction/corridor mục tiêu và thời gian quan trắc, không theo khoảnh khắc có lợi nhất cho RL. Mọi clip được ghi là minh họa một run, bảng aggregate cung cấp kết luận chung.

## 5. Bundle và launcher

Output đề xuất khi triển khai: `results/defense_bundle/<bundle-version>/` với `index.html`, assets JS/CSS/fonts/vendor local, network/replays/metrics được chọn, manifest, một launcher macOS, README một trang, MP4 và ảnh fallback. Bundle phải chứa các file cần thiết của chính nó, không tham chiếu tới absolute path của repo hoặc máy tác giả.

Launcher phục vụ riêng bundle ở `127.0.0.1`, mặc định một port, có fallback khi port bận và mở đúng trang defense. Không mở legacy index có CDN. Chỉ kiểm tra các dependency thực sự cần, báo rõ lỗi và đường mở video dự phòng. Nếu cần Python cho launcher, kiểm tra Python trên máy bảo vệ; video/PDF phải mở được ngay cả khi Python không có.

Không mặc định dùng `file://` cho HTML có fetch; kiểm tra bằng localhost. Kiểm tra đường dẫn có dấu/khoảng trắng và copy bundle sang vị trí khác. Đóng gói kèm vendor license và quyền phân phối dữ liệu. Camera/video quan trắc raw không tự đi vào bundle.

## 6. Milestone xuyên suốt nghiên cứu

| Mốc | Công việc | Tiêu chí ra |
|---|---|---|
| D0 — T00/F1 | Audit replay legacy, browser dependencies và launcher | Có danh sách lỗi/thứ thiếu; có video/ảnh legacy nếu cần dùng tạm, dán nhãn kết quả cũ |
| D1 — T06 pilot | Chốt exporter + 2D viewer đọc một baseline pilot | Play/seek/phase/metric đúng trên backend đã chọn |
| D2 — T09 | Export preset normal/AM/PM và controllers từ final runs | Đúng manifest, case/seed/camera đồng bộ, aggregate liên kết |
| D3 — T10–T11 | Đóng gói offline, provenance/scoreboard, 3D nếu ổn | Cold start không Internet; UI không dùng số cũ; missing asset không silent fallback |
| D4 — trước bảo vệ khoảng 7 ngày | Quay MP4 1080p, ảnh/PDF, lời thoại; rehearsal lần 1 | Kịch bản 5 phút chạy được, có log vấn đề để sửa |
| D5 — trước bảo vệ 48 giờ và ngày bảo vệ | Freeze bundle/checksum, rehearsal lần 2 và preflight | Không đổi dependency/model phút cuối; cùng bundle có bản sao máy/USB |

Nếu deadline ngắn hơn mốc trên, vẫn giữ ít nhất hai lượt rehearsal và kiểm tra bản bundle đã freeze; giảm nội dung demo thay vì bỏ fallback.

## 7. Acceptance tests bắt buộc

- **Offline cold start:** ngắt Wi-Fi hoặc chặn mọi remote request, dùng browser session mới không dựa cache; cho phép localhost. Load cả 2D và 3D, tất cả preset/control được chọn đều mở được.
- **Artifact integrity:** đường dẫn, hash, timestamp, scenario và checkpoint khớp; missing file hoặc metric mismatch có lỗi rõ, không hiện 0% hoặc dùng kết quả scenario khác.
- **Correctness:** một toy replay và một final run được đối chiếu signal/vehicle position/queue; scoreboard khớp evaluator trong rounding tolerance công bố. Mọi metric sử dụng đúng dt.
- **Synchronization:** hai panel đứng ở cùng simulation timestamp sau seek/pause/speed change; camera chung; playback kết thúc có hành vi rõ khi độ dài hai replay khác nhau.
- **Legibility:** kiểm tra ở 1280×720 và 1920×1080, chữ/số đủ lớn, không bị crop; không chỉ dùng màu để phân biệt controller hoặc trạng thái.
- **Performance mục tiêu trên máy bảo vệ:** trang ready ≤10 giây với bundle local, đổi preset ≤5 giây, 2D phát mượt tối thiểu khoảng 20 FPS ở view đã chọn; thao tác không làm browser treo. Đo thật rồi giảm clip/detail nếu không đạt; đây là target chưa kiểm chứng.
- **WebGL failure:** tắt/không có WebGL thì chuyển được 2D; nếu server/browser lỗi thì mở MP4 trong khoảng 15 giây bằng cách đã tập.
- **Port/path failure:** port mặc định bận, thư mục có khoảng trắng và bundle chuyển vị trí vẫn có đường launch/fallback rõ.
- **Endurance:** chạy liên tục 15 phút, đổi scenario/controller ít nhất 10 lần, seek tới đầu/cuối; không lỗi console chưa giải thích hoặc memory tăng không kiểm soát.
- **Projection:** rehearsal với máy chiếu thực nếu tiếp cận được; nếu không, ghi rõ chỉ mới kiểm tra external display/resolution tương đương, không báo “đã test hội trường”.

Test hiện có dùng làm điểm xuất phát: `node --test tests/replay_ab/*.test.cjs tests/replay_3d/*.test.cjs`. Khi triển khai thay exporter/manifest/viewer, bổ sung đúng tests về mapping/time/provenance; browser QA không được thay bằng unit tests duy nhất.

## 8. Kịch bản trình bày 5 phút

| Thời lượng | Nội dung và thao tác |
|---|---|
| 0:00–0:40 | Giới thiệu khu vực, nguồn dữ liệu, phạm vi thời gian; nói rõ đang xem replay |
| 0:40–1:30 | Giờ thường: Fixed-Time vs RL cùng case; chỉ vị trí đèn và queue |
| 1:30–2:40 | Cao điểm: phát/tạm dừng/tua preset đã chọn; đổi baseline sang MP |
| 2:40–3:40 | Cao điểm chiều hoặc stress: minh họa thay đổi nhu cầu và một giới hạn của phương pháp |
| 3:40–4:30 | Mở bảng aggregate và CI; phân biệt episode đang xem với kết quả nhiều seed/ngày |
| 4:30–5:00 | Chốt phát hiện đúng theo kết quả, phạm vi áp dụng và giới hạn dữ liệu/mô phỏng |

Lời thoại không viết sẵn “RL giảm X%” trước kết quả cuối. Phần hỏi đáp chuẩn bị: xe thật từ đâu, tại sao chọn simulator, chính sách có học thật không, replay khác live thế nào, tại sao khác số trên bảng nhiều seed, khi nào RL thua MP và có thể triển khai thực tế chưa.

## 9. Files dự kiến tác động khi triển khai demo

Tái sử dụng `frontend/replay_ab*`, `frontend/replay_3d*`, `frontend/vendor/`, `scripts/serve_replay.py`, `scripts/truncate_replay.py`, `tests/replay_ab/`, `tests/replay_3d/`. Chỉ sửa viewer để nhận bundle/manifest/time/metrics mới và giải quyết lỗi trình diễn; không bắt buộc làm dashboard mới.

Đầu ra docs: `docs/defense/demo-runbook.md`, `docs/defense/demo-qa.md`, `docs/defense/demo-script.md`, `docs/defense/questions-and-answers.md`. Runbook một trang ghi lệnh launch chính, đường mở 2D/3D, MP4/PDF, lỗi thường gặp và preflight. QA ghi máy/browser/resolution/network state/bundle hash/ngày và từng kết quả acceptance, không dùng checklist đã tick trước.

Chỉ được báo **demo sẵn sàng bảo vệ** khi D3–D5 và acceptance phù hợp đã được thực hiện trên bundle cuối. Trong phiên hiện tại chỉ xác lập kế hoạch và điều kiện nghiệm thu, chưa có tuyên bố demo đã chạy thành công.
