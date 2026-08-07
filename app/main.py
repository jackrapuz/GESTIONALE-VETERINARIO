"""Avvio dell'applicazione: FastAPI locale + apertura automatica del browser.

Il gestionale e' un'app desktop offline: il server ascolta solo su 127.0.0.1 e
non fa alcuna chiamata di rete in uscita. Eseguibile sia con ``python -m app.main``
sia come exe PyInstaller.
"""
from __future__ import annotations

import asyncio
import socket
import sys
import threading
import time
import webbrowser
from datetime import date
from decimal import Decimal
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.db import DATI_DIR, get_conn, init_db
from app.templating import templates
from app.versione import VERSIONE

BASE_DIR = Path(__file__).resolve().parent

# --- Vive quanto vive la finestra del browser -------------------------------
# Senza finestra del terminale, chiudere il browser lasciava il server vivo e
# invisibile: nessun segno che fosse acceso, l'unico modo di fermarlo era il
# Gestione attivita' di Windows, e intanto teneva bloccato Gestionale.exe.
#
# Il primo tentativo era un "battito" a timer dalla pagina. Sbagliato: il
# gestionale si tiene aperto tutto il giorno mentre si lavora ad altro, e la vita
# del programma finiva per dipendere da un timer JavaScript in una scheda in
# secondo piano — che Chrome rallenta, e in certi casi (scheda scartata per
# memoria, sospensione del computer) ferma del tutto. Il programma si spegneva
# con la pagina ancora aperta.
#
# Ora vale una **connessione aperta**: ogni pagina tiene un flusso SSE verso
# /presenza e il server conta i flussi. Finche' ce n'e' almeno uno il gestionale
# vive, senza limiti di tempo e senza chiedere niente al JavaScript. Quando la
# finestra si chiude, il sistema operativo chiude la connessione e il server se
# ne accorge da se'.
# **Chiudere la finestra deve spegnere il programma subito**, come ci si aspetta
# da una pagina qualsiasi. La grazia era di 30 secondi, e serviva a coprire il
# buco fra una pagina e l'altra: mentre si passa da /clienti a /fatture il
# vecchio flusso e' gia' chiuso e il nuovo non e' ancora partito, e un guardiano
# impaziente spegnerebbe il gestionale in mezzo a una navigazione.
#
# Trenta secondi erano pero' una misura grossolana per un problema piccolo. Il
# buco vero dura quanto ci mette il browser a chiedere la pagina nuova, cioe'
# niente; quello che dura davvero e' la *generazione* di una pagina lenta (un
# PDF, uno zip di export), e quella si riconosce meglio contando le richieste in
# corso che allungando un timer. Con il contatore, la grazia puo' scendere a un
# secondo e mezzo senza rischiare nulla: chi sta ancora servendo una richiesta
# non si spegne comunque, per quanto ci metta.
GRAZIA_SECONDI = 1.5         # zero pagine tollerato prima di spegnersi
INTERVALLO_CONTROLLO = 0.3   # ogni quanto il guardiano ricontrolla
INTERVALLO_KEEPALIVE = 15.0  # ogni quanto il flusso manda un segno di vita

# Pagine attualmente collegate. Il contatore viene toccato dal loop asincrono
# (apertura/chiusura dei flussi) e letto dal thread del guardiano: il lock evita
# di ragionare su cosa sia atomico e cosa no.
_pagine_aperte = 0
_lucchetto = threading.Lock()

# Richieste attualmente in lavorazione. Senza questo, una grazia corta uccide il
# gestionale *mentre* sta generando una pagina lenta: la vita veniva segnata
# all'inizio della richiesta, quindi un PDF da tre secondi con grazia di uno e
# mezzo si spegneva da solo a meta' strada.
_richieste_in_corso = 0

# Ultima richiesta ricevuta, orologio monotono (immune ai cambi di ora). E' il
# secondo segnale: copre la pagina vecchia rimasta in cache, senza il flusso.
_ultima_vita: float = time.monotonic()


def segna_vita() -> None:
    """Registra che qualcuno sta usando il programma proprio adesso."""
    global _ultima_vita
    _ultima_vita = time.monotonic()


