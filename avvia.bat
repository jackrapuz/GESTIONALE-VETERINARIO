@echo off
REM Avvio del Gestionale senza eseguibile (fallback).
REM Richiede Python 3.12 installato. Crea un ambiente locale al primo avvio.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Primo avvio: preparazione in corso, attendere...
  py -3 -m venv .venv
  call ".venv\Scripts\activate.bat"
  python -m pip install --upgrade pip >nul
  python -m pip install -r requirements.txt
) else (
  call ".venv\Scripts\activate.bat"
)

python -m app.main
pause
