"""Un numero scritto male non deve mai diventare una pagina di errore.

Nati dalla revisione dell'intero programma. Lo stesso difetto viveva in moduli
diversi: i valori arrivano dai form come testo, e finivano in ``q2()`` senza che
nessuno avesse la possibilita' di raccogliere l'errore e rimandarlo nel modulo.

Il caso peggiore non e' quello che si rompe subito. **Le percentuali delle
Impostazioni vengono rilette a ogni emissione di fattura**: un carattere
sbagliato salvato li' non dava alcun segnale al momento, e poi bloccava *tutta*
la fatturazione con un errore che non spiegava niente — settimane dopo, senza
alcun modo di collegarlo al campo toccato allora.
"""
from urllib.parse import unquote_plus

import pytest
from fastapi.testclient import TestClient

from app.db import get_conn
from app.main import app
from app.validazioni import valida_percentuale


def _client():
    return TestClient(app)


@pytest.fixture()
def studio_intatto():
    """Le impostazioni sono una riga sola e condivisa: va rimessa com'era."""
    conn = get_conn()
    prima = dict(conn.execute("SELECT * FROM studio WHERE id=1").fetchone())
    conn.close()
    yield prima
    conn = get_conn()
    with conn:
        conn.execute("UPDATE studio SET enpav_pct=?, iva_default_pct=? WHERE id=1",
                     (prima["enpav_pct"], prima["iva_default_pct"]))
    conn.close()


# --- il controllo ------------------------------------------------------------

def test_valida_percentuale_accetta_le_due_notazioni():
    assert valida_percentuale("2", "ENPAV") == []
    assert valida_percentuale("2.00", "ENPAV") == []
    assert valida_percentuale("2,50", "ENPAV") == []   # come si scrive a mano


def test_valida_percentuale_rifiuta_il_resto():
    assert valida_percentuale("", "ENPAV")
    assert valida_percentuale("due", "ENPAV")
    assert valida_percentuale("-1", "ENPAV")
    assert valida_percentuale("2222", "ENPAV")


def test_il_messaggio_dice_quale_campo_e():
    """Con sei percentuali in giro, "valore non valido" non basta a trovarla."""
    (errore,) = valida_percentuale("due", "Contributo ENPAV")
    assert "Contributo ENPAV" in errore


# --- Impostazioni: il difetto più pericoloso --------------------------------

def test_un_enpav_rovinato_non_si_salva(studio_intatto):
    """**Il caso peggiore della revisione.** Se questo valore entra nel database,
    ogni emissione di fattura si rompe, e nessuno collega la cosa a un campo
    toccato settimane prima."""
    dati = {c: studio_intatto.get(c) or "" for c in
            ("denominazione", "nome", "cognome", "codice_fiscale", "partita_iva",
             "via", "cap", "citta", "prov", "email", "telefono", "iban", "regime",
             "n_iscrizione_albo", "formato_numerazione",
             "testo_dicitura_opposizione_ts", "logo_path")}
    dati["enpav_pct"] = "due per cento"
    dati["iva_default_pct"] = "22"

    r = _client().post("/impostazioni", data=dati, follow_redirects=False)
    assert r.status_code == 303
    # L'indirizzo e' codificato: va letto come lo leggera' la pagina.
    messaggio = unquote_plus(r.headers["location"])
    assert "NON sono state salvate" in messaggio
    assert "ENPAV" in messaggio

    conn = get_conn()
    try:
        assert conn.execute("SELECT enpav_pct FROM studio WHERE id=1").fetchone()[0] \
            == studio_intatto["enpav_pct"], "il valore rovinato e' entrato nel database"
    finally:
        conn.close()


def test_un_enpav_gia_rovinato_non_da_una_pagina_di_errore(studio_intatto):
    """Se un valore sbagliato fosse gia' dentro — salvato da una versione
    precedente — l'emissione deve spiegarlo e mandare dove si corregge, non
    morire."""
    conn = get_conn()
    with conn:
        conn.execute("UPDATE studio SET enpav_pct='xx' WHERE id=1")
    conn.close()

    r = _client().post("/fatture", data={
        "cliente_id": "1", "data_emissione": "2026-08-07",
        "r_descrizione": "Visita", "r_quantita": "1", "r_prezzo": "50,00",
        "r_sconto": "0", "r_aliquota": "22", "r_tipo_spesa": "SV",
        "r_prestazione_id": "", "r_paziente_id": "", "r_data": "",
    }, follow_redirects=False)

    assert r.status_code == 400
    assert "ENPAV" in r.text
    assert "Impostazioni" in r.text, "deve dire dove si corregge"


