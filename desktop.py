#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
桌面应用入口(PyInstaller 打包目标):
  后台线程起 uvicorn,pywebview 打开原生窗口(系统自带 WebView,无需浏览器)。
  用户机器无需安装 Python —— 运行时已打进应用包。

数据目录:打包后应用目录只读,DEM 瓦片放到用户目录
  macOS:  ~/Library/Application Support/高程计算/dem
  Windows:%LOCALAPPDATA%\\高程计算\\dem
"""
import os
import socket
import sys
import threading
import time

APP_NAME = "高程计算"
PREFERRED_PORT = int(os.environ.get("SLOPE_PORT", "8107"))   # 首选端口,占用时自动顺延


def user_data_dir() -> str:
    if sys.platform == "darwin":
        base = os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")
    else:
        base = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), APP_NAME)
    os.makedirs(base, exist_ok=True)
    return base


def find_port() -> int:
    """优先用习惯端口;被占用(如已开着一个实例)时顺延。"""
    for port in (PREFERRED_PORT, PREFERRED_PORT + 1, PREFERRED_PORT + 2, 0):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
        except OSError:
            continue
    return PREFERRED_PORT


def main() -> None:
    # 必须在 import server 之前设置(server 模块导入时读环境变量建 DemPool)
    os.environ.setdefault("DEM_DIR", os.path.join(user_data_dir(), "dem"))
    os.environ.setdefault("AUTO_DOWNLOAD", "1")

    # 冻结环境下系统 CA 证书路径不可用,显式指向打包内的 certifi;
    # 否则 DEM 自动下载(urllib HTTPS)全部握手失败
    try:
        import certifi
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    except ImportError:
        pass

    import uvicorn
    import webview

    import server

    port = find_port()
    uvi = uvicorn.Server(uvicorn.Config(
        server.app, host="127.0.0.1", port=port, log_level="warning"))

    t = threading.Thread(target=uvi.run, daemon=True)
    t.start()
    for _ in range(100):                    # 等服务就绪再开窗口,避免白屏
        if uvi.started:
            break
        time.sleep(0.1)

    webview.create_window(
        f"司机轨迹坡度分析 · 单趟复盘",
        f"http://127.0.0.1:{port}/",
        width=1440, height=900, min_size=(1080, 680),
    )
    webview.start()                         # 阻塞至窗口关闭

    uvi.should_exit = True                  # 通知 uvicorn 退出
    t.join(timeout=5)
    os._exit(0)                             # 兜底:确保杀掉全部子线程,进程干净退出


if __name__ == "__main__":
    main()
