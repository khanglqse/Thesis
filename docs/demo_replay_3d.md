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
- Xe = hộp 3D dựng từ (x, y, góc, dài, rộng) trong replay.

## Điều khiển

Kéo chuột: xoay camera · Shift+kéo / chuột phải: trượt · lăn chuột: thu-phóng ·
"Đặt lại camera": về khung nhìn toàn mạng. Play/tua/tốc độ như bản 2D.
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
