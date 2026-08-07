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
from pathlib import Path

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


# --- riconoscere la PROPRIA istanza -----------------------------------------

def test_salute_dice_quale_archivio_sta_servendo():
    """Il difetto che ha bruciato tre giorni: un server di sviluppo rispondeva
    "gestionale" come l'exe, e il doppio clic portava sull'archivio sbagliato."""
    corpo = _client().get("/salute").text
    righe = corpo.splitlines()
    assert len(righe) >= 3, f"/salute deve dire nome, cartella dati e pagine: {corpo!r}"
    assert Path(righe[1]).resolve() == m.DATI_DIR.resolve()
    assert righe[2].isdigit()


def test_la_propria_risposta_viene_riconosciuta():
    """Ciclo chiuso: quello che /salute scrive, _stessa_installazione lo accetta."""
    assert m._stessa_installazione(_client().get("/salute").text) is True


def test_un_istanza_su_un_altro_archivio_non_viene_riusata():
    """E' il cuore della correzione: stesso programma, dati diversi -> non e' la
    nostra, il doppio clic deve avviarne una propria invece di mostrare le
    fatture di un altro archivio."""
    altrove = "gestionale-veterinario\nC:\\\\altro\\\\posto\\\\dati\n1"
    assert m._stessa_installazione(altrove) is False


def test_una_versione_vecchia_senza_cartella_non_viene_riusata():
    """Prudenza: se non dice quale archivio serve, non ci fidiamo."""
    assert m._stessa_installazione("gestionale-veterinario") is False


def test_una_risposta_estranea_non_viene_riusata():
    for corpo in ("", "qualcos'altro", '{"detail":"Not Found"}'):
        assert m._stessa_installazione(corpo) is False


def test_le_pagine_aperte_si_leggono_da_salute():
    assert m._pagine_da_salute("gestionale-veterinario\nC:\\dati\n3") == 3
    assert m._pagine_da_salute("gestionale-veterinario\nC:\\dati") == 0
    assert m._pagine_da_salute("gestionale-veterinario\nC:\\dati\nboh") == 0


# --- quale versione sta girando ---------------------------------------------

def test_salute_dice_la_versione():
    """Gli exe si sostituiscono copiando un file: senza questa riga, due cartelle
    identiche possono contenere programmi diversi e non c'e' modo di saperlo se
    non confrontando l'hash del binario."""
    from app.versione import VERSIONE
    righe = _client().get("/salute").text.splitlines()
    assert righe[3] == VERSIONE


def test_la_versione_sta_in_fondo_a_salute():
    """**Le righe nuove vanno aggiunte in fondo, mai in mezzo.**

    Chi legge ``/salute`` lo fa per posizione, e puo' essere un eseguibile di
    un'altra versione: si sostituisce solo il binario, quindi un exe vecchio
    puo' interrogarne uno nuovo. Una riga infilata in mezzo sposterebbe la
    cartella dati, e il vecchio si attaccherebbe all'archivio sbagliato — che e'
    esattamente il difetto gia' pagato con tre giorni di indagine.

    Le prime tre righe restano quelle di prima: e' questo che il test difende.
    """
    from app.versione import VERSIONE
    righe = _client().get("/salute").text.splitlines()
    assert righe[0].startswith("gestionale")
    assert Path(righe[1]).resolve() == m.DATI_DIR.resolve()
    assert righe[2].isdigit()
    assert righe[-1] == VERSIONE, "la versione deve essere l'ultima riga"


def test_una_risposta_di_una_versione_futura_resta_leggibile():
    """L'altro verso della compatibilita': se un domani ``/salute`` guadagnasse
    altre righe, il codice di oggi deve continuare a leggere le sue."""
    futura = f"gestionale-veterinario\n{m.DATI_DIR}\n2\n2027.01.01\nchissa-che-altro"
    assert m._stessa_installazione(futura) is True
    assert m._pagine_da_salute(futura) == 2


def test_la_versione_ha_il_formato_di_una_data():
    """``AAAA.MM.GG``, come i tag in VERSIONI.md: se qualcuno scrive '2026.8.7'
    o 'v2026.08.07' le versioni non si ordinano piu' guardandole."""
    import re
    from app.versione import VERSIONE
    assert re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", VERSIONE), VERSIONE


def test_la_versione_compare_nel_piede_delle_pagine():
    """Al telefono si chiede "cosa c'e' scritto in fondo", non si calcola un hash."""
    from app.versione import VERSIONE
    testo = _client().get("/").text
    assert f"versione {VERSIONE}" in testo


def test_portare_in_primo_piano_non_esplode_se_non_trova_nulla():
    """Best effort: se la finestra non c'e', deve dire False, non sollevare —
    altrimenti il doppio clic finirebbe in un errore invece di aprire il browser."""
    assert m._porta_in_primo_piano("titolo che non esiste da nessuna parte") is False


def test_spegni_risponde_prima_di_fermare_il_server(monkeypatch):
    """La pagina di commiato deve arrivare: se il server morisse subito, l'utente
    vedrebbe un errore del browser invece di una conferma."""
    monkeypatch.setattr(m, "_server", ServerFinto())
    r = _client().post("/spegni")
    assert r.status_code == 200
    assert "Gestionale chiuso" in r.text
    # l'arresto e' rimandato di un istante, non immediato
    assert m._server.should_exit is False
    time.sleep(1.4)
    assert m._server.should_exit is True


def test_se_non_puo_chiudere_lo_dice(monkeypatch):
    """Avviato dalla CLI di uvicorn non c'e' l'oggetto server e il pulsante non
    puo' fermare nulla. Prima la pagina diceva "chiuso" comunque: e' cosi' che e'
    nato un orfano rimasto in piedi tre giorni, invisibile, con codice vecchio.
    Un'istanza che si crede spenta e invece vive e' peggio di un errore."""
    monkeypatch.setattr(m, "_server", None)
    testo = _client().post("/spegni").text
    assert "Non l'ho potuto chiudere" in testo
    assert "Ctrl+C" in testo


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
