@echo off
cd /d "%~dp0"
start "" http://localhost:8880/
py -3 -m http.server 8880 --directory site
if errorlevel 1 pause
