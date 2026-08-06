"""Estrazione per il Sistema Tessera Sanitaria (spese veterinarie).

Filtra i documenti per **data di pagamento** (il Sistema TS segue la cassa),
costruisce la fornitura con il modello di :mod:`app.tracciato_ts`, valida e
divide l'esito in tre, non in due:

- **trasmissibili**: pronti per l'invio;
- **esclusi**: fuori dall'ambito della norma, non e' un errore. Le spese
  veterinarie detraibili sono quelle "sostenute dalle persone fisiche" (Allegato
  A, par. 2.6.1): una fattura a un allevamento o a una scuderia con partita IVA
  non ci rientra. Chiamarle "scarti" le farebbe sembrare da correggere, e in uno
  studio equino sarebbero tante;
- **scarti**: documenti che dovrebbero andare ma hanno dati mancanti o incoerenti.
  Questi si correggono.

Il file XML da caricare sul portale **non e' ancora generabile**: vedi
``ts_xml.py``. Qui si produce un'anteprima leggibile in CSV, utile per
controllare i dati prima dell'invio, che non e' e non deve sembrare il file da
caricare.
"""
from __future__ import annotations

import csv
import io

from app import tracciato_ts
from app.calcolo import dec
from app.fatturazione import gruppi_iva_da_righe, leggi_fattura
from app.validazioni import is_codice_fiscale


def estrai_documenti(conn, dal: str, al: str) -> list[dict]:
    """Fatture (non annullate) con DATA DI PAGAMENTO nell'intervallo [dal, al].

    Le note di credito e le fatture non ancora pagate restano fuori: la
    trasmissione segue la cassa, cioe' quanto l'assistito ha effettivamente
    speso nel periodo.
    """
    righe = conn.execute(
        "SELECT * FROM fatture "
        "WHERE tipo_documento='fattura' AND stato != 'annullata' "
        "AND data_pagamento != '' AND data_pagamento BETWEEN ? AND ? "
        "ORDER BY data_pagamento, numero_progressivo",
        (dal, al),
    ).fetchall()
    return [dict(r) for r in righe]


def _fuori_ambito(f: dict) -> str | None:
    """Motivo per cui il documento non va trasmesso, o None se va trasmesso.

    Con opposizione si trasmette comunque (senza codice fiscale): e' una scelta
    esplicita fatta sul cliente, non un dato mancante.
    """
    if int(f["opposizione_ts"] or 0):
        return None
    cf = (f["cli_codice_fiscale"] or "").strip()
    if is_codice_fiscale(cf):
        return None
    if (f["cli_partita_iva"] or "").strip():
        return ("Cliente con partita IVA e senza codice fiscale personale: la "
                "detrazione delle spese veterinarie riguarda le persone fisiche.")
    return None   # nessun CF e nessuna P.IVA: e' un dato mancante, non un'esclusione


def genera_export(conn, dal: str, al: str, studio: dict) -> dict:
    """Fornitura, esclusi, scarti e anteprima CSV per il periodo indicato."""
    documenti: list[tracciato_ts.DocumentoFiscale] = []
    esclusi: list[tuple[str, str]] = []
    scarti: list[tuple[str, list[str]]] = []

    for f in estrai_documenti(conn, dal, al):
        motivo = _fuori_ambito(f)
        if motivo:
            esclusi.append((f["numero_visualizzato"], motivo))
            continue
        f["righe"] = leggi_fattura(conn, f["id"])["righe"]
        gruppi = gruppi_iva_da_righe(f["righe"], f["enpav_pct"])
        doc = tracciato_ts.costruisci_documento(studio, f, gruppi)
        errori = tracciato_ts.valida_documento(doc, dec(f["totale_documento"]))
        if errori:
            scarti.append((f["numero_visualizzato"], errori))
        else:
            documenti.append(doc)

    fornitura = tracciato_ts.Fornitura(
        cf_professionista=(studio.get("codice_fiscale") or "").strip(),
        documenti=tuple(documenti),
    )
    return {
        "fornitura": fornitura,
        "anteprima_csv": anteprima_csv(fornitura),
        "n_ok": len(documenti),
        "n_esclusi": len(esclusi),
        "n_scarti": len(scarti),
        "esclusi": esclusi,
        "scarti": scarti,
    }


# --- Anteprima leggibile ---------------------------------------------------
INTESTAZIONE_ANTEPRIMA = [
    "documento", "data_emissione", "data_pagamento", "codice_fiscale",
    "opposizione", "pagamento_tracciato", "tipo_spesa", "importo", "aliquota",
]


def anteprima_csv(fornitura: tracciato_ts.Fornitura) -> bytes:
    """CSV di controllo: **una riga per voce di spesa**, non per documento.

    Serve a rileggere prima dell'invio quello che verra' trasmesso, con lo stesso
    dettaglio del file vero. Non e' il file da caricare sul portale — quello e'
    un XML compresso e con i codici fiscali cifrati (vedi ``ts_xml.py``).

    Contiene codici fiscali in chiaro: e' un file da tenere sul computer.
    """
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(INTESTAZIONE_ANTEPRIMA)
    for d in fornitura.documenti:
        for v in d.voci:
            w.writerow([
                d.numero_visualizzato,
                d.id_spesa.data_emissione,
                d.data_pagamento,
                d.cf_assistito,
                tracciato_ts.FLAG_SI if d.opposizione else tracciato_ts.FLAG_NO,
                tracciato_ts.FLAG_SI if d.pagamento_tracciato else tracciato_ts.FLAG_NO,
                v.tipo_spesa,
                tracciato_ts.importo_ts(v.importo),
                str(v.aliquota),
            ])
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def report_problemi_csv(esito: dict) -> bytes:
    """Esclusi e scarti in un unico foglio, con la distinzione ben visibile."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(["documento", "esito", "motivo"])
    for numero, motivo in esito["esclusi"]:
        w.writerow([numero, "escluso (non va trasmesso)", motivo])
    for numero, motivi in esito["scarti"]:
        w.writerow([numero, "da correggere", " | ".join(motivi)])
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")
