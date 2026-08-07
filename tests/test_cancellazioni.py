"""Cancellare un'anagrafica ancora in uso: dire cosa la blocca, non un'eccezione.

Caso vero: eliminando un cliente usciva
``sqlite3.IntegrityError: FOREIGN KEY constraint failed`` come pagina di errore
di sistema. Il rifiuto era giusto — le fatture emesse restano, per legge, e
devono restare intestate a qualcuno — ma sembrava un guasto del programma, e non
diceva **cosa** impedisse l'operazione.
"""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.db import get_conn, usi_che_impediscono_cancellazione
from app.main import app


def _client():
    return TestClient(app)


def _conn():
    return get_conn()


@pytest.fixture()
def archivio_con_una_fattura():
    """Cliente + voce di listino + una fattura che li usa, creati e poi tolti.

    Non ci si appoggia a quel che c'e' gia' nell'archivio di sviluppo: un test
    che si salta perche' non trova i dati giusti non protegge niente, e proprio
    questo difetto era passato inosservato.
    """
    conn = _conn()
    with conn:
        cid = conn.execute(
            "INSERT INTO clienti (tipo, nome, cognome, codice_fiscale) "
            "VALUES ('fisica','Prova','Legami','')").lastrowid
        pid = conn.execute(
            "INSERT INTO prestazioni (codice, descrizione, prezzo_unitario, "
            "aliquota_iva, tipo_spesa_ts, unita_misura, attiva) "
            "VALUES ('PRV','Prestazione di prova','10.00','22','SV','nr',1)").lastrowid
        cav = conn.execute(
            "INSERT INTO pazienti (cliente_id, nome, specie) "
            "VALUES (?,'Cavallo di prova','Equino')", (cid,)).lastrowid
        fid = conn.execute(
            "INSERT INTO fatture (anno, numero_progressivo, numero_visualizzato, "
            "data_emissione, cliente_id, cli_denominazione) "
            "VALUES (9999, 1, '1/9999', '9999-01-01', ?, 'Prova Legami')",
            (cid,)).lastrowid
        conn.execute(
            "INSERT INTO righe_fattura (fattura_id, prestazione_id, paziente_id, "
            "descrizione, quantita, prezzo_unitario, aliquota_iva, imponibile_riga) "
            "VALUES (?,?,?,'Prestazione di prova','1','10.00','22','10.00')",
            (fid, pid, cav))
    try:
        yield {"cliente": cid, "prestazione": pid, "cavallo": cav, "fattura": fid}
    finally:
        with conn:
            conn.execute("DELETE FROM righe_fattura WHERE fattura_id=?", (fid,))
            conn.execute("DELETE FROM fatture WHERE id=?", (fid,))
            conn.execute("DELETE FROM pazienti WHERE id=?", (cav,))
            conn.execute("DELETE FROM prestazioni WHERE id=?", (pid,))
            conn.execute("DELETE FROM clienti WHERE id=?", (cid,))
        conn.close()


# --- il controllo che guarda i legami ---------------------------------------

def test_dice_quante_cose_sono_attaccate(archivio_con_una_fattura):
    """Il numero serve: "ha delle fatture" non dice se cercarne una o venti."""
    conn = _conn()
    try:
        usi = usi_che_impediscono_cancellazione(
            conn, "clienti", archivio_con_una_fattura["cliente"])
        assert usi == ["1 fatture"], usi
        assert usi_che_impediscono_cancellazione(
            conn, "prestazioni", archivio_con_una_fattura["prestazione"]) \
            == ["1 righe di fattura"]
        assert usi_che_impediscono_cancellazione(
            conn, "pazienti", archivio_con_una_fattura["cavallo"]) \
            == ["1 righe di fattura"]
    finally:
        conn.close()


def test_chi_non_e_attaccato_a_niente_si_puo_togliere():
    conn = _conn()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO clienti (tipo, nome, cognome, codice_fiscale) "
                "VALUES ('fisica','Prova','Cancellabile','')")
            nuovo = cur.lastrowid
        assert usi_che_impediscono_cancellazione(conn, "clienti", nuovo) == []
        with conn:
            conn.execute("DELETE FROM clienti WHERE id=?", (nuovo,))
    finally:
        conn.close()


def test_i_cavalli_non_bloccano_il_proprietario():
    """La loro chiave e' ``ON DELETE CASCADE``: se ne vanno insieme a lui, quindi
    elencarli fra i motivi del rifiuto sarebbe una bugia."""
    from app.db import LEGAMI
    assert not any(t == "pazienti" for t, _c, _e in LEGAMI["clienti"])


# --- le rotte: un messaggio, non un errore di sistema ------------------------

def test_eliminare_un_cliente_con_fatture_spiega_perche_no(archivio_con_una_fattura):
    cid = archivio_con_una_fattura["cliente"]
    r = _client().post(f"/clienti/{cid}/elimina", follow_redirects=False)

    assert r.status_code == 303, "doveva rimandare all'elenco, non esplodere"
    assert "fatture" in r.headers["location"]

    conn = _conn()
    try:
        assert conn.execute("SELECT COUNT(*) FROM clienti WHERE id=?",
                            (cid,)).fetchone()[0] == 1, \
            "il cliente non doveva essere toccato"
    finally:
        conn.close()


def test_eliminare_un_cavallo_gia_fatturato_spiega_perche_no(archivio_con_una_fattura):
    """Il nome del cavallo e' nello snapshot immutabile della riga: il legame non
    si puo' spezzare."""
    cav = archivio_con_una_fattura["cavallo"]
    r = _client().post(f"/pazienti/{cav}/elimina", follow_redirects=False)
    assert r.status_code == 303
    assert "righe" in r.headers["location"]

    conn = _conn()
    try:
        assert conn.execute("SELECT COUNT(*) FROM pazienti WHERE id=?",
                            (cav,)).fetchone()[0] == 1
    finally:
        conn.close()


def test_eliminare_una_voce_di_listino_in_uso_suggerisce_di_disattivarla(
        archivio_con_una_fattura):
    """Restare bloccati senza sapere che fare e' peggio del divieto: la strada
    giusta esiste gia' ed e' la spunta «Attiva»."""
    pid = archivio_con_una_fattura["prestazione"]
    r = _client().post(f"/listino/{pid}/elimina", follow_redirects=False)
    assert r.status_code == 303
    assert "Attiva" in r.headers["location"]


# --- la rete di sicurezza ----------------------------------------------------

def test_un_vincolo_non_controllato_non_diventa_una_pagina_di_errore():
    """Per il legame che qualcuno aggiungera' domani senza ricordarsi di
    controllarlo dove viene usato."""
    from app import main as m

    @m.app.get("/_prova_vincolo")
    def _prova():
        raise sqlite3.IntegrityError("FOREIGN KEY constraint failed")

    try:
        r = TestClient(m.app, raise_server_exceptions=False).get("/_prova_vincolo")
        assert r.status_code == 409, "doveva diventare una pagina spiegata"
        assert "Non si può fare" in r.text
        assert "dati non sono stati toccati" in r.text
    finally:
        m.app.router.routes = [
            rot for rot in m.app.router.routes
            if getattr(rot, "path", None) != "/_prova_vincolo"]
