"""Test dell'avvio senza finestra del terminale (app/main.py).

Togliendo la console si perdono quattro cose che l'utente dava per scontate: il
messaggio d'errore quando qualcosa non parte, il modo per chiudere il programma,
la prova visiva che sta girando, e un posto dove i log possano finire. Questi
test verificano i sostituti, perche' se saltano il difetto e' silenzioso: l'exe
semplicemente non si apre e non dice niente.
"""
import sys

from fastapi.testclient import TestClient

from app import main as m


def _client():
    return TestClient(m.app)


def test_lo_spec_non_apre_la_finestra_del_terminale():
    from pathlib import Path
    spec = (Path(__file__).resolve().parent.parent / "Gestionale.spec").read_text(encoding="utf-8")
    assert "console=False" in spec


def test_salute_permette_di_riconoscere_un_istanza_gia_avviata():
    """Se rispondesse qualcosa d'altro, un secondo doppio clic aprirebbe una
    seconda copia del gestionale sugli stessi dati."""
    r = _client().get("/salute")
    assert r.status_code == 200
    assert r.text.startswith("gestionale")


def test_spegni_risponde_prima_di_fermare_il_server():
    """La pagina di commiato deve arrivare: se il server morisse subito, l'utente
    vedrebbe un errore del browser invece di una conferma."""
    r = _client().post("/spegni")
    assert r.status_code == 200
    assert "chiuso" in r.text.lower()


def test_ogni_pagina_offre_come_chiudere_il_gestionale():
    """Senza console e' l'unico modo di fermarlo."""
    for percorso in ("/", "/clienti", "/fatture", "/registro"):
        html = _client().get(percorso).text
        assert 'action="/spegni"' in html, f"manca la chiusura in {percorso}"


def test_l_output_viene_dirottato_su_file_quando_manca_la_console(tmp_path, monkeypatch):
    """Nell'exe senza finestra stdout e' None: la prima riga di log di uvicorn
    farebbe saltare l'avvio."""
    monkeypatch.setattr(m, "DATI_DIR", tmp_path)
    vero_out, vero_err = sys.stdout, sys.stderr
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    try:
        percorso = m._dirotta_output()
        assert percorso is not None and percorso.exists()
        print("prova")            # non deve sollevare
        assert sys.stdout is not None
    finally:
        sys.stdout, sys.stderr = vero_out, vero_err


def test_con_la_console_l_output_resta_dov_e():
    assert m._dirotta_output() is None
