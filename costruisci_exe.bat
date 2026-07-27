@echo off
REM Crea l'eseguibile Gestionale.exe con PyInstaller.
REM Da lanciare una sola volta (o quando cambia il codice) su un PC con Python 3.12.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Preparazione ambiente...
  py -3 -m venv .venv
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo.
echo Costruzione eseguibile in corso...
pyinstaller --clean --noconfirm Gestionale.spec

echo.
echo Fatto. Trovi l'eseguibile in:  dist\Gestionale.exe
echo Copialo dove vuoi: al primo avvio creera' accanto a se' la cartella "dati".
pause
