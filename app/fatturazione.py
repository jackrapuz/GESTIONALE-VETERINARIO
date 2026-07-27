"""Emissione fattura: livello di servizio (indipendente dal web).

Qui vive l'unica operazione che *emette* un documento fiscale: calcola i totali,
riserva il numero progressivo e scrive fattura + righe **in un'unica transazione
atomica**. Se qualcosa fallisce, si annulla tutto (rollback) e non resta alcun
numero "bruciato": la numerazione non presenta buchi.

Tenerlo separato dai router lo rende testabile con un DB temporaneo, senza dover
avviare il server web (vedi ``tests/test_fatture.py``).
"""
from __future__ import annotations

import sqlite3

from app.calcolo import RigaInput, RisultatoFattura, calcola_fattura
from app.numerazione import formatta_numero, prossimo_numero


def leggi_fattura(conn: sqlite3.Connection, fid: int) -> dict | None:
    """Legge una fattura con le sue righe (ordinate). ``None`` se inesistente."""
    row = conn.execute("SELECT * FROM fatture WHERE id=?", (fid,)).fetchone()
    if row is None:
        return None
    fattura = dict(row)
    fattura["righe"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM righe_fattura WHERE fattura_id=? ORDER BY ordine, id", (fid,)
        ).fetchall()
    ]
    return fattura


def gruppi_iva_da_righe(righe: list[dict], enpav_pct) -> list[dict]:
    """Ricostruisce la ripartizione IVA per aliquota dai dati salvati.

    Usato per stampa/dettaglio/export: ripercorre il calcolo partendo dagli
    imponibili di riga gia' memorizzati, cosi' i totali combaciano con quelli
    salvati sulla fattura.
    """
    inp = [
        RigaInput(
            descrizione=r["descrizione"], quantita=1,
            prezzo_unitario=r["imponibile_riga"], aliquota_iva=r["aliquota_iva"],
            tipo_spesa_ts=r["tipo_spesa_ts"],
        )
        for r in righe
    ]
    ris = calcola_fattura(inp, enpav_pct=enpav_pct)
    return [
        {"aliquota": str(g.aliquota), "imponibile": str(g.imponibile),
         "enpav": str(g.enpav), "base_iva": str(g.base_iva), "iva": str(g.iva)}
        for g in ris.gruppi_iva
    ]


def denominazione_cliente(cli: dict | sqlite3.Row) -> str:
    """Nome da mostrare/salvare: ragione sociale (giuridica) o 'Cognome Nome'."""
    cli = dict(cli)
    if cli.get("tipo") == "giuridica":
        return (cli.get("ragione_sociale") or "").strip()
    return f"{cli.get('cognome', '')} {cli.get('nome', '')}".strip()


def indirizzo_cliente(cli: dict | sqlite3.Row) -> str:
    """Indirizzo su una riga: 'Via Roma 1, 00100 Roma (RM)'. Parti vuote omesse."""
    cli = dict(cli)
    via = (cli.get("via") or "").strip()
    cap = (cli.get("cap") or "").strip()
    citta = (cli.get("citta") or "").strip()
    prov = (cli.get("provincia") or "").strip()
    localita = " ".join(p for p in (cap, citta) if p)
    if prov:
        localita = f"{localita} ({prov})".strip()
    return ", ".join(p for p in (via, localita) if p)


# Colonne della tabella ``fatture`` scritte in fase di emissione (id/created_at esclusi).
_COLONNE_FATTURA = [
    "tipo_documento", "anno", "numero_progressivo", "numero_visualizzato",
    "data_emissione", "cliente_id",
    "cli_denominazione", "cli_codice_fiscale", "cli_partita_iva", "cli_indirizzo",
    "modalita_pagamento", "pagamento_tracciato", "data_pagamento", "stato",
    "opposizione_ts", "ritenuta_applicata", "ritenuta_pct", "enpav_pct",
    "imponibile", "contributo_enpav", "base_iva", "iva_totale", "ritenuta_importo",
    "totale_documento", "netto_a_pagare", "documento_riferimento_id", "note",
]


