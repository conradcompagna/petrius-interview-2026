@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 goto failed
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -X utf8 task1.py
if errorlevel 1 goto failed
echo Results: labels_00040.jpg, labels_00041.jpg, lines.csv and evaluation.json
pause
exit /b 0
:failed
echo Run failed. Read the message above. Install Python 3.12 from python.org if Python was not found.
pause
exit /b 1
