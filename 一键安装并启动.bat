@echo off
chcp 936 >nul
title SOULHEALTH V1 一键配置与启动工具

echo ============================================================
echo   SOULHEALTH V1 一键环境配置与启动
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/3] 检查并配置 .env 环境变量文件...
if not exist .env (
    copy .env.example .env >nul
    echo       已自动从 .env.example 生成 .env 配置文件！
) else (
    echo       .env 配置文件已存在，跳过生成。
)

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
