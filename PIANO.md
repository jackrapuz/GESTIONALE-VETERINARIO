# Gestionale Fatturazione Studio Veterinario (offline)

## Context
Studio veterinario individuale (P.IVA, **regime ordinario**, cassa **ENPAV**). Serve un
gestionale **desktop 100% offline** per emettere **fatture cartacee/PDF** (NON elettroniche
via SdI, come da normativa STS per le prestazioni sanitarie veterinarie) e per produrre
**flussi separati**: invio dati al Sistema Tessera Sanitaria e registro per il commercialista.
Tutti i dati restano sul PC in un unico SQLite. Utente finale NON tecnico su Windows.

## Stack proposto (decisioni tecniche)
- **Python 3.12** (già installato) + **FastAPI** + **Uvicorn** su `127.0.0.1` (solo localhost).
- Frontend **server-rendered con Jinja2** + vanilla JS minimale → **nessun build step, nessun npm**,
  massima robustezza offline. Un po' di JS solo per il calcolo live della fattura.
- **SQLite** in `dati/gestionale.db` (modalità WAL). Accesso via `sqlite3` stdlib (niente ORM pesante)
  o SQLModel leggero — si valuta in fase 2; default: `sqlite3` + query commentate.
- **PDF: ReportLab** (pure-Python, nessuna dipendenza nativa → si impacchetta in .exe senza problemi
  di GTK come avrebbe WeasyPrint). Layout fattura definito in un modulo dedicato.
- **Excel: openpyxl**; **CSV: stdlib csv**.
- Calcoli monetari con **`decimal.Decimal`** e `ROUND_HALF_UP`, 2 decimali.
- **Packaging: PyInstaller** → `Gestionale.exe` che avvia il server e apre il browser su
  `http://127.0.0.1:<porta>`. In più `avvia.bat` come fallback. Nessuna installazione manuale.
- **Nessuna telemetria, nessuna chiamata di rete in uscita.**

## Layout progetto
```
PROGRAMMA GESTIONALE FRANCI/
├─ dati/                     # gestionale.db + backup (creata al primo avvio)
├─ app/
│  ├─ main.py                # avvio FastAPI + apertura browser
│  ├─ db.py                  # connessione, migrazioni, schema_version
│  ├─ models.py              # dataclass/schema tabelle
│  ├─ calcolo.py             # motore di calcolo fattura (ENPAV, IVA, ritenuta)
│  ├─ numerazione.py         # sequenza progressiva per anno + controllo continuità
│  ├─ validazioni.py         # CF/P.IVA, input
│  ├─ pdf_fattura.py         # generazione PDF (ReportLab)
│  ├─ export_ts.py           # export Sistema TS (usa tracciato_ts.py)
│  ├─ tracciato_ts.py        # *** LAYOUT CAMPI STS ISOLATO E VERSIONATO ***
│  ├─ export_commercialista.py
│  ├─ backup.py              # backup/ripristino DB
│  ├─ routers/               # clienti, pazienti, listino, fatture, export, impostazioni
│  ├─ templates/             # Jinja2 (it-IT)
│  └─ static/                # css/js minimale
├─ dati_esempio/             # seed di collaudo
├─ avvia.bat
├─ requirements.txt
└─ README.md                 # guida passo-passo per utente non tecnico
```

## Modello dati (SQLite)
- **studio** (singola riga, config emittente): denominazione, nome, cognome, codice_fiscale,
  partita_iva, indirizzo (via, cap, citta, prov), email, telefono, iban, regime, n_iscrizione_albo,
  enpav_pct (default 2.00), iva_default_pct (default 22.00), formato_numerazione,
  testo_dicitura_opposizione_ts, logo_path.
- **clienti**: id, tipo (`fisica`/`giuridica`), nome, cognome, ragione_sociale, codice_fiscale,
  partita_iva, via, cap, citta, provincia, email, telefono, sconto_default_pct,
  opposizione_ts_default (bool), sostituto_imposta (bool → abilita ritenuta), note, created_at.
- **pazienti** *(INCLUSA — attività per equini)*: id, cliente_id (FK), nome, specie
  (default `Equino`), razza, microchip, **sesso**, **data_nascita**, **mantello**,
  **passaporto_equino / UELN**, note. Tutti i campi extra opzionali; specie modificabile per
  eventuali altri animali.
- **prestazioni** (listino): id, codice, descrizione, prezzo_unitario, aliquota_iva (default 22),
  tipo_spesa_ts (default `SV`), unita_misura, attiva (bool).
- **fatture**: id, tipo_documento (`fattura`/`nota_credito`), anno, numero_progressivo,
  numero_visualizzato, data_emissione, cliente_id (FK), + **snapshot immutabile** dati cliente
  (denominazione, CF, P.IVA, indirizzo) per garantire immutabilità legale del documento emesso,
  modalita_pagamento, pagamento_tracciato (bool), data_pagamento, stato
  (`emessa`/`incassata`/`annullata`), opposizione_ts (bool), ritenuta_applicata (bool), ritenuta_pct,
  enpav_pct, + totali salvati: imponibile, contributo_enpav, base_iva, iva_totale, ritenuta_importo,
  totale_documento, netto_a_pagare, documento_riferimento_id (per note di credito), note, created_at.
