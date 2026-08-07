"""Versione del programma, in un posto solo.

Serve a rispondere a una domanda che prima non aveva risposta: **quale versione
sta girando su quel computer?** Gli eseguibili si sostituiscono a mano copiando
un file (vedi ``VERSIONI.md``), quindi due cartelle identiche possono contenere
programmi diversi, e finora l'unico modo di distinguerli era confrontare l'hash
del binario con gli zip in ``versioni/``. Scomodo al telefono, che e' proprio la
situazione in cui serve.

**Va alzata a mano a ogni consegna**, insieme al tag git e alla riga in
``VERSIONI.md``: e' la stessa versione scritta li'. Non la ricaviamo da git
perche' nell'exe git non c'e' — il pacchetto PyInstaller contiene solo il codice.
"""
from __future__ import annotations

VERSIONE = "2026.08.07"
