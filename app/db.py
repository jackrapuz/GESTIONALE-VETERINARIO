"""Connessione SQLite, schema e migrazioni.

Principi:
- Un unico file DB in ``dati/gestionale.db`` (modalita' WAL per robustezza).
- Accesso via ``sqlite3`` stdlib, niente ORM. Le query stanno nei router/moduli.
- Le migrazioni sono una lista ordinata e *idempotente*: ogni voce porta lo
  schema alla versione successiva. ``schema_version`` (tabella a riga singola)
  tiene traccia della versione applicata. Aggiungere una migrazione = appendere
  una funzione alla lista MIGRATIONS, mai modificarne una gia' rilasciata.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Callable

# Radice per la cartella "dati":
# - in sviluppo: la cartella che contiene "app/";
# - come .exe PyInstaller: la cartella dell'eseguibile (i dati devono restare
#   ACCANTO all'exe e persistere, NON nella cartella temporanea _MEIPASS).
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
DATI_DIR = BASE_DIR / "dati"
DB_PATH = DATI_DIR / "gestionale.db"


def get_conn(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Apre una connessione configurata (WAL, foreign_keys, row_factory).

    ``db_path`` serve principalmente ai test (DB temporaneo). In produzione si
    usa il default ``DB_PATH``.
    """
    path = Path(db_path) if db_path is not None else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Migrazioni
