"""Backup e ripristino del database.

Il backup usa l'API ufficiale di SQLite (``Connection.backup``) che produce una
copia coerente anche mentre l'app e' in uso (niente file mezzo scritti). I backup
finiscono in ``dati/backup/``. Il ripristino crea PRIMA una copia di sicurezza
del database attuale, poi vi sovrascrive il contenuto del backup scelto.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.db import DATI_DIR, DB_PATH, get_conn

BACKUP_DIR = DATI_DIR / "backup"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def crea_backup(prefisso: str = "backup") -> Path:
    """Crea una copia coerente del DB in ``dati/backup/`` e restituisce il percorso."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    dest = BACKUP_DIR / f"{prefisso}_{_timestamp()}.db"
    src = get_conn(DB_PATH)
    try:
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return dest


def elenco_backup() -> list[dict]:
    """Elenco dei backup disponibili (piu' recenti prima)."""
    if not BACKUP_DIR.exists():
        return []
    file = sorted(BACKUP_DIR.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {"nome": p.name,
         "dimensione_kb": round(p.stat().st_size / 1024, 1),
         "data": datetime.fromtimestamp(p.stat().st_mtime).strftime("%d/%m/%Y %H:%M")}
        for p in file
    ]


def _valido_db(path: Path) -> bool:
    """Verifica minima che il file sia un DB SQLite integro con le tabelle attese."""
    try:
        c = sqlite3.connect(str(path))
        try:
            if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                return False
            nomi = {r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            return {"studio", "clienti", "fatture"}.issubset(nomi)
        finally:
            c.close()
    except sqlite3.DatabaseError:
        return False


def ripristina(nome_backup: str) -> Path:
    """Ripristina il DB dal backup indicato (in ``dati/backup/``).

    Crea prima una copia di sicurezza del DB corrente. Solleva ``ValueError`` se
    il file non esiste o non e' un DB valido.

    ``nome_backup`` arriva da un modulo, quindi si prende **solo il nome**: un
    valore come ``..\\..\\altro.db`` uscirebbe dalla cartella dei backup e
    farebbe sovrascrivere il database con un file qualsiasi del computer. Non e'
    un attacco - qui l'unica che usa il programma e' la dottoressa - ma
    l'operazione piu' distruttiva che il gestionale sa fare non deve poter
    puntare fuori dalla sua cartella.
    """
    nome = Path(nome_backup or "").name
    if not nome:
        raise ValueError("File di backup non trovato.")
    origine = BACKUP_DIR / nome
    if not origine.exists():
        raise ValueError("File di backup non trovato.")
    return ripristina_da_file(origine)


def ripristina_da_file(origine: Path) -> Path:
    """Ripristina il DB dal file indicato (percorso qualsiasi)."""
    origine = Path(origine)
    if not _valido_db(origine):
        raise ValueError("Il file selezionato non e' un backup valido del gestionale.")
    sicurezza = crea_backup(prefisso="pre-ripristino")
    src = sqlite3.connect(str(origine))
    try:
        dst = get_conn(DB_PATH)
        try:
            src.backup(dst)  # sovrascrive il contenuto del DB attivo
        finally:
            dst.close()
    finally:
        src.close()
    return sicurezza
