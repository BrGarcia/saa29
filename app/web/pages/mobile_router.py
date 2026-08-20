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
async def mobile_aeronave_page(request: Request, aeronave_id: str, user=Depends(get_current_user)):
    """Hub da aeronave: Panes, Inspeções, Vencimentos e Inventário em 4 abas."""
    return templates.TemplateResponse("mobile/aeronave.html", {
        "request": request,
        "aeronave_id": aeronave_id,
        "user": user
    })


@router.get("/pane/nova", response_class=HTMLResponse, include_in_schema=False)
async def mobile_pane_nova_page(request: Request, aeronave_id: str, user=Depends(get_current_user)):
    """Relato rápido de nova pane, com aeronave pré-preenchida."""
    return templates.TemplateResponse("mobile/pane_nova.html", {
        "request": request,
        "aeronave_id": aeronave_id,
        "user": user
    })


@router.get("/pane/{pane_id}", response_class=HTMLResponse, include_in_schema=False)
async def mobile_pane_detalhe_page(request: Request, pane_id: str, user=Depends(get_current_user)):
    """Detalhe da pane: anexos, assumir responsabilidade, comentar e concluir."""
    return templates.TemplateResponse("mobile/pane_detalhe.html", {
        "request": request,
        "pane_id": pane_id,
        "user": user
    })


@router.get("/inspecao/{inspecao_id}", response_class=HTMLResponse, include_in_schema=False)
async def mobile_inspecao_checklist_page(request: Request, inspecao_id: str, user=Depends(get_current_user)):
    """Checklist de inspeção: execução de tarefa (Pendente/Concluída/N-A) + tarefa avulsa."""
    return templates.TemplateResponse("mobile/inspecao_checklist.html", {
        "request": request,
        "inspecao_id": inspecao_id,
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
