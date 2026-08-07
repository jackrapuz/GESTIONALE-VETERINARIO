"""Genera GUIDA.html: la guida d'uso per l'utente finale.

    python build_guida.py

Il file prodotto e' **autosufficiente**: il marchio viene incorporato in base64
dentro il CSS, quindi la guida si apre con un doppio clic, funziona offline e si
stampa. Viene scritta in radice e, se esiste ``dist/``, anche accanto all'exe.

La guida e' scritta per **scenari**, non per funzioni: "una visita e la fatturi
subito", "cliente mensile con piu' cavalli", "il cliente ti paga". Ogni etichetta
di pulsante citata qui e' quella vera dei template in ``app/templates``: se un
pulsante viene rinominato, questo file va aggiornato.

Nota: i nomi di clienti e cavalli negli esempi sono **inventati**. Questo
repository e' pubblico e i dati reali non ci devono finire.
"""
from base64 import b64encode
from pathlib import Path

RADICE = Path(__file__).resolve().parent
# Lo stesso marchio dell'interfaccia e dei PDF: una maschera RGBA, colorata via CSS.
MARCHIO = RADICE / "app" / "static" / "img" / "marchio.png"
URI = "data:image/png;base64," + b64encode(MARCHIO.read_bytes()).decode("ascii")

VOCI = ["Clienti", "Pazienti", "Listino", "Registro", "Fatture",
        "Preventivi", "Esportazioni", "Backup", "Impostazioni"]
NAV = "".join(f"<span>{v}</span>" for v in VOCI)
NAV_REG = NAV.replace("<span>Registro</span>", "<span class='on'>Registro</span>")

