"""Router Listino: prestazioni con prezzo, aliquota IVA e tipo spesa STS."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from urllib.parse import quote_plus

from app.calcolo import ValoreNonNumerico, dec, q2
from app.db import get_conn, usi_che_impediscono_cancellazione
from app.templating import templates
from app.validazioni import (
    TIPI_SPESA_TS, normalizza_tipo_spesa_ts, valida_percentuale,
    valida_tipo_spesa_ts,
)

router = APIRouter()

_CAMPI = ["codice", "descrizione", "prezzo_unitario", "aliquota_iva",
          "tipo_spesa_ts", "unita_misura"]


def _estrai(form) -> dict:
    """Legge il modulo **senza convertire**: la conversione la fa :func:`_valida`.

    Prima qui dentro girava ``q2()`` sul valore grezzo. Con un prezzo scritto
    male l'eccezione partiva da qui, cioe' *prima* che qualcuno avesse la
    possibilita' di raccogliere l'errore e rimandarlo nel modulo: usciva una
    pagina di errore di sistema per un semplice refuso.
    """
    dati = {c: str(form.get(c, "")).strip() for c in _CAMPI}
    dati["attiva"] = 1 if form.get("attiva") else 0
    dati["tipo_spesa_ts"] = normalizza_tipo_spesa_ts(dati["tipo_spesa_ts"])
    return dati


def _valida(dati: dict) -> list[str]:
    """Controlla, e **normalizza a 2 decimali** i valori buoni (modifica ``dati``)."""
    errori: list[str] = []
    if not dati["descrizione"]:
        errori.append("La descrizione della prestazione e' obbligatoria.")
    # Il menu offre solo i codici ammessi, ma la richiesta puo' arrivare comunque
    # con altro: da qui il valore finisce negli snapshot immutabili delle fatture.
    errori += valida_tipo_spesa_ts(dati["tipo_spesa_ts"])

    prezzo = dati["prezzo_unitario"] or "0"
    aliquota = dati["aliquota_iva"] or "22"
    try:
        d_prezzo = dec(prezzo)
    except ValoreNonNumerico:
        errori.append(f"Prezzo non valido: «{prezzo}» non è un numero.")
        d_prezzo = None
    if d_prezzo is not None and d_prezzo < 0:
        errori.append("Il prezzo non può essere negativo.")
        d_prezzo = None
    errori += valida_percentuale(aliquota, "Aliquota IVA")

    if not errori:
        dati["prezzo_unitario"] = str(q2(d_prezzo))
        dati["aliquota_iva"] = str(q2(aliquota))
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
    """Toglie una voce di listino, se non e' gia' finita su qualche documento.

    Qui la strada giusta c'e' gia' ed e' un'altra: togliere la spunta **Attiva**.
    La voce sparisce dai menu delle nuove fatture ma resta collegata a quelle
    vecchie. Il messaggio lo dice, altrimenti si resta bloccati senza sapere che
    fare.
    """
    conn = get_conn()
    try:
        usi = usi_che_impediscono_cancellazione(conn, "prestazioni", pid)
        if usi:
            return RedirectResponse(
                "/listino?msg=" + quote_plus(
                    f"Non si può eliminare questa voce: è usata in {', '.join(usi)}. "
                    "Per non vederla più fra le nuove, aprila e togli la spunta «Attiva»."),
                status_code=303)
        with conn:
            conn.execute("DELETE FROM prestazioni WHERE id=?", (pid,))
    finally:
        conn.close()
    return RedirectResponse("/listino?msg=Prestazione+eliminata", status_code=303)
