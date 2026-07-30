"""Test dell'avvio senza finestra del terminale (app/main.py).

Togliendo la console si perdono quattro cose che l'utente dava per scontate: il
messaggio d'errore quando qualcosa non parte, il modo per chiudere il programma,
la prova visiva che sta girando, e un posto dove i log possano finire. Questi
test verificano i sostituti, perche' se saltano il difetto e' silenzioso: l'exe
semplicemente non si apre e non dice niente.
"""
import socket
import sys
import time

import pytest
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


# --- vive quanto vive la finestra del browser -------------------------------

class ServerFinto:
    """Il minimo che il guardiano guarda."""

    def __init__(self):
        self.should_exit = False


@pytest.fixture()
def server_vero():
    """Un uvicorn vero su una porta libera, in un thread.

    Il flusso di presenza si prova solo cosi': con ``TestClient`` la chiusura
    della risposta aspetta che il generatore finisca, e il generatore aspetta il
    segnale di scollegamento che arriverebbe solo dopo — si bloccano a vicenda.
    Con un socket vero il percorso e' quello del browser.
    """
    import threading

    import uvicorn

    porta = m._porta_libera((8531, 8532, 8533))
    server = uvicorn.Server(uvicorn.Config(
        m.app, host="127.0.0.1", port=porta, log_level="error",
        timeout_graceful_shutdown=3))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started, "il server di prova non e' partito"
    yield porta
    server.should_exit = True
    t.join(timeout=10)


def _apri_presenza(porta: int) -> socket.socket:
    """Apre /presenza a mano e legge la prima riga: come farebbe il browser."""
    s = socket.create_connection(("127.0.0.1", porta), timeout=5)
    s.sendall(b"GET /presenza HTTP/1.1\r\nHost: 127.0.0.1\r\nAccept: text/event-stream\r\n\r\n")
    intestazioni = b""
    while b"\r\n\r\n" not in intestazioni:
        intestazioni += s.recv(1024)
    assert b"200 OK" in intestazioni, intestazioni[:120]
    assert b"text/event-stream" in intestazioni
    return s


def _attendi(condizione, secondi=5.0) -> bool:
    scadenza = time.monotonic() + secondi
    while time.monotonic() < scadenza:
        if condizione():
            return True
        time.sleep(0.05)
    return False


def test_il_flusso_di_presenza_conta_la_pagina(server_vero):
    """Mentre il flusso e' aperto la pagina risulta presente; chiuso, no."""
    prima = m.pagine_aperte()
    s = _apri_presenza(server_vero)
    try:
        assert _attendi(lambda: m.pagine_aperte() == prima + 1), \
            "la pagina collegata non viene contata"
    finally:
        s.close()
    assert _attendi(lambda: m.pagine_aperte() == prima), \
        "chiusa la pagina, il contatore non e' tornato giu': non si spegnerebbe mai piu'"


def test_due_pagine_aperte_contano_due(server_vero):
    """Due schede: la prima che si chiude non deve spegnere il gestionale."""
    prima = m.pagine_aperte()
    a = _apri_presenza(server_vero)
    b = _apri_presenza(server_vero)
    try:
        assert _attendi(lambda: m.pagine_aperte() == prima + 2)
        a.close()
        assert _attendi(lambda: m.pagine_aperte() == prima + 1)
    finally:
        a.close()
        b.close()
    assert _attendi(lambda: m.pagine_aperte() == prima)


def test_spegnersi_non_resta_appeso_al_flusso(server_vero):
    """La regressione piu' insidiosa: con una pagina aperta, "Chiudi il
    gestionale" deve chiudere davvero. Il flusso e' fatto per non finire mai,
    quindi deve mollare da se' quando il server sta chiudendo."""
    import threading

    import uvicorn

    porta = m._porta_libera((8541, 8542, 8543))
    server = uvicorn.Server(uvicorn.Config(
        m.app, host="127.0.0.1", port=porta, log_level="error",
        timeout_graceful_shutdown=3))
    vecchio, m._server = m._server, server
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    assert _attendi(lambda: server.started)
    s = _apri_presenza(porta)
    try:
        inizio = time.monotonic()
        server.should_exit = True
        t.join(timeout=15)
        durata = time.monotonic() - inizio
        assert not t.is_alive(), "il server e' rimasto appeso al flusso di presenza"
        assert durata < 10, f"spegnimento troppo lento: {durata:.1f}s"
    finally:
        s.close()
        m._server = vecchio


