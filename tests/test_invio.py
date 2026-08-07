"""Test dell'invio via WhatsApp (numero, link, preparazione del PDF)."""
import time

import pytest

from app import invio as mod
from app.invio import (
    TelefonoMancante, link_whatsapp_app, link_whatsapp_web, nome_file_documento,
    normalizza_telefono, prepara_invio_whatsapp,
)

STUDIO = {"denominazione": "Studio Veterinario"}
DOC = {"tipo_documento": "fattura", "numero_visualizzato": "91/2026",
       "data_emissione": "2026-07-30", "totale_documento": "510.20",
       "cli_denominazione": "Maria Rossi"}


def test_normalizza_telefono():
    assert normalizza_telefono("+39 340 123 4567") == "393401234567"
    assert normalizza_telefono("340 1234567") == "393401234567"
    assert normalizza_telefono("0039 3401234567") == "393401234567"
    assert normalizza_telefono("393401234567") == "393401234567"


def test_un_cellulare_39x_non_e_un_numero_gia_internazionale():
    """``391``, ``392`` e ``393`` sono prefissi di cellulare veri (Wind/3).

    Scambiarli per il prefisso internazionale lasciava il numero senza ``39``
    davanti, e WhatsApp apriva su un numero inesistente: il difetto si vedeva solo
    con quei clienti li'. Si distingue dalla lunghezza, non da come comincia.
    """
    assert normalizza_telefono("391 1234567") == "393911234567"
    assert normalizza_telefono("392 1234567") == "393921234567"
    assert normalizza_telefono("393 1234567") == "393931234567"
    # e quello che il prefisso ce l'ha davvero resta intatto
    assert normalizza_telefono("39 391 1234567") == "393911234567"


def test_lo_zero_dei_numeri_fissi_non_si_toglie():
    """In Italia lo ``0`` urbano fa parte del numero anche in internazionale:
    Bologna e' ``+39 051``, non ``+39 51``. La regola "via gli zeri iniziali"
    vale in Francia o nel Regno Unito, non qui."""
    assert normalizza_telefono("051 2345678") == "390512345678"
    assert normalizza_telefono("+39 051 2345678") == "390512345678"


def test_il_link_apre_la_chat_e_non_una_pagina_di_passaggio():
    """``wa.me`` non e' un collegamento alla conversazione: e' una pagina di
    WhatsApp con un pulsante "Continua sulla chat", da cui ogni volta si sceglie
    fra applicazione e Web. Questi due invece ci vanno dritti."""
    app = link_whatsapp_app("340 1234567", "Ciao, in allegato la fattura")
    assert app.startswith("whatsapp://send?phone=393401234567&text=")
    assert "text=Ciao" in app and "%20" in app  # testo urlencoded

    web = link_whatsapp_web("340 1234567", "Ciao, in allegato la fattura")
    assert web.startswith("https://web.whatsapp.com/send?phone=393401234567&text=")

    assert "wa.me" not in app and "wa.me" not in web


def test_nome_file_leggibile_e_valido_su_windows():
    # La barra del numero (91/2026) non puo' finire in un nome di file.
    assert nome_file_documento(DOC) == "fattura_91-2026.pdf"
    assert nome_file_documento({**DOC, "tipo_documento": "proforma"}) \
        == "preventivo_91-2026.pdf"


def test_prepara_invio_salva_il_pdf_e_costruisce_il_link(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "CARTELLA_INVII", tmp_path / "da_inviare")
    # Gli appunti sono un effetto di sistema: qui interessa il resto.
    monkeypatch.setattr(mod, "copia_negli_appunti", lambda p: True)

    esito = prepara_invio_whatsapp(STUDIO, DOC, b"%PDF-1.4 finto", "340 1234567")

    assert esito["percorso"].read_bytes() == b"%PDF-1.4 finto"
    assert esito["percorso"].name == "fattura_91-2026.pdf"
    assert esito["negli_appunti"] is True
    assert esito["link_app"].startswith("whatsapp://send?phone=393401234567&text=")
    assert esito["link_web"].startswith(
        "https://web.whatsapp.com/send?phone=393401234567&text=")
    # Il numero del documento e' nel messaggio; la barra resta letterale, che
    # dentro una query string e' legale.
    assert "91/2026" in esito["link_app"]
    assert "91/2026" in esito["link_web"]


def test_senza_telefono_non_si_prepara_niente(tmp_path, monkeypatch):
    """Senza numero non c'e' chat da aprire: meglio dirlo che salvare un PDF a vuoto."""
    cartella = tmp_path / "da_inviare"
    monkeypatch.setattr(mod, "CARTELLA_INVII", cartella)
    with pytest.raises(TelefonoMancante):
        prepara_invio_whatsapp(STUDIO, DOC, b"%PDF", "   ")
    assert not cartella.exists()


def test_appunti_non_disponibili_non_bloccano_l_invio(tmp_path, monkeypatch):
    """Se gli appunti non si popolano, il PDF resta su disco e l'invio e' manuale."""
    monkeypatch.setattr(mod, "CARTELLA_INVII", tmp_path / "da_inviare")
    monkeypatch.setattr(mod, "copia_negli_appunti", lambda p: False)
    esito = prepara_invio_whatsapp(STUDIO, DOC, b"%PDF", "3401234567")
    assert esito["negli_appunti"] is False
    assert esito["percorso"].exists()


