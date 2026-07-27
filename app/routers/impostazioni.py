"""Router Impostazioni: dati dello studio emittente (riga singola)."""
from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.db import get_conn
from app.templating import templates

router = APIRouter()

# Campi editabili di testo della tabella studio (esclusa la PK id).
_CAMPI = [
    "denominazione", "nome", "cognome", "codice_fiscale", "partita_iva",
    "via", "cap", "citta", "prov", "email", "telefono", "iban", "regime",
    "n_iscrizione_albo", "enpav_pct", "iva_default_pct", "formato_numerazione",
    "testo_dicitura_opposizione_ts", "logo_path",
    "smtp_host", "smtp_porta", "smtp_sicurezza", "smtp_utente", "smtp_password",
    "smtp_mittente",
]
# Campi booleani (checkbox).
_CHECKBOX = ["invio_auto_email"]


def leggi_studio(conn) -> dict:
    row = conn.execute("SELECT * FROM studio WHERE id=1").fetchone()
    return dict(row)


@router.get("/impostazioni", response_class=HTMLResponse)
def form_impostazioni(request: Request):
    conn = get_conn()
    try:
        studio = leggi_studio(conn)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "impostazioni.html", {"titolo": "Impostazioni", "studio": studio}
    )


@router.post("/impostazioni")
async def salva_impostazioni(request: Request):
    form = await request.form()
    colonne = _CAMPI + _CHECKBOX
    valori = [str(form.get(c, "")).strip() for c in _CAMPI]
    valori += [1 if form.get(c) else 0 for c in _CHECKBOX]
    set_clause = ", ".join(f"{c}=?" for c in colonne)
    conn = get_conn()
    try:
        with conn:
            conn.execute(f"UPDATE studio SET {set_clause} WHERE id=1", valori)
    finally:
        conn.close()
    return RedirectResponse("/impostazioni?msg=Impostazioni+salvate", status_code=303)
