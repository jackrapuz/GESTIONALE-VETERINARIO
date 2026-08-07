"""I dati sopravvivono alla sostituzione dell'eseguibile.

**Il requisito.** Il gestionale viene aggiornato copiando un exe nuovo sopra il
vecchio. Se la cartella "dati" fosse legata all'eseguibile invece che alla
cartella che lo contiene, ogni aggiornamento presenterebbe alla dottoressa un
programma vuoto: fatture, clienti e backup ancora sul disco ma invisibili. E' il
difetto peggiore che questo programma possa avere, perche' non da' errore.

Questi test guardano la regola, non il caso singolo: il ramo congelato non si puo'
percorrere sotto pytest (``sys.frozen`` e' sempre falso), quindi viene esercitato
passando i parametri a ``_radice_dati``.
"""
from pathlib import Path

from app import backup, db, invio


def test_da_exe_i_dati_stanno_accanto_all_eseguibile():
    """Sostituire l'exe nella stessa cartella non deve toccare "dati"."""
    radice = db._radice_dati(
        congelato=True,
        eseguibile=Path(r"C:\Gestionale\Gestionale.exe"),
        sorgente=Path(r"C:\temp\_MEI123456\app\db.py"),
    )
    assert radice == Path(r"C:\Gestionale")
    assert (radice / "dati") == Path(r"C:\Gestionale\dati")


def test_da_exe_i_dati_non_finiscono_mai_nella_cartella_temporanea():
    """_MEIPASS viene cancellata alla chiusura: i dati sparirebbero a ogni avvio.

    La sorgente passata *e'* dentro una cartella temporanea di PyInstaller: se la
    radice la seguisse, il difetto sarebbe silenzioso e distruttivo.
    """
    temporanea = Path(r"C:\temp\_MEI123456")
    radice = db._radice_dati(
        congelato=True,
        eseguibile=Path(r"C:\Gestionale\Gestionale.exe"),
        sorgente=temporanea / "app" / "db.py",
    )
    assert temporanea not in radice.parents and radice != temporanea


def test_in_sviluppo_i_dati_stanno_alla_radice_del_progetto():
    """Senza exe la radice e' la cartella che contiene "app/"."""
    radice = db._radice_dati(
        congelato=False,
        eseguibile=Path(r"C:\Python\python.exe"),
        sorgente=Path(r"C:\progetto\app\db.py"),
    )
    assert radice == Path(r"C:\progetto")


def test_nessun_modulo_si_inventa_un_percorso_dati():
    """Backup e PDF da inviare devono stare DENTRO la cartella dati.

    Se un modulo ricalcolasse la radice per conto suo, l'aggiornamento potrebbe
    spostare solo una parte dei dati: quella divergenza si scoprirebbe tardi.
    """
    assert backup.BACKUP_DIR.parent == db.DATI_DIR
    assert invio.CARTELLA_INVII.parent == db.DATI_DIR


def test_il_database_sta_nella_cartella_dati():
    assert db.DB_PATH.parent == db.DATI_DIR
