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


# --- sconto di anagrafica: i due percorsi devono coincidere -----------------

def test_lo_sconto_del_cliente_vale_anche_fatturando_dal_registro(conn):
    """Stesso cliente e stessa prestazione: fattura a mano e fattura dal registro
    devono dare lo stesso totale.

    Il registro annota il prezzo di LISTINO (il form lo precompila da li'), quindi
    lo sconto concordato in anagrafica va tolto all'emissione. Senza, il cliente
    veniva sovrafatturato solo perche' la fattura era nata dal registro.
    """
    from decimal import Decimal

    from app.calcolo import RigaInput
    from app.fatturazione import emetti_fattura

    conn.execute("UPDATE clienti SET sconto_default_pct='10.00' WHERE id=2")
    conn.commit()
    cliente = conn.execute("SELECT * FROM clienti WHERE id=2").fetchone()
    studio = {"enpav_pct": "2", "formato_numerazione": "{n}/{anno}"}

    a_mano = emetti_fattura(
        conn, cliente=dict(cliente),
        righe=[RigaInput("Visita", Decimal(1), Decimal("100"), Decimal(22))],
        data_emissione="2026-07-30", sconto_cliente_pct="10", enpav_pct="2",
    )
    annota(conn, data_prestazione="2026-07-30", cliente_id=2, descrizione="Visita",
           quantita="1", prezzo_unitario="100.00", aliquota_iva="22.00")
    dal_registro = genera_fattura(conn, 2, studio)

    assert (dal_registro["risultato"].totale_documento
            == a_mano["risultato"].totale_documento)


def test_il_totale_a_schermo_e_quello_che_finira_in_fattura(conn):
    """Se la schermata del registro ignorasse lo sconto, direbbe un numero e la
    fattura ne stamperebbe un altro."""
    conn.execute("UPDATE clienti SET sconto_default_pct='10.00' WHERE id=2")
    conn.commit()
    annota(conn, data_prestazione="2026-07-30", cliente_id=2, descrizione="Visita",
           quantita="1", prezzo_unitario="100.00", aliquota_iva="22.00")

    gruppo = next(g for g in da_fatturare(conn) if g["cliente_id"] == 2)
    esito = genera_fattura(conn, 2, {"enpav_pct": "2"})
    assert gruppo["totale"] == str(esito["risultato"].imponibile)


def test_la_proforma_dal_registro_applica_lo_stesso_sconto(conn):
    conn.execute("UPDATE clienti SET sconto_default_pct='10.00' WHERE id=2")
    conn.commit()
    annota(conn, data_prestazione="2026-07-30", cliente_id=2, descrizione="Visita",
           quantita="1", prezzo_unitario="100.00", aliquota_iva="22.00")
    esito = genera_proforma(conn, 2, {"enpav_pct": "2"})
    assert str(esito["risultato"].imponibile) == "90.00"


def test_la_proforma_non_puo_restare_scollegata_dalle_voci(conn):
    """Se il collegamento delle voci fallisce, non deve restare una proforma orfana.

    Il collegamento gira dentro la stessa transazione dell'emissione: un errore li'
    annulla tutto, proforma compresa.
    """
    import app.registro as reg

    annota(conn, data_prestazione="2026-07-30", cliente_id=2, descrizione="Visita",
           quantita="1", prezzo_unitario="100.00", aliquota_iva="22.00")
    prima = conn.execute("SELECT COUNT(*) FROM proforme").fetchone()[0]

    originale = reg.emetti_proforma

    def esplodi(conn_, **kw):
        def rompi(c, pid):
            raise RuntimeError("collegamento fallito")
        kw["dopo_inserimento"] = rompi
        return originale(conn_, **kw)

    reg.emetti_proforma = esplodi
    try:
        with pytest.raises(RuntimeError):
            genera_proforma(conn, 2, {"enpav_pct": "2"})
    finally:
        reg.emetti_proforma = originale

    assert conn.execute("SELECT COUNT(*) FROM proforme").fetchone()[0] == prima, \
        "la proforma e' rimasta anche se il collegamento e' fallito"
    assert conn.execute(
        "SELECT COUNT(*) FROM prestazioni_eseguite WHERE proforma_id IS NOT NULL"
    ).fetchone()[0] == 0
