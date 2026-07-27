"""Test della numerazione progressiva e della verifica di continuita'."""
import pytest

from app.db import get_conn, init_db
from app.numerazione import assegna_numero, formatta_numero, verifica_continuita


@pytest.fixture()
def conn(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    c = get_conn(db)
    yield c
    c.close()


def _inserisci_fattura(conn, anno, numero, stato="emessa"):
    conn.execute(
        "INSERT INTO fatture (tipo_documento, anno, numero_progressivo, "
        "numero_visualizzato, data_emissione, stato) VALUES ('fattura',?,?,?,?,?)",
        (anno, numero, f"{numero}/{anno}", f"{anno}-01-01", stato),
    )
    conn.commit()


def test_sequenza_per_anno(conn):
    assert assegna_numero(conn, 2026) == 1
    assert assegna_numero(conn, 2026) == 2
    assert assegna_numero(conn, 2026) == 3
    # anno diverso riparte da 1
    assert assegna_numero(conn, 2027) == 1


def test_sequenze_separate_per_tipo(conn):
    assert assegna_numero(conn, 2026, "fattura") == 1
    assert assegna_numero(conn, 2026, "nota_credito") == 1
    assert assegna_numero(conn, 2026, "fattura") == 2


def test_continuita_senza_buchi(conn):
    for n in (1, 2, 3):
        _inserisci_fattura(conn, 2026, n)
    assert verifica_continuita(conn, 2026) == []


def test_continuita_con_buco(conn):
    _inserisci_fattura(conn, 2026, 1)
    _inserisci_fattura(conn, 2026, 3)
    assert verifica_continuita(conn, 2026) == [2]


def test_annullata_non_conta_come_buco(conn):
    # una fattura annullata non deve rientrare nella sequenza attesa
    _inserisci_fattura(conn, 2026, 1)
    _inserisci_fattura(conn, 2026, 2, stato="annullata")
    assert verifica_continuita(conn, 2026) == []


def test_formatta_numero():
    assert formatta_numero(1, 2026) == "1/2026"
    assert formatta_numero(7, 2026, "FT-{anno}-{n}") == "FT-2026-7"
    # formato errato -> fallback sicuro
    assert formatta_numero(5, 2026, "{sbagliato}") == "5/2026"
