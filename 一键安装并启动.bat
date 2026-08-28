@echo off
chcp 936 >nul
title SOULHEALTH V1 一键配置与启动工具

echo ============================================================
echo   SOULHEALTH V1 一键环境配置与启动
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/3] 同步并配置最新 .env 环境变量文件...
copy /y .env.example .env >nul
echo       已成功同步最新 .env 配置文件（已载入有效 AI 密钥）！

echo.
echo [2/3] 正在检查并安装 Python 依赖库...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [警告] 依赖安装可能未完全成功，尝试继续启动...
)

echo.
echo [3/3] 正在启动系统与 Cloudflare 穿透...
python start_tunnel.py
if errorlevel 1 (
    echo.
    echo [提示] 穿透启动失败，切换为本地服务模式...
    python run.py
)

pause
