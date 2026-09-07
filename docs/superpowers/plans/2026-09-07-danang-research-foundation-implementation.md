# Da Nang Research Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Người dùng dự định giao Sol thực thi ở lượt sau; không tự dispatch subagent hoặc chạy task trong lượt planning.

**Goal:** Tạo hồ sơ nguồn, văn liệu và khả năng tái lập đủ để quyết định pilot Đà Nẵng mà không dựa vào lưu lượng giả định được gắn nhãn thực.

**Architecture:** Giữ code và artifacts nghiên cứu cũ làm đối chiếu. Thực hiện audit và lưu evidence bằng Markdown/JSONL; dùng thư mục output riêng cho smoke. Đầu ra là quyết định dữ liệu và phạm vi pilot, không phải model mới.

**Tech Stack:** Repo Python/NumPy hiện có; Git; CityFlow qua Docker nếu môi trường dùng được; công cụ web/MCP có sẵn; Markdown, JSON/JSONL, BibTeX. Không thêm framework trong giai đoạn này.

**Spec:** [Foundation design](../specs/2026-09-07-danang-research-foundation-design.md), đọc cùng [roadmap](2026-09-07-danang-thesis-research-roadmap.md).

## Global Constraints

- Chỉ thay đổi tài liệu kế hoạch trong phiên planning; không cài công cụ hoặc chạy learning.
- Bảo toàn `results/references/`, checkpoint và dữ liệu lịch sử; mọi kết quả mới có thư mục riêng.
- Không đưa số liệu chưa xác minh vào thesis dưới nhãn quan trắc thực tế.
- Không dùng dữ liệu test để hiệu chỉnh mô phỏng, tune baseline, chọn tham số hoặc chọn checkpoint.
- Không gửi email, tin nhắn hoặc yêu cầu dữ liệu tới người khác nếu chưa được người dùng cho phép gửi.
- Không tự mua dịch vụ, thuê cloud hoặc suy ra ngân sách từ subscription đang có.
- Báo thiếu dữ liệu là thiếu dữ liệu; không thay bằng zero hoặc confidence interval bằng zero.
- Mọi claim định lượng có đường dẫn nguồn hoặc artifact và nêu đúng đơn vị, phạm vi, thời gian.

Các lệnh dưới đây là hướng dẫn cho phiên **thực thi sau này**. Không phải nhật ký lệnh đã chạy. Mỗi task kết thúc bằng cập nhật `docs/research/status.md`, kiểm tra diff và commit đúng file của task khi đã vào workflow triển khai; không stage toàn repo.

## Map file và thứ tự

Task F0–F2 = T00; F3 = T01; F4 = T02; F5–F6 = T03. Đường phụ thuộc: F0 → F1/F2; F3 và F4 có thể làm mà chưa có simulator; F5 → F6. Sol làm tuần tự, chuyển sang việc độc lập khi một nhánh bị thiếu dữ liệu.

Không tạo package Python mới trong giai đoạn nghiên cứu này. Test là chạy bộ test hiện có, kiểm tra evidence và kiểm tra thủ công schema/metadata; không viết unit tests cho Markdown.

## F0: Ghi snapshot và đường chạy audit

**Files:** tạo `docs/research/status.md`, `docs/research/reproducibility-audit.md`; tạo artifacts dưới `results/research_foundation/<run-id>/`; đọc `Makefile`, `pyproject.toml`, `requirements*.txt`, `.gitignore`.

**Interfaces:** nhận repo hiện tại; xuất root output đã tạo, commit và manifest SHA256 của inputs/artifacts. Tất cả task sau lấy đường dẫn output từ `status.md`, không tự đoán tên.

- [ ] Đọc `AGENTS.md` nếu xuất hiện mới; ghi `git status --short`, `git rev-parse HEAD`, `git branch --show-current`. Không xóa untracked files hay reset thay đổi người dùng.
- [ ] Tạo thư mục audit duy nhất và manifest bằng đoạn lệnh dưới. Chạy từ repo root, không đưa `.env`, cấu hình tài khoản hay browser profile vào hồ sơ.

