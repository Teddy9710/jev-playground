@echo off
chcp 65001 >nul
cd /d %~dp0
echo Starting Jev Playground on http://127.0.0.1:8770 ...
D:\jev\bench\jev-benchmarking\.venv\Scripts\python.exe server.py
pause
