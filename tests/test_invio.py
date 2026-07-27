"""Test delle utilità di invio (telefono/WhatsApp/email)."""
import pytest

from app.invio import (
    ConfigurazioneMancante, invia_email, link_whatsapp, normalizza_telefono,
)


def test_normalizza_telefono():
    assert normalizza_telefono("+39 340 123 4567") == "393401234567"
    assert normalizza_telefono("340 1234567") == "39340123456" + "7"
    assert normalizza_telefono("0039 3401234567") == "393401234567"
    assert normalizza_telefono("393401234567") == "393401234567"


def test_link_whatsapp():
    url = link_whatsapp("340 1234567", "Ciao, in allegato la fattura")
    assert url.startswith("https://wa.me/39340")
    assert "text=Ciao" in url and "%20" in url  # testo urlencoded


def test_email_senza_config_solleva():
    # Nessun host SMTP -> ConfigurazioneMancante prima di qualsiasi rete.
    with pytest.raises(ConfigurazioneMancante):
        invia_email({"smtp_host": "", "smtp_mittente": ""},
                    destinatario="c@x.it", oggetto="x", corpo="y")


def test_email_senza_destinatario_solleva():
    with pytest.raises(ConfigurazioneMancante):
        invia_email({"smtp_host": "smtp.x.it", "smtp_mittente": "s@x.it"},
                    destinatario="", oggetto="x", corpo="y")