```bash
python3 - <<'PY'
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
out = Path('results/research_foundation') / stamp
out.mkdir(parents=True, exist_ok=False)
roots = ['data', 'osm_danang', 'results/references']
manifest = {}
for root in roots:
    for p in sorted(Path(root).rglob('*')):
        if p.is_file() and not p.is_symlink():
            h = hashlib.sha256()
            with p.open('rb') as f:
                for block in iter(lambda: f.read(1024 * 1024), b''):
                    h.update(block)
            manifest[str(p)] = {'sha256': h.hexdigest(), 'bytes': p.stat().st_size}
(out / 'inputs-before.json').write_text(json.dumps(manifest, indent=2))
print(out)
PY
```

- [ ] Ghi hardware và executable versions, không dump toàn bộ environment variables: `python3 --version`, `sumo --version`, `netconvert --version`, `docker version`. Nếu Docker daemon chưa chạy, ghi đúng trạng thái và tiếp tục phần không cần daemon.
- [ ] Kiểm tra `docker image inspect cityflowproject/cityflow:latest` khi image có sẵn, lưu ID/RepoDigest và kiến trúc. Nếu thiếu image thì bước cài đặt thuộc F3, không ghi giả một digest.
- [ ] Phân loại files: tracked trong Git; local-only tái tạo được; local-only cần cung cấp; artifact thiếu. Kiểm tra OSM snapshot và checkpoint thực sự có thể tải/tái tạo.
- [ ] Cập nhật audit: yêu cầu môi trường tối thiểu dựa trên lệnh đã chạy, chỗ không tái lập được, đường dẫn manifest.

**Done:** biết chính xác những gì có, thiếu và cần bảo toàn; không gọi fresh-clone reproducible chỉ vì máy hiện tại có dữ liệu local.

## F1: Kiểm tra tests và smoke simulator có output riêng

**Files:** đọc `tests/`, `scripts/import_check.py`, `src/traffic_rl/sim/`, `agents/fixed_time.py`; cập nhật `docs/research/reproducibility-audit.md`. Chỉ tạo log/config trong output F0.

**Interfaces:** dùng root output F0 và scenario `data/danang/*_subarea.json`; xuất log pytest, import check và smoke metric. Smoke là kiểm tra kỹ thuật, không phải kết quả nghiên cứu.

- [ ] Chạy `python3 -m pytest --version`. Nếu thiếu dependency, khi đã vào triển khai tạo `venv/research` và cài đúng dependency cần cho test; không cài nguyên requirements legacy vào môi trường global. Ghi phiên bản đã dùng.
- [ ] Chạy `python3 -m pytest -m 'not docker' -v`. Lưu exit code, số collected/passed/failed/skipped và lý do skip. Lỗi import trong collection là lỗi test suite, không phải pass.
- [ ] Nếu CityFlow image dùng được, chạy import check qua `make cf-run CMD="PYTHONPATH=src python3 scripts/import_check.py"`. Ghi digest của image thực sự chạy. Không sửa toàn bộ môi trường trong task này để che mất lỗi ban đầu.
- [ ] Chạy smoke ngắn bằng lệnh dưới với biến `RESEARCH_RUN_DIR` trỏ tới output F0. Đoạn này được pipe vào container, không sửa script hiện có vốn ghi đè `results/<scenario>/`.

