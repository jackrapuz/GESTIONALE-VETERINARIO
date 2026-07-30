"""Router Preventivi (proforma): elenco, creazione, dettaglio, PDF, invio,
conversione in fattura, eliminazione.

Riusa il form e gli helper di emissione delle fatture; la logica di dominio sta
in :mod:`app.proforma`.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.calcolo import q2
from app.db import get_conn
from app.fatturazione import gruppi_iva_da_righe
from app.invio import (
    ConfigurazioneMancante, invia_email, link_whatsapp, testo_messaggio,
)
from app.pdf_fattura import genera_pdf_fattura
from app.proforma import (
    converti_in_fattura, elimina_proforma, emetti_proforma, leggi_proforma,
)
from app.routers.fatture import (
    MODALITA_PAGAMENTO, _clienti_per_select, _contatti, _nomi_pazienti,
    _pazienti_per_cliente, _prestazioni_attive, _righe_da_form,
)
from app.routers.impostazioni import leggi_studio
from app.templating import templates

router = APIRouter()


@router.get("/preventivi", response_class=HTMLResponse)
def lista(request: Request):
    conn = get_conn()
    try:
        proforme = [dict(r) for r in conn.execute(
            "SELECT * FROM proforme ORDER BY anno DESC, numero_progressivo DESC"
        ).fetchall()]
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "preventivi_lista.html", {"titolo": "Preventivi", "proforme": proforme})


@router.get("/preventivi/nuovo", response_class=HTMLResponse)
def nuovo(request: Request):
    conn = get_conn()
    try:
        clienti = _clienti_per_select(conn)
        prestazioni = _prestazioni_attive(conn)
        pazienti = _pazienti_per_cliente(conn)
        studio = leggi_studio(conn)
    finally:
        conn.close()
    if not clienti:
        return RedirectResponse("/clienti?msg=Crea+prima+almeno+un+cliente", status_code=303)
    return templates.TemplateResponse(
        request, "fattura_nuova.html",
        {"titolo": "Nuovo preventivo", "doc": "preventivo", "clienti": clienti,
         "prestazioni": prestazioni, "pazienti": pazienti, "studio": studio,
         "modalita": MODALITA_PAGAMENTO, "oggi": date.today().isoformat(),
         "errori": [], "dati": {}})


@router.post("/preventivi")
async def crea(request: Request):
    form = await request.form()
    conn = get_conn()
    try:
        clienti = _clienti_per_select(conn)
        prestazioni = _prestazioni_attive(conn)
        pazienti = _pazienti_per_cliente(conn)
        studio = leggi_studio(conn)

        errori: list[str] = []
        cid = str(form.get("cliente_id", "")).strip()
        cliente = None
        if not cid.isdigit():
            errori.append("Selezionare un cliente.")
        else:
            cliente = conn.execute("SELECT * FROM clienti WHERE id=?", (int(cid),)).fetchone()
            if cliente is None:
                errori.append("Cliente non trovato.")
        data_emissione = str(form.get("data_emissione", "")).strip() or date.today().isoformat()
        righe = _righe_da_form(form, _nomi_pazienti(conn))
        if not righe:
            errori.append("Inserire almeno una riga con importo.")

        if errori:
            return templates.TemplateResponse(
                request, "fattura_nuova.html",
                {"titolo": "Nuovo preventivo", "doc": "preventivo", "clienti": clienti,
                 "prestazioni": prestazioni, "pazienti": pazienti, "studio": studio,
                 "modalita": MODALITA_PAGAMENTO, "oggi": date.today().isoformat(),
                 "errori": errori, "dati": {k: form.get(k) for k in form.keys()}},
                status_code=400)

        validita = str(form.get("validita_giorni", "30")).strip()
        esito = emetti_proforma(
            conn, cliente=cliente, righe=righe, data_emissione=data_emissione,
            sconto_cliente_pct=q2(form.get("sconto_cliente_pct") or "0"),
            enpav_pct=q2(studio.get("enpav_pct") or "2"),
            ritenuta_applicata=bool(form.get("ritenuta_applicata")),
            ritenuta_pct=q2(form.get("ritenuta_pct") or "0"),
            validita_giorni=int(validita) if validita.isdigit() else 30,
            note=str(form.get("note", "")).strip())
    finally:
        conn.close()
    return RedirectResponse(
        f"/preventivi/{esito['id']}?msg=Preventivo+{esito['numero_visualizzato']}+creato",
        status_code=303)


@router.get("/preventivi/{pid}", response_class=HTMLResponse)
def dettaglio(request: Request, pid: int):
    conn = get_conn()
    try:
        p = leggi_proforma(conn, pid)
        studio = leggi_studio(conn)
        if p is None:
            return RedirectResponse("/preventivi?msg=Preventivo+non+trovato", status_code=303)
        contatti = _contatti(conn, p["cliente_id"])
    finally:
        conn.close()
    gruppi = gruppi_iva_da_righe(p["righe"], p["enpav_pct"])
    wa = link_whatsapp(contatti["telefono"], testo_messaggio(studio, p)) if contatti["telefono"] else ""
    return templates.TemplateResponse(
        request, "preventivo_dettaglio.html",
        {"titolo": p["numero_visualizzato"], "p": p, "studio": studio, "gruppi": gruppi,
         "contatti": contatti, "whatsapp": wa})


@router.get("/preventivi/{pid}/pdf")
def pdf(pid: int):
    conn = get_conn()
    try:
        p = leggi_proforma(conn, pid)
        studio = leggi_studio(conn)
    finally:
        conn.close()
    if p is None:
        return RedirectResponse("/preventivi?msg=Preventivo+non+trovato", status_code=303)
    gruppi = gruppi_iva_da_righe(p["righe"], p["enpav_pct"])
    contenuto = genera_pdf_fattura(p, studio, gruppi)
    nome = f"preventivo_{p['numero_visualizzato'].replace('/', '-')}.pdf"
    return Response(content=contenuto, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{nome}"'})


@router.post("/preventivi/{pid}/invia-email")
def invia_email_route(pid: int):
    conn = get_conn()
    try:
        p = leggi_proforma(conn, pid)
        studio = leggi_studio(conn)
        if p is None:
            return RedirectResponse("/preventivi?msg=Preventivo+non+trovato", status_code=303)
        contatti = _contatti(conn, p["cliente_id"])
        gruppi = gruppi_iva_da_righe(p["righe"], p["enpav_pct"])
        pdf_bytes = genera_pdf_fattura(p, studio, gruppi)
        try:
            invia_email(studio, destinatario=contatti["email"],
                        oggetto=f"Preventivo n. {p['numero_visualizzato']}",
                        corpo=testo_messaggio(studio, p),
                        allegati=[(f"preventivo_{p['numero_visualizzato'].replace('/', '-')}.pdf",
                                   pdf_bytes, "pdf")])
            msg = f"Email+inviata+a+{contatti['email']}"
        except (ConfigurazioneMancante, OSError) as e:
            msg = f"Errore+invio:+{str(e)[:80]}"
    finally:
        conn.close()
    return RedirectResponse(f"/preventivi/{pid}?msg={msg}", status_code=303)


@router.post("/preventivi/{pid}/converti")
def converti(pid: int):
    conn = get_conn()
    try:
        studio = leggi_studio(conn)
        try:
            esito = converti_in_fattura(conn, pid, studio)
        except ValueError as e:
            return RedirectResponse(f"/preventivi/{pid}?msg=Errore:+{e}", status_code=303)
    finally:
        conn.close()
    return RedirectResponse(
        f"/fatture/{esito['id']}?msg=Fattura+{esito['numero_visualizzato']}+creata+dal+preventivo",
        status_code=303)


@router.post("/preventivi/{pid}/elimina")
def elimina(pid: int):
    conn = get_conn()
    try:
        elimina_proforma(conn, pid)
    finally:
        conn.close()
    return RedirectResponse("/preventivi?msg=Preventivo+eliminato", status_code=303)
