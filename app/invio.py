"""Invio dei documenti al cliente via WhatsApp.

**Perche' non l'email.** C'era un invio SMTP: chiedeva server, porta, utente e
password del provider, e la password finiva nel database. Per un unico utente che
manda i documenti dal telefono e' complicazione pura, quindi e' stato rimosso.

**Perche' non l'API di WhatsApp.** L'API ufficiale (WhatsApp Business Cloud)
vuole un account business, un numero dedicato, token da rinnovare e messaggi su
modello approvato, ed e' a pagamento. Le librerie che pilotano WhatsApp Web
"facendo finta di essere un umano" si rompono a ogni aggiornamento e violano i
termini d'uso. Nessuna delle due strade e' adatta a questo programma.

**Come funziona qui.** Tre pezzi, tutti locali:

1. il PDF viene salvato in ``dati/da_inviare`` (resta li', ritrovabile);
2. il file viene messo negli **appunti di Windows** *come file*, non come testo,
   cosi' nella chat basta un Ctrl+V;
3. si apre la chat del cliente col messaggio gia' scritto — l'applicazione se c'e'
   (:func:`link_whatsapp_app`), altrimenti WhatsApp Web (:func:`link_whatsapp_web`).

Il programma non puo' attaccare l'allegato da solo: deve **consegnare il file** a
chi manda. La pagina d'invio quindi lo mostra e lo rende afferrabile — si trascina
nella chat, si scarica, o si incolla dagli appunti (vedi
``templates/invio_whatsapp.html``).

**Quale via funzioni dipende da dove si lascia il file, ed e' stato misurato.**
Trascinare consegna un documento vero solo verso l'**applicazione** WhatsApp, che
per Windows e' un programma come gli altri. Se il bersaglio e' una **pagina web**
— WhatsApp Web — il browser toglie di mezzo il ``DownloadURL`` e consegna solo
l'indirizzo del PDF: nella chat finirebbe un ``http://127.0.0.1:...`` che al
cliente non serve, e che smette di funzionare appena il gestionale si chiude. Su
WhatsApp Web quindi vale il Ctrl+V, non il trascinamento.

Resta comunque un gesto umano finale, ed e' voluto: e' l'ultimo controllo prima che
il documento parta.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

from app.db import DATI_DIR

# I PDF preparati per l'invio: accanto ai dati, non in una cartella temporanea,
# cosi' se l'incollata va storta il file e' ancora la'.
CARTELLA_INVII = DATI_DIR / "da_inviare"

# Evita il lampo della finestra di console: l'app gira senza terminale.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class TelefonoMancante(Exception):
    """Il cliente non ha un numero di telefono in anagrafica."""


def normalizza_telefono(telefono: str, prefisso_default: str = "39") -> str:
    """Numero in formato internazionale senza simboli (es. '393401234567').

    Rimuove spazi/segni; se manca il prefisso internazionale assume l'Italia.

    **Due trappole italiane, entrambe pagate.** Bastava una di queste perche'
    WhatsApp si aprisse su un numero inesistente invece che sulla chat giusta:

    1. *Un numero che comincia per 39 non ha per forza il prefisso.* ``391``,
       ``392`` e ``393`` sono prefissi di cellulare veri: riconoscerli come
       "gia' internazionale" lasciava il numero senza prefisso. Si distinguono
       dalla **lunghezza** — con il prefisso un cellulare fa 12 cifre, senza ne
       fa 10 — non da come comincia.
    2. *Lo zero dei fissi non va tolto.* In Italia il prefisso urbano ``0`` fa
       parte del numero anche in forma internazionale: Bologna e' ``+39 051``,
       non ``+39 51``. La regola "togli gli zeri iniziali" vale altrove (Francia,
       Regno Unito), non qui.
    """
    t = re.sub(r"[^\d+]", "", telefono or "")
    if t.startswith("+"):
        return t[1:]
    if t.startswith("00"):
        return t[2:]
    # Gia' internazionale solo se e' abbastanza lungo da esserlo davvero: un
    # numero nazionale che comincia per 39 e' un cellulare 39x di 10 cifre.
    if t.startswith(prefisso_default) and len(t) >= 11:
        return t
    return prefisso_default + t


def link_whatsapp_app(telefono: str, testo: str) -> str:
    """Indirizzo che apre **l'applicazione WhatsApp** dritta sulla chat.

    E' la via preferita per due motivi, non uno:

    - **Apre la chat, non una pagina di passaggio.** ``wa.me`` — quello che c'era
      prima — non e' un collegamento alla conversazione: e' una pagina di WhatsApp
      con un pulsante "Continua sulla chat", da cui ogni volta si sceglie fra
      applicazione e Web, e che a volte finisce sulla pagina di scaricamento.
    - **Il trascinamento del PDF funziona.** L'applicazione e' un programma di
      Windows, non una pagina web, e il documento le arriva come file vero. Verso
      una pagina web il browser consegna solo l'indirizzo (vedi
      ``templates/invio_whatsapp.html``), che al cliente non serve a niente.

    Se l'applicazione non e' installata non succede nulla: per questo la pagina
    offre accanto :func:`link_whatsapp_web`.
    """
    numero = normalizza_telefono(telefono)
    return f"whatsapp://send?phone={numero}&text={quote(testo)}"


def link_whatsapp_web(telefono: str, testo: str) -> str:
    """Indirizzo che apre **WhatsApp Web** dritto sulla chat, senza intermezzi.

    La riserva per chi non ha l'applicazione sul computer. Apre la conversazione
    giusta come l'altro, ma essendo una pagina web il PDF va incollato con
    Ctrl+V o allegato con la graffetta: trascinarlo non lo consegna.
    """
    numero = normalizza_telefono(telefono)
    return f"https://web.whatsapp.com/send?phone={numero}&text={quote(testo)}"


def testo_messaggio(studio: dict, f: dict) -> str:
    """Testo predefinito del messaggio WhatsApp per un documento."""
    tipo = "nota di credito" if f.get("tipo_documento") == "nota_credito" else \
           ("preventivo" if f.get("tipo_documento") == "proforma" else "fattura")
    nome_studio = (studio.get("denominazione")
                   or f"{studio.get('nome','')} {studio.get('cognome','')}").strip()
    return (
        f"Gentile {f.get('cli_denominazione', 'cliente')},\n"
        f"in allegato trova la {tipo} n. {f.get('numero_visualizzato')} "
        f"del {f.get('data_emissione')}, per un totale di € {f.get('totale_documento')}.\n"
        f"Cordiali saluti,\n{nome_studio}"
    )


def nome_file_documento(f: dict) -> str:
    """Nome del PDF: leggibile dal cliente e valido come nome file su Windows."""
    tipo = {"nota_credito": "nota_credito", "proforma": "preventivo"}.get(
        f.get("tipo_documento", ""), "fattura")
    numero = str(f.get("numero_visualizzato", "")).replace("/", "-")
    return f"{tipo}_{numero}.pdf"


def salva_pdf_da_inviare(nome_file: str, contenuto: bytes) -> Path:
    """Scrive il PDF in ``dati/da_inviare`` e ne restituisce il percorso."""
    CARTELLA_INVII.mkdir(parents=True, exist_ok=True)
    percorso = CARTELLA_INVII / nome_file
    percorso.write_bytes(contenuto)
    return percorso


def copia_negli_appunti(percorso: Path) -> bool:
    """Mette il file negli appunti di Windows, cosi' Ctrl+V lo allega in WhatsApp.

    Serve un *file drop list*, non del testo: lo fa ``Set-Clipboard -LiteralPath``.
    PowerShell viene chiamato con ``-STA`` perche' le API degli appunti di Windows
    funzionano solo in un apartment a thread singolo.

    Ritorna ``False`` invece di sollevare: se gli appunti non si popolano l'invio
    e' comunque possibile allegando il file a mano, e la pagina lo spiega.
    """
    if sys.platform != "win32":
        return False
    # Nelle stringhe PowerShell tra apici singoli, l'apice si raddoppia.
    letterale = str(percorso).replace("'", "''")
    try:
        esito = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-STA", "-Command",
             f"Set-Clipboard -LiteralPath '{letterale}'"],
            capture_output=True, timeout=20, creationflags=_NO_WINDOW,
        )
        return esito.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def prepara_invio_whatsapp(studio: dict, f: dict, pdf: bytes, telefono: str) -> dict:
    """Prepara tutto per l'invio: PDF su disco, negli appunti, link alla chat.

    Solleva :class:`TelefonoMancante` se il cliente non ha un numero: senza quello
    non c'e' chat da aprire, ed e' meglio dirlo che aprire WhatsApp sul vuoto.
    """
    if not (telefono or "").strip():
        raise TelefonoMancante(
            "Questo cliente non ha un numero di telefono in anagrafica.")
    percorso = salva_pdf_da_inviare(nome_file_documento(f), pdf)
    testo = testo_messaggio(studio, f)
    return {
        "percorso": percorso,
        "cartella": str(percorso.parent),
        "negli_appunti": copia_negli_appunti(percorso),
        # Due indirizzi, non uno: il primo apre l'applicazione, il secondo il Web.
        # Quale funzioni dipende da com'e' quel computer, e il programma non puo'
        # saperlo — quindi li offre entrambi invece di indovinare.
        "link_app": link_whatsapp_app(telefono, testo),
        "link_web": link_whatsapp_web(telefono, testo),
        "numero": normalizza_telefono(telefono),
    }
