"""Registro delle prestazioni eseguite: livello di servizio.

Francesca annota il lavoro *appena lo fa* (data + cliente + cavallo + prestazione
+ prezzo), senza pensare alle fatture. Ogni voce e' "da fatturare" finche' non
viene inglobata in un documento: l'insieme delle voci non fatturate di un cliente
e' la sua "bozza" implicita.

- Clienti con ``fatturazione_mensile``: si accumula durante il mese e si emette un
  unico documento a fine mese, raggruppato per cavallo.
- Clienti una-tantum: si annota e si fattura subito.

La generazione **riusa** :func:`app.fatturazione.emetti_fattura` (nessuna
duplicazione della logica fiscale) e marca le voci come fatturate **dentro la
stessa transazione** tramite il callback ``dopo_inserimento``: cosi' non puo'
nascere una fattura con le voci ancora "da fatturare".
"""
from __future__ import annotations

import sqlite3
from datetime import date

from app.calcolo import RigaInput, dec, q2
from app.fatturazione import denominazione_cliente, emetti_fattura
from app.proforma import emetti_proforma

# Colonne della voce di registro scritte in fase di annotazione (id/created_at/
# fattura_id/proforma_id esclusi: li gestisce il sistema).
_COLONNE = [
    "data_prestazione", "cliente_id", "paziente_id", "prestazione_id",
    "descrizione", "quantita", "prezzo_unitario", "sconto_riga_pct",
    "aliquota_iva", "tipo_spesa_ts", "note",
]


def _importo_voce(v: dict | sqlite3.Row, sconto_cliente_pct="0") -> str:
    """Importo praticato della voce: quantita x prezzo, meno sconto riga e cliente.

    Deve seguire lo stesso ordine di :func:`app.calcolo.calcola_fattura` (prima lo
    sconto di riga, poi quello del cliente, arrotondando a fine riga): e' l'importo
    che finira' in fattura, e a schermo non puo' dire un numero diverso.
    """
    lordo = dec(v["quantita"]) * dec(v["prezzo_unitario"])
    dopo_riga = lordo * (dec("1") - dec(v["sconto_riga_pct"]) / dec("100"))
    dopo_cliente = dopo_riga * (dec("1") - dec(sconto_cliente_pct) / dec("100"))
    return str(q2(dopo_cliente))


def annota(
    conn: sqlite3.Connection,
    *,
    data_prestazione: str,
    cliente_id: int,
    paziente_id: int | None = None,
    prestazione_id: int | None = None,
    descrizione: str = "",
    quantita: str = "1",
    prezzo_unitario: str = "0.00",
    sconto_riga_pct: str = "0.00",
    aliquota_iva: str = "22.00",
    tipo_spesa_ts: str = "SV",
    note: str = "",
) -> int:
    """Registra una prestazione eseguita (``fattura_id`` NULL = da fatturare)."""
    valori = {
        "data_prestazione": data_prestazione or date.today().isoformat(),
        "cliente_id": cliente_id,
        "paziente_id": paziente_id,
        "prestazione_id": prestazione_id,
        "descrizione": descrizione,
        "quantita": str(quantita or "1"),
        "prezzo_unitario": str(prezzo_unitario or "0.00"),
        "sconto_riga_pct": str(sconto_riga_pct or "0.00"),
        "aliquota_iva": str(aliquota_iva or "22.00"),
        "tipo_spesa_ts": tipo_spesa_ts or "SV",
        "note": note,
    }
    ph = ", ".join("?" for _ in _COLONNE)
    with conn:
        cur = conn.execute(
            f"INSERT INTO prestazioni_eseguite ({', '.join(_COLONNE)}) VALUES ({ph})",
            [valori[c] for c in _COLONNE],
        )
    return int(cur.lastrowid)


