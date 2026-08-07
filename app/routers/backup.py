"""Router Backup e manutenzione: copia, ripristino e dati di esempio."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app import backup as bkp
from app.db import DB_PATH, get_conn
from app.templating import templates
from dati_esempio.carica_esempi import carica_dati_esempio

router = APIRouter()


@router.get("/backup", response_class=HTMLResponse)
def pagina(request: Request):
    dim_kb = round(DB_PATH.stat().st_size / 1024, 1) if DB_PATH.exists() else 0
    return templates.TemplateResponse(
        request, "backup.html",
        {"titolo": "Backup e manutenzione", "backups": bkp.elenco_backup(), "dim_kb": dim_kb},
    )


@router.post("/backup/crea")
def crea():
    dest = bkp.crea_backup()
    return RedirectResponse(f"/backup?msg=Backup+creato:+{dest.name}", status_code=303)


@router.get("/backup/scarica")
def scarica():
    """Esporta (scarica) una copia coerente del database corrente."""
    copia = bkp.crea_backup(prefisso="copia")
    return FileResponse(str(copia), filename=copia.name, media_type="application/octet-stream")


@router.post("/backup/ripristina")
async def ripristina(request: Request):
    form = await request.form()
    nome = str(form.get("nome_backup", "")).strip()
    try:
        sicurezza = bkp.ripristina(nome)
    except ValueError as e:
        return RedirectResponse(f"/backup?msg=Errore:+{e}", status_code=303)
    return RedirectResponse(
        f"/backup?msg=Ripristinato+da+{nome}+(copia+di+sicurezza:+{sicurezza.name})",
        status_code=303)


@router.post("/backup/ripristina-upload")
async def ripristina_upload(request: Request):
    form = await request.form()
    file = form.get("file")
    if file is None or not getattr(file, "filename", ""):
        return RedirectResponse("/backup?msg=Nessun+file+selezionato", status_code=303)
    contenuto = await file.read()
    # **Solo il nome, mai il percorso.** ``file.filename`` arriva dal browser e
    # puo' contenere separatori: un nome come "..\\..\\qualcosa" farebbe scrivere
    # il file fuori dalla cartella temporanea. Qui l'unico che carica e' la
    # dottoressa dal proprio computer, quindi non e' un attacco - e' che un nome
    # storto non deve poter scrivere dove gli pare.
    tmp = Path(tempfile.gettempdir()) / f"ripristino_{Path(file.filename).name}"
    tmp.write_bytes(contenuto)
    try:
        sicurezza = bkp.ripristina_da_file(tmp)
    except ValueError as e:
        return RedirectResponse(f"/backup?msg=Errore:+{e}", status_code=303)
    finally:
        tmp.unlink(missing_ok=True)
    return RedirectResponse(
        f"/backup?msg=Ripristinato+dal+file+caricato+(copia+di+sicurezza:+{sicurezza.name})",
        status_code=303)


@router.post("/dati-esempio")
def dati_esempio():
    conn = get_conn()
    try:
        r = carica_dati_esempio(conn)
    finally:
        conn.close()
    return RedirectResponse(
        f"/backup?msg=Dati+di+esempio:+{r['clienti']}+clienti,+{r['prestazioni']}+prestazioni,+{r['fatture']}+fatture",
        status_code=303)