```bash
: "${RESEARCH_RUN_DIR:?Set the relative output path created by F0}"
docker run --rm -i \
  -v "$PWD":/work:ro \
  -v "$PWD/$RESEARCH_RUN_DIR":/audit \
  -w /work -e PYTHONPATH=src \
  cityflowproject/cityflow:latest python3 - <<'PY'
import json, time
from traffic_rl.network.roadnet import RoadNet
from traffic_rl.sim.engine import CityFlowEngine
from traffic_rl.sim.multi_agent_env import MultiAgentTrafficEnv
from traffic_rl.agents.fixed_time import FixedTimeController
from traffic_rl.eval.runner import run_episode
cfg = {'interval': 1.0, 'seed': 0, 'dir': '/work/data/danang/',
       'roadnetFile': 'roadnet_subarea.json', 'flowFile': 'flow_subarea.json',
       'rlTrafficLight': True, 'laneChange': False, 'saveReplay': False}
path = '/audit/smoke-cityflow-config.json'
with open(path, 'w') as f:
    json.dump(cfg, f)
rn = RoadNet.load('/work/data/danang/roadnet_subarea.json')
env = MultiAgentTrafficEnv(rn, CityFlowEngine(path), max_steps=60)
start = time.monotonic()
row = run_episode(env, FixedTimeController(env.num_actions))
row['wall_seconds'] = time.monotonic() - start
row['purpose'] = 'technical_smoke_only'
assert row['steps'] == 60
assert row['final_vehicle_count'] >= 0
with open('/audit/smoke-cityflow.json', 'w') as f:
    json.dump(row, f, indent=2)
print(json.dumps(row))
PY
```

- [ ] Nếu image thiếu `dataclasses`/NumPy, ghi failure rồi xử lý dependency image trong F3 và chạy lại smoke; không sửa kết quả fail thành pass. Không chạy full comparison/training như cách smoke thay thế.
- [ ] Kiểm tra lại SHA256 của từng file trong manifest F0 bằng cùng thuật toán, so map đường dẫn → hash; mọi thay đổi ngoài phạm vi phải được giải thích trước khi tiếp tục.
- [ ] Audit demo theo [defense demo spec](../specs/2026-09-07-danang-defense-demo-design.md): đọc `frontend/replay_ab.html`, `frontend/replay_3d.html`, scripts và dependencies; tạo `docs/research/demo-readiness-audit.md`. Kiểm tra data files có trong bundle, launcher mở đúng trang và không phụ thuộc CDN; legacy `frontend/index.html` hiện có CDN nên không mặc định dùng nó làm đường chạy offline.
- [ ] Chạy `node --test tests/replay_ab/*.test.cjs tests/replay_3d/*.test.cjs` khi Node dùng được; ghi kết quả mới. Mở 2D/3D bằng browser, kiểm tra play/pause/seek, camera có xe, cùng timestamp A/B và console; xem đây là audit demo legacy, chưa chứng nhận demo cho kết quả mới.

**Done:** tests và smoke có bằng chứng pass hoặc failure cụ thể. Failure không ngăn F4–F5; phải được xử lý trước khi gọi simulator đáng tin cậy để chạy nghiên cứu.

## F2: Kiểm toán claim và định nghĩa metric cũ

**Files:** tạo `docs/research/legacy-claims-audit.md`; đọc `paper/trafic_rf.tex`, `paper/chapter4_experiments_results.tex`, `docs/scenario_regimes.md`, `docs/danang_peak_demo_scenario.md`, `src/traffic_rl/eval/`, `train/trainer.py`, `scripts/train_dqn.py`, `scripts/run_experiment_eval.py`.

**Interfaces:** nhận source/artifacts hiện tại; xuất bảng `claim | location | evidence | verdict | required_change`. Verdict: `supported_in_legacy_protocol | overclaimed | inconsistent | unverified`.

