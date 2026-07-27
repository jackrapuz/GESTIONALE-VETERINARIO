"""Test delle validazioni CF / P.IVA."""
from app.validazioni import is_codice_fiscale, is_partita_iva


def test_codice_fiscale_valido():
    # CF di esempio con carattere di controllo corretto
    assert is_codice_fiscale("RSSMRA85T10A562S")
    assert is_codice_fiscale("rssmra85t10a562s")  # case-insensitive


def test_codice_fiscale_non_valido():
    assert not is_codice_fiscale("RSSMRA85T10A562X")  # check char errato
    assert not is_codice_fiscale("TROPPO_CORTO")
    assert not is_codice_fiscale("")


def test_partita_iva_valida():
    assert is_partita_iva("00743110157")  # esempio valido (checksum ok)


def test_partita_iva_non_valida():
    assert not is_partita_iva("00743110158")  # ultima cifra errata
    assert not is_partita_iva("1234567890")   # 10 cifre
    assert not is_partita_iva("abcdefghijk")
    assert not is_partita_iva("")
