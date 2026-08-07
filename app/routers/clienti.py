"""Router Clienti: anagrafica proprietari (persona fisica o giuridica)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from urllib.parse import quote_plus

from app.db import get_conn, usi_che_impediscono_cancellazione
from app.templating import templates
from app.validazioni import valida_codice_fiscale, valida_partita_iva

router = APIRouter()

_CAMPI = [
    "tipo", "nome", "cognome", "ragione_sociale", "codice_fiscale", "partita_iva",
    "via", "cap", "citta", "provincia", "email", "telefono", "sconto_default_pct",
    "note",
]
_CHECKBOX = ["opposizione_ts_default", "sostituto_imposta", "fatturazione_mensile"]


def _estrai(form) -> dict:
    dati = {c: str(form.get(c, "")).strip() for c in _CAMPI}
    for c in _CHECKBOX:
        dati[c] = 1 if form.get(c) else 0
    if not dati["tipo"]:
        dati["tipo"] = "fisica"
    return dati


def _valida(dati: dict) -> list[str]:
    errori: list[str] = []
    if dati["tipo"] == "fisica":
        if not dati["nome"] or not dati["cognome"]:
            errori.append("Nome e cognome obbligatori per persona fisica.")
        errori += valida_codice_fiscale(dati["codice_fiscale"], obbligatorio=True)
        if dati["partita_iva"]:
            errori += valida_partita_iva(dati["partita_iva"])
    else:
        if not dati["ragione_sociale"]:
            errori.append("Ragione sociale obbligatoria per persona giuridica.")
        errori += valida_partita_iva(dati["partita_iva"], obbligatorio=True)
        if dati["codice_fiscale"]:
            # per le societa' il CF puo' coincidere con la P.IVA (11 cifre): non forziamo il check CF
            pass
    return errori


@router.get("/clienti", response_class=HTMLResponse)
def lista(request: Request):
    conn = get_conn()
    try:
        righe = [dict(r) for r in conn.execute(
            "SELECT * FROM clienti ORDER BY COALESCE(NULLIF(cognome,''), ragione_sociale), nome"
        ).fetchall()]
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "clienti_lista.html", {"titolo": "Clienti", "clienti": righe}
    )


@router.get("/clienti/nuovo", response_class=HTMLResponse)
def nuovo(request: Request):
    return templates.TemplateResponse(
        request, "clienti_form.html",
        {"titolo": "Nuovo cliente", "cliente": {"tipo": "fisica"}, "errori": []},
    )


@router.get("/clienti/{cid}", response_class=HTMLResponse)
def modifica(request: Request, cid: int):
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM clienti WHERE id=?", (cid,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return RedirectResponse("/clienti?msg=Cliente+non+trovato", status_code=303)
    return templates.TemplateResponse(
        request, "clienti_form.html",
        {"titolo": "Modifica cliente", "cliente": dict(row), "errori": []},
    )


@router.post("/clienti")
async def crea(request: Request):
    form = await request.form()
    dati = _estrai(form)
    errori = _valida(dati)
    if errori:
        dati["id"] = ""
        return templates.TemplateResponse(
            request, "clienti_form.html",
            {"titolo": "Nuovo cliente", "cliente": dati, "errori": errori},
            status_code=400,
        )
    colonne = _CAMPI + _CHECKBOX
    ph = ", ".join("?" for _ in colonne)
    conn = get_conn()
    try:
        with conn:
            conn.execute(
                f"INSERT INTO clienti ({', '.join(colonne)}) VALUES ({ph})",
                [dati[c] for c in colonne],
            )
    finally:
        conn.close()
    return RedirectResponse("/clienti?msg=Cliente+creato", status_code=303)


@router.post("/clienti/{cid}")
async def aggiorna(request: Request, cid: int):
    form = await request.form()
    dati = _estrai(form)
    errori = _valida(dati)
    if errori:
        dati["id"] = cid
        return templates.TemplateResponse(
            request, "clienti_form.html",
            {"titolo": "Modifica cliente", "cliente": dati, "errori": errori},
            status_code=400,
        )
    colonne = _CAMPI + _CHECKBOX
    set_clause = ", ".join(f"{c}=?" for c in colonne)
    conn = get_conn()
    try:
        with conn:
            conn.execute(
                f"UPDATE clienti SET {set_clause} WHERE id=?",
                [dati[c] for c in colonne] + [cid],
            )
    finally:
        conn.close()
    return RedirectResponse("/clienti?msg=Cliente+aggiornato", status_code=303)


@router.post("/clienti/{cid}/elimina")
def elimina(cid: int):
    """Toglie un cliente, se non e' rimasto attaccato a niente.

    Prima usciva ``FOREIGN KEY constraint failed`` come pagina di errore di
    sistema: sembrava un guasto, e non diceva cosa lo impedisse. Il rifiuto e'
    giusto — le fatture emesse restano, per legge, e devono restare intestate a
    qualcuno — ma va spiegato. I cavalli invece se ne vanno col proprietario:
    la loro chiave e' ``ON DELETE CASCADE``.
    """
    conn = get_conn()
    try:
        usi = usi_che_impediscono_cancellazione(conn, "clienti", cid)
        if usi:
            return RedirectResponse(
                "/clienti?msg=" + quote_plus(
                    f"Non si può eliminare questo cliente: ha {', '.join(usi)}. "
                    "I documenti emessi devono restare intestati a lui."),
                status_code=303)
        with conn:
            conn.execute("DELETE FROM clienti WHERE id=?", (cid,))
    finally:
        conn.close()
    return RedirectResponse("/clienti?msg=Cliente+eliminato", status_code=303)
