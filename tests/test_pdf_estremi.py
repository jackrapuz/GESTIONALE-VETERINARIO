"""Il PDF con dati che nella realta' capitano, e che nessun test provava.

Il generatore del PDF e' l'unico pezzo che produce un documento *fiscale*: se si
rompe, si rompe nel momento in cui la fattura serve. E si rompe per motivi
banali — una descrizione lunga, quaranta righe, un nome di cavallo chilometrico —
che nei dati di esempio non compaiono mai.

Questi test non guardano l'impaginazione, che va vista con gli occhi: verificano
che un PDF esca comunque, invece di un'eccezione a meta' emissione.
"""
import pytest

from app.fatturazione import gruppi_iva_da_righe
from app.pdf_fattura import genera_pdf_fattura

STUDIO = {
    "denominazione": "Dott.ssa Giulia Bianchi", "nome": "Giulia", "cognome": "Bianchi",
    "codice_fiscale": "BNCGLI85T55F205X", "partita_iva": "12345678903",
    "via": "Via delle Scuderie 12", "cap": "40100", "citta": "Bologna", "prov": "BO",
    "email": "studio@example.it", "telefono": "051 1234567",
    "iban": "IT60X0542811101000000123456", "regime": "", "n_iscrizione_albo": "1234",
    "enpav_pct": "2.00", "iva_default_pct": "22.00",
    "testo_dicitura_opposizione_ts": "Opposizione all'invio al Sistema TS",
    "logo_path": "",
}


def _riga(descrizione, cavallo="", prezzo="100.00", aliquota="22.00", data="2026-07-15"):
    return {"descrizione": descrizione, "quantita": "1", "prezzo_unitario": prezzo,
            "sconto_riga_pct": "0", "aliquota_iva": aliquota, "tipo_spesa_ts": "SV",
            "imponibile_riga": prezzo, "paziente_nome": cavallo,
            "data_prestazione": data}


def _fattura(righe, cliente="Rossi Mario", note=""):
    return {"tipo_documento": "fattura", "numero_visualizzato": "1/2026",
            "data_emissione": "2026-08-07", "cli_denominazione": cliente,
            "cli_codice_fiscale": "RSSMRA80A01H501U", "cli_partita_iva": "",
            "cli_indirizzo": "Via Prova 1, 00100 Roma (RM)",
            "modalita_pagamento": "Bonifico", "data_pagamento": "", "stato": "emessa",
            "opposizione_ts": 0, "ritenuta_applicata": 0, "ritenuta_pct": "0.00",
            "enpav_pct": "2.00", "imponibile": "100.00", "contributo_enpav": "2.00",
            "base_iva": "102.00", "iva_totale": "22.44", "ritenuta_importo": "0.00",
            "totale_documento": "124.44", "netto_a_pagare": "124.44",
            "note": note, "righe": righe}


def _genera(f) -> bytes:
    return genera_pdf_fattura(f, STUDIO, gruppi_iva_da_righe(f["righe"], f["enpav_pct"]))


CASI = {
    # Una giornata di lavoro su una scuderia grande sta tutta in una fattura.
    "quaranta righe": _fattura([_riga(f"Prestazione {i}", f"CAVALLO{i}")
                                for i in range(1, 41)]),
    "descrizione lunghissima": _fattura([_riga(
        "Visita clinica generale con valutazione ortopedica completa, esame "
        "dell'andatura al passo e al trotto su terreno duro e morbido, flessioni "
        "degli arti anteriori e posteriori e relazione scritta", "FULMINE")]),
    "nome di cavallo chilometrico": _fattura([_riga(
        "Visita", "BAIARDO DELLA VALLE DEI CAVALIERI ERRANTI DI SAN MARTINO")]),
    "ragione sociale lunghissima": _fattura(
        [_riga("Visita")],
        cliente="Societa' Agricola Scuderia Il Galoppo dei Fratelli Bianchi e Rossi "
                "Societa' a responsabilita' limitata semplificata"),
    "tre aliquote diverse": _fattura([_riga("A", "", "100.00", "22.00"),
                                      _riga("B", "", "50.00", "10.00"),
                                      _riga("C", "", "30.00", "4.00")]),
    "importo enorme": _fattura([_riga("Intervento", "", "1234567.89")]),
    "note lunghissime": _fattura([_riga("Visita")], note="Nota molto lunga. " * 60),
    # Le maiuscole con accento e la e commerciale sono quelle che tipicamente
    # fanno saltare i generatori di PDF.
    "caratteri che di solito rompono": _fattura([_riga(
        "Visita <b>&</b> \"virgolette\" — trattino, accénti àèìòù, 50% & 100%")]),
    "senza cavallo e senza data": _fattura([_riga("Visita", "", data="")]),
}


@pytest.mark.parametrize("nome", list(CASI))
def test_il_pdf_esce_comunque(nome):
    pdf = _genera(CASI[nome])
    assert pdf.startswith(b"%PDF-"), f"{nome}: non e' un PDF"
    assert len(pdf) > 2000, f"{nome}: PDF sospettosamente vuoto"


def test_quaranta_righe_producono_piu_pagine_non_un_troncamento():
    """Se le righe in eccesso sparissero, la fattura sarebbe sbagliata **e**
    sembrerebbe a posto: il difetto peggiore possibile su un documento fiscale."""
    corto = _genera(_fattura([_riga("Una sola")]))
    lungo = _genera(CASI["quaranta righe"])
    assert len(lungo) > len(corto), "quaranta righe non pesano piu' di una: troncate?"