def _entra_richiesta() -> None:
    global _richieste_in_corso
    with _lucchetto:
        _richieste_in_corso += 1


def _esce_richiesta() -> None:
    global _richieste_in_corso
    with _lucchetto:
        _richieste_in_corso = max(0, _richieste_in_corso - 1)


def richieste_in_corso() -> int:
    """Quante richieste il gestionale sta servendo in questo momento."""
    with _lucchetto:
        return _richieste_in_corso


def _entra_pagina() -> int:
    global _pagine_aperte
    with _lucchetto:
        _pagine_aperte += 1
        return _pagine_aperte


def _esce_pagina() -> int:
    global _pagine_aperte
    with _lucchetto:
        _pagine_aperte = max(0, _pagine_aperte - 1)
        return _pagine_aperte


def pagine_aperte() -> int:
    """Quante pagine del gestionale sono aperte in questo momento."""
    with _lucchetto:
        return _pagine_aperte


def _guardiano(server: uvicorn.Server) -> None:
    """Spegne il server quando non c'e' piu' nessuna pagina aperta.

    Servono **entrambe** le condizioni: nessun flusso collegato e nessuna
    richiesta recente. Il tempo di grazia copre il buco di un istante mentre si
    passa da una pagina all'altra, quando il vecchio flusso e' gia' chiuso e il
    nuovo non e' ancora partito.

    Gira come thread demone: se il server muore per altre vie, non trattiene il
    processo in vita.
    """
    while not server.should_exit:
        time.sleep(INTERVALLO_CONTROLLO)
        if pagine_aperte() > 0:
            continue
        # Nessuna pagina, ma una richiesta ancora in lavorazione: e' il caso di
        # chi ha appena premuto "Emetti fattura" e sta aspettando il PDF. La
        # pagina vecchia se n'e' andata, quella nuova non c'e' ancora, e
        # spegnersi adesso vorrebbe dire perdere il lavoro a meta'.
        if richieste_in_corso() > 0:
            continue
        if time.monotonic() - _ultima_vita > GRAZIA_SECONDI:
            print("Nessuna pagina aperta: il gestionale si spegne.")
            server.should_exit = True
            return


def _statistiche_dashboard() -> dict:
    """Numeri di sintesi per la dashboard iniziale (anno corrente)."""
    anno = date.today().year
    conn = get_conn()
    try:
        def _scalare(sql, args=()):
            return conn.execute(sql, args).fetchone()[0]

        def _somma(sql, args=()):
            tot = Decimal("0")
            for r in conn.execute(sql, args).fetchall():
                tot += Decimal(r[0] or "0")
            return tot

        n_clienti = _scalare("SELECT COUNT(*) FROM clienti")
        n_pazienti = _scalare("SELECT COUNT(*) FROM pazienti")
        n_fatture = _scalare(
            "SELECT COUNT(*) FROM fatture WHERE tipo_documento='fattura' "
            "AND stato!='annullata' AND anno=?", (anno,))
        fatturato = _somma(
            "SELECT totale_documento FROM fatture WHERE tipo_documento='fattura' "
            "AND stato!='annullata' AND anno=?", (anno,))
        da_incassare = _somma(
            "SELECT totale_documento FROM fatture WHERE tipo_documento='fattura' "
            "AND stato='emessa' AND anno=?", (anno,))
        ultime = [dict(r) for r in conn.execute(
            "SELECT * FROM fatture ORDER BY anno DESC, numero_progressivo DESC LIMIT 6"
        ).fetchall()]
        studio_nome = conn.execute("SELECT denominazione FROM studio WHERE id=1").fetchone()[0]
    finally:
        conn.close()
    return {
        "anno": anno, "n_clienti": n_clienti, "n_pazienti": n_pazienti,
        "n_fatture": n_fatture, "fatturato": str(fatturato),
        "da_incassare": str(da_incassare), "ultime": ultime,
        "studio_nome": (studio_nome or "").strip() or "Studio Veterinario",
    }


