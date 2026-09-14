@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
rem ============================================================
rem  Windows 桌面版打包脚本(必须在 Windows 电脑上运行!)
rem  产物: dist\SlopeAnalysis\SlopeAnalysis.exe
rem  把 dist\SlopeAnalysis 整个文件夹压缩成 zip 发给用户,
rem  用户解压后双击 exe 即可,无需安装 Python。
rem ============================================================

rem ---- 构建机需要 Python 3.10~3.12(64 位);用户电脑不需要 ----
where py >nul 2>nul
if %errorlevel%==0 (set PYCMD=py -3) else (set PYCMD=python)
%PYCMD% --version >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 Python。请安装 64 位 Python 3.10~3.12,
  echo        安装时勾选 "Add Python to PATH" 后重跑本脚本:
  echo        https://www.python.org/downloads/windows/
  pause
  exit /b 1
)

echo [1/3] 创建虚拟环境并安装依赖(首次约 2~5 分钟)...
if not exist .venv %PYCMD% -m venv .venv
".venv\Scripts\python.exe" -m pip install -r requirements.txt pywebview pyinstaller ^
  -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
  echo [错误] 依赖安装失败,请检查网络后重试。
  pause
  exit /b 1
)

echo [2/3] PyInstaller 打包(约 1~3 分钟)...
".venv\Scripts\pyinstaller.exe" desktop.py ^
  --name SlopeAnalysis ^
  --windowed --onedir ^
  --add-data "static;static" ^
  --collect-submodules rasterio ^
  --collect-all certifi ^
  --exclude-module tkinter
if errorlevel 1 (
  echo [错误] 打包失败。
  pause
  exit /b 1
)

echo [3/3] 完成!
echo.
echo   产物目录: dist\SlopeAnalysis\   (入口 SlopeAnalysis.exe)
echo   分发方式: 把 dist\SlopeAnalysis 整个文件夹压缩成 zip 发给用户。
echo   用户解压后双击 SlopeAnalysis.exe,无需安装任何环境。
echo.
echo   首次运行提示:
echo   - Windows 可能弹 "已保护你的电脑"(未签名 exe 的正常提示),
echo     点 "更多信息" - "仍要运行" 即可。
echo   - 若窗口空白/报 WebView2 错误,安装一次微软 WebView2 Runtime:
echo     https://developer.microsoft.com/microsoft-edge/webview2/
echo   - 首次分析新区域会联网下载 DEM 数据(每片约 20~50 MB),
echo     保存在 %%LOCALAPPDATA%%\高程计算\dem,之后同区域不再下载。
echo.
pause