def elimina_voce(conn: sqlite3.Connection, voce_id: int) -> None:
    """Cancella una voce del registro, se non e' ancora finita in una fattura.

    Annotare e' un gesto veloce fatto in stalla, quindi si sbaglia: senza questa
    via d'uscita l'unico rimedio era fatturare l'errore e poi stornarlo con una
    nota di credito.

    Il limite e' ``fattura_id``: una volta che la voce e' dentro un documento
    fiscale non si tocca piu' (la fattura non cambia, si storna). Essere legata a
    una **proforma** invece non blocca nulla: la proforma non e' fiscale e resta
    valida come documento gia' consegnato.
    """
    riga = conn.execute(
        "SELECT fattura_id FROM prestazioni_eseguite WHERE id=?", (voce_id,)
    ).fetchone()
    if riga is None:
        raise ValueError("Prestazione non trovata.")
    if riga["fattura_id"] is not None:
        raise ValueError(
            "Questa prestazione e' gia' in una fattura: per correggerla serve una "
            "nota di credito.")
    with conn:
        conn.execute("DELETE FROM prestazioni_eseguite WHERE id=?", (voce_id,))


def _voci_cliente(conn: sqlite3.Connection, cliente_id: int) -> list[dict]:
    """Voci ancora da fatturare di un cliente (con nome cavallo corrente)."""
    righe = conn.execute(
        "SELECT pe.*, pa.nome AS paziente_nome_corrente "
        "FROM prestazioni_eseguite pe "
        "LEFT JOIN pazienti pa ON pa.id = pe.paziente_id "
        "WHERE pe.cliente_id=? AND pe.fattura_id IS NULL "
        "ORDER BY pa.nome, pe.data_prestazione, pe.id",
        (cliente_id,),
    ).fetchall()
    return [dict(r) for r in righe]


def da_fatturare(conn: sqlite3.Connection) -> list[dict]:
    """Voci non ancora fatturate, raggruppate per cliente.

    Ogni gruppo riporta denominazione, se il cliente e' a fatturazione mensile,
    il totale praticato e l'elenco delle voci (con importo di riga gia' calcolato
    per la visualizzazione).
    """
    clienti = conn.execute(
        "SELECT DISTINCT c.id, c.tipo, c.nome, c.cognome, c.ragione_sociale, "
        "c.fatturazione_mensile, c.sconto_default_pct "
        "FROM clienti c JOIN prestazioni_eseguite pe ON pe.cliente_id = c.id "
        "WHERE pe.fattura_id IS NULL "
        "ORDER BY c.fatturazione_mensile DESC, c.cognome, c.ragione_sociale, c.nome",
    ).fetchall()

    gruppi: list[dict] = []
    for c in clienti:
        c = dict(c)
        sconto = c.get("sconto_default_pct") or "0"
        voci = _voci_cliente(conn, c["id"])
        totale = q2(sum((dec(_importo_voce(v, sconto)) for v in voci), dec("0")))
        for v in voci:
            v["importo"] = _importo_voce(v, sconto)
        gruppi.append({
            "cliente_id": c["id"],
            "denominazione": denominazione_cliente(c),
            "fatturazione_mensile": bool(c["fatturazione_mensile"]),
            "totale": str(totale),
            "voci": voci,
        })
    return gruppi


def _righe_da_voci(voci: list[dict]) -> list[RigaInput]:
    """Costruisce le RigaInput dalle voci del registro (snapshot nome cavallo)."""
    return [
        RigaInput(
            descrizione=v["descrizione"] or "Prestazione",
            quantita=dec(v["quantita"]) or dec("1"),
            prezzo_unitario=dec(v["prezzo_unitario"]),
            aliquota_iva=dec(v["aliquota_iva"]) or dec("22"),
            sconto_riga_pct=dec(v["sconto_riga_pct"]),
            tipo_spesa_ts=v["tipo_spesa_ts"] or "SV",
            prestazione_id=v["prestazione_id"],
            paziente_id=v["paziente_id"],
            paziente_nome=v.get("paziente_nome_corrente") or "",
            data_prestazione=v["data_prestazione"],
        )
        for v in voci
    ]


