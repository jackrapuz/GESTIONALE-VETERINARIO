"""Punto di avvio per l'eseguibile (PyInstaller) e per l'esecuzione diretta.

Equivale a ``python -m app.main`` ma come singolo script, cosi' PyInstaller ha
un entry point chiaro. Avvia il server locale e apre il browser.
"""
from app.main import main

if __name__ == "__main__":
    main()
