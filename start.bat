@echo off
cd /d %~dp0
if not exist .env copy .env.example .env
python -m pip install -r requirements.txt -q
python run.py