def create_app() -> FastAPI:
    """Costruisce l'app FastAPI, monta gli static e registra i router."""
    # Crea DB, cartella dati e applica migrazioni prima di servire richieste.
    DATI_DIR.mkdir(parents=True, exist_ok=True)
    init_db()

    app = FastAPI(title="Gestionale Fatturazione", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    @app.middleware("http")
    async def tieni_in_vita(request: Request, call_next):
        """Qualunque richiesta vale come segno di vita.

        E' il secondo segnale, accanto al flusso di presenza: cosi' il programma
        non si spegne mentre lo si sta usando anche se il flusso non ci fosse
        (JavaScript disattivato, pagina vecchia rimasta in cache).

        La vita si segna **due volte, prima e dopo**, e non e' una ripetizione
        inutile: con la grazia scesa a un secondo e mezzo, segnarla solo
        all'inizio farebbe scadere il tempo *durante* una richiesta lunga. Il
        contatore in mezzo copre proprio quel tratto, e il ``finally`` garantisce
        che scenda anche se la richiesta finisce male — altrimenti un solo errore
        basterebbe a rendere il gestionale inspegnibile.
        """
        segna_vita()
        _entra_richiesta()
        try:
            return await call_next(request)
        finally:
            _esce_richiesta()
            segna_vita()

    # Router delle sezioni (registrati man mano che vengono implementati).
    from app.routers import (
        backup, clienti, export, fatture, impostazioni, pazienti, prestazioni,
        preventivi, registro,
    )

    app.include_router(impostazioni.router)
    app.include_router(clienti.router)
    app.include_router(pazienti.router)
    app.include_router(prestazioni.router)
    app.include_router(registro.router)
    app.include_router(fatture.router)
    app.include_router(preventivi.router)
    app.include_router(export.router)
    app.include_router(backup.router)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        ctx = {"titolo": "Home"}
        ctx.update(_statistiche_dashboard())
        return templates.TemplateResponse(request, "home.html", ctx)

    @app.get("/salute", response_class=PlainTextResponse)
    def salute():
        """Carta d'identita' dell'istanza, per chi prova ad avviarne una seconda.

        Quattro righe: il nome del programma, **quale cartella dati sta servendo**,
        quante pagine ha aperte e **quale versione e'**.

        La cartella e' la parte importante. Prima c'era solo il nome, e un secondo
        avvio si accontentava di quello: con un server di sviluppo acceso sulla
        radice del progetto e l'exe sui propri dati, il doppio clic ti portava
        sull'archivio sbagliato senza dire niente. Per un gestionale di fatture
        e' il difetto peggiore possibile.

        **Le righe nuove si aggiungono in fondo, mai in mezzo.** Chi legge questa
        risposta lo fa per posizione (``_stessa_installazione``,
        ``_pagine_da_salute``), e chi legge puo' essere un eseguibile *di un'altra
        versione*: si sostituisce solo il binario, quindi capita che un exe vecchio
        interroghi un exe nuovo o viceversa. In fondo, la riga in piu' viene
        semplicemente ignorata da chi non la conosce; in mezzo, sposterebbe le
        altre e il vecchio leggerebbe la cartella dati sbagliata.
        """
        return f"gestionale-veterinario\n{DATI_DIR}\n{pagine_aperte()}\n{VERSIONE}"

    @app.get("/presenza")
    async def presenza(request: Request):
        """Flusso che resta aperto quanto la pagina: e' il segno che c'e' qualcuno.

        Non serve che il browser faccia nulla: basta che la connessione esista.
        Quando la finestra si chiude e' il sistema operativo a chiuderla, quindi
        funziona anche se la scheda era in secondo piano da ore.

        Il ciclo si interrompe per due motivi, e servono entrambi:

        - ``request.is_disconnected()``: la pagina se n'e' andata. Senza questo
          controllo il flusso continuerebbe a girare a vuoto e il contatore
          resterebbe alto, cioe' il gestionale non si spegnerebbe mai piu'.
        - ``should_exit``: il server sta chiudendo. Un flusso fatto per non
          finire mai terrebbe in ostaggio lo spegnimento (vedi
          ``timeout_graceful_shutdown`` in :func:`main`).

        Il ``finally`` decrementa in ogni caso, anche se il flusso muore male.
        """
        async def flusso():
            _entra_pagina()
            try:
                # Primo byte subito: il browser considera la connessione
                # stabilita solo quando arriva qualcosa.
                yield b": collegato\n\n"
                while True:
                    atteso = 0.0
                    while atteso < INTERVALLO_KEEPALIVE:
                        if _server is not None and _server.should_exit:
                            return
                        if await request.is_disconnected():
                            return
                        await asyncio.sleep(0.25)
                        atteso += 0.25
                    yield b": vivo\n\n"
            finally:
                _esce_pagina()

        return StreamingResponse(
            flusso(), media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @app.post("/spegni", response_class=HTMLResponse)
    def spegni(request: Request):
        """Ferma il gestionale.

        L'arresto e' rimandato di un istante, altrimenti il server morirebbe prima
        di aver consegnato questa pagina e l'utente resterebbe con un errore del
        browser.

        ``senza_presenza`` toglie il flusso da *questa* pagina: aprirne uno verso
        un server che sta morendo terrebbe in vita il contatore e mostrerebbe
        l'avviso "si e' chiuso" proprio dove c'e' scritto che l'hai chiuso tu.
        """
        if _server is not None:
            threading.Timer(1.0, lambda: setattr(_server, "should_exit", True)).start()
        return templates.TemplateResponse(
            request, "spento.html",
            {"titolo": "Chiuso", "senza_presenza": True,
             # Avviato dalla CLI di uvicorn (sviluppo): non abbiamo l'oggetto
             # server, quindi non possiamo fermarlo. Prima la pagina diceva
             # "chiuso" comunque, e il server restava vivo: e' cosi' che e' nato
             # un orfano rimasto in piedi per tre giorni sulla porta 8420,
             # invisibile e con codice vecchio. Meglio dire la verita'.
             "davvero_chiuso": _server is not None})

    return app


app = create_app()

# Riferimento al server in esecuzione: serve a /spegni per fermarlo.
_server: uvicorn.Server | None = None


def _porta_libera(preferite: tuple[int, ...] = (8420, 8421, 8422)) -> int:
    """Restituisce una porta libera su localhost (prova prima quelle preferite)."""
    for porta in preferite:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", porta)) != 0:
                return porta
    # Nessuna preferita libera: lascia scegliere al sistema.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _stessa_installazione(corpo: str) -> bool:
    """Vero se la risposta di ``/salute`` viene da un'istanza sui **nostri** dati.

    Non basta che risponda "gestionale": un server di sviluppo avviato sulla
    radice del progetto risponde uguale ma serve un altro database. Deve
    combaciare la cartella dati (confronto senza distinzione di maiuscole, come
    fa Windows con i percorsi).
    """
    righe = corpo.splitlines()
    if not righe or not righe[0].startswith("gestionale"):
        return False
    if len(righe) < 2:
        return False  # versione vecchia, che non diceva quale archivio serviva
    try:
        loro = Path(righe[1].strip()).resolve()
    except OSError:
        return False
    return str(loro).casefold() == str(DATI_DIR.resolve()).casefold()


def _pagine_da_salute(corpo: str) -> int:
    """Quante pagine ha aperte l'istanza che ha risposto (0 se non lo dice)."""
    righe = corpo.splitlines()
    if len(righe) < 3:
        return 0
    try:
        return int(righe[2].strip())
    except ValueError:
        return 0


def _gia_in_esecuzione(preferite: tuple[int, ...] = (8420, 8421, 8422)) -> tuple[str, int] | None:
    """``(url, pagine_aperte)`` di un'istanza gia' avviata **sui nostri dati**.

    Senza finestra del terminale non si vede che il gestionale e' gia' aperto: un
    secondo doppio clic ne avvierebbe un'altra copia sugli stessi dati. Le porte
    occupate da qualcos'altro — o da un'istanza su un altro archivio — vengono
    saltate.
    """
    import urllib.request

    for porta in preferite:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            if s.connect_ex(("127.0.0.1", porta)) != 0:
                continue
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{porta}/salute", timeout=1.5) as r:
                if r.status != 200:
                    continue
                corpo = r.read(1024).decode("utf-8", "replace")
        except Exception:
            continue  # la porta e' occupata da altro: si prova la successiva
        if _stessa_installazione(corpo):
            return f"http://127.0.0.1:{porta}", _pagine_da_salute(corpo)
    return None


# Il titolo di ogni pagina finisce con questo (vedi templates/base.html), quindi
# la finestra del browser che la mostra lo contiene.
TITOLO_FINESTRA = "Gestionale Veterinario"


def _porta_in_primo_piano(pezzo_titolo: str = TITOLO_FINESTRA) -> bool:
    """Porta davanti la finestra del browser che sta mostrando il gestionale.

    Serve al secondo doppio clic: aprire un'altra scheda sulla stessa pagina e'
    fastidioso, la cosa giusta e' mostrare quella che c'e' gia'. Solo Win32 via
    ``ctypes`` (nessuna dipendenza), e best effort: se la finestra non si trova
    (per esempio la scheda del gestionale non e' quella attiva, e quindi il
    titolo non compare) si ritorna ``False`` e il chiamante apre il browser.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        trovate: list[int] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def esamina(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            lunghezza = user32.GetWindowTextLengthW(hwnd)
            if lunghezza:
                buf = ctypes.create_unicode_buffer(lunghezza + 1)
                user32.GetWindowTextW(hwnd, buf, lunghezza + 1)
                if pezzo_titolo in buf.value:
                    trovate.append(hwnd)
                    return False  # la prima basta
            return True

        user32.EnumWindows(esamina, 0)
        if not trovate:
            return False
        hwnd = trovate[0]
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE: se era ridotta a icona
        return bool(user32.SetForegroundWindow(hwnd))
    except Exception:
        return False


def _dirotta_output() -> Path | None:
    """Manda stdout/stderr su file quando non c'e' una console.

    Nell'exe senza finestra ``sys.stdout``/``sys.stderr`` sono ``None``: la prima
    riga di log di uvicorn farebbe saltare l'avvio, e per giunta in silenzio. Il
    file resta accanto ai dati, cosi' se qualcosa non parte c'e' dove guardare.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return None
    DATI_DIR.mkdir(parents=True, exist_ok=True)
    percorso = DATI_DIR / "avvio.log"
    f = open(percorso, "a", encoding="utf-8", buffering=1)
    sys.stdout = f
    sys.stderr = f
    return percorso


def _avviso(titolo: str, messaggio: str) -> None:
    """Finestrella di sistema: senza console e' l'unico modo di farsi sentire."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, messaggio, titolo, 0x10)
    except Exception:
        pass


def main() -> None:
    global _server
    log = _dirotta_output()
    try:
        gia = _gia_in_esecuzione()
        if gia:
            url, pagine = gia
            # Se una pagina e' gia' aperta, la cosa giusta e' mostrarla, non
            # aprirne un'altra sulla stessa cosa. Se non c'e' nessuna pagina
            # (istanza accesa ma browser chiuso) o se la finestra non si trova,
            # allora si apre il browser.
            if pagine > 0 and _porta_in_primo_piano():
                print(f"Gestionale gia' aperto su {url}: riportata avanti la finestra.")
                return
            webbrowser.open(url)
            return

        porta = _porta_libera()
        url = f"http://127.0.0.1:{porta}"
        # Apre il browser dopo un attimo, quando il server e' pronto ad accettare.
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        print(f"Gestionale avviato su {url}")
        _server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=porta, log_level="warning",
            # SENZA QUESTO IL PROGRAMMA NON SI CHIUDE. Il default e' None: uvicorn
            # aspetta *senza limite* che le richieste in corso finiscano, e il
            # flusso /presenza e' fatto per non finire mai. "Chiudi il gestionale"
            # resterebbe appeso. Il flusso molla da se' (controlla should_exit),
            # questo e' la rete di sicurezza se un domani smettesse di farlo.
            timeout_graceful_shutdown=3))
        # Il conto alla rovescia parte da adesso: il browser ha tutta la finestra di
        # grazia per aprirsi e collegare il primo flusso.
        segna_vita()
        threading.Thread(target=_guardiano, args=(_server,), daemon=True).start()
        _server.run()
    except Exception as e:
        dove = f"\n\nDettagli in:\n{log}" if log else ""
        _avviso("Gestionale — avvio non riuscito",
                f"Il gestionale non e' riuscito ad avviarsi.\n\n{type(e).__name__}: {e}{dove}")
        raise


if __name__ == "__main__":
    main()
