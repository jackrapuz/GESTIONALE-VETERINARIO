"""Test del registro prestazioni (service layer, DB temporaneo)."""
import sqlite3

import pytest

from app.db import get_conn, init_db
from app.registro import annota, da_fatturare, genera_fattura, genera_proforma


@pytest.fixture()
def conn(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    c = get_conn(db)
    # Un cliente a fatturazione mensile con due cavalli, e uno una-tantum.
    c.execute(
        "INSERT INTO clienti (tipo, nome, cognome, codice_fiscale, fatturazione_mensile) "
        "VALUES ('fisica','Franci','Sesia','SSEFNC80A01A562S',1)"
    )
    c.execute("INSERT INTO pazienti (cliente_id, nome) VALUES (1,'GUUS')")
    c.execute("INSERT INTO pazienti (cliente_id, nome) VALUES (1,'FULLY LOADED')")
    c.execute(
        "INSERT INTO clienti (tipo, nome, cognome, codice_fiscale, fatturazione_mensile) "
        "VALUES ('fisica','Maria','Rossi','RSSMRA85T10A562S',0)"
    )
    c.commit()
    yield c
    c.close()


def _studio(conn):
    return dict(conn.execute("SELECT * FROM studio WHERE id=1").fetchone())


def _annota_mensile(conn):
    annota(conn, data_prestazione="2026-05-26", cliente_id=1, paziente_id=1,
           descrizione="Visita + anestesia", prezzo_unitario="190")
    annota(conn, data_prestazione="2026-06-16", cliente_id=1, paziente_id=1,
           descrizione="Controllo montato", prezzo_unitario="120")
    annota(conn, data_prestazione="2026-07-02", cliente_id=1, paziente_id=2,
           descrizione="Esame del sangue", prezzo_unitario="100")


def test_annota_e_da_fatturare(conn):
    _annota_mensile(conn)
    gruppi = da_fatturare(conn)
    assert len(gruppi) == 1
    g = gruppi[0]
    assert g["denominazione"] == "Sesia Franci"
    assert g["fatturazione_mensile"] is True
    assert g["totale"] == "410.00"
    assert len(g["voci"]) == 3


def test_genera_fattura_lega_le_voci(conn):
    _annota_mensile(conn)
    esito = genera_fattura(conn, 1, _studio(conn))
    # totale = 410 imponibile + 2% ENPAV + 22% IVA
    assert str(esito["risultato"].totale_documento) == "510.20"
    # le voci risultano legate alla fattura e spariscono da "da fatturare"
    n_legate = conn.execute(
        "SELECT COUNT(*) FROM prestazioni_eseguite WHERE fattura_id=?", (esito["id"],)
    ).fetchone()[0]
    assert n_legate == 3
    assert da_fatturare(conn) == []
    # snapshot cavallo + data sulle righe della fattura
    righe = conn.execute(
        "SELECT paziente_nome, data_prestazione FROM righe_fattura "
        "WHERE fattura_id=? ORDER BY ordine", (esito["id"],)
    ).fetchall()
    assert {r["paziente_nome"] for r in righe} == {"GUUS", "FULLY LOADED"}
    assert all(r["data_prestazione"] for r in righe)


def test_seconda_generazione_non_ripesca(conn):
    _annota_mensile(conn)
    genera_fattura(conn, 1, _studio(conn))
    with pytest.raises(ValueError):
        genera_fattura(conn, 1, _studio(conn))  # niente piu' voci da fatturare


def test_rollback_lascia_le_voci_da_fatturare(conn):
    """Se l'emissione fallisce, le voci restano da fatturare e il numero non si brucia."""
    _annota_mensile(conn)
    # Pre-inserisco una fattura 1/2026 SENZA toccare il contatore: la generazione
    # tentera' di riassegnare il n.1 -> viola UNIQUE -> rollback totale.
    conn.execute(
        "INSERT INTO fatture (tipo_documento, anno, numero_progressivo, "
        "numero_visualizzato, data_emissione) VALUES ('fattura',2026,1,'1/2026','2026-01-01')"
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        genera_fattura(conn, 1, _studio(conn))
    # nessuna voce marcata fatturata
    n_legate = conn.execute(
        "SELECT COUNT(*) FROM prestazioni_eseguite WHERE fattura_id IS NOT NULL"
    ).fetchone()[0]
    assert n_legate == 0
    assert len(da_fatturare(conn)[0]["voci"]) == 3
    # contatore non avanzato
    row = conn.execute(
        "SELECT ultimo_numero FROM numerazione WHERE anno=2026 AND tipo_documento='fattura'"
    ).fetchone()
    assert row is None or int(row["ultimo_numero"]) == 0


def test_annotare_non_tocca_fatture_ne_numerazione(conn):
    """Invariante anti-Trappola: le voci del registro NON entrano in ``fatture``.

    Cruscotto, export commercialista e continuita' numerazione leggono ``fatture``:
    finche' non si genera un documento, nulla di tutto cio' deve cambiare.
    """
    from app.export_commercialista import registro as registro_commercialista
    from app.numerazione import verifica_continuita

    _annota_mensile(conn)
    assert conn.execute("SELECT COUNT(*) FROM fatture").fetchone()[0] == 0
    assert verifica_continuita(conn, 2026, "fattura") == []
    assert registro_commercialista(conn, "2026-01-01", "2026-12-31") == []


def test_proforma_non_consuma_le_voci(conn):
    """La proforma e' non fiscale: le voci restano da fatturare."""
    _annota_mensile(conn)
    genera_proforma(conn, 1, _studio(conn))
    # le voci restano da fatturare (solo proforma_id valorizzato)
    assert len(da_fatturare(conn)[0]["voci"]) == 3
    n_proforma = conn.execute(
        "SELECT COUNT(*) FROM prestazioni_eseguite WHERE proforma_id IS NOT NULL"
    ).fetchone()[0]
    assert n_proforma == 3
