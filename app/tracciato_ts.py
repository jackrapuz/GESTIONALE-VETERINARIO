"""Modello dei dati per il Sistema Tessera Sanitaria — SPESE VETERINARIE.

===========================================================================
 IMPORTANTE — LEGGERE PRIMA DI MODIFICARE
===========================================================================
Qui vive **la forma dei dati** prescritta dal disciplinare tecnico (Allegato A al
DM 19/10/2020). Il resto del codice non conosce la struttura: ``export_ts.py``
raccoglie i documenti, questo modulo li modella, ``ts_xml.py`` li scrive.

**Cosa e' fissato dal disciplinare e non dipende dall'XSD** (quindi sta qui):

- struttura ``Fornitura -> DocumentoFiscale -> VoceSpesa``;
- ``IdSpesa`` come chiave composta (P.IVA + data emissione + identificativo);
- una **voce di spesa per riga**, non un unico importo per documento;
- i flag obbligatori (operazione, pagamento anticipato, opposizione);
- i codici di tipologia spesa ammessi a un veterinario (par. 2.6.1).

**Cosa NON e' ancora noto** e vive dietro una cucitura:

- nomi e ordine degli elementi XML -> ``app/ts_xml.py``;
- cifratura RSA del codice fiscale -> ``app/ts_cifratura.py``.

Entrambi richiedono materiale dell'area riservata di sistemats.it (XSD corrente
e certificato X.509), raggiungibile solo con le credenziali della professionista.

**Perche' non c'e' piu' il vecchio CSV a 9 colonne.** Era una bozza: dichiarava
``SV-2026-bozza`` e nessuno l'aveva mai confrontata col documento ufficiale. Il
Sistema TS non accetta CSV, non accetta il codice fiscale in chiaro, e vuole le
singole voci di spesa. Quel file veniva respinto.
===========================================================================
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.calcolo import dec, q2
from app.validazioni import TIPI_SPESA_TS, is_codice_fiscale, is_tipo_spesa_ts

# --- Costanti del tracciato ------------------------------------------------
TIPO_DOCUMENTO_FATTURA = "F"      # 'F' = fattura, 'D' = documento commerciale
FLAG_SI = "1"
FLAG_NO = "0"

# Operazioni sul record (Allegato A, cap. 3). Finche' non esiste un registro
# degli invii effettuati, ogni documento e' un inserimento: nulla e' mai stato
# trasmesso, quindi non ci sono variazioni ne' cancellazioni da comunicare.
OP_INSERIMENTO = "I"
OP_VARIAZIONE = "V"
OP_RIMBORSO = "R"
OP_CANCELLAZIONE = "C"

# "Numero progressivo del dispositivo che genera il documento": il gestionale
# gira su una postazione sola, quindi e' costante.
#
# ATTENZIONE: dispositivo e progressivo compongono la chiave con cui il Sistema
# TS identifica il documento. Cambiarli dopo il primo invio significa che le
# correzioni successive non troverebbero piu' il record da correggere: si
# creerebbero duplicati invece di variazioni. Sono da considerare immutabili.
DISPOSITIVO = "1"


def data_ts(valore: str) -> str:
    """Data del tracciato (GG/MM/AAAA) da una data ISO del database."""
    v = (valore or "").strip()
    if len(v) >= 10 and v[4] == "-":
        return f"{v[8:10]}/{v[5:7]}/{v[0:4]}"
    return v


def importo_ts(valore) -> str:
    """Importo con due decimali e punto decimale (es. '99.55')."""
    return f"{q2(valore):.2f}"


# --- Modello ---------------------------------------------------------------
@dataclass(frozen=True)
class VoceSpesa:
    """Una riga della fattura, come la vede il Sistema TS.

    ``importo`` e' **lordo di ENPAV e IVA**: e' quanto il cliente ha speso per
    quella voce, non l'imponibile.
    """

    tipo_spesa: str
    importo: Decimal
    aliquota: Decimal


@dataclass(frozen=True)
class IdSpesa:
    """Chiave con cui il Sistema TS identifica il documento fiscale.

    Le tre parti restano separate perche' il modo di comporle in una stringa e'
    dettato dall'XSD, che ancora non abbiamo: comporle qui vorrebbe dire
    indovinare, e questa e' la chiave usata per variazioni e cancellazioni —
    l'ultimo posto dove conviene tirare a indovinare.
    """

    partita_iva: str
    data_emissione: str          # GG/MM/AAAA
    dispositivo: str
    numero_documento: str        # progressivo del documento


@dataclass(frozen=True)
class DocumentoFiscale:
    numero_visualizzato: str     # solo per diagnostica: non fa parte del tracciato
    id_spesa: IdSpesa
    data_pagamento: str          # GG/MM/AAAA
    flag_pagamento_anticipato: bool
    flag_operazione: str
    cf_assistito: str            # IN CHIARO: la cifratura avviene scrivendo il file
    opposizione: bool
    pagamento_tracciato: bool
    voci: tuple[VoceSpesa, ...]
    tipo_documento: str = TIPO_DOCUMENTO_FATTURA

    @property
    def totale(self) -> Decimal:
        return sum((v.importo for v in self.voci), Decimal("0.00"))


@dataclass(frozen=True)
class Fornitura:
    """Il contenuto di un invio: l'emittente e i suoi documenti.

    **Non va scritta su disco cosi' com'e'**: contiene i codici fiscali in
    chiaro, che il disciplinare (par. 4.4) impone di cifrare prima di uscire.
    """

    cf_professionista: str
    documenti: tuple[DocumentoFiscale, ...]


# --- Costruzione -----------------------------------------------------------
def ripartisci_lordo(righe: list[dict], gruppi: list[dict]) -> list[Decimal]:
    """Importo lordo (ENPAV + IVA inclusi) di ogni riga, a partire dai gruppi IVA.

    Il database tiene l'imponibile per riga, mentre ENPAV e IVA sono calcolati per
    **gruppo di aliquota** e arrotondati li'. Il Sistema TS vuole invece un
    importo per voce di spesa, quindi il lordo del gruppo va ripartito fra le sue
    righe in proporzione all'imponibile.

    Ripartire e arrotondare riga per riga farebbe perdere qualche centesimo: la
    somma delle voci non tornerebbe col totale del documento, e sarebbe un invio
    che dichiara un importo diverso da quello fatturato. Il residuo viene quindi
    assegnato per intero alla riga di imponibile maggiore (a parita', la prima):
    una regola qualsiasi va bene purche' sia **deterministica**, perche' due
    generazioni della stessa fattura devono dare lo stesso file.
    """
    lordo_per_aliquota: dict[str, Decimal] = {}
    for g in gruppi:
        chiave = str(dec(g["aliquota"]))
        lordo_per_aliquota[chiave] = q2(dec(g["base_iva"]) + dec(g["iva"]))

    quote: list[Decimal] = [Decimal("0.00")] * len(righe)
    for chiave, lordo_gruppo in lordo_per_aliquota.items():
        indici = [i for i, r in enumerate(righe)
                  if str(dec(r["aliquota_iva"])) == chiave]
        imponibile_gruppo = sum((dec(righe[i]["imponibile_riga"]) for i in indici),
                                Decimal("0"))
        if not indici:
            continue
        if imponibile_gruppo == 0:
            # Gruppo a importo nullo: niente da ripartire in proporzione.
            quote[indici[0]] = lordo_gruppo
            continue
        for i in indici:
            quote[i] = q2(lordo_gruppo * dec(righe[i]["imponibile_riga"])
                          / imponibile_gruppo)
        residuo = lordo_gruppo - sum(quote[i] for i in indici)
        if residuo:
            maggiore = max(indici, key=lambda i: (dec(righe[i]["imponibile_riga"]), -i))
            quote[maggiore] += residuo
    return quote


def costruisci_documento(studio: dict, fattura: dict, gruppi: list[dict],
                         flag_operazione: str = OP_INSERIMENTO) -> DocumentoFiscale:
    """Un documento fiscale del tracciato a partire da una fattura del database.

    L'importo trasmesso e' ``totale_documento``, **non** ``netto_a_pagare``: la
    ritenuta d'acconto e' versata all'erario per conto della professionista, ma
    la spesa sostenuta dal cliente resta l'intero. Il Sistema TS chiede quanto ha
    speso il cliente.
    """
    righe = fattura["righe"]
    quote = ripartisci_lordo(righe, gruppi)
    voci = tuple(
        VoceSpesa(tipo_spesa=(r["tipo_spesa_ts"] or "").strip().upper(),
                  importo=quote[i], aliquota=dec(r["aliquota_iva"]))
        for i, r in enumerate(righe)
    )
    opposizione = bool(int(fattura["opposizione_ts"] or 0))
    emissione = str(fattura["data_emissione"] or "")
    pagamento = str(fattura["data_pagamento"] or "")
    return DocumentoFiscale(
        numero_visualizzato=fattura["numero_visualizzato"],
        id_spesa=IdSpesa(
            partita_iva=(studio.get("partita_iva") or "").strip(),
            data_emissione=data_ts(emissione),
            dispositivo=DISPOSITIVO,
            numero_documento=str(fattura["numero_progressivo"]),
        ),
        data_pagamento=data_ts(pagamento),
        # Obbligatorio solo quando il pagamento precede l'emissione.
        flag_pagamento_anticipato=bool(pagamento and emissione and pagamento < emissione),
        flag_operazione=flag_operazione,
        # Con opposizione il codice fiscale non si trasmette: e' proprio il senso
        # dell'opposizione. Il flag dice al Sistema TS che l'assenza e' voluta.
        cf_assistito="" if opposizione else (fattura["cli_codice_fiscale"] or "").strip(),
        opposizione=opposizione,
        pagamento_tracciato=bool(int(fattura["pagamento_tracciato"] or 0)),
        voci=voci,
    )


# --- Validazione -----------------------------------------------------------
def valida_documento(doc: DocumentoFiscale, totale_atteso: Decimal) -> list[str]:
    """Errori che impediscono la trasmissione (lista vuota = conforme).

    ``totale_atteso`` e' il totale della fattura come sta nel database: se le voci
    non ci quadrano, il file dichiarerebbe al Sistema TS un importo diverso da
    quello fatturato al cliente. E' l'errore piu' grave possibile qui, perche'
    passerebbe i controlli formali del portale e sbaglierebbe la detrazione.
    """
    errori: list[str] = []

    if not doc.id_spesa.partita_iva:
        errori.append("Manca la partita IVA dello studio (Impostazioni): "
                      "senza non si puo' identificare il documento.")
    if not doc.id_spesa.data_emissione:
        errori.append("Manca la data di emissione.")
    if not doc.data_pagamento:
        errori.append("Manca la data di pagamento.")

    if not doc.opposizione and not doc.cf_assistito:
        errori.append("Manca il codice fiscale del cliente (e non c'e' opposizione).")
    if doc.cf_assistito and not is_codice_fiscale(doc.cf_assistito):
        errori.append(f"Codice fiscale del cliente non valido: {doc.cf_assistito}")

    if not doc.voci:
        errori.append("Il documento non ha righe.")
    for v in doc.voci:
        if not is_tipo_spesa_ts(v.tipo_spesa):
            ammessi = "/".join(TIPI_SPESA_TS)
            errori.append(f"Tipo di spesa non ammesso su una riga: "
                          f"{v.tipo_spesa or '(vuoto)'} (ammessi {ammessi})")
        if v.importo <= 0:
            errori.append(f"Importo non positivo su una riga: {importo_ts(v.importo)}")

    if doc.voci and doc.totale != q2(totale_atteso):
        errori.append(
            f"Le voci sommano {importo_ts(doc.totale)} ma il documento vale "
            f"{importo_ts(totale_atteso)}: differenza di "
            f"{importo_ts(doc.totale - q2(totale_atteso))}.")

    if doc.flag_operazione not in (OP_INSERIMENTO, OP_VARIAZIONE,
                                   OP_RIMBORSO, OP_CANCELLAZIONE):
        errori.append(f"Flag operazione non ammesso: {doc.flag_operazione}")
    return errori
