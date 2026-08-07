# Versioni consegnate e come tornare indietro

Ogni versione consegnata ha **due cose che devono restare accoppiate**: un tag git
(il sorgente) e un pacchetto in `versioni/` (l'eseguibile costruito da quel
sorgente). Gli eseguibili non stanno nel repository — è pubblico e un binario da
30 MB per versione lo appesantirebbe per sempre — quindi `versioni/` vive solo in
locale ed è la sola copia. **Non svuotarla.**

| Data | Tag | Pacchetto in `versioni/` | Cosa contiene |
|---|---|---|---|
| 2026-07-31 | `46d38fa` (main) | `gestionale_2026-07-31_pre-pdf.zip` | Prima della consegna del PDF. L'invio WhatsApp poggiava solo sugli appunti |
| 2026-08-05 | `v2026.08.05-pdf-whatsapp` | `gestionale_2026-08-05_pdf-whatsapp.zip` | Il PDF si trascina nella chat, si scarica e si vede in anteprima |
| 2026-08-06 | `v2026.08.06-export` | `gestionale_2026-08-06_export.zip` | Export commercialista con importi sommabili; modello dati Sistema TS; tipo spesa vincolato a FV/SV/AA |

## Quale versione sta girando

In fondo a ogni pagina del gestionale, sotto il pulsante di chiusura: **versione
2026.08.07**. È la domanda da fare al telefono quando qualcosa non torna, prima
di qualsiasi altra: la stessa cartella può contenere programmi diversi, perché
l'aggiornamento è una copia di file fatta a mano.

Da programma risponde anche `http://127.0.0.1:8420/salute`, quarta riga.

Il numero sta in `app/versione.py`, in un posto solo. **Va alzato a mano a ogni
consegna**, insieme al tag e alla riga nella tabella qui sopra — se resta
indietro, il gestionale dichiara una versione che non è la sua, che è peggio del
non dire niente.

## Aggiornare

1. Chiudere il gestionale dal pulsante **Chiudi il gestionale** in fondo alla
   pagina. Windows blocca un `.exe` in esecuzione: senza questo la copia fallisce.
2. Copiare il nuovo `Gestionale.exe` **nella stessa cartella**, sostituendo il
   vecchio. Il collegamento sul Desktop punta al percorso, quindi continua a
   funzionare.
3. Non toccare la cartella `dati`.

## Tornare indietro

Stessa procedura con il pacchetto della versione precedente: si sostituisce solo
l'eseguibile, i dati restano dove sono.

**Il ritorno è sicuro finché nessuna versione introduce una migrazione dello
schema.** Le migrazioni sono in avanti soltanto (`app/db.py`, lista `MIGRATIONS`):
una volta che il database è salito di versione, un eseguibile più vecchio
troverebbe colonne che non conosce. Fino a `v2026.08.06-export` lo schema è fermo
a **4** e nessuna delle versioni qui sopra lo cambia, quindi si può andare avanti
e indietro liberamente.

Dalla prima versione che aggiungerà una migrazione, tornare indietro richiederà
anche il ripristino di un backup del database precedente (menu **Backup**). Da
segnare in questa tabella quando succederà.

## Ricostruire un eseguibile da un tag

    git checkout v2026.08.05-pdf-whatsapp
    .\costruisci_exe.bat

Il pacchetto in `versioni/` esiste proprio per non doverlo fare: ricostruire da
capo dà un binario diverso byte per byte, e in caso di problemi conviene tornare
esattamente a quello che girava.
