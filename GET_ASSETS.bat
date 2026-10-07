@echo off
cd /d "%~dp0"
py -3 tools/get_assets.py
if errorlevel 1 pause
