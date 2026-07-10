@echo off
rem Sets up and starts Harmonica. Safe to run again at any time.
cd /d "%~dp0"

rem 1. uv (the Python package manager): install if missing.
where uv >nul 2>nul
if errorlevel 1 (
  echo Installing uv, the Python package manager...
  powershell -ExecutionPolicy ByPass -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

rem 2. Python dependencies.
call uv sync
if errorlevel 1 goto fail

rem 3. Build the player UI once (needs Node.js; skipped when already built).
if exist web\dist\index.html goto run
where npm >nul 2>nul
if errorlevel 1 (
  echo Node.js is needed to build the player UI, a one-off step.
  echo Install it from https://nodejs.org, then run this script again.
  pause
  exit /b 1
)
pushd web
call npm install
if errorlevel 1 ( popd & goto fail )
call npm run build
if errorlevel 1 ( popd & goto fail )
popd

:run
rem 4. Open the player and start the daemon (close this window to stop it).
start "" /min cmd /c "timeout /t 3 /nobreak >nul & start "" http://127.0.0.1:8765"
echo Harmonica is starting at http://127.0.0.1:8765 (close this window to stop it).
call uv run harmonica serve
goto :eof

:fail
echo Setup failed. See the messages above.
pause
exit /b 1
