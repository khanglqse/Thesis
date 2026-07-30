# Demo 3D A/B: Fixed-Time vs DQN (deck.gl)

Trang: `frontend/replay_3d.html` — chạy cùng server với bản 2D:

    python3 scripts/serve_replay.py --no-browser
    # mở http://localhost:8080/frontend/replay_3d.html

## Trang này là gì

- Hai khung 3D **khoá cùng camera và cùng thời điểm**: trái mặc định Cố định
  (Fixed-Time), phải mặc định DQN; đổi được từng bên (Max-Pressure, Ngẫu nhiên).
- **Replay CityFlow thật** (120 khung × 1 s — ~2 phút đầu của episode) trên mạng Hải Châu 53 nút đèn —
  không phải suy luận trực tiếp (live inference). Số liệu bảng điểm đọc từ
  `results/<kịch bản>/comparison.json` (số thật của Chương 4).
- **Đèn theo từng làn:** thanh đứng màu xanh/đỏ tại vạch dừng của mỗi làn
  (ký tự `g/r/i` per-lane trong replay; `i` = làn không có đèn — không vẽ).
  Đây là điểm bản 2D không thể hiện được (bản 2D gộp mỗi đường 1 chấm).
  Lưu ý trung thực: thứ tự thanh trong một đường theo thứ tự làn trong replay;
  danh tính trái/phải tuyệt đối của làn chưa đối chiếu với viewer gốc —
  thông điệp demo là "nhánh nào xanh", không phải "làn số mấy".
- **Xe = mô hình 3D theo đúng loại xe trong replay** (từ 2026-07-30; trước đó là hộp trơn):
  CityFlow ghi kèm template kích thước cho từng xe — **2.0 × 1.0 m = xe máy** (chiếm **~90%**
  số xe trên mạng này) và **5.0 × 2.0 m = ô tô** (~10%). Xe máy vẽ thành khung + người lái +
  ghi-đông + 2 bánh; ô tô thành thân + ca-bin + 4 bánh. **Không phóng đại kích thước**: mesh
  đúng bằng template, dựng tại (x, y) với hướng đúng góc `a` trong replay (đã kiểm: 96% xe
  đang chạy có `a` trùng hướng dịch chuyển thực tế giữa 2 khung).
  Xe máy dùng tông pastel ấm, ô tô tông lạnh → **nhìn là thấy ngay tỉ lệ ~90/10** của Đà Nẵng.
  Hình học thuần ở `vehicleMesh()` (`replay_3d_core.js`), có test kiểm bounding box đúng
  bằng template. Hiệu năng: ~1.200 xe/khung × 2 panel ≈ **10 ms/bước (~94 fps)**.

## Điều khiển

Kéo chuột: xoay camera · Shift+kéo / chuột phải: trượt · lăn chuột: thu-phóng ·
**"🔍 Điểm đông"**: nhảy camera tới **giao lộ CÓ ĐÈN đông xe nhất** của replay
(`signalizedInters` + `busiestJunction`), khung ~170 m, góc nghiêng 62° — ở đó xe
2 m chiếm ~9 px nên thấy rõ mô hình xe *và* thanh đèn từng làn. Ở khung nhìn toàn
mạng xe chỉ ~0.1 px nên **chỉ thấy đường, không thấy xe** — **bấm nút này trước
khi trình bày** · "Đặt lại camera": về khung nhìn toàn mạng. Play/tua/tốc độ như
bản 2D.
Đổi kịch bản giữa chừng được (haichau_rush → danang_peak → haichau_peak →
haichau) — câu chuyện bão hoà giữ nguyên như bản 2D.

## Kỹ thuật

- deck.gl 9.3.7 vendor tại `frontend/vendor/deck.min.js` (offline hoàn toàn).
- Hình học thuần (footprint xe xoay, quad thanh đèn theo làn, fitView) ở
  `frontend/replay_3d_core.js`, test Node: `node --test tests/replay_3d/*.test.cjs`.
- Tiền lệ tài liệu: DTUMOS (deck.gl, digital twin đô thị, 2023); MARLens
  (IEEE TVCG 2024 — visual analytics cho RL điều khiển đèn); sumo3Dviz
  (arXiv:2604.19194 — 3D nhẹ cho SUMO, chỉ xuất video). Xem spec
  `docs/superpowers/specs/2026-07-19-replay-3d-demo-design.md`.