- [ ] Lập dòng audit riêng cho: 53 nút thật/suy đoán; số xe 50.500; demand thực; tỷ lệ xe máy; 37,1%; CI; so MP; coordination; signal safety; travel time; robustness incidents.
- [ ] Tái tính lịch xe từ flow bằng `startTime`, `endTime`, `interval`, tách `[0,1000)` và toàn lịch. Ghi semantics endpoint của file/engine sau khi kiểm tra source simulator; không coi scheduled departures là inserted vehicles.
- [ ] Theo trace hiện tại, chứng minh waiting-hours = `sum(queue_series) * 10 / 3600`; ghi đó là sampling theo decision. Kiểm tra reward, `mean_reward`, queue và travel time có cùng ý nghĩa với mô tả không.
- [ ] Kiểm tra seed, đường flow train/eval, early stopping và preprocessing checkpoint. Đặc biệt metadata hiện chưa lưu đầy đủ `count_norm`, constraints và mọi config; đưa vào yêu cầu runner mới.
- [ ] Đối chiếu pressure/efficient pressure trong `sim/intersection.py` và MP trong `agents/max_pressure.py` với công thức paper. Không kết luận tương đương chỉ dựa tên hàm.
- [ ] Đánh dấu unit tests đang kiểm tra all-red mặc dù tên gọi yellow; max-red chưa được chứng minh; env step counting và action interval cần audit khi dt thay đổi.
- [ ] Xếp sửa theo mức tác động: làm sai kết luận; làm sai tính tái lập; mô tả chưa chính xác. Chưa sửa paper hàng loạt trước khi có protocol/kết quả mới; chỉ lưu audit.

**Done:** các headline cũ có verdict cụ thể, có file/line và không dựa vào nội dung audit tháng trước như bằng chứng hiện tại.

## F3: Kiểm tra tooling nghiên cứu và workflow citation

**Files:** tạo `docs/research/tooling.md`; đọc skill plugin-management khi thực thi. Nếu cài dependency simulator, lưu recipe tách biệt trong `docs/research/reproducibility-audit.md` và ghi image digest.

**Interfaces:** nhận inventory runtime; xuất bảng tool/name/version/status/smoke/evidence và cách nhập/xuất một citation đã kiểm chứng.

- [ ] Xác nhận tool Perplexity, Context7 và browser hiện có qua discovery runtime. Thử query công khai đơn giản và kiểm tra URL trả về thực sự hỗ trợ câu trả lời.
- [ ] Nếu Perplexity vẫn trả rỗng/lỗi, ghi lỗi và dùng web search; không cài trùng hay vòng lặp retry vô hạn. Không ghi key vào docs hoặc logs.
- [ ] Kiểm tra Chrome/profile để cài extension theo yêu cầu ở lượt thực thi: dùng link nhà phát hành từ roadmap. Phân biệt Perplexity Companion với extension bridge điều khiển browser. Kiểm tra cài thành công trong UI và thử trên trang công khai.
- [ ] Kiểm tra Zotero có sẵn không. Dùng Zotero Connector khi phù hợp; xuất một BibTeX mẫu với DOI/title/year đã kiểm tra. Nếu chưa cài, có thể hoàn thành luồng citation bằng file BibTeX và metadata nguồn, không khóa research vì thiếu Zotero MCP.
- [ ] Chỉ chọn MCP citation bổ sung sau khi xác định thao tác còn thiếu; ghi repository nhà phát hành, quyền, transport, version, cách gỡ và smoke. Không mặc định một package cộng đồng là chính thức.
- [ ] Nếu cần sửa image để import CityFlow, tạo recipe có version cụ thể sau khi kiểm tra package hỗ trợ Python của image. Smoke ở F1 phải được chạy lại trên image đó; lưu digest mới, không âm thầm dùng `latest` như version khóa.

**Done:** có đường tìm nguồn → kiểm tra nguồn → lưu metadata → BibTeX hoạt động. Trạng thái extension/MCP được báo đúng là installed/available/tested/failed, không gộp cả bốn thành “đã cài”.

## F4: Core literature review và audit bibliography

**Files:** tạo `docs/research/search-protocol.md`, `docs/research/literature-matrix.jsonl`, `docs/research/bibliography-audit.md`; đọc `paper/references.bib`, `paper/guideline.txt`. Chưa thay toàn bộ bibliography trước khi audit xong.

