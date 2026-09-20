# Kịch bản thuyết trình thesis: điều khiển đèn giao thông bằng RL trên mạng Hải Châu

**Mục đích của tài liệu này.** Đây là lời thoại và checklist để trình bày một bài bảo vệ khoảng 30 phút. Nó dùng đúng bằng chứng hiện có trong repository, tránh trộn số liệu của prototype cũ với mạng 53 nút giao thông. Bạn có thể cầm tài liệu này để tập, nói theo phần chữ nghiêng, rồi thay dần bằng cách nói tự nhiên của mình.

**Luận điểm trung tâm cần giữ xuyên suốt:** luận văn xây dựng và đánh giá một bộ điều khiển đèn tín hiệu học tăng cường cho một **mạng mô phỏng gồm 53 đèn tín hiệu trên topology OSM-derived ở Hải Châu, Đà Nẵng**. Bộ điều khiển không được quảng bá là tốt nhất trong mọi điều kiện. Nó giữ nguyên lịch fixed-time ở lưu lượng bình thường để không gây hại, và dùng schedule-residual DDQN ở giờ cao điểm PM. Trên bộ đánh giá exploratory nhiều seed, chính sách theo regime giảm queue-hours toàn ngày 1.03–5.62%, trung bình 3.48% so với tuned fixed-time. Dữ liệu topology có nguồn thực; lưu lượng, tuyến xe và chương trình đèn là mô phỏng tổng hợp bị ràng buộc bởi bằng chứng Đà Nẵng, không phải đo đếm toàn quận.

---

## 1. Trước ngày bảo vệ: chuẩn bị đúng thứ cần mở

### 1.1. Hai artifact phải tách bạch

| Artifact | Dùng để làm gì | Không được nói là gì |
|---|---|---|
| `presentation/thesis_defense_danang.pptx` | Slide nền cho câu chuyện, phương pháp, số liệu và giới hạn | Không phải nguồn chạy mô phỏng trực tiếp |
| `results/haichau_network_v2/demo-visual/` | Demo browser A/B, xe máy/ô tô, đèn tín hiệu và topology | Không phải huấn luyện trực tiếp, không phải replay đủ 3,600 giây |
| `results/haichau_network_v2/final15-regime-gated-direct-multi-seed-summary.json` | Nguồn số headline 5 seed exploratory | Không phải strict confirmatory release |
| `results/haichau_network_v2/final15-seed14-step4-summary.json` | Bảng 15 matched cases seed 14 và kết quả theo regime | Không được thay cho suy luận 5 seed |

Nên chuẩn bị một thư mục USB chỉ chứa slide, `demo-visual` và ảnh fallback. Không cần Docker, CityFlow, checkpoint, Internet hay huấn luyện lại trong lúc bảo vệ.

### 1.2. Chạy demo trước khi vào phòng

Mở Terminal tại repository và chạy:

```sh
cd results/haichau_network_v2/demo-visual
python3 launch_demo.py --no-browser
```

Mở URL loopback mà terminal in ra. Nếu máy đang có server cũ, launcher tự kiểm tra hash và tìm cổng khả dụng. Khi cần mở nhanh, double-click `launch_demo.command` trên macOS.

Kiểm tra năm điểm trong khoảng hai phút:

1. Header hiển thị scope PM peak và ghi rõ telemetry chỉ từ 0 đến 1,200 giây.
2. Hai panel A/B hiện `Tuned fixed-time` và `DDQN`, cùng mốc thời gian.
3. Chế độ **Single junction** hiện box `M`/`C`, đèn xanh/đỏ theo làn và queue.
4. Bấm **Linked junctions**, thấy bốn tín hiệu liên kết bằng đường thực tế.
5. Bấm **Whole network**, thấy toàn bộ 53 nút điều khiển. Ở chế độ này glyph xe được ẩn có chủ ý để không đánh lừa rằng “0 xe”; số Active/M/C và queue vẫn là tổng toàn mạng.

Tập thao tác seek đến **900 s**, sau đó Play 10–15 giây. Đây là vị trí được chọn để số xe và tín hiệu dễ nhìn. Nếu browser bị lỗi, dùng các ảnh đã kiểm tra:

- `results/haichau_network_v2/demo-visual-work/fallbacks/single-junction.jpg`
- `results/haichau_network_v2/demo-visual-work/fallbacks/linked-junctions.jpg`
- `results/haichau_network_v2/demo-visual-work/fallbacks/whole-network.jpg`

### 1.3. Câu mở đầu về trung thực khoa học

Nói ngay từ đầu, trước khi ai hỏi:

> “Tôi phân biệt ba tầng bằng chứng. Topology đường và vị trí nút giao đến từ OpenStreetMap. Profile thời gian và thành phần phương tiện được ràng buộc bởi công bố tại Đà Nẵng. Nhưng OD flow, route và signal timing của toàn mạng vẫn là dữ liệu tổng hợp trong CityFlow. Vì vậy kết luận của tôi là về hiệu năng có điều kiện trong mạng mô phỏng Hải Châu, không phải dự báo hiệu năng vận hành cho toàn quận ngoài thực địa.”

