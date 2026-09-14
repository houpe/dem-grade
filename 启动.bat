@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PORT=8107

rem ---- 定位 Python(优先 py 启动器)----
where py >nul 2>nul
if %errorlevel%==0 (set PYCMD=py -3) else (set PYCMD=python)

rem ---- Python 检测:缺失时自动打开附带安装包,装完自动继续 ----
:checkpy
%PYCMD% --version >nul 2>nul
if not errorlevel 1 goto pyok
if not exist "安装包\python-3.12.10-amd64.exe" goto nopy
echo 未检测到 Python,正在打开附带的安装包...
echo ------------------------------------------------------------
echo  [重要] 安装界面底部务必勾选 "Add Python to PATH",
echo         然后点 "Install Now"。安装完成后本脚本自动继续。
echo ------------------------------------------------------------
start "" /wait "安装包\python-3.12.10-amd64.exe"
where py >nul 2>nul
if %errorlevel%==0 set PYCMD=py -3
goto checkpy

:nopy
echo [错误] 未找到 Python,且目录内无附带安装包。
echo        请安装 Python 3.9~3.12(64 位),安装时勾选 "Add Python to PATH":
echo        https://www.python.org/downloads/windows/
pause
exit /b 1

:pyok
rem ---- 首次运行:创建虚拟环境----
if not exist .venv (
  echo [1/3] 首次运行:正在创建虚拟环境...
  %PYCMD% -m venv .venv
  if errorlevel 1 (
    echo [错误] 创建虚拟环境失败,请确认 Python 版本为 3.9~3.12(64 位)。
    pause
    exit /b 1
  )
)

rem ---- 依赖检查与安装(仅首次)----
".venv\Scripts\python.exe" -c "import fastapi, uvicorn, rasterio, numpy, openpyxl" >nul 2>nul
if errorlevel 1 (
  echo [2/3] 正在安装依赖(首次需联网,约 1~3 分钟;已配置国内镜像)...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  if errorlevel 1 (
    echo [错误] 依赖安装失败,请检查网络后重试。
    pause
    exit /b 1
  )
)

rem ---- 启动并打开浏览器----
echo [3/3] 启动服务: http://127.0.0.1:%PORT%
echo        关闭本窗口(或按 Ctrl+C)即停止服务。
echo        DEM 数据缺失时会在分析时自动联网下载。
start "" cmd /c "timeout /t 3 /nobreak >nul & start "" http://127.0.0.1:%PORT%"
".venv\Scripts\python.exe" -m uvicorn server:app --host 127.0.0.1 --port %PORT%
echo.
echo 服务已停止。
pause
