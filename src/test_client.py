#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端测试:生成一条跨两个瓦片的山地测试轨迹,调用 /analyze 验证指标。"""
import json
import urllib.request

# 从 (115.93, 40.28) 到 (116.30, 40.42) 的直线轨迹,跨 E115/E116 两个瓦片,穿过山脊
N = 80
p0 = (115.93, 40.28)
p1 = (116.30, 40.42)
points = [
    [p0[0] + (p1[0] - p0[0]) * i / (N - 1), p0[1] + (p1[1] - p0[1]) * i / (N - 1)]
    for i in range(N)
]

req = urllib.request.Request(
    "http://127.0.0.1:8107/analyze",
    data=json.dumps({
        "points": points,
        "coord_system": "wgs84",
        "grade_threshold": 0.02,
        "smooth_window_m": 60,
    }).encode(),
    headers={"Content-Type": "application/json"},
)
print(json.dumps(json.load(urllib.request.urlopen(req)), ensure_ascii=False, indent=2))
