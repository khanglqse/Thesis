# Kế hoạch đề xuất: hoàn thiện thesis RL điều khiển đèn giao thông Đà Nẵng

Ngày khảo sát: 2026-09-07. Repo tại commit `ca91c7b`.

Trạng thái: lộ trình brainstorming; người dùng đã đồng ý tiếp tục lập kế hoạch. Phạm vi phiên vẫn là planning, chưa phải lệnh triển khai. Chưa cài công cụ, sửa thuật toán, chạy training hoặc tạo kết quả thí nghiệm mới. Những số bên dưới là kiểm tra artifact cũ, không phải kết quả tái chạy.

Bộ tài liệu tiếp nối:

- [Thiết kế giai đoạn nền tảng](../specs/2026-09-07-danang-research-foundation-design.md): quyết định, hợp đồng dữ liệu và điều kiện chuyển giai đoạn.
- [Kế hoạch triển khai nền tảng cho Sol](2026-09-07-danang-research-foundation-implementation.md): các bước cụ thể cho T00–T03, lệnh kiểm tra và prompt bàn giao.
- [Thiết kế các đợt thí nghiệm](../specs/2026-09-07-danang-experiment-campaign-design.md): cohort, seed, budget, baseline và điều kiện mở rộng T04–T12.
- [Thiết kế demo bảo vệ thesis](../specs/2026-09-07-danang-defense-demo-design.md): replay offline, minh bạch kết quả, fallback và diễn tập bắt buộc theo yêu cầu bổ sung của người dùng.

## 1. Hướng nghiên cứu đề xuất

Tên làm việc: **Điều khiển tín hiệu giao thông bằng học tăng cường trên mạng lưới Đà Nẵng: hiệu chỉnh giao thông hỗn hợp, phối hợp nút giao và đánh giá tổng quát hóa giữa giờ cao điểm và giờ bình thường**.

Đóng góp chính nên là một nghiên cứu thực nghiệm đáng tin cậy trên mạng Đà Nẵng, với demand có nguồn, mô phỏng được hiệu chỉnh và benchmark công bằng. Chỉ khẳng định đóng góp thuật toán mới sau khi đối chiếu văn liệu và có ablation hỗ trợ. Không đặt mục tiêu bắt buộc RL phải thắng Max-Pressure hoặc đạt một tỷ lệ cải thiện định sẵn.

Các câu hỏi nghiên cứu:

- RQ1: Sau hiệu chỉnh bằng dữ liệu đếm xe và hành vi giao thông hỗn hợp, các controller khác nhau thế nào ở giờ bình thường, cao điểm sáng và cao điểm chiều?
- RQ2: Quan sát dòng xe sắp đến, khả năng chứa của đường phía sau và thông tin nút lân cận có cải thiện hiệu năng so với shared DQN quan sát cục bộ không?
- RQ3: Chính sách huấn luyện trên nhiều ngày/khung giờ có tổng quát tốt hơn chính sách chuyên từng regime không?
- RQ4: Các kết luận nhạy thế nào với tham số mô phỏng, seed, nhiễu cảm biến, thay đổi nhu cầu và sự cố?

Giả thuyết về lợi ích phối hợp và độ bền là câu hỏi cần thử nghiệm; kết quả không cải thiện vẫn có giá trị nếu phương pháp đánh giá hợp lệ.

## 2. Khảo sát hiện trạng: giữ gì, sửa gì

| Thành phần | Bằng chứng đã đọc | Quyết định đề xuất |
|---|---|---|
| OSM → SUMO → CityFlow | `src/traffic_rl/network/`, `configs/network.yaml`, `data/danang/` | Giữ dữ liệu gốc và pipeline chuyển đổi; kiểm tra hình học, hướng rẽ, làn, vị trí đèn |
| Shared DQN NumPy | `src/traffic_rl/agents/dqn.py`, `train/trainer.py` | Giữ như baseline lịch sử; cân nhắc PyTorch cho phương pháp mới nếu pilot chứng minh cần |
| Fixed-Time, Max-Pressure, Random | `src/traffic_rl/agents/` | Tái sử dụng qua interface; kiểm tra công thức, phase và ràng buộc công bằng |
| Neighbor observation | `sim/encoder.py`, `network/roadnet.py`, tests | Có mean-pooling đơn giản, không phải CoLight attention đầy đủ; kiểm tra láng giềng qua các junction trung gian |
| Ablation, robustness, thống kê | `results/`, `eval/`, `scripts/`, docs | Giữ artifacts lịch sử và cách tổ chức; protocol mới phải chạy lại baseline tương ứng |
| LaTeX và BibTeX | `paper/trafic_rf.tex`, `chapter4_experiments_results.tex`, `references.bib` | Tận dụng cấu trúc, viết lại claim theo chứng cứ mới |
| Demo 2D/3D | `frontend/`, replay scripts | Tái sử dụng; kiểm tra khả năng trình diễn từ đầu, đóng gói offline và diễn tập trước bảo vệ |

