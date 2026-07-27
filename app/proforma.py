"""Preventivi / proforma: documenti NON fiscali.

Riusano il motore di calcolo delle fatture (ENPAV, IVA, ritenuta) e il generatore
PDF. A differenza delle fatture NON sono immutabili: si possono eliminare finche'
non convertite. La conversione crea una vera fattura dagli stessi importi.
"""
from __future__ import annotations

import sqlite3
from datetime import date

from app.calcolo import RigaInput, calcola_fattura
from app.fatturazione import (
    denominazione_cliente, emetti_fattura, indirizzo_cliente,
)
from app.numerazione import prossimo_numero

_COLONNE = [
    "anno", "numero_progressivo", "numero_visualizzato", "data_emissione",
    "validita_giorni", "cliente_id", "cli_denominazione", "cli_codice_fiscale",
    "cli_partita_iva", "cli_indirizzo", "ritenuta_applicata", "ritenuta_pct",
    "enpav_pct", "imponibile", "contributo_enpav", "base_iva", "iva_totale",
    "ritenuta_importo", "totale_documento", "netto_a_pagare", "note",
]


def leggi_proforma(conn: sqlite3.Connection, pid: int) -> dict | None:
    """Legge una proforma con le sue righe; aggiunge tipo_documento='proforma'."""
    row = conn.execute("SELECT * FROM proforme WHERE id=?", (pid,)).fetchone()
    if row is None:
        return None
    p = dict(row)
    p["tipo_documento"] = "proforma"
    p["righe"] = [dict(r) for r in conn.execute(
        "SELECT * FROM righe_proforma WHERE proforma_id=? ORDER BY ordine, id", (pid,)
    ).fetchall()]
    return p


def emetti_proforma(
    conn: sqlite3.Connection, *, cliente: dict | sqlite3.Row, righe: list[RigaInput],
    data_emissione: str, sconto_cliente_pct="0", enpav_pct="2",
    ritenuta_applicata: bool = False, ritenuta_pct="0", validita_giorni: int = 30,
    note: str = "",
) -> dict:
    """Crea una proforma (numerazione propria 'P{n}/{anno}') e la restituisce."""
    ris = calcola_fattura(
        righe, sconto_cliente_pct=sconto_cliente_pct, enpav_pct=enpav_pct,
        ritenuta_applicata=ritenuta_applicata, ritenuta_pct=ritenuta_pct)
    anno = int(str(data_emissione)[:4])
    cli = dict(cliente)

    conn.execute("BEGIN IMMEDIATE")
    try:
        numero = prossimo_numero(conn, anno, "proforma")
        numero_vis = f"P{numero}/{anno}"
        valori = {
            "anno": anno, "numero_progressivo": numero, "numero_visualizzato": numero_vis,
            "data_emissione": data_emissione, "validita_giorni": validita_giorni,
            "cliente_id": cli.get("id"),
            "cli_denominazione": denominazione_cliente(cli),
            "cli_codice_fiscale": (cli.get("codice_fiscale") or "").strip(),
            "cli_partita_iva": (cli.get("partita_iva") or "").strip(),
            "cli_indirizzo": indirizzo_cliente(cli),
            "ritenuta_applicata": 1 if ritenuta_applicata else 0,
            "ritenuta_pct": str(ritenuta_pct), "enpav_pct": str(enpav_pct),
            "imponibile": str(ris.imponibile), "contributo_enpav": str(ris.contributo_enpav),
            "base_iva": str(ris.base_iva), "iva_totale": str(ris.iva_totale),
            "ritenuta_importo": str(ris.ritenuta_importo),
            "totale_documento": str(ris.totale_documento),
            "netto_a_pagare": str(ris.netto_a_pagare), "note": note,
        }
        ph = ", ".join("?" for _ in _COLONNE)
        cur = conn.execute(
            f"INSERT INTO proforme ({', '.join(_COLONNE)}) VALUES ({ph})",
            [valori[c] for c in _COLONNE])
        pid = int(cur.lastrowid)
        for ordine, rc in enumerate(ris.righe):
            conn.execute(
                "INSERT INTO righe_proforma (proforma_id, prestazione_id, descrizione, "
                "quantita, prezzo_unitario, sconto_riga_pct, aliquota_iva, tipo_spesa_ts, "
                "imponibile_riga, ordine) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (pid, rc.prestazione_id, rc.descrizione, str(rc.quantita),
                 str(rc.prezzo_unitario), str(rc.sconto_riga_pct), str(rc.aliquota_iva),
                 rc.tipo_spesa_ts, str(rc.imponibile_riga), ordine))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"id": pid, "numero_visualizzato": numero_vis, "risultato": ris}


def elimina_proforma(conn: sqlite3.Connection, pid: int) -> None:
    with conn:
        conn.execute("DELETE FROM proforme WHERE id=? AND stato!='convertita'", (pid,))


def converti_in_fattura(conn: sqlite3.Connection, pid: int, studio: dict) -> dict:
    """Crea una fattura dagli importi della proforma e marca la proforma convertita.

    Le righe usano l'imponibile gia' calcolato (quantita' 1, prezzo = imponibile)
    cosi' i totali della fattura coincidono con quelli del preventivo.
    """
    proforma = leggi_proforma(conn, pid)
    if proforma is None:
        raise ValueError("Preventivo non trovato.")
    if proforma["stato"] == "convertita":
        raise ValueError("Preventivo gia' convertito in fattura.")

    cliente = conn.execute(
        "SELECT * FROM clienti WHERE id=?", (proforma["cliente_id"],)).fetchone()
    cliente = dict(cliente) if cliente else {
        "id": proforma["cliente_id"], "tipo": "fisica",
        "cognome": proforma["cli_denominazione"], "nome": "",
        "codice_fiscale": proforma["cli_codice_fiscale"],
        "partita_iva": proforma["cli_partita_iva"],
    }
    righe = [
        RigaInput(descrizione=r["descrizione"], quantita=1,
                  prezzo_unitario=r["imponibile_riga"], aliquota_iva=r["aliquota_iva"],
                  tipo_spesa_ts=r["tipo_spesa_ts"], prestazione_id=r["prestazione_id"])
        for r in proforma["righe"]
    ]
    esito = emetti_fattura(
        conn, cliente=cliente, righe=righe,
        data_emissione=date.today().isoformat(),
        enpav_pct=proforma["enpav_pct"],
        ritenuta_applicata=bool(proforma["ritenuta_applicata"]),
        ritenuta_pct=proforma["ritenuta_pct"],
        note=f"Da preventivo n. {proforma['numero_visualizzato']}.",
        formato_numerazione=studio.get("formato_numerazione") or "{n}/{anno}",
        proforma_origine_id=pid,
    )
    with conn:
        conn.execute("UPDATE proforme SET stato='convertita', fattura_generata_id=? WHERE id=?",
                     (esito["id"], pid))
    return esito
