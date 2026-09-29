@echo off
cd /d "%~dp0"
py -3 run_menu.py
if errorlevel 1 (
    echo.
    echo [Error] Python could not run run_menu.py
    pause
)
