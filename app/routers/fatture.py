"""Router Fatture: emissione, elenco, dettaglio, stato, annullo, nota di credito.

L'emissione vera e propria e' delegata a :func:`app.fatturazione.emetti_fattura`
(transazione atomica). Qui restano il parsing del form, le validazioni d'input e
la resa delle pagine.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.calcolo import RigaInput, dec, q2
from app.db import get_conn
from app.fatturazione import (
    denominazione_cliente, emetti_fattura, gruppi_iva_da_righe, leggi_fattura,
)
from app.numerazione import verifica_continuita
from app.pdf_fattura import genera_pdf_fattura
from app.routers.impostazioni import leggi_studio
from app.templating import templates

router = APIRouter()

MODALITA_PAGAMENTO = ["Bonifico", "Contanti", "Carta", "Assegno", "POS", "Altro"]


# ---------------------------------------------------------------------------
# Helper di lettura
# ---------------------------------------------------------------------------
def _clienti_per_select(conn) -> list[dict]:
    righe = conn.execute("SELECT * FROM clienti ORDER BY cognome, ragione_sociale, nome").fetchall()
    out = []
    for r in righe:
        d = dict(r)
        out.append({
            "id": d["id"],
            "denominazione": denominazione_cliente(d),
            "sconto_default_pct": d["sconto_default_pct"],
            "opposizione_ts_default": d["opposizione_ts_default"],
            "sostituto_imposta": d["sostituto_imposta"],
            "partita_iva": d["partita_iva"],
        })
    return out


def _prestazioni_attive(conn) -> list[dict]:
    righe = conn.execute(
        "SELECT id, codice, descrizione, prezzo_unitario, aliquota_iva, tipo_spesa_ts "
        "FROM prestazioni WHERE attiva=1 ORDER BY descrizione"
    ).fetchall()
    return [dict(r) for r in righe]


# ---------------------------------------------------------------------------
# Parsing del form di emissione
# ---------------------------------------------------------------------------
def _righe_da_form(form) -> list[RigaInput]:
    """Costruisce le RigaInput dalle liste parallele del form, scartando le righe vuote."""
    descrizioni = form.getlist("r_descrizione")
    quantita = form.getlist("r_quantita")
    prezzi = form.getlist("r_prezzo")
    sconti = form.getlist("r_sconto")
    aliquote = form.getlist("r_aliquota")
    tipi = form.getlist("r_tipo_spesa")
    presta = form.getlist("r_prestazione_id")

    righe: list[RigaInput] = []
    for i in range(len(descrizioni)):
        desc = (descrizioni[i] or "").strip()
        prezzo = (prezzi[i] if i < len(prezzi) else "") or ""
        # riga vuota: nessuna descrizione e prezzo nullo -> ignora
        if not desc and dec(prezzo) == 0:
            continue
        pid = presta[i] if i < len(presta) else ""
        righe.append(RigaInput(
            descrizione=desc or "Prestazione",
            quantita=dec(quantita[i] if i < len(quantita) else "1") or 1,
            prezzo_unitario=dec(prezzo),
            aliquota_iva=dec(aliquote[i] if i < len(aliquote) else "22") or dec("22"),
            sconto_riga_pct=dec(sconti[i] if i < len(sconti) else "0"),
            tipo_spesa_ts=(tipi[i] if i < len(tipi) else "SV") or "SV",
            prestazione_id=int(pid) if str(pid).strip().isdigit() else None,
        ))
    return righe


# ---------------------------------------------------------------------------
# Rotte
# ---------------------------------------------------------------------------
@router.get("/fatture", response_class=HTMLResponse)
def lista(request: Request):
    conn = get_conn()
    try:
        fatture = [dict(r) for r in conn.execute(
            "SELECT * FROM fatture ORDER BY anno DESC, tipo_documento, numero_progressivo DESC"
        ).fetchall()]
        # Segnala eventuali buchi nella numerazione dell'anno corrente.
        anno = date.today().year
        buchi = verifica_continuita(conn, anno, "fattura")
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "fatture_lista.html",
        {"titolo": "Fatture", "fatture": fatture, "anno": anno, "buchi": buchi},
    )


@router.get("/fatture/nuova", response_class=HTMLResponse)
def nuova(request: Request):
    conn = get_conn()
    try:
        clienti = _clienti_per_select(conn)
        prestazioni = _prestazioni_attive(conn)
        studio = leggi_studio(conn)
    finally:
        conn.close()
    if not clienti:
        return RedirectResponse(
            "/clienti?msg=Crea+prima+almeno+un+cliente", status_code=303)
    return templates.TemplateResponse(
        request, "fattura_nuova.html",
        {"titolo": "Nuova fattura", "clienti": clienti, "prestazioni": prestazioni,
         "studio": studio, "modalita": MODALITA_PAGAMENTO, "oggi": date.today().isoformat(),
         "errori": [], "dati": {}},
    )


@router.post("/fatture")
async def crea(request: Request):
    form = await request.form()
    conn = get_conn()
    try:
        clienti = _clienti_per_select(conn)
        prestazioni = _prestazioni_attive(conn)
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
        righe = _righe_da_form(form)
        if not righe:
            errori.append("Inserire almeno una riga con importo.")

        ritenuta_applicata = bool(form.get("ritenuta_applicata"))
        if ritenuta_applicata and cliente is not None and not cliente["sostituto_imposta"]:
            errori.append("La ritenuta d'acconto e' ammessa solo per clienti sostituto d'imposta.")

        if errori:
            return templates.TemplateResponse(
                request, "fattura_nuova.html",
                {"titolo": "Nuova fattura", "clienti": clienti, "prestazioni": prestazioni,
                 "studio": studio, "modalita": MODALITA_PAGAMENTO,
                 "oggi": date.today().isoformat(), "errori": errori,
                 "dati": {k: form.get(k) for k in form.keys()}},
                status_code=400,
            )

        esito = emetti_fattura(
            conn,
            cliente=cliente,
            righe=righe,
            data_emissione=data_emissione,
            sconto_cliente_pct=q2(form.get("sconto_cliente_pct") or "0"),
            enpav_pct=q2(studio.get("enpav_pct") or "2"),
            ritenuta_applicata=ritenuta_applicata,
            ritenuta_pct=q2(form.get("ritenuta_pct") or "0"),
            modalita_pagamento=str(form.get("modalita_pagamento", "")).strip(),
            pagamento_tracciato=bool(form.get("pagamento_tracciato")),
            data_pagamento=str(form.get("data_pagamento", "")).strip(),
            stato=str(form.get("stato", "emessa")).strip() or "emessa",
            opposizione_ts=bool(form.get("opposizione_ts")),
            note=str(form.get("note", "")).strip(),
            formato_numerazione=studio.get("formato_numerazione") or "{n}/{anno}",
        )
    finally:
        conn.close()
    return RedirectResponse(
        f"/fatture/{esito['id']}?msg=Fattura+{esito['numero_visualizzato']}+emessa",
        status_code=303)


@router.get("/fatture/{fid}", response_class=HTMLResponse)
def dettaglio(request: Request, fid: int):
    conn = get_conn()
    try:
        fattura = leggi_fattura(conn, fid)
        studio = leggi_studio(conn)
    finally:
        conn.close()
    if fattura is None:
        return RedirectResponse("/fatture?msg=Documento+non+trovato", status_code=303)
    gruppi = gruppi_iva_da_righe(fattura["righe"], fattura["enpav_pct"])
    return templates.TemplateResponse(
        request, "fattura_dettaglio.html",
        {"titolo": fattura["numero_visualizzato"], "f": fattura, "studio": studio,
         "gruppi": gruppi, "modalita": MODALITA_PAGAMENTO},
    )


@router.get("/fatture/{fid}/pdf")
def pdf(fid: int):
    conn = get_conn()
    try:
        fattura = leggi_fattura(conn, fid)
        studio = leggi_studio(conn)
    finally:
        conn.close()
    if fattura is None:
        return RedirectResponse("/fatture?msg=Documento+non+trovato", status_code=303)
    gruppi = gruppi_iva_da_righe(fattura["righe"], fattura["enpav_pct"])
    contenuto = genera_pdf_fattura(fattura, studio, gruppi)
    nome = f"{fattura['tipo_documento']}_{fattura['numero_visualizzato'].replace('/', '-')}.pdf"
    return Response(
        content=contenuto,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{nome}"'},
    )


@router.post("/fatture/{fid}/stato")
async def cambia_stato(request: Request, fid: int):
    form = await request.form()
    stato = str(form.get("stato", "emessa")).strip()
    data_pagamento = str(form.get("data_pagamento", "")).strip()
    if stato not in ("emessa", "incassata"):
        return RedirectResponse(f"/fatture/{fid}?msg=Stato+non+valido", status_code=303)
    conn = get_conn()
    try:
        with conn:
            conn.execute(
                "UPDATE fatture SET stato=?, data_pagamento=? WHERE id=? AND stato!='annullata'",
                (stato, data_pagamento, fid),
            )
    finally:
        conn.close()
    return RedirectResponse(f"/fatture/{fid}?msg=Stato+aggiornato", status_code=303)


@router.post("/fatture/{fid}/annulla")
def annulla(fid: int):
    conn = get_conn()
    try:
        with conn:
            conn.execute("UPDATE fatture SET stato='annullata' WHERE id=?", (fid,))
    finally:
        conn.close()
    return RedirectResponse(f"/fatture/{fid}?msg=Documento+annullato", status_code=303)


@router.post("/fatture/{fid}/nota-credito")
def nota_credito(fid: int):
    """Genera una nota di credito che storna integralmente la fattura indicata.

    Le righe riportano gli imponibili gia' calcolati (quantita' 1, prezzo =
    imponibile di riga) cosi' i totali della nota rispecchiano esattamente quelli
    del documento stornato. La nota ha una propria numerazione (tipo 'nota_credito').
    """
    conn = get_conn()
    try:
        originale = leggi_fattura(conn, fid)
        studio = leggi_studio(conn)
        if originale is None:
            return RedirectResponse("/fatture?msg=Documento+non+trovato", status_code=303)
        if originale["tipo_documento"] != "fattura":
            return RedirectResponse(
                f"/fatture/{fid}?msg=Solo+le+fatture+possono+essere+stornate", status_code=303)
        cliente = conn.execute(
            "SELECT * FROM clienti WHERE id=?", (originale["cliente_id"],)).fetchone()
        cliente = dict(cliente) if cliente else {
            "id": originale["cliente_id"], "tipo": "fisica",
            "cognome": originale["cli_denominazione"], "nome": "",
            "codice_fiscale": originale["cli_codice_fiscale"],
            "partita_iva": originale["cli_partita_iva"],
        }
        righe = [
            RigaInput(
                descrizione=r["descrizione"], quantita=1,
                prezzo_unitario=r["imponibile_riga"], aliquota_iva=r["aliquota_iva"],
                tipo_spesa_ts=r["tipo_spesa_ts"], prestazione_id=r["prestazione_id"],
            )
            for r in originale["righe"]
        ]
        esito = emetti_fattura(
            conn,
            cliente=cliente,
            righe=righe,
            data_emissione=date.today().isoformat(),
            tipo_documento="nota_credito",
            enpav_pct=originale["enpav_pct"],
            ritenuta_applicata=bool(originale["ritenuta_applicata"]),
            ritenuta_pct=originale["ritenuta_pct"],
            opposizione_ts=bool(originale["opposizione_ts"]),
            note=f"Storno della fattura n. {originale['numero_visualizzato']} "
                 f"del {originale['data_emissione']}.",
            formato_numerazione=studio.get("formato_numerazione") or "{n}/{anno}",
            documento_riferimento_id=fid,
        )
    finally:
        conn.close()
    return RedirectResponse(
        f"/fatture/{esito['id']}?msg=Nota+di+credito+{esito['numero_visualizzato']}+creata",
        status_code=303)