Câu này không làm yếu bài. Nó cho thấy bạn biết chính xác kết quả trả lời câu hỏi nào.

---

## 2. Câu chuyện 30 phút

### Phân bổ thời gian

| Phần | Thời gian | Mục tiêu |
|---|---:|---|
| Mở vấn đề và research question | 0:00–3:30 | Cho hội đồng biết câu hỏi thực tế và giới hạn claim |
| Dữ liệu và phạm vi | 3:30–8:00 | Chứng minh network có gốc Đà Nẵng, không làm quá dữ liệu |
| Phương pháp và protocol | 8:00–14:00 | Giải thích DDQN, baseline, metric và so sánh công bằng |
| Kết quả và diễn giải | 14:00–21:30 | Trình bày gain, variance, negative result và giới hạn |
| Demo | 21:30–26:30 | Cho thấy nó hoạt động ở một nút, cụm nút và toàn mạng |
| Kết luận và câu hỏi | 26:30–30:00 | Chốt đúng phạm vi, giá trị và bước tiếp theo |

Đừng cố đọc mọi chữ trên slide. Mỗi slide chỉ cần trả lời một câu hỏi của người nghe: vấn đề gì, dữ liệu nào, mô hình làm gì, bằng chứng nói gì, và nó chưa chứng minh được điều gì.

---

## 3. Lời thoại slide-by-slide

Deck hiện có 15 slide. Nếu thời gian thiếu, cắt chi tiết ở slide 7 và 11 trước, không cắt slide 3, 4, 9, 10, 13 hoặc demo.

### Slide 1 — Title: Traffic signal control in Da Nang

**Thời gian: 30–40 giây**

**Mục tiêu:** đặt bài toán và phạm vi địa lý.

**Nói:**

> “Em là Lương Quang Khang. Luận văn nghiên cứu điều khiển đèn tín hiệu bằng reinforcement learning cho giao thông đô thị. Phần thực nghiệm chính mở rộng từ evidence ở một giao lộ Đà Nẵng sang mạng gồm 53 tín hiệu trên topology Hải Châu. Hôm nay em tập trung vào ba câu hỏi: dữ liệu đến từ đâu, mô hình được đánh giá công bằng như thế nào, và kết quả thực sự cho phép kết luận đến mức nào.”

**Không nói:** “em mô phỏng toàn thành phố Đà Nẵng” hoặc “dữ liệu giao thông thực toàn Hải Châu”.

### Slide 2 — Research question

**Thời gian: 1 phút**

**Nói:**

> “Câu hỏi nghiên cứu không phải là RL có thắng mọi thuật toán hay không. Câu hỏi chính xác hơn là: *khi nào một learned controller làm giảm tích lũy hàng đợi so với fixed-time đã được tuning?* Mạng có 53 tín hiệu, ba regime normal, AM peak và PM peak. Dữ liệu test được tách khỏi train và validation; chúng em kiểm tra nhiều learning seed để tránh kết luận từ một policy may mắn.”

**Nếu được hỏi ‘vì sao fixed-time là baseline?’** Trả lời: vì đây là baseline vận hành đơn giản và phổ biến; đồng thời bài vẫn báo cáo Max-Pressure để tránh tạo baseline yếu.

### Slide 3 — Evidence boundary

**Thời gian: 1 phút 20 giây**

**Nói:**

> “Em chia nguồn thành direct evidence và model assumptions. Direct evidence gồm mô tả làn, chu kỳ 103 giây của giao lộ công bố, bốn camera movement lines ngày 1/4/2025, và bảng turning movements 6,171 PCU/h. Những nguồn đó neo thời gian và thành phần phương tiện ở Đà Nẵng. Tuy nhiên chúng không cung cấp OD matrix, timing plan hoặc đếm xe toàn bộ 53 nút. Phần đó là giả định mô phỏng và được ghi rõ trong data provenance.”

**Điểm cần chỉ:** slide có hai cột. Dùng ngón tay chỉ “Direct evidence” rồi “Model assumptions” khi nói.

### Slide 4 — Observed demand profile

**Thời gian: 1 phút**

**Nói:**

> “Từ biểu đồ camera đã công bố, chúng em digitize bốn luồng chuyển động. Tổng quan sát là 1,395 xe/giờ lúc 13:00, 2,330 lúc 08:00 và 2,400 lúc 17:00. Đây là lý do chọn ba regime normal, AM và PM. Con số này chỉ là bốn camera lines, không phải tổng lưu lượng của giao lộ hay của quận. Vì vậy nó chỉ dùng để tạo temporal profile cho synthetic network demand.”

**Giải thích khi bị hỏi digitize là gì:** “Từ figure công bố, xác định vị trí marker trên trục và làm tròn mỗi giá trị đến 5 xe/giờ. File lưu tolerance ±15 xe/giờ, hoặc ±30 cho series lớn. Nó không phải raw camera logs.”

### Slide 5 — Experiment protocol

**Thời gian: 1 phút 30 giây**

**Nói:**

