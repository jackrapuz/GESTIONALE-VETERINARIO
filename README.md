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

## 2. Avviare e chiudere il programma

### Modo semplice — eseguibile
1. Fai **doppio clic** su `Gestionale.exe` (o sul collegamento *Gestionale Studio*
   sul Desktop, creato da `crea_collegamento.bat`).
2. **Non compare nessuna finestra nera**: si apre direttamente il **browser** sulla
   pagina del gestionale (`http://127.0.0.1:...`).
3. Per **chiudere** il programma: pulsante **"Chiudi il gestionale"** in fondo a
   qualsiasi pagina, **oppure semplicemente chiudi il browser** — vedi sotto.

### Vive quanto vive la finestra del browser
Senza console, chiudere il browser lasciava il server vivo e **invisibile**: nessun
segno che fosse acceso e nessun modo di fermarlo se non il Gestione attività (con
l'effetto collaterale che il file `Gestionale.exe` resta bloccato e non si può
sostituire con un nuovo build).

Il primo tentativo era un **battito a timer** dalla pagina. Sbagliato: il gestionale
si tiene aperto tutto il giorno mentre si lavora ad altro, e così la vita del
programma dipendeva da un timer JavaScript in una scheda in secondo piano — che
Chrome rallenta, e che in certi casi (scheda scartata per memoria, sospensione del
computer) ferma del tutto. Il programma si spegneva con la pagina ancora aperta.

Ora vale una **connessione aperta**:

- ogni pagina tiene un flusso SSE su **`GET /presenza`** (`base.html`, `EventSource`);
- il server **conta i flussi** (`pagine_aperte()` in `app/main.py`). Finché ce n'è
  almeno uno il gestionale vive, **senza limiti di tempo**;
- chiudendo la finestra è il sistema operativo a chiudere la connessione. Il flusso
  se ne accorge con `request.is_disconnected()` e decrementa il contatore;
- `_guardiano` (thread demone) spegne quando il contatore è a zero **e** non
  arrivano richieste da `GRAZIA_SECONDI` (30 s). La doppia condizione copre la
  pagina vecchia rimasta in cache, senza il flusso.

Nessun timer nella pagina, quindi la limitazione delle schede nascoste non conta.

**Due trappole, entrambe già pagate:**

1. **`timeout_graceful_shutdown=3` nella `uvicorn.Config` non è decorativo.** Il
   default è `None`: uvicorn aspetta *senza limite* che le richieste in corso
   finiscano, e `/presenza` è fatto per non finire mai — "Chiudi il gestionale"
   resterebbe appeso per sempre. Il flusso molla da sé controllando `should_exit`;
   il timeout è la rete di sicurezza. C'è un test che verifica entrambe le cose.
2. **`TestClient` non serve a provare il flusso**: chiudendo la risposta aspetta che
   il generatore finisca, e il generatore aspetta il segnale di scollegamento che
   arriverebbe solo dopo — si bloccano a vicenda e il test si appende. In
   `tests/test_avvio.py` la presenza si prova con un **uvicorn vero** e un socket
   (fixture `server_vero`), che è anche il percorso del browser.

La pagina di commiato (`spento.html`) riceve `senza_presenza`: non deve aprire un
flusso verso un server che sta morendo.

### Un secondo doppio clic non apre una seconda scheda
`/salute` è la carta d'identità dell'istanza e risponde con **tre righe**: nome del
programma, **cartella dati servita**, numero di pagine aperte. All'avvio,
`_gia_in_esecuzione()` interroga le porte 8420-8422 e riusa un'istanza **solo se la
cartella dati combacia** (`_stessa_installazione()`).

Perché è importante: prima bastava che rispondesse "gestionale". Con un server di
sviluppo acceso sulla radice del progetto e l'exe sui propri dati, il doppio clic
portava **sull'archivio sbagliato**, in silenzio. Per un gestionale di fatture è il
difetto peggiore possibile. Un'istanza che non dichiara la cartella (versione
vecchia) non viene riusata: meglio avviarne una propria che indovinare.

