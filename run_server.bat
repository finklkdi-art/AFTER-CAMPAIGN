@echo off
setlocal

rem ============================================================
rem  AFTER - Campaign intelligence, after the campaign.
rem  Intranet server launcher (Windows)
rem
rem  NOTE: This file is intentionally ASCII-only.
rem        cmd.exe parses .bat with the active OEM codepage, so
rem        Korean text here breaks depending on the machine.
rem
rem  .streamlit/config.toml belongs to the single-user local
rem  setup (app.py) and is left untouched. Server settings are
rem  injected as CLI flags, which override config.toml.
rem
rem  Usage:  run_server.bat        (port 8501)
rem          run_server.bat 9000   (custom port)
rem ============================================================

cd /d "%~dp0"

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8501"

echo.
echo  ============================================================
echo   AFTER  ^|  starting in SERVER mode
echo  ============================================================
echo   Port         : %PORT%
echo   Bind address : 0.0.0.0  (all intranet interfaces)
echo   Max upload   : 200 MB
echo   Stop         : Ctrl+C
echo  ------------------------------------------------------------
echo   Run "ipconfig" in another window to find the intranet URL.
echo  ============================================================
echo.

python -m streamlit run web_main.py ^
  --server.address=0.0.0.0 ^
  --server.port=%PORT% ^
  --server.maxUploadSize=200 ^
  --server.headless=true ^
  --browser.gatherUsageStats=false

endlocal
