"""Test dei preventivi/proforma: emissione e conversione in fattura."""
import pytest

from app.calcolo import RigaInput
from app.db import get_conn, init_db
from app.proforma import converti_in_fattura, emetti_proforma, leggi_proforma


@pytest.fixture()
def conn(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    c = get_conn(db)
    c.execute("INSERT INTO clienti (tipo, nome, cognome, codice_fiscale) "
              "VALUES ('fisica','Mario','Rossi','RSSMRA85T10A562S')")
    c.commit()
    yield c
    c.close()


def _cliente(conn):
    return conn.execute("SELECT * FROM clienti WHERE id=1").fetchone()


def test_emissione_proforma(conn):
    esito = emetti_proforma(
        conn, cliente=_cliente(conn),
        righe=[RigaInput("Visita clinica equino", 1, "80", "22")],
        data_emissione="2026-03-01", validita_giorni=15)
    assert esito["numero_visualizzato"] == "P1/2026"
    r = esito["risultato"]
    assert str(r.totale_documento) == "99.55"  # 80 -> ENPAV 1.60 -> 81.60 -> +22% = 99.55
    p = leggi_proforma(conn, esito["id"])
    assert p["tipo_documento"] == "proforma"
    assert p["stato"] == "bozza"
    assert p["validita_giorni"] == 15
    assert len(p["righe"]) == 1


def test_conversione_in_fattura(conn):
    prev = emetti_proforma(
        conn, cliente=_cliente(conn),
        righe=[RigaInput("Ecografia", 1, "90", "22")],
        data_emissione="2026-03-01")
    studio = {"formato_numerazione": "{n}/{anno}"}
    esito = converti_in_fattura(conn, prev["id"], studio)

    # la fattura riprende esattamente il totale del preventivo
    assert esito["risultato"].totale_documento == prev["risultato"].totale_documento
    f = conn.execute("SELECT * FROM fatture WHERE id=?", (esito["id"],)).fetchone()
    assert f["tipo_documento"] == "fattura"
    assert f["proforma_origine_id"] == prev["id"]
    # il preventivo risulta convertito e collegato
    p = leggi_proforma(conn, prev["id"])
    assert p["stato"] == "convertita"
    assert p["fattura_generata_id"] == esito["id"]

    # non ri-convertibile
    with pytest.raises(ValueError):
        converti_in_fattura(conn, prev["id"], studio)
