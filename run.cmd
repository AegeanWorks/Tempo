@echo off
rem One-click run for Tempo on Windows: double-click this file.
rem Starts the server (python run.py, same defaults) and opens the page
rem in your default browser once the server answers. Any arguments are
rem passed through to run.py, including --port and --state.
setlocal
set PORT=8765
if not "%~1"=="" (
  for %%a in (%*) do (
    if defined TAKE_NEXT (
      set PORT=%%a
      set TAKE_NEXT=
    ) else if "%%a"=="--port" (
      set TAKE_NEXT=1
    )
  )
)
start "Tempo server" python "%~dp0run.py" %*
for /L %%i in (1,1,30) do (
  powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:%PORT%/' -UseBasicParsing -TimeoutSec 1 | Out-Null; exit 0 } catch { exit 1 }"
  if not errorlevel 1 goto open
  timeout /t 1 /nobreak >nul
)
echo The server did not answer on port %PORT% within 30 seconds.
echo The "Tempo server" window should show why - fix that, then double-click again.
pause
exit /b 1
:open
start "" "http://127.0.0.1:%PORT%/"