# --- le percentuali fuori dalle righe ---------------------------------------

def test_uno_sconto_cliente_scritto_male_torna_nel_modulo():
    r = _client().post("/fatture", data={
        "cliente_id": "1", "data_emissione": "2026-08-07",
        "sconto_cliente_pct": "dieci",
        "r_descrizione": "Visita", "r_quantita": "1", "r_prezzo": "50,00",
        "r_sconto": "0", "r_aliquota": "22", "r_tipo_spesa": "SV",
        "r_prestazione_id": "", "r_paziente_id": "", "r_data": "",
    }, follow_redirects=False)
    assert r.status_code == 400
    assert "Sconto cliente" in r.text


# --- Listino -----------------------------------------------------------------

def test_un_prezzo_di_listino_scritto_male_torna_nel_modulo():
    """Prima ``q2()`` girava dentro ``_estrai``, cioe' *prima* che qualcuno
    potesse raccogliere l'errore: usciva una pagina di errore di sistema."""
    r = _client().post("/listino", data={
        "codice": "ZZZ", "descrizione": "Prova", "prezzo_unitario": "molto",
        "aliquota_iva": "22", "tipo_spesa_ts": "SV", "unita_misura": "nr",
        "attiva": "1"}, follow_redirects=False)
    assert r.status_code == 400
    assert "non è un numero" in r.text or "non &#232; un numero" in r.text


def test_il_listino_accetta_la_virgola():
    conn = get_conn()
    try:
        r = _client().post("/listino", data={
            "codice": "ZZV", "descrizione": "Prova virgola",
            "prezzo_unitario": "45,50", "aliquota_iva": "22",
            "tipo_spesa_ts": "SV", "unita_misura": "nr", "attiva": "1"},
            follow_redirects=False)
        assert r.status_code == 303
        salvato = conn.execute(
            "SELECT prezzo_unitario FROM prestazioni WHERE codice='ZZV'").fetchone()[0]
        assert salvato == "45.50", f"salvato {salvato!r}: la virgola non e' arrivata"
    finally:
        with conn:
            conn.execute("DELETE FROM prestazioni WHERE codice IN ('ZZV','ZZZ')")
        conn.close()


# --- Registro ----------------------------------------------------------------

def test_il_registro_rifiuta_un_aliquota_impossibile():
    """Quello che si annota qui diventa poi riga di fattura: un'aliquota
    impossibile accettata adesso rientrerebbe dalla porta di servizio."""
    r = _client().post("/registro", data={
        "cliente_id": "1", "data_prestazione": "2026-08-07",
        "descrizione": "Visita", "quantita": "1", "prezzo_unitario": "50,00",
        "sconto_riga_pct": "0", "aliquota_iva": "2222", "tipo_spesa_ts": "SV",
    }, follow_redirects=False)
    assert r.status_code == 400
    assert "2222" in r.text


def test_il_registro_accetta_la_virgola_e_la_salva_normalizzata():
    conn = get_conn()
    try:
        r = _client().post("/registro", data={
            "cliente_id": "1", "data_prestazione": "2026-08-07",
            "descrizione": "Prova virgola registro", "quantita": "2",
            "prezzo_unitario": "45,50", "sconto_riga_pct": "0",
            "aliquota_iva": "22", "tipo_spesa_ts": "SV",
        }, follow_redirects=False)
        assert r.status_code == 303
        salvato = conn.execute(
            "SELECT prezzo_unitario FROM prestazioni_eseguite "
            "WHERE descrizione='Prova virgola registro'").fetchone()[0]
        assert salvato == "45.50", f"salvato {salvato!r}"
    finally:
        with conn:
            conn.execute("DELETE FROM prestazioni_eseguite "
                         "WHERE descrizione='Prova virgola registro'")
        conn.close()


def test_i_campi_degli_importi_del_registro_accettano_la_virgola():
    html = _client().get("/registro/nuovo").text
    for campo in ("quantita", "prezzo_unitario", "sconto_riga_pct", "aliquota_iva"):
        riga = [l for l in html.splitlines() if f'name="{campo}"' in l]
        assert riga, f"campo {campo} non trovato"
        assert 'type="number"' not in riga[0], f"{campo} rifiuterebbe la virgola"
