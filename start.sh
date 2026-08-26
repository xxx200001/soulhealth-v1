#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
[ -f .env ] || cp .env.example .env
python -m pip install -r requirements.txt -q
python run.py