> “Protocol đi theo thứ tự build, train, select, test, report. Điều quan trọng là checkpoint được chọn trên validation, không nhìn test. Mỗi cặp so sánh dùng cùng road network, cùng demand realization, cùng simulator seed và cùng horizon 3,600 giây. Như vậy khi queue khác nhau, nguyên nhân cần xét là controller chứ không phải random demand khác nhau.”

**Giải thích split:** 9 case train, 6 case validation, 15 held-out test. Mười lăm test case là 5 demand seed cho mỗi regime normal, AM và PM.

**Cẩn thận:** đừng nói tất cả evidence hiện tại đã là strict preregistered release. Phần five-seed regime-gated là exploratory direct evidence; strict verifier chưa hoàn thành acceptance bởi selector của seed 13 và 16 không eligible theo contract frozen.

### Slide 6 — Controller and safety envelope

**Thời gian: 1 phút 40 giây**

**Nói theo thứ tự state → action → safety → reward:**

> “State đưa vào policy gồm queue theo approach, pending vehicles và phase hiện tại. DDQN chọn một trong các green phase hợp lệ. Nhưng neural network không được phép tự ý bỏ qua an toàn. Minimum green 20 giây và clearance 7 giây nằm trong environment, do đó action bất hợp lệ không đi trực tiếp ra đèn. Reward phạt network queue và demand đang chờ ngoài network: `−0.01 × (network queue + pending vehicles)`. Metric report sau cùng không phải reward, mà là queue integral tính theo vehicle-hours, càng thấp càng tốt.”

**Nếu hỏi DDQN khác DQN:** “Double DQN tách action selection khỏi action evaluation để giảm over-estimation; dueling head tách state value khỏi advantage của từng action. Đây là các thành phần đã implement, không phải tên gọi marketing.”

**Nếu hỏi coordination:** “Bản network dùng neighbor-aware phase scoring với mean-pooled context; nó không dùng GNN attention hay CTDE. Những kỹ thuật đó thuộc hướng future work nếu chưa được đánh giá.”

### Slide 7 — A held-out collision changed the model

**Thời gian: 1 phút hoặc 30 giây nếu gấp**

**Nói:**

> “Một phần quan trọng của quy trình là giữ negative evidence. Khi motorcycle time headway là 1.0 giây, một held-out AM case tạo rear-end collision ở giây 1,762. Chúng em tăng đúng một tham số lên 1.2 giây, sau đó invalidated toàn bộ run cũ, retrain và retest. Vì headway thay đổi capacity và policy dynamics, không thể lấy kết quả trước và sau rồi chọn số đẹp hơn.”

**Ý nghĩa:** slide này cho thấy bạn kiểm tra safety trong simulator và quản lý version thí nghiệm có kỷ luật. Không được kết luận “zero collision chứng minh an toàn thực địa”.

### Slide 8 — Learning varies across confirmation seeds

**Thời gian: 1 phút**

**Nói:**

> “RL có variance do khởi tạo, trải nghiệm train và checkpoint. Seed 14 cho bounded result tốt nhất 6.12%, nhưng seed khác thấp hơn. Do đó một số đẹp ở một seed chỉ là case study, không phải headline duy nhất. Kết quả presentation-ready mạnh hơn là policy gate qua 5 seed, mỗi seed đều có full-day improvement dương trong khoảng 1.03 đến 5.62%.”

**Nếu bị hỏi ‘tại sao vẫn dùng seed 14 trên slide?’** “Seed 14 cung cấp ma trận 15 paired cases và diagnostics hoàn chỉnh, nên hữu ích để giải thích mechanism. Claim tổng quát sử dụng aggregate multi-seed exploratory, không dùng seed 14 một mình.”

### Slide 9 — Hai Chau bounded result by regime

**Thời gian: 1 phút 30 giây**

**Nói:**

> “Ở normal, residual controller được anchor về fixed-time nên kết quả bằng nhau chính xác. Đây là thiết kế có chủ đích để không trả giá switching khi demand thưa. Ở seed-14 raw residual matrix, AM trung bình thấp hơn 3.53% nhưng có một case xấu hơn 4.24%; PM trung bình thấp hơn 8.86% nhưng cũng có case kém 2.40%. Tổng 15 cases là 8,339.43 xuống 7,829.25 queue-hours, tương đương 6.12% thấp hơn. Vì có regressions từng case, em không nói mô hình luôn tốt hơn.”

**Số chi tiết chỉ dùng nếu có người hỏi:** paired bootstrap 15 case-level effects của seed 14 là 0.90% đến 8.35%. Đây không thay cho seed-level inference.

### Slide 10 — Interpretation by regime

**Thời gian: 1 phút 20 giây**

**Nói:**

> “Kết quả dẫn đến deployment rule đơn giản hơn một controller chạy mọi lúc: normal và AM giữ tuned fixed-time; PM mới bật residual DDQN. Trên năm learning seed, full-day queue reduction là 1.03–5.62%, trung bình 3.48%, bootstrap 95% interval 2.01–4.95%. Đây là kết quả exploratory nhiều seed, và policy gate được diễn giải là một rule vận hành có điều kiện, không phải tuyên bố DDQN tốt cho từng case.”

