@echo off
setlocal

cd /d "%~dp0"

if exist "dist\QuizOfficeHelper.exe" (
  echo [Quiz Office Helper] EXE ishga tushirilmoqda...
  start "" "dist\QuizOfficeHelper.exe"
  echo [Quiz Office Helper] Tayyor.
  exit /b 0
)

if not exist ".venv\Scripts\python.exe" (
  echo [Quiz Office Helper] Virtual environment topilmadi. Yaratilmoqda...
  py -m venv .venv || python -m venv .venv
)

echo [Quiz Office Helper] Dependency o'rnatilmoqda...
".venv\Scripts\python.exe" -m pip install -r requirements.txt

echo [Quiz Office Helper] Dastur ishga tushirilmoqda...
start "" ".venv\Scripts\python.exe" bridge.py

echo [Quiz Office Helper] Tayyor. Brauzerda http://127.0.0.1:8765 ni tekshirishingiz mumkin.
pause
