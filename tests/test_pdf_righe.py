"""Test della tabella righe nel PDF (app/pdf_fattura.py).

Due regole che si perdono con facilita', perche' romperle non fa fallire nulla:

1. Il cliente deve vedere **solo il prezzo praticato**. Listino e sconto sono
   informazioni dell'emittente, e una colonna "Sc. 0%" si presta a essere
   fraintesa da chi riceve il documento.
2. L'aliquota va indicata riga per riga **quando ce n'e' piu' d'una**: senza,
   il cliente non puo' sapere quale importo sta a quale aliquota e il documento
   non e' riconciliabile. Con un'aliquota sola, invece, ripeterla e' rumore.
"""
from app.pdf_fattura import _stili, _tabella_righe


def _riga(descrizione, prezzo, sconto, imponibile, aliquota="22.00",
          cavallo="", data="2026-07-15"):
    return {
        "descrizione": descrizione,
        "quantita": "1",
        "prezzo_unitario": prezzo,      # listino: NON deve finire nel PDF
        "sconto_riga_pct": sconto,      # idem
        "aliquota_iva": aliquota,
        "tipo_spesa_ts": "SV",
        "imponibile_riga": imponibile,  # praticato: e' questo che si stampa
        "paziente_nome": cavallo,
        "data_prestazione": data,
    }


def _celle(tabella):
    """Il contenuto testuale della tabella, riga per riga."""
    return [[c if isinstance(c, str) else getattr(c, "text", "") for c in r]
            for r in tabella._cellvalues]


def test_listino_e_sconto_non_arrivano_al_cliente():
    f = {"righe": [
        _riga("Esame radiografico", "240.00", "20.8333", "190.00"),
        _riga("Esame ecografico", "120.00", "16.6667", "100.00"),
    ]}
    celle = _celle(_tabella_righe(f, _stili()))
    piatto = " ".join(v for riga in celle for v in riga)

    assert "Sc.%" not in celle[0], "la colonna sconto non deve esistere"
    assert "Prezzo" not in celle[0], "il prezzo di listino non deve esistere"
    for nascosto in ("240", "120,00", "20,83", "16,66"):
        assert nascosto not in piatto, f"trapelato al cliente: {nascosto}"
    for praticato in ("190,00", "100,00"):
        assert praticato in piatto, f"manca il prezzo praticato: {praticato}"


def test_con_una_sola_aliquota_la_colonna_iva_non_c_e():
    f = {"righe": [_riga("Visita", "60.00", "0.00", "60.00"),
                   _riga("Vaccinazione", "35.00", "0.00", "35.00")]}
    assert _celle(_tabella_righe(f, _stili()))[0] == ["Data", "Descrizione", "Q.tà", "Importo"]


def test_con_piu_aliquote_la_colonna_iva_compare():
    f = {"righe": [_riga("Prestazione ridotta", "60.00", "0.00", "60.00", "10.00"),
                   _riga("Vaccinazione", "35.00", "0.00", "35.00", "22.00")]}
    celle = _celle(_tabella_righe(f, _stili()))
    assert celle[0] == ["Data", "Descrizione", "Q.tà", "IVA%", "Importo"]
    assert celle[1][3] == "10" and celle[2][3] == "22"


def test_il_raggruppamento_per_cavallo_regge_anche_con_la_colonna_iva():
    """La riga-intestazione del cavallo deve avere tante celle quante le colonne,
    altrimenti lo SPAN che la fa da titolo non combacia con la tabella."""
    f = {"righe": [_riga("Visita", "60.00", "0.00", "60.00", "10.00", cavallo="GUUS"),
                   _riga("Ecografia", "35.00", "0.00", "35.00", "22.00", cavallo="TEMPESTA")]}
    celle = _celle(_tabella_righe(f, _stili()))
    n_col = len(celle[0])
    assert all(len(r) == n_col for r in celle), "righe con numero di celle diverso"
    # il nome del cavallo e' un Paragraph in grassetto: si cerca dentro il markup
    assert "GUUS" in celle[1][0] and "TEMPESTA" in celle[3][0]


def test_la_larghezza_della_tabella_resta_dentro_il_foglio():
    """A4 meno i margini di SimpleDocTemplate: 210 - 20 - 20 = 170 mm."""
    for righe in ([_riga("A", "1.00", "0.00", "1.00")],
                  [_riga("A", "1.00", "0.00", "1.00", "10.00"),
                   _riga("B", "1.00", "0.00", "1.00", "22.00")]):
        t = _tabella_righe({"righe": righe}, _stili())
        assert abs(sum(t._colWidths) - 170 * 2.834645669) < 1.0
