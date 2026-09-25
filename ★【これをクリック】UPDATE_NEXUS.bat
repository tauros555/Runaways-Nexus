@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "LOG=%~dp0update_nexus.log"
set "REMOTE_URL=https://github.com/tauros555/Runaways-Nexus.git"
set "REMOTE_NAME=origin"
set "BRANCH=main"

echo ==================================================>> "%LOG%"
echo Runaway's Nexus update started: %date% %time%>> "%LOG%"
echo Folder: %CD%>> "%LOG%"
echo ==================================================>> "%LOG%"

echo.
echo ==============================================
echo Runaway's Nexus AUTO UPDATE
echo ==============================================
echo.
echo Folder: %CD%
echo Log   : %LOG%
echo.

if not exist "scripts\update_nexus.ps1" (
    echo [ERROR] scripts\update_nexus.ps1 is missing.
    echo [ERROR] Missing scripts\update_nexus.ps1>> "%LOG%"
    echo.
    pause
    exit /b 1
)

where powershell.exe >nul 2>&1
if errorlevel 1 (
    echo [ERROR] powershell.exe was not found.
    echo [ERROR] powershell.exe not found>> "%LOG%"
    echo.
    pause
    exit /b 1
)

where git.exe >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git was not found. Install Git for Windows first.
    echo [ERROR] git.exe not found>> "%LOG%"
    echo.
    pause
    exit /b 1
)

rem --------------------------------------------------
rem Git repository check / safe metadata recovery
rem This does NOT overwrite working files.
rem --------------------------------------------------
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo [INFO] .git metadata is missing. Restoring Git metadata...
    echo [INFO] Restoring Git metadata>> "%LOG%"

    git init >nul 2>&1
    if errorlevel 1 goto :git_repair_failed

    git remote get-url %REMOTE_NAME% >nul 2>&1
    if errorlevel 1 (
        git remote add %REMOTE_NAME% "%REMOTE_URL%"
        if errorlevel 1 goto :git_repair_failed
    )

    git fetch %REMOTE_NAME% %BRANCH%
    if errorlevel 1 goto :git_repair_failed

    git update-ref refs/heads/%BRANCH% refs/remotes/%REMOTE_NAME%/%BRANCH%
    if errorlevel 1 goto :git_repair_failed

    git symbolic-ref HEAD refs/heads/%BRANCH%
    if errorlevel 1 goto :git_repair_failed

    rem Synchronize only the index with remote HEAD; working files are preserved.
    git reset --mixed HEAD >nul 2>&1
    if errorlevel 1 goto :git_repair_failed

    echo [OK] Git metadata restored. Working files were preserved.
    echo [OK] Git metadata restored>> "%LOG%"
) else (
    echo [OK] Git repository detected.
)

echo.
echo Starting PowerShell updater...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\update_nexus.ps1"
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
    echo ==============================================
    echo UPDATE FAILED  exit=%RC%
    echo ==============================================
    echo.
    echo Check: %LOG%
    echo.
    pause
    exit /b %RC%
)

echo ==============================================
echo UPDATE COMPLETE
echo ==============================================
echo.
echo GitHub push completed when changes were detected.
echo Streamlit Cloud will update from GitHub.
echo.
pause
exit /b 0

:git_repair_failed
echo.
echo [ERROR] Git metadata recovery failed.
echo [ERROR] Git metadata recovery failed>> "%LOG%"
echo Working files were not intentionally overwritten.
echo Please send update_nexus.log to ChatGPT.
echo.
pause
exit /b 1