def emetti_fattura(
    conn: sqlite3.Connection,
    *,
    cliente: dict | sqlite3.Row,
    righe: list[RigaInput],
    data_emissione: str,
    tipo_documento: str = "fattura",
    sconto_cliente_pct="0",
    enpav_pct="2",
    ritenuta_applicata: bool = False,
    ritenuta_pct="0",
    modalita_pagamento: str = "",
    pagamento_tracciato: bool = True,
    data_pagamento: str = "",
    stato: str = "emessa",
    opposizione_ts: bool = False,
    note: str = "",
    formato_numerazione: str = "{n}/{anno}",
    documento_riferimento_id: int | None = None,
) -> dict:
    """Emette il documento e restituisce ``{id, numero, numero_visualizzato, risultato}``.

    Il calcolo (ENPAV -> base IVA -> IVA -> totale, ritenuta a parte) e' delegato
    a :func:`app.calcolo.calcola_fattura`. La numerazione e' per anno di
    ``data_emissione`` e per ``tipo_documento``.
    """
    risultato: RisultatoFattura = calcola_fattura(
        righe,
        sconto_cliente_pct=sconto_cliente_pct,
        enpav_pct=enpav_pct,
        ritenuta_applicata=ritenuta_applicata,
        ritenuta_pct=ritenuta_pct,
    )
    anno = int(str(data_emissione)[:4])
    cli = dict(cliente)

    # Transazione unica: riserva numero + inserimenti. Rollback totale su errore.
    conn.execute("BEGIN IMMEDIATE")
    try:
        numero = prossimo_numero(conn, anno, tipo_documento)
        numero_vis = formatta_numero(numero, anno, formato_numerazione)
        valori = {
            "tipo_documento": tipo_documento,
            "anno": anno,
            "numero_progressivo": numero,
            "numero_visualizzato": numero_vis,
            "data_emissione": data_emissione,
            "cliente_id": cli.get("id"),
            "cli_denominazione": denominazione_cliente(cli),
            "cli_codice_fiscale": (cli.get("codice_fiscale") or "").strip(),
            "cli_partita_iva": (cli.get("partita_iva") or "").strip(),
            "cli_indirizzo": indirizzo_cliente(cli),
            "modalita_pagamento": modalita_pagamento,
            "pagamento_tracciato": 1 if pagamento_tracciato else 0,
            "data_pagamento": data_pagamento or "",
            "stato": stato,
            "opposizione_ts": 1 if opposizione_ts else 0,
            "ritenuta_applicata": 1 if ritenuta_applicata else 0,
            "ritenuta_pct": str(ritenuta_pct),
            "enpav_pct": str(enpav_pct),
            "imponibile": str(risultato.imponibile),
            "contributo_enpav": str(risultato.contributo_enpav),
            "base_iva": str(risultato.base_iva),
            "iva_totale": str(risultato.iva_totale),
            "ritenuta_importo": str(risultato.ritenuta_importo),
            "totale_documento": str(risultato.totale_documento),
            "netto_a_pagare": str(risultato.netto_a_pagare),
            "documento_riferimento_id": documento_riferimento_id,
            "note": note,
        }
        ph = ", ".join("?" for _ in _COLONNE_FATTURA)
        cur = conn.execute(
            f"INSERT INTO fatture ({', '.join(_COLONNE_FATTURA)}) VALUES ({ph})",
            [valori[c] for c in _COLONNE_FATTURA],
        )
        fattura_id = int(cur.lastrowid)

        for ordine, rc in enumerate(risultato.righe):
            conn.execute(
                "INSERT INTO righe_fattura (fattura_id, prestazione_id, descrizione, "
                "quantita, prezzo_unitario, sconto_riga_pct, aliquota_iva, "
                "tipo_spesa_ts, imponibile_riga, ordine) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    fattura_id, rc.prestazione_id, rc.descrizione,
                    str(rc.quantita), str(rc.prezzo_unitario), str(rc.sconto_riga_pct),
                    str(rc.aliquota_iva), rc.tipo_spesa_ts, str(rc.imponibile_riga),
                    ordine,
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "id": fattura_id,
        "numero": numero,
        "numero_visualizzato": numero_vis,
        "risultato": risultato,
    }