**Tại sao AM giữ fixed-time dù seed 14 có gain?** “Trong nhiều seed, AM có biến thiên và case-level regression. Quy tắc gate chọn stability thay vì tối đa hóa một điểm estimate.”

### Slide 11 — Synthetic demand sensitivity

**Thời gian: 40–60 giây**

**Nói:**

> “Slide này là historical/legacy sensitivity, không phải headline của `haichau_network_v2`. Nó cho thấy kết quả có thể đổi mạnh khi scale demand. Bài học là không được cherry-pick một load. Trong thesis chính, tất cả figure legacy phải mang nhãn legacy, còn kết luận chính dùng 53-signal namespace riêng.”

Nếu slide này dễ gây nhầm lẫn trong buổi bảo vệ, nói một câu rồi qua ngay. Đừng dùng con số 181%, 48% hoặc 35% làm kết quả chính.

### Slide 12 — Safety and accounting results

**Thời gian: 1 phút**

**Nói:**

> “Ngoài queue-hours, chúng em kiểm tra accounting để không làm mất xe khỏi hệ thống. Với seed-14 pairs, completion rate tăng 1.06 điểm phần trăm, insertion rate tăng 0.82 điểm, và mean maximum node queue giảm 16.93 xe. Nhưng completed-trip travel time tăng 5.45 giây và AM spillback tăng. Vì vậy conclusion chỉ là giảm queue integral trong điều kiện thí nghiệm, không phải ‘cải thiện mọi KPI’.”

**Nếu hỏi queue integral là gì:** “Ở mỗi time step, cộng queue trong network với vehicles đã đến entry nhưng chưa insert được; tích phân theo thời gian, rồi đổi sang vehicle-hours. Nó phạt cả hàng đợi nhìn thấy trong network lẫn demand bị chặn ở biên.”

### Slide 13 — Limits on the claim

**Thời gian: 1 phút 20 giây**

**Nói chậm, dứt khoát:**

> “Các giới hạn không phải footnote. Camera evidence chỉ một ngày và bốn movement lines. Network demand và signal plans không field-calibrated. CityFlow là lane-disciplined nên chưa tái tạo việc xe máy lọc làn. Năm seed vẫn chưa đủ để thay cho chiến dịch confirmatory được frozen hoàn toàn. Vì vậy supported conclusion là: performance có điều kiện trên mô phỏng network Hải Châu, với policy gate và full disclosure về variance.”

Sau slide này, hội đồng thường tin bạn hơn vì bạn chủ động nói đúng limitation.

### Slide 14 — Defense demo: reliable by design

**Thời gian: 30–40 giây trước khi đổi sang browser**

**Nói:**

> “Demo là synchronized recorded replay, không phải live training hay live inference. Hai bên dùng cùng PM demand case và cùng clock, nên có thể quan sát phase, queue và vehicle composition. Telemetry trực quan kéo dài 0–1,200 giây; headline metric đầy đủ 3,600 giây nằm trong summary đã lưu riêng. Em sẽ dùng demo để minh họa mechanism và scale, không dùng nó để tự suy ra kết quả mới.”

### Slide 15 — Conclusion

**Thời gian: 50 giây sau demo**

**Nói:**

> “Luận văn đóng góp một pipeline có provenance từ nguồn Đà Nẵng đến CityFlow, một residual DDQN có safety envelope, một protocol paired comparison nhiều regime, và một demo offline có thể kiểm tra được. Kết quả không nói DDQN thắng Max-Pressure hoặc thắng fixed-time ở mọi demand. Kết quả nói: policy gated không làm tệ normal/AM vì giữ fixed-time, và trong PM peak nó tạo giảm queue có điều kiện trên mạng mô phỏng. Bước cần thiết trước khi vận hành thật là OD và signal-plan calibration, dữ liệu nhiều ngày, shadow deployment và kiểm định giao thông.”

Sau đó mời câu hỏi.

---

## 4. Kịch bản demo 5 phút

### Mục tiêu demo

Demo cần trả lời bằng mắt ba câu hỏi: “Đây có phải hơn một intersection không?”, “đèn có thực sự đổi phase không?”, và “xe máy, ô tô và lượng xe được nhìn/đếm như thế nào?”. Nó không có nhiệm vụ chứng minh thống kê.

### 0:00–0:30 — Mở scope và nguồn replay

Trên UI, chỉ header và nói:

> “Đây là PM peak `test_pm_peak_demand105`. Cột trái là tuned fixed-time, cột phải là DDQN. Clock được khóa chung. Đây là recorded CityFlow telemetry, sample mỗi 5 giây, từ 0 đến 1,200 giây. Các metric cuối episode 3,600 giây được đọc từ summary riêng, nên tôi không đánh đồng hình đang chạy với toàn bộ kết quả.”

### 0:30–1:45 — Single junction

1. Bấm **Single junction**.
2. Seek đến **900**.
3. Chỉ legend `M` và `C`.
4. Bấm Play khoảng 10–15 giây.

