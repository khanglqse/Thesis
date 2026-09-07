# Thiết kế nền tảng nghiên cứu thesis Đà Nẵng

Ngày: 2026-09-07. Trạng thái: thiết kế phục vụ bước lập kế hoạch tiếp theo theo phản hồi “ok, tiếp tục plan đi”. Người dùng chưa yêu cầu triển khai trong phiên này. Simulator cuối, dataset và thuật toán mở rộng được quyết định bằng chứng cứ từ pilot.

Nguồn yêu cầu: [roadmap](../plans/2026-09-07-danang-thesis-research-roadmap.md). Tiểu dự án này bao phủ T00–T03; kết quả là hồ sơ tái lập, văn liệu và khả năng dùng dữ liệu. Không có training chính thức trong phạm vi tiểu dự án.

## 1. Các quyết định làm cơ sở lập kế hoạch

- Hướng mặc định: giữ CityFlow/shared DQN làm mốc lịch sử, đánh giá SUMO sublane trên pilot trước khi đổi backend.
- Chọn khu vực theo dữ liệu: một cụm 4–8 nút liên thông trước khi mở rộng mạng 53 nút hiện có.
- Giao thông thực gồm số xe theo thời gian, hướng và loại xe; số đăng ký phương tiện hoặc forecast không thay thế count quan trắc.
- Độ tin cậy dữ liệu và benchmark có giá trị ngay cả khi RL không vượt MP. Không lấy mức cải thiện cũ làm ngưỡng nghiệm thu.
- Chưa biết deadline và quyền tiếp cận dữ liệu; dùng nhánh quyết định trong tài liệu này để tiếp tục phần độc lập.
- Khi thực thi, Sol làm từng gói và báo artifact; không mặc định khởi chạy subagent hoặc mọi training job.
- Demo lúc presentation là đầu ra bắt buộc theo yêu cầu bổ sung của người dùng; audit và chốt replay export từ giai đoạn nền tảng, không đợi viết xong thesis. Xem [defense demo spec](2026-09-07-danang-defense-demo-design.md).

## 2. Global Constraints

- Chỉ thay đổi tài liệu kế hoạch trong phiên planning; không cài công cụ hoặc chạy learning.
- Bảo toàn `results/references/`, checkpoint và dữ liệu lịch sử; mọi kết quả mới có thư mục riêng.
- Không đưa số liệu chưa xác minh vào thesis dưới nhãn quan trắc thực tế.
- Không dùng dữ liệu test để hiệu chỉnh mô phỏng, tune baseline, chọn tham số hoặc chọn checkpoint.
- Không gửi email, tin nhắn hoặc yêu cầu dữ liệu tới người khác nếu chưa được người dùng cho phép gửi.
- Không tự mua dịch vụ, thuê cloud hoặc suy ra ngân sách từ subscription đang có.
- Báo thiếu dữ liệu là thiếu dữ liệu; không thay bằng zero hoặc confidence interval bằng zero.
- Mọi claim định lượng có đường dẫn nguồn hoặc artifact và nêu đúng đơn vị, phạm vi, thời gian.

## 3. Hiện trạng môi trường đã kiểm tra chỉ đọc

Host trả về Apple M4 Pro, 12 CPU logical, 25.769.803.776 bytes RAM = 24 GiB. `python3` hiện trỏ tới Python 3.13; `docker`, `colima`, `sumo`, `netconvert` có executable trong PATH. Chưa kiểm tra daemon Docker, phiên bản/chức năng simulator hay tốc độ chạy. `latexmk` và `pdflatex` không tìm thấy trong PATH lúc kiểm tra; chưa kết luận máy không có bộ TeX ở vị trí khác.

Hệ quả: chưa có lý do mua compute; ưu tiên benchmark local trước. Thời gian dự kiến 8–12 tuần trong roadmap vẫn chỉ là giả định kế hoạch. GPU chưa được benchmark; không đánh đồng số lõi CPU với số worker simulator tối ưu.

## 4. Hồ sơ đầu ra và trách nhiệm

