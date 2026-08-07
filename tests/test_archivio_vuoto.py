"""Il primo giorno: archivio appena creato, niente dentro.

E' lo stato in cui la dottoressa trovera' il programma appena installato, ed era
l'unico che nessun test copriva: gli altri partono dall'archivio di sviluppo, che
e' pieno di dati di esempio. Un export che si rompe su zero fatture si scoprirebbe
il primo giorno, davanti a lei.
"""
import sqlite3

import pytest

from app import export_commercialista as exc
from app import export_ts
from app.db import init_db
from app.registro import da_fatturare


@pytest.fixture()
def vuoto(tmp_path):
    """Un database appena inizializzato: schema completo, tabelle vuote."""
    db = tmp_path / "gestionale.db"
    init_db(db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


def _studio(conn) -> dict:
    return dict(conn.execute("SELECT * FROM studio WHERE id=1").fetchone())


def test_lo_schema_nasce_gia_alla_versione_corrente(vuoto):
    from app.db import MIGRATIONS
    assert vuoto.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)


def test_c_e_una_riga_studio_da_subito(vuoto):
    """Ogni pagina la legge con ``fetchone()`` senza controllare il ``None``: se
    non ci fosse, il gestionale non si aprirebbe nemmeno."""
    assert _studio(vuoto)


def test_il_registro_vuoto_non_e_un_errore(vuoto):
    assert da_fatturare(vuoto) == []


def test_gli_export_del_commercialista_reggono_zero_fatture(vuoto):
    dal, al = "2026-01-01", "2026-12-31"
    assert exc.registro(vuoto, dal, al) == []

    csv = exc.genera_csv(vuoto, dal, al)
    assert csv, "il CSV vuoto deve avere almeno le intestazioni"

    xlsx = exc.genera_xlsx(vuoto, dal, al)
    assert xlsx.startswith(b"PK"), "non e' un file Excel"

    zip_pdf = exc.genera_zip_pdf(vuoto, dal, al, _studio(vuoto))
    assert zip_pdf.startswith(b"PK")


def test_l_export_sistema_ts_regge_zero_fatture(vuoto):
    esito = export_ts.genera_export(vuoto, "2026-01-01", "2026-12-31", _studio(vuoto))
    assert esito["n_ok"] == 0
    assert esito["n_scarti"] == 0
    assert esito["n_esclusi"] == 0
    assert export_ts.report_problemi_csv(esito) is not None
