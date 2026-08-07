"""Validazioni di input: Codice Fiscale, Partita IVA, tipo di spesa Sistema TS.

Le funzioni ``valida_*`` restituiscono una lista di messaggi di errore (vuota se
il valore e' valido), cosi' i router possono accumulare piu' errori e mostrarli.
Le funzioni ``is_*`` restituiscono un semplice bool.
"""
from __future__ import annotations

import re

# --- Tipo di spesa per il Sistema Tessera Sanitaria -------------------------
# Valori ammessi per un iscritto all'albo dei veterinari: Allegato A al DM
# 19/10/2020, par. 2.6.1. Non sono tre fra tanti, sono TUTTI quelli previsti.
#
# Perche' e' vincolato: questo valore viene copiato nello snapshot immutabile
# della riga di fattura al momento dell'emissione. Un valore fuori standard
# digitato oggi resta li' per sempre e rende quel documento non trasmissibile,
# senza che niente lo segnali fino al giorno dell'invio al Sistema TS.
TIPI_SPESA_TS: dict[str, str] = {
    "SV": "Spese veterinarie",
    "FV": "Farmaco per uso veterinario",
    "AA": "Altre spese",
}
TIPO_SPESA_TS_DEFAULT = "SV"

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


def is_tipo_spesa_ts(tipo: str) -> bool:
    """True se ``tipo`` e' uno dei codici ammessi per un veterinario."""
    return (tipo or "").strip().upper() in TIPI_SPESA_TS


def normalizza_tipo_spesa_ts(tipo: str) -> str:
    """Codice in maiuscolo, o il default se vuoto. Non inventa: un valore non
    ammesso torna com'e', perche' sia la validazione a respingerlo."""
    t = (tipo or "").strip().upper()
    return t or TIPO_SPESA_TS_DEFAULT


def valida_tipo_spesa_ts(tipo: str) -> list[str]:
    if is_tipo_spesa_ts(tipo):
        return []
    ammessi = ", ".join(f"{k} ({v})" for k, v in TIPI_SPESA_TS.items())
    return [f"Tipo spesa Sistema TS non valido: sono ammessi solo {ammessi}."]


# --- Importi di una riga di fattura -----------------------------------------
# Aliquote IVA italiane in vigore. Non e' un elenco chiuso qui — una prestazione
# esente o non imponibile puo' legittimamente avere 0 — ma serve a fermare i
# valori impossibili PRIMA che finiscano nello snapshot immutabile.
#
# Perche' esiste questo controllo: e' stata emessa davvero una fattura con
# aliquota **2222%** e totale zero. Il campo IVA era largo pochi pixel, il "22"
# che conteneva non si vedeva, e digitandoci dentro e' diventato "2222". Il
# server l'ha accettato senza una parola e ha prodotto un documento che per
# legge non si cancella. Un numero non si giudica solo dal tipo: va guardato se
# ha senso.
ALIQUOTA_IVA_MASSIMA = 100


def valida_percentuale(testo, etichetta: str, massimo: int = 100) -> list[str]:
    """Controlla una percentuale scritta a mano, prima che finisca nel database.

    Serve dove il valore viene **salvato come testo** e riletto molto piu' tardi:
    le percentuali delle Impostazioni (ENPAV, IVA predefinita) sono il caso
    peggiore, perche' passano per ``q2()`` a **ogni** emissione di fattura. Un
    carattere sbagliato salvato li' non da' nessun segnale al momento, e poi
    blocca la fatturazione con un errore che non spiega niente — e chi legge non
    ha modo di collegare la cosa a un campo toccato settimane prima.
    """
    from app.calcolo import ValoreNonNumerico, dec

    testo = str(testo or "").strip()
    if not testo:
        return [f"{etichetta}: manca il valore."]
    try:
        valore = dec(testo)
    except ValoreNonNumerico:
        return [f"{etichetta}: «{testo}» non è un numero."]
    if valore < 0 or valore > massimo:
        return [f"{etichetta} non valida: {valore}%. Dev'essere fra 0 e {massimo}."]
    return []


def valida_importi_riga(descrizione: str, quantita, prezzo, sconto_pct,
                        aliquota) -> list[str]:
    """Controlla che gli importi di una riga siano possibili, non solo numerici."""
    errori: list[str] = []
    dove = f" (riga «{descrizione}»)" if descrizione else ""

    if aliquota < 0 or aliquota > ALIQUOTA_IVA_MASSIMA:
        errori.append(
            f"Aliquota IVA non valida: {aliquota}%{dove}. "
            f"Dev'essere fra 0 e {ALIQUOTA_IVA_MASSIMA}."
        )
    if prezzo < 0:
        errori.append(f"Prezzo negativo{dove}. Per uno storno usa una nota di credito.")
    if quantita <= 0:
        errori.append(f"Quantità dev'essere maggiore di zero{dove}.")
    if sconto_pct < 0 or sconto_pct > 100:
        errori.append(f"Sconto non valido: {sconto_pct}%{dove}. Dev'essere fra 0 e 100.")
    return errori
