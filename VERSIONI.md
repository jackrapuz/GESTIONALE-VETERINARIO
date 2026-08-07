# Versioni consegnate e come tornare indietro

Ogni versione consegnata ha **due cose che devono restare accoppiate**: un tag git
(il sorgente) e un pacchetto in `versioni/` (il programma costruito da quel
sorgente). I binari non stanno nel repository — è pubblico e decine di MB per
versione lo appesantirebbero per sempre — quindi `versioni/` vive solo in
locale ed è la sola copia. **Non svuotarla.**

| Data | Tag | Pacchetto in `versioni/` | Forma | Cosa contiene |
|---|---|---|---|---|
| 2026-07-31 | `46d38fa` (main) | `gestionale_2026-07-31_pre-pdf.zip` | file unico | Prima della consegna del PDF. L'invio WhatsApp poggiava solo sugli appunti |
| 2026-08-05 | `v2026.08.05-pdf-whatsapp` | `gestionale_2026-08-05_pdf-whatsapp.zip` | file unico | Il PDF si trascina nella chat, si scarica e si vede in anteprima |
| 2026-08-06 | `v2026.08.06-export` | `gestionale_2026-08-06_export.zip` | file unico | Export commercialista con importi sommabili; modello dati Sistema TS; tipo spesa vincolato a FV/SV/AA |
| 2026-08-07 | `v2026.08.07-cartella` | `gestionale_2026-08-07_cartella.zip` | **cartella** | Versione visibile, chat WhatsApp diretta, campi delle fatture leggibili, chiusura immediata, pacchetto a cartella |

### Impronte (SHA256 di `Gestionale.exe`)

Servono a riconoscere una copia senza aprirla. Dalla versione 2026.08.07 c'è un
modo più comodo: il numero è scritto **in fondo a ogni pagina** del gestionale e
nella quarta riga di `http://127.0.0.1:8420/salute`.

| Versione | SHA256 |
|---|---|
| 2026-07-31 | `EDFD508ED4DC81501CE99DE03045C59D0A788BF9CC074A3E1E444C97D004620B` |
| 2026-08-05 | `A7501CAD8A3F3C66EA5DDF2A2ED1AF43976A40A88B5F15CBA8D8E9F320354874` |
| 2026-08-06 | `760193A0A56B46DF98C98F7220077AE55901514340FBCE248B453259556E5B95` |
| 2026-08-07 | `3DED55E9CDFE61CFEC56F85E8D8EE671418EBF60CA106C2A13A1C0207501C3CB` |

## Da file unico a cartella (2026-08-07)

Fino alla 2026.08.06 si consegnava **un solo file**, `Gestionale.exe`. Portava
l'archivio dentro di sé e a ogni avvio lo scompattava in `%TEMP%\_MEIxxxxx`, per
cancellarlo alla chiusura. Quando la cancellazione non riusciva — un antivirus
che teneva aperto un file, una chiusura forzata — la cartella restava: ne sono
state trovate **21 abbandonate, per 290 MB**, e ogni tanto compariva l'errore
*"impossibile eliminare un file temporaneo"*.

Ora si consegna una **cartella** `Gestionale`, che contiene:

    Gestionale\
      Gestionale.exe          il programma
      _internal\              le librerie: senza questa cartella l'exe non parte
      GUIDA.html              la guida
      crea_collegamento.bat   crea l'icona sul Desktop
      dati\                   creata al primo avvio: DB, backup, PDF preparati

Niente da scompattare, niente da cancellare, il difetto sparisce alla radice.
In più l'avvio scende da 4,75 s a 3,8 s e l'eseguibile non resta più bloccato
dopo la chiusura (era la causa dei `PermissionError [WinError 5]` nelle
ricostruzioni).

**La cartella `dati` resta accanto all'eseguibile, quindi ora sta dentro la
cartella del programma.** È una scelta, non una conseguenza: è ciò che permette
di rimettere in quella stessa cartella un eseguibile *file unico* già consegnato
e ritrovare lo stesso archivio. Spostare i dati altrove renderebbe cieche tutte
le versioni precedenti — esattamente il disastro che questo documento esiste per
evitare.

## Aggiornare

1. Chiudere il gestionale dal pulsante **Chiudi il gestionale** in fondo alla
   pagina. Windows blocca un programma in esecuzione: senza questo la copia
   fallisce.
2. Estrarre il pacchetto nuovo **sopra la cartella esistente**, rispondendo
   *Sostituisci i file nella destinazione*.
3. **Non cancellare la cartella per far posto a quella nuova: contiene `dati`.**
   Sostituire sì, cancellare no.

Il collegamento sul Desktop punta al percorso della cartella, quindi continua a
funzionare senza rifarlo.

## Tornare indietro

Stessa procedura con il pacchetto della versione precedente. Tornando a una
versione *file unico*, si mette il suo `Gestionale.exe` nella cartella e si
ignora `_internal\`: l'exe onefile non la guarda, e trova `dati` accanto a sé
come si aspetta.

**Il ritorno è sicuro finché nessuna versione introduce una migrazione dello
schema.** Le migrazioni sono in avanti soltanto (`app/db.py`, lista
`MIGRATIONS`): una volta che il database è salito di versione, un eseguibile più
vecchio troverebbe colonne che non conosce. Fino a `v2026.08.07-cartella` lo
schema è fermo a **4** e nessuna delle versioni qui sopra lo cambia, quindi si
può andare avanti e indietro liberamente — **verificato con gli eseguibili veri**,
non solo affermato.

Dalla prima versione che aggiungerà una migrazione, tornare indietro richiederà
anche il ripristino di un backup del database precedente (menu **Backup**). Da
segnare in questa tabella quando succederà.

## Ricostruire da un tag

    git checkout v2026.08.07-cartella
    .\costruisci_exe.bat

Il pacchetto in `versioni/` esiste proprio per non doverlo fare: ricostruire da
capo dà un binario diverso byte per byte, e in caso di problemi conviene tornare
esattamente a quello che girava.

## Quando si consegna una versione nuova

Le quattro cose vanno insieme, e se una resta indietro il resto diventa
inaffidabile:

1. alzare il numero in `app/versione.py` (è quello che si legge nel piede delle
   pagine: se resta indietro, il programma dichiara una versione che non è la
   sua, il che è peggio del non dire niente);
2. aggiungere la riga nella tabella qui sopra, con data, tag e impronta;
3. creare il tag git;
4. archiviare lo zip della cartella in `versioni/`.