def genera_fattura(
    conn: sqlite3.Connection, cliente_id: int, studio: dict, *,
    ids: list[int] | None = None,
) -> dict:
    """Emette una fattura dalle voci non fatturate del cliente e le marca fatturate.

    Lo snapshot del cliente (indirizzo, denominazione) e' preso **adesso**, non
    all'annotazione: se il cliente cambia indirizzo a meta' mese, la fattura
    riporta quello corretto. La marcatura delle voci avviene dentro la stessa
    transazione dell'emissione (callback ``dopo_inserimento``).
    """
    cliente = conn.execute("SELECT * FROM clienti WHERE id=?", (cliente_id,)).fetchone()
    if cliente is None:
        raise ValueError("Cliente non trovato.")
    voci = _voci_cliente(conn, cliente_id)
    if ids is not None:
        scelti = {int(i) for i in ids}
        voci = [v for v in voci if v["id"] in scelti]
    if not voci:
        raise ValueError("Nessuna prestazione da fatturare per questo cliente.")

    righe = _righe_da_voci(voci)
    voci_ids = [v["id"] for v in voci]

    def marca(conn: sqlite3.Connection, fattura_id: int) -> None:
        conn.executemany(
            "UPDATE prestazioni_eseguite SET fattura_id=? WHERE id=?",
            [(fattura_id, i) for i in voci_ids],
        )

    return emetti_fattura(
        conn,
        cliente=dict(cliente),
        righe=righe,
        data_emissione=date.today().isoformat(),
        # Il registro annota il prezzo di LISTINO: lo sconto concordato col cliente
        # va tolto qui, come fa gia' la fattura compilata a mano. Senza, lo stesso
        # cliente pagherebbe di piu' a seconda della strada usata per fatturarlo.
        sconto_cliente_pct=cliente["sconto_default_pct"] or "0",
        enpav_pct=studio.get("enpav_pct") or "2",
        opposizione_ts=bool(cliente["opposizione_ts_default"]),
        formato_numerazione=studio.get("formato_numerazione") or "{n}/{anno}",
        dopo_inserimento=marca,
    )


def genera_proforma(
    conn: sqlite3.Connection, cliente_id: int, studio: dict, *,
    ids: list[int] | None = None,
) -> dict:
    """Emette una proforma (riepilogo del mese) dalle voci non fatturate.

    La proforma e' non fiscale: NON consuma le voci, che restano "da fatturare"
    fino alla fattura vera. Marca solo ``proforma_id`` per tracciabilita'.
    """
    cliente = conn.execute("SELECT * FROM clienti WHERE id=?", (cliente_id,)).fetchone()
    if cliente is None:
        raise ValueError("Cliente non trovato.")
    voci = _voci_cliente(conn, cliente_id)
    if ids is not None:
        scelti = {int(i) for i in ids}
        voci = [v for v in voci if v["id"] in scelti]
    if not voci:
        raise ValueError("Nessuna prestazione da fatturare per questo cliente.")

    voci_ids = [v["id"] for v in voci]

    def collega(conn: sqlite3.Connection, proforma_id: int) -> None:
        conn.executemany(
            "UPDATE prestazioni_eseguite SET proforma_id=? WHERE id=?",
            [(proforma_id, i) for i in voci_ids],
        )

    return emetti_proforma(
        conn,
        cliente=dict(cliente),
        righe=_righe_da_voci(voci),
        data_emissione=date.today().isoformat(),
        sconto_cliente_pct=cliente["sconto_default_pct"] or "0",
        enpav_pct=studio.get("enpav_pct") or "2",
        # Dentro la transazione, come per la fattura: una proforma non puo'
        # restare scollegata dalle voci che la compongono.
        dopo_inserimento=collega,
    )
