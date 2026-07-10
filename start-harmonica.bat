@echo off
rem Sets up and starts Harmonica. Safe to run again at any time.
cd /d "%~dp0"

rem uv (the Python package manager): install it if missing.
where uv >nul 2>nul || powershell -ExecutionPolicy ByPass -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

rem Install Python dependencies.
call uv sync || goto fail

rem Build the player UI once (needs Node.js from https://nodejs.org).
if not exist web\dist\index.html (
  cd web
  call npm install || goto fail
  call npm run build || goto fail
  cd ..
)

rem Start Harmonica and open it in the browser (close this window to stop it).
start "" /min cmd /c "timeout /t 3 /nobreak >nul & start "" http://127.0.0.1:8765"
call uv run harmonica serve
exit /b

:fail
echo Something went wrong. See the message above.
pause
exit /b 1
