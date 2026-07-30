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


# --- spegnimento automatico quando nessuno lo usa --------------------------

def test_il_battito_risponde_leggero():
    """Le pagine lo chiamano ogni mezzo minuto: deve costare quasi nulla."""
    r = _client().post("/battito")
    assert r.status_code == 204
    assert r.content == b""


def test_qualunque_richiesta_vale_come_segno_di_vita(monkeypatch):
    """Se contasse solo il battito, il gestionale potrebbe spegnersi mentre lo si
    usa da una pagina vecchia rimasta in cache (senza il nostro JavaScript)."""
    monkeypatch.setattr(m, "_ultima_vita", 0.0)
    _client().get("/clienti")
    assert m._ultima_vita > 0.0


def test_il_guardiano_spegne_dopo_il_silenzio(monkeypatch):
    """Browser chiuso: nessun battito, il server si ferma da se'."""
    monkeypatch.setattr(m, "GRAZIA_SECONDI", 0.05)
    monkeypatch.setattr(m, "INTERVALLO_CONTROLLO", 0.01)
    monkeypatch.setattr(m, "_ultima_vita", 0.0)  # silenzio da sempre

    class ServerFinto:
        should_exit = False

    finto = ServerFinto()
    m._guardiano(finto)
    assert finto.should_exit is True


def test_il_guardiano_non_spegne_se_qualcuno_c_e(monkeypatch):
    """Con i battiti che arrivano, non deve chiudersi sotto le mani dell'utente."""
    import threading
    import time

    monkeypatch.setattr(m, "GRAZIA_SECONDI", 0.5)
    monkeypatch.setattr(m, "INTERVALLO_CONTROLLO", 0.01)

    class ServerFinto:
        should_exit = False

    finto = ServerFinto()
    t = threading.Thread(target=m._guardiano, args=(finto,), daemon=True)
    t.start()
    # Batte per mezzo secondo: piu' a lungo della grazia, ma senza mai tacere.
    scadenza = time.monotonic() + 0.5
    while time.monotonic() < scadenza:
        m.segna_vita()
        time.sleep(0.02)
    assert finto.should_exit is False
    finto.should_exit = True  # ferma il thread


def test_ogni_pagina_manda_il_battito():
    for percorso in ("/", "/clienti", "/fatture", "/registro"):
        assert "/battito" in _client().get(percorso).text, f"manca il battito in {percorso}"


def test_la_pagina_di_chiusura_non_batte():
    """Batterebbe verso un server che sta morendo, e mostrerebbe l'avviso
    "si e' chiuso da solo" proprio dove c'e' scritto che l'hai chiuso tu."""
    html = _client().post("/spegni").text
    assert "/battito" not in html


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