HTML = f"""<title>Il gestionale, in pratica</title>
<style>
:root {{
  --carta:#f3f5f1; --superficie:#ffffff; --inchiostro:#16211c; --verde:#223d33;
  --ottone:#b5822e; --nebbia:#5e6b63; --bordo:#dbe2db; --tint:#e7efe9;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
  --sans:system-ui,"Segoe UI",Roboto,-apple-system,Arial,sans-serif;
}}
@media (prefers-color-scheme:dark) {{
  :root {{ --carta:#121815; --superficie:#18211d; --inchiostro:#e4ece6; --verde:#b9d0c0;
    --ottone:#d09a45; --nebbia:#93a29a; --bordo:#2a3831; --tint:#1d2a23; }}
}}
:root[data-theme="dark"] {{ --carta:#121815; --superficie:#18211d; --inchiostro:#e4ece6;
  --verde:#b9d0c0; --ottone:#d09a45; --nebbia:#93a29a; --bordo:#2a3831; --tint:#1d2a23; }}
:root[data-theme="light"] {{ --carta:#f3f5f1; --superficie:#ffffff; --inchiostro:#16211c;
  --verde:#223d33; --ottone:#b5822e; --nebbia:#5e6b63; --bordo:#dbe2db; --tint:#e7efe9; }}

body {{ margin:0; background:var(--carta); color:var(--inchiostro);
  font-family:var(--sans); font-size:16.5px; line-height:1.65;
  -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:52rem; margin:0 auto;
  padding:clamp(1.5rem,4vw,3.5rem) clamp(1.1rem,4vw,2rem) 5rem; }}
p {{ margin:0; max-width:64ch; }}
.dim {{ color:var(--nebbia); }}
.piccolo {{ font-size:.88rem; }}

.testa {{ display:flex; align-items:center; gap:1.4rem; flex-wrap:wrap; }}
.marchio {{ display:inline-block; flex:0 0 auto; aspect-ratio:376/457; height:92px;
  background-color:var(--verde);
  -webkit-mask:url("{URI}") no-repeat center/contain;
  mask:url("{URI}") no-repeat center/contain; }}
.occhiello {{ font-size:.72rem; letter-spacing:.18em; text-transform:uppercase;
  color:var(--ottone); font-weight:700; }}
h1 {{ font-family:var(--serif); font-weight:400; font-size:clamp(2rem,5vw,2.9rem);
  line-height:1.1; margin:.35rem 0 0; text-wrap:balance; }}
h2 {{ font-family:var(--serif); font-weight:400; font-size:clamp(1.4rem,3vw,1.8rem);
  margin:0; text-wrap:balance; }}
h3 {{ font-family:var(--serif); font-weight:400; font-size:1.15rem; margin:0; }}

section {{ margin-top:clamp(2.6rem,6vw,4rem); display:flex; flex-direction:column; gap:1.2rem; }}
.testata {{ border-top:2px solid var(--bordo); padding-top:1.1rem;
  display:flex; flex-direction:column; gap:.45rem; }}

.caso {{ background:var(--superficie); border:1px solid var(--bordo); border-radius:16px;
  padding:clamp(1.2rem,3vw,1.8rem); display:flex; flex-direction:column; gap:1rem; }}
.caso__n {{ display:inline-flex; align-items:center; justify-content:center;
  width:2rem; height:2rem; border-radius:50%; background:var(--verde); color:#fff;
  font-family:var(--serif); font-size:1.05rem; flex:0 0 auto; }}
.caso__cima {{ display:flex; align-items:center; gap:.9rem; }}
.situazione {{ background:var(--tint); border-left:3px solid var(--ottone);
  padding:.7rem 1rem; border-radius:0 8px 8px 0; font-style:italic; }}
/* flex-wrap: l'etichetta e' nowrap e con una etichetta lunga ("Se qualcosa non
   torna") il testo accanto sbordava di qualche decina di pixel. Andando a capo,
   l'etichetta si prende la sua riga invece di spingere fuori il resto. */
.risultato {{ display:flex; gap:.6rem; align-items:flex-start; flex-wrap:wrap;
  border-top:1px dashed var(--bordo); padding-top:.9rem; font-size:.94rem; }}
.risultato b {{ color:var(--verde); font-weight:700; white-space:nowrap; }}

ol.passi {{ margin:0; padding-left:0; list-style:none; counter-reset:p;
  display:flex; flex-direction:column; gap:.75rem; }}
ol.passi li {{ counter-increment:p; padding-left:2.3rem; position:relative; }}
ol.passi li::before {{ content:counter(p); position:absolute; left:0; top:.08rem;
  width:1.6rem; height:1.6rem; border-radius:50%; border:1.5px solid var(--verde);
  color:var(--verde); font-size:.82rem; font-weight:700;
  display:flex; align-items:center; justify-content:center; }}
kbd {{ font:inherit; font-weight:700; color:var(--verde); background:var(--tint);
  border:1px solid var(--bordo); border-radius:6px; padding:.05em .45em;
  white-space:nowrap; }}
.tasti {{ font-family:var(--sans); font-weight:700; background:var(--superficie);
  border:1.5px solid var(--verde); border-bottom-width:3px; border-radius:7px;
  padding:.06em .5em; color:var(--verde); white-space:nowrap; }}

.schermo {{ border:1px solid var(--bordo); border-radius:12px; overflow:hidden;
  background:var(--superficie); font-size:.85rem; }}
.schermo__barra {{ background:#223d33; color:#e7efe9; padding:.5rem .8rem;
  display:flex; align-items:center; gap:.6rem; }}
.schermo__barra .marchio {{ height:22px; background-color:#f3f5f1; }}
.schermo__barra b {{ font-family:var(--serif); font-weight:400; font-size:.95rem; color:#fff; }}
.schermo__barra nav {{ margin-left:auto; display:flex; gap:.7rem;
  font-size:.68rem; letter-spacing:.04em; opacity:.75; }}
.schermo__barra nav span.on {{ opacity:1; color:#fff; border-bottom:2px solid var(--ottone); }}
@media (max-width:640px) {{ .schermo__barra nav {{ display:none; }} }}
.schermo__corpo {{ padding:.9rem 1rem; overflow-x:auto; }}
table.finta {{ width:100%; border-collapse:collapse; font-size:.85rem; min-width:26rem; }}
table.finta th {{ text-align:left; font-weight:600; color:var(--verde);
  background:var(--tint); padding:.4rem .6rem; font-size:.75rem; }}
table.finta td {{ padding:.4rem .6rem; border-bottom:1px solid var(--bordo); }}
table.finta td.num, table.finta th.num {{ text-align:right;
  font-variant-numeric:tabular-nums; }}
table.finta tfoot td {{ border-bottom:none; border-top:1.5px solid var(--bordo); }}
td.x {{ text-align:center; color:var(--nebbia); font-size:1.05rem; }}
.badge {{ display:inline-block; font-size:.68rem; letter-spacing:.04em; padding:.1em .5em;
  border-radius:999px; border:1px solid var(--bordo); background:var(--tint);
  color:var(--verde); vertical-align:middle; }}
.bottone {{ display:inline-block; background:var(--verde); color:#fff;
  padding:.32rem .8rem; border-radius:8px; font-size:.78rem; font-weight:600; }}
.bottone.chiaro {{ background:var(--superficie); color:var(--verde);
  border:1.5px solid var(--verde); }}

.nota {{ border-radius:14px; padding:1.1rem 1.3rem; display:flex; gap:.9rem;
  align-items:flex-start; }}
.nota__i {{ font-size:1.2rem; line-height:1.2; flex:0 0 auto; }}
.nota--info {{ background:var(--tint); border:1px solid var(--bordo); }}
.nota--attenzione {{ background:#fbf3e3; border:1px solid #e6d3a8; color:#6b4a10; }}
@media (prefers-color-scheme:dark) {{
  .nota--attenzione {{ background:#2a2313; border-color:#5c4a1e; color:#e8d5a8; }}
}}
:root[data-theme="dark"] .nota--attenzione {{ background:#2a2313; border-color:#5c4a1e; color:#e8d5a8; }}
:root[data-theme="light"] .nota--attenzione {{ background:#fbf3e3; border-color:#e6d3a8; color:#6b4a10; }}

.rapido {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:.9rem; }}
.rapido div {{ background:var(--superficie); border:1px solid var(--bordo);
  border-radius:12px; padding:.9rem 1rem; }}
.rapido b {{ display:block; font-family:var(--serif); font-weight:400;
  font-size:1.05rem; color:var(--verde); }}
.rapido span {{ font-size:.85rem; color:var(--nebbia); }}

@media print {{
  body {{ background:#fff; font-size:11pt; }}
  .wrap {{ max-width:none; padding:0; }}
  section {{ margin-top:1.6rem; page-break-inside:avoid; }}
  .caso {{ page-break-inside:avoid; }}
  .schermo__barra nav {{ display:none; }}
}}
</style>

<div class="wrap">

  <header class="testa">
    <span class="marchio"></span>
    <div>
      <div class="occhiello">Guida pratica</div>
      <h1>Il gestionale, in pratica</h1>
      <p class="dim" style="margin-top:.6rem">Come si usa, con gli esempi delle
      cose che farai davvero.</p>
    </div>
  </header>

  <section>
    <div class="testata">
      <h2>Le tre cose da sapere</h2>
    </div>
    <div class="rapido">
      <div><b>&Egrave; tutto sul tuo computer</b><span>Nessun dato esce da qui. Niente
        account, niente password, nessun abbonamento.</span></div>
      <div><b>Si apre col doppio clic</b><span>L'icona <em>Gestionale Studio</em>
        sul Desktop. Si apre il browser: quella &egrave; l'applicazione.</span></div>
      <div><b>Il Registro &egrave; il tuo blocco-note</b><span>Ci scrivi cosa hai fatto,
        quando lo fai. Le fatture nascono da l&igrave;.</span></div>
    </div>
    <div class="schermo">
      <div class="schermo__barra">
        <span class="marchio"></span><b>Studio Veterinario</b>
        <nav>{NAV}</nav>
      </div>
      <div class="schermo__corpo dim piccolo">
        Questa &egrave; la barra in alto: da l&igrave; raggiungi tutto. Le voci che userai di pi&ugrave;
        sono <strong>Registro</strong> e <strong>Fatture</strong>.
      </div>
    </div>
  </section>

  <section>
    <div class="testata">
      <div class="occhiello">Da fare una volta sola</div>
      <h2>Installazione e primo giorno</h2>
    </div>

    <div class="caso">
      <div class="caso__cima"><span class="caso__n">1</span>
        <h3>Mettere il programma sul computer</h3></div>
      <p class="situazione">&laquo;Giacomo mi ha dato il programma. Cosa devo fare per
      averlo sul mio computer?&raquo;</p>
      <ol class="passi">
        <li>Crea una cartella sul computer &mdash; per esempio <strong>C:\\Gestionale</strong>
          &mdash; e copiaci dentro i tre file: <strong>Gestionale.exe</strong> (il programma),
          <strong>crea_collegamento.bat</strong> e <strong>GUIDA.html</strong> (questa guida).</li>
        <li>Doppio clic su <strong>crea_collegamento.bat</strong>: mette sul Desktop l'icona
          <em>Gestionale Studio</em>. Scrive "Fatto" e si chiude premendo un tasto.</li>
        <li>Doppio clic sull'icona. Si apre il browser sul gestionale: quella &egrave;
          l'applicazione. Ogni avvio richiede qualche secondo, il primo un po' di pi&ugrave;.</li>
        <li>Se compare un riquadro blu <strong>"Windows ha protetto il PC"</strong>, non &egrave;
          un virus: capita a tutti i programmi non registrati presso Microsoft. Clicca
          <strong>Ulteriori informazioni</strong> e poi <strong>Esegui comunque</strong>.
          Lo chiede una volta sola.</li>
      </ol>
      <div class="nota nota--attenzione">
        <span class="nota__i">&#9888;</span>
        <div><strong>Non metterlo in OneDrive, Dropbox o Google Drive.</strong> I tuoi dati
        stanno in una cartella <strong>dati</strong> accanto al programma, e le cartelle
        sincronizzate copiano i file <em>mentre</em> il programma li sta scrivendo: si
        rischia di rovinare l'archivio delle fatture. Una cartella normale del computer &egrave;
        il posto giusto. Per avere una copia altrove c'&egrave; il <strong>Backup</strong>
        (caso 11), che &egrave; il modo sicuro di farlo.</div>
      </div>
      <p class="risultato"><b>Se un giorno lo sposti &rarr;</b> sposta <strong>tutta la
      cartella</strong>, non solo il programma: i tuoi dati sono nella cartella
      <strong>dati</strong> che gli sta accanto. Poi ridai doppio clic su
      <em>crea_collegamento.bat</em> per rifare l'icona.</p>
      <p class="dim piccolo">Se l'antivirus si insospettisce del programma &egrave; un falso
      allarme (succede con i programmi costruiti cos&igrave;): chiedi a Giacomo prima di
      cancellare qualcosa.</p>
    </div>

    <div class="caso">
      <div class="caso__cima"><span class="caso__n">2</span>
        <h3>Prepara il programma</h3></div>
      <ol class="passi">
        <li>Vai su <kbd>Impostazioni</kbd> e inserisci i tuoi dati: denominazione,
          indirizzo, P. IVA, codice fiscale, numero di iscrizione all'albo, IBAN. Sono
          quelli che compariranno in cima a ogni fattura.</li>
        <li>Sempre l&igrave;, in fondo, c'&egrave; <strong>Continuit&agrave; numerazione</strong>:
          scrivi il <strong>prossimo numero</strong> da usare.</li>
        <li>Vai su <kbd>Listino</kbd> e inserisci le prestazioni che fai pi&ugrave; spesso
          con il loro prezzo: visita, ecografia, onde d'urto, radiografie&hellip; Servono a
          non riscrivere ogni volta descrizione e importo.</li>
        <li>Vai su <kbd>Clienti</kbd> e inserisci i proprietari &mdash; con il
          <strong>numero di telefono</strong>, che serve per mandargli i documenti su
          WhatsApp &mdash; poi su <kbd>Pazienti</kbd> i loro cavalli.</li>
      </ol>
      <div class="nota nota--attenzione">
        <span class="nota__i">&#9888;</span>
        <div><strong>Il numero di partenza va messo prima della prima fattura.</strong>
        Se l'ultima fattura che hai fatto a mano quest'anno &egrave; la n. 90, qui scrivi
        <strong>91</strong>. Dopo aver emesso la prima fattura non si pu&ograve; pi&ugrave;
        cambiare: la numerazione deve restare senza buchi.</div>
      </div>
      <p class="dim piccolo">Se vuoi solo provare il programma senza rischiare, vai su
      <kbd>Backup</kbd> &rarr; <span class="bottone chiaro">Carica dati di esempio</span>:
      riempie tutto con clienti e cavalli finti.</p>
    </div>

    <div class="caso">
      <div class="caso__cima"><span class="caso__n">3</span>
        <h3>Collega WhatsApp al computer</h3></div>
      <p class="situazione">&laquo;I documenti li mando su WhatsApp. Devo aprire un
      account nuovo? Devo pagare qualcosa?&raquo;</p>
      <p><strong>No a entrambe.</strong> Si usa il <em>tuo</em> WhatsApp, quello che hai
      gi&agrave; sul telefono. Serve solo che sia collegato anche a questo computer, e si fa
      una volta sola:</p>
      <ol class="passi">
        <li>Sul computer, installa <strong>WhatsApp</strong> dal Microsoft Store
          (cerca "WhatsApp"). In alternativa va bene anche il sito
          <strong>web.whatsapp.com</strong> nel browser.</li>
        <li>Si apre una pagina con un <strong>quadrato di puntini</strong> (il QR code).</li>
        <li>Sul telefono apri WhatsApp &rarr; <strong>Impostazioni</strong> &rarr;
          <strong>Dispositivi collegati</strong> &rarr; <strong>Collega dispositivo</strong>,
          e inquadra il quadrato con la fotocamera.</li>
        <li>Fatto: da adesso le tue chat sono anche sul computer.</li>
      </ol>
      <div class="nota nota--info">
        <span class="nota__i">&#10003;</span>
        <div>Non serve <strong>nessun account business</strong>, nessun codice, nessun
        abbonamento: il gestionale non parla con WhatsApp, ti apre solo la chat giusta
        col messaggio gi&agrave; scritto. <strong>Il telefono deve essere accesso e
        connesso</strong> perch&eacute; WhatsApp sul computer funzioni.</div>
      </div>
      <p class="dim piccolo">Nel programma non c'&egrave; niente da configurare: in
      <kbd>Impostazioni</kbd> trovi solo un promemoria di quanto sopra.</p>
    </div>
  </section>

  <section>
    <div class="testata">
      <div class="occhiello">Esempi</div>
      <h2>Le situazioni di tutti i giorni</h2>
    </div>

    <div class="caso">
      <div class="caso__cima"><span class="caso__n">4</span>
        <h3>Una visita e basta, la fatturi subito</h3></div>
      <p class="situazione">&laquo;Mi chiama una signora che non ho mai visto, vado a
      vedere il cavallo, faccio un'ecografia. Voglio darle la fattura e chiuderla l&igrave;.&raquo;</p>
      <ol class="passi">
        <li>Se il cliente &egrave; nuovo: <kbd>Clienti</kbd> &rarr; <span class="bottone">+ Nuovo cliente</span>,
          e in <kbd>Pazienti</kbd> aggiungi il cavallo.</li>
        <li>Vai su <kbd>Registro</kbd> &rarr; <span class="bottone">+ Annota prestazione</span>.</li>
        <li>Scegli cliente e cavallo, la data di oggi, e la prestazione dal listino
          (il prezzo si compila da solo).</li>
        <li>Torni sul <kbd>Registro</kbd> e accanto al suo nome premi
          <span class="bottone">Fattura ora</span>.</li>
      </ol>
      <p class="risultato"><b>Cosa ottieni &rarr;</b> La fattura &egrave; emessa e numerata.
      Si apre da sola: premi <span class="bottone">Stampa PDF</span> per stamparla,
      oppure <span class="bottone chiaro">Invia con WhatsApp</span> per mandarla
      (vedi il caso 6).</p>
    </div>

    <div class="caso">
      <div class="caso__cima"><span class="caso__n">5</span>
        <h3>Un cliente con pi&ugrave; cavalli, che paga a fine mese</h3></div>
      <p class="situazione">&laquo;Dalla signora Rossi ci vado di continuo: ha due cavalli
      e nel mese ci passo tre o quattro volte. Le faccio una fattura sola alla fine.&raquo;</p>
      <ol class="passi">
        <li><strong>Una volta sola:</strong> apri la sua scheda in <kbd>Clienti</kbd> e
          spunta <strong>Fatturazione mensile</strong>. Cos&igrave; il programma sa che le sue
          prestazioni vanno accumulate.</li>
        <li><strong>Ogni volta che vai da lei</strong>, appena finito:
          <kbd>Registro</kbd> &rarr; <span class="bottone">+ Annota prestazione</span>.
          Scegli il cavallo giusto, la data di oggi e cosa hai fatto. Trenta secondi.</li>
        <li>Non pensare pi&ugrave; alle fatture. Le prestazioni si accumulano da sole sotto
          il suo nome.</li>
        <li><strong>A fine mese</strong> apri <kbd>Registro</kbd>: sotto il suo nome
          trovi tutto quello che hai fatto. Premi <span class="bottone">Fattura il mese</span>.</li>
      </ol>
      <div class="schermo">
        <div class="schermo__barra">
          <span class="marchio"></span><b>Studio Veterinario</b>
          <nav>{NAV_REG}</nav>
        </div>
        <div class="schermo__corpo">
          <p class="piccolo" style="margin-bottom:.6rem"><strong>Da fatturare</strong>
            &mdash; Sig.ra Rossi <span class="badge">rapporto continuativo</span></p>
          <table class="finta">
            <thead><tr><th>Data</th><th>Cavallo</th><th>Prestazione</th>
              <th class="num">Importo</th><th></th></tr></thead>
            <tbody>
              <tr><td>11/07/2026</td><td>BAIARDO</td><td>Controllo + esame del sangue</td>
                <td class="num">120,00</td><td class="x">&times;</td></tr>
              <tr><td>04/07/2026</td><td>STELLA</td><td>Visita + anestesia</td>
                <td class="num">190,00</td><td class="x">&times;</td></tr>
              <tr><td>18/07/2026</td><td>STELLA</td><td>Esame ecografico</td>
                <td class="num">100,00</td><td class="x">&times;</td></tr>
            </tbody>
            <tfoot><tr><td colspan="3" class="num"><strong>Totale da fatturare</strong></td>
              <td class="num"><strong>410,00</strong></td><td></td></tr></tfoot>
          </table>
          <p style="margin-top:.8rem"><span class="bottone chiaro">Proforma (riepilogo mese)</span>
            <span class="bottone" style="margin-left:.4rem">Fattura il mese</span></p>
        </div>
      </div>
      <p class="risultato"><b>Cosa ottieni &rarr;</b> Una fattura sola, con le prestazioni
      <strong>raggruppate per cavallo</strong> e la data di ognuna &mdash; come le facevi a mano.</p>
      <div class="nota nota--info">
        <span class="nota__i">&#10003;</span>
        <div>La <strong>&times;</strong> in fondo a ogni riga serve se hai annotato una
        cosa sbagliata: la toglie, senza lasciare traccia. Funziona <strong>finch&eacute; non
        hai fatturato</strong>.</div>
      </div>
    </div>

    <div class="caso">
      <div class="caso__cima"><span class="caso__n">6</span>
        <h3>Mandare la fattura al cliente su WhatsApp</h3></div>
      <p class="situazione">&laquo;La fattura &egrave; pronta. Gliela mando su WhatsApp, come
      faccio sempre.&raquo;</p>
      <ol class="passi">
        <li>Apri la fattura e premi <span class="bottone chiaro">Invia con WhatsApp</span>.</li>
        <li>Il programma prepara tutto e ti mostra una pagina con
          <strong>la fattura in anteprima</strong> e il pulsante
          <span class="bottone">Apri WhatsApp</span>: premilo. Si apre la chat del cliente
          con il <strong>messaggio gi&agrave; scritto</strong>.</li>
        <li>Torna sulla pagina del gestionale e <strong>trascina</strong> la scheda del
          PDF dentro la chat &mdash; tienila premuta col mouse e lasciala cadere sul
          messaggio. In alternativa premi <span class="tasti">Ctrl</span> +
          <span class="tasti">V</span>: il PDF &egrave; anche negli appunti.</li>
        <li>Premi <span class="tasti">Invio</span> e il documento &egrave; partito.</li>
      </ol>
      <div class="nota nota--info">
        <span class="nota__i">&#33;</span>
        <div><strong>Se WhatsApp ti si apre dentro il browser</strong> (WhatsApp Web, in
        una scheda) invece che nel suo programma, il trascinamento <strong>non
        funziona</strong>: nella chat finirebbe un indirizzo invece del documento. L&igrave;
        usa <span class="tasti">Ctrl</span> + <span class="tasti">V</span>, oppure la
        <strong>graffetta</strong>. Nel programma di WhatsApp invece il trascinamento va.</div>
      </div>
      <div class="nota nota--info">
        <span class="nota__i">&#10003;</span>
        <div><strong>Perch&eacute; devi farlo tu?</strong> WhatsApp non permette a un programma
        di attaccare file da solo. Il gestionale allora ti <em>mette il file in mano</em>:
        lo vedi sulla pagina, lo trascini o lo incolli. &Egrave; anche l'ultima occasione per
        controllare che stai scrivendo alla persona giusta.</div>
      </div>
      <p class="risultato"><b>Se qualcosa non torna &rarr;</b> Clicca la scheda del PDF
      sulla pagina di invio: il file si <strong>scarica</strong> e lo puoi allegare a mano
      con la <strong>graffetta</strong> di WhatsApp. Resta comunque salvato anche nella
      cartella <strong>dati &rarr; da_inviare</strong>, accanto al programma.</p>
      <p class="dim piccolo">Il numero del cliente lo prende dalla sua scheda in
      <kbd>Clienti</kbd>. Se manca, al posto del pulsante trovi scritto
      <em>"Nessun telefono in anagrafica"</em>: aggiungilo e riprova. Funziona allo stesso
      modo per i <strong>preventivi</strong>.</p>
    </div>

    <div class="caso">
      <div class="caso__cima"><span class="caso__n">7</span>
        <h3>Il cliente vuole sapere prima quanto viene</h3></div>
      <p class="situazione">&laquo;Prima di partire con un ciclo di onde d'urto, il
      proprietario mi chiede un'idea della spesa.&raquo;</p>
      <ol class="passi">
        <li>Se le prestazioni sono gi&agrave; nel <kbd>Registro</kbd>, premi
          <span class="bottone chiaro">Proforma (riepilogo mese)</span> accanto al suo nome:
          &egrave; il riepilogo di quello che ha gi&agrave; maturato.</li>
        <li>Se invece &egrave; un preventivo per cose non ancora fatte, vai su
          <kbd>Preventivi</kbd> &rarr; <span class="bottone">+ Nuovo preventivo</span>
          e componi le righe.</li>
        <li>Premi <span class="bottone">Stampa PDF</span> per stamparlo, oppure
          <span class="bottone chiaro">Invia con WhatsApp</span> per mandarlo.</li>
      </ol>
      <div class="nota nota--info">
        <span class="nota__i">&#10003;</span>
        <div>La proforma <strong>non consuma</strong> le prestazioni del registro:
        restano l&igrave;, da fatturare. E <strong>non &egrave; una fattura</strong> &mdash; non ha
        valore fiscale finch&eacute; non emetti quella vera.</div>
      </div>
      <p class="risultato"><b>Cosa ottieni &rarr;</b> Un PDF con la stessa intestazione
      della fattura. Se poi il lavoro si fa, dal preventivo premi
      <span class="bottone">Converti in fattura</span> e diventa una fattura vera.</p>
    </div>

    <div class="caso">
      <div class="caso__cima"><span class="caso__n">8</span>
        <h3>Il cliente ti paga</h3></div>
      <p class="situazione">&laquo;Mi &egrave; arrivato il bonifico della fattura di giugno.&raquo;</p>
      <ol class="passi">
        <li>Vai su <kbd>Fatture</kbd> e apri quella pagata.</li>
        <li>In fondo, sotto <strong>Azioni</strong>: metti lo stato su
          <strong>Incassata</strong>, scrivi la <strong>data incasso</strong> e premi
          <span class="bottone">Aggiorna stato</span>.</li>
      </ol>
      <p class="risultato"><b>Cosa ottieni &rarr;</b> La fattura passa da
      <strong>Da incassare</strong> ad <strong>Archivio</strong>. Cos&igrave; nell'elenco vedi
      a colpo d'occhio solo chi ti deve ancora pagare.</p>
      <div class="nota nota--attenzione">
        <span class="nota__i">&#9888;</span>
        <div>La <strong>data incasso conta</strong>: &egrave; quella che decide in che
        anno la prestazione va comunicata al Sistema Tessera Sanitaria. Mettila
        giusta, anche se la registri in ritardo.</div>
      </div>
    </div>
  </section>

  <section>
    <div class="testata">
      <div class="occhiello">Ogni tanto</div>
      <h2>Fine mese, fine anno</h2>
    </div>

    <div class="caso">
      <div class="caso__cima"><span class="caso__n">9</span>
        <h3>Dare i numeri al commercialista</h3></div>
      <ol class="passi">
        <li><kbd>Esportazioni</kbd> &rarr; in alto scegli il periodo (<strong>Dal</strong> /
          <strong>Al</strong>) e premi <span class="bottone">Aggiorna periodo</span>.</li>
        <li>Nella sezione <strong>Commercialista</strong> scarica il registro fatture in
          <strong>Excel</strong> o <strong>CSV</strong>: c'&egrave; tutto &mdash; imponibile, ENPAV,
          IVA, totale, e il riepilogo IVA per aliquota.</li>
        <li>Se ti chiede anche le copie, scarica lo <strong>ZIP dei PDF</strong> del periodo.</li>
      </ol>
    </div>

    <div class="caso">
      <div class="caso__cima"><span class="caso__n">10</span>
        <h3>Il Sistema Tessera Sanitaria</h3></div>
      <ol class="passi">
        <li><kbd>Esportazioni</kbd> &rarr; imposta il periodo, poi sezione
          <strong>Sistema Tessera Sanitaria</strong>.</li>
        <li>Scarica il file. Contiene <strong>solo le fatture effettivamente incassate</strong>
          nel periodo, perch&eacute; il TS segue la data di pagamento.</li>
        <li>Guarda <strong>Scarti Sistema TS nel periodo</strong>: elenca i documenti che
          non possono essere trasmessi e perch&eacute; (per esempio manca il codice fiscale).</li>
      </ol>
      <p class="risultato"><b>Se un cliente si oppone &rarr;</b> Spunta
      <em>opposizione TS</em> sulla sua scheda: il suo codice fiscale non verr&agrave; incluso,
      come prevede la norma.</p>
      <div class="nota nota--info">
        <span class="nota__i">&#10003;</span>
        <div>Il tracciato del TS cambia nel tempo: <strong>prima di un invio vero</strong>
        fatti confermare da Giacomo che il formato sia ancora quello corrente.</div>
      </div>
    </div>

    <div class="caso">
      <div class="caso__cima"><span class="caso__n">11</span>
        <h3>Mettere al sicuro i dati</h3></div>
      <ol class="passi">
        <li><kbd>Backup</kbd> &rarr; <span class="bottone">Crea backup</span>.</li>
        <li>Premi <span class="bottone chiaro">Scarica copia (.db)</span> e salva il file
          <strong>su una chiavetta</strong> o in un'altra cartella.</li>
      </ol>
      <div class="nota nota--attenzione">
        <span class="nota__i">&#9888;</span>
        <div>I dati stanno <strong>solo su questo computer</strong>. Se si rompe e non
        hai una copia da un'altra parte, sono persi. Fallo una volta al mese: ci
        vogliono dieci secondi.</div>
      </div>
    </div>
  </section>

  <section>
    <div class="testata">
      <h2>Quando hai finito</h2>
    </div>
    <div class="caso">
      <p><strong>Chiudi la finestra del browser e basta.</strong> Il gestionale si
      accorge che non ci sono pi&ugrave; pagine aperte e <strong>si spegne da
      solo</strong>. Non devi fare altro.</p>
      <p>Se vuoi chiuderlo subito senza chiudere il browser, in fondo a ogni pagina
        c'&egrave; il pulsante <span class="bottone chiaro">&#9211; Chiudi il gestionale</span>.</p>
      <div class="nota nota--info">
        <span class="nota__i">&#10003;</span>
        <div>Puoi lasciarlo aperto <strong>quanto vuoi</strong> &mdash; tutta la
        giornata, mentre fai altro al computer. Finch&eacute; la pagina resta aperta il
        gestionale resta acceso, anche se non lo guardi per ore.</div>
      </div>
      <p class="dim piccolo">E se per abitudine ridai doppio clic sull'icona quando
      &egrave; gi&agrave; aperto, non ne apre un altro: ti riporta davanti la finestra che hai
      gi&agrave;.</p>
    </div>
  </section>

  <section>
    <div class="testata">
      <h2>Se qualcosa non va</h2>
    </div>
    <div class="caso">
      <ol class="passi">
        <li><strong>Doppio clic e non succede niente.</strong> Aspetta cinque secondi:
          la prima apertura &egrave; la pi&ugrave; lenta. Se non parte davvero, compare una
          finestrella di Windows che spiega il perch&eacute;.</li>
        <li><strong>Si &egrave; aperta una pagina bianca o un errore.</strong> Chiudi la
          scheda e ridai doppio clic sull'icona.</li>
        <li><strong>Ho aggiornato il programma e sembra vuoto: non ci sono pi&ugrave; le
          fatture.</strong> Non hai perso niente. Il programma legge i dati dalla cartella
          <strong>dati</strong> che sta <em>accanto</em> a Gestionale.exe: se l'exe nuovo
          &egrave; finito in un'altra cartella, l&igrave; ha creato un archivio nuovo e
          vuoto. Rimetti l'exe nuovo <strong>nella stessa cartella di prima</strong>,
          sostituendo il vecchio, e i tuoi dati tornano. La regola per gli aggiornamenti
          &egrave; una sola: <strong>sostituire l'exe sul posto, mai spostarlo</strong>.</li>
        <li><strong>Premo "Apri WhatsApp" e non si apre niente.</strong> Vuol dire che
          il programma di WhatsApp non &egrave; installato su questo computer. Sulla
          stessa pagina, sotto il pulsante, c'&egrave; scritto <em>"usa WhatsApp
          Web"</em>: quello si apre nel browser. Se invece si apre ma la chat resta
          vuota, WhatsApp non &egrave; collegato: rifai il caso <strong>3</strong>, e
          controlla che il telefono sia acceso e connesso.</li>
        <li><strong>Ho premuto Ctrl+V e non si allega nulla.</strong> Clicca prima
          <em>dentro</em> il campo del messaggio, poi riprova. Se ancora niente, clicca
          la scheda del PDF per scaricarlo e allegalo con la <strong>graffetta</strong>:
          lo trovi anche nella cartella <strong>dati &rarr; da_inviare</strong>.</li>
        <li><strong>Trascino il PDF nella chat e arriva un indirizzo, non il
          documento.</strong> Stai usando WhatsApp <strong>Web</strong>, dentro il
          browser: l&igrave; il trascinamento non consegna il file. Cancella quel
          messaggio e usa <span class="tasti">Ctrl</span> + <span class="tasti">V</span>
          o la <strong>graffetta</strong>. Il trascinamento funziona nel programma di
          WhatsApp, non nella scheda del browser.</li>
        <li><strong>Ho sbagliato una prestazione nel Registro.</strong> Premi la
          <strong>&times;</strong> in fondo alla riga: si toglie. Ma solo se quel cliente
          non &egrave; ancora stato fatturato.</li>
        <li><strong>Ho sbagliato una fattura gi&agrave; emessa.</strong> Non si cancella:
          per legge deve restare. Apri la fattura sbagliata e premi
          <span class="bottone chiaro">Crea nota di credito (storno)</span>.</li>
      </ol>
      <p class="risultato"><b>In ogni caso &rarr;</b> Chiama Giacomo. I dati non si perdono
      per un errore di uso: il programma non cancella niente da solo.</p>
    </div>
  </section>

</div>
"""


def main() -> None:
    out = RADICE / "GUIDA.html"
    out.write_text(HTML, encoding="utf-8")
    print(f"{out}  ({len(HTML) // 1024} KB)")
    # Copia accanto all'exe, dove l'utente la trova senza cercarla.
    dist = RADICE / "dist"
    if dist.is_dir():
        (dist / "GUIDA.html").write_text(HTML, encoding="utf-8")
        print(dist / "GUIDA.html")


if __name__ == "__main__":
    main()
