"""Numerazione progressiva dei documenti.

Regole (PIANO.md):
- Progressiva per anno e per tipo documento.
- Assegnata SOLO all'emissione definitiva, in transazione atomica: niente buchi,
  nessuna modifica a ritroso.
- Formato configurabile (default ``{n}/{anno}``, es. ``1/2026``).
"""
from __future__ import annotations

import sqlite3


def formatta_numero(numero: int, anno: int, formato: str = "{n}/{anno}") -> str:
    """Applica il formato al numero progressivo. Fallback sicuro se il formato e' errato."""
    try:
        return formato.format(n=numero, anno=anno)
    except (KeyError, IndexError, ValueError):
        return f"{numero}/{anno}"


def prossimo_numero(
    conn: sqlite3.Connection, anno: int, tipo_documento: str = "fattura"
) -> int:
    """Legge e incrementa il contatore, SENZA gestire la transazione.

    Va chiamata dentro una transazione di scrittura gia' aperta dal chiamante
    (vedi ``assegna_numero`` e l'emissione fattura): il commit/rollback e la
    scelta del lock restano responsabilita' del chiamante, cosi' la riserva del
    numero e l'inserimento della fattura possono essere un'unica operazione
    atomica (niente buchi se l'inserimento fallisce).
    """
    row = conn.execute(
        "SELECT ultimo_numero FROM numerazione WHERE anno=? AND tipo_documento=?",
        (anno, tipo_documento),
    ).fetchone()
    if row is None:
        prossimo = 1
        conn.execute(
            "INSERT INTO numerazione (anno, tipo_documento, ultimo_numero) VALUES (?,?,?)",
            (anno, tipo_documento, prossimo),
        )
    else:
        prossimo = int(row["ultimo_numero"]) + 1
        conn.execute(
            "UPDATE numerazione SET ultimo_numero=? WHERE anno=? AND tipo_documento=?",
            (prossimo, anno, tipo_documento),
        )
    return prossimo


def assegna_numero(
    conn: sqlite3.Connection, anno: int, tipo_documento: str = "fattura"
) -> int:
    """Riserva e restituisce il prossimo numero progressivo, in modo atomico.

    Usa ``BEGIN IMMEDIATE`` per prendere subito il lock di scrittura: due
    emissioni concorrenti non possono ottenere lo stesso numero. Fa commit da
    sola: utile quando serve solo il numero. Per emettere anche la fattura nella
    stessa transazione usare invece ``prossimo_numero`` dentro la propria
    ``BEGIN IMMEDIATE``.
    """
    # Apriamo esplicitamente una transazione di scrittura.
    conn.execute("BEGIN IMMEDIATE")
    try:
        prossimo = prossimo_numero(conn, anno, tipo_documento)
        conn.commit()
        return prossimo
    except Exception:
        conn.rollback()
        raise


def verifica_continuita(
    conn: sqlite3.Connection, anno: int, tipo_documento: str = "fattura"
) -> list[int]:
    """Restituisce i numeri mancanti nella sequenza emessa per anno/tipo.

    Confronta i ``numero_progressivo`` effettivamente presenti in ``fatture``
    (escluse le annullate) con la sequenza 1..max. Lista vuota = nessun buco.
    """
    numeri = [
        int(r["numero_progressivo"])
        for r in conn.execute(
            "SELECT numero_progressivo FROM fatture "
            "WHERE anno=? AND tipo_documento=? AND stato != 'annullata' "
            "ORDER BY numero_progressivo",
            (anno, tipo_documento),
        ).fetchall()
    ]
    if not numeri:
        return []
    presenti = set(numeri)
    return [n for n in range(1, max(numeri) + 1) if n not in presenti]
