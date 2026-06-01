# Thiết kế: Tối ưu đèn giao thông Đà Nẵng bằng MARL trên CityFlow

- **Ngày:** 2026-06-01
- **Bối cảnh:** Thesis. Dựng thành phố ảo từ dữ liệu OpenStreetMap (OSM) Đà Nẵng, mô phỏng bằng CityFlow, huấn luyện Multi-Agent Reinforcement Learning (MARL) để tối ưu đèn tín hiệu, và hiển thị kết quả trên UI.
- **Quyết định nền tảng đã chốt:**
  - Simulator: **CityFlow** (viết lại từ đầu, archive code SUMO/DQN cũ).
  - Phạm vi mạng: **toàn bộ trung tâm Đà Nẵng** — các ngã tư có đèn tín hiệu thực tế (~37 nút tagged
    `traffic_signals`, có thể nhiều hơn sau khi netconvert sinh tín hiệu). Không ép buộc đủ 100 nút;
    làm theo tầng (sub-area trước → full network).
  - Kiến trúc RL: **MARL + parameter sharing** (mỗi ngã tư = 1 agent, dùng chung 1 mạng policy).
  - UI: **CityFlow web replay + dashboard so sánh** (training curves + bảng metrics).
  - Reward: **pressure-based**. Baselines: **Fixed-Time, Max-Pressure, Random**.

## 1. Mục tiêu & đóng góp

Tối ưu điều khiển đèn tín hiệu trên **mạng đô thị thật của Đà Nẵng** (trích từ OSM), so sánh MARL
parameter-sharing với các baseline kinh điển. Điểm mới so với phần lớn nghiên cứu (vốn dùng các
dataset có sẵn như Hangzhou/Jinan): pipeline OSM → CityFlow cho một thành phố Việt Nam, với luồng
giao thông nặng xe máy.

Tiêu chí thành công:
- Pipeline OSM → CityFlow chạy được trên toàn trung tâm Đà Nẵng (mạng load được, mô phỏng không crash).
- MARL giảm **average travel time** (metric chính) so với Fixed-Time và đạt mức cạnh tranh / vượt Max-Pressure.
- UI hiển thị được: replay xe chạy trên bản đồ + dashboard so sánh RL vs baseline.
- Kết quả đủ để viết Chapter 4 của thesis.

## 2. Pipeline tổng thể

```
OSM Đà Nẵng (.osm)
   │  netconvert --osm-files        (SUMO CLI, chỉ dùng lúc convert)
   ▼
SUMO net (.net.xml)                 ← xử lý sạch hình học + sinh đèn tín hiệu
   │  CityFlow tools/Converter/converter.py
   ▼
CityFlow roadnet.json  +  flow.json (sinh luồng xe, tỉ lệ xe máy cao kiểu VN)
   │
   ▼
CityFlow Engine  ──►  Multi-Agent Env (mỗi ngã tư có đèn = 1 agent)
   │                        │
   │                   ┌────┴─────┐
   │              MARL DQN        Baselines
   │              (param-sharing) (Fixed / Max-Pressure / Random)
   ▼                        │
Replay (xe trên bản đồ)  +  Dashboard so sánh (curves + bảng metrics)
```

Lý do chọn đường OSM → SUMO → CityFlow thay vì `osm2cityflow` trực tiếp: `osm2cityflow` chỉ lấy đường
`highway.primary`, không có lane width, dễ tạo đoạn đường quá ngắn gần ngã tư. `netconvert` xử lý OSM
sạch hơn và sinh được signal plan, sau đó dùng converter chính thức của CityFlow.

## 3. Kiến trúc & các module

Mỗi module một trách nhiệm rõ ràng, giao tiếp qua interface định nghĩa sẵn, test độc lập được.

