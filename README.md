# Gestionale Fatturazione — Studio Veterinario

Programma **desktop, completamente offline** per la fatturazione di uno studio
veterinario individuale (regime ordinario, cassa **ENPAV**). Produce **fatture in
PDF** (cartacee/analogiche, **non** elettroniche via SdI, come previsto per le
prestazioni sanitarie i cui dati vanno al Sistema Tessera Sanitaria) e gestisce le
esportazioni verso il **Sistema TS** e verso il **commercialista** come flussi
separati.

> Tutti i dati restano **solo sul tuo computer**, in un unico file, dentro la
> cartella `dati`. Nessuna connessione a Internet, nessun servizio cloud.

---

## 1. Requisiti

- **Windows 10/11**.
- Nessun requisito se usi l'eseguibile `Gestionale.exe`.
- Solo per l'avvio da sorgente o per creare l'exe: **Python 3.12** installato
  (con l'opzione "Add Python to PATH").

## 2. Avviare il programma

### Modo semplice — eseguibile
1. Fai **doppio clic** su `Gestionale.exe`.
2. Si apre una finestrella nera (il "motore") e in automatico il **browser** sulla
   pagina del gestionale (`http://127.0.0.1:...`).
3. Usa il programma dal browser.
4. Per **chiudere** il programma: chiudi la finestrella nera.

La prima volta viene creata accanto all'exe la cartella **`dati`** con il database.

### Modo alternativo — senza eseguibile
Se non hai l'exe ma hai Python: doppio clic su **`avvia.bat`**. Al primo avvio
prepara l'ambiente (qualche minuto), poi apre il browser. Anche qui si chiude
chiudendo la finestra nera.

## 3. Primo utilizzo (ordine consigliato)

1. **Impostazioni** → inserisci i dati dello studio (denominazione, C.F., P.IVA,
   indirizzo, IBAN, n. iscrizione albo). Qui puoi cambiare: percentuale ENPAV
   (2%), IVA di default (22%), formato del numero fattura e il testo della
   dicitura di opposizione al Sistema TS.
2. **Clienti** → crea i proprietari. Per le persone fisiche il **Codice Fiscale**
   viene validato; puoi impostare uno **sconto di default**, il flag
   **opposizione TS** e (solo per titolari di P.IVA sostituti d'imposta) l'uso
   della **ritenuta d'acconto**.
3. **Pazienti** → gli animali collegati al proprietario (pensato per **equini**:
   nome, razza, microchip, sesso, data di nascita, mantello, passaporto/UELN).
4. **Listino** → le prestazioni con prezzo, IVA e tipo spesa TS (`SV`).
5. **Fatture** → emetti i documenti (vedi sotto).

> Vuoi provare subito con dati finti? Vai in **Backup e manutenzione → Carica dati
> di esempio**.

### Se hai già emesso fatture quest'anno (con altri mezzi)
In **Impostazioni → Continuità numerazione** indica il **prossimo numero** da usare
(es. `24`), così la prima fattura sarà `24/2026` e la numerazione prosegue senza
doppioni. Si può impostare **solo prima** di emettere la prima fattura dell'anno nel
gestionale. Le vecchie fatture in PDF/Word restano valide dove sono: **tienile come
archivio** (non serve reinserirle nel gestionale).

## 4. Emettere una fattura

**Fatture → Nuova fattura**:
- scegli il **cliente** (sconto e opposizione TS si precompilano dai suoi dati);
- aggiungi **righe** dal listino o libere (quantità, prezzo, sconto riga, IVA);
- imposta modalità di pagamento, **pagamento tracciato** (sì/no), stato
  (emessa/incassata) e **data di incasso**;
- il **totale si aggiorna in tempo reale**.

L'ordine di calcolo è: **imponibile → contributo ENPAV 2% → base imponibile IVA →
IVA 22% → totale** (l'ENPAV è incluso nella base IVA). L'eventuale **ritenuta**
riduce solo il *netto a pagare*, non l'IVA né il totale.

Dopo l'emissione, dal dettaglio puoi:
- **Stampa PDF** (fattura professionale con ENPAV come voce separata, IVA per
  aliquota, totale, ed eventuale dicitura di opposizione TS);
- **Invia email** / **WhatsApp** al cliente (vedi punto 6);
- aggiornare lo **stato**/data di incasso;
- creare una **nota di credito** (storno);
- **annullare** il documento (il numero resta usato: la numerazione non ha buchi).

La **numerazione** è automatica, progressiva per anno e non modificabile a
ritroso. La lista fatture segnala eventuali "buchi" nella sequenza.

> I campi per clienti con partita IVA (P.IVA, ritenuta d'acconto) sono sotto
> **"Opzioni avanzate"**: servono solo per i sostituti d'imposta. Il gestionale
> produce fatture **cartacee**, non fatture elettroniche via SdI: eventuali
> documenti che richiedono la e-fattura vanno gestiti altrove/dal commercialista.

## 5. Preventivi (proforma)

In **Preventivi → Nuovo preventivo** crei un documento **non fiscale** con lo
stesso calcolo della fattura e una **validità in giorni**. Dal dettaglio puoi
stamparlo in PDF, inviarlo al cliente, **eliminarlo** oppure **convertirlo in
fattura** (crea una vera fattura con gli stessi importi; il preventivo resta
collegato e segnato come "convertito").

## 6. Invio al cliente (email e WhatsApp)

- **Email**: in *Impostazioni → Invio email (SMTP)* inserisci una sola volta i
  dati del tuo provider (server, porta, sicurezza, utente, password, mittente).
  Poi dal documento premi **Invia email**: parte il PDF allegato all'indirizzo
  del cliente. Puoi anche spuntare *"Invia automaticamente all'emissione"*.
  Le credenziali restano **solo sul tuo computer**; l'invio usa Internet solo in
  quel momento.
- **WhatsApp**: premi **WhatsApp** e si apre WhatsApp con un messaggio già
  pronto per il cliente (il numero è preso dalla sua anagrafica). Il PDF va
  inviato via email o allegato a mano: WhatsApp da link non allega file.

## 7. Esportazioni

**Esportazioni** (scegli il periodo in alto):

- **Sistema Tessera Sanitaria** — file nel tracciato TS per le spese veterinarie,
  filtrato per **data di pagamento**. Il C.F. del proprietario viene **omesso in
  caso di opposizione**. Vengono mostrati i documenti conformi e gli eventuali
  **scarti** (con motivo e report scaricabile).
- **Commercialista** — registro delle fatture del periodo in **Excel** e **CSV**
  (con riepilogo IVA per aliquota) e un **ZIP con le copie PDF** delle fatture.

> Il tracciato del Sistema TS cambia nel tempo: il formato esatto dei campi è
> isolato nel file `app/tracciato_ts.py`, facile da aggiornare senza toccare il
> resto. **Verifica sempre la versione ufficiale corrente prima di un invio reale.**

## 8. Backup e ripristino

**Backup e manutenzione**:
- **Crea backup**: salva una copia del database in `dati/backup`.
- **Scarica copia (.db)**: scarica una copia da conservare altrove (chiavetta, ecc.).
- **Ripristina**: da un backup in elenco o da un file `.db` caricato. Prima del
  ripristino viene creata automaticamente una **copia di sicurezza** del database
  attuale.

Consiglio: fai un backup periodico e conservane una copia fuori dal PC.

## 9. Creare l'eseguibile (per chi sviluppa)

Con Python 3.12: doppio clic su **`costruisci_exe.bat`**. Al termine trovi
`dist\Gestionale.exe`. Copialo dove vuoi: al primo avvio creerà accanto a sé la
cartella `dati`.

## 10. Note fiscali

- Regime **ordinario**: IVA in fattura (default 22%, modificabile per prestazione).
- **ENPAV 2%** in rivalsa sul cliente, incluso nella base imponibile IVA.
- **Niente marca da bollo** (si applica solo alle fatture senza IVA).
- **Ritenuta d'acconto**: disattivata di default, solo per clienti sostituti d'imposta.

## 11. Struttura del progetto

```
app/            codice dell'applicazione (server, calcolo, PDF, export, backup)
  routers/      pagine web (clienti, pazienti, listino, fatture, export, backup)
  templates/    pagine HTML (in italiano)
  static/       CSS e JavaScript
  tracciato_ts.py   *** layout campi Sistema TS, isolato e versionato ***
dati/           database e backup (creata automaticamente; NON versionata)
dati_esempio/   dati finti per il collaudo
tests/          test automatici
avvia.bat            avvio senza eseguibile
costruisci_exe.bat   creazione di Gestionale.exe
```

## 12. Verifica tecnica (facoltativa)

Con l'ambiente attivo: `python -m pytest` esegue i test automatici
(calcolo, numerazione, validazioni ed emissione fatture).
