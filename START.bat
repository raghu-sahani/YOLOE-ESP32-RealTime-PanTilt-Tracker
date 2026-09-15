@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv-yolo\Scripts\python.exe" (
  py -3 -m venv .venv-yolo
  if errorlevel 1 goto failed
)
if not exist ".venv-yolo\installed.txt" (
  ".venv-yolo\Scripts\python.exe" setup_dependencies.py
  if errorlevel 1 goto failed
  echo installed>".venv-yolo\installed.txt"
)
".venv-yolo\Scripts\python.exe" download_model.py
if errorlevel 1 goto failed
".venv-yolo\Scripts\python.exe" studio.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo Setup or startup failed. Keep this window open and send its error text.
echo Python 3.11 or 3.12 for Windows is recommended.
pause
exit /b 1
