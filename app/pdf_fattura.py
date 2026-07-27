"""Generazione della fattura in PDF (ReportLab, pure-Python).

Layout professionale: intestazione studio, dati cliente, tabella righe e
riepilogo con contributo ENPAV come voce separata, IVA per aliquota, totale ed
eventuale netto a pagare. In presenza di opposizione al Sistema TS viene stampata
la dicitura prevista.

ReportLab e' scelto perche' pure-Python: nessuna dipendenza nativa, quindi il
packaging in .exe (PyInstaller) resta pulito.
"""
from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from app.templating import data_it, euro

_ACCENTO = colors.HexColor("#2563eb")
_GRIGIO = colors.HexColor("#64748b")
_BORDO = colors.HexColor("#d7dce3")


def _stili():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("Studio", parent=ss["Normal"], fontSize=9, leading=12, textColor=_GRIGIO))
    ss.add(ParagraphStyle("StudioNome", parent=ss["Normal"], fontSize=14, leading=17,
                          textColor=colors.HexColor("#1f2933"), spaceAfter=2))
    ss.add(ParagraphStyle("TitoloDoc", parent=ss["Normal"], fontSize=16, leading=19,
                          textColor=_ACCENTO, spaceBefore=6, spaceAfter=2))
    ss.add(ParagraphStyle("Etichetta", parent=ss["Normal"], fontSize=8, leading=10,
                          textColor=_GRIGIO, spaceAfter=1))
    ss.add(ParagraphStyle("Corpo", parent=ss["Normal"], fontSize=9.5, leading=13))
    ss.add(ParagraphStyle("Piccolo", parent=ss["Normal"], fontSize=8, leading=11, textColor=_GRIGIO))
    ss.add(ParagraphStyle("Dicitura", parent=ss["Normal"], fontSize=8.5, leading=12,
                          textColor=colors.HexColor("#92400e"),
                          backColor=colors.HexColor("#fffbeb"),
                          borderColor=colors.HexColor("#fde68a"), borderWidth=0.5,
                          borderPadding=6, spaceBefore=8))
    return ss


def _intestazione_studio(studio: dict, ss) -> list:
    nome = studio.get("denominazione") or f"{studio.get('nome','')} {studio.get('cognome','')}".strip()
    righe = [Paragraph(nome or "Studio Veterinario", ss["StudioNome"])]
    ind = ", ".join(p for p in [
        studio.get("via", ""),
        " ".join(x for x in [studio.get("cap", ""), studio.get("citta", "")] if x)
        + (f" ({studio['prov']})" if studio.get("prov") else ""),
    ] if p and p.strip())
    dati = []
    if ind:
        dati.append(ind)
    fisc = []
    if studio.get("partita_iva"):
        fisc.append(f"P.IVA {studio['partita_iva']}")
    if studio.get("codice_fiscale"):
        fisc.append(f"C.F. {studio['codice_fiscale']}")
    if fisc:
        dati.append(" · ".join(fisc))
    contatti = [x for x in [studio.get("email", ""), studio.get("telefono", "")] if x]
    if contatti:
        dati.append(" · ".join(contatti))
    if studio.get("n_iscrizione_albo"):
        dati.append(f"Iscr. Albo n. {studio['n_iscrizione_albo']}")
    if studio.get("iban"):
        dati.append(f"IBAN {studio['iban']}")
    for d in dati:
        righe.append(Paragraph(d, ss["Studio"]))
    return righe