**Nói:**

> “Ở zoom này mỗi glyph `M` là motorbike và `C` là car. Kích thước và heading đến từ telemetry; đây không phải icon ngẫu nhiên. Đèn xanh/đỏ là trạng thái lane signal của CityFlow. Những trạng thái implicit/uncontrolled được để neutral, không tô đỏ để tránh gán sai nghĩa. Panel cũng tách Active toàn mạng, số motorbike/car toàn mạng, queue và số glyph đang hiển thị quanh tín hiệu.”

Đừng nói “bên phải luôn ít xe hơn”. Trong một frame ngắn, số xe nhìn thấy có thể dao động và không phải primary metric.

### 1:45–3:00 — Linked junctions

1. Pause.
2. Bấm **Linked junctions**.
3. Giữ mốc 900 hoặc bấm Play 10 giây.

**Nói:**

> “Bây giờ ta thấy cụm bốn tín hiệu láng giềng trên geometry đường thực tế, không phải bốn box ghép bằng đường thẳng. Đây là phần quan trọng của multi-intersection: action tại một nút thay đổi discharge downstream, nên state của DDQN có neighbor context. Nhìn đèn và lượng xe ở mỗi nhánh để thấy decision không còn là bài toán isolated intersection.”

Nếu người xem hỏi “có bao nhiêu xe?”, chỉ cả hai loại counter:

> “Visible glyphs là subset trong vùng 140 m quanh controlled signals để ảnh còn đọc được. Active/M/C là count của toàn mạng tại đúng cùng time step. Hai con số có scope khác nhau, nên UI ghi tách.”

### 3:00–4:00 — Whole network

1. Bấm **Whole network**.
2. Không zoom và không cố vẽ từng xe.

**Nói:**

> “Đây là full source bounds: 1,107 đường vật lý, 592 junctions và 53 controlled signals trong topology mô hình. Ở scale này tôi chủ động ẩn glyph xe, bởi vẽ hàng nghìn icon nhỏ sẽ tạo cảm giác sai về mật độ. Counter vẫn báo Active, motorbike, car và queue toàn mạng. Mục tiêu của view này là chứng minh phạm vi network, không phải đọc hành vi từng xe.”

### 4:00–5:00 — Chốt demo và quay về slide kết quả

Quay lại Slide 15 hoặc slide 10.

> “Demo cho thấy replay cùng network, cùng demand và cùng clock. Kết luận định lượng vẫn dựa trên paired 3,600-second evaluation và multi-seed summary. Điều tôi muốn minh họa là pipeline có thể kiểm tra từ xe, đèn, cụm nút đến toàn network mà không phải chạy training trong phòng.”

### Những thao tác không nên làm khi demo

- Không chuyển sang normal/AM trong visual bundle hiện tại; bundle trực quan mới chỉ có PM peak telemetry.
- Không dùng Play để ‘chứng minh’ bên nào tốt hơn chỉ từ vài giây hình ảnh.
- Không zoom toàn mạng rồi nói glyph xe biến mất do không có xe. Ở chế độ đó glyph bị ẩn có chủ ý.
- Không gọi DDQN là “published fixed-time” hoặc nói fixed schedule là kế hoạch vận hành thực của Hải Châu. Tên đúng là **tuned fixed-time reference trong mô phỏng**.
- Không gọi demo là live AI. Tên đúng là **synchronized recorded replay**.

---

## 5. Data lấy từ đâu và đi qua pipeline nào

### 5.1. Bảng provenance có thể đọc thành lời

| Thành phần | Nguồn | Cách dùng | Giới hạn cần nói |
|---|---|---|---|
| Bản đồ và topology | OpenStreetMap extract qua Geofabrik, bbox Hải Châu | OSM → SUMO `netconvert` → CityFlow roadnet | Road geometry không tự động có signal plan thực tế |
| Mạng mô hình | Source network được lọc arterial, 53 controlled signals | Nghiên cứu coordination trên multi-intersection | Không phải toàn bộ hệ thống đường hành chính Hải Châu |
| Profile giờ trong ngày | Phan, Le, Nguyen (2025), 4 camera lines ngày 01/04/2025 | Normal 13:00, AM 08:00, PM 17:00 | Bốn lines, không phải full intersection count |
| Bảng turning movement | Cùng nghiên cứu công bố, 12 movements tổng 6,171 PCU/h | Neo và sanity check cho pilot | Provenance từng row mixed; không phân phối raw DoT data |
| Thành phần xe | Số đăng ký quốc gia, dùng 90% motorbike synthetic ratio | Ràng buộc vehicle composition | Không phải measured Hai Châu OD mix |
| Flow, routes, timing | Tạo trong pipeline CityFlow | Tạo experiment matched và reproducible | Synthetic; không field-calibrated |

### 5.2. Trình bày pipeline bằng 60 giây

