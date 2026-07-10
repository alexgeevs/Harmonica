@echo off
rem Downloads Harmonica into your user folder, sets it up, and starts it.
rem For Windows. Safe to run again at any time.
cd /d "%USERPROFILE%"

if not exist Harmonica (
  curl -L -o harmonica.tar.gz https://github.com/alexgeevs/Harmonica/archive/refs/tags/v1.0.0.tar.gz || goto fail
  tar -xzf harmonica.tar.gz || goto fail
  ren Harmonica-1.0.0 Harmonica
  del harmonica.tar.gz
  echo Harmonica downloaded to %USERPROFILE%\Harmonica
)

cd Harmonica
call start-harmonica.bat
exit /b

:fail
echo Something went wrong. Check your internet connection and try again.
pause
exit /b 1
