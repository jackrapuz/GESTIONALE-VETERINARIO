"""Avvio dell'applicazione: FastAPI locale + apertura automatica del browser.

Il gestionale e' un'app desktop offline: il server ascolta solo su 127.0.0.1 e
non fa alcuna chiamata di rete in uscita. Eseguibile sia con ``python -m app.main``
sia come exe PyInstaller.
"""
from __future__ import annotations

import socket
import threading
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.db import DATI_DIR, init_db
from app.templating import templates

BASE_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    """Costruisce l'app FastAPI, monta gli static e registra i router."""
    # Crea DB, cartella dati e applica migrazioni prima di servire richieste.
    DATI_DIR.mkdir(parents=True, exist_ok=True)
    init_db()

    app = FastAPI(title="Gestionale Fatturazione", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    # Router delle sezioni (registrati man mano che vengono implementati).
    from app.routers import clienti, fatture, impostazioni, pazienti, prestazioni

    app.include_router(impostazioni.router)
    app.include_router(clienti.router)
    app.include_router(pazienti.router)
    app.include_router(prestazioni.router)
    app.include_router(fatture.router)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        return templates.TemplateResponse(request, "home.html", {"titolo": "Home"})

    return app


app = create_app()


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


def main() -> None:
    porta = _porta_libera()
    url = f"http://127.0.0.1:{porta}"
    # Apre il browser dopo un attimo, quando il server e' pronto ad accettare.
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"Gestionale avviato su {url}  (chiudi questa finestra per uscire)")
    uvicorn.run(app, host="127.0.0.1", port=porta, log_level="warning")


if __name__ == "__main__":
    main()
