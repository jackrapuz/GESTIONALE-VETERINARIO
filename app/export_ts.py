"""Estrazione per il Sistema Tessera Sanitaria (spese veterinarie).

Filtra i documenti per **data di pagamento** (logica di cassa del Sistema TS),
costruisce i record tramite il layout isolato in :mod:`app.tracciato_ts`, valida
e produce due output: il file CSV dei record conformi e un report degli scarti.

Il formato dei campi NON e' definito qui: vive in ``tracciato_ts.py`` cosi' da
poter essere aggiornato quando cambiano le specifiche ufficiali.
"""
from __future__ import annotations

import csv
import io

from app import tracciato_ts


def _record_da_fattura(f: dict) -> dict:
    """Record grezzo (chiavi neutre) che il tracciato sa formattare."""
    return {
        "cf_proprietario": (f["cli_codice_fiscale"] or "").strip(),
        "numero_documento": f["numero_visualizzato"],
        "data_emissione": f["data_emissione"],
        "data_pagamento": f["data_pagamento"],
        "tipo_spesa": "SV",
        "importo": f["totale_documento"],
        "pagamento_tracciato": bool(int(f["pagamento_tracciato"] or 0)),
        "opposizione": bool(int(f["opposizione_ts"] or 0)),
    }


def estrai_documenti(conn, dal: str, al: str) -> list[dict]:
    """Fatture (non annullate) con DATA DI PAGAMENTO nell'intervallo [dal, al].

    Le note di credito e le fatture senza data di pagamento sono escluse: la
    trasmissione TS segue la cassa (documenti effettivamente incassati).
    """
    righe = conn.execute(
        "SELECT * FROM fatture "
        "WHERE tipo_documento='fattura' AND stato != 'annullata' "
        "AND data_pagamento != '' AND data_pagamento BETWEEN ? AND ? "
        "ORDER BY data_pagamento, numero_progressivo",
        (dal, al),
    ).fetchall()
    return [dict(r) for r in righe]


def genera_export(conn, dal: str, al: str) -> dict:
    """Genera CSV conformi + report scarti per il periodo indicato.

    Ritorna dict con: ``csv`` (bytes), ``scarti_csv`` (bytes), ``n_ok``,
    ``n_scarti``, ``scarti`` (lista di (numero, motivi)).
    """
    documenti = estrai_documenti(conn, dal, al)

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=tracciato_ts.SEPARATORE, lineterminator="\r\n")
    w.writerow(tracciato_ts.intestazione())

    scarti_buf = io.StringIO()
    ws = csv.writer(scarti_buf, delimiter=";", lineterminator="\r\n")
    ws.writerow(["numero_documento", "data_pagamento", "motivi_scarto"])

    n_ok = 0
    scarti: list[tuple[str, list[str]]] = []
    for f in documenti:
        record = _record_da_fattura(f)
        errori = tracciato_ts.valida_record(record)
        if errori:
            scarti.append((f["numero_visualizzato"], errori))
            ws.writerow([f["numero_visualizzato"], f["data_pagamento"], " | ".join(errori)])
        else:
            w.writerow(tracciato_ts.costruisci_riga(record))
            n_ok += 1

    return {
        "csv": buf.getvalue().encode("utf-8"),
        "scarti_csv": scarti_buf.getvalue().encode("utf-8"),
        "n_ok": n_ok,
        "n_scarti": len(scarti),
        "scarti": scarti,
        "versione": tracciato_ts.VERSIONE_TRACCIATO,
    }
