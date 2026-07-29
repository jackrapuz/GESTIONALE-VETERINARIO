"""Test del marchio (app/marchio.py).

Il marchio e' una maschera senza colore: i rischi sono che il file non finisca
nell'exe, che le proporzioni dichiarate divergano da quelle vere (il marchio si
schiaccerebbe) e che la maschera perda la trasparenza — cioe' che si porti dietro
un rettangolo di sfondo sulla barra verde e in stampa.
"""
from PIL import Image
from reportlab.lib import colors

from app import marchio


def test_il_file_della_maschera_esiste_dentro_il_pacchetto():
    """Sta sotto app/static, che Gestionale.spec impacchetta gia' nell'exe."""
    assert marchio.PERCORSO.is_file()
    assert marchio.PERCORSO.parent.parent.name == "static"


def test_le_proporzioni_dichiarate_sono_quelle_del_file():
    """Se divergono, il marchio viene stampato schiacciato senza che nulla fallisca."""
    with Image.open(marchio.PERCORSO) as im:
        assert im.size == (marchio.LARGHEZZA, marchio.ALTEZZA)
    assert marchio.larghezza_per(457) == 376


def test_la_forma_sta_nel_canale_alfa():
    """La maschera CSS legge l'alfa: senza, il marchio diventa un rettangolo pieno."""
    with Image.open(marchio.PERCORSO) as im:
        assert im.mode == "RGBA", "senza canale alfa la maschera non ritaglia nulla"
        istogramma = im.getchannel("A").histogram()
    assert istogramma[0] > sum(istogramma) * 0.5, "manca lo sfondo trasparente"
    assert sum(istogramma[250:]) > 5000, "il tratto pieno e' sparito"


def _pixel(im):
    """I pixel RGBA come tuple, senza passare da API Pillow deprecate."""
    grezzo = im.tobytes()
    return [tuple(grezzo[i:i + 4]) for i in range(0, len(grezzo), 4)]


def test_la_colorazione_rispetta_il_colore_chiesto():
    im = marchio._colorata(colors.HexColor("#223d33"))
    assert im.mode == "RGBA"
    pixel = _pixel(im)
    pieni = [p for p in pixel if p[3] > 250]
    assert pieni, "nessun pixel opaco"
    assert all(p[:3] == (0x22, 0x3d, 0x33) for p in pieni)
    # lo sfondo resta trasparente: e' cio' che lo fa funzionare sul verde
    assert any(p[3] == 0 for p in pixel)


def test_colori_diversi_non_si_confondono_in_cache():
    verde = marchio._colorata(colors.HexColor("#223d33"))
    bianco = marchio._colorata(colors.HexColor("#ffffff"))
    assert verde is not bianco
    assert next(p[:3] for p in _pixel(bianco) if p[3] > 250) == (255, 255, 255)


def test_flowable_ha_le_proporzioni_giuste():
    f = marchio.flowable(40, colors.black)
    assert f.drawHeight == 40
    assert abs(f.drawWidth - marchio.larghezza_per(40)) < 0.01


# --- icona dell'eseguibile ------------------------------------------------

ICONA = marchio.PERCORSO.parent / "marchio.ico"


def test_l_icona_ha_tutte_le_misure_che_windows_chiede():
    """Manca una misura e Windows ne scala un'altra, con risultati sgranati."""
    with Image.open(ICONA) as im:
        misure = {m for m, _ in im.ico.sizes()}
    assert {16, 24, 32, 48, 64, 128, 256} <= misure


def test_l_icona_e_ottone_su_verde_e_non_e_vuota():
    """A ogni misura devono esserci sia il fondo sia il segno: se il tratto sparisce
    resta un quadrato verde pieno, che sul desktop non dice piu' nulla."""
    # Si misura sul canale rosso, dove verde (0x22) e ottone (0xc9) sono lontanissimi.
    # La soglia e' relativa al fondo, non assoluta: alle misure piccole l'antialiasing
    # smorza l'ottone e un confronto su "quanto e' chiaro" darebbe falsi allarmi.
    for lato in (16, 24, 32, 48, 64, 128, 256):
        im = Image.open(ICONA)
        im.size = (lato, lato)
        pixel = im.convert("RGB").getchannel("R").tobytes()
        fondo = sum(1 for r in pixel if r <= 0x30)
        segno = sum(1 for r in pixel if r > 0x45)
        assert fondo > len(pixel) * 0.5, f"a {lato} px manca il fondo verde"
        assert segno > len(pixel) * 0.04, f"a {lato} px il segno e' sparito"


def test_lo_spec_punta_all_icona():
    spec = (marchio.PERCORSO.parents[3] / "Gestionale.spec").read_text(encoding="utf-8")
    assert 'icon="app/static/img/marchio.ico"' in spec
