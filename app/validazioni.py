"""Validazioni di input: Codice Fiscale e Partita IVA italiani.

Le funzioni ``valida_*`` restituiscono una lista di messaggi di errore (vuota se
il valore e' valido), cosi' i router possono accumulare piu' errori e mostrarli.
Le funzioni ``is_*`` restituiscono un semplice bool.
"""
from __future__ import annotations

import re

# --- Codice Fiscale persona fisica (16 caratteri alfanumerici) --------------
_CF_RE = re.compile(r"^[A-Z0-9]{16}$")

# Tabelle ufficiali per il carattere di controllo del CF.
_CF_DISPARI = {
    "0": 1, "1": 0, "2": 5, "3": 7, "4": 9, "5": 13, "6": 15, "7": 17, "8": 19,
    "9": 21, "A": 1, "B": 0, "C": 5, "D": 7, "E": 9, "F": 13, "G": 15, "H": 17,
    "I": 19, "J": 21, "K": 2, "L": 4, "M": 18, "N": 20, "O": 11, "P": 3, "Q": 6,
    "R": 8, "S": 12, "T": 14, "U": 16, "V": 10, "W": 22, "X": 25, "Y": 24, "Z": 23,
}
_CF_PARI = {
    "0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
    "A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6, "H": 7, "I": 8, "J": 9,
    "K": 10, "L": 11, "M": 12, "N": 13, "O": 14, "P": 15, "Q": 16, "R": 17, "S": 18,
    "T": 19, "U": 20, "V": 21, "W": 22, "X": 23, "Y": 24, "Z": 25,
}
_CF_RESTO = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def is_codice_fiscale(cf: str) -> bool:
    """True se ``cf`` e' un CF persona fisica formalmente valido (con check char)."""
    cf = (cf or "").strip().upper()
    if not _CF_RE.match(cf):
        return False
    somma = 0
    for i, ch in enumerate(cf[:15]):
        # posizione 1-based: dispari usa tabella dispari, pari usa tabella pari
        somma += _CF_DISPARI[ch] if (i % 2 == 0) else _CF_PARI[ch]
    return _CF_RESTO[somma % 26] == cf[15]


def is_partita_iva(piva: str) -> bool:
    """True se ``piva`` e' una P.IVA italiana valida (11 cifre, checksum Luhn-IT)."""
    piva = (piva or "").strip()
    if not re.match(r"^\d{11}$", piva):
        return False
    somma = 0
    for i, ch in enumerate(piva[:10]):
        n = int(ch)
        if i % 2 == 0:  # posizioni dispari (1-based)
            somma += n
        else:  # posizioni pari: raddoppia e, se >9, sottrai 9
            d = n * 2
            somma += d - 9 if d > 9 else d
    controllo = (10 - (somma % 10)) % 10
    return controllo == int(piva[10])


def valida_codice_fiscale(cf: str, *, obbligatorio: bool = False) -> list[str]:
    cf = (cf or "").strip()
    if not cf:
        return ["Codice Fiscale obbligatorio."] if obbligatorio else []
    return [] if is_codice_fiscale(cf) else ["Codice Fiscale non valido."]


def valida_partita_iva(piva: str, *, obbligatorio: bool = False) -> list[str]:
    piva = (piva or "").strip()
    if not piva:
        return ["Partita IVA obbligatoria."] if obbligatorio else []
    return [] if is_partita_iva(piva) else ["Partita IVA non valida (attese 11 cifre)."]