**Interfaces:** dùng schema trong foundation spec; xuất core review, candidate shortlist và 3–5 quyết định thiết kế có evidence.

- [ ] Ghi truy vấn và ngày tìm cho các nhóm: `traffic signal control reinforcement learning pressure coordination`; `motorcycle mixed traffic microsimulation calibration Vietnam`; `Da Nang turning movement counts traffic survey`; `traffic signal control robustness generalization benchmark`. Bổ sung bộ lọc 2023–2026 cho bài gần đây và giữ paper nền tảng.
- [ ] Duyệt nguồn từ roadmap và references của chúng. Mỗi bài ghi lý do include/exclude, không chọn chỉ vì báo RL thắng mạnh.
- [ ] Đọc sâu 8–12 nguồn ưu tiên: pressure gốc/PressLight; CoLight; Efficient hoặc Advanced-MP; RESCO; đánh giá thống kê RL; T-REX; calibration guidance; bài dữ liệu/giao thông hỗn hợp Đà Nẵng. Chọn bản full text hợp lệ; ghi truy cập thất bại nếu có.
- [ ] Trích evidence theo page/equation/table cho state/action/reward, signal constraints, demand, seed, split và metric. Kiểm tra điều kiện áp dụng định lý MP thay vì lặp claim “luôn tối ưu”.
- [ ] Kiểm tra mỗi citation được dùng trong LaTeX: key tồn tại, DOI đúng title/author/year, duplicate DOI/title, preprint/publication trùng, URL chết, nguồn không liên quan. Không ép xóa entry chỉ vì uncited nếu dự kiến dùng và metadata hợp lệ; đưa quyết định vào audit.
- [ ] Tạo shortlist: một baseline mạnh cần cài; phương pháp neighbor tối thiểu; dữ liệu quan trắc cần thiết để state mới có thể đo; khác biệt có thể kiểm tra bằng ablation.

**Done:** không coi abstract-only là full-text; mọi đề xuất thuật toán có nguồn và phân biệt reimplementation, adaptation và đóng góp dự kiến.

## F5: Khả năng tiếp cận dữ liệu và chọn phạm vi pilot

**Files:** tạo `docs/research/data-sources.jsonl`, `docs/research/data-feasibility.md`; dùng sources trong roadmap và cơ quan/nhóm nghiên cứu tìm được từ nguồn chính thức.

**Interfaces:** registry theo foundation spec; xuất nhánh D1/D2/D3/D4 và phạm vi ứng viên có bằng chứng. Không cần API mới để tạo hồ sơ.

- [ ] Kiểm tra Ton et al., JICA/DaCRISS và nguồn khảo sát địa phương: có data link hay chỉ paper; năm đo; vị trí; kiểu biến; quyền dùng. Một con số trong báo chí không đủ thành dataset calibration.
- [ ] Với dữ liệu tải được, kiểm tra file format, units, timestamp và provenance. Tách forecast, registered fleet, network movement counts và observed entry counts.
- [ ] Lập bảng 2–3 hành lang: counts/video; normal/AM/PM; số ngày; signal plans; network mapping; quyền; chi phí chuẩn bị. Ưu tiên dữ liệu kiểm chứng được và đủ split, không ưu tiên khu vực mô phỏng ra nhiều xe nhất.
- [ ] Sau đợt tìm tối đa 2 ngày công, xuất quyết định D1–D4 và danh sách thiếu cụ thể. Nếu cần liên hệ tác giả/cơ quan thì soạn nội dung yêu cầu dữ liệu như artifact nháp; không gửi khi chưa được cho phép gửi.
- [ ] Nếu dữ liệu chỉ có một nút, đề xuất pilot một nút và kế hoạch mở rộng; không giả lập các nút còn lại rồi gọi cả mạng là đã hiệu chỉnh.

**Done:** dữ liệu đủ/thiếu là kết luận có bằng chứng. Quyết định thiếu dữ liệu vẫn hoàn thành feasibility audit, nhưng không hoàn thành yêu cầu thesis dùng lưu lượng thật.