- **righe_fattura**: id, fattura_id (FK), prestazione_id (FK nullable per righe libere), descrizione,
  quantita, prezzo_unitario, sconto_riga_pct, aliquota_iva, tipo_spesa_ts, imponibile_riga.
- **numerazione**: anno, tipo_documento, ultimo_numero (per sequenza senza buchi).
- **schema_version**: versione schema per migrazioni.

Principio chiave: le **fatture emesse sono immutabili** (snapshot dati cliente + totali salvati);
modifiche successive ad anagrafica/listino non alterano documenti già emessi.

## Motore di calcolo (`calcolo.py`) — ordine imposto
1. Per ogni riga: `imponibile_riga = quantità × prezzo × (1 − sconto_riga%)`, poi sconto cliente.
2. Raggruppa per **aliquota IVA**; somma imponibili → **Imponibile**.
3. **Contributo ENPAV 2%** = 2% dell'imponibile (per gruppo aliquota, ripartito
   proporzionalmente se coesistono più aliquote).
4. **Base imponibile IVA** = imponibile + ENPAV (ENPAV incluso nella base IVA).
5. **IVA** = base × aliquota (per gruppo).
6. **Totale documento** = base IVA + IVA.
7. Se ritenuta attiva (solo clienti sostituto d'imposta): `ritenuta = ritenuta_pct × imponibile`;
   **netto a pagare** = totale − ritenuta. La ritenuta NON tocca IVA/totale.
8. Niente marca da bollo (regime con IVA).

## Numerazione (`numerazione.py`)
- Progressiva **per anno**, assegnata **solo all'emissione definitiva**, in transazione atomica.
- Nessun buco, nessuna modifica a ritroso. Funzione `verifica_continuita(anno)` che segnala salti.
- Formato configurabile (default `N/AAAA`, es. `1/2026`).

## Export A — Sistema Tessera Sanitaria
- `tracciato_ts.py`: **layout esatto dei campi isolato, versionato e documentato** (facile aggiornarlo
  quando cambiano le specifiche ufficiali STS). Il resto del codice non conosce il formato.
- Filtro per **anno/periodo in base alla DATA DI PAGAMENTO**.
- Campi per documento: dati emittente, CF proprietario (**omesso se opposizione**), tipo+numero
  documento, data emissione, data pagamento, importo, tipo spesa `SV`, flag pagamento tracciato,
  flag opposizione.
- **Validazioni + report scarti** (record non conformi con motivazione).

## Export B — Commercialista
- **Registro fatture** in CSV **e** Excel, filtrabile per periodo: numero, data, cliente, CF/P.IVA,
  imponibile, contributo ENPAV, aliquota IVA, IVA, totale, stato incasso.
- **Riepilogo IVA per aliquota**.
- **Bundle dei PDF** delle fatture del periodo (cartella/zip).

## Backup / Ripristino (`backup.py`)
- Backup = copia coerente del DB (SQLite backup API) in `dati/backup/backup_AAAAMMGG_HHMM.db`.
- Ripristino = selezione file backup + sostituzione con conferma e backup di sicurezza automatico.

## Fasi di lavoro (commit incrementali su git)
1. **Bootstrap**: init git, scaffolding, requirements, db+migrazioni, `main.py`, `avvia.bat`.
2. **Anagrafiche**: studio (impostazioni), clienti (+ validazione CF/P.IVA), listino prestazioni, pazienti (equini).
3. **Calcolo + Numerazione**: motore `calcolo.py` con test, sequenza per anno + continuità.
4. **Emissione fattura**: UI righe da listino/libere, sconti, flag pagamento/opposizione/ritenuta,
   stati; nota di credito/storno.
5. **PDF fattura**: layout professionale (intestazione, righe, riepilogo con ENPAV come voce
   separata, IVA per aliquota, totale, dicitura opposizione TS quando pertinente).
6. **Export A (STS)**: `tracciato_ts.py` + validazioni + report scarti.
7. **Export B (commercialista)**: CSV/Excel + riepilogo IVA + bundle PDF.
8. **Backup/Ripristino** + **dati di esempio** + **README** + **packaging PyInstaller (.exe)**.

## Verifica (end-to-end)
- Test unitari su `calcolo.py` (ENPAV→base→IVA→totale, mono e multi-aliquota, ritenuta) e
  su `numerazione.py` (continuità, atomicità).
- Test validazioni CF/P.IVA.
- Collaudo manuale: avvio via `avvia.bat`/exe → crea cliente/listino → emetti fattura →
  verifica PDF → genera export STS (con caso opposizione) → export commercialista → backup e
  ripristino. Confronto importi con calcolo atteso su dati di esempio.

## Decisioni confermate dall'utente
1. Anagrafica **pazienti/animali INCLUSA**, ottimizzata per **equini** (campi cavallo opzionali).
2. Sistema operativo di destinazione: **solo Windows** (packaging `.exe` + `avvia.bat`, test su Win 11).
