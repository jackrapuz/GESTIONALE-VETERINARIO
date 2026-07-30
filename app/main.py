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
GRAZIA_SECONDI = 30.0        # zero pagine tollerato prima di spegnersi
INTERVALLO_CONTROLLO = 5.0   # ogni quanto il guardiano ricontrolla
INTERVALLO_KEEPALIVE = 15.0  # ogni quanto il flusso manda un segno di vita

# Pagine attualmente collegate. Il contatore viene toccato dal loop asincrono
# (apertura/chiusura dei flussi) e letto dal thread del guardiano: il lock evita
# di ragionare su cosa sia atomico e cosa no.
_pagine_aperte = 0
_lucchetto = threading.Lock()

# Ultima richiesta ricevuta, orologio monotono (immune ai cambi di ora). E' il
# secondo segnale: copre la pagina vecchia rimasta in cache, senza il flusso.
_ultima_vita: float = time.monotonic()


def segna_vita() -> None:
    """Registra che qualcuno sta usando il programma proprio adesso."""
    global _ultima_vita
    _ultima_vita = time.monotonic()


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
        """
        segna_vita()
        return await call_next(request)

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
        """Serve a un secondo avvio per riconoscere che il gestionale gira gia'."""
        return "gestionale-veterinario"

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
            request, "spento.html", {"titolo": "Chiuso", "senza_presenza": True})

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


def _gia_in_esecuzione(preferite: tuple[int, ...] = (8420, 8421, 8422)) -> str | None:
    """URL di un'istanza gia' avviata, se ce n'e' una.

    Senza finestra del terminale non si vede che il gestionale e' gia' aperto: un
    secondo doppio clic ne avvierebbe un'altra copia sugli stessi dati. Qui si
    controlla se una delle porte risponde *ed e' questo programma*, cosi' il
    secondo avvio si limita a riportare in primo piano quello gia' in funzione.
    """
    for porta in preferite:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            if s.connect_ex(("127.0.0.1", porta)) != 0:
                continue
        try:
            import urllib.request
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{porta}/salute", timeout=1.5) as r:
                if r.status == 200 and r.read(32).startswith(b"gestionale"):
                    return f"http://127.0.0.1:{porta}"
        except Exception:
            continue  # la porta e' occupata da altro: si prova la successiva
    return None


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
            webbrowser.open(gia)
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
