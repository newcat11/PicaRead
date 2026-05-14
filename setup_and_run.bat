@echo off
chcp 65001 >nul
title PicaRead - 安装和启动

echo.
echo ============================================
echo    PicaRead -- 漫画阅读器 v1.0
echo ============================================
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

python --version
echo.

:: 创建虚拟环境（仅首次）
if not exist "venv" (
    echo [1/3] 创建虚拟环境...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
) else (
    echo [1/3] 虚拟环境已存在，跳过创建
)

:: 安装依赖
echo.
echo [2/3] 安装依赖包...
call venv\Scripts\activate.bat
pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [警告] 部分依赖安装失败，尝试使用国内镜像...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)
echo 依赖安装完成

:: 启动应用
echo.
echo [3/3] 启动应用...
echo.
echo ============================================
echo    浏览器将自动打开 http://localhost:8501
echo    关闭此窗口即可停止运行
echo ============================================
echo.

start "" http://localhost:8501
streamlit run bika_gui.py --server.port 8501 --server.headless true

:: 如果 streamlit 没找到，尝试直接 python 运行
if %errorlevel% neq 0 (
    echo [提示] 正在使用备用方式启动...
    python -m streamlit run bika_gui.py --server.port 8501 --server.headless true
)

pause
