@echo off
rem ---------------------------------------------------------------------------
rem  Crea sul Desktop il collegamento "Gestionale Studio".
rem
rem  Da usare cosi': mettere questo file nella STESSA cartella di Gestionale.exe
rem  e farci doppio clic. Il collegamento prende da solo l'icona dell'exe.
rem  Si puo' rieseguire quante volte si vuole: riscrive il collegamento.
rem ---------------------------------------------------------------------------
setlocal
set "CARTELLA=%~dp0"
set "ESEGUIBILE=%CARTELLA%Gestionale.exe"

if not exist "%ESEGUIBILE%" (
  echo.
  echo   Non trovo Gestionale.exe in questa cartella:
  echo   %CARTELLA%
  echo.
  echo   Copia questo file accanto a Gestionale.exe e riprova.
  echo.
  pause
  exit /b 1
)

rem Il Desktop viene chiesto a Windows: funziona anche se e' su OneDrive
rem o se il profilo utente sta in un percorso non standard.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s = New-Object -ComObject WScript.Shell;" ^
  "$desktop = $s.SpecialFolders('Desktop');" ^
  "$c = $s.CreateShortcut((Join-Path $desktop 'Gestionale Studio.lnk'));" ^
  "$c.TargetPath = '%ESEGUIBILE%';" ^
  "$c.WorkingDirectory = '%CARTELLA:~0,-1%';" ^
  "$c.IconLocation = '%ESEGUIBILE%,0';" ^
  "$c.Description = 'Gestionale fatturazione dello studio veterinario';" ^
  "$c.Save();" ^
  "Write-Host ('  Collegamento creato in: ' + $desktop)"

if errorlevel 1 (
  echo.
  echo   Qualcosa e' andato storto nella creazione del collegamento.
  echo.
  pause
  exit /b 1
)

echo.
echo   Fatto. Sul Desktop trovi "Gestionale Studio": doppio clic per avviare.
echo.
pause
