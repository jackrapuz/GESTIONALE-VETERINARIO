"""Crea l'icona dell'eseguibile: marchio in ottone su fondo verde scuderia.

Si esegue a mano quando cambia il marchio; il risultato (app/static/img/marchio.ico)
sta in git, cosi' il build dell'exe non dipende da questo script.

Ottone su verde pieno e non il marchio da solo: sul desktop un tratto sottile si
perde, una tessera piena si riconosce da lontano.

Alle misure piccole il monogramma intero diventa comunque una macchia (ingrossare
il tratto peggiora le cose: diventa un blocco). Sotto i 32 px si usa quindi la
sola testa di cavallo, che ha tratti piu' larghi ed e' la parte riconoscibile.
"""
from PIL import Image

VERDE = (0x22, 0x3d, 0x33)
OTTONE = (0xc9, 0x93, 0x3a)   # ottone schiarito: su verde regge meglio del #b5822e
MISURE = [16, 24, 32, 48, 64, 128, 256]


# Sotto questa misura il monogramma intero diventa una macchia: si usa allora la
# sola testa di cavallo, che ha tratti piu' larghi ed e' la parte riconoscibile.
SOGLIA_SOLO_TESTA = 32
TESTA = (100, 0, 350, 235)


def riquadro(maschera, lato):
    """Un'icona quadrata: fondo verde pieno, marchio in ottone al centro."""
    segno_pieno = maschera.crop(TESTA) if lato < SOGLIA_SOLO_TESTA else maschera
    margine = 0.14 if lato >= 48 else 0.08   # da piccola serve piu' segno e meno aria
    utile = int(lato * (1 - 2 * margine))
    w = max(1, int(utile * segno_pieno.width / segno_pieno.height))

    segno = segno_pieno.resize((w, utile), Image.LANCZOS)

    icona = Image.new("RGBA", (lato, lato), VERDE + (255,))
    icona.paste(Image.new("RGBA", segno.size, OTTONE + (255,)),
                ((lato - w) // 2, (lato - utile) // 2), segno)
    return icona


maschera = Image.open("app/static/img/marchio.png").convert("RGBA").getchannel("A")
immagini = [riquadro(maschera, m) for m in MISURE]
immagini[-1].save("app/static/img/marchio.ico", format="ICO",
                  sizes=[(m, m) for m in MISURE], append_images=immagini[:-1])
print("creata app/static/img/marchio.ico con le misure", MISURE)
