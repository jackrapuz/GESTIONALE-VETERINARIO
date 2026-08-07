@echo off
REM Crea la cartella dist\Gestionale\ (programma + librerie) con PyInstaller.
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
echo Fatto. Trovi il programma nella cartella:  dist\Gestionale\
echo Si consegna la CARTELLA INTERA, non il solo .exe: senza _internal non parte.
echo Al primo avvio creera' al proprio interno la cartella "dati".
echo.
echo AGGIORNAMENTO: estrarre il nuovo pacchetto SOPRA la cartella esistente
echo rispondendo "Sostituisci". Non cancellarla mai: contiene "dati".
pause
