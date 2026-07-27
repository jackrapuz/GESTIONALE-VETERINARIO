"""Test del motore di calcolo. Valori attesi verificati a mano."""
from decimal import Decimal

from app.calcolo import RigaInput, calcola_fattura


def _riga(prezzo, aliquota="22", qta="1", sconto="0"):
    return RigaInput(
        descrizione="X",
        quantita=Decimal(qta),
        prezzo_unitario=Decimal(prezzo),
        aliquota_iva=Decimal(aliquota),
        sconto_riga_pct=Decimal(sconto),
    )


def test_mono_aliquota_base():
    r = calcola_fattura([_riga("100.00")], enpav_pct="2")
    assert r.imponibile == Decimal("100.00")
    assert r.contributo_enpav == Decimal("2.00")
    assert r.base_iva == Decimal("102.00")
    assert r.iva_totale == Decimal("22.44")
    assert r.totale_documento == Decimal("124.44")
    assert r.ritenuta_importo == Decimal("0.00")
    assert r.netto_a_pagare == Decimal("124.44")


def test_ritenuta_non_tocca_totale():
    r = calcola_fattura(
        [_riga("100.00")], enpav_pct="2",
        ritenuta_applicata=True, ritenuta_pct="20",
    )
    assert r.totale_documento == Decimal("124.44")  # invariato
    assert r.ritenuta_importo == Decimal("20.00")   # 20% dell'imponibile
    assert r.netto_a_pagare == Decimal("104.44")


def test_multi_aliquota():
    r = calcola_fattura([_riga("100.00", "22"), _riga("50.00", "10")], enpav_pct="2")
    assert r.imponibile == Decimal("150.00")
    assert r.contributo_enpav == Decimal("3.00")
    assert r.base_iva == Decimal("153.00")
    assert r.iva_totale == Decimal("27.54")  # 22.44 + 5.10
    assert r.totale_documento == Decimal("180.54")
    aliquote = {str(g.aliquota): g for g in r.gruppi_iva}
    assert aliquote["22"].iva == Decimal("22.44")
    assert aliquote["10"].iva == Decimal("5.10")


def test_sconto_riga_e_cliente():
    r = calcola_fattura(
        [_riga("50.00", "22", qta="2", sconto="10")],  # 100 -> 90
        sconto_cliente_pct="10",                        # 90 -> 81
        enpav_pct="2",
    )
    assert r.imponibile == Decimal("81.00")
    assert r.contributo_enpav == Decimal("1.62")
    assert r.base_iva == Decimal("82.62")
    assert r.iva_totale == Decimal("18.18")  # 82.62 * 22% = 18.1764 -> 18.18
    assert r.totale_documento == Decimal("100.80")


def test_nessuna_riga():
    r = calcola_fattura([], enpav_pct="2")
    assert r.imponibile == Decimal("0.00")
    assert r.totale_documento == Decimal("0.00")
    assert r.netto_a_pagare == Decimal("0.00")


def test_importi_sono_due_decimali():
    r = calcola_fattura([_riga("33.33", "22")], enpav_pct="2")
    for valore in (r.imponibile, r.contributo_enpav, r.base_iva,
                   r.iva_totale, r.totale_documento, r.netto_a_pagare):
        assert valore.as_tuple().exponent == -2
