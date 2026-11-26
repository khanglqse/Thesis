# Câu hỏi hội đồng và câu trả lời có bằng chứng

Cập nhật 23/09/2026. Đây là tài liệu chuẩn bị phản biện. Mỗi câu trả lời giới hạn theo bằng chứng hiện có; không biến thí nghiệm thăm dò thành xác nhận. Mở [sổ bằng chứng](../research/thesis-evidence-ledger.md), [báo cáo kiểm tra](../research/thesis-evidence-audit.json) và [PDF bài nguồn](../../datasets/danang_published/sources/phan2025_make7030065.pdf) khi cần đối chiếu.

## 1. Em tự thu thập dữ liệu hay sử dụng dữ liệu của người khác?

Em sử dụng dữ liệu đã công bố của Phan, Le và Nguyen (2025). Em chép Bảng 1 và dùng các giá trị đọc từ Hình 17–18 để dựng đầu vào mô phỏng. Em không tự quay camera, không có raw detector export và không nhận trực tiếp bộ dữ liệu của Sở Giao thông. Trang 23 bài nguồn nói dữ liệu gốc cần liên hệ tác giả. **Bằng chứng:** PDF trang 8, 20, 23; E03–E08 trong sổ bằng chứng.

## 2. Vì sao gọi là dữ liệu Đà Nẵng? Có đại diện toàn Hải Châu không?

Bài nguồn xác định một nút giao tại Đà Nẵng. Dữ liệu camera chỉ có bốn chuyển động tại nút đó, một ngày 01/04/2025. Dữ liệu không đại diện lưu lượng, OD hoặc lịch đèn toàn quận. Mạng 53 đèn dùng topology OSM và nhu cầu tổng hợp. **Bằng chứng:** PDF trang 16–20; E09–E10; `datasets/haichau_network_v2/provenance.json`.

## 3. Tên nút là Nguyễn Thanh Nghị hay Lê Thanh Nghị?

Bài nguồn không nhất quán: trang 7 viết `Nguyenthanhnghi`, nhưng Bảng 1, Hình 12 và tài liệu số 33 viết `Lethanhnghi`. Luận văn dùng Lê Thanh Nghị–Cách Mạng Tháng 8–2/9, phía cầu Hòa Xuân, và công khai sự khác biệt. Khi đối chiếu lưu lượng, em dùng NW/SE/NE/SW để tránh phụ thuộc lỗi chính tả. **Bằng chứng:** PDF trang 7, 8, 17, 24; README nguồn.

## 4. 6.171 là xe/giờ hay PCU/giờ? Có phải hoàn toàn đo trực tiếp không?

Đó là **PCU/giờ**, tổng 12 chuyển động trong Bảng 1. Trang 7 gán nguồn cho dữ liệu năm 2022; em chưa có dữ liệu gốc để xác nhận cách đo từng dòng. Nhãn mixed trong CSV là phân loại thận trọng của dự án. Bài báo nói ước lượng hướng ngoài camera trong phần năm 2025; không thể suy ra chắc chắn dòng nào của bảng năm 2022 đã được ước lượng. **Bằng chứng:** E03, E06, E07.

## 5. 2.330, 1.395, 2.400 lấy ở đâu?

Đó là tổng bốn cột loại xe trên bốn chuyển động tại các nhãn 08:00, 13:00, 17:00 trong CSV. Giá trị CSV được đọc và làm tròn từ Hình 17–18, nên đây là các tổng xấp xỉ từ dữ liệu đã số hóa. Chúng không phải tổng tất cả xe qua nút. **Bằng chứng:** E04–E05; lệnh `python3 scripts/audit_thesis_evidence.py` tính lại.

## 6. Sai số ±15/±30 có cơ sở thế nào? Đây có phải CI 95% không?

Đây là dung sai đọc biểu đồ do dự án đặt ra, không phải CI 95%, cũng không phải sai số YOLO/SORT được tác giả đo. Log tọa độ marker của lần số hóa ban đầu chưa được lưu. PDF gốc hiện được lưu để kiểm tra trực quan, nhưng em không khẳng định đã phục dựng toàn bộ quy trình số hóa hoặc đã truyền sai số đầu vào qua thí nghiệm. **Bằng chứng:** README dữ liệu, E04 và mục giới hạn trong audit.

