"""Router Listino: prestazioni con prezzo, aliquota IVA e tipo spesa STS."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.calcolo import q2
from app.db import get_conn
from app.templating import templates

router = APIRouter()

_CAMPI = ["codice", "descrizione", "prezzo_unitario", "aliquota_iva",
          "tipo_spesa_ts", "unita_misura"]


def _estrai(form) -> dict:
    dati = {c: str(form.get(c, "")).strip() for c in _CAMPI}
    dati["attiva"] = 1 if form.get("attiva") else 0
    # normalizza importi/percentuali a 2 decimali
    dati["prezzo_unitario"] = str(q2(dati["prezzo_unitario"] or "0"))
    dati["aliquota_iva"] = str(q2(dati["aliquota_iva"] or "22"))
    if not dati["tipo_spesa_ts"]:
        dati["tipo_spesa_ts"] = "SV"
    return dati


def _valida(dati: dict) -> list[str]:
    errori: list[str] = []
    if not dati["descrizione"]:
        errori.append("La descrizione della prestazione e' obbligatoria.")
    return errori


@router.get("/listino", response_class=HTMLResponse)
def lista(request: Request):
    conn = get_conn()
    try:
        righe = [dict(r) for r in conn.execute(
            "SELECT * FROM prestazioni ORDER BY attiva DESC, descrizione"
        ).fetchall()]
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "listino_lista.html", {"titolo": "Listino", "prestazioni": righe}
    )


@router.get("/listino/nuovo", response_class=HTMLResponse)
def nuovo(request: Request):
    return templates.TemplateResponse(
        request, "listino_form.html",
        {"titolo": "Nuova prestazione",
         "prestazione": {"aliquota_iva": "22.00", "tipo_spesa_ts": "SV",
                         "unita_misura": "nr", "attiva": 1},
         "errori": []},
    )


@router.get("/listino/{pid}", response_class=HTMLResponse)
def modifica(request: Request, pid: int):
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM prestazioni WHERE id=?", (pid,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return RedirectResponse("/listino?msg=Prestazione+non+trovata", status_code=303)
    return templates.TemplateResponse(
        request, "listino_form.html",
        {"titolo": "Modifica prestazione", "prestazione": dict(row), "errori": []},
    )


@router.post("/listino")
async def crea(request: Request):
    form = await request.form()
    dati = _estrai(form)
    errori = _valida(dati)
    if errori:
        return templates.TemplateResponse(
            request, "listino_form.html",
            {"titolo": "Nuova prestazione", "prestazione": dati, "errori": errori},
            status_code=400,
        )
    colonne = _CAMPI + ["attiva"]
    ph = ", ".join("?" for _ in colonne)
    conn = get_conn()
    try:
        with conn:
            conn.execute(
                f"INSERT INTO prestazioni ({', '.join(colonne)}) VALUES ({ph})",
                [dati[c] for c in colonne],
            )
    finally:
        conn.close()
    return RedirectResponse("/listino?msg=Prestazione+creata", status_code=303)


@router.post("/listino/{pid}")
async def aggiorna(request: Request, pid: int):
    form = await request.form()
    dati = _estrai(form)
    errori = _valida(dati)
    if errori:
        dati["id"] = pid
        return templates.TemplateResponse(
            request, "listino_form.html",
            {"titolo": "Modifica prestazione", "prestazione": dati, "errori": errori},
            status_code=400,
        )
    colonne = _CAMPI + ["attiva"]
    set_clause = ", ".join(f"{c}=?" for c in colonne)
    conn = get_conn()
    try:
        with conn:
            conn.execute(
                f"UPDATE prestazioni SET {set_clause} WHERE id=?",
                [dati[c] for c in colonne] + [pid],
            )
    finally:
        conn.close()
    return RedirectResponse("/listino?msg=Prestazione+aggiornata", status_code=303)


@router.post("/listino/{pid}/elimina")
def elimina(pid: int):
    conn = get_conn()
    try:
        with conn:
            conn.execute("DELETE FROM prestazioni WHERE id=?", (pid,))
    finally:
        conn.close()
    return RedirectResponse("/listino?msg=Prestazione+eliminata", status_code=303)
