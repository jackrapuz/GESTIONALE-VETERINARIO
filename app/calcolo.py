"""Motore di calcolo della fattura.

Ordine dei calcoli imposto da PIANO.md (sezione "Motore di calcolo"):

1. Per ogni riga: imponibile = quantita x prezzo x (1 - sconto_riga%), poi si
   applica lo sconto cliente.
2. Raggruppamento per aliquota IVA; somma imponibili -> Imponibile.
3. Contributo ENPAV (default 2%) sull'imponibile, per gruppo aliquota.
4. Base imponibile IVA = imponibile + ENPAV (ENPAV incluso nella base IVA).
5. IVA = base x aliquota, per gruppo.
6. Totale documento = base IVA + IVA.
7. Ritenuta (solo clienti sostituto d'imposta) = ritenuta% x imponibile;
   netto a pagare = totale - ritenuta. La ritenuta NON tocca IVA/totale.
8. Nessuna marca da bollo (regime con IVA).

Tutti gli importi monetari sono ``Decimal`` arrotondati a 2 decimali con
ROUND_HALF_UP. Gli arrotondamenti avvengono a livello di riga e di gruppo, mai
sui float: il denaro non passa mai per ``float``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")


class ValoreNonNumerico(ValueError):
    """Quel che e' stato scritto in un campo importo non e' un numero."""


def dec(valore) -> Decimal:
    """Converte in Decimal in modo sicuro (via str per evitare imprecisioni float).

    Accetta le due notazioni che entrano davvero in questo programma:

    - quella **del database**, con il punto decimale (``"45.00"``);
    - quella **italiana**, che e' come si scrive un prezzo a mano — virgola
      decimale, e punto per le migliaia (``"1.234,56"``).

    Si distinguono guardando se compaiono entrambi i segni: se c'e' anche la
    virgola, allora il punto e' un separatore di migliaia e va tolto. Prima
    ``"1.234,56"`` sollevava ``decimal.InvalidOperation`` e la pagina moriva con
    un errore di sistema, per un prezzo scritto nel modo piu' naturale possibile.

    Su un valore che numero non e' solleva :class:`ValoreNonNumerico`, non zero:
    un importo che sparisce in silenzio e' il difetto che ha gia' prodotto una
    fattura da 0,00 euro senza che nessuno se ne accorgesse.
    """
    if isinstance(valore, Decimal):
        return valore
    if valore is None or valore == "":
        return Decimal("0")
    testo = str(valore).strip()
    if "," in testo:
        testo = testo.replace(".", "").replace(",", ".")
    try:
        return Decimal(testo)
    except InvalidOperation:
        raise ValoreNonNumerico(f"«{valore}» non è un numero.") from None


def q2(valore) -> Decimal:
    """Arrotonda a 2 decimali con ROUND_HALF_UP."""
    return dec(valore).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class RigaInput:
    descrizione: str
    quantita: Decimal
    prezzo_unitario: Decimal
    aliquota_iva: Decimal
    sconto_riga_pct: Decimal = Decimal("0")
    tipo_spesa_ts: str = "SV"
    prestazione_id: int | None = None
    # Cavallo e data della prestazione: opzionali, attraversano il calcolo
    # invariati per finire sulla riga del documento (vedi RigaCalcolata).
    paziente_id: int | None = None
    paziente_nome: str = ""
    data_prestazione: str = ""


@dataclass
class RigaCalcolata:
    descrizione: str
    quantita: Decimal
    prezzo_unitario: Decimal
    aliquota_iva: Decimal
    sconto_riga_pct: Decimal
    tipo_spesa_ts: str
    prestazione_id: int | None
    imponibile_riga: Decimal
    paziente_id: int | None = None
    paziente_nome: str = ""
    data_prestazione: str = ""


@dataclass
class GruppoIva:
    aliquota: Decimal
    imponibile: Decimal
    enpav: Decimal
    base_iva: Decimal
    iva: Decimal


@dataclass
class RisultatoFattura:
    righe: list[RigaCalcolata] = field(default_factory=list)
    gruppi_iva: list[GruppoIva] = field(default_factory=list)
    imponibile: Decimal = Decimal("0.00")
    contributo_enpav: Decimal = Decimal("0.00")
    base_iva: Decimal = Decimal("0.00")
    iva_totale: Decimal = Decimal("0.00")
    ritenuta_importo: Decimal = Decimal("0.00")
    totale_documento: Decimal = Decimal("0.00")
    netto_a_pagare: Decimal = Decimal("0.00")


def _pct(base: Decimal, percentuale: Decimal) -> Decimal:
    """base x percentuale/100 (senza arrotondamento intermedio)."""
    return base * percentuale / Decimal("100")


def calcola_fattura(
    righe: list[RigaInput],
    *,
    sconto_cliente_pct: Decimal | str | float = Decimal("0"),
    enpav_pct: Decimal | str | float = Decimal("2"),
    ritenuta_applicata: bool = False,
    ritenuta_pct: Decimal | str | float = Decimal("0"),
) -> RisultatoFattura:
    """Calcola totali e ripartizione IVA a partire dalle righe."""
    sconto_cliente_pct = dec(sconto_cliente_pct)
    enpav_pct = dec(enpav_pct)
    ritenuta_pct = dec(ritenuta_pct)

    ris = RisultatoFattura()

    # 1) Imponibile per riga: sconto riga poi sconto cliente. Arrotondato a 2 dec.
    for r in righe:
        qta = dec(r.quantita)
        prezzo = dec(r.prezzo_unitario)
        lordo = qta * prezzo
        dopo_sconto_riga = lordo * (Decimal("1") - _pct(Decimal("1"), r.sconto_riga_pct))
        dopo_sconto_cliente = dopo_sconto_riga * (
            Decimal("1") - _pct(Decimal("1"), sconto_cliente_pct)
        )
        imp_riga = q2(dopo_sconto_cliente)
        ris.righe.append(
            RigaCalcolata(
                descrizione=r.descrizione,
                quantita=qta,
                prezzo_unitario=prezzo,
                aliquota_iva=dec(r.aliquota_iva),
                sconto_riga_pct=dec(r.sconto_riga_pct),
                tipo_spesa_ts=r.tipo_spesa_ts,
                prestazione_id=r.prestazione_id,
                imponibile_riga=imp_riga,
                paziente_id=r.paziente_id,
                paziente_nome=r.paziente_nome,
                data_prestazione=r.data_prestazione,
            )
        )

    # 2) Raggruppamento per aliquota (ordine di prima comparsa, stabile).
    imponibili_per_aliquota: dict[str, Decimal] = {}
    ordine_aliquote: list[str] = []
    for rc in ris.righe:
        chiave = str(rc.aliquota_iva)
        if chiave not in imponibili_per_aliquota:
            imponibili_per_aliquota[chiave] = Decimal("0.00")
            ordine_aliquote.append(chiave)
        imponibili_per_aliquota[chiave] += rc.imponibile_riga

    # 3-5) Per ogni gruppo: ENPAV sull'imponibile, base IVA, IVA.
    for chiave in ordine_aliquote:
        aliquota = Decimal(chiave)
        imponibile_gruppo = q2(imponibili_per_aliquota[chiave])
        enpav_gruppo = q2(_pct(imponibile_gruppo, enpav_pct))
        base_gruppo = q2(imponibile_gruppo + enpav_gruppo)
        iva_gruppo = q2(_pct(base_gruppo, aliquota))
        ris.gruppi_iva.append(
            GruppoIva(
                aliquota=aliquota,
                imponibile=imponibile_gruppo,
                enpav=enpav_gruppo,
                base_iva=base_gruppo,
                iva=iva_gruppo,
            )
        )

    # Totali di documento come somma dei gruppi (gia' arrotondati).
    ris.imponibile = q2(sum((g.imponibile for g in ris.gruppi_iva), Decimal("0")))
    ris.contributo_enpav = q2(sum((g.enpav for g in ris.gruppi_iva), Decimal("0")))
    ris.base_iva = q2(sum((g.base_iva for g in ris.gruppi_iva), Decimal("0")))
    ris.iva_totale = q2(sum((g.iva for g in ris.gruppi_iva), Decimal("0")))

    # 6) Totale documento.
    ris.totale_documento = q2(ris.base_iva + ris.iva_totale)

    # 7) Ritenuta sull'imponibile (solo se sostituto d'imposta). Non tocca il totale.
    if ritenuta_applicata:
        ris.ritenuta_importo = q2(_pct(ris.imponibile, ritenuta_pct))
    ris.netto_a_pagare = q2(ris.totale_documento - ris.ritenuta_importo)

    return ris
