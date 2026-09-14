#!/bin/bash
# macOS 双击启动(或终端执行 bash 启动.command)
cd "$(dirname "$0")" || exit 1
export PYTHONUTF8=1
PORT=8107

if ! command -v python3 >/dev/null 2>&1; then
  echo "[错误] 未找到 python3,请先安装 Python 3.9~3.12(python.org 或 brew install python)"
  read -r -p "按回车关闭..." _
  exit 1
fi

if [ ! -d .venv ]; then
  echo "[1/3] 首次运行:正在创建虚拟环境..."
  python3 -m venv .venv || { echo "[错误] 创建虚拟环境失败"; read -r -p "按回车关闭..." _; exit 1; }
fi

if ! .venv/bin/python -c "import fastapi, uvicorn, rasterio, numpy, openpyxl" >/dev/null 2>&1; then
  echo "[2/3] 正在安装依赖(首次需联网)..."
  .venv/bin/python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple \
    || { echo "[错误] 依赖安装失败,请检查网络"; read -r -p "按回车关闭..." _; exit 1; }
fi

echo "[3/3] 启动服务: http://127.0.0.1:$PORT  (Ctrl+C 停止)"
( sleep 3; open "http://127.0.0.1:$PORT/" >/dev/null 2>&1 ) &
exec .venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port "$PORT"