Se l'istanza trovata ha **già una pagina aperta**, il secondo avvio non apre una
scheda nuova: porta davanti la finestra del browser che la sta mostrando
(`_porta_in_primo_piano()`, Win32 via `ctypes`, nessuna dipendenza). Cerca una
finestra visibile il cui titolo contenga `Gestionale Veterinario` — è il suffisso
del `<title>` di ogni pagina. È **best effort**: se la scheda del gestionale non è
quella attiva nella sua finestra, il titolo non compare e si ricade sull'apertura
del browser.

### Se il pulsante non può chiudere, lo dice
`/spegni` ferma il server tramite l'oggetto `uvicorn.Server` che `main()` mette in
`_server`. Avviando dalla **CLI di uvicorn** (`python -m uvicorn app.main:app`)
quell'oggetto non esiste: prima la pagina diceva "Gestionale chiuso" comunque e il
server restava vivo. È così che è nato un **orfano rimasto in piedi tre giorni**
sulla porta 8420, invisibile e con codice vecchio, che occupava la porta preferita
dell'exe. Ora la pagina dice che non ha potuto chiuderlo e rimanda a Ctrl+C.

In sviluppo si ferma con **Ctrl+C**, oppure si avvia con `python -m app.main`
(che passa da `main()`, quindi il pulsante funziona).

La prima volta viene creata accanto all'exe la cartella **`dati`** con il database.
Se l'avvio fallisce non c'è una console dove leggere l'errore: compare una
**finestrella di Windows** e il dettaglio finisce in `dati/avvio.log`.

### Modo alternativo — senza eseguibile
Se non hai l'exe ma hai Python: doppio clic su **`avvia.bat`**. Al primo avvio
prepara l'ambiente (qualche minuto), poi apre il browser. Questo è l'unico modo di
avvio che *ha* una finestra di terminale, perché serve a vedere gli errori in
sviluppo.

> **Guida per l'utente finale:** `GUIDA.html` (doppio clic, si apre nel browser) è
> scritta per Francesca, per scenari e non per funzioni. Va tenuta accanto all'exe.
> Si rigenera con lo script `build_guida.py`; se rinomini un pulsante
> dell'interfaccia, aggiorna anche la guida.

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
5. **Registro** → annota le prestazioni mentre le fai; da lì nascono le fatture.
6. **Fatture** → emetti i documenti (vedi sotto).

> Vuoi provare subito con dati finti? Vai in **Backup e manutenzione → Carica dati
> di esempio**.

### Se hai già emesso fatture quest'anno (con altri mezzi)
In **Impostazioni → Continuità numerazione** indica il **prossimo numero** da usare
(es. `24`), così la prima fattura sarà `24/2026` e la numerazione prosegue senza
doppioni. Si può impostare **solo prima** di emettere la prima fattura dell'anno nel
gestionale. Le vecchie fatture in PDF/Word restano valide dove sono: **tienile come
archivio** (non serve reinserirle nel gestionale).

## 4. Registro delle prestazioni (il percorso normale)

Il **Registro** è il diario di lavoro: si annota la prestazione appena eseguita
(data, cliente, cavallo, prestazione dal listino, prezzo) senza pensare alle
fatture. Ogni voce resta **"da fatturare"** finché non entra in un documento.

- **Registro → + Annota prestazione**: trenta secondi, in stalla.
- Il cliente con **"Fatturazione mensile"** spuntata in anagrafica accumula le
  prestazioni; a fine mese **"Fattura il mese"** produce **una** fattura con le
  righe **raggruppate per cavallo** e la data di ognuna (come la fattura cartacea).
  **"Proforma (riepilogo mese)"** fa lo stesso in forma non fiscale, **senza
  consumare** le voci.
- Il cliente occasionale si fattura subito con **"Fattura ora"**.
- Una voce annotata per errore si toglie con la **×** accanto alla riga, ma **solo
  finché non è fatturata**: dopo, il rimedio è la nota di credito. Essere collegata
  a una proforma non blocca l'eliminazione (la proforma non è fiscale).

