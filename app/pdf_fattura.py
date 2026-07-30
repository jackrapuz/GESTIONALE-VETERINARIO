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
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from app import marchio
from app.templating import data_it, euro

# Stessa identita' dell'app ("Scuderia"): verde da corsa, ottone come accento,
# grigio-verde per i testi secondari. I valori sono quelli di app/static/css/stile.css.
_VERDE = colors.HexColor("#223d33")
_OTTONE = colors.HexColor("#b5822e")
_ACCENTO = _VERDE
_GRIGIO = colors.HexColor("#5e6b63")
_BORDO = colors.HexColor("#dbe2db")
_TINTA = colors.HexColor("#eef2ec")     # fondo tenue per l'intestazione della tabella
_MARCHIO = _VERDE

# Serif per il nome dello studio: e' il carattere dei titoli nell'app. Times-Roman
# e' incluso in ReportLab, quindi non aggiunge nessun file al pacchetto.
_SERIF = "Times-Roman"


def _stili():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("Studio", parent=ss["Normal"], fontSize=9, leading=12, textColor=_GRIGIO))
    ss.add(ParagraphStyle("StudioNome", parent=ss["Normal"], fontName=_SERIF,
                          fontSize=16, leading=19,
                          textColor=colors.HexColor("#16211c"), spaceAfter=3))
    ss.add(ParagraphStyle("Qualifica", parent=ss["Normal"], fontSize=7, leading=9,
                          textColor=_OTTONE, spaceAfter=3))
    ss.add(ParagraphStyle("TitoloDoc", parent=ss["Normal"], fontName=_SERIF,
                          fontSize=17, leading=20,
                          textColor=_ACCENTO, spaceBefore=4, spaceAfter=2))
    ss.add(ParagraphStyle("Etichetta", parent=ss["Normal"], fontSize=8, leading=10,
                          textColor=_GRIGIO, spaceAfter=1))
    ss.add(ParagraphStyle("Corpo", parent=ss["Normal"], fontSize=9.5, leading=13))
    ss.add(ParagraphStyle("Piccolo", parent=ss["Normal"], fontSize=8, leading=11, textColor=_GRIGIO))
    # Stessi toni d'avviso dell'app (--warn / --warn-bg in stile.css).
    ss.add(ParagraphStyle("Dicitura", parent=ss["Normal"], fontSize=8.5, leading=12,
                          textColor=colors.HexColor("#8a5f14"),
                          backColor=colors.HexColor("#fbf3e3"),
                          borderColor=colors.HexColor("#e6d3a8"), borderWidth=0.5,
                          borderPadding=6, spaceBefore=8))
    return ss


def _intestazione_studio(studio: dict, ss) -> list:
    """Testata: il marchio a sinistra, i dati dello studio accanto."""
    nome = studio.get("denominazione") or f"{studio.get('nome','')} {studio.get('cognome','')}".strip()
    nome = nome or "Studio Veterinario"
    righe = []
    # La qualifica sopra il nome, come nelle fatture cartacee gia' in uso. Si omette
    # se il nome la contiene gia', per non ripeterla due volte di seguito.
    if "veterinari" not in nome.lower():
        righe.append(Paragraph("M E D I C O &nbsp; V E T E R I N A R I O", ss["Qualifica"]))
    righe.append(Paragraph(nome, ss["StudioNome"]))
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

    testata = Table([[marchio.flowable(20 * mm, _MARCHIO), righe]],
                    colWidths=[marchio.larghezza_per(20 * mm) + 6 * mm, None])
    testata.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    # Filetto in ottone che chiude la carta intestata e la stacca dal documento.
    return [testata, Spacer(1, 4 * mm),
            HRFlowable(width="100%", thickness=1.2, color=_OTTONE,
                       spaceBefore=0, spaceAfter=0)]


_TITOLI = {"nota_credito": "NOTA DI CREDITO", "proforma": "PROFORMA"}


def _blocco_cliente(f: dict, ss) -> Table:
    tipo = _TITOLI.get(f["tipo_documento"], "FATTURA")
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