## F6: Protocol khảo sát và handoff sang network/calibration

**Files:** tạo `docs/research/survey-protocol.md`, `docs/research/foundation-handoff.md`; cập nhật `docs/research/status.md`.

**Interfaces:** dùng quyết định F5, core review F4, audit F1/F2; xuất danh sách input, người/phương tiện cần huy động và điều kiện mở T04–T06.

- [ ] Với D1: ghi mapping counts → movements → OSM IDs, kiểm tra overlap thời gian và danh sách ngày giữ riêng. Với D2/D4: thiết kế khảo sát pilot, không tự nhận đã có quyền truy cập camera.
- [ ] Chọn cửa sổ 15 phút cho bảng count ban đầu; giữ timestamp gốc nếu video cho phép tổng hợp lại 5 phút. Phân loại xe máy/ô tô/buýt/tải và left/through/right; đếm thủ công mẫu trải đều normal/peak trước khi dùng tracker.
- [ ] Protocol QC đề xuất: hai người đếm độc lập 10–20% các interval, bao phủ từng movement/class quan trọng; đối soát chênh lệch và đo absolute/relative count error. Nếu chỉ một người, blind recount sau một khoảng cách thời gian và nêu giới hạn. Không dùng mAP để thay count error.
- [ ] Ghi camera angle/occlusion/time coverage, tín hiệu cùng thời điểm, queue hoặc travel-time observations. Đánh dấu missing và partial coverage theo schema; không tự điền bằng trung bình cả ngày.
- [ ] Đưa ra split bằng nhóm ngày/buổi; số ngày cuối phụ thuộc dữ liệu thật, tối thiểu phải có nhóm giữ riêng để kiểm chứng. Ghi rõ nếu không thể ước lượng biến thiên giữa ngày.
- [ ] Handoff chốt: phạm vi pilot, data branch, backend pilot nào chạy được, bugs cần sửa trước chạy, mức compute đo/thiếu, nhiệm vụ tiếp theo. Bao gồm contract replay export và milestone demo hoạt động sau pilot để thay backend không làm mất khả năng presentation. Chuyển sang viết plan T04–T06 từ bằng chứng này; không nhảy thẳng vào retrain 53 nút.
- [ ] So manifest sau task với F0; review toàn bộ file mới, JSONL parse được, Markdown links hoạt động, không credentials, không unsupported actual traffic count. Ghi trạng thái từng task vào `status.md`.

**Done:** Sol hoặc người khác đọc handoff có thể xác định chính xác việc tiếp theo và điều kiện còn thiếu, không phải tìm lại lịch sử chat.

## Prompt bàn giao cho Sol

```text
Hãy thực thi kế hoạch docs/superpowers/plans/2026-09-07-danang-research-foundation-implementation.md theo superpowers:executing-plans. Đọc foundation spec, defense demo spec và roadmap được liên kết trước. Bắt đầu F0, sau đó từng task F1–F6; cập nhật docs/research/status.md và lưu evidence cho mỗi kết luận. Giữ nguyên artifacts/checkpoint lịch sử; smoke chỉ ghi ra thư mục riêng. Chưa chạy full training hoặc đổi simulator chính thức. Demo bảo vệ là bắt buộc: audit offline A/B replay, dữ liệu, camera và provenance, rồi đưa replay-export contract vào handoff. Nếu thiếu dữ liệu/daemon/quyền truy cập, ghi chính xác điều kiện thiếu và tiếp tục task độc lập. Không gửi yêu cầu tới người khác và không mua compute. Kết thúc bằng foundation-handoff với phạm vi pilot, nguồn dữ liệu khả dụng và đề xuất kế hoạch T04–T06.
```

Prompt trên dành cho người dùng gửi khi chuyển sang Sol và muốn bắt đầu triển khai. Nó không tự kích hoạt thực thi trong phiên hiện tại.
