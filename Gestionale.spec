# -*- mode: python ; coding: utf-8 -*-
"""Configurazione PyInstaller per produrre un unico Gestionale.exe.

Racchiude template e static nel pacchetto; la cartella "dati" viene invece creata
ACCANTO all'eseguibile al primo avvio (vedi app/db.py, ramo sys.frozen), cosi' i
dati persistono tra un avvio e l'altro.
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
    a.binaries,
    a.datas,
    [],
    name="Gestionale",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
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