def _pagina_invio(negli_appunti: bool, tmp_path) -> str:
    """Rende la pagina d'invio come la vedrebbe lei, senza toccare il database.

    Il minimo che ``base.html`` chiede alla richiesta: il percorso (per il menu)
    e i messaggi in coda.
    """
    from types import SimpleNamespace

    from app.templating import templates
    richiesta = SimpleNamespace(
        url=SimpleNamespace(path="/fatture/1/whatsapp"),
        query_params=SimpleNamespace(getlist=lambda _n: []),
    )
    pdf = tmp_path / "fattura_91-2026.pdf"
    pdf.write_bytes(b"%PDF")
    return templates.get_template("invio_whatsapp.html").render(
        request=richiesta, senza_presenza=True, doc=DOC, ritorno="/fatture/1",
        pdf_url="/fatture/1/pdf",
        invio={"percorso": pdf, "cartella": str(tmp_path),
               "negli_appunti": negli_appunti,
               "link_app": "whatsapp://send?phone=393401234567&text=Ciao",
               "link_web": "https://web.whatsapp.com/send?phone=393401234567&text=Ciao",
               "numero": "393401234567"},
    )


def test_la_pagina_offre_tutte_e_due_le_vie_per_aprire_whatsapp(tmp_path):
    """Il programma non puo' sapere se su quel computer WhatsApp e' installato:
    se offrisse solo l'applicazione, chi non ce l'ha premerebbe un pulsante che
    non fa niente — e senza console non se ne accorgerebbe nessuno."""
    html = _pagina_invio(True, tmp_path)
    assert "whatsapp://send?phone=393401234567" in html
    assert "web.whatsapp.com/send?phone=393401234567" in html


def test_la_pagina_non_promette_il_trascinamento_su_whatsapp_web(tmp_path):
    """Misurato in Chrome: verso una **pagina web** il browser toglie il
    ``DownloadURL`` e consegna solo l'indirizzo del PDF, che al cliente non serve
    e muore col programma. Il trascinamento vale per l'applicazione; su Web serve
    Ctrl+V, e la pagina deve dirlo invece di lasciarlo scoprire a un invio andato
    a vuoto."""
    html = _pagina_invio(True, tmp_path)
    assert "non si trascina" in html
    assert "Ctrl+V" in html


def test_la_pagina_consegna_il_pdf_da_scaricare_e_trascinare(tmp_path):
    """**Il requisito.** Senza API l'allegato lo prende lei dalla pagina: se il
    PDF non e' li' da afferrare, l'invio non si puo' completare. Prima la pagina
    lo nominava soltanto, e non c'era niente da prendere."""
    html = _pagina_invio(True, tmp_path)
    # scaricabile: un link al PDF che il browser salva col nome giusto
    assert 'href="/fatture/1/pdf"' in html
    assert 'download="fattura_91-2026.pdf"' in html
    # trascinabile: senza DownloadURL nella chat finirebbe l'indirizzo, non il file
    assert 'draggable="true"' in html
    assert "DownloadURL" in html
    assert "application/pdf:" in html
    # visibile: l'anteprima e' la prova che e' il documento giusto
    assert 'class="anteprima-pdf"' in html


def test_il_pdf_si_prende_anche_senza_appunti(tmp_path):
    """Il trascinamento non passa per gli appunti: se quelli falliscono, il file
    deve restare comunque afferrabile dalla pagina."""
    html = _pagina_invio(False, tmp_path)
    assert 'download="fattura_91-2026.pdf"' in html
    assert "graffetta" in html  # e la terza via resta spiegata


def _appunti_di_windows_funzionano() -> bool:
    """Gli appunti di Windows sono **una risorsa condivisa di tutto il computer**.

    Un qualunque altro programma puo' tenerli aperti, e allora falliscono per
    chiunque: e' successo davvero durante una sessione di lavoro, con
    ``Set-Clipboard`` che non riusciva nemmeno da PowerShell a mano.

    Senza questo controllo il test cadeva in quei momenti, dando la colpa al
    gestionale per qualcosa che non aveva fatto. Un test che diventa rosso a caso
    e' peggio di un test che manca: insegna a ignorare i test rossi, e da li' in
    poi copre anche i guasti veri.
    """
    import subprocess

    for _ in range(3):        # i blocchi sugli appunti di solito durano un attimo
        esito = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-STA", "-Command",
             "Set-Clipboard -Value 'prova'"],
            capture_output=True, timeout=30)
        if esito.returncode == 0:
            return True
        time.sleep(0.5)
    return False


def test_copia_negli_appunti_mette_davvero_il_file(tmp_path):
    """Test di integrazione con gli appunti di Windows (salta altrove)."""
    import subprocess
    import sys

    if sys.platform != "win32":
        pytest.skip("appunti Windows")
    if not _appunti_di_windows_funzionano():
        pytest.skip("gli appunti di Windows sono occupati da un altro programma: "
                    "non e' un difetto del gestionale")

    f = tmp_path / "documento di prova.pdf"
    f.write_bytes(b"%PDF")
    assert mod.copia_negli_appunti(f) is True
    letto = subprocess.run(
        ["powershell", "-NoProfile", "-STA", "-Command",
         "(Get-Clipboard -Format FileDropList).Name"],
        capture_output=True, text=True, timeout=30)
    assert "documento di prova.pdf" in letto.stdout
