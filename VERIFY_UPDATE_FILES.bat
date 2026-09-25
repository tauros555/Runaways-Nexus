@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ==============================================
echo Runaway's Nexus LATEST FILE CHECK 2026-09-25
echo ==============================================
echo.

set "NG=0"
call :check "app.py"
call :check "★【これをクリック】UPDATE_NEXUS.bat"
call :check "scripts\update_nexus.ps1"
call :check "config\data_update.json"
call :check "tools\training\training_judgement_ver2_1.xlsx"
call :check "modules\course_judgement_v29.py"
call :check "modules\crown_rules.py"
call :check "modules\crown_rules_addon_v29.py"
call :check "modules\trainer_rules_v26.py"
call :check "modules\day_before_training.py"
call :check "data\course_role_master_v29_20260925.csv"
call :check "data\crown_master_v29_20260925.csv"
call :check "data\trainer_type_master_v1_2_20260924.csv"
call :check "data\day_before_training_effect_master.csv"

echo.
if exist "modules\course_judgement_v3.py" (
  echo [NG] obsolete file remains: modules\course_judgement_v3.py
  set "NG=1"
) else (
  echo [OK] obsolete course_judgement_v3.py is absent.
)
if exist "modules\crown_rules_addon_v2.py" (
  echo [NG] obsolete file remains: modules\crown_rules_addon_v2.py
  set "NG=1"
) else (
  echo [OK] obsolete crown_rules_addon_v2.py is absent.
)

if "%NG%"=="0" (
  echo.
  echo ALL LATEST FILE CHECKS PASSED.
  echo.
  pause
  exit /b 0
)

echo.
echo CHECK FAILED. Missing or obsolete files were detected.
echo.
pause
exit /b 1

:check
if exist %1 (
  echo [OK] %~1
) else (
  echo [NG] missing: %~1
  set "NG=1"
)
exit /b 0