def _raggruppa_per_cavallo(righe: list[dict]) -> list[tuple[str, list[dict]]]:
    """Righe raggruppate per nome del cavallo, in ordine di prima comparsa.

    Le righe senza cavallo confluiscono in un gruppo con chiave vuota (nessuna
    intestazione stampata). Rispecchia la fattura cartacea, che elenca le
    prestazioni sotto il nome di ogni cavallo.
    """
    gruppi: dict[str, list[dict]] = {}
    ordine: list[str] = []
    for r in righe:
        nome = (r.get("paziente_nome") or "").strip()
        if nome not in gruppi:
            gruppi[nome] = []
            ordine.append(nome)
        gruppi[nome].append(r)
    return [(nome, gruppi[nome]) for nome in ordine]


def _tabella_righe(f: dict, ss) -> Table:
    """Tabella righe VERSO IL CLIENTE: Data, Descrizione, Q.tà, Importo.

    Prezzo di listino e sconto NON compaiono qui: sono informazioni dell'emittente
    e restano nell'app. L'importo e' il praticato (``imponibile_riga``). Le righe
    sono raggruppate per cavallo, con una riga-intestazione per gruppo e la data
    all'inizio di ogni prestazione.

    L'aliquota compare **solo se il documento ne ha piu' d'una**. Con un'aliquota
    sola la dice gia' il riepilogo qui sotto e ripeterla a ogni riga e' rumore; con
    piu' aliquote, invece, senza quella colonna il cliente non puo' sapere quale
    importo sta a quale aliquota, e il documento non e' riconciliabile.
    """
    aliquote = {str(r.get("aliquota_iva")) for r in f["righe"]}
    mostra_iva = len(aliquote) > 1

    intest = ["Data", "Descrizione", "Q.tà"] + (["IVA%"] if mostra_iva else []) + ["Importo"]
    n_col = len(intest)
    dati = [intest]
    stile = [
        ("BACKGROUND", (0, 0), (-1, 0), _TINTA),
        ("TEXTCOLOR", (0, 0), (-1, 0), _VERDE),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),   # Q.tà e Importo a destra
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, _BORDO),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    r_idx = 0  # indice della prossima riga da inserire in ``dati``
    for nome_cavallo, righe in _raggruppa_per_cavallo(f["righe"]):
        if nome_cavallo:
            dati.append([Paragraph(f"<b>{nome_cavallo}</b>", ss["Corpo"])] + [""] * (n_col - 1))
            r_idx += 1
            stile.append(("SPAN", (0, r_idx), (-1, r_idx)))
            stile.append(("BACKGROUND", (0, r_idx), (-1, r_idx), _TINTA))
            stile.append(("TEXTCOLOR", (0, r_idx), (-1, r_idx), _VERDE))
        for r in righe:
            riga = [
                data_it(r.get("data_prestazione")),
                Paragraph(r["descrizione"], ss["Corpo"]),
                euro(r["quantita"]) if "." in str(r["quantita"]) else str(r["quantita"]),
            ]
            if mostra_iva:
                riga.append(_pulisci(r["aliquota_iva"]))
            riga.append(euro(r["imponibile_riga"]))
            dati.append(riga)
            r_idx += 1
            stile.append(("LINEBELOW", (0, r_idx), (-1, r_idx), 0.3, _BORDO))
    larghezze = ([26 * mm, 104 * mm, 18 * mm, 22 * mm] if not mostra_iva
                 else [26 * mm, 90 * mm, 18 * mm, 14 * mm, 22 * mm])
    t = Table(dati, colWidths=larghezze, repeatRows=1)
    t.setStyle(TableStyle(stile))
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

    # Nota in calce: diversa per proforma (non fiscale) o fattura cartacea.
    story.append(Spacer(1, 8 * mm))
    if f["tipo_documento"] == "proforma":
        validita = f.get("validita_giorni") or 30
        nota = (f"Preventivo non fiscale, non valido ai fini IVA. "
                f"Validita': {validita} giorni dalla data di emissione.")
    else:
        nota = ("Documento non soggetto a fatturazione elettronica via SdI (prestazioni "
                "sanitarie i cui dati confluiscono nel Sistema Tessera Sanitaria).")
    story.append(Paragraph(nota, ss["Piccolo"]))

    doc.build(story)
    return buf.getvalue()
