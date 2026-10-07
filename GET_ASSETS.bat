@echo off
setlocal
pushd "%~dp0"
py -3 tools/get_assets.py
set "asset_status=%errorlevel%"
popd
if not "%asset_status%"=="0" pause
exit /b %asset_status%
