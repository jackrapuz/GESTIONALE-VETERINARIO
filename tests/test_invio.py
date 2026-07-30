"""Test dell'invio via WhatsApp (numero, link, preparazione del PDF)."""
import pytest

from app import invio as mod
from app.invio import (
    TelefonoMancante, link_whatsapp, nome_file_documento, normalizza_telefono,
    prepara_invio_whatsapp,
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


def test_link_whatsapp():
    url = link_whatsapp("340 1234567", "Ciao, in allegato la fattura")
    assert url.startswith("https://wa.me/39340")
    assert "text=Ciao" in url and "%20" in url  # testo urlencoded


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
    assert esito["link"].startswith("https://wa.me/393401234567?text=")
    # Il numero del documento e' nel messaggio; la barra resta letterale, che
    # dentro una query string e' legale.
    assert "91/2026" in esito["link"]


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


def test_copia_negli_appunti_mette_davvero_il_file(tmp_path):
    """Test di integrazione con gli appunti di Windows (salta altrove)."""
    import subprocess
    import sys

    if sys.platform != "win32":
        pytest.skip("appunti Windows")
    f = tmp_path / "documento di prova.pdf"
    f.write_bytes(b"%PDF")
    assert mod.copia_negli_appunti(f) is True
    letto = subprocess.run(
        ["powershell", "-NoProfile", "-STA", "-Command",
         "(Get-Clipboard -Format FileDropList).Name"],
        capture_output=True, text=True, timeout=30)
    assert "documento di prova.pdf" in letto.stdout