| Module | Trách nhiệm | Input → Output |
|--------|-------------|----------------|
| `src/network/` | Converter OSM→SUMO→CityFlow + sinh `flow.json` | `.osm` → `roadnet.json`, `flow.json` |
| `src/sim/` | Wrapper quanh CityFlow Engine + Multi-Agent Env | roadnet/flow → observation/reward per agent |
| `src/agents/` | DQN param-sharing + baselines (Fixed-Time, Max-Pressure, Random) | obs → action (chọn phase) |
| `src/train/` | Vòng lặp training MARL, checkpoint + log | config → model + logs |
| `src/eval/` | Chạy so sánh, tính metrics, xuất replay | model → JSON metrics + replay |
| `src/ui/` | CityFlow web replay + dashboard so sánh | metrics/replay → trang web |

Cấu trúc thư mục mới:

```
traffic-rl/
├── data/
│   ├── osm/                # OSM thô (.osm, graphml)
│   └── danang/             # roadnet.json, flow.json sinh ra (sub-area + full)
├── src/
│   ├── network/            # converters + flow generator
│   ├── sim/                # CityFlow engine wrapper, multi-agent env
│   ├── agents/             # shared-param DQN, baselines
│   ├── train/              # training loop, config
│   ├── eval/               # metrics, run comparisons
│   └── ui/                 # dashboard + replay launcher
├── configs/                # YAML: network, training, eval
├── experiments/            # script chạy đầu-cuối
├── results/                # metrics + replay + plots
└── paper/                  # giữ nguyên thesis
```

Code SUMO/DQN cũ: archive vào branch git (vd `legacy-sumo`) rồi xóa khỏi `main`.

## 4. Thiết kế RL (MARL parameter-sharing)

- **Agent:** mỗi ngã tư có đèn tín hiệu = 1 agent. **Tất cả agent dùng chung 1 mạng Q** (chia sẻ tham số)
  → một policy generalize cho mọi ngã tư, scale được tới 100+ nút.
- **Observation (per agent):** số xe / chiều dài hàng chờ trên các incoming lane + phase hiện tại (one-hot).
  Chuẩn hóa để mạng dùng chung học được trên các ngã tư có hình học khác nhau.
- **Action:** chọn phase tín hiệu kế tiếp trong tập phase hợp lệ của ngã tư đó. Ràng buộc vận hành:
  min-green time + thời gian đèn vàng khi chuyển phase.
- **Reward:** **pressure** (chênh lệch tổng hàng chờ lane vào và lane ra của ngã tư) — chuẩn trong
  CityFlow MARL (PressLight/CoLight), ổn định hơn `-waiting_time` đơn thuần.
- **Thuật toán:** DQN (replay buffer + target network) với mạng chia sẻ tham số; epsilon-greedy.
- **Baselines:**
  - **Fixed-Time:** phase cố định theo chu kỳ.
  - **Max-Pressure:** chọn phase tối đa hóa pressure mỗi bước (baseline mạnh, không học) — dùng làm
    chuẩn cạnh tranh chính.
  - **Random:** đổi phase ngẫu nhiên (sàn dưới).
- **Metrics đánh giá:**
  - **Average travel time** (chính).
  - Throughput (số xe hoàn thành chuyến).
  - Average waiting time.
  - Average queue length.

## 5. Thiết kế dữ liệu mạng & luồng

- **Network:** trích bbox trung tâm Đà Nẵng từ OSM (`scripts/download_osm_danang.py`, đã import lại:
  11.345 nodes / 29.633 edges thô, trong đó **37 nút tagged `traffic_signals`**). Convert qua
  netconvert → CityFlow converter; netconvert sẽ consolidate cụm node hình học thành junction thật và
  có thể sinh thêm tín hiệu (`--tls.guess`). **Chỉ các ngã tư có đèn mới là agent** (~37+ nút) — phủ
  toàn thành phố Đà Nẵng, không cần đạt mốc 100 nút; ngã tư không đèn để mặc định.
- **Flow (`flow.json`):** sinh luồng tổng hợp (synthetic) với tỉ lệ xe máy cao đặc trưng VN. Định
  nghĩa route theo OD đơn giản trên mạng + tần suất xuất phát. Calibrate ở mức hợp lý (mật độ tạo
  được tắc nghẽn quan sát được, không cần khớp số liệu thực tế tuyệt đối — nêu rõ là synthetic trong thesis).