# ---------------------------------------------------------------------------
def _m001_schema_iniziale(conn: sqlite3.Connection) -> None:
    """Schema iniziale completo (v1). Vedi PIANO.md sezione Modello dati."""
    conn.executescript(
        """
        CREATE TABLE studio (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            denominazione TEXT NOT NULL DEFAULT '',
            nome TEXT NOT NULL DEFAULT '',
            cognome TEXT NOT NULL DEFAULT '',
            codice_fiscale TEXT NOT NULL DEFAULT '',
            partita_iva TEXT NOT NULL DEFAULT '',
            via TEXT NOT NULL DEFAULT '',
            cap TEXT NOT NULL DEFAULT '',
            citta TEXT NOT NULL DEFAULT '',
            prov TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            telefono TEXT NOT NULL DEFAULT '',
            iban TEXT NOT NULL DEFAULT '',
            regime TEXT NOT NULL DEFAULT 'ordinario',
            n_iscrizione_albo TEXT NOT NULL DEFAULT '',
            enpav_pct TEXT NOT NULL DEFAULT '2.00',
            iva_default_pct TEXT NOT NULL DEFAULT '22.00',
            formato_numerazione TEXT NOT NULL DEFAULT '{n}/{anno}',
            testo_dicitura_opposizione_ts TEXT NOT NULL DEFAULT
                'Il cliente si oppone alla trasmissione dei dati al Sistema Tessera Sanitaria.',
            logo_path TEXT NOT NULL DEFAULT ''
        );
        -- riga singola di configurazione, creata subito con i default
        INSERT INTO studio (id) VALUES (1);

        CREATE TABLE clienti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL DEFAULT 'fisica' CHECK (tipo IN ('fisica','giuridica')),
            nome TEXT NOT NULL DEFAULT '',
            cognome TEXT NOT NULL DEFAULT '',
            ragione_sociale TEXT NOT NULL DEFAULT '',
            codice_fiscale TEXT NOT NULL DEFAULT '',
            partita_iva TEXT NOT NULL DEFAULT '',
            via TEXT NOT NULL DEFAULT '',
            cap TEXT NOT NULL DEFAULT '',
            citta TEXT NOT NULL DEFAULT '',
            provincia TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            telefono TEXT NOT NULL DEFAULT '',
            sconto_default_pct TEXT NOT NULL DEFAULT '0.00',
            opposizione_ts_default INTEGER NOT NULL DEFAULT 0,
            sostituto_imposta INTEGER NOT NULL DEFAULT 0,
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE pazienti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL REFERENCES clienti(id) ON DELETE CASCADE,
            nome TEXT NOT NULL DEFAULT '',
            specie TEXT NOT NULL DEFAULT 'Equino',
            razza TEXT NOT NULL DEFAULT '',
            microchip TEXT NOT NULL DEFAULT '',
            sesso TEXT NOT NULL DEFAULT '',
            data_nascita TEXT NOT NULL DEFAULT '',
            mantello TEXT NOT NULL DEFAULT '',
            passaporto_ueln TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE prestazioni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codice TEXT NOT NULL DEFAULT '',
            descrizione TEXT NOT NULL DEFAULT '',
            prezzo_unitario TEXT NOT NULL DEFAULT '0.00',
            aliquota_iva TEXT NOT NULL DEFAULT '22.00',
            tipo_spesa_ts TEXT NOT NULL DEFAULT 'SV',
            unita_misura TEXT NOT NULL DEFAULT 'nr',
            attiva INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE fatture (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_documento TEXT NOT NULL DEFAULT 'fattura'
                CHECK (tipo_documento IN ('fattura','nota_credito')),
            anno INTEGER NOT NULL,
            numero_progressivo INTEGER NOT NULL,
            numero_visualizzato TEXT NOT NULL,
            data_emissione TEXT NOT NULL,
            cliente_id INTEGER REFERENCES clienti(id),
            -- snapshot immutabile dei dati cliente al momento dell'emissione
            cli_denominazione TEXT NOT NULL DEFAULT '',
            cli_codice_fiscale TEXT NOT NULL DEFAULT '',
            cli_partita_iva TEXT NOT NULL DEFAULT '',
            cli_indirizzo TEXT NOT NULL DEFAULT '',
            modalita_pagamento TEXT NOT NULL DEFAULT '',
            pagamento_tracciato INTEGER NOT NULL DEFAULT 1,
            data_pagamento TEXT NOT NULL DEFAULT '',
            stato TEXT NOT NULL DEFAULT 'emessa'
                CHECK (stato IN ('emessa','incassata','annullata')),
            opposizione_ts INTEGER NOT NULL DEFAULT 0,
            ritenuta_applicata INTEGER NOT NULL DEFAULT 0,
            ritenuta_pct TEXT NOT NULL DEFAULT '0.00',
            enpav_pct TEXT NOT NULL DEFAULT '2.00',
            -- totali salvati (immutabili) come stringhe Decimal a 2 decimali
            imponibile TEXT NOT NULL DEFAULT '0.00',
            contributo_enpav TEXT NOT NULL DEFAULT '0.00',
            base_iva TEXT NOT NULL DEFAULT '0.00',
            iva_totale TEXT NOT NULL DEFAULT '0.00',
            ritenuta_importo TEXT NOT NULL DEFAULT '0.00',
            totale_documento TEXT NOT NULL DEFAULT '0.00',
            netto_a_pagare TEXT NOT NULL DEFAULT '0.00',
            documento_riferimento_id INTEGER REFERENCES fatture(id),
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE (tipo_documento, anno, numero_progressivo)
        );

        CREATE TABLE righe_fattura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fattura_id INTEGER NOT NULL REFERENCES fatture(id) ON DELETE CASCADE,
            prestazione_id INTEGER REFERENCES prestazioni(id),
            descrizione TEXT NOT NULL DEFAULT '',
            quantita TEXT NOT NULL DEFAULT '1',
            prezzo_unitario TEXT NOT NULL DEFAULT '0.00',
            sconto_riga_pct TEXT NOT NULL DEFAULT '0.00',
            aliquota_iva TEXT NOT NULL DEFAULT '22.00',
            tipo_spesa_ts TEXT NOT NULL DEFAULT 'SV',
            imponibile_riga TEXT NOT NULL DEFAULT '0.00',
            ordine INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE numerazione (
            anno INTEGER NOT NULL,
            tipo_documento TEXT NOT NULL,
            ultimo_numero INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (anno, tipo_documento)
        );

        CREATE INDEX idx_pazienti_cliente ON pazienti(cliente_id);
        CREATE INDEX idx_fatture_cliente ON fatture(cliente_id);
        CREATE INDEX idx_fatture_anno ON fatture(anno);
        CREATE INDEX idx_righe_fattura ON righe_fattura(fattura_id);
        """
    )


