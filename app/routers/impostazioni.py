"""Router Impostazioni: dati dello studio emittente (riga singola)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.db import get_conn
from app.numerazione import esistono_documenti, imposta_partenza, numero_corrente
from app.templating import templates

router = APIRouter()

# Campi editabili di testo della tabella studio (esclusa la PK id).
_CAMPI = [
    "denominazione", "nome", "cognome", "codice_fiscale", "partita_iva",
    "via", "cap", "citta", "prov", "email", "telefono", "iban", "regime",
    "n_iscrizione_albo", "enpav_pct", "iva_default_pct", "formato_numerazione",
    "testo_dicitura_opposizione_ts", "logo_path",
]
# Campi booleani (checkbox). Nessuno al momento: l'invio via WhatsApp non ha
# niente da configurare (le colonne smtp_* sono morte, vedi migrazione v4).
_CHECKBOX: list[str] = []


def leggi_studio(conn) -> dict:
    row = conn.execute("SELECT * FROM studio WHERE id=1").fetchone()
    return dict(row)


@router.get("/impostazioni", response_class=HTMLResponse)
def form_impostazioni(request: Request):
    anno = date.today().year
    conn = get_conn()
    try:
        studio = leggi_studio(conn)
        prossimo = numero_corrente(conn, anno, "fattura") + 1
        bloccata = esistono_documenti(conn, anno, "fattura")
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "impostazioni.html",
        {"titolo": "Impostazioni", "studio": studio, "anno": anno,
         "prossimo_numero": prossimo, "numerazione_bloccata": bloccata},
    )


@router.post("/impostazioni/numerazione")
async def salva_numerazione(request: Request):
    form = await request.form()
    anno = date.today().year
    valore = str(form.get("prossimo_numero", "")).strip()
    if not valore.isdigit():
        return RedirectResponse("/impostazioni?msg=Numero+non+valido", status_code=303)
    conn = get_conn()
    try:
        try:
            imposta_partenza(conn, anno, int(valore), "fattura")
            msg = f"Prossima+fattura:+{valore}/{anno}"
        except ValueError as e:
            msg = f"Errore:+{e}"
    finally:
        conn.close()
    return RedirectResponse(f"/impostazioni?msg={msg}", status_code=303)


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
