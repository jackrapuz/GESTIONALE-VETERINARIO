/* Emissione fattura: righe dinamiche + anteprima totali.
 *
 * Il calcolo qui e' solo un'ANTEPRIMA per l'utente: i totali definitivi li
 * ricalcola il server (app/calcolo.py) all'emissione. La logica rispecchia
 * comunque quella del server: riga -> gruppo per aliquota -> ENPAV -> base IVA
 * -> IVA -> totale, con arrotondamento a 2 decimali.
 */
(function () {
  "use strict";
  var D = window.DATI_FATTURA || { clienti: [], prestazioni: [], enpavPct: "2" };
  var enpavPct = parseFloat(String(D.enpavPct).replace(",", ".")) || 0;

  var body = document.getElementById("righe-body");
  var tpl = document.getElementById("tpl-riga");
  var selCliente = document.getElementById("cliente_id");
  var selListino = document.getElementById("add-listino");

  function num(v) {
    var n = parseFloat(String(v == null ? "" : v).replace(",", "."));
    return isFinite(n) ? n : 0;
  }
  function round2(x) { return Math.round((x + Number.EPSILON) * 100) / 100; }
  function euro(x) {
    return (x || 0).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function aggiungiRiga(preset) {
    var tr = tpl.content.firstElementChild.cloneNode(true);
    body.appendChild(tr);
    if (preset) {
      tr.querySelector('[name=r_prestazione_id]').value = preset.id || "";
      tr.querySelector('[name=r_descrizione]').value = preset.descrizione || "";
      tr.querySelector('[name=r_prezzo]').value = preset.prezzo_unitario || "0.00";
      tr.querySelector('[name=r_aliquota]').value = preset.aliquota_iva || "22";
      tr.querySelector('[name=r_tipo_spesa]').value = preset.tipo_spesa_ts || "SV";
    }
    tr.querySelector(".rimuovi").addEventListener("click", function () {
      tr.remove();
      ricalcola();
    });
    tr.addEventListener("input", ricalcola);
    ricalcola();
    return tr;
  }

  function ricalcola() {
    var scontoCliente = num(document.getElementById("sconto_cliente_pct").value);
    var gruppi = {};      // aliquota -> imponibile
    var ordine = [];
    body.querySelectorAll("tr.riga-fattura").forEach(function (tr) {
      var qta = num(tr.querySelector('[name=r_quantita]').value);
      var prezzo = num(tr.querySelector('[name=r_prezzo]').value);
      var sc = num(tr.querySelector('[name=r_sconto]').value);
      var aliq = num(tr.querySelector('[name=r_aliquota]').value);
      var imp = round2(qta * prezzo * (1 - sc / 100) * (1 - scontoCliente / 100));
      tr.querySelector(".imp-riga").textContent = euro(imp);
      var k = String(aliq);
      if (!(k in gruppi)) { gruppi[k] = 0; ordine.push(k); }
      gruppi[k] += imp;
    });

    var imponibile = 0, enpav = 0, base = 0, iva = 0;
    ordine.forEach(function (k) {
      var impG = round2(gruppi[k]);
      var enpavG = round2(impG * enpavPct / 100);
      var baseG = round2(impG + enpavG);
      var ivaG = round2(baseG * parseFloat(k) / 100);
      imponibile += impG; enpav += enpavG; base += baseG; iva += ivaG;
    });
    imponibile = round2(imponibile); enpav = round2(enpav);
    base = round2(base); iva = round2(iva);
    var totale = round2(base + iva);

    document.getElementById("t-imponibile").textContent = euro(imponibile);
    document.getElementById("t-enpav-pct").textContent = enpavPct;
    document.getElementById("t-enpav").textContent = euro(enpav);
    document.getElementById("t-base").textContent = euro(base);
    document.getElementById("t-iva").textContent = euro(iva);
    document.getElementById("t-totale").textContent = euro(totale);

    var applicaRit = document.getElementById("ritenuta_applicata").checked;
    var rigaRit = document.getElementById("riga-ritenuta");
    var rigaNetto = document.getElementById("riga-netto");
    if (applicaRit) {
      var rit = round2(imponibile * num(document.getElementById("ritenuta_pct").value) / 100);
      document.getElementById("t-ritenuta").textContent = euro(rit);
      document.getElementById("t-netto").textContent = euro(round2(totale - rit));
      rigaRit.style.display = ""; rigaNetto.style.display = "";
    } else {
      rigaRit.style.display = "none"; rigaNetto.style.display = "none";
    }
  }

  // Precompila sconto/opposizione/ritenuta in base al cliente selezionato.
  function applicaCliente() {
    var id = selCliente.value;
    var c = (D.clienti || []).filter(function (x) { return String(x.id) === String(id); })[0];
    var chkRit = document.getElementById("ritenuta_applicata");
    var boxRit = document.getElementById("box-ritenuta");
    if (c) {
      document.getElementById("sconto_cliente_pct").value = c.sconto_default_pct || "0";
      document.getElementById("opposizione_ts").checked = !!Number(c.opposizione_ts_default);
      var sostituto = !!Number(c.sostituto_imposta);
      chkRit.disabled = !sostituto;
      if (!sostituto) chkRit.checked = false;
      boxRit.style.opacity = sostituto ? "1" : "0.5";
    }
    ricalcola();
  }

  document.getElementById("agg-riga").addEventListener("click", function () { aggiungiRiga(); });
  selListino.addEventListener("change", function () {
    var id = selListino.value;
    var p = (D.prestazioni || []).filter(function (x) { return String(x.id) === String(id); })[0];
    if (p) aggiungiRiga(p);
    selListino.value = "";
  });
  selCliente.addEventListener("change", applicaCliente);
  document.getElementById("ritenuta_applicata").addEventListener("change", ricalcola);
  document.getElementById("ritenuta_pct").addEventListener("input", ricalcola);
  document.getElementById("sconto_cliente_pct").addEventListener("input", ricalcola);

  // Stato iniziale: una riga vuota pronta all'uso.
  aggiungiRiga();
  applicaCliente();
})();