## 7. Vì sao dùng một ngày mà chạy nhiều seed? Seed có phải nhiều ngày thật không?

Seed thay đổi khởi tạo/học của mô hình hoặc hiện thực hóa nhu cầu trong bộ sinh. Nó không tạo ra ngày khảo sát thực địa mới. Năm learning seed giúp mô tả biến thiên thuật toán trong các ca đã chọn; không đủ để ước lượng biến thiên giao thông giữa nhiều ngày. **Bằng chứng:** cấu hình split, E11 và E14.

## 8. Có bao nhiêu thí nghiệm chính?

SUMO có 120 bản ghi một giờ: 75 từ năm mô hình học × 15 ca và 45 từ ba baseline × 15 ca. Bộ sensitivity có 120 bản ghi; 30 ca ở mức 1,00 lặp lại kết quả điều kiện AM chính nên không được cộng thành 30 điều kiện độc lập mới. Mạng CityFlow có các đợt riêng, không cộng chung để tạo một cỡ mẫu thống kê. **Bằng chứng:** audit và các thư mục `evaluation`, `sensitivity`.

## 9. DDQN trong hai simulator có giống nhau không?

Không. SUMO dùng dueling Double DQN với n-step=3. Mạng dùng schedule-residual Double DQN: 27 đặc trưng, hai lớp 64 nút, đầu ra scalar chung, không có hai nhánh dueling. Mạng chọn chỉnh sửa lịch theo block 300 giây và dùng target semi-Markov. **Bằng chứng:** E15; snapshot cấu hình; `src/traffic_rl/agents/schedule_residual.py` và `phase_ddqn.py`.

## 10. Chỉ số xe·giờ có phải thời gian chờ trung bình một xe không?

Không. Em tích phân số xe đứng chờ trong mạng cộng số xe đã đến hạn nhưng chưa vào được mạng theo từng giây rồi chia 3.600. Chỉ số đo tổng tích lũy hàng đợi. Xe chưa tới giờ xuất phát không nằm trong pending. Không được phát biểu giảm 34,5% chỉ số này thành giảm 34,5% thời gian hành trình thực tế. **Bằng chứng:** phần metric trong luận văn và E11.

## 11. Tại sao cộng xe chờ ngoài mạng?

Nếu chỉ đếm hàng đợi bên trong, một controller chặn xe vào mạng có thể nhìn như ít tắc hơn. Cộng pending giúp hạn chế sai lệch đó. Em vẫn báo cáo insertion, completion và xe còn lại để biết hàng đợi có giảm bằng cách hy sinh phục vụ hay không. **Bằng chứng:** queue-objective trong cấu hình và E13.

## 12. Có phải RL tốt hơn fixed-time trong mọi tình huống?

Không. Ở nút đơn, normal tăng queue integral 320,7%; AM chưa phân biệt được với fixed-time; PM giảm 34,5%. Khoảng AM chứa 0 không chứng minh hai phương pháp tương đương. Đây là bằng chứng về phụ thuộc chế độ nhu cầu. **Bằng chứng:** E11, bảng kết quả SUMO.

## 13. Max-Pressure tốt hơn thì lý do gì dùng RL?

Trong ma trận mạng hiện có, Max-Pressure giảm 23,89% so với fixed-time, tốt hơn residual DDQN 6,12%. Em báo cáo kết quả đó và không đề xuất RL là lựa chọn vận hành tốt nhất từ bằng chứng hiện tại. Giá trị nghiên cứu gồm xây dựng và đánh giá controller có ràng buộc lịch, mô tả failure modes, và xác định điều kiện cần nghiên cứu thêm. **Bằng chứng:** E13; bảng so sánh bốn controller.

## 14. Vì sao Max-Pressure kém ở nút đơn nhưng tốt ở mạng?

Hai mô hình có cấu trúc, quan sát, nhu cầu, phase và chi phí chuyển khác nhau. Việc thứ hạng đổi theo kịch bản là kết quả quan sát được. Các giải thích về partial coverage và chuyển phase là giả thuyết cơ chế; chưa có ablation tách từng yếu tố để chứng minh nguyên nhân. Em không dùng một thí nghiệm để bác bỏ lý thuyết Max-Pressure. **Bằng chứng:** E11, E13 và phần Threats to validity.

