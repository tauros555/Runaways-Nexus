@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ==============================================
echo Runaway's Nexus PRE-FLIGHT CHECK
echo ==============================================
echo.
echo このチェックではGit pushを行いません。
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\update_nexus.ps1" -NoGit
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
    echo CHECK FAILED.
    echo update_nexus.log をChatGPTへ送ってください。
) else (
    echo CHECK / LOCAL UPDATE COMPLETE.
)
echo.
pause
exit /b %RC%
