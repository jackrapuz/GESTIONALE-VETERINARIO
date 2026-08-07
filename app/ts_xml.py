"""Scrittura del file XML per il Sistema TS — **non ancora implementabile**.

Questa e' una cucitura, non un lavoro dimenticato: il modello dei dati
(``tracciato_ts.py``) e' completo e verificato, ma tradurlo in XML richiede
materiale che non e' pubblico.

**Cosa manca, esattamente:**

1. **L'XSD corrente delle spese veterinarie** — nomi degli elementi, loro ordine,
   cardinalita' e formati. Sta nell'area riservata di sistemats.it ("Documenti e
   specifiche tecniche"), raggiungibile con le credenziali della professionista.
2. **Il certificato X.509 del Sistema TS**, per cifrare i codici fiscali: vedi
   ``ts_cifratura.py``.

**Cosa gia' si sa** (Allegato A al DM 19/10/2020, cap. 3), e che il modello
rispetta gia':

    Precompilata
      +- identificativo del soggetto che emette (CF del professionista)
      +- DocumentoFiscale *
           +- IdSpesa (P.IVA + data emissione + identificativo)
           +- data pagamento, flag pagamento anticipato, flag operazione
           +- codice fiscale assistito (cifrato)
           +- modalita' pagamento, tipo documento
           +- VoceSpesa * (tipologia + importo)

Il file va poi **compresso**: il Sistema TS verifica l'integrita' "attraverso la
corretta decompressione del file e della decifratura del codice fiscale" (par.
4.6), e lo zip caricato sul portale non puo' superare i 5 MB.

**Perche' non l'ho scritto lo stesso, indovinando.** E' esattamente cosi' che era
nata la versione precedente di questo modulo: un tracciato "bozza" mai
confrontato con il documento ufficiale, che sembrava funzionare e produceva un
file che il portale avrebbe respinto. Un generatore XML plausibile ma sbagliato
e' peggio di uno assente, perche' non si distingue da uno giusto finche' non
scade il termine di invio.
"""
from __future__ import annotations

from app.tracciato_ts import Fornitura

MOTIVO = (
    "Il file XML per il Sistema TS non e' ancora generabile: servono l'XSD "
    "corrente delle spese veterinarie e il certificato X.509 per la cifratura "
    "dei codici fiscali, entrambi nell'area riservata di sistemats.it. "
    "Vedi app/ts_xml.py."
)


def disponibile() -> bool:
    """True quando la generazione dell'XML e' implementata.

    L'interfaccia esiste gia' cosi' che la pagina delle esportazioni possa dire
    la verita' all'utente invece di offrire un file che verrebbe respinto.
    """
    return False


def serializza(fornitura: Fornitura, cifra_cf) -> bytes:
    """Il file XML della fornitura, con i codici fiscali cifrati da ``cifra_cf``.

    ``cifra_cf`` viene iniettato invece di essere importato perche' e' l'unico
    punto in cui i codici fiscali in chiaro lasciano il programma: passarlo dal
    chiamante lo rende visibile e sostituibile nei test.
    """
    raise NotImplementedError(MOTIVO)
