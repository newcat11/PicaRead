@echo off
chcp 65001 >nul
title PicaRead

echo 正在启动 PicaRead...

:: 激活虚拟环境并启动
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    start "" http://localhost:8501
    streamlit run bika_gui.py --server.port 8501 --server.headless true
    pause
) else (
    echo 未找到虚拟环境，请先运行 setup_and_run.bat 进行安装
    pause
)
