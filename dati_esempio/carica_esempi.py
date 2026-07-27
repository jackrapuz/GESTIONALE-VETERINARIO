"""Carica un piccolo set di dati di esempio per il collaudo.

Inserisce dati SOLO dove le tabelle sono vuote, cosi' e' sicuro da lanciare su
un'installazione nuova senza rischiare duplicati o sovrascritture. Puo' essere
eseguito da riga di comando (``python -m dati_esempio.carica_esempi``) oppure
richiamato dall'app (pagina Backup e manutenzione).
"""
from __future__ import annotations

from app.calcolo import RigaInput
from app.db import get_conn, init_db
from app.fatturazione import emetti_fattura

STUDIO = {
    "denominazione": "Dott.ssa Giulia Bianchi — Medico Veterinario",
    "nome": "Giulia", "cognome": "Bianchi",
    "codice_fiscale": "BNCGLI85T55F205X", "partita_iva": "12345678903",
    "via": "Via delle Scuderie 12", "cap": "40100", "citta": "Bologna", "prov": "BO",
    "email": "studio@example.it", "telefono": "051 1234567",
    "iban": "IT60X0542811101000000123456", "n_iscrizione_albo": "BO 1234",
}

CLIENTI = [
    # (tipo, nome, cognome, ragione_sociale, CF, P.IVA, via, cap, citta, prov, email, sconto, opp, sost)
    ("fisica", "Marco", "Verdi", "", "VRDMRC80A01H501U", "", "Via dei Prati 5", "40100", "Bologna", "BO", "marco.verdi@example.it", "0.00", 0, 0),
    ("fisica", "Laura", "Neri", "", "NRELRA90E45A944T", "", "Strada del Maneggio 8", "40050", "Monterenzio", "BO", "laura.neri@example.it", "5.00", 0, 0),
    ("giuridica", "", "", "Scuderia Il Galoppo S.r.l.", "", "03456789012", "Via Ippica 100", "40060", "Ozzano", "BO", "info@ilgaloppo.example.it", "10.00", 0, 1),
]

PAZIENTI = [
    # (indice_cliente, nome, razza, microchip, sesso, data_nascita, mantello, passaporto)
    (0, "Fulmine", "Sella Italiano", "380260123456781", "M", "2015-04-12", "Baio", "IT01512345678"),
    (1, "Stella", "Purosangue Arabo", "380260123456782", "F", "2018-06-30", "Grigio", "IT01812345679"),
    (2, "Tornado", "Trottatore", "380260123456783", "M", "2013-03-05", "Sauro", "IT01312345680"),
]

PRESTAZIONI = [
    # (codice, descrizione, prezzo, aliquota, tipo_ts, unita)
    ("VIS", "Visita clinica generale", "60.00", "22.00", "SV", "prestazione"),
    ("VAC", "Vaccinazione", "35.00", "22.00", "SV", "prestazione"),
    ("DEN", "Pareggio e ferratura (controllo dentale)", "45.00", "22.00", "SV", "prestazione"),
    ("ECO", "Ecografia tendinea", "90.00", "22.00", "SV", "prestazione"),
    ("FAR", "Somministrazione farmaco", "18.00", "22.00", "SV", "prestazione"),
]


def carica_dati_esempio(conn) -> dict:
    riepilogo = {"studio": False, "clienti": 0, "pazienti": 0, "prestazioni": 0, "fatture": 0}

    if not (conn.execute("SELECT denominazione FROM studio WHERE id=1").fetchone()[0] or "").strip():
        set_clause = ", ".join(f"{k}=?" for k in STUDIO)
        conn.execute(f"UPDATE studio SET {set_clause} WHERE id=1", list(STUDIO.values()))
        riepilogo["studio"] = True

    if conn.execute("SELECT COUNT(*) FROM clienti").fetchone()[0] == 0:
        ids = []
        for c in CLIENTI:
            cur = conn.execute(
                "INSERT INTO clienti (tipo,nome,cognome,ragione_sociale,codice_fiscale,"
                "partita_iva,via,cap,citta,provincia,email,sconto_default_pct,"
                "opposizione_ts_default,sostituto_imposta) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", c)
            ids.append(cur.lastrowid)
        riepilogo["clienti"] = len(ids)
        for p in PAZIENTI:
            conn.execute(
                "INSERT INTO pazienti (cliente_id,nome,razza,microchip,sesso,data_nascita,"
                "mantello,passaporto_ueln) VALUES (?,?,?,?,?,?,?,?)",
                (ids[p[0]], p[1], p[2], p[3], p[4], p[5], p[6], p[7]))
        riepilogo["pazienti"] = len(PAZIENTI)

    if conn.execute("SELECT COUNT(*) FROM prestazioni").fetchone()[0] == 0:
        for pr in PRESTAZIONI:
            conn.execute(
                "INSERT INTO prestazioni (codice,descrizione,prezzo_unitario,aliquota_iva,"
                "tipo_spesa_ts,unita_misura,attiva) VALUES (?,?,?,?,?,?,1)", pr)
        riepilogo["prestazioni"] = len(PRESTAZIONI)

    # Chiudiamo la transazione degli inserimenti: emetti_fattura apre una propria
    # transazione (BEGIN IMMEDIATE) e non puo' annidarsi.
    conn.commit()

    # Due fatture di esempio (solo se non ci sono documenti).
    if conn.execute("SELECT COUNT(*) FROM fatture").fetchone()[0] == 0:
        clienti = conn.execute("SELECT * FROM clienti ORDER BY id").fetchall()
        if clienti:
            emetti_fattura(
                conn, cliente=clienti[0],
                righe=[RigaInput("Visita clinica generale", 1, "60", "22"),
                       RigaInput("Vaccinazione", 1, "35", "22")],
                data_emissione="2026-02-15", modalita_pagamento="Bonifico",
                pagamento_tracciato=True, data_pagamento="2026-02-15", stato="incassata")
            emetti_fattura(
                conn, cliente=clienti[1],
                righe=[RigaInput("Ecografia tendinea", 1, "90", "22")],
                sconto_cliente_pct="5", data_emissione="2026-03-10",
                modalita_pagamento="Contanti", pagamento_tracciato=False,
                data_pagamento="2026-03-10", stato="incassata")
            riepilogo["fatture"] = 2

    conn.commit()
    return riepilogo


def main() -> None:
    init_db()
    conn = get_conn()
    try:
        r = carica_dati_esempio(conn)
    finally:
        conn.close()
    print("Dati di esempio caricati:", r)


if __name__ == "__main__":
    main()