Các vấn đề đã thấy trực tiếp:

1. `flow_gen.py` sinh tuyến bằng random walk và chọn loại xe bằng xác suất. Đây là demand tổng hợp, chưa phải OD hoặc turning counts quan trắc.
2. Các doc dùng cụm “realistic peak” dựa vào mức tải, số xe đồng thời hoặc tỷ lệ dừng. Các đại lượng này chưa xác nhận mô phỏng khớp thực địa. `peak_queue / final_vehicle_count` còn ghép hai thời điểm; không phải v/c và không phải phép áp dụng Little's Law.
3. `haichau_rush` có 50.500 lượt khởi hành lên lịch trên khoảng 0–3.600 giây; kiểm đếm lịch trước giây 1.000 là 14.000. Script đánh giá chính mặc định 1.000 giây. Cần phân biệt lịch phát sinh, xe được đưa vào mạng, xe đang chạy và xe hoàn tất; không gọi tổng lịch cả giờ là xe đã chạy trong episode.
4. `exp_multiseed_tier2.sh` thay RL seed nhưng đánh giá cùng canonical flow; `train_dqn.py` và `run_experiment_eval.py` cố định engine seed 0. Baseline được tái dùng nên có độ lệch chuẩn bằng 0 trong aggregate. Điều đó không mô tả bất định giữa các ngày/lưu lượng thực.
5. Greedy checkpoint selection sử dụng môi trường cùng flow với báo cáo cuối; chưa thấy split độc lập train/validation/test trong đường chạy này. Phải tách trước khi tuning mới.
6. `run_episode` lấy queue cuối mỗi decision; waiting-hours suy ra bằng tổng queue × 10 giây. Đây là xấp xỉ tích phân. Cần metric theo simulation step và kiểm tra ngưỡng “waiting”, xe chưa nhập mạng, chuyến chưa hoàn tất.
7. `yellow_time` hiện được thực hiện bằng all-red khi chuyển pha. Không được mô tả là yellow vật lý đã được xác thực. Kiểm tra cả minimum green, maximum red, lost time và conflict matrix.
8. CityFlow hiện chạy `laneChange=False`; motorbike được xấp xỉ bằng kích thước và headway. Đổi tỷ lệ xe máy chưa tự chứng minh hành vi giao thông xe máy đúng.
9. Converter dùng suy đoán đèn (`--tls.guess-signals`) và bỏ đường residential. Cần xác nhận số nút điều khiển thực tế; xem xét ảnh hưởng cắt đường đến route và lưu lượng biên. Mạng có phase object không đồng nghĩa mỗi junction đều có đèn thực.
10. Tài liệu demo mâu thuẫn về tỷ lệ xe máy: 70%, khoảng 72%, 84,3%, trong khi config chung là 92%. Số 100.000–200.000 xe đồng thời đang gán cho Ton et al. cần kiểm tra trang/bảng gốc; lượt đọc này chưa xác minh được claim đó.
11. `.gitignore` bỏ toàn bộ `data/`; image CityFlow dùng tag `latest`, môi trường host/container khác thế hệ Python. Khả năng tái lập từ fresh clone cần kiểm tra thực tế.
12. Audit doc cũ có thông tin đã lỗi thời: kiểm tra hiện tại thấy 122 BibTeX entries, không trùng citation key, đã có entry 2025. Vẫn cần kiểm tra trùng công trình, metadata và nội dung từng citation; không sao chép nguyên checklist cũ.

Kết quả cũ đáng giữ làm mốc: `results/multiseed/haichau_rush.json` ghi waiting-hours DQN 113,239 ± 3,892 (CI 95%, 5 seed), Fixed-Time 179,889, MP 107,831. DQN giảm khoảng 37,1% so với Fixed-Time nhưng waiting cao hơn MP khoảng 5,0%. Các số này chỉ áp dụng protocol tổng hợp cũ; không suy ra mức cải thiện ngoài thực tế. Đơn vị CI tuyệt đối phải tách khỏi phần trăm cải thiện.

## 3. Ba phương án và lựa chọn

| Phương án | Lợi ích | Chi phí / giới hạn | Khi chọn |
|---|---|---|---|
| A. Giữ CityFlow, sửa demand và protocol | Tái sử dụng nhiều nhất, tiến độ ngắn | Hạn chế mô tả giao thông xe máy theo chiều ngang | Deadline ngắn; pilot cho thấy sai số hiệu chỉnh chấp nhận được; giới hạn claim rõ |
| B. Giữ baseline cũ, pilot SUMO sublane rồi dùng backend phù hợp | Phù hợp trọng tâm giao thông hỗn hợp; tận dụng OSM/SUMO sẵn có | Cần adapter, hiệu chỉnh và chạy lại; sublane tăng compute | **Khuyến nghị cho yêu cầu hiện tại**, quyết định cuối dựa trên pilot |
| C. Viết lại toàn bộ, graph MARL trên toàn thành phố ngay | Phạm vi rộng, nhiều khả năng thử thuật toán | Dễ thiếu dữ liệu, quá tải compute, khó phân biệt lỗi mô phỏng và lỗi học | Chỉ sau khi B ổn định và có dữ liệu/compute đủ |

