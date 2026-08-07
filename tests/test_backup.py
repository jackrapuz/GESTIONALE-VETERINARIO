"""Backup e ripristino: la rete di sicurezza dei dati, finora senza test.

E' il modulo che la dottoressa userebbe nel momento peggiore — dopo un errore,
con le fatture dell'anno dentro. Se qui qualcosa non funziona non c'e' una
seconda rete: proprio per questo non poteva restare l'unico pezzo importante
senza prove.
"""
import sqlite3

import pytest

from app import backup as bkp
from app.db import init_db


@pytest.fixture()
def archivio(tmp_path, monkeypatch):
    """Un database vero e una cartella di backup, tutti dentro tmp_path."""
    db = tmp_path / "gestionale.db"
    init_db(db)
    conn = sqlite3.connect(db)
    with conn:
        conn.execute("INSERT INTO clienti (tipo, nome, cognome, codice_fiscale) "
                     "VALUES ('fisica','Mario','Rossi','')")
    conn.close()

    monkeypatch.setattr(bkp, "DB_PATH", db)
    monkeypatch.setattr(bkp, "BACKUP_DIR", tmp_path / "backup")
    return db


def _clienti(db) -> list[str]:
    c = sqlite3.connect(db)
    try:
        return [r[0] for r in c.execute("SELECT cognome FROM clienti ORDER BY id")]
    finally:
        c.close()


def test_il_backup_e_una_copia_leggibile(archivio):
    dest = bkp.crea_backup()
    assert dest.exists()
    assert _clienti(dest) == ["Rossi"], "la copia non contiene i dati"


def test_l_elenco_mette_prima_i_piu_recenti(archivio):
    import os
    import time

    primo = bkp.crea_backup(prefisso="a")
    time.sleep(0.05)
    secondo = bkp.crea_backup(prefisso="b")
    # I nomi contengono i secondi: su una macchina veloce sarebbero uguali, e a
    # ordinare e' comunque la data di modifica. La rendo esplicitamente diversa.
    os.utime(primo, (1, 1))

    nomi = [b["nome"] for b in bkp.elenco_backup()]
    assert nomi[0] == secondo.name


def test_un_file_qualsiasi_non_viene_scambiato_per_un_backup(archivio, tmp_path):
    """Ripristinare da un file sbagliato distruggerebbe l'archivio vero."""
    finto = tmp_path / "foto.db"
    finto.write_bytes(b"non sono un database")
    with pytest.raises(ValueError):
        bkp.ripristina_da_file(finto)


def test_un_database_di_un_altro_programma_viene_rifiutato(archivio, tmp_path):
    """E' un SQLite valido, ma non e' il gestionale: mancano le tabelle."""
    altro = tmp_path / "altro.db"
    c = sqlite3.connect(altro)
    with c:
        c.execute("CREATE TABLE ricette (id INTEGER)")
    c.close()
    with pytest.raises(ValueError):
        bkp.ripristina_da_file(altro)


def test_il_ripristino_salva_prima_com_era(archivio):
    """**La garanzia che rende il ripristino non spaventoso.** Se si sceglie il
    backup sbagliato, quello di prima e' ancora li'."""
    copia = bkp.crea_backup()

    conn = sqlite3.connect(archivio)
    with conn:
        conn.execute("INSERT INTO clienti (tipo, nome, cognome, codice_fiscale) "
                     "VALUES ('fisica','Laura','Neri','')")
    conn.close()
    assert _clienti(archivio) == ["Rossi", "Neri"]

    sicurezza = bkp.ripristina(copia.name)

    assert _clienti(archivio) == ["Rossi"], "il ripristino non ha riportato indietro"
    assert sicurezza.exists()
    assert _clienti(sicurezza) == ["Rossi", "Neri"], \
        "la copia di sicurezza non contiene com'era prima del ripristino"


def test_il_ripristino_non_esce_dalla_cartella_dei_backup(archivio, tmp_path):
    """Il nome arriva da un modulo. Un valore come ``..\\..\\altro.db`` farebbe
    sovrascrivere il database con un file qualsiasi del computer: l'operazione
    piu' distruttiva del gestionale non deve poter puntare fuori casa."""
    fuori = tmp_path / "estraneo.db"
    init_db(fuori)
    c = sqlite3.connect(fuori)
    with c:
        c.execute("INSERT INTO clienti (tipo, nome, cognome, codice_fiscale) "
                  "VALUES ('fisica','Estraneo','Estraneo','')")
    c.close()

    with pytest.raises(ValueError):
        bkp.ripristina(f"..\\..\\{fuori.name}")
    with pytest.raises(ValueError):
        bkp.ripristina("../../estraneo.db")

    assert _clienti(archivio) == ["Rossi"], "l'archivio e' stato toccato"


def test_ripristinare_un_backup_inesistente_lo_dice(archivio):
    with pytest.raises(ValueError):
        bkp.ripristina("non_esiste.db")
    with pytest.raises(ValueError):
        bkp.ripristina("")