> “Pipeline bắt đầu từ OSM bbox Hải Châu. `netconvert` tạo SUMO topology, sau đó converter chuyển sang CityFlow. Chúng em loại residential alleys để demand đi qua các arterial signals có thể điều khiển, thay vì làm một network lớn nhưng 97% đường trống hoặc không có tín hiệu. Từ profile camera Đà Nẵng, generator tạo normal, AM và PM demand; seed tạo các realization khác nhau nhưng matched giữa controller. CityFlow chạy fixed-time, Max-Pressure, hysteretic Max-Pressure và schedule-residual DDQN. Cuối cùng các summary hash-bound ghi network, runtime, demand và checkpoint identity.”

### 5.3. Vì sao chọn 53 signals thay vì một intersection

> “Một intersection cho phép causal analysis tốt nhưng không đo được spillback hay coordination downstream. Toàn bộ city map thì lại có nhiều hẻm, local-access roads và intersection không điều khiển, làm demand không đi qua action của controller. Vì vậy scope arterial 53 signals là điểm cân bằng: đủ lớn để có network effect, nhưng vẫn buộc demand đi qua tín hiệu mà thuật toán có thể tác động.”

### 5.4. Trả lời câu hỏi ‘dữ liệu này có thật không?’

Trả lời chính xác:

> “Có ba mức. Bản đồ là dữ liệu thật từ OSM; temporal profile có neo bằng camera figure công bố tại Đà Nẵng; nhưng toàn bộ network flow và timing không phải dữ liệu vận hành đo trực tiếp. Vì thế đây là evidence-constrained synthetic experiment. Em không gọi đó là real traffic count cho toàn Hải Châu.”

---

## 6. Cách phân tích số liệu khi hội đồng hỏi sâu

### 6.1. Primary metric: queue-hours

Định nghĩa đơn giản:

> “Queue-hours là diện tích dưới đường cong số xe đang chờ theo thời gian. Một xe chờ một giờ đóng góp một vehicle-hour; 60 xe chờ một phút cũng đóng góp một vehicle-hour. Metric này bao gồm xe queue trong network và xe pending ở entry chưa insert được, nên controller không thể làm đẹp score bằng cách chặn xe ở boundary.”

Vì sao không lấy completed-trip travel time làm headline:

> “Travel time chỉ quan sát những xe đã hoàn thành, nên trong oversaturation nó có survivorship bias. Queue-hours + pending demand phản ánh backlog toàn hệ thống. Travel time vẫn được report như secondary diagnostic và ở seed-14 nó tăng nhẹ 5.45 giây, vì vậy không có claim universal travel-time improvement.”

### 6.2. Các nhóm kết quả cần phân biệt

| Nhóm | Số có thể nói | Cách diễn giải |
|---|---:|---|
| Seed-14 matched matrix | 8,339.43 → 7,829.25 queue-hours, 6.12% thấp hơn | Case study đầy đủ 15 test cases, không phải inference duy nhất |
| Seed-14 theo regime | Normal 0%; AM 3.53%; PM 8.86% | Có case-level regressions; normal tie do contract |
| Stronger baseline | Max-Pressure 23.89% thấp hơn fixed; hysteretic MP 19.19% | DDQN cải thiện fixed-time nhưng không thắng Max-Pressure ở matrix này |
| Five-seed exploratory gate | 1.03–5.62%, mean 3.48%, CI 2.01–4.95% | Headline multi-seed có điều kiện, không phải strict frozen release |
| Secondary seed-14 diagnostics | completion +1.06 pp; maximum node queue −16.93 | Descriptive, không thay primary inference |

### 6.3. Cách nói kết quả tốt mà không overclaim

Thay vì: “DDQN tốt hơn fixed-time.”

Nói: “Ở PM peak và theo policy gate đã định nghĩa, schedule-residual DDQN giảm primary queue integral so với tuned fixed-time trên các matched synthetic cases. Ở normal và AM, gate trả về fixed-time để tránh rủi ro điều khiển không ổn định.”

Thay vì: “AI tối ưu giao thông Hải Châu.”

Nói: “Mô hình đánh giá khả năng điều khiển trên topology Hải Châu trong CityFlow. Nó chưa phải khuyến nghị triển khai cho cơ quan vận hành giao thông.”

Thay vì: “DDQN thắng baseline.”

Nói: “DDQN vượt tuned fixed-time ở PM-gated comparison; Max-Pressure vẫn là baseline mạnh hơn trong matrix seed-14. Đây là một phát hiện giúp định vị rõ giới hạn của policy học.”

### 6.4. Ý nghĩa của normal tie

Nếu ai nói “normal tie thì model không có ích”, trả lời:

> “Đó là một design choice để giải đúng failure mode của policy adaptive: ở lưu lượng thưa, switching thêm có thể tạo lost time mà không tạo benefit. Hệ thống thực dụng nên có abstention/gating. Giá trị của model không phải ép nó hành động mọi lúc, mà biết khi nào giữ controller đã ổn định và khi nào kích hoạt residual action.”

### 6.5. Ý nghĩa của Max-Pressure mạnh hơn