SUMO có mô hình sublane cho động học ngang; đây là lý do thử nghiệm, chưa phải bằng chứng nó tự khớp Đà Nẵng. Xem [tài liệu mô hình chính thức](https://github.com/eclipse-sumo/sumo/blob/main/docs/web/docs/Simulation/SublaneModel.md).

Phạm vi không gian: bắt đầu 4–8 nút liên tiếp có dữ liệu tốt trên hành lang trung tâm, rồi mở rộng sang phần Hải Châu hiện có (repo mô tả 53 nút). Hành lang ứng viên: Nguyễn Văn Linh, Lê Duẩn, Điện Biên Phủ; lựa chọn dựa vào dữ liệu, kết nối và điều khiển thực, không mặc định chọn cả ba. Không gán kết quả hành lang cho toàn Đà Nẵng. Ghi bbox, OSM snapshot, danh sách junction và năm dữ liệu để tránh nhập nhằng phạm vi địa lý qua thời gian.

## 4. Dữ liệu thực: điều kiện bắt buộc của nghiên cứu mới

Trong lúc chưa nhận được thông tin từ người dùng, lập kế hoạch theo giả định chưa có dataset đếm xe được cấp quyền sử dụng. Không giả định sẽ tìm được dữ liệu đầy đủ trên web.

Thứ tự nguồn:

1. Dữ liệu đếm xe/khảo sát do cơ quan quản lý hoặc nhóm nghiên cứu cung cấp: vị trí, hướng, loại xe, timestamp, cách đo, sai số và quyền sử dụng.
2. Video/camera có thể sử dụng hợp lệ, hoặc khảo sát thực địa có tổ chức. Đếm thủ công là phương án khả thi cho pilot; detector/tracker chỉ là công cụ hỗ trợ, cần đối chiếu manual count.
3. Báo cáo JICA/DaCRISS và nghiên cứu địa phương: nguồn lịch sử và điểm xuất phát; phân biệt số quan trắc với dự báo, PCU/h với veh/h và phạm vi tuyến.
4. Dữ liệu tổng hợp cho stress test, dán nhãn rõ, không gọi là số xe thực.

Nguồn đã tìm được:

- [Ton et al. (2024), bài về theo dõi phương tiện tại Đà Nẵng](https://jst-ud.vn/jst-ud/article/view/8995), DOI `10.31130/ud-jst.2024.022ICT`. Trang bài báo xác nhận nghiên cứu có dataset địa phương và so sánh MOT. Chưa xác nhận tải được dataset, đủ turning counts hay bao phủ giờ cần nghiên cứu. mAP/HOTA không phải độ chính xác đếm xe theo movement.
- [DaCRISS, báo cáo JICA](https://openjicareport.jica.go.jp/pdf/12014932_01.pdf): search index mô tả đếm 24 giờ tại 8 điểm, nguồn năm 2008; PDF chưa tải được qua web tool ở lượt này. Cần đọc bảng/trang gốc trước khi dùng số.
- [Cơ quan vận tải Đà Nẵng mô tả khảo sát phân luồng năm 2019](https://www.danangbus.vn/tin-tuc/tin-tuc/giai-phap-phan-luong-giao-thong-khu-vuc-trung-tam-thanh-pho-da-nang-2177.html): đầu mối tìm bộ khảo sát, không phải dataset turning-count tải sẵn.

Gói dữ liệu cần thu:

- Đếm theo hướng vào và hướng rẽ trái/thẳng/phải, mỗi 5–15 phút; riêng xe máy, ô tô, xe buýt, xe tải khi có mặt.
- Giờ bình thường, cao điểm sáng, cao điểm chiều; khung giờ lấy từ dữ liệu. 06:30–08:30, 10:00–12:00 và 16:30–18:30 chỉ là cửa sổ khảo sát ứng viên.
- Pilot ở một ngày để thiết kế đo; mục tiêu full study 5–10 ngày làm việc, thêm cuối tuần nếu đủ nguồn. Nếu ít ngày, thu hẹp claim và báo bất định thay vì coi các đoạn video cùng ngày là mẫu độc lập.
- Chu kỳ đèn, pha, split, offset nếu có; làn, chiều rộng, giới hạn tốc độ, cấm rẽ, hướng một chiều.
- Quan trắc bổ sung về travel time, queue theo chu kỳ, discharge headway/saturation flow để hiệu chỉnh động học; chỉ có flow counts chưa đủ xác thực queue và travel time.
- Nguồn, ngày đo, timezone, đơn vị, missing values, detector error, checksum, giấy phép; tách dữ liệu raw bất biến và dữ liệu processed.

Không lấy số xe đăng ký toàn thành phố nhân một hệ số để gọi là lưu lượng thực tại nút. Không ép demand về regime RL có lợi. Nếu chỉ có dữ liệu cũ: nêu case study của năm đó; tăng trưởng giả định là sensitivity, không phải quan trắc mới.

Gate dữ liệu: phải có số quan trắc đủ để hiệu chỉnh một khu vực nhỏ và một tập ngày/khung giờ giữ riêng để kiểm chứng. Nếu chưa đạt, Sol tiếp tục audit, văn liệu và pilot tổng hợp; kết quả đó chỉ mang nhãn synthetic. Không thể hoàn thành yêu cầu “lưu lượng thật” bằng cách tự đặt số.

## 5. Hiệu chỉnh và kiến trúc thí nghiệm

Luồng xử lý: nguồn/raw → QA dữ liệu → mapping vào network → demand theo thời gian và loại xe → calibration → bộ scenario đóng băng → controller → log mỗi run → thống kê → bảng/hình → thesis.

Các module có trách nhiệm riêng:

- Data registry: truy nguồn, version, đơn vị, địa lý và split theo ngày.
- Network/scenario builder: tái tạo network và demand; kiểm tra đường đi, nguồn/đích, luồng biên và cấu trúc tín hiệu.
- Simulator adapter: reset, step, state, action, thời gian, thống kê xe; backend chỉ thay khi cần.
- Signal controller: baseline và RL dùng chung ràng buộc vật lý.
- Experiment runner: cấu hình tường minh, seed, resume, checkpoint, lỗi và manifest.
- Evaluator/report: đọc raw metrics, áp protocol đã đóng băng, sinh bảng/hình tự động.

Calibration: chỉnh OD/route probabilities, turning ratios, arrival profile, vehicle mix và thông số car-following/sublane dựa trên quan trắc; tối ưu sai số mô phỏng, không tối ưu chênh lệch RL-baseline. Không coi OD suy ngược là duy nhất nếu dữ liệu không đủ; lưu nhiều demand realization hợp lệ để đánh giá độ nhạy.

Pilot SUMO/CityFlow: dùng cùng phạm vi, cùng observed demand, cùng signal plan để so calibration fit, discharge, queue, travel time và tốc độ simulation. Dùng MAE/RMSE, sai số tương đối khi mẫu số phù hợp; GEH có thể bổ sung sau khi chọn hướng dẫn đúng đơn vị/chu kỳ. Ngưỡng chấp nhận phải ghi trước vòng calibration chính, dựa vào sai số đo và tài liệu chuyên ngành, không đặt sau khi nhìn kết quả controller.

Nếu chuyển backend, kết quả chính so controller trên cùng backend/demand/protocol; không so DQN CityFlow với MP SUMO để kết luận hơn kém. Model weights và số cũ không tự chuyển sang backend mới.

## 6. Thuật toán và giới hạn phạm vi

Baseline bắt buộc:

1. Fixed-Time theo kế hoạch thực nếu thu được; thêm tuned Fixed-Time với chu kỳ/split/offset được chọn trên calibration/validation.
2. Actuated control với cảm biến và tham số được công bố.
3. Max-Pressure; đối chiếu queue theo movement, turning ratios, saturation rates và downstream capacity. Không gán định lý throughput-optimal cho biến thể hiện tại nếu chưa kiểm tra giả thiết.
4. Shared DQN theo logic project cũ, được chạy lại trong protocol mới.
5. Một baseline mạnh từ Efficient-MP/Advanced-MP hoặc pressure-based RL, chọn theo kết quả literature audit và ngân sách.

Phương pháp nghiên cứu chính: shared value-based RL có quan sát upstream arrivals, downstream occupancy/capacity, pha hiện tại và elapsed green; bổ sung thông tin láng giềng theo đồ thị tín hiệu thực. Bắt đầu từ mean-pool đang có; chỉ thêm attention nếu ablation và ngân sách hỗ trợ. Đây là tổ hợp cần kiểm tra tính mới, không mặc định là thuật toán mới.

Action masking, min-green và clearance dùng chung cho mọi controller. Max-red/fairness được định nghĩa và kiểm tra. Reward thử queue/pressure và một thành phần chống spillback; phải có ablation cho từng thay đổi. Không chọn reward bằng test set.

Domain randomization là một biến thể có/không để kiểm tra generalization, lấy dải từ calibration uncertainty. PPO/MAPPO, residual RL, graph attention đầy đủ, emissions và ưu tiên xe buýt là phần mở rộng có điều kiện; không đưa tất cả vào critical path.

## 7. Ma trận scenario và protocol đánh giá

| Nhóm | Scenario | Nguồn và mục đích |
|---|---|---|
| Chính | Giờ bình thường ngày làm việc | Quan trắc; kiểm tra lợi ích nhỏ và tránh switching thừa |
| Chính | Cao điểm sáng | Quan trắc profile theo thời gian, hướng và loại xe |
| Chính | Cao điểm chiều | Quan trắc; kiểm tra đảo hướng chủ đạo |
| Chính | Chuyển tiếp bình thường → đỉnh → phục hồi | Chỉ gọi thực nếu dữ liệu liên tục hỗ trợ |
| Generalization | Ngày giữ riêng, train sáng/test chiều, multi-regime/test ngày mới | Không retrain hoặc retune trên test |
| Stress | Demand ×0,75 / 1 / 1,25 / 1,5 | Giá trị đề xuất để thử độ nhạy, không gọi các mức nhân là giờ thực |
| Stress | Đổi tỷ lệ xe máy, turning ratios | Dải thực nghiệm từ sai số/biến thiên dữ liệu; dải ngoài đó dán nhãn synthetic |
| Robustness | Noise/dropout cảm biến, đóng một làn hoặc mất năng lực một link | Cùng mức can thiệp và cùng realization cho các controller |
| Khả năng mở rộng | Cụm pilot → mạng Hải Châu mở rộng | Chỉ mở rộng khi có kiểm chứng demand và phase |

Tách ba nguồn bất định: ngày quan trắc, seed sinh demand/mô phỏng, seed huấn luyện RL. Split theo ngày hoặc buổi độc lập trước calibration/tuning; tránh chia random từng frame khiến cùng cảnh lọt cả train/test.

- Dành riêng dữ liệu calibration và validation mô phỏng; dành riêng train/validation/test policy. Có thể tái dùng phần train cho calibration theo thiết kế, nhưng không được dùng test policy để chỉnh mô phỏng/thuật toán.
- Mỗi test demand có seed và hash chung cho tất cả controller; baseline có randomness phải chạy theo seed riêng được ghi lại.
- Chọn checkpoint chỉ trên validation, test chạy sau khi khóa lựa chọn.
- Các rollout phải có warm-up, cửa sổ đo đủ dài và drain period. Giá trị pilot ứng viên: warm-up 15–30 phút, đo 60–120 phút, drain đến hết hoặc giới hạn công bố. Kiểm chứng warm-up bằng trạng thái mạng và quan trắc, không coi đây là con số chuẩn mặc định.
- Log scheduled/eligible departures, inserted, arrived, running, pending; kiểm tra bảo toàn xe và báo xe chưa hoàn tất. Đừng để controller có vẻ tốt chỉ vì giữ xe ngoài mạng.
- Pilot 3 training seed để debug/ước lượng variance; final tối thiểu dự kiến 5, ưu tiên 10 cho phương pháp chính nếu compute cho phép. Đây là ngân sách khởi điểm, không đảm bảo statistical power.
- Ghép cặp controller theo ngày/demand realization. Dùng CI cho chênh lệch, báo mean/median và per-run values. Bootstrap phân cấp theo ngày và training run; không coi mọi tổ hợp seed/ngày hay mỗi timestep là mẫu độc lập. Student-t chỉ dùng cho đơn vị mẫu độc lập phù hợp.
- Phân biệt so sánh chính và exploratory; xử lý multiple comparisons khi cần. Không suy ra “tương đương MP” chỉ vì kiểm định không có ý nghĩa; muốn claim tương đương phải đặt equivalence margin trước.

Metrics chính: cumulative stopped delay theo bước mô phỏng (vehicle-hours) và travel time trên cohort có định nghĩa rõ. Báo đồng thời throughput, tỷ lệ hoàn tất, pending departure/delay ngoài mạng, residual queues; không dùng riêng travel time của xe đã đến đích.

Metrics phụ: p95 waiting/travel time, queue trung bình/tối đa theo hướng, spillback duration, thời gian phục hồi, max-red, số lần chuyển pha, inference latency và thời gian train. Báo theo loại xe khi đủ dữ liệu; PCU hoặc person-delay chỉ dùng khi hệ số/occupancy có nguồn. Nêu rõ “waiting” là dừng dưới ngưỡng tốc độ hay time loss so với free flow.

## 8. Training, tuning và ablation

Trình tự: tái lập baseline → chạy pilot → khóa protocol → tuning trên validation → retrain nhiều seed → test giữ riêng → ablation và robustness đã định trước → tổng hợp cả kết quả thất bại.

Không chạy tích Descartes toàn bộ tham số. Random search hoặc successive halving có ngân sách ngang nhau cho các phương pháp; công bố chi phí tuning và tiêu chí pruning. Dải ứng viên ban đầu, sẽ khóa sau pilot:

| Tham số | Dải / lựa chọn ứng viên |
|---|---|
| Learning rate | 1e-4, 3e-4, 1e-3 |
| Discount | 0,95 / 0,99 / 0,995; báo decision interval tương ứng |
| Batch | 64 / 128 / 256 |
| Hidden size | 64 / 128 / 256 |
| Reward | queue, pressure, queue + spillback penalty |
| Normalization | Theo capacity hoặc thống kê train; kiểm tra lại các mức 5/10/40 lịch sử |
| Target update | Khoảng cập nhật theo số gradient steps, chọn sau pilot ổn định |
| Exploration | Schedule theo số quyết định, budget 20–50% giai đoạn khám phá là ứng viên |
| Control interval | 5 / 10 / 15 giây nếu signal constraints cho phép; các phương pháp so sánh cùng mức |

Ablation tối thiểu: local vs neighbor; không/có upstream arrivals; không/có downstream capacity/spillback; không/có domain randomization. Nếu không dùng attention thì không cần ablation attention. Dueling và n-step là kiểm tra bổ sung khi có câu hỏi cụ thể, không lặp tất cả experiment cũ.

Ngân sách: pilot đo simulated seconds/second, số update/episode, RAM, thời gian checkpoint/evaluation. Ước lượng tổng compute từ số cấu hình × seed × episode × thời lượng episode / tốc độ đo, cộng evaluation và dự phòng. Không cam kết số giờ train khi chưa đo. Ưu tiên máy CPU chạy simulator native; GPU chỉ hữu ích theo profiling. Không thuê cloud trả phí trong giai đoạn plan.

Mỗi run có run ID, git commit, config hash, network/demand hash, seed từng tầng, phiên bản simulator/dependencies, checkpoint được chọn, metrics/raw logs, thời gian chạy và trạng thái complete/failed. Resume dựa trên manifest khớp toàn bộ đầu vào, không chỉ sự tồn tại của `comparison.json`.

## 9. Literature và trích dẫn

`paper/guideline.txt` yêu cầu 50–70 references và tập trung tài liệu gần đây. Đề xuất tuyển chọn 50–70 nguồn thực sự được sử dụng, 5–7 công trình thuật toán đọc sâu, 15–25 nguồn related work trực tiếp; vẫn giữ các công trình nền tảng cũ cần thiết. Phần cập nhật tập trung 2023–2026 tính tại ngày khảo sát, phân biệt preprint với bài đã phản biện. Không bổ sung citation chỉ để đủ số lượng.

Danh sách khởi đầu đã tra nguồn, chưa phải systematic review hoàn tất:

| Nguồn | Dùng để làm gì | Trạng thái lượt khảo sát |
|---|---|---|
| [CoLight, Wei et al., 2019](https://arxiv.org/abs/1905.05717) | Phối hợp bằng graph attention; đối chiếu với mean-pool hiện có | Đã mở trang paper |
| [CityFlow, Zhang et al., 2019](https://arxiv.org/abs/1905.05217) | Simulator và khả năng mở rộng | Đã mở trang paper |
| [RESCO, Ault & Sharon, 2021](https://datasets-benchmarks-proceedings.neurips.cc/paper_files/paper/2021/hash/f0935e4cd5920aa6c7c996a5ee53a70f-Abstract-round1.html) | Benchmark, sensing và hình học nút không đồng nhất | Đã tìm nguồn proceedings |
| [Efficient Pressure, Wu et al., bản arXiv 2021](https://arxiv.org/abs/2112.02336) | Efficient-MP và biểu diễn pressure | Đã mở trang paper; kiểm tra bản xuất bản khi làm bib |
| [Advanced-XLight, Zhang et al., bản cập nhật 2022](https://arxiv.org/abs/2112.10107) | Running demand + queue/pressure | Đã mở trang paper; kiểm tra venue và phương trình từ full text |
| [Agarwal et al., NeurIPS 2021](https://arxiv.org/abs/2108.13264) | Bất định thống kê và đánh giá RL ít run | Đã tra abstract và nguồn tác giả |
| [Nguyen et al., T-REX, preprint 2025](https://arxiv.org/abs/2506.13836) | Incidents và generalization ngoài phân phối | Đã tra abstract; không gán venue chưa xác minh |
| [Ton et al., 2024](https://jst-ud.vn/jst-ud/article/view/8995) | Đầu mối dữ liệu/video Đà Nẵng | Đã mở trang bài; full PDF chưa tải được |

Cần bổ sung/đọc sâu: Varaiya về Max-Pressure và giả thiết ổn định; Webster/timed coordination; PressLight; SUMO publication và traffic-model calibration; nghiên cứu headway/saturation flow xe máy ở Việt Nam; công trình 2023–2026 trực tiếp xử lý coordination/robustness. Link PDF PressLight từ kết quả tìm kiếm bị 404 ở lượt này, cần tìm bản tác giả hoặc publisher trước khi trích phương trình.

Tạo evidence matrix: claim → paper → DOI/URL → trang/bảng/phương trình → dataset/giả thiết → kết quả liên quan → giới hạn → tác động thiết kế. Xác minh BibTeX với publisher/Crossref/arXiv, deduplicate theo DOI/title. Phân biệt “đã đọc full text”, “chỉ abstract”, “chưa truy cập”. Perplexity giúp tìm nguồn; câu trả lời AI không là nguồn học thuật cuối cùng.

## 10. MCP, Chrome extension và môi trường nghiên cứu

Trong phiên này đã thấy Perplexity MCP, Context7 MCP và Playwright MCP được cung cấp. Đã thử một truy vấn Perplexity, tool trả thành công nhưng `web_results` rỗng; dùng web search để tiếp tục xác minh nguồn. Đây chưa phải chứng nhận mọi tool Perplexity hoạt động với mọi loại truy vấn.

| Công cụ | Kế hoạch cho Sol |
|---|---|
| Perplexity MCP có sẵn | Smoke query đơn giản, xác nhận kết quả/citation; không cài trùng |
| Context7 có sẵn | Dùng khi cần tài liệu thư viện; kiểm tra callable trước khi dựa vào |
| Playwright / browser control có sẵn | Duyệt nguồn, xử lý trang cần browser; kiểm tra khả năng dùng phiên Chrome phù hợp |
| [Perplexity AI Companion](https://chromewebstore.google.com/detail/perplexity-ai-companion/hlgbcneanomplepojfcnclggenpcoldo) | Trang Chrome Web Store đã mở, liên kết nhà phát hành tới perplexity.ai; kiểm tra Chrome/profile và compatibility trước khi cài theo yêu cầu người dùng |
| [Zotero Connector](https://www.zotero.org/download/connectors) và Zotero | Đề xuất quản lý thư viện, lưu metadata/PDF và xuất BibTeX; kiểm tra ứng dụng hiện có trước |
| Zotero MCP, Crossref/OpenAlex/Semantic Scholar integration | Chỉ thêm nếu workflow thực sự thiếu khả năng; xác minh package/maintainer/quyền và thử với thư viện test. Chưa chọn hay xác nhận cài một server cụ thể |

Phân biệt extension Perplexity để hỗ trợ đọc web với bridge extension điều khiển Chrome của một automation tool. MCP không tự có quyền với mọi tab đã đăng nhập; tính phí API và subscription web cũng không mặc định dùng chung. Mọi việc cài đặt thực hiện ở bước triển khai theo phạm vi đã thống nhất, không làm trong lượt lập plan.

## 11. Các gói công việc bàn giao cho Sol

Mỗi gói phải báo: thay đổi, file liên quan, lệnh tái lập, kết quả kiểm tra, artifact và giới hạn. Thực hiện tuần tự theo phụ thuộc; chưa giao subagent hoặc chạy task trong phiên lập kế hoạch này.

| ID | Công việc và phạm vi | Phụ thuộc | Artifact và tiêu chí xong |
|---|---|---|---|
| T00 | Audit khả năng tái lập: commit, dữ liệu, checkpoint, toolchain; chạy test hiện có và một baseline ngắn sau khi vào triển khai | Chốt phạm vi pilot | `docs/research/reproducibility-audit.md`; phân biệt lỗi thật với docs cũ; hash artifacts lịch sử |
| T01 | Kiểm tra công cụ hiện có; thiết lập citation workflow và extension cần thiết | Bắt đầu triển khai | `docs/research/tooling.md`; có nguồn mẫu được lưu và bib export, không lộ credential |
| T02 | Literature search, full-text review, metadata/citation audit | Không cần dữ liệu thực | `docs/research/literature-matrix.*`, bibliographic audit; mỗi claim chính truy được nguồn |
| T03 | Data feasibility và thiết kế khảo sát | Thông tin tiếp cận dữ liệu | `docs/research/data-feasibility.md`, data dictionary và kế hoạch thu; xác định khu vực có số thật |
| T04 | Network audit, mapping, sửa hình học/phase cho pilot | T03 | Network version + báo cáo node/phase/turn QA; đối chiếu thực địa |
| T05 | Pilot CityFlow/SUMO và calibration; chọn backend | T00, T03, T04 | Calibration trên tập riêng, validation plot, tốc độ chạy; quyết định backend có chứng cứ |
| T06 | Đóng băng scenario split, metrics, constraints và manifest; sửa runner | T05 | `docs/research/experiment-protocol.md`; kiểm tra bảo toàn xe, thời gian, signal transition, test leakage |
| T07 | Tái lập và tune baseline | T02, T06 | Fixed/actuated/MP/shared-DQN + baseline mạnh; budgets và logs đầy đủ |
| T08 | Cài phương pháp phối hợp tối thiểu; pilot và tuning validation | T07 | Spec phương pháp, tests quan trọng, checkpoint pilot; không tuyên bố tính mới trước audit |
| T09 | Final multi-seed, test nhiều regime và ngày giữ riêng | T08, protocol đã khóa | Raw per-run metrics + manifests, toàn bộ runs hợp lệ hoặc lý do failure |
| T10 | Ablation, robustness, sensitivity và thống kê | T09 và kế hoạch đã đăng ký | CI/effect size, learning curves, heatmaps, queue/spillback/recovery; negative results đầy đủ |
| T11 | Viết lại thesis/paper, build LaTeX, kiểm tra số và citations | T02; kết quả T09–T10 cho phần thực nghiệm | Source + PDF, bảng/hình tái sinh từ raw results, không placeholder/claim vượt chứng cứ |
| T12 | Fresh-clone reproduction và demo/bảo vệ bắt buộc | Audit demo từ T00; export pilot từ T06; bản cuối theo T09–T11 | Bundle offline, 2D/3D A/B, video/ảnh fallback, kịch bản 5 phút, diễn tập và replay dùng đúng artifact |

Kiểm tra cần làm trong triển khai: unit/integration cho signal timing, metric accumulation, reset/seeding, route/demand validation, checkpoint preprocessing, split độc lập; smoke real simulator; đối chiếu thủ công một episode nhỏ. Không coi việc tất cả unit test pass là bằng chứng mô phỏng khớp thực địa.

## 12. Thesis cuối và tiêu chí nghiệm thu

Chương 1: bài toán, phạm vi Đà Nẵng, câu hỏi và đóng góp có thể kiểm chứng.

Chương 2: related work có bảng so sánh giả thiết, dữ liệu, action/state/reward, baseline và giới hạn; cập nhật tài liệu gần đây.

Chương 3: dữ liệu và calibration, network, formulation, phương pháp, constraints, pipeline tái lập.

Chương 4: protocol, baseline, tuning, kết quả giờ thường/cao điểm, generalization, ablation, robustness và chi phí tính toán.

Chương 5: diễn giải kết quả, kết quả âm, giới hạn mô phỏng và dữ liệu, điều kiện áp dụng; kết luận tương ứng đúng bằng chứng.

Phụ lục: manifests, per-seed results, hyperparameters, citation evidence, data dictionary, lệnh chạy. Một bản manuscript ngắn có thể rút từ thesis sau khi hoàn tất, không viết như đã có kết quả từ trước.

Nghiệm thu:

- Có quan trắc thật cho khu vực/khung giờ được tuyên bố, với nguồn và sai số; forecast/synthetic tách riêng.
- Mô phỏng được kiểm chứng trên dữ liệu giữ riêng; các giả thiết xe máy và tín hiệu nêu rõ.
- Controller so cùng demand, ràng buộc, metric, ngân sách; test chưa dùng để chọn model.
- Bảng/hình truy được raw logs, config, checkpoint và commit; có bất định thống kê phù hợp.
- Toàn bộ claim của abstract/conclusion khớp kết quả, kể cả trường hợp RL thua baseline.
- Có đường tái lập từ môi trường sạch và phương án truy cập dữ liệu hợp lệ.
- Demo bảo vệ chạy được khi ngắt Internet từ browser session mới, có fallback video/ảnh và đã diễn tập trên cấu hình trình chiếu; số trên demo truy được episode và khác biệt với aggregate được ghi rõ.

## 13. Thời gian dự kiến và quyết định còn cần chốt

Kế hoạch tham khảo 8–12 tuần sau khi có nguồn dữ liệu khả thi: tuần 1 audit/văn liệu/tooling; tuần 2–3 dữ liệu/network; tuần 3–4 pilot/calibration; tuần 5 protocol/baseline; tuần 6–8 training/ablation/robustness; tuần 9–10 viết và tái lập; phần dự phòng cho thu thập dữ liệu và compute. Đây là ước lượng kế hoạch, chưa gồm thời gian chờ cơ quan cấp dữ liệu và chưa cam kết wall-clock training. Có thể rút phạm vi về hành lang để phù hợp deadline.

Ba đầu vào làm thay đổi kế hoạch nhiều nhất: quyền tiếp cận dữ liệu Đà Nẵng; hạn nộp và bậc/yêu cầu thesis; CPU/GPU/RAM và ngân sách chạy. Câu hỏi về dữ liệu đã gửi trong phiên, chưa có câu trả lời tại lúc soạn bản này.

Điểm bàn giao: sau khi người dùng chọn hướng và bổ sung ràng buộc, Sol cập nhật bản này thành thiết kế được chấp thuận rồi chia kế hoạch triển khai chi tiết theo T00–T12. Ưu tiên đầu tiên là T00–T03. Chưa chạy full training trước khi chốt dữ liệu, simulator và protocol.
