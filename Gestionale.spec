# -*- mode: python ; coding: utf-8 -*-
"""Configurazione PyInstaller: una CARTELLA "Gestionale", non un file unico.

**Perche' non piu' il file unico.** Un eseguibile onefile porta l'archivio dentro
di se' e a ogni avvio lo scompatta in %TEMP%\\_MEIxxxxx, per poi cancellarlo alla
chiusura. Quando la cancellazione non riesce - antivirus che tiene aperto un
file, chiusura forzata - la cartella resta. Sono state trovate **21 cartelle
abbandonate per 290 MB**, alcune vecchie di settimane, e ogni tanto usciva
l'errore "impossibile eliminare un file temporaneo". Su un computer che non ha
nessuno a guardarlo, quella roba cresce fino a farsi sentire.

Con la cartella non c'e' niente da scompattare e niente da cancellare: il difetto
sparisce alla radice. In piu' l'avvio e' piu' rapido di circa 400 ms (misurato) e
l'eseguibile non resta bloccato dopo la chiusura, cosa che faceva fallire le
ricostruzioni con ``PermissionError [WinError 5]``.

**La cartella "dati" resta accanto all'eseguibile** (vedi ``_radice_dati`` in
app/db.py), quindi ora vive DENTRO la cartella del programma. E' voluto: e' cio'
che permette di rimettere un eseguibile onefile gia' consegnato in quella stessa
cartella e ritrovare lo stesso archivio. Spostare i dati altrove renderebbe cieche
tutte le versioni precedenti, che e' il disastro che VERSIONI.md esiste per
evitare.

Conseguenza sulla consegna: si aggiorna estraendo il pacchetto **sopra** la
cartella esistente, rispondendo "Sostituisci". La cartella non va mai cancellata,
perche' contiene i dati.
"""
from PyInstaller.utils.hooks import collect_submodules

datas = [
    ("app/templates", "app/templates"),
    ("app/static", "app/static"),
]

# uvicorn carica dinamicamente protocolli/loop/lifespan: vanno inclusi a mano.
hiddenimports = (
    collect_submodules("uvicorn")
    + ["anyio", "email_validator"]
)

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    # I binari NON entrano nell'eseguibile: e' questa riga che fa la cartella.
    exclude_binaries=True,
    name="Gestionale",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    # Nessuna finestra del terminale al doppio clic: si apre solo il browser.
    # Cio' che la console garantiva e' sostituito in app/main.py:
    #   - stdout/stderr dirottati su dati/avvio.log (senza, uvicorn muore al primo log);
    #   - errori di avvio mostrati in una finestrella di sistema, non in silenzio;
    #   - "Chiudi il gestionale" nel piede di ogni pagina, al posto della X sulla console;
    #   - un secondo doppio clic riapre l'istanza gia' in funzione invece di duplicarla.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="app/static/img/marchio.ico",   # marchio in ottone su fondo verde
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Gestionale",
)
