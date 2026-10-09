@echo off
chcp 65001 >nul
cd /d %~dp0
echo Starting Jev Playground on http://127.0.0.1:8770 ...
echo (server auto-restarts if it crashes; close this window to stop)
:loop
D:\jev\bench\jev-benchmarking\.venv\Scripts\python.exe server.py
echo.
echo Server exited (code %errorlevel%). Restarting in 3 s ...
timeout /t 3 >nul
goto :loop
