"""Test dell'emissione fattura (service layer, DB temporaneo)."""
import sqlite3

import pytest

from app.calcolo import RigaInput
from app.db import get_conn, init_db
from app.fatturazione import emetti_fattura
from app.numerazione import verifica_continuita


@pytest.fixture()
def conn(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    c = get_conn(db)
    # un cliente di prova (persona fisica)
    c.execute(
        "INSERT INTO clienti (tipo, nome, cognome, codice_fiscale) "
        "VALUES ('fisica','Mario','Rossi','RSSMRA85T10A562S')"
    )
    c.commit()
    yield c
    c.close()


def _cliente(conn):
    return conn.execute("SELECT * FROM clienti WHERE id=1").fetchone()


def test_emissione_totali_e_numero(conn):
    esito = emetti_fattura(
        conn, cliente=_cliente(conn),
        righe=[RigaInput("Visita clinica equino", 1, "80", "22")],
        data_emissione="2026-03-01",
    )
    assert esito["numero"] == 1
    assert esito["numero_visualizzato"] == "1/2026"
    r = esito["risultato"]
    assert str(r.imponibile) == "80.00"
    assert str(r.contributo_enpav) == "1.60"
    assert str(r.base_iva) == "81.60"
    assert str(r.iva_totale) == "17.95"
    assert str(r.totale_documento) == "99.55"

    # persistenza: fattura + riga + snapshot cliente
    f = conn.execute("SELECT * FROM fatture WHERE id=?", (esito["id"],)).fetchone()
    assert f["cli_denominazione"] == "Rossi Mario"
    assert f["cli_codice_fiscale"] == "RSSMRA85T10A562S"
    assert f["totale_documento"] == "99.55"
    n_righe = conn.execute(
        "SELECT COUNT(*) FROM righe_fattura WHERE fattura_id=?", (esito["id"],)
    ).fetchone()[0]
    assert n_righe == 1


def test_numerazione_progressiva_senza_buchi(conn):
    for atteso in (1, 2, 3):
        esito = emetti_fattura(
            conn, cliente=_cliente(conn),
            righe=[RigaInput("Prestazione", 1, "50", "22")],
            data_emissione="2026-05-10",
        )
        assert esito["numero"] == atteso
    assert verifica_continuita(conn, 2026, "fattura") == []


def test_rollback_non_brucia_il_numero(conn):
    """Se l'inserimento fallisce, il numero riservato viene annullato (niente buchi)."""
    # Inseriamo a mano una fattura n.1/2026 SENZA toccare il contatore.
    conn.execute(
        "INSERT INTO fatture (tipo_documento, anno, numero_progressivo, "
        "numero_visualizzato, data_emissione) VALUES ('fattura',2026,1,'1/2026','2026-01-01')"
    )
    conn.commit()
    # L'emissione assegnera' di nuovo il n.1 -> viola UNIQUE(tipo,anno,numero) -> rollback.
    with pytest.raises(sqlite3.IntegrityError):
        emetti_fattura(
            conn, cliente=_cliente(conn),
            righe=[RigaInput("Prestazione", 1, "50", "22")],
            data_emissione="2026-02-01",
        )
    # Il contatore NON deve essere avanzato dalla transazione annullata.
    row = conn.execute(
        "SELECT ultimo_numero FROM numerazione WHERE anno=2026 AND tipo_documento='fattura'"
    ).fetchone()
    assert row is None or int(row["ultimo_numero"]) == 0


def test_nota_credito_ha_sequenza_separata(conn):
    f = emetti_fattura(
        conn, cliente=_cliente(conn),
        righe=[RigaInput("Prestazione", 1, "100", "22")],
        data_emissione="2026-04-01",
    )
    nc = emetti_fattura(
        conn, cliente=_cliente(conn), tipo_documento="nota_credito",
        righe=[RigaInput("Storno", 1, "100", "22")],
        data_emissione="2026-04-02", documento_riferimento_id=f["id"],
    )
    assert f["numero"] == 1 and nc["numero"] == 1  # sequenze indipendenti
    # totali speculari
    assert f["risultato"].totale_documento == nc["risultato"].totale_documento
