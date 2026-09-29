@echo off
chcp 65001 >nul
title BUKVA-49 Publishing Assistant
cd /d "%~dp0"
py -3 publish_helper.py
pause
