"""Router Registro prestazioni: annotazione rapida e generazione documenti.

Il registro e' il diario di lavoro: si annota una prestazione appena eseguita e
resta "da fatturare" finche' non viene inglobata in una fattura (subito, per i
clienti una-tantum) o a fine mese (clienti a fatturazione mensile).

La logica di dominio sta in :mod:`app.registro`; qui restano parsing del form e
resa delle pagine.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.db import get_conn
from app.registro import (
    annota, da_fatturare, elimina_voce, genera_fattura, genera_proforma,
)
from app.routers.fatture import (
    _clienti_per_select, _pazienti_per_cliente, _prestazioni_attive,
)
from app.routers.impostazioni import leggi_studio
from app.templating import templates

router = APIRouter()


@router.get("/registro", response_class=HTMLResponse)
def lista(request: Request):
    conn = get_conn()
    try:
        gruppi = da_fatturare(conn)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "registro_lista.html",
        {"titolo": "Registro prestazioni", "gruppi": gruppi},
    )


@router.get("/registro/nuovo", response_class=HTMLResponse)
def nuovo(request: Request):
    conn = get_conn()
    try:
        clienti = _clienti_per_select(conn)
        pazienti = _pazienti_per_cliente(conn)
        prestazioni = _prestazioni_attive(conn)
    finally:
        conn.close()
    if not clienti:
        return RedirectResponse("/clienti?msg=Crea+prima+almeno+un+cliente", status_code=303)
    return templates.TemplateResponse(
        request, "registro_form.html",
        {"titolo": "Annota prestazione", "clienti": clienti, "pazienti": pazienti,
         "prestazioni": prestazioni, "oggi": date.today().isoformat(),
         "errori": [], "dati": {}},
    )


@router.post("/registro")
async def crea(request: Request):
    form = await request.form()
    conn = get_conn()
    try:
        clienti = _clienti_per_select(conn)
        pazienti = _pazienti_per_cliente(conn)
        prestazioni = _prestazioni_attive(conn)

        errori: list[str] = []
        cid = str(form.get("cliente_id", "")).strip()
        if not cid.isdigit():
            errori.append("Selezionare un cliente.")
        descrizione = str(form.get("descrizione", "")).strip()
        prezzo = str(form.get("prezzo_unitario", "")).strip()
        if not descrizione:
            errori.append("Inserire la descrizione della prestazione.")

        if errori:
            return templates.TemplateResponse(
                request, "registro_form.html",
                {"titolo": "Annota prestazione", "clienti": clienti, "pazienti": pazienti,
                 "prestazioni": prestazioni, "oggi": date.today().isoformat(),
                 "errori": errori, "dati": {k: form.get(k) for k in form.keys()}},
                status_code=400,
            )

        paz = str(form.get("paziente_id", "")).strip()
        pres = str(form.get("prestazione_id", "")).strip()
        annota(
            conn,
            data_prestazione=str(form.get("data_prestazione", "")).strip(),
            cliente_id=int(cid),
            paziente_id=int(paz) if paz.isdigit() else None,
            prestazione_id=int(pres) if pres.isdigit() else None,
            descrizione=descrizione,
            quantita=str(form.get("quantita", "1")).strip() or "1",
            prezzo_unitario=prezzo or "0.00",
            sconto_riga_pct=str(form.get("sconto_riga_pct", "0")).strip() or "0",
            aliquota_iva=str(form.get("aliquota_iva", "22")).strip() or "22",
            tipo_spesa_ts=str(form.get("tipo_spesa_ts", "SV")).strip() or "SV",
            note=str(form.get("note", "")).strip(),
        )
    finally:
        conn.close()
    return RedirectResponse("/registro?msg=Prestazione+annotata", status_code=303)


@router.post("/registro/voce/{voce_id}/elimina")
def elimina(voce_id: int):
    """Toglie una prestazione annotata per errore (solo se non ancora fatturata).

    Il percorso ha il segmento fisso ``voce`` per non confondersi con
    ``/registro/{cliente_id}/...``, dove il numero e' un cliente e non una voce.
    """
    conn = get_conn()
    try:
        try:
            elimina_voce(conn, voce_id)
        except ValueError as e:
            return RedirectResponse(f"/registro?msg=Errore:+{e}", status_code=303)
    finally:
        conn.close()
    return RedirectResponse("/registro?msg=Prestazione+eliminata", status_code=303)


@router.post("/registro/{cliente_id}/fattura")
def fattura(cliente_id: int):
    conn = get_conn()
    try:
        studio = leggi_studio(conn)
        try:
            esito = genera_fattura(conn, cliente_id, studio)
        except ValueError as e:
            return RedirectResponse(f"/registro?msg=Errore:+{e}", status_code=303)
    finally:
        conn.close()
    return RedirectResponse(
        f"/fatture/{esito['id']}?msg=Fattura+{esito['numero_visualizzato']}+emessa+dal+registro",
        status_code=303)


@router.post("/registro/{cliente_id}/proforma")
def proforma(cliente_id: int):
    conn = get_conn()
    try:
        studio = leggi_studio(conn)
        try:
            esito = genera_proforma(conn, cliente_id, studio)
        except ValueError as e:
            return RedirectResponse(f"/registro?msg=Errore:+{e}", status_code=303)
    finally:
        conn.close()
    return RedirectResponse(
        f"/preventivi/{esito['id']}?msg=Proforma+{esito['numero_visualizzato']}+creata+dal+registro",
        status_code=303)
