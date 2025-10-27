# Cấu Trúc Thư Mục Dự Án

## 📁 Cấu trúc đã được tổ chức lại

```
traffic-rl/
├── src/                              # Mã nguồn chính
│   ├── agents/                      # Các agents và controllers
│   │   ├── baseline_controllers.py
│   │   ├── dqn_agent.py
│   │   └── ppo_agent.py
│   ├── environment.py               # Môi trường traffic
│   └── visualization.py             # Tiện ích vẽ biểu đồ
│
├── experiments/                      # Các script chạy experiments
│   ├── experiment.py                # Experiment runner chính
│   ├── run_one_intersection_mock.py      # 1 intersection + Mock
│   ├── run_one_intersection_sumo.py      # 1 intersection + SUMO  
│   ├── run_three_intersections_mock.py   # 3 intersections + Mock
│   └── run_three_intersections_sumo.py   # 3 intersections + SUMO
│
├── sumo_configs/                     # Cấu hình SUMO
│   ├── one_intersection/
│   └── three_intersections/
│
├── results/                         # Kết quả experiments
│   ├── one_intersection/            # Kết quả cho 1 intersection
│   │   ├── experiments/            # JSON files
│   │   └── plots/                 # Visualizations
│   └── three_intersections/        # Kết quả cho 3 intersections
│       ├── experiments/
│       └── plots/
│
├── paper/                           # LaTeX files
└── logs/                           # Log files
```

## 🚀 Cách chạy experiments

### One Intersection với Mock
```bash
cd experiments
python3 run_one_intersection_mock.py
```

### One Intersection với Real SUMO
```bash
python3 run_one_intersection_sumo.py
```

### Three Intersections với Mock
```bash
python3 run_three_intersections_mock.py
```

### Three Intersections với Real SUMO
```bash
python3 run_three_intersections_sumo.py
```

## 📊 Kết quả

Mỗi experiment sẽ tạo:
- `results/{config_type}/experiments/results_*.json` - Dữ liệu metrics
- `results/{config_type}/plots/` - Các biểu đồ so sánh

## ✨ Lợi ích của cấu trúc mới

1. **Tách biệt code và experiments**: `src/` chứa code chính, `experiments/` chứa scripts chạy
2. **Kết quả theo config**: Mỗi loại config có thư mục riêng trong `results/`
3. **Dễ dàng chạy real SUMO**: Có script riêng cho mock và SUMO
4. **Dễ mở rộng**: Có thể thêm configs/experiments mới dễ dàng

