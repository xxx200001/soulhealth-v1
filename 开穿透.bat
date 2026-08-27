@echo off
chcp 936 >nul
title SOULHEALTH V1 一键启动与穿透
cd /d %~dp0
echo ============================================================
echo   正在启动 SOULHEALTH V1 与 Cloudflare 穿透...
echo ============================================================
python start_tunnel.py
pause