> “Đây không phải điều phải che giấu. Max-Pressure có lý thuyết throughput mạnh khi queue local là đủ thông tin và network synthetic có structure phù hợp. DDQN vẫn hữu ích như một candidate học từ observation và có thể mở rộng context, nhưng kết quả hiện tại chưa chứng minh superiority với Max-Pressure. Thesis có giá trị vì report comparison công bằng, không vì chọn một baseline yếu.”

---

## 7. Bộ câu hỏi phản biện và câu trả lời ngắn

### “Đóng góp khoa học của bài là gì?”

> “Đóng góp là một pipeline kiểm chứng được từ evidence Đà Nẵng tới multi-intersection CityFlow, residual DDQN có safety constraints ngoài neural policy, paired protocol qua ba regime và nhiều seed, cùng một visualization replay giúp audit từ lane signal đến network. Về kết quả, bài xác định rằng gated deployment tránh normal-hour penalty và có lợi ở PM peak trong synthetic network này.”

### “Vì sao không dùng dữ liệu thực cho toàn Hải Châu?”

> “Dataset OD, detector và timing plan toàn quận chưa sẵn có hoặc không đủ license/provenance để tái lập. Thay vì giả vờ có dữ liệu đó, bài dùng evidence-constrained synthetic design. Bước tiếp theo là hợp tác để lấy detector logs nhiều ngày, phase plans và OD calibration.”

### “Tại sao dùng CityFlow, không phải SUMO?”

> “CityFlow phù hợp cho multi-intersection RL với performance cao và API cho queue/vehicle state. SUMO được dùng ở pilot để kiểm tra geometry/evidence riêng. Backend choice cũng tạo limitation: CityFlow lane-disciplined chưa mô tả đầy đủ motorcycle filtering ở Việt Nam.”

### “Có bao nhiêu xe thật trong simulator?”

> “Không có ‘số xe thật toàn quận’ được claim. Demand generator dùng profile từ bốn camera lines và 90% motorcycle composition như ràng buộc tổng hợp. Số Active trên UI là số xe mô phỏng đang active tại time step, không phải quan sát thực địa.”

### “Tại sao PM tốt hơn AM?”

> “Theo seed-14 matrix, PM có backlog và opportunity cho residual phase adjustment lớn hơn. AM variance cao hơn, có case regression; do đó gate không bật learned residual ở AM. Đây là empirical observation trong simulator, không phải quy luật cho Đà Nẵng thật.”

### “Vì sao dùng bootstrap?”

> “Vì effect không được giả định normal và số sample nhỏ. Với five-seed gate, mỗi seed là unit độc lập của policy; bootstrap resample các seed-level effects, không coi các replay cùng một trained policy là năm policy độc lập.”

### “Strict publication-grade đã xong chưa?”

> “Chưa. Artifact strict confirmatory có acceptance gate fail-closed vì selector preregistered chưa eligible ở seed 13 và 16, nên chưa có frozen release. Presentation dùng direct exploratory summaries và ghi nhãn đó. Đây là status trung thực, không phải thay nhãn kết quả exploratory thành confirmatory.”

### “Nếu triển khai ngoài đường thì làm gì trước?”

> “Đầu tiên calibrate demand, route choice, motorcycle behavior và controller phase plans bằng logs nhiều ngày. Sau đó offline replay trên held-out days, shadow mode không điều khiển đèn, traffic-engineering review của minimum green/clearance, rồi mới có pilot giới hạn với safety override.”

### “Demo có thật sự chạy AI không?”

> “Demo không train hoặc infer live trong phòng; nó phát recorded telemetry của các simulation evaluation đã lưu. Đó là chủ ý để demo deterministically, offline và không thay đổi kết quả. Policy đã tạo telemetry là DDQN evaluation policy.”

---

## 8. Nội dung nên ghi vào thesis viết

Nếu hội đồng yêu cầu báo cáo/luận văn hoàn chỉnh, cấu trúc chapter nên đi theo logic dưới đây.

### Chương 1 — Problem and scope

1. Bài toán urban traffic signal control và hạn chế fixed timing khi demand biến đổi.
2. Research question theo điều kiện, không đặt mục tiêu vô lý “thắng mọi baseline”.
3. Đóng góp và boundary của evidence.
4. Cấu trúc luận văn.

### Chương 2 — Related work

1. Fixed-time, actuated control và Max-Pressure.
2. DQN, Double DQN, dueling networks trong traffic signal control.
3. Multi-intersection coordination và giới hạn của local policy.
4. Research gap: evidence-constrained Vietnamese urban topology, reproducibility và safe deployment gate.

Không tuyên bố đã implement CTDE, GNN attention, QMIX, PPO hay TraCI nếu repository không có evaluation tương ứng.

### Chương 3 — Data and methodology

1. OSM/Geofabrik topology provenance và conversion chain.
2. Published camera profile, turning-movement table và digitization uncertainty.
3. Synthetic demand design, motorbike composition, scenario definition.
4. CityFlow network, 53 controlled signals và source/assumption boundary.
5. Controller definitions: tuned fixed-time, Max-Pressure, hysteretic MP, schedule-residual DDQN.
6. State, action, safety envelope, reward, queue-hours accounting.
7. Train/validation/test split, seed definition, matched pairs và bootstrap.

