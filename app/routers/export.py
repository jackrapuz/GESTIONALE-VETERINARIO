"""Router Esportazioni: Sistema Tessera Sanitaria e commercialista."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

from app import export_commercialista as exc
from app import export_ts
from app.db import get_conn
from app.routers.impostazioni import leggi_studio
from app.templating import templates

router = APIRouter()


def _periodo(dal: str | None, al: str | None) -> tuple[str, str]:
    """Default: anno corrente intero, se non specificato."""
    anno = date.today().year
    return (dal or f"{anno}-01-01", al or f"{anno}-12-31")


def _scarica(contenuto: bytes, nome: str, media: str) -> Response:
    return Response(content=contenuto, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@router.get("/export", response_class=HTMLResponse)
def pagina(request: Request, dal: str | None = None, al: str | None = None):
    dal, al = _periodo(dal, al)
    conn = get_conn()
    try:
        ts = export_ts.genera_export(conn, dal, al)
        n_registro = len(exc.registro(conn, dal, al))
    finally:
        conn.close()
    return templates.TemplateResponse(
        request, "export.html",
        {"titolo": "Esportazioni", "dal": dal, "al": al,
         "ts_ok": ts["n_ok"], "ts_scarti": ts["n_scarti"], "ts_dettaglio_scarti": ts["scarti"],
         "ts_versione": ts["versione"], "n_registro": n_registro},
    )


# --- Sistema TS ------------------------------------------------------------
@router.get("/export/ts.csv")
def ts_csv(dal: str | None = None, al: str | None = None):
    dal, al = _periodo(dal, al)
    conn = get_conn()
    try:
        out = export_ts.genera_export(conn, dal, al)
    finally:
        conn.close()
    return _scarica(out["csv"], f"sistema_ts_{dal}_{al}.csv", "text/csv")


@router.get("/export/ts-scarti.csv")
def ts_scarti(dal: str | None = None, al: str | None = None):
    dal, al = _periodo(dal, al)
    conn = get_conn()
    try:
        out = export_ts.genera_export(conn, dal, al)
    finally:
        conn.close()
    return _scarica(out["scarti_csv"], f"sistema_ts_scarti_{dal}_{al}.csv", "text/csv")


# --- Commercialista --------------------------------------------------------
@router.get("/export/commercialista.csv")
def comm_csv(dal: str | None = None, al: str | None = None):
    dal, al = _periodo(dal, al)
    conn = get_conn()
    try:
        contenuto = exc.genera_csv(conn, dal, al)
    finally:
        conn.close()
    return _scarica(contenuto, f"registro_fatture_{dal}_{al}.csv", "text/csv")


@router.get("/export/commercialista.xlsx")
def comm_xlsx(dal: str | None = None, al: str | None = None):
    dal, al = _periodo(dal, al)
    conn = get_conn()
    try:
        contenuto = exc.genera_xlsx(conn, dal, al)
    finally:
        conn.close()
    return _scarica(
        contenuto, f"registro_fatture_{dal}_{al}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.get("/export/commercialista-pdf.zip")
def comm_zip(dal: str | None = None, al: str | None = None):
    dal, al = _periodo(dal, al)
    conn = get_conn()
    try:
        studio = leggi_studio(conn)
        contenuto = exc.genera_zip_pdf(conn, dal, al, studio)
    finally:
        conn.close()
    return _scarica(contenuto, f"copie_fatture_{dal}_{al}.zip", "application/zip")
