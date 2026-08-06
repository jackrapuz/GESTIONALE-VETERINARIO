"""Il tipo di spesa Sistema TS e' un elenco chiuso, non testo libero.

**Perche' conta.** Il codice viene copiato nello snapshot immutabile della riga di
fattura al momento dell'emissione. Un valore fuori standard digitato oggi resta
li' per sempre, e nessuno se ne accorge fino al giorno dell'invio al Sistema TS —
quando quel documento viene scartato e non e' piu' correggibile.

I valori ammessi per un iscritto all'albo dei veterinari sono tre, e sono tutti:
Allegato A al DM 19/10/2020, par. 2.6.1.
"""
import pytest

from app.routers.fatture import _righe_da_form
from app.validazioni import (
    TIPI_SPESA_TS, is_tipo_spesa_ts, normalizza_tipo_spesa_ts, valida_tipo_spesa_ts,
)


class FormFinto:
    """Il minimo dell'interfaccia di starlette usata da ``_righe_da_form``."""

    def __init__(self, **liste):
        self._liste = liste

    def getlist(self, nome):
        return self._liste.get(nome, [])


def test_i_tre_codici_del_veterinario_sono_ammessi():
    assert set(TIPI_SPESA_TS) == {"SV", "FV", "AA"}
    for codice in ("SV", "FV", "AA"):
        assert is_tipo_spesa_ts(codice)
        assert valida_tipo_spesa_ts(codice) == []


@pytest.mark.parametrize("valore", ["TK", "XX", "sv1", "spese", "", "  "])
def test_qualunque_altro_codice_viene_respinto(valore):
    errori = valida_tipo_spesa_ts(valore)
    assert errori, f"{valore!r} non doveva passare"
    # Il messaggio deve dire quali sono i codici buoni: chi lo legge non e' tecnico.
    assert "SV" in errori[0] and "FV" in errori[0] and "AA" in errori[0]


def test_il_farmaco_veterinario_non_e_una_spesa_veterinaria():
    """FV e SV sono cose diverse per il Sistema TS: l'export non puo' appiattirle."""
    assert TIPI_SPESA_TS["FV"] != TIPI_SPESA_TS["SV"]
    assert is_tipo_spesa_ts("FV") and is_tipo_spesa_ts("SV")


def test_la_normalizzazione_accetta_il_minuscolo_ma_non_inventa():
    assert normalizza_tipo_spesa_ts("fv") == "FV"
    assert normalizza_tipo_spesa_ts(" sv ") == "SV"
    assert normalizza_tipo_spesa_ts("") == "SV"          # default esplicito
    # Un valore non ammesso NON viene trasformato in qualcosa di valido: deve
    # arrivare intatto alla validazione ed essere respinto, non corretto di
    # nascosto in un codice che la dottoressa non ha scelto.
    assert normalizza_tipo_spesa_ts("TK") == "TK"
    assert valida_tipo_spesa_ts(normalizza_tipo_spesa_ts("TK")) != []


def test_le_righe_di_fattura_normalizzano_il_tipo_di_spesa():
    righe = _righe_da_form(FormFinto(
        r_descrizione=["Visita", "Antibiotico"],
        r_prezzo=["80", "20"],
        r_tipo_spesa=["sv", "fv"],
    ))
    assert [r.tipo_spesa_ts for r in righe] == ["SV", "FV"]


def test_una_riga_senza_tipo_di_spesa_prende_il_default():
    righe = _righe_da_form(FormFinto(r_descrizione=["Visita"], r_prezzo=["80"]))
    assert righe[0].tipo_spesa_ts == "SV"