Il prezzo annotato è quello di **listino**: lo sconto di anagrafica del cliente
viene applicato all'emissione, così fatturare dal registro o a mano dà lo stesso
totale.

## 5. Emettere una fattura

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
- **Invia con WhatsApp** al cliente (vedi punto 7);
- aggiornare lo **stato**/data di incasso;
- creare una **nota di credito** (storno);
- **annullare** il documento (il numero resta usato: la numerazione non ha buchi).

La **numerazione** è automatica, progressiva per anno e non modificabile a
ritroso. La lista fatture segnala eventuali "buchi" nella sequenza.

> I campi per clienti con partita IVA (P.IVA, ritenuta d'acconto) sono sotto
> **"Opzioni avanzate"**: servono solo per i sostituti d'imposta. Il gestionale
> produce fatture **cartacee**, non fatture elettroniche via SdI: eventuali
> documenti che richiedono la e-fattura vanno gestiti altrove/dal commercialista.

## 6. Preventivi (proforma)

In **Preventivi → Nuovo preventivo** crei un documento **non fiscale** con lo
stesso calcolo della fattura e una **validità in giorni**. Dal dettaglio puoi
stamparlo in PDF, inviarlo al cliente, **eliminarlo** oppure **convertirlo in
fattura** (crea una vera fattura con gli stessi importi; il preventivo resta
collegato e segnato come "convertito").

## 7. Invio al cliente (WhatsApp)

Unico canale: **WhatsApp**. Non c'è niente da configurare nel programma — serve
solo che WhatsApp sia collegato al computer (app *WhatsApp* per Windows oppure
`web.whatsapp.com`, associati una volta col QR code dal telefono) e che il cliente
abbia il **telefono** in anagrafica.

Dal documento, **Invia con WhatsApp**:
1. il PDF viene generato e salvato in **`dati/da_inviare`**;
2. il file viene messo negli **appunti di Windows** *come file*
   (`Set-Clipboard -LiteralPath` via PowerShell, `-STA`);
3. si apre `wa.me` sulla chat del cliente col **messaggio già scritto**.

L'allegato non può essere attaccato dal programma, quindi la pagina d'invio
**consegna il file**: lo mostra in anteprima e lo rende afferrabile in tre modi,
dal più comodo al più manuale.

| Via | Come | Dipende da |
|---|---|---|
| **Trascinamento** | si prende la scheda del PDF e si lascia cadere nella chat | `dataTransfer.setData('DownloadURL', …)` — Chrome/Edge |
| **Ctrl+V** | il file è già negli appunti | `Set-Clipboard`, e che nessuna altra copia li sovrascriva |
| **Graffetta** | si scarica (o si prende da `dati/da_inviare`) e si allega a mano | niente |

Il trascinamento è la via principale proprio perché non dipende dagli appunti.
Un link nudo, trascinato, porterebbe in chat l'**indirizzo della pagina**: è
`DownloadURL` a far consegnare al browser un file vero.

È il compromesso scelto consapevolmente:

- l'**API ufficiale** (WhatsApp Business Cloud) richiede account business, numero
  dedicato, token da rinnovare, messaggi su modello approvato ed è a pagamento;
- le librerie che **pilotano WhatsApp Web** si rompono a ogni aggiornamento e
  violano i termini d'uso;
- quindi resta un gesto umano finale, che è anche l'ultimo controllo prima che il
  documento parta.

`fatture.whatsapp_at` registra quando un documento è stato **preparato** per
l'invio, non che il cliente l'abbia ricevuto: quello succede dentro WhatsApp e il
programma non lo può sapere.

> **L'invio email (SMTP) è stato rimosso.** Chiedeva server, porta, utente e
> password del provider, con la password salvata nel database: troppa
> configurazione per un uso che si fa dal telefono. Le colonne `smtp_*`,
> `invio_auto_email` e `email_inviata_at` restano nello schema ma sono **morte**
> (in SQLite eliminare colonne significa ricostruire la tabella, e non vale il
> rischio su un archivio di fatture emesse).

## 8. Esportazioni

**Esportazioni** (scegli il periodo in alto):

- **Commercialista** — registro delle fatture del periodo in **Excel** e **CSV**
  (con riepilogo IVA per aliquota) e un **ZIP con le copie PDF** dei documenti,
  note di credito comprese. Nell'Excel importi e date sono **valori veri**, non
  testo: le colonne si sommano e si ordinano.
- **Sistema Tessera Sanitaria** — spese veterinarie, filtrate per **data di
  pagamento** (il Sistema TS segue la cassa). ⚠️ **Il file da caricare sul
  portale non è ancora generabile:** vedi sotto.

### Sistema TS: stato del lavoro

Il modello dei dati è conforme al disciplinare tecnico (Allegato A al DM
19/10/2020) e vive in `app/tracciato_ts.py`:

    Fornitura
      └─ DocumentoFiscale *
           ├─ IdSpesa (P.IVA + data emissione + dispositivo + progressivo)
           ├─ data pagamento, flag pagamento anticipato, flag operazione
           ├─ codice fiscale assistito (omesso in caso di opposizione)
           ├─ modalità pagamento, tipo documento
           └─ VoceSpesa *  ← **una per riga di fattura**, con tipologia FV/SV/AA

Il punto delicato è la **ripartizione**: il database tiene l'imponibile per riga,
mentre ENPAV e IVA sono calcolati e arrotondati per gruppo di aliquota. Il lordo
di gruppo viene ripartito in proporzione, con il residuo assegnato a una riga
sola secondo una regola deterministica; la validazione **rifiuta** il documento
se le voci non sommano esattamente il totale della fattura. Un file che dichiara
un importo diverso da quello fatturato passerebbe i controlli formali del portale
e sbaglierebbe la detrazione.

L'esito è diviso in **tre**, non in due:

| Esito | Significato |
|---|---|
| Da trasmettere | pronti per l'invio |
| Fuori ambito | la detrazione riguarda le **persone fisiche**: le fatture a clienti con P.IVA non vanno al TS. Non c'è nulla da correggere |
| Da correggere | dovrebbero andare ma hanno dati mancanti o incoerenti |

**Cosa manca per completare**, e perché non è stato indovinato:

1. **L'XSD corrente delle spese veterinarie** → `app/ts_xml.py`. Il file è un XML
   compresso, non un CSV, e lo zip caricato sul portale non supera i 5 MB.
2. **Il certificato X.509 del Sistema TS** → `app/ts_cifratura.py`. Il codice
   fiscale «deve essere sempre cifrato utilizzando la chiave pubblica RSA
   contenuta nel certificato X.509 fornito dal sistema TS ed applicando il
   padding PKCS#1 v1.5» (par. 4.4); in chiaro viene scartato.

Entrambi stanno nell'area riservata di `sistemats.it`, raggiungibile con le
credenziali della professionista (che arrivano via PEC tramite Ordine/FNOVI).
Le due funzioni esistono già con la firma definitiva e sollevano
`NotImplementedError` con l'istruzione su cosa serve: una versione precedente di
questo export era stata scritta "a occhio" sul disciplinare e produceva un file
che il portale avrebbe respinto, indistinguibile da uno giusto fino alla scadenza.

Le tre modalità di invio previste dal Sistema TS sono: inserimento manuale a web,
**upload di un file** (zip contenente XML, max 5 MB) e web service.

## 9. Backup e ripristino

**Backup e manutenzione**:
- **Crea backup**: salva una copia del database in `dati/backup`.
- **Scarica copia (.db)**: scarica una copia da conservare altrove (chiavetta, ecc.).
- **Ripristina**: da un backup in elenco o da un file `.db` caricato. Prima del
  ripristino viene creata automaticamente una **copia di sicurezza** del database
  attuale.

Consiglio: fai un backup periodico e conservane una copia fuori dal PC.

## 10. Creare l'eseguibile (per chi sviluppa)

Con Python 3.12: doppio clic su **`costruisci_exe.bat`**. Al termine trovi
`dist\Gestionale.exe`. Copialo dove vuoi: al primo avvio creerà accanto a sé la
cartella `dati`.

**Se il build fallisce con `PermissionError: [WinError 5]` su `dist\Gestionale.exe`**,
il file è in uso. Due cause, in ordine di frequenza:

1. **Il gestionale è in esecuzione.** Non serve il Gestione attività: chiudilo dal
   pulsante *"Chiudi il gestionale"*, oppure con `POST /spegni` sulla porta su cui
   ascolta (`Get-NetTCPConnection -State Listen -OwningProcess <pid>` per trovarla).
2. **È appena stato chiuso**, ma il **bootloader onefile** di PyInstaller è ancora
   lì a ripulire la propria cartella temporanea, e in quel tempo il file resta
   bloccato. Di solito esce in mezzo minuto, ma è stato visto restare **oltre
   quattro minuti**. Riconoscerlo è facile e permette di chiuderlo senza dubbi:

   ```powershell
   Get-Process -Name Gestionale | ForEach-Object {
     $py = $_.Modules | Where-Object { $_.ModuleName -like "python*.dll" }
     $porte = (Get-NetTCPConnection -State Listen -OwningProcess $_.Id -ErrorAction SilentlyContinue).LocalPort
     "PID $($_.Id) | python: $(if($py){'SI'}else{'no'}) | porte: $porte"
   }
   ```

   **Nessun `python*.dll` caricato e nessuna porta in ascolto** = l'applicazione è
   già uscita e quello è solo il bootloader: `Stop-Process -Name Gestionale -Force`
   è sicuro, non c'è niente da salvare. Se invece ha Python caricato e una porta,
   è il gestionale vero e va chiuso con `/spegni`.

## 11. Note fiscali

- Regime **ordinario**: IVA in fattura (default 22%, modificabile per prestazione).
- **ENPAV 2%** in rivalsa sul cliente, incluso nella base imponibile IVA.
- **Niente marca da bollo** (si applica solo alle fatture senza IVA).
- **Ritenuta d'acconto**: disattivata di default, solo per clienti sostituti d'imposta.

## 12. Struttura del progetto

```
app/            codice dell'applicazione (server, calcolo, PDF, invio, export, backup)
  routers/      pagine web (clienti, pazienti, listino, registro, fatture,
                preventivi, export, backup, impostazioni)
  templates/    pagine HTML (in italiano)
  static/       CSS, JavaScript, marchio e icona
  registro.py       diario delle prestazioni eseguite (da cui nascono le fatture)
  invio.py          invio WhatsApp (PDF negli appunti + link wa.me)
  marchio.py        marchio come maschera colorabile, per schermo e PDF
  tracciato_ts.py   *** modello dati Sistema TS, isolato e documentato ***
  ts_xml.py         scrittura XML per il TS — DA COMPLETARE (serve l'XSD)
  ts_cifratura.py   cifratura RSA del C.F. — DA COMPLETARE (serve il certificato)
dati/           database, backup e da_inviare/ (creata da sola; NON versionata)
dati_esempio/   dati finti per il collaudo
tests/          test automatici
GUIDA.html           guida per l'utente finale (generata da build_guida.py)
build_guida.py       genera GUIDA.html con il marchio incorporato
avvia.bat            avvio senza eseguibile
costruisci_exe.bat   creazione di Gestionale.exe
crea_collegamento.bat  collegamento "Gestionale Studio" sul Desktop
crea_icona.py        genera l'icona dell'exe dal marchio
```

## 13. Verifica tecnica (facoltativa)

Con l'ambiente attivo: `python -m pytest` esegue i test automatici (calcolo,
numerazione, validazioni, emissione fatture, registro, invio WhatsApp e avvio
senza console).
