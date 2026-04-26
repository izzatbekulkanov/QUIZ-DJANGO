$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

if (Test-Path "dist\QuizOfficeHelper.exe") {
    Write-Host "[Quiz Office Helper] EXE ishga tushirilmoqda..."
    Start-Process -FilePath ".\dist\QuizOfficeHelper.exe" -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
    Write-Host "[Quiz Office Helper] Tayyor."
    exit
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[Quiz Office Helper] Virtual environment topilmadi. Yaratilmoqda..."
    try {
        py -m venv .venv
    }
    catch {
        python -m venv .venv
    }
}

Write-Host "[Quiz Office Helper] Dependency o'rnatilmoqda..."
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host "[Quiz Office Helper] Dastur ishga tushirilmoqda..."
Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "bridge.py" -WorkingDirectory $PSScriptRoot

Write-Host "[Quiz Office Helper] Tayyor. http://127.0.0.1:8765 ni tekshirishingiz mumkin."
