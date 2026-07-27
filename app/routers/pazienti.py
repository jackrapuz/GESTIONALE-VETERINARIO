"""Router Pazienti: animali (ottimizzato per equini, campi extra opzionali)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.db import get_conn
from app.templating import templates

router = APIRouter()

_CAMPI = [
    "cliente_id", "nome", "specie", "razza", "microchip", "sesso",
    "data_nascita", "mantello", "passaporto_ueln", "note",
]


def _clienti_opzioni(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT id, tipo, nome, cognome, ragione_sociale FROM clienti "
        "ORDER BY COALESCE(NULLIF(cognome,''), ragione_sociale)"
    ).fetchall()]


def _estrai(form) -> dict:
    dati = {c: str(form.get(c, "")).strip() for c in _CAMPI}
    if not dati["specie"]:
        dati["specie"] = "Equino"
    return dati


@router.get("/pazienti", response_class=HTMLResponse)
def lista(request: Request):
    conn = get_conn()
    try:
        righe = [dict(r) for r in conn.execute(
            """SELECT p.*, c.nome AS cli_nome, c.cognome AS cli_cognome,
                      c.ragione_sociale AS cli_rag
               FROM pazienti p LEFT JOIN clienti c ON c.id = p.cliente_id
               ORDER BY p.nome"""
        ).fetchall()]
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "pazienti_lista.html", {"titolo": "Pazienti", "pazienti": righe}
    )


@router.get("/pazienti/nuovo", response_class=HTMLResponse)
def nuovo(request: Request):
    conn = get_conn()
    try:
        clienti = _clienti_opzioni(conn)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "pazienti_form.html",
        {"titolo": "Nuovo paziente", "paziente": {"specie": "Equino"},
         "clienti": clienti, "errori": []},
    )


@router.get("/pazienti/{pid}", response_class=HTMLResponse)
def modifica(request: Request, pid: int):
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM pazienti WHERE id=?", (pid,)).fetchone()
        clienti = _clienti_opzioni(conn)
    finally:
        conn.close()
    if row is None:
        return RedirectResponse("/pazienti?msg=Paziente+non+trovato", status_code=303)
    return templates.TemplateResponse(
        request, "pazienti_form.html",
        {"titolo": "Modifica paziente", "paziente": dict(row),
         "clienti": clienti, "errori": []},
    )


def _valida(dati: dict) -> list[str]:
    errori: list[str] = []
    if not dati["cliente_id"]:
        errori.append("Selezionare il proprietario (cliente).")
    if not dati["nome"]:
        errori.append("Il nome del paziente e' obbligatorio.")
    return errori


@router.post("/pazienti")
async def crea(request: Request):
    form = await request.form()
    dati = _estrai(form)
    errori = _valida(dati)
    if errori:
        conn = get_conn()
        try:
            clienti = _clienti_opzioni(conn)
        finally:
            conn.close()
        return templates.TemplateResponse(
            request, "pazienti_form.html",
            {"titolo": "Nuovo paziente", "paziente": dati, "clienti": clienti,
             "errori": errori}, status_code=400,
        )
    ph = ", ".join("?" for _ in _CAMPI)
    conn = get_conn()
    try:
        with conn:
            conn.execute(
                f"INSERT INTO pazienti ({', '.join(_CAMPI)}) VALUES ({ph})",
                [dati[c] for c in _CAMPI],
            )
    finally:
        conn.close()
    return RedirectResponse("/pazienti?msg=Paziente+creato", status_code=303)


@router.post("/pazienti/{pid}")
async def aggiorna(request: Request, pid: int):
    form = await request.form()
    dati = _estrai(form)
    errori = _valida(dati)
    if errori:
        conn = get_conn()
        try:
            clienti = _clienti_opzioni(conn)
        finally:
            conn.close()
        dati["id"] = pid
        return templates.TemplateResponse(
            request, "pazienti_form.html",
            {"titolo": "Modifica paziente", "paziente": dati, "clienti": clienti,
             "errori": errori}, status_code=400,
        )
    set_clause = ", ".join(f"{c}=?" for c in _CAMPI)
    conn = get_conn()
    try:
        with conn:
            conn.execute(
                f"UPDATE pazienti SET {set_clause} WHERE id=?",
                [dati[c] for c in _CAMPI] + [pid],
            )
    finally:
        conn.close()
    return RedirectResponse("/pazienti?msg=Paziente+aggiornato", status_code=303)


@router.post("/pazienti/{pid}/elimina")
def elimina(pid: int):
    conn = get_conn()
    try:
        with conn:
            conn.execute("DELETE FROM pazienti WHERE id=?", (pid,))
    finally:
        conn.close()
    return RedirectResponse("/pazienti?msg=Paziente+eliminato", status_code=303)
