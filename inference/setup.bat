@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install torch==2.9.1 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements-lock-cpu.txt
if errorlevel 1 goto failed
echo Setup complete. Double-click run.bat to process the two interview pages.
pause
exit /b 0
:failed
echo Setup failed. Read the message above. Python 3.12 is required.
pause
exit /b 1
