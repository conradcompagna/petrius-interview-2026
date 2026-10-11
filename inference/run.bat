@echo off
setlocal
cd /d "%~dp0"
if not exist "..\models\neural_v3.pt" call "..\GET_ASSETS.bat"
if errorlevel 1 exit /b 1
if not exist ".venv\Scripts\python.exe" call setup.bat
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -X utf8 run.py %*
if errorlevel 1 (echo Inference failed. & pause & exit /b 1)
echo Results are in "%~dp0outputs". Random runs have their own dated folders.
pause