## 6. Thiết kế UI

- **Replay CityFlow:** dùng web frontend có sẵn của CityFlow (chạy qua Docker), load `replay_roadnet.json`
  + `replay.txt` do bước eval sinh ra → xem xe chạy trên bản đồ Đà Nẵng theo từng phương pháp.
- **Dashboard so sánh (Streamlit):** trang web hiển thị:
  - Training curves (reward / loss theo episode).
  - Bảng so sánh metrics RL vs các baseline (travel time, throughput, waiting, queue).
  - Link/hướng dẫn mở replay tương ứng.

## 7. Lộ trình theo tầng (giảm rủi ro mạng 100+ nút)

1. **P0 — Setup môi trường:** CityFlow chạy được (Docker), chạy example mẫu + replay UI hoạt động.
2. **P1 — Network:** converter chạy trên **sub-area nhỏ Đà Nẵng trước** (verify từng bước), rồi scale
   lên **toàn trung tâm**. Sinh `flow.json`.
3. **P2 — Sim + Env:** wrapper CityFlow + multi-agent env + reward pressure. Validate bằng Fixed-Time
   + xem replay.
4. **P3 — Baselines:** Max-Pressure + Random + Fixed-Time chạy & log metrics.
5. **P4 — MARL training:** DQN param-sharing, train trên full network, lưu checkpoint.
6. **P5 — Eval + UI:** so sánh RL vs baseline, dashboard + replay nhúng.
7. **P6 — Viết Chapter 4** từ kết quả thật.

Mỗi phase có cổng kiểm chứng (gate) trước khi sang phase sau; đặc biệt P1 phải verify trên sub-area
trước khi scale.

## 8. Stack công nghệ

- **CityFlow** (Docker) — engine + web replay.
- **PyTorch** — DQN param-sharing.
- **Streamlit** — dashboard so sánh.
- **netconvert (SUMO CLI)** + **CityFlow `converter.py`** — chỉ dùng lúc convert mạng.
- **osmnx / OSM** — trích mạng đường (đã có sẵn trong repo).

## 9. Rủi ro & giảm thiểu

| Rủi ro | Giảm thiểu |
|--------|------------|
| OSM → CityFlow lỗi trên mạng lớn (lane width, đoạn ngắn, đèn thiếu) | Validate trên sub-area trước; làm sạch net bằng tùy chọn netconvert; chấp nhận đơn giản hóa và nêu rõ trong thesis |
| Train MARL 100+ nút chậm / không hội tụ | Parameter sharing + reward pressure (đã chứng minh scale); train sub-area trước để tinh chỉnh hyperparameter |
| Flow không thực tế | Nêu rõ synthetic; calibrate mật độ tạo tắc nghẽn quan sát được |
| CityFlow Docker / replay phức tạp khi setup | P0 dành riêng để dựng & verify môi trường trước khi làm tiếp |

## 10. Ngoài phạm vi (YAGNI)

- Không làm coordination/communication layer giữa agent ở giai đoạn này (có thể là hướng mở rộng tương lai).
- Không làm dashboard tương tác chạy-live; dashboard chỉ hiển thị kết quả đã chạy.
- Không khớp dữ liệu giao thông thực tế tuyệt đối; dùng flow synthetic.
- Giữ lại nhánh SUMO chỉ để đối chiếu, không phát triển tiếp.

## Nguồn tham khảo (research)

- CityFlow roadnet format: https://cityflow.readthedocs.io/en/latest/roadnet.html
- SUMO netconvert OSM import: https://sumo.dlr.de/docs/Networks/Import/OpenStreetMap.html
- osm2cityflow (hạn chế): https://github.com/cityflow-project/CityFlow/pull/63/files
- sumo-rl (tham khảo thiết kế env): https://github.com/LucasAlegre/sumo-rl
- RESCO benchmark: https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/file/f0935e4cd5920aa6c7c996a5ee53a70f-Paper-round1.pdf
- PyTSC (MARL TSC đa simulator): https://pmc.ncbi.nlm.nih.gov/articles/PMC11902778/
