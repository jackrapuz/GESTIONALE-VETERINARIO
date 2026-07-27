"""Tracciato del Sistema Tessera Sanitaria — SPESE VETERINARIE (isolato e versionato).

===========================================================================
 IMPORTANTE — LEGGERE PRIMA DI MODIFICARE
===========================================================================
Le specifiche tecniche ufficiali del Sistema TS cambiano nel tempo (ordine dei
campi, separatore, codifiche, formato date). Per questo **tutto il layout vive
qui**: il resto del codice (``export_ts.py``, i router) non conosce l'ordine dei
campi ne' la loro formattazione. Per adeguarsi a una nuova versione del tracciato
basta aggiornare questo file — in particolare la lista ``CAMPI`` e le costanti in
alto — senza toccare la logica di estrazione/validazione.

Riferimento: portale Sistema TS, sezione "Spese Veterinarie" (documento tecnico
del formato di trasmissione). Verificare SEMPRE la versione corrente prima di un
invio reale e allineare ``VERSIONE_TRACCIATO`` e ``CAMPI``.
===========================================================================
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

# --- Parametri di formato (aggiornabili) -----------------------------------
VERSIONE_TRACCIATO = "SV-2026-bozza"   # allineare al documento tecnico ufficiale
SEPARATORE = ";"                        # separatore campi del CSV
TIPO_DOCUMENTO_TS = "F"                 # 'F' = fattura
TIPO_SPESA_DEFAULT = "SV"               # spese veterinarie
FLAG_SI = "1"
FLAG_NO = "0"


def _data_ts(valore: str) -> str:
    """Data nel formato del tracciato (GG/MM/AAAA). Input atteso 'AAAA-MM-GG'."""
    v = (valore or "").strip()
    if len(v) >= 10 and v[4] == "-":
        return f"{v[8:10]}/{v[5:7]}/{v[0:4]}"
    return v


def _importo_ts(valore) -> str:
    """Importo con 2 decimali e punto come separatore (es. '99.55')."""
    try:
        return f"{Decimal(str(valore)):.2f}"
    except Exception:
        return "0.00"


# --- Definizione dichiarativa dei campi ------------------------------------
@dataclass
class Campo:
    nome: str
    descrizione: str
    estrai: Callable[[dict], str]   # dal record grezzo -> stringa del tracciato
    obbligatorio: bool = True
    valida: Callable[[str], str | None] | None = None  # ritorna errore o None


def _valida_cf(v: str) -> str | None:
    # CF vuoto e' lecito SOLO se c'e' opposizione (gestito a livello di record).
    if v and len(v) not in (11, 16):
        return "Codice fiscale proprietario di lunghezza non valida"
    return None


def _valida_importo(v: str) -> str | None:
    try:
        if Decimal(v) <= 0:
            return "Importo non positivo"
    except Exception:
        return "Importo non numerico"
    return None


# L'ORDINE di questa lista = l'ordine delle colonne nel file. Aggiornare qui per
# adeguarsi al tracciato ufficiale corrente.
CAMPI: list[Campo] = [
    Campo("cf_proprietario", "Codice fiscale del proprietario (omesso se opposizione)",
          lambda r: "" if r["opposizione"] else r["cf_proprietario"],
          obbligatorio=False, valida=_valida_cf),
    Campo("tipo_documento", "Tipo documento (F=fattura)",
          lambda r: TIPO_DOCUMENTO_TS),
    Campo("numero_documento", "Numero del documento",
          lambda r: r["numero_documento"]),
    Campo("data_emissione", "Data di emissione (GG/MM/AAAA)",
          lambda r: _data_ts(r["data_emissione"])),
    Campo("data_pagamento", "Data di pagamento (GG/MM/AAAA)",
          lambda r: _data_ts(r["data_pagamento"])),
    Campo("tipo_spesa", "Tipologia di spesa (SV=veterinaria)",
          lambda r: r.get("tipo_spesa") or TIPO_SPESA_DEFAULT),
    Campo("importo", "Importo pagato (comprensivo di IVA e contributo)",
          lambda r: _importo_ts(r["importo"]), valida=_valida_importo),
    Campo("pagamento_tracciato", "Flag pagamento tracciato (1/0)",
          lambda r: FLAG_SI if r["pagamento_tracciato"] else FLAG_NO),
    Campo("flag_opposizione", "Flag opposizione invio al Sistema TS (1/0)",
          lambda r: FLAG_SI if r["opposizione"] else FLAG_NO),
]


def intestazione() -> list[str]:
    """Riga di intestazione (nomi colonna). Utile per lettura umana/debug."""
    return [c.nome for c in CAMPI]


def costruisci_riga(record: dict) -> list[str]:
    """Trasforma un record grezzo (vedi ``export_ts._record_da_fattura``) nella
    lista ordinata di stringhe secondo ``CAMPI``."""
    return [c.estrai(record) for c in CAMPI]


def valida_record(record: dict) -> list[str]:
    """Valida un record e restituisce la lista di errori (vuota se conforme)."""
    errori: list[str] = []
    valori = {c.nome: c.estrai(record) for c in CAMPI}
    # Regola trasversale: senza opposizione il CF proprietario e' obbligatorio.
    if not record["opposizione"] and not record.get("cf_proprietario"):
        errori.append("Codice fiscale proprietario mancante (nessuna opposizione)")
    for c in CAMPI:
        v = valori[c.nome]
        if c.obbligatorio and not v:
            errori.append(f"Campo obbligatorio mancante: {c.nome}")
        if c.valida:
            e = c.valida(v)
            if e:
                errori.append(e)
    return errori
