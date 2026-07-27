"""Invio dei documenti al cliente: email (SMTP) e link WhatsApp.

Coerente col modello offline-first: l'app non usa alcun servizio cloud; l'invio
email parte dal PC via SMTP (configurato in Impostazioni, credenziali salvate solo
in locale) e richiede Internet solo nel momento dell'invio. Per WhatsApp si genera
un link ``wa.me`` con messaggio precompilato: sara' l'utente a premere invio
(niente API a pagamento, niente automazioni non ufficiali).
"""
from __future__ import annotations

import re
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import quote


class ConfigurazioneMancante(Exception):
    """Sollevata quando manca la configurazione SMTP o l'email del destinatario."""


def _mittente(studio: dict) -> str:
    return (studio.get("smtp_mittente") or studio.get("smtp_utente") or studio.get("email") or "").strip()


def invia_email(
    studio: dict,
    *,
    destinatario: str,
    oggetto: str,
    corpo: str,
    allegati: list[tuple[str, bytes, str]] | None = None,
) -> None:
    """Invia un'email con eventuali allegati usando l'SMTP configurato in ``studio``.

    ``allegati`` = lista di (nome_file, contenuto_bytes, sottotipo_mime) es.
    ("fattura.pdf", b"...", "pdf"). Solleva ``ConfigurazioneMancante`` o le
    eccezioni di ``smtplib`` in caso di problemi (gestite dal chiamante).
    """
    host = (studio.get("smtp_host") or "").strip()
    mittente = _mittente(studio)
    if not host or not mittente:
        raise ConfigurazioneMancante(
            "Configura server SMTP e mittente in Impostazioni prima di inviare email.")
    if not (destinatario or "").strip():
        raise ConfigurazioneMancante("Il cliente non ha un indirizzo email.")

    porta = int(str(studio.get("smtp_porta") or "587").strip() or "587")
    sicurezza = (studio.get("smtp_sicurezza") or "starttls").strip().lower()
    utente = (studio.get("smtp_utente") or "").strip()
    password = studio.get("smtp_password") or ""

    msg = EmailMessage()
    msg["From"] = mittente
    msg["To"] = destinatario
    msg["Subject"] = oggetto
    msg.set_content(corpo)
    for nome, dati, sottotipo in (allegati or []):
        msg.add_attachment(dati, maintype="application", subtype=sottotipo, filename=nome)

    if sicurezza == "ssl":
        with smtplib.SMTP_SSL(host, porta, context=ssl.create_default_context(), timeout=30) as s:
            if utente:
                s.login(utente, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, porta, timeout=30) as s:
            if sicurezza == "starttls":
                s.starttls(context=ssl.create_default_context())
            if utente:
                s.login(utente, password)
            s.send_message(msg)


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
    """Testo predefinito del messaggio (email/WhatsApp) per un documento."""
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
