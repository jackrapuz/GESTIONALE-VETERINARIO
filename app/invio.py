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
3. si apre ``wa.me`` sul numero del cliente con il messaggio gia' scritto.

Il programma non puo' attaccare l'allegato da solo: deve **consegnare il file** a
chi manda. La pagina d'invio quindi lo mostra e lo rende afferrabile — si trascina
nella chat, si scarica, o si incolla dagli appunti — e trascinare e' la via
principale perche' non dipende dagli appunti, che qualunque altra copia sovrascrive
(vedi ``templates/invio_whatsapp.html``).

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
    """
    t = re.sub(r"[^\d+]", "", telefono or "")
    if t.startswith("+"):
        return t[1:]
    if t.startswith("00"):
        return t[2:]
    if t.startswith(prefisso_default):
        return t
    return prefisso_default + t.lstrip("0")


def link_whatsapp(telefono: str, testo: str) -> str:
    """Costruisce un link wa.me con messaggio precompilato."""
    numero = normalizza_telefono(telefono)
    return f"https://wa.me/{numero}?text={quote(testo)}"


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
    return {
        "percorso": percorso,
        "cartella": str(percorso.parent),
        "negli_appunti": copia_negli_appunti(percorso),
        "link": link_whatsapp(telefono, testo_messaggio(studio, f)),
        "numero": normalizza_telefono(telefono),
    }