def _m002_proforma_e_invio(conn: sqlite3.Connection) -> None:
    """v2: preventivi/proforma, configurazione invio (SMTP) e tracce d'invio.

    - Nuove tabelle ``proforme`` / ``righe_proforma`` (documenti NON fiscali,
      con colonne allineate a ``fatture`` cosi' PDF e calcoli si riusano).
    - Colonne SMTP su ``studio`` (invio email; credenziali solo locali).
    - Colonne su ``fatture`` per collegare la proforma di origine e tracciare
      l'eventuale invio email.
    """
    conn.executescript(
        """
        CREATE TABLE proforme (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anno INTEGER NOT NULL,
            numero_progressivo INTEGER NOT NULL,
            numero_visualizzato TEXT NOT NULL,
            data_emissione TEXT NOT NULL,
            validita_giorni INTEGER NOT NULL DEFAULT 30,
            cliente_id INTEGER REFERENCES clienti(id),
            cli_denominazione TEXT NOT NULL DEFAULT '',
            cli_codice_fiscale TEXT NOT NULL DEFAULT '',
            cli_partita_iva TEXT NOT NULL DEFAULT '',
            cli_indirizzo TEXT NOT NULL DEFAULT '',
            ritenuta_applicata INTEGER NOT NULL DEFAULT 0,
            ritenuta_pct TEXT NOT NULL DEFAULT '0.00',
            enpav_pct TEXT NOT NULL DEFAULT '2.00',
            imponibile TEXT NOT NULL DEFAULT '0.00',
            contributo_enpav TEXT NOT NULL DEFAULT '0.00',
            base_iva TEXT NOT NULL DEFAULT '0.00',
            iva_totale TEXT NOT NULL DEFAULT '0.00',
            ritenuta_importo TEXT NOT NULL DEFAULT '0.00',
            totale_documento TEXT NOT NULL DEFAULT '0.00',
            netto_a_pagare TEXT NOT NULL DEFAULT '0.00',
            stato TEXT NOT NULL DEFAULT 'bozza'
                CHECK (stato IN ('bozza','convertita')),
            fattura_generata_id INTEGER REFERENCES fatture(id),
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE (anno, numero_progressivo)
        );

        CREATE TABLE righe_proforma (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proforma_id INTEGER NOT NULL REFERENCES proforme(id) ON DELETE CASCADE,
            prestazione_id INTEGER REFERENCES prestazioni(id),
            descrizione TEXT NOT NULL DEFAULT '',
            quantita TEXT NOT NULL DEFAULT '1',
            prezzo_unitario TEXT NOT NULL DEFAULT '0.00',
            sconto_riga_pct TEXT NOT NULL DEFAULT '0.00',
            aliquota_iva TEXT NOT NULL DEFAULT '22.00',
            tipo_spesa_ts TEXT NOT NULL DEFAULT 'SV',
            imponibile_riga TEXT NOT NULL DEFAULT '0.00',
            ordine INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX idx_righe_proforma ON righe_proforma(proforma_id);

        ALTER TABLE studio ADD COLUMN smtp_host TEXT NOT NULL DEFAULT '';
        ALTER TABLE studio ADD COLUMN smtp_porta TEXT NOT NULL DEFAULT '587';
        ALTER TABLE studio ADD COLUMN smtp_sicurezza TEXT NOT NULL DEFAULT 'starttls';
        ALTER TABLE studio ADD COLUMN smtp_utente TEXT NOT NULL DEFAULT '';
        ALTER TABLE studio ADD COLUMN smtp_password TEXT NOT NULL DEFAULT '';
        ALTER TABLE studio ADD COLUMN smtp_mittente TEXT NOT NULL DEFAULT '';
        ALTER TABLE studio ADD COLUMN invio_auto_email INTEGER NOT NULL DEFAULT 0;

        ALTER TABLE fatture ADD COLUMN proforma_origine_id INTEGER REFERENCES proforme(id);
        ALTER TABLE fatture ADD COLUMN email_inviata_at TEXT NOT NULL DEFAULT '';

        CREATE INDEX idx_proforme_anno ON proforme(anno);
        """
    )


