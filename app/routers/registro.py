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

from app.calcolo import ValoreNonNumerico, dec, q2
from app.db import get_conn
from app.registro import (
    annota, da_fatturare, elimina_voce, genera_fattura, genera_proforma,
)
from app.routers.fatture import (
    _clienti_per_select, _pazienti_per_cliente, _prestazioni_attive,
)
from app.routers.impostazioni import leggi_studio
from app.templating import templates
from app.validazioni import (
    normalizza_tipo_spesa_ts, valida_importi_riga, valida_tipo_spesa_ts,
)

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
        if not descrizione:
            errori.append("Inserire la descrizione della prestazione.")
        # Il valore attraversa il registro e finisce nello snapshot immutabile
        # della riga di fattura: se e' fuori standard non si corregge piu'.
        tipo_spesa = normalizza_tipo_spesa_ts(str(form.get("tipo_spesa_ts", "")))
        errori += valida_tipo_spesa_ts(tipo_spesa)

        # **Gli stessi controlli delle righe di fattura, e per lo stesso motivo.**
        # Quello che si annota qui non resta qui: la voce viene poi trasformata in
        # riga di fattura da "Fattura il registro". Un'aliquota impossibile
        # accettata adesso rientrerebbe dalla porta di servizio, dentro un
        # documento che non si cancella piu'.
        importi = {"quantita": "1", "prezzo_unitario": "0", "sconto_riga_pct": "0",
                   "aliquota_iva": "22"}
        numeri = {}
        for campo, predefinito in importi.items():
            grezzo = str(form.get(campo, "")).strip() or predefinito
            try:
                numeri[campo] = dec(grezzo)
            except ValoreNonNumerico:
                errori.append(f"{campo.replace('_', ' ').capitalize()}: "
                              f"«{grezzo}» non è un numero.")
        if len(numeri) == len(importi):
            errori += valida_importi_riga(
                descrizione, numeri["quantita"], numeri["prezzo_unitario"],
                numeri["sconto_riga_pct"], numeri["aliquota_iva"])

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
            # Gia' convertiti e controllati sopra: si salvano normalizzati col
            # punto decimale, come ogni altro importo nel database. Salvare "45,50"
            # cosi' com'e' funzionerebbe (``dec()`` la virgola la legge), ma
            # lascerebbe due notazioni diverse nella stessa colonna.
            quantita=str(q2(numeri["quantita"])),
            prezzo_unitario=str(q2(numeri["prezzo_unitario"])),
            sconto_riga_pct=str(q2(numeri["sconto_riga_pct"])),
            aliquota_iva=str(q2(numeri["aliquota_iva"])),
            tipo_spesa_ts=tipo_spesa,
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
