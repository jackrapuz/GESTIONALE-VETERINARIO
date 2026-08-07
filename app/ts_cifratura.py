"""Cifratura del codice fiscale per il Sistema TS — **manca il certificato**.

Il disciplinare (Allegato A al DM 19/10/2020, par. 4.4) e' esplicito:

    "il dato riguardante il codice fiscale rilevato da parte delle strutture e
    soggetti abilitati, prima di essere trasmesso al sistema TS deve essere
    sempre cifrato utilizzando la chiave pubblica RSA contenuta nel certificato
    X.509 fornito dal sistema TS ed applicando il padding PKCS#1 v1.5"

e in ricezione il Sistema TS esegue "la decifratura del codice fiscale" (par.
4.6). Un codice fiscale in chiaro non passa: e' quello che faceva la versione
precedente dell'export.

**L'algoritmo e' interamente noto** — RSA con la chiave pubblica del certificato,
padding PKCS#1 v1.5, risultato in base64. Manca solo **il certificato**, che si
scarica dall'area riservata di sistemats.it con le credenziali della
professionista. Quando ci sara':

1. metterlo in ``dati/certificato_ts.cer`` (accanto al database, cosi' segue i
   backup e non finisce nel repository, che e' pubblico);
2. aggiungere la dipendenza ``cryptography`` a ``requirements.txt`` — attenzione,
   fa crescere l'eseguibile di una decina di MB;
3. implementare ``cifra_cf`` e togliere il ``NotImplementedError``.

Il codice fiscale e' un dato personale: **non deve essere scritto in chiaro** in
nessun file destinato a uscire dal computer.
"""
from __future__ import annotations

from pathlib import Path

from app.db import DATI_DIR

# Accanto al database: rientra nei backup e non passa mai dal repository.
CERTIFICATO = DATI_DIR / "certificato_ts.cer"

MOTIVO = (
    "Manca il certificato X.509 del Sistema TS per cifrare i codici fiscali. "
    "Va scaricato dall'area riservata di sistemats.it e messo in "
    f"{CERTIFICATO}. Vedi app/ts_cifratura.py."
)


def certificato_presente(percorso: Path | None = None) -> bool:
    return (percorso or CERTIFICATO).exists()


def cifra_cf(cf: str, certificato: Path | None = None) -> str:
    """Codice fiscale cifrato RSA (PKCS#1 v1.5) con la chiave del Sistema TS, in base64."""
    raise NotImplementedError(MOTIVO)
