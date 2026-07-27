"""Avvio dell'applicazione: FastAPI locale + apertura automatica del browser.

Il gestionale e' un'app desktop offline: il server ascolta solo su 127.0.0.1 e
non fa alcuna chiamata di rete in uscita. Eseguibile sia con ``python -m app.main``
sia come exe PyInstaller.
"""
from __future__ import annotations

import socket
import threading
import webbrowser
from datetime import date
from decimal import Decimal
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.db import DATI_DIR, get_conn, init_db
from app.templating import templates

BASE_DIR = Path(__file__).resolve().parent


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

    # Router delle sezioni (registrati man mano che vengono implementati).
    from app.routers import (
        backup, clienti, export, fatture, impostazioni, pazienti, prestazioni,
        preventivi,
    )

    app.include_router(impostazioni.router)
    app.include_router(clienti.router)
    app.include_router(pazienti.router)
    app.include_router(prestazioni.router)
    app.include_router(fatture.router)
    app.include_router(preventivi.router)
    app.include_router(export.router)
    app.include_router(backup.router)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        ctx = {"titolo": "Home"}
        ctx.update(_statistiche_dashboard())
        return templates.TemplateResponse(request, "home.html", ctx)

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
