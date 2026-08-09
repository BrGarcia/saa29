"""
app/web/pages/mobile_router.py
Router dedicado para servir as páginas HTML da interface mobile (/m/).
Projetado com foco em concisão, alta legibilidade e conformidade CSP.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.bootstrap.dependencies import get_current_user, DBSession
from app.modules.publicacoes import service as publicacoes_service

router = APIRouter(prefix="/m", tags=["Mobile Frontend"])

templates = Jinja2Templates(directory="app/web/templates")


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def mobile_frota_page(request: Request, user=Depends(get_current_user)):
    """Dashboard Cockpit Mobile — Lista de Frota para Linha de Voo."""
    return templates.TemplateResponse("mobile/frota.html", {"request": request, "user": user})


@router.get("/aeronave/{aeronave_id}", response_class=HTMLResponse, include_in_schema=False)
async def mobile_tarefas_aeronave_page(request: Request, aeronave_id: str, user=Depends(get_current_user)):
    """Lista de Tarefas e Panes da Aeronave para Mantenedor em 1 Toque."""
    return templates.TemplateResponse("mobile/tarefas_aeronave.html", {
        "request": request,
        "aeronave_id": aeronave_id,
        "user": user
    })


@router.get("/publicacoes", response_class=HTMLResponse, include_in_schema=False)
async def mobile_publicacoes_page(request: Request, db: DBSession, user=Depends(get_current_user)):
    """
    Busca + navegação do acervo, mobile — reusa `publicacoes.js` do desktop e as
    mesmas rotas de navegação (`/publicacoes/manuais/...`, Etapa 2 de
    `09_plano_configuracoes.md`), para não manter um segundo conjunto de telas
    em sincronia.
    """
    manuais = await publicacoes_service.listar_manuais_vigentes(db)
    categorias_manuais: dict[str, list[dict]] = {}
    for manual in manuais:
        categorias_manuais.setdefault(manual["categoria"], []).append(manual)
    return templates.TemplateResponse(
        "mobile/publicacoes.html",
        {"request": request, "user": user, "categorias_manuais": categorias_manuais},
    )