### Chương 4 — Results

1. Main seed-14 15-case matrix, per-regime table và full controller matrix.
2. Five-seed regime-gated exploratory summary, luôn có label exploratory.
3. Secondary operations metrics, không đổi primary conclusion.
4. Negative results: Max-Pressure stronger; AM variance; travel time/spillback tradeoff.
5. Visual replay scope: PM only, 0–1,200 s, separate from 3,600-s metrics.

### Chương 5 — Discussion and conclusion

1. Diễn giải mechanism của regime gate.
2. Threats to validity: synthetic OD/timing, one-day camera profile, lane-based motorcycle behavior, finite seed count.
3. Reproducibility artifacts, hashes, fixed replay.
4. Field-calibration roadmap và safety review.

---

## 9. Reference list nên dùng trong slide/thesis

Các citation dưới đây cần được kiểm tra format theo template trường trước khi nộp. Không tự thêm DOI/issue nếu BibTeX trong repository không có dữ liệu chắc chắn.

1. Phan, Le, and Nguyen (2025), *Application of Dueling Double Deep Q-Network for Dynamic Traffic Signal Optimization: A Case Study in Danang City, Vietnam*, **Make**, DOI: `10.3390/make7030065`. Nguồn lane/program, aggregate turning table và camera figures được digitize.
2. OpenStreetMap contributors. OpenStreetMap data, ODbL. Topology source; extract cung cấp qua Geofabrik Vietnam.
3. Wei et al. (2019), *CityFlow: A Multi-Agent Reinforcement Learning Environment for Large Scale City Traffic Scenario*. Simulator and benchmark context.
4. Van der Pol and Oliehoek (2016), *Coordinated Deep Reinforcement Learners for Traffic Light Control*. Multi-agent RL context.
5. Van Hasselt, Guez, and Silver (2016), *Deep Reinforcement Learning with Double Q-learning*. Double DQN.
6. Wang et al. (2016), *Dueling Network Architectures for Deep Reinforcement Learning*. Dueling head.
7. Varaiya (2013), *The Max-Pressure Controller for Arbitrary Networks of Signalized Intersections*. Strong baseline theory.

Trong speaker notes hoặc cuối slide có số liệu, ghi nguồn data cụ thể: `datasets/haichau_network_v2/provenance.json`, `datasets/danang_published/README.md`, và JSON summary tương ứng. Citation paper không thay thế provenance của artifact; cần có cả hai.

---

## 10. Checklist cuối cùng trước khi bước vào phòng

### Nội dung

- [ ] Thuộc một câu research question và một câu conclusion có điều kiện.
- [ ] Phân biệt được topology thực, camera evidence, và synthetic network demand.
- [ ] Không dùng số legacy single-junction trong phần kết quả 53-signal.
- [ ] Nói được Max-Pressure mạnh hơn DDQN ở matrix seed-14.
- [ ] Nói được strict confirmatory release chưa complete.
- [ ] Có câu trả lời cho normal tie, AM variability, PM gain và data limitation.

### Kỹ thuật

- [ ] Deck mở được offline.
- [ ] `demo-visual` launcher chạy và hash pass trên laptop sẽ dùng.
- [ ] Browser zoom 100%, full-screen, không có tab/notification thừa.
- [ ] Đã mở sẵn URL demo và seek 900 s.
- [ ] Có ba JPEG fallback trên desktop hoặc USB.
- [ ] Có bản PDF của deck nếu PowerPoint lỗi.
- [ ] Cắm nguồn, tắt sleep, tắt auto-update và thử projector một lần.

### Cách kết thúc khi câu hỏi quá sâu

Không đoán. Dùng mẫu sau:

> “Điểm đó chưa được phép suy ra từ artifact hiện tại. Phần em có thể khẳng định là [bằng chứng chính xác]. Để trả lời câu hỏi đó, bước tiếp theo cần là [dữ liệu/experiment cụ thể].”

Đó là câu trả lời tốt hơn việc biến một assumption thành fact.

---

## 11. Một phiên bản kết luận 45 giây để học thuộc

> “Luận văn xây dựng một pipeline điều khiển tín hiệu bằng RL cho topology OSM-derived ở Hải Châu, gồm 53 tín hiệu, với demand mô phỏng được ràng buộc bởi evidence Đà Nẵng. Kết quả cho thấy một schedule-residual DDQN không cần can thiệp ở normal và AM khi fixed-time ổn định; ở PM peak, policy gate làm giảm queue integral trong các matched simulation cases. Trên năm seed exploratory, full-day improvement nằm từ 1.03 đến 5.62%, trung bình 3.48%. Tuy nhiên Max-Pressure vẫn mạnh hơn trong bounded matrix, và network demand, routes, signal plans chưa được field-calibrated. Vì vậy đóng góp của bài là một kết quả có điều kiện, tái lập được và được trình bày trung thực, đồng thời chỉ ra chính xác dữ liệu và kiểm định cần có trước khi triển khai thực tế.”

