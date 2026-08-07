"""Istanza Jinja2 condivisa + filtri di formattazione italiani.

Centralizzata qui cosi' che ``main.py`` e i router usino lo stesso ambiente
(stessi filtri, stessa cartella template).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.validazioni import TIPI_SPESA_TS

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def euro(valore) -> str:
    """Formatta un importo come '1.234,56' (separatori italiani, senza simbolo)."""
    try:
        d = Decimal(str(valore))
    except (InvalidOperation, ValueError, TypeError):
        return str(valore)
    # 12345.6 -> '12,345.67' (US) -> swap in '12.345,67' (IT)
    grezzo = f"{d:,.2f}"
    return grezzo.replace(",", "§").replace(".", ",").replace("§", ".")


def data_it(valore) -> str:
    """Converte 'AAAA-MM-GG' (o date/datetime) in 'GG/MM/AAAA'. Vuoto se assente."""
    if not valore:
        return ""
    if isinstance(valore, (date, datetime)):
        return valore.strftime("%d/%m/%Y")
    testo = str(valore)
    try:
        return datetime.strptime(testo[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return testo


def si_no(valore) -> str:
    return "Sì" if valore else "No"


templates.env.filters["euro"] = euro
templates.env.filters["data_it"] = data_it
templates.env.filters["si_no"] = si_no

# I codici di spesa del Sistema TS servono a due form (listino e registro) e sono
# un elenco chiuso di legge: come globale evitano di essere passati a mano da ogni
# router, e soprattutto evitano che qualcuno ne riscriva a mano una copia.
templates.env.globals["TIPI_SPESA_TS"] = TIPI_SPESA_TS
