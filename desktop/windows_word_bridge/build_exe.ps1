$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[Quiz Office Helper] Virtual environment yaratilmoqda..."
    try {
        py -m venv .venv
    }
    catch {
        python -m venv .venv
    }
}

Write-Host "[Quiz Office Helper] Build uchun kutubxonalar o'rnatilmoqda..."
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller

Write-Host "[Quiz Office Helper] EXE yig'ilmoqda..."
& ".\.venv\Scripts\pyinstaller.exe" --noconfirm --clean --onefile --noconsole --name QuizOfficeHelper bridge.py

Write-Host "[Quiz Office Helper] Tayyor: dist\QuizOfficeHelper.exe"