## 15. Tại sao 8,86% và 10,39% đều xuất hiện cho PM seed 14?

8,86% là trung bình không trọng số của năm phần trăm cải thiện từng ca. 10,39% được tính sau khi cộng queue của năm ca rồi lấy tỷ lệ giảm. Ca có queue lớn có trọng số lớn hơn ở cách thứ hai. Luận văn hiện ghi rõ hai mẫu số. **Bằng chứng:** E13 và `final15-seed14-step4-summary.json` so với controller matrix.

## 16. 3,48% là cả ngày 24 giờ hay gì?

Đó là mức giảm gộp qua 15 ca một giờ, mỗi ca reset riêng, sau đó lấy trung bình qua năm seed. Tên `full_day` trong JSON cũ là tên trường lịch sử; luận văn dùng “pooled-case”. Không có thí nghiệm liên tục chuyển normal→AM→PM trong 24 giờ. **Bằng chứng:** công thức E14, horizon và case IDs.

## 17. Vì sao chỉ dùng RL trong PM? Có xem test để chọn không?

Có. Quy tắc giữ fixed-time ở normal/AM và bật residual trong PM hình thành sau khi xem các kết quả test. Em gọi đây là **thăm dò sau phân tích**, không phải đánh giá xác nhận độc lập. Chạy lại controller trên cùng ca xác minh thực thi, không xóa được việc đã dùng test để chọn quy tắc. **Bằng chứng:** trình tự kết quả trong luận văn, E14.

## 18. Năm seed có đều đạt validation không?

Không. Seed 12, 14, 15 được chọn; seed 13 và 16 bị từ chối. Các checkpoint chẩn đoán của 13/16 vẫn được replay để thăm dò PM. Điều đó không chuyển trạng thái chúng thành đạt validation. **Bằng chứng:** snapshot `seed13-selection.json`, `seed16-selection.json`; trường `status: rejected`, `winner: null`; E14.

## 19. CI 95% dương có đủ chứng minh không?

CI [2,01%; 4,95%] mô tả trung bình năm hiệu ứng trong bộ ca đã chọn. Nó không điều chỉnh lựa chọn gate sau khi xem test, checkpoint chẩn đoán, sai số digitization hay simulator mismatch. Vì vậy em không gọi nó là bằng chứng xác nhận hiệu quả tổng quát. **Bằng chứng:** script bootstrap, E14 và phần giới hạn thống kê.

## 20. Có phải gate cải thiện cả 75 ca?

Không. 50 ô normal/AM bằng fixed-time do thiết kế. Trong 25 ô PM, 15 cải thiện và 10 xấu đi. “Cả năm seed có tổng dương” khác với “mọi ca đều cải thiện”. **Bằng chứng:** số regression theo seed ở E14.

## 21. Mô hình biết lúc nào là PM bằng cách nào?

Thí nghiệm cấp sẵn nhãn operational regime. Nó không đánh giá một bộ nhận dạng chế độ nhu cầu từ camera hay sensor. Sai nhãn và chuyển chế độ theo thời gian chưa được kiểm tra, nên không có claim về tự phát hiện PM ngoài thực địa. **Bằng chứng:** trường `operational_mode.input: declared_time_of_day` trong resolved config.

## 22. Chứng minh neighbor-aware hoặc dueling tạo ra cải thiện ở đâu?

Chưa có thí nghiệm hiện tại đủ để quy kết từng thành phần. Ablation SUMO chỉ một seed và thay đổi đồng thời dueling cùng n-step. Mạng chưa có matched multi-seed ablation bỏ neighbor features; residual còn không dùng dueling heads. RQ và contribution đã chỉnh để không hứa một kết luận nhân quả chưa được đo. **Bằng chứng:** phần Methodology và E15.

## 23. Không có collision có nghĩa là an toàn không? Đổi tau sau test thì sao?

