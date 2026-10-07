@echo off
cd /d "%~dp0"
py -3 -m annotation_viewer.server --open
if errorlevel 1 pause