| File tạo khi triển khai | Nội dung |
|---|---|
| `docs/research/status.md` | Bảng task, trạng thái, artifact và blocker có điều kiện |
| `docs/research/reproducibility-audit.md` | Môi trường, test, dataset/checkpoint, câu lệnh và hạn chế tái lập |
| `docs/research/legacy-claims-audit.md` | Đối chiếu claim trong paper/docs với code/artifact |
| `docs/research/tooling.md` | Tool nào có sẵn/đã thử/cần cài; kiểm tra citation workflow |
| `docs/research/search-protocol.md` | Query, ngày tìm, cơ sở dữ liệu, tiêu chí chọn/loại |
| `docs/research/literature-matrix.jsonl` | Một công trình mỗi dòng JSON; bằng chứng và giới hạn |
| `docs/research/bibliography-audit.md` | Sai metadata, nguồn thiếu, duplicate theo công trình, cited/uncited |
| `docs/research/data-sources.jsonl` | Một nguồn dữ liệu mỗi dòng; phân biệt khả dụng và đầu mối |
| `docs/research/data-feasibility.md` | Khu vực ưu tiên, độ phủ, nhánh dữ liệu và quyết định tiếp theo |
| `docs/research/survey-protocol.md` | Phương pháp thu thập, manual validation, đơn vị và split |
| `docs/research/foundation-handoff.md` | Quyết định, bằng chứng, gói tiếp theo có thể chạy |
| `docs/research/demo-readiness-audit.md` | Browser dependencies, replay artifacts, số liệu, 2D/3D và đường khởi động offline |

Log máy đọc được đặt dưới `results/research_foundation/<run-id>/`; raw traffic data sau này dưới `data/research/raw/` theo quyền dữ liệu. Hồ sơ nguồn có thể version trong Git; không tự đưa video hoặc dữ liệu hạn chế vào Git. Dùng JSONL để không phát sinh hệ quản trị dữ liệu/công cụ spreadsheet cho một registry nhỏ.

## 5. Hợp đồng hồ sơ văn liệu

Mỗi dòng `literature-matrix.jsonl` có các trường:

```json
{
  "paper_id": "ton2024danang_mot",
  "title": "Optimizing traffic management in Danang: a comparative study of multi-object tracking techniques for real-time vehicle flow monitoring",
  "doi": "10.31130/ud-jst.2024.022ICT",
  "url": "https://jst-ud.vn/jst-ud/article/view/8995",
  "year": 2024,
  "publication_status": "journal",
  "reading_status": "abstract_only",
  "topics": ["danang", "vehicle_tracking", "data_source"],
  "evidence": [{"claim": "Bài báo mô tả một dataset giao thông Đà Nẵng", "locator": "Abstract", "verification": "publisher_page"}],
  "limitations": ["Chưa xác nhận khả năng truy cập dataset và turning counts"],
  "implementation_relevance": "Đầu mối dữ liệu; không dùng chỉ số tracking làm sai số đếm xe",
  "code_url": null,
  "data_url": null,
  "accessed_on": "2026-09-07"
}
```

`reading_status`: `metadata_only | abstract_only | full_text`. `publication_status`: `journal | conference | preprint | report | documentation | unverified`. DOI/code/data URL không có thì `null`; không tự sinh. Mỗi locator trong full-text review ghi page/section/table/equation. Tên tác giả đầy đủ và BibTeX publisher ghi trong hồ sơ bibliographic audit hoặc trường bổ sung `authors`/`bibtex`; không bắt buộc nhồi metadata chưa tra xong vào record.

Giai đoạn nền tảng hoàn thành một core review 8–12 công trình thực sự đọc full text, hoặc báo chính xác công trình không truy cập được và lựa chọn thay thế. Nhóm phải phủ pressure baseline, phối hợp, calibration/xe máy, đánh giá RL và robustness. Mốc 50–70 references áp cho thesis cuối, không phải điều kiện bắt buộc để chạy pilot.

## 6. Hợp đồng nguồn và số đếm xe

`data-sources.jsonl`: `source_id`, `title`, `url`, `source_kind`, `access_status`, `rights_status`, `spatial_coverage`, `temporal_coverage`, `units`, `vehicle_classes`, `measurement_method`, `raw_file_sha256`, `limitations`, `next_action`.

