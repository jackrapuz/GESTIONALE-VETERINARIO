"""Modello dati per il Sistema Tessera Sanitaria.

Il test che regge tutto e' quello sulla quadratura: **la somma delle voci di
spesa deve fare esattamente il totale del documento**. Il database tiene
l'imponibile per riga, mentre ENPAV e IVA sono calcolati e arrotondati per
gruppo di aliquota; ripartire male vorrebbe dire dichiarare al Sistema TS un
importo diverso da quello fatturato al cliente. Sarebbe un errore che passa i
controlli formali del portale e sbaglia la detrazione — cioe' invisibile.
"""
from decimal import Decimal

import pytest

from app import export_ts, ts_cifratura, ts_xml, tracciato_ts
from app.calcolo import RigaInput, dec
from app.db import get_conn, init_db
from app.fatturazione import emetti_fattura, gruppi_iva_da_righe, leggi_fattura

STUDIO = {"codice_fiscale": "RPAFNC85M41H501Z", "partita_iva": "12345678903"}
DAL, AL = "2026-01-01", "2026-12-31"


@pytest.fixture()
def conn(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    c = get_conn(db)
    c.execute(
        "INSERT INTO clienti (tipo, nome, cognome, codice_fiscale) "
        "VALUES ('fisica','Mario','Rossi','RSSMRA85T10A562S')"
    )
    c.commit()
    yield c
    c.close()


def _cliente(conn, cid=1):
    return conn.execute("SELECT * FROM clienti WHERE id=?", (cid,)).fetchone()


def _emetti(conn, righe, **kw):
    kw.setdefault("data_emissione", "2026-03-10")
    kw.setdefault("data_pagamento", kw["data_emissione"])
    kw.setdefault("stato", "incassata")
    return emetti_fattura(conn, cliente=_cliente(conn, kw.pop("cliente_id", 1)),
                          righe=righe, **kw)


def _documento(conn, fid):
    f = leggi_fattura(conn, fid)
    gruppi = gruppi_iva_da_righe(f["righe"], f["enpav_pct"])
    return f, tracciato_ts.costruisci_documento(STUDIO, f, gruppi)


# --- la quadratura ---------------------------------------------------------

@pytest.mark.parametrize("righe", [
    pytest.param([RigaInput("Visita", 1, "80", "22")], id="una-riga"),
    pytest.param([RigaInput("A", 1, "33.33", "22"),
                  RigaInput("B", 1, "33.33", "22"),
                  RigaInput("C", 1, "33.33", "22")], id="tre-terzi-che-non-tornano"),
    pytest.param([RigaInput("Visita", 1, "80", "22"),
                  RigaInput("Farmaco", 1, "12.50", "10")], id="aliquote-miste"),
    pytest.param([RigaInput("A", 3, "19.99", "22"),
                  RigaInput("B", 7, "1.01", "4"),
                  RigaInput("C", 1, "0.01", "22")], id="centesimi-cattivi"),
    pytest.param([RigaInput("A", 1, "1000", "22"),
                  RigaInput("B", 1, "0.01", "22")], id="una-riga-domina"),
])
def test_le_voci_sommano_esattamente_il_totale_del_documento(conn, righe):
    """**Il requisito.** Ripartire ENPAV e IVA per riga non deve perdere centesimi."""
    esito = _emetti(conn, righe)
    f, doc = _documento(conn, esito["id"])
    assert doc.totale == dec(f["totale_documento"]), (
        f"voci {doc.totale} contro totale {f['totale_documento']}")
    assert tracciato_ts.valida_documento(doc, dec(f["totale_documento"])) == []


def test_il_residuo_finisce_su_una_riga_sola(conn):
    """Verifica che il caso difficile sia davvero difficile.

    Tre righe da 33,33 al 22% con ENPAV al 2% danno un lordo di gruppo di 124,43,
    che diviso in tre da' 41,48 ciascuna: 124,44, un centesimo di troppo. Se le
    tre voci risultassero uguali vorrebbe dire che il residuo non e' stato
    gestito e che il test della quadratura sta passando per caso.
    """
    esito = _emetti(conn, [RigaInput("A", 1, "33.33", "22"),
                           RigaInput("B", 1, "33.33", "22"),
                           RigaInput("C", 1, "33.33", "22")])
    f, doc = _documento(conn, esito["id"])
    importi = [v.importo for v in doc.voci]
    assert len(set(importi)) == 2, f"nessun residuo da assorbire: {importi}"
    assert sum(importi) == dec(f["totale_documento"])


def test_la_ripartizione_e_deterministica(conn):
    """Due generazioni della stessa fattura devono dare lo stesso file.

    Il residuo va assegnato con una regola fissa: se dipendesse dall'ordine di un
    dizionario, un reinvio in variazione differirebbe dall'originale senza motivo.
    """
    esito = _emetti(conn, [RigaInput("A", 1, "33.33", "22"),
                           RigaInput("B", 1, "33.33", "22"),
                           RigaInput("C", 1, "33.34", "22")])
    _, primo = _documento(conn, esito["id"])
    _, secondo = _documento(conn, esito["id"])
    assert [v.importo for v in primo.voci] == [v.importo for v in secondo.voci]


def test_una_voce_per_riga_col_proprio_tipo_di_spesa(conn):
    """Il vecchio export mandava un unico importo per documento con SV fisso."""
    esito = _emetti(conn, [
        RigaInput("Visita", 1, "80", "22", tipo_spesa_ts="SV"),
        RigaInput("Antibiotico", 1, "20", "22", tipo_spesa_ts="FV"),
    ])
    _, doc = _documento(conn, esito["id"])
    assert len(doc.voci) == 2
    assert [v.tipo_spesa for v in doc.voci] == ["SV", "FV"]


# --- flag e identificativi -------------------------------------------------

def test_id_spesa_tiene_insieme_piva_data_e_progressivo(conn):
    esito = _emetti(conn, [RigaInput("Visita", 1, "80", "22")],
                    data_emissione="2026-03-10")
    _, doc = _documento(conn, esito["id"])
    assert doc.id_spesa.partita_iva == "12345678903"
    assert doc.id_spesa.data_emissione == "10/03/2026"      # GG/MM/AAAA
    assert doc.id_spesa.dispositivo == tracciato_ts.DISPOSITIVO
    assert doc.id_spesa.numero_documento == str(esito["numero"])


def test_il_flag_pagamento_anticipato_solo_se_pagato_prima(conn):
    dopo = _emetti(conn, [RigaInput("Visita", 1, "80", "22")],
                   data_emissione="2026-03-10", data_pagamento="2026-03-10")
    _, doc = _documento(conn, dopo["id"])
    assert doc.flag_pagamento_anticipato is False

    prima = _emetti(conn, [RigaInput("Visita", 1, "80", "22")],
                    data_emissione="2026-04-10", data_pagamento="2026-04-01")
    _, doc = _documento(conn, prima["id"])
    assert doc.flag_pagamento_anticipato is True


def test_con_opposizione_il_codice_fiscale_non_si_trasmette(conn):
    """E' il senso stesso dell'opposizione; il flag dice che l'assenza e' voluta."""
    esito = _emetti(conn, [RigaInput("Visita", 1, "80", "22")], opposizione_ts=True)
    f, doc = _documento(conn, esito["id"])
    assert doc.cf_assistito == ""
    assert doc.opposizione is True
    assert tracciato_ts.valida_documento(doc, dec(f["totale_documento"])) == []


def test_ogni_documento_e_un_inserimento_finche_non_si_e_mai_trasmesso(conn):
    esito = _emetti(conn, [RigaInput("Visita", 1, "80", "22")])
    _, doc = _documento(conn, esito["id"])
    assert doc.flag_operazione == tracciato_ts.OP_INSERIMENTO
    assert doc.tipo_documento == tracciato_ts.TIPO_DOCUMENTO_FATTURA


# --- validazione -----------------------------------------------------------

def test_un_totale_che_non_quadra_viene_respinto(conn):
    """La rete di sicurezza: meglio uno scarto visibile di un importo sbagliato."""
    esito = _emetti(conn, [RigaInput("Visita", 1, "80", "22")])
    f, doc = _documento(conn, esito["id"])
    errori = tracciato_ts.valida_documento(doc, dec(f["totale_documento"]) + Decimal("1"))
    assert any("sommano" in e for e in errori)


def test_senza_partita_iva_dello_studio_non_si_trasmette(conn):
    esito = _emetti(conn, [RigaInput("Visita", 1, "80", "22")])
    f = leggi_fattura(conn, esito["id"])
    gruppi = gruppi_iva_da_righe(f["righe"], f["enpav_pct"])
    doc = tracciato_ts.costruisci_documento({"partita_iva": ""}, f, gruppi)
    assert any("partita IVA" in e for e in tracciato_ts.valida_documento(
        doc, dec(f["totale_documento"])))


def test_un_tipo_di_spesa_fuori_standard_e_uno_scarto(conn):
    """Un valore entrato prima che l'elenco fosse chiuso non deve passare zitto."""
    esito = _emetti(conn, [RigaInput("Visita", 1, "80", "22")])
    with conn:
        conn.execute("UPDATE righe_fattura SET tipo_spesa_ts='TK' WHERE fattura_id=?",
                     (esito["id"],))
    f, doc = _documento(conn, esito["id"])
    assert any("Tipo di spesa non ammesso" in e
               for e in tracciato_ts.valida_documento(doc, dec(f["totale_documento"])))


# --- selezione dei documenti ----------------------------------------------

def test_si_trasmette_per_data_di_pagamento_non_di_emissione(conn):
    """Il Sistema TS segue la cassa: conta quando l'assistito ha speso."""
    _emetti(conn, [RigaInput("Visita", 1, "80", "22")],
            data_emissione="2025-12-20", data_pagamento="2026-01-15")
    assert len(export_ts.estrai_documenti(conn, DAL, AL)) == 1
    assert export_ts.estrai_documenti(conn, "2025-01-01", "2025-12-31") == []


def test_le_fatture_non_pagate_restano_fuori(conn):
    _emetti(conn, [RigaInput("Visita", 1, "80", "22")],
            data_pagamento="", stato="emessa")
    assert export_ts.estrai_documenti(conn, DAL, AL) == []


def test_un_cliente_con_partita_iva_e_escluso_non_scartato(conn):
    """Le spese veterinarie detraibili sono quelle delle persone fisiche.

    In uno studio equino i clienti con partita IVA sono tanti: metterli fra gli
    scarti farebbe sembrare che ci sia da correggere qualcosa, ogni anno.
    """
    conn.execute(
        "INSERT INTO clienti (tipo, ragione_sociale, partita_iva) "
        "VALUES ('giuridica','Scuderia Le Querce','12345678903')")
    conn.commit()
    _emetti(conn, [RigaInput("Visita", 1, "80", "22")], cliente_id=2)

    esito = export_ts.genera_export(conn, DAL, AL, STUDIO)
    assert esito["n_ok"] == 0
    assert esito["n_esclusi"] == 1
    assert esito["n_scarti"] == 0
    assert "persone fisiche" in esito["esclusi"][0][1]


def test_l_export_completo_produce_una_fornitura_valida(conn):
    esito = _emetti(conn, [RigaInput("Visita", 1, "80", "22", tipo_spesa_ts="SV"),
                           RigaInput("Farmaco", 1, "15", "10", tipo_spesa_ts="FV")])
    out = export_ts.genera_export(conn, DAL, AL, STUDIO)
    assert out["n_ok"] == 1 and out["n_scarti"] == 0
    fornitura = out["fornitura"]
    assert fornitura.cf_professionista == STUDIO["codice_fiscale"]
    assert len(fornitura.documenti) == 1
    assert len(fornitura.documenti[0].voci) == 2
    del esito


def test_l_anteprima_ha_una_riga_per_voce_di_spesa(conn):
    _emetti(conn, [RigaInput("Visita", 1, "80", "22"),
                   RigaInput("Farmaco", 1, "15", "22", tipo_spesa_ts="FV")])
    out = export_ts.genera_export(conn, DAL, AL, STUDIO)
    righe = out["anteprima_csv"].decode("utf-8-sig").strip().splitlines()
    assert righe[0].split(";") == export_ts.INTESTAZIONE_ANTEPRIMA
    assert len(righe) == 3, "intestazione + una riga per voce"


def test_il_report_distingue_esclusi_e_da_correggere(conn):
    conn.execute("INSERT INTO clienti (tipo, ragione_sociale, partita_iva) "
                 "VALUES ('giuridica','Scuderia','12345678903')")
    conn.commit()
    _emetti(conn, [RigaInput("Visita", 1, "80", "22")], cliente_id=2)
    testo = export_ts.report_problemi_csv(
        export_ts.genera_export(conn, DAL, AL, STUDIO)).decode("utf-8-sig")
    assert "escluso (non va trasmesso)" in testo


# --- le cuciture -----------------------------------------------------------

def test_il_file_xml_dichiara_di_non_essere_pronto():
    """La pagina si fida di questo per non offrire un file che verrebbe respinto."""
    assert ts_xml.disponibile() is False
    with pytest.raises(NotImplementedError) as e:
        ts_xml.serializza(tracciato_ts.Fornitura("X", ()), lambda cf: cf)
    assert "sistemats.it" in str(e.value)


def test_la_cifratura_dice_cosa_manca_e_dove_metterlo():
    """Il messaggio e' l'istruzione per chi riprendera' il lavoro."""
    with pytest.raises(NotImplementedError) as e:
        ts_cifratura.cifra_cf("RSSMRA85T10A562S")
    messaggio = str(e.value)
    assert "certificato" in messaggio and "certificato_ts.cer" in messaggio
