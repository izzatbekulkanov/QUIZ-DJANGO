@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [Quiz Office Helper] Virtual environment yaratilmoqda...
  py -m venv .venv || python -m venv .venv
)

echo [Quiz Office Helper] Build uchun kutubxonalar o'rnatilmoqda...
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller

echo [Quiz Office Helper] EXE yig'ilmoqda...
".venv\Scripts\pyinstaller.exe" --noconfirm --clean --onefile --noconsole --name QuizOfficeHelper bridge.py

echo [Quiz Office Helper] Tayyor: dist\QuizOfficeHelper.exe
pause