- `source_kind`: `observed_counts | observed_video | observed_signal_plan | historical_report | forecast | synthetic`.
- `access_status`: `downloaded | public_link_unchecked | request_required | unavailable`.
- `rights_status`: `verified_public_use | permission_granted | unclear | restricted`.
- Hash chỉ có khi đã có file; thiếu thời gian/phạm vi dùng `null` và ghi hạn chế.
- Nguồn chỉ đủ làm bối cảnh phải được ghi rõ; không tự nâng sang nguồn calibration.

Hợp đồng một observation dùng cho bước dữ liệu sau này:

```text
observation_id, source_id, observation_group_id,
site_id, approach_id, movement_id, vehicle_class,
start_time, end_time, count, coverage_fraction,
measurement_method, quality_flag
```

`start_time/end_time` là ISO 8601 có offset `+07:00`; khoảng đo là `[start_time, end_time)`. `count` là số nguyên không âm, `null` khi không đo được, không phải PCU. `coverage_fraction` trong [0,1] ghi tỷ lệ thời gian quan sát; thiếu thì không tự ngoại suy. Phân biệt movement đếm tại nút với external inflow và trip OD: cùng xe có thể qua nhiều nút, không cộng tất cả movement counts thành unique trips.

`observation_group_id` nhóm toàn bộ camera/clip liên quan cùng buổi hoặc ngày để không bị chia sang các tập độc lập giả. File phase plans có timestamp riêng; traffic count không thay thế thông tin pha.

## 7. Các nhánh dữ liệu và điều kiện chuyển giai đoạn

| Nhánh | Bằng chứng tối thiểu | Việc Sol tiếp tục |
|---|---|---|
| D1: Có counts và signal/network phù hợp | Đã có file, hiểu đơn vị, vị trí và thời gian | Network mapping + pilot calibration |
| D2: Có video, chưa có counts | Quyền sử dụng rõ, nhìn được movements, đủ timestamp | Protocol manual count; thử tracker trên mẫu và đo sai số count |
| D3: Chỉ có nguồn lịch sử | Có bảng/page kiểm tra được, biết năm và vị trí | Case study theo năm nguồn; không gọi đại diện giao thông 2026 |
| D4: Chưa có dữ liệu đủ dùng | Search/access log cho các nguồn đã thử | Khảo sát có kế hoạch + pilot kỹ thuật synthetic; treo claim thực tế |

Không liên tục tìm nguồn vô hạn: đợt đầu giới hạn 2 ngày công chủ động; nếu chưa có nguồn đủ dùng, xuất hồ sơ D4 với 2–3 đường tiếp cận cụ thể. Đây là mốc báo cáo và đổi cách làm, không phải cho phép hoàn thành yêu cầu dữ liệu thật bằng synthetic.

Điều kiện mở full study: có calibration observations, dữ liệu validation độc lập phù hợp, profile normal/AM/PM có chứng cứ, network/signal QA, protocol seed/split/metrics và budget đo được. Nếu chỉ đủ một nút hoặc một ngày thì thu hẹp cấp độ kết luận, không tuyên bố benchmark nhiều ngày.

## 8. Phân tách kế hoạch còn lại

T04–T06 là tiểu dự án network/calibration/experiment infrastructure; T07–T10 là tiểu dự án benchmark/learning; T11–T12 là thesis/reproduction. Mỗi phần được viết implementation plan sau khi đầu vào có thật. [Thiết kế campaign](2026-09-07-danang-experiment-campaign-design.md) xác định sẵn đầu ra, ma trận và điều kiện chọn; không giả vờ đã biết route, simulator version, hoặc budget training tối ưu.

Phương pháp calibration tham chiếu [FHWA Traffic Analysis Toolbox III, chương 5, bản 2019](https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter5.htm). Dùng quy trình đặt mục tiêu theo quan trắc và kiểm tra biến thiên; việc đạt tiêu chí trong guideline không tự chứng nhận mô phỏng xe máy Đà Nẵng.