def _blocco_cliente(f: dict, ss) -> Table:
    tipo = "NOTA DI CREDITO" if f["tipo_documento"] == "nota_credito" else "FATTURA"
    sinistra = [
        Paragraph("Cliente", ss["Etichetta"]),
        Paragraph(f["cli_denominazione"] or "—", ss["Corpo"]),
    ]
    if f.get("cli_indirizzo"):
        sinistra.append(Paragraph(f["cli_indirizzo"], ss["Piccolo"]))
    if f.get("cli_codice_fiscale"):
        sinistra.append(Paragraph(f"C.F. {f['cli_codice_fiscale']}", ss["Piccolo"]))
    if f.get("cli_partita_iva"):
        sinistra.append(Paragraph(f"P.IVA {f['cli_partita_iva']}", ss["Piccolo"]))

    destra = [
        Paragraph(tipo, ss["TitoloDoc"]),
        Paragraph(f"n. <b>{f['numero_visualizzato']}</b>", ss["Corpo"]),
        Paragraph(f"del {data_it(f['data_emissione'])}", ss["Corpo"]),
    ]
    t = Table([[sinistra, destra]], colWidths=[105 * mm, 65 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _tabella_righe(f: dict, ss) -> Table:
    intest = ["Descrizione", "Q.tà", "Prezzo", "Sc.%", "IVA%", "Imponibile"]
    dati = [intest]
    for r in f["righe"]:
        dati.append([
            Paragraph(r["descrizione"], ss["Corpo"]),
            euro(r["quantita"]) if "." in str(r["quantita"]) else str(r["quantita"]),
            euro(r["prezzo_unitario"]),
            str(r["sconto_riga_pct"]).rstrip("0").rstrip(".") if "." in str(r["sconto_riga_pct"]) else str(r["sconto_riga_pct"]),
            str(r["aliquota_iva"]).rstrip("0").rstrip(".") if "." in str(r["aliquota_iva"]) else str(r["aliquota_iva"]),
            euro(r["imponibile_riga"]),
        ])
    t = Table(dati, colWidths=[80 * mm, 15 * mm, 25 * mm, 14 * mm, 14 * mm, 22 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef1f5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), _GRIGIO),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, _BORDO),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, _BORDO),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _tabella_riepilogo(f: dict, gruppi: list[dict], ss) -> Table:
    righe = []
    for g in gruppi:
        righe.append([f"Imponibile (IVA {_pulisci(g['aliquota'])}%)", euro(g["imponibile"])])
        righe.append([f"Contributo integrativo ENPAV {_pulisci(f['enpav_pct'])}%", euro(g["enpav"])])
        righe.append([f"Base imponibile IVA {_pulisci(g['aliquota'])}%", euro(g["base_iva"])])
        righe.append([f"IVA {_pulisci(g['aliquota'])}%", euro(g["iva"])])
    righe.append(["Totale documento", euro(f["totale_documento"])])
    if int(f.get("ritenuta_applicata") or 0):
        righe.append([f"Ritenuta d'acconto {_pulisci(f['ritenuta_pct'])}%", "-" + euro(f["ritenuta_importo"])])
        righe.append(["Netto a pagare", euro(f["netto_a_pagare"])])

    idx_tot = next(i for i, r in enumerate(righe) if r[0] == "Totale documento")
    t = Table([[Paragraph(a, ss["Corpo"]), b] for a, b in righe], colWidths=[55 * mm, 30 * mm])
    stile = [
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEABOVE", (0, idx_tot), (-1, idx_tot), 0.8, _GRIGIO),
        ("FONTNAME", (0, idx_tot), (-1, idx_tot), "Helvetica-Bold"),
        ("FONTSIZE", (0, idx_tot), (-1, idx_tot), 11),
    ]
    if int(f.get("ritenuta_applicata") or 0):
        stile.append(("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"))
        stile.append(("LINEABOVE", (0, -1), (-1, -1), 0.4, _BORDO))
    t.setStyle(TableStyle(stile))
    return t


def _pulisci(v) -> str:
    s = str(v)
    return s.rstrip("0").rstrip(".") if "." in s else s


def genera_pdf_fattura(f: dict, studio: dict, gruppi: list[dict]) -> bytes:
    """Restituisce i byte del PDF della fattura ``f`` (dict con chiave 'righe')."""
    ss = _stili()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=20 * mm, rightMargin=20 * mm,
        title=f["numero_visualizzato"],
    )
    story: list = []
    story += _intestazione_studio(studio, ss)
    story.append(Spacer(1, 8 * mm))
    story.append(_blocco_cliente(f, ss))
    story.append(Spacer(1, 6 * mm))
    story.append(_tabella_righe(f, ss))
    story.append(Spacer(1, 5 * mm))

    # Riepilogo allineato a destra.
    riep = _tabella_riepilogo(f, gruppi, ss)
    contenitore = Table([[ "", riep]], colWidths=[85 * mm, 85 * mm])
    contenitore.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                     ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                     ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(contenitore)

    # Pagamento.
    pag = []
    if f.get("modalita_pagamento"):
        tracc = "tracciato" if int(f.get("pagamento_tracciato") or 0) else "non tracciato"
        pag.append(f"Pagamento: {f['modalita_pagamento']} ({tracc}).")
    if f.get("data_pagamento"):
        pag.append(f"Data incasso: {data_it(f['data_pagamento'])}.")
    if pag:
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(" ".join(pag), ss["Piccolo"]))

    if int(f.get("opposizione_ts") or 0):
        story.append(Paragraph(
            studio.get("testo_dicitura_opposizione_ts")
            or "Il cliente si oppone alla trasmissione dei dati al Sistema Tessera Sanitaria.",
            ss["Dicitura"]))

    if f.get("note"):
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(f"<b>Note:</b> {f['note']}", ss["Piccolo"]))

    # Nota fiscale: prestazioni sanitarie -> fattura non elettronica.
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        "Documento non soggetto a fatturazione elettronica via SdI (prestazioni "
        "sanitarie i cui dati confluiscono nel Sistema Tessera Sanitaria).",
        ss["Piccolo"]))

    doc.build(story)
    return buf.getvalue()
