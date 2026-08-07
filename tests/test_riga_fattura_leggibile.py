"""Il modulo di emissione deve far *vedere* quello che si scrive, e rifiutare l'impossibile.

Nati da un caso vero: e' stata emessa una fattura con **aliquota IVA 2222%**,
prezzo 0,00 e totale 0,00. Nessun errore, nessun avviso, e un documento che per
legge non si cancella piu'. Tre difetti concatenati, uno per gruppo di test:

1. i campi numerici non mostravano le cifre (colonne schiacciate dal layout);
2. il campo rifiutava la virgola, che e' come si scrive un prezzo in italiano;
3. il server accettava qualunque numero, purche' fosse un numero.
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.calcolo import ValoreNonNumerico, dec
from app.main import app
from app.validazioni import valida_importi_riga


def _client():
    return TestClient(app)


# --- 1. Le colonne numeriche devono restare leggibili ------------------------

def test_le_larghezze_delle_colonne_sono_rispettate():
    """``table-layout: fixed`` non e' un dettaglio estetico.

    Senza, la larghezza la decide il contenuto: i menu' (cavallo, Sp. TS)
    reclamano il loro spazio e a cedere sono le colonne numeriche, che si
    riducono a pochi pixel. Il campo continua ad accettare quel che scrivi, ma
    le cifre non si vedono — ed e' cosi' che dentro un "22" gia' presente e'
    finito un altro "22".
    """
    from pathlib import Path
    css = (Path(__file__).resolve().parent.parent
           / "app" / "static" / "css" / "stile.css").read_text(encoding="utf-8")
    assert "table.righe-fattura { table-layout: fixed; }" in css


def test_i_campi_degli_importi_non_sono_di_tipo_number():
    """``type="number"`` porta con se' le frecce di incremento, che in una
    colonna stretta si mangiano lo spazio delle cifre — e soprattutto rifiuta la
    virgola (vedi il gruppo 2)."""
    from pathlib import Path
    html = (Path(__file__).resolve().parent.parent
            / "app" / "templates" / "fattura_nuova.html").read_text(encoding="utf-8")
    for campo in ("r_quantita", "r_prezzo", "r_sconto", "r_aliquota"):
        riga = [l for l in html.splitlines() if f'name="{campo}"' in l]
        assert riga, f"campo {campo} non trovato"
        assert 'type="number"' not in riga[0], f"{campo} e' ancora di tipo number"
        assert 'inputmode="decimal"' in riga[0], f"{campo} senza tastierino numerico"


# --- 2. La virgola e' come si scrive un prezzo in italiano -------------------

def test_il_prezzo_con_la_virgola_arriva_intero():
    """``dec()`` la accettava gia'; era il campo del browser a buttarla via.

    Con ``type="number"`` un valore scritto "45,50" e' invalido: il campo
    restituisce **stringa vuota**, il server legge zero e la fattura esce a zero
    senza un errore. Da qui "non riuscivo a vedere i valori che immettevo".
    """
    assert dec("45,50") == Decimal("45.50")


def test_il_separatore_delle_migliaia_non_fa_esplodere_la_pagina():
    """"1.234,56" e' il modo piu' naturale di scrivere milleduecento euro, e
    sollevava ``decimal.InvalidOperation``: pagina di errore di sistema, in
    mezzo all'emissione di una fattura."""
    assert dec("1.234,56") == Decimal("1234.56")
    # Senza virgola il punto resta decimale, ed e' voluto: e' la notazione con
    # cui ogni importo e' salvato nel database. "12.345" vale dodici e trentotto
    # centesimi arrotondati, non dodicimila — chi scrive le migliaia mette anche
    # la virgola dei centesimi.
    assert dec("12.345") == Decimal("12.345")


def test_la_notazione_del_database_continua_a_funzionare():
    """Il punto decimale arriva da ogni riga gia' salvata: guai a romperlo."""
    assert dec("45.00") == Decimal("45.00")
    assert dec("1234.56") == Decimal("1234.56")
    assert dec(Decimal("7.25")) == Decimal("7.25")


def test_un_valore_che_non_e_un_numero_lo_dice_invece_di_sparire():
    """Restituire zero in silenzio e' il difetto che ha prodotto la fattura da
    0,00 euro: meglio un errore visibile."""
    with pytest.raises(ValoreNonNumerico):
        dec("quarantacinque")
    assert dec("") == Decimal("0")   # il campo vuoto resta zero, quello e' legittimo


def test_un_importo_scritto_male_non_da_una_pagina_di_errore():
    """Deve tornare nel modulo con un messaggio, non un 500."""
    r = _client().post("/fatture", data={
        "cliente_id": "1", "data_emissione": "2026-08-07",
        "r_descrizione": "Visita", "r_quantita": "1", "r_prezzo": "quarantacinque",
        "r_sconto": "0", "r_aliquota": "22", "r_tipo_spesa": "SV",
        "r_prestazione_id": "", "r_paziente_id": "", "r_data": "",
    }, follow_redirects=False)
    assert r.status_code == 400
    assert "non è un numero" in r.text or "non &#232; un numero" in r.text


# --- 3. Il server deve rifiutare l'impossibile -------------------------------

def test_aliquota_2222_viene_rifiutata():
    """**Il caso vero.** Prima passava, e produceva un documento immutabile."""
    errori = valida_importi_riga("Visita", dec("1"), dec("50"), dec("0"), dec("2222"))
    assert errori, "un'aliquota del 2222% deve essere rifiutata"
    assert "2222" in errori[0]


@pytest.mark.parametrize("aliquota", ["0", "4", "5", "10", "22"])
def test_le_aliquote_vere_passano(aliquota):
    """Comprese 0 (esente/non imponibile): il controllo ferma l'impossibile, non
    decide al posto di chi fattura."""
    assert valida_importi_riga("Visita", dec("1"), dec("50"), dec("0"),
                               dec(aliquota)) == []


def test_quantita_zero_e_prezzo_negativo_vengono_rifiutati():
    assert valida_importi_riga("Visita", dec("0"), dec("50"), dec("0"), dec("22"))
    assert valida_importi_riga("Visita", dec("1"), dec("-50"), dec("0"), dec("22"))
    assert valida_importi_riga("Visita", dec("1"), dec("50"), dec("150"), dec("22"))


def test_il_messaggio_dice_di_quale_riga_si_parla():
    """Con piu' righe, "aliquota non valida" da solo non basta a trovarla."""
    errori = valida_importi_riga("Ecografia tendinea", dec("1"), dec("90"),
                                 dec("0"), dec("2222"))
    assert "Ecografia tendinea" in errori[0]


def test_la_fattura_con_aliquota_impossibile_non_viene_emessa():
    """Il giro completo dal modulo: prima usciva 400 solo per altri motivi, e
    una riga con aliquota 2222 arrivava allo snapshot immutabile."""
    c = _client()
    elenco_prima = c.get("/fatture").text

    r = c.post("/fatture", data={
        "cliente_id": "1", "data_emissione": "2026-08-07", "stato": "emessa",
        "r_descrizione": "Visita clinica", "r_quantita": "1", "r_prezzo": "50,00",
        "r_sconto": "0", "r_aliquota": "2222", "r_tipo_spesa": "SV",
        "r_prestazione_id": "", "r_paziente_id": "", "r_data": "2026-08-07",
    }, follow_redirects=False)

    assert r.status_code == 400, "doveva rifiutare, non emettere"
    assert "2222" in r.text
    # e nessun documento nuovo e' comparso nell'elenco
    assert c.get("/fatture").text.count("<tr") == elenco_prima.count("<tr")