def test_il_guardiano_non_spegne_con_una_pagina_aperta(monkeypatch):
    """**Il requisito.** Il gestionale si tiene aperto tutto il giorno: con una
    pagina collegata non deve spegnersi, per quanto tempo passi senza usarlo."""
    import threading
    import time

    monkeypatch.setattr(m, "GRAZIA_SECONDI", 0.05)
    monkeypatch.setattr(m, "INTERVALLO_CONTROLLO", 0.01)
    monkeypatch.setattr(m, "_ultima_vita", 0.0)   # nessuna richiesta da sempre
    monkeypatch.setattr(m, "_pagine_aperte", 1)   # ...ma una pagina e' aperta

    finto = ServerFinto()
    t = threading.Thread(target=m._guardiano, args=(finto,), daemon=True)
    t.start()
    time.sleep(0.3)  # sei volte la grazia
    assert finto.should_exit is False, "si e' spento con una pagina aperta"
    finto.should_exit = True


def test_il_guardiano_spegne_quando_non_resta_nessuna_pagina(monkeypatch):
    """Finestra chiusa: nessun flusso, nessuna richiesta, si ferma da se'."""
    monkeypatch.setattr(m, "GRAZIA_SECONDI", 0.05)
    monkeypatch.setattr(m, "INTERVALLO_CONTROLLO", 0.01)
    monkeypatch.setattr(m, "_ultima_vita", 0.0)
    monkeypatch.setattr(m, "_pagine_aperte", 0)

    finto = ServerFinto()
    m._guardiano(finto)
    assert finto.should_exit is True


def test_una_richiesta_recente_basta_a_tenerlo_su(monkeypatch):
    """Secondo segnale: una pagina vecchia in cache, senza il flusso, deve
    comunque impedire che si chiuda sotto le mani di chi la sta usando."""
    import threading
    import time

    monkeypatch.setattr(m, "GRAZIA_SECONDI", 0.3)
    monkeypatch.setattr(m, "INTERVALLO_CONTROLLO", 0.01)
    monkeypatch.setattr(m, "_pagine_aperte", 0)

    finto = ServerFinto()
    t = threading.Thread(target=m._guardiano, args=(finto,), daemon=True)
    t.start()
    scadenza = time.monotonic() + 0.5
    while time.monotonic() < scadenza:
        m.segna_vita()
        time.sleep(0.02)
    assert finto.should_exit is False
    finto.should_exit = True


def test_qualunque_richiesta_vale_come_segno_di_vita(monkeypatch):
    monkeypatch.setattr(m, "_ultima_vita", 0.0)
    _client().get("/clienti")
    assert m._ultima_vita > 0.0


def test_ogni_pagina_tiene_il_flusso_di_presenza():
    for percorso in ("/", "/clienti", "/fatture", "/registro"):
        assert "/presenza" in _client().get(percorso).text, \
            f"manca la presenza in {percorso}"


def test_la_pagina_di_chiusura_non_apre_il_flusso():
    """Aprirebbe un flusso verso un server che sta morendo: terrebbe su il
    contatore e mostrerebbe "si e' chiuso" dove c'e' scritto che l'hai chiuso tu."""
    html = _client().post("/spegni").text
    assert "/presenza" not in html


def test_lo_spegnimento_ha_un_limite_di_attesa():
    """Senza questo il programma non si chiude: il default di uvicorn e' aspettare
    *senza limite* che le richieste finiscano, e /presenza e' fatto per non finire
    mai. "Chiudi il gestionale" resterebbe appeso per sempre."""
    import inspect
    sorgente = inspect.getsource(m.main)
    assert "timeout_graceful_shutdown" in sorgente


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
