"""Marchio dello studio: il monogramma con la testa di cavallo.

Il disegno e' quello fornito (`app/static/img/marchio.png`), conservato come
**maschera**: nessun colore dentro, solo l'opacita' del tratto. Da un'unica maschera
escono tutte le declinazioni — verde su carta, chiaro in negativo, ottone, nero per
la fotocopia — perche' il colore lo mette chi la usa:

- nelle pagine, via CSS (`.marchio` in `app/static/css/stile.css`) con
  `background-color: currentColor`, quindi eredita il colore del testo che la
  circonda e cambia da sola fra sfondo chiaro e scuro;
- nel PDF, colorandola al volo con `disegna_pdf()`.

Il file sta in `app/static`, che `Gestionale.spec` impacchetta gia' dentro l'exe:
nessun file sciolto da spedire insieme al programma. Pillow, usato qui per la
colorazione, arriva gia' con reportlab: nessuna dipendenza nuova.
"""
from pathlib import Path

PERCORSO = Path(__file__).resolve().parent / "static" / "img" / "marchio.png"
URL = "/static/img/marchio.png"

# Dimensioni della maschera. Sono qui perche' servono per le proporzioni senza
# dover aprire il file a ogni pagina; un test verifica che coincidano con esso.
LARGHEZZA, ALTEZZA = 376, 457
PROPORZIONE = LARGHEZZA / ALTEZZA

_cache = {}


def larghezza_per(altezza):
    """Larghezza che il marchio occupa a una data altezza, mantenendo le proporzioni."""
    return altezza * PROPORZIONE


def _colorata(colore):
    """La maschera tinta del colore richiesto, su sfondo trasparente."""
    chiave = str(colore)
    if chiave not in _cache:
        from PIL import Image
        # La forma sta nel canale alfa: e' quello che usa anche la maschera CSS.
        maschera = Image.open(PERCORSO).convert("RGBA").getchannel("A")
        rgb = tuple(int(round(v * 255)) for v in colore.rgb())
        immagine = Image.new("RGBA", maschera.size, rgb + (0,))
        immagine.putalpha(maschera)
        _cache[chiave] = immagine
    return _cache[chiave]


def _png(colore):
    """I byte PNG del marchio colorato, con la trasparenza conservata."""
    chiave = ("png", str(colore))
    if chiave not in _cache:
        import io
        buf = io.BytesIO()
        _colorata(colore).save(buf, "PNG")
        _cache[chiave] = buf.getvalue()
    return _cache[chiave]


def flowable(altezza, colore):
    """Il marchio come elemento impaginabile ReportLab, gia' colorato.

    `altezza` in punti; la larghezza segue le proporzioni. Si passa un file in
    memoria e non l'immagine: platypus.Image vuole un percorso o un file-like,
    e ogni chiamata ne riceve uno nuovo perche' ReportLab lo consuma leggendolo.
    """
    import io

    from reportlab.platypus import Image

    # lazy=0: di default platypus rileggerebbe lo stream al momento del disegno,
    # ma a quel punto e' gia' stato consumato e l'immagine esce vuota.
    return Image(io.BytesIO(_png(colore)),
                 width=larghezza_per(altezza), height=altezza,
                 mask="auto", lazy=0)