Zero collision chỉ là số sự kiện ghi nhận trong những mô phỏng này. Nó không kiểm chứng hành vi xe máy, người đi bộ hoặc an toàn ngoài đường. Tau 1,2 s là điều chỉnh kỹ thuật sau một failure trên held-out case; chạy lại toàn bộ giúp nhất quán cấu hình nhưng không phục hồi bộ test chưa từng được nhìn. Cần ca mới sau khi khóa simulator để xác nhận. **Bằng chứng:** `tau_sensitivity.json`, E11, Threats to validity.

## 24. Hash và verifier chứng minh được gì? Vì sao strict vẫn fail?

Hash chứng minh đúng file đã giữ; audit đối chiếu số liệu và nguồn. Strict verifier yêu cầu một gói protocol/campaign/checkpoint/runtime/clean-checkout đầy đủ. Gói cuối còn thiếu và hai seed không đạt selector. Em giữ nguyên trạng thái fail và không dùng cờ presentation-ready làm bằng chứng khoa học. **Bằng chứng:** `thesis-evidence-audit.json` và lệnh verifier `--no-write`.

## 25. Có chạy robustness 420 ca như phần thiết kế không?

Chưa có kết quả hoàn tất 420 lượt cho controller residual/gated hiện tại. Phần đó là kế hoạch. Các file robustness cũ thuộc protocol khác nên không được dùng để xác nhận robustness của model này. Sensitivity SUMO đã hoàn tất được báo cáo riêng. **Bằng chứng:** Methodology mới, E12 và bảng trạng thái trong ledger.

## 26. Đóng góp mới so với Phan et al. là gì?

Em không nhận là người đầu tiên áp dụng dueling Double DQN tại nút này. Phần đóng góp là tái dựng có truy vết bằng chứng, đánh giá nhiều learning seed và baseline, tính cả pending demand, công khai điều kiện thất bại, và mở rộng thành benchmark 53 đèn với nguồn gốc synthetic rõ ràng. Chưa có bằng chứng để nhận là thuật toán tốt nhất hoặc chứng minh lợi ích giao thông thực địa. **Bằng chứng:** bài nguồn; phần Contributions đã sửa.

## 27. Demo thấy ít hơn 13 xe chờ thì có phải đã giải phóng thêm 13 xe?

Không thể suy ra vậy từ một frame. Đó là chênh lệch queue tại một thời điểm; có thể liên quan lượng xe đến, rời nút hoặc còn đang di chuyển. Em nói “ít hơn 13 xe đang chờ tại frame này”, rồi dẫn kết quả full-horizon cho kết luận tổng hợp. **Bằng chứng:** demo manifest/replay và hướng dẫn demo.

## 28. Nếu cần xác nhận thêm thì làm gì cụ thể?

Khóa model, quy tắc gate, selector, baseline, chỉ số và cách phân tích trước; đánh giá trên bộ demand chưa dùng để ra quyết định; báo cáo tất cả seed và trường hợp fail theo quy tắc đã khóa; giữ Max-Pressure trong so sánh. Thu thập thêm nhiều ngày, đủ chuyển động và queue/travel-time nếu muốn chuyển sang claim thực địa. Không thay checkpoint hoặc nới gate sau khi thấy test mới. **Bằng chứng:** mục 4 trong ledger; đây là yêu cầu nghiên cứu tiếp theo, không phải công việc đã hoàn thành.

## 29. Tài liệu tham khảo đã được xác thực tới mức nào?

49 mục có DOI đã khớp tên bài với metadata Crossref; họ tác giả và năm cũng được rà soát. 18 mục khác có nguồn publisher/proceedings/kho tác giả hoặc báo cáo chính thức. Mục SURTRAC được sửa tên bài, tác giả và hội nghị từ bản ghi CMU. Riêng bản gốc Webster 1958 chưa lấy được; thông tin được đối chiếu gián tiếp qua FHWA và chỉ dùng làm bối cảnh lịch sử. Đối chiếu metadata không có nghĩa đã kiểm chứng toàn văn mọi phát biểu. Các nguồn tạo dữ liệu thí nghiệm được kiểm tra riêng tới trang/bảng/hình. **Bằng chứng:** `docs/research/bibliography-metadata-audit.json`, mục 3 trong ledger.