def _m003_registro_e_cavalli(conn: sqlite3.Connection) -> None:
    """v3: registro delle prestazioni eseguite + cavallo/data sulle righe.

    - ``prestazioni_eseguite``: il diario di lavoro. Una riga = data + cliente +
      cavallo + prestazione + prezzo, annotata quando la prestazione viene fatta.
      Finche' ``fattura_id``/``proforma_id`` restano NULL la voce e' "da
      fatturare"; l'insieme delle voci non fatturate di un cliente e' la sua
      "bozza" implicita. E' una tabella a se': NON tocca ``fatture``, cosi'
      cruscotto, export e numerazione restano invariati.
    - ``clienti.fatturazione_mensile``: caratteristica stabile del cliente
      (rapporto continuativo / piu' cavalli), non una scelta per documento.
    - ``paziente_id`` + ``paziente_nome`` (snapshot) + ``data_prestazione`` sulle
      righe di fattura e proforma: il PDF puo' raggruppare per cavallo con la data
      della singola prestazione, come la fattura cartacea gia' in uso.

    ``paziente_nome`` e' uno snapshot come i dati cliente su ``fatture``: se il
    cavallo viene rinominato o cancellato, il documento emesso non cambia.
    """
    conn.executescript(
        """
        CREATE TABLE prestazioni_eseguite (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_prestazione TEXT NOT NULL,
            cliente_id  INTEGER NOT NULL REFERENCES clienti(id),
            paziente_id INTEGER REFERENCES pazienti(id),
            prestazione_id INTEGER REFERENCES prestazioni(id),
            descrizione TEXT NOT NULL DEFAULT '',
            quantita TEXT NOT NULL DEFAULT '1',
            prezzo_unitario TEXT NOT NULL DEFAULT '0.00',
            sconto_riga_pct TEXT NOT NULL DEFAULT '0.00',
            aliquota_iva TEXT NOT NULL DEFAULT '22.00',
            tipo_spesa_ts TEXT NOT NULL DEFAULT 'SV',
            note TEXT NOT NULL DEFAULT '',
            fattura_id  INTEGER REFERENCES fatture(id),
            proforma_id INTEGER REFERENCES proforme(id),
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX idx_registro_da_fatturare
            ON prestazioni_eseguite(cliente_id, fattura_id);

        ALTER TABLE clienti ADD COLUMN fatturazione_mensile INTEGER NOT NULL DEFAULT 0;

        ALTER TABLE righe_fattura  ADD COLUMN paziente_id INTEGER REFERENCES pazienti(id);
        ALTER TABLE righe_fattura  ADD COLUMN paziente_nome TEXT NOT NULL DEFAULT '';
        ALTER TABLE righe_fattura  ADD COLUMN data_prestazione TEXT NOT NULL DEFAULT '';
        ALTER TABLE righe_proforma ADD COLUMN paziente_id INTEGER REFERENCES pazienti(id);
        ALTER TABLE righe_proforma ADD COLUMN paziente_nome TEXT NOT NULL DEFAULT '';
        ALTER TABLE righe_proforma ADD COLUMN data_prestazione TEXT NOT NULL DEFAULT '';
        """
    )


def _m004_invio_whatsapp(conn: sqlite3.Connection) -> None:
    """v4: l'invio passa da email a WhatsApp.

    ``fatture.whatsapp_at`` registra quando un documento e' stato *preparato* per
    l'invio (PDF generato e messo negli appunti). Non dice che il cliente l'ha
    ricevuto: l'ultimo passo avviene dentro WhatsApp e il programma non lo vede.

    Le colonne SMTP di ``studio`` (``smtp_*``, ``invio_auto_email``) e
    ``fatture.email_inviata_at`` **restano nello schema pur non essendo piu' usate
    da nessuna parte**: in SQLite togliere una colonna vuol dire ricostruire la
    tabella, e non vale il rischio su un database che contiene fatture emesse.
    Sono da considerare morte: nessun codice le legge o le scrive.
    """
    conn.executescript(
        "ALTER TABLE fatture ADD COLUMN whatsapp_at TEXT NOT NULL DEFAULT '';"
    )


# Lista ordinata delle migrazioni. L'indice+1 e' la versione risultante.
MIGRATIONS: list[Callable[[sqlite3.Connection], None]] = [
    _m001_schema_iniziale,
    _m002_proforma_e_invio,
    _m003_registro_e_cavalli,
    _m004_invio_whatsapp,
]


def _get_schema_version(conn: sqlite3.Connection) -> int:
    """Legge la versione di schema tramite ``PRAGMA user_version``.

    Usiamo ``user_version`` (intero interno del file SQLite) invece di una
    tabella dedicata: e' atomico, non richiede setup e non rischia di essere
    letto prima della sua stessa creazione.
    """
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    # PRAGMA non accetta parametri bindati: la versione e' un int controllato.
    conn.execute(f"PRAGMA user_version = {int(version)}")


def init_db(db_path: Path | str | None = None) -> None:
    """Crea/aggiorna il DB applicando le migrazioni mancanti in transazione."""
    conn = get_conn(db_path)
    try:
        current = _get_schema_version(conn)
        target = len(MIGRATIONS)
        for version in range(current, target):
            with conn:  # transazione: commit se ok, rollback se eccezione
                MIGRATIONS[version](conn)
                _set_schema_version(conn, version + 1)
    finally:
        conn.close()
