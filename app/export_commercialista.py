"""Esportazioni per il commercialista.

- Registro delle fatture emesse nel periodo (per DATA DI EMISSIONE), in CSV e in
  Excel, con tutte le colonne fiscali e un riepilogo IVA per aliquota.
- Bundle ZIP con le copie PDF delle fatture del periodo.

Le note di credito compaiono con importi di segno negativo, cosi' il riepilogo
IVA rappresenta l'imposta netta del periodo.
"""
from __future__ import annotations

import csv
import io
import zipfile
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Font

from app.fatturazione import gruppi_iva_da_righe, leggi_fattura
from app.pdf_fattura import genera_pdf_fattura

COLONNE = [
    "Numero", "Data", "Tipo", "Cliente", "CF", "P.IVA", "Imponibile",
    "Contributo ENPAV", "Aliquote IVA", "IVA", "Totale", "Ritenuta", "Stato",
]


def _segno(tipo: str) -> Decimal:
    return Decimal("-1") if tipo == "nota_credito" else Decimal("1")


def _documenti(conn, dal: str, al: str) -> list[dict]:
    righe = conn.execute(
        "SELECT * FROM fatture "
        "WHERE stato != 'annullata' AND data_emissione BETWEEN ? AND ? "
        "ORDER BY data_emissione, tipo_documento, numero_progressivo",
        (dal, al),
    ).fetchall()
    return [dict(r) for r in righe]


def registro(conn, dal: str, al: str) -> list[list]:
    """Righe del registro (liste allineate a COLONNE), con segno per le note credito."""
    out: list[list] = []
    for f in _documenti(conn, dal, al):
        f["righe"] = leggi_fattura(conn, f["id"])["righe"]
        gruppi = gruppi_iva_da_righe(f["righe"], f["enpav_pct"])
        aliquote = ";".join(sorted({g["aliquota"].rstrip("0").rstrip(".") for g in gruppi}))
        s = _segno(f["tipo_documento"])
        out.append([
            f["numero_visualizzato"],
            f["data_emissione"],
            "Nota credito" if f["tipo_documento"] == "nota_credito" else "Fattura",
            f["cli_denominazione"],
            f["cli_codice_fiscale"],
            f["cli_partita_iva"],
            str(s * Decimal(f["imponibile"])),
            str(s * Decimal(f["contributo_enpav"])),
            aliquote,
            str(s * Decimal(f["iva_totale"])),
            str(s * Decimal(f["totale_documento"])),
            str(s * Decimal(f["ritenuta_importo"])),
            f["stato"],
        ])
    return out


def riepilogo_iva(conn, dal: str, al: str) -> list[dict]:
    """Aggrega imponibile/ENPAV/base/IVA per aliquota nel periodo (segno incluso)."""
    acc: dict[str, dict[str, Decimal]] = {}
    for f in _documenti(conn, dal, al):
        righe = leggi_fattura(conn, f["id"])["righe"]
        s = _segno(f["tipo_documento"])
        for g in gruppi_iva_da_righe(righe, f["enpav_pct"]):
            k = g["aliquota"].rstrip("0").rstrip(".")
            a = acc.setdefault(k, {"imponibile": Decimal("0"), "enpav": Decimal("0"),
                                   "base_iva": Decimal("0"), "iva": Decimal("0")})
            a["imponibile"] += s * Decimal(g["imponibile"])
            a["enpav"] += s * Decimal(g["enpav"])
            a["base_iva"] += s * Decimal(g["base_iva"])
            a["iva"] += s * Decimal(g["iva"])
    return [
        {"aliquota": k, "imponibile": str(v["imponibile"]), "enpav": str(v["enpav"]),
         "base_iva": str(v["base_iva"]), "iva": str(v["iva"])}
        for k, v in sorted(acc.items())
    ]


def genera_csv(conn, dal: str, al: str) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(COLONNE)
    for r in registro(conn, dal, al):
        w.writerow(r)
    w.writerow([])
    w.writerow(["Riepilogo IVA per aliquota"])
    w.writerow(["Aliquota %", "Imponibile", "ENPAV", "Base IVA", "IVA"])
    for g in riepilogo_iva(conn, dal, al):
        w.writerow([g["aliquota"], g["imponibile"], g["enpav"], g["base_iva"], g["iva"]])
    # BOM utf-8 per apertura corretta in Excel italiano.
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def genera_xlsx(conn, dal: str, al: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Registro"
    ws.append(COLONNE)
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in registro(conn, dal, al):
        ws.append(r)

    ws2 = wb.create_sheet("Riepilogo IVA")
    ws2.append(["Aliquota %", "Imponibile", "ENPAV", "Base IVA", "IVA"])
    for c in ws2[1]:
        c.font = Font(bold=True)
    for g in riepilogo_iva(conn, dal, al):
        ws2.append([g["aliquota"], float(g["imponibile"]), float(g["enpav"]),
                    float(g["base_iva"]), float(g["iva"])])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def genera_zip_pdf(conn, dal: str, al: str, studio: dict) -> bytes:
    """ZIP con le copie PDF delle fatture (non note di credito) del periodo."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in _documenti(conn, dal, al):
            fattura = leggi_fattura(conn, f["id"])
            gruppi = gruppi_iva_da_righe(fattura["righe"], fattura["enpav_pct"])
            pdf = genera_pdf_fattura(fattura, studio, gruppi)
            nome = f"{f['tipo_documento']}_{f['numero_visualizzato'].replace('/', '-')}.pdf"
            z.writestr(nome, pdf)
    return buf.getvalue()
