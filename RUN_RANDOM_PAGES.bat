@echo off
setlocal
cd /d "%~dp0"
echo Testing three randomly selected pages from matching-layout books.
call "inference\run.bat" --random-pages 3 %*
