"""
app/pages/router.py
Rotas do Frontend (Jinja2 Templates). Servindo o MVP de Interface.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.bootstrap.dependencies import get_current_user, AdminRequired

router = APIRouter(tags=["Frontend"])

# Diretório base dos templates (raiz do repositório)
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/", include_in_schema=False)
async def root_page():
    """Redireciona a raiz para o Dashboard (página principal do sistema)."""
    return RedirectResponse(url="/dashboard", status_code=307)


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_page(request: Request, _=Depends(get_current_user)):
    """Dashboard Central — página inicial do sistema para todos os perfis."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    """Renderiza a tela de Login."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/panes", response_class=HTMLResponse, include_in_schema=False)
async def list_panes_page(request: Request, _=Depends(get_current_user)):
    """Renderiza a listagem de panes."""
    return templates.TemplateResponse("panes/lista.html", {"request": request})


@router.get("/panes/{pane_id}/detalhes", response_class=HTMLResponse, include_in_schema=False)
async def detail_pane_page(request: Request, pane_id: str, _=Depends(get_current_user)):
    """Renderiza a visualização detalhada de uma pane."""
    return templates.TemplateResponse("panes/detalhe.html", {"request": request, "pane_id": pane_id})


@router.get("/frota", response_class=HTMLResponse, include_in_schema=False)
async def frota_page(request: Request, _=Depends(get_current_user)):
    """Visualização da Gestão de Frota Aeronaves"""
    return templates.TemplateResponse("aeronaves.html", {"request": request})


@router.get("/efetivo", response_class=HTMLResponse, include_in_schema=False)
async def efetivo_page(request: Request, _=Depends(get_current_user)):
    """Visualização da Gestão de Usuários e Efetivo (Militares) - Consulta livre, edição restrita"""
    return templates.TemplateResponse("efetivo.html", {"request": request})


@router.get("/inventario", response_class=HTMLResponse, include_in_schema=False)
async def inventario_page(request: Request, _=Depends(get_current_user)):
    """Visualização do Inventário de Equipamentos por Aeronave"""
    return templates.TemplateResponse("inventario.html", {"request": request})


@router.get("/inspecoes", response_class=HTMLResponse, include_in_schema=False)
async def inspecoes_page(request: Request, _=Depends(get_current_user)):
    """Módulo de Inspeções"""
    return templates.TemplateResponse("inspecoes/lista.html", {"request": request})


@router.get("/inspecoes/{id}/detalhes", response_class=HTMLResponse, include_in_schema=False)
async def detalhe_inspecao_page(request: Request, id: str, _=Depends(get_current_user)):
    """Visualização detalhada de uma inspeção."""
    return templates.TemplateResponse("inspecoes/detalhe.html", {"request": request, "inspecao_id": id})


@router.get("/vencimentos", response_class=HTMLResponse, include_in_schema=False)
async def vencimentos_page(request: Request, _=Depends(get_current_user)):
    """Visualização do Controle de Vencimentos da Frota"""
    return templates.TemplateResponse("vencimentos.html", {"request": request})


@router.get("/calendario", response_class=HTMLResponse, include_in_schema=False)
async def calendario_page(request: Request, _=Depends(get_current_user)):
    """Calendario operacional do SAA29."""
    return templates.TemplateResponse("calendario.html", {"request": request})


@router.get("/publicacoes", response_class=HTMLResponse, include_in_schema=False)
async def publicacoes_lista_page(request: Request, _=Depends(get_current_user)):
    """Busca unificada no acervo de manuais e resolução de mensagem do FIM."""
    return templates.TemplateResponse("publicacoes/lista.html", {"request": request})


@router.get("/publicacoes/viewer/{doc_id}", response_class=HTMLResponse, include_in_schema=False)
async def publicacoes_viewer_page(request: Request, doc_id: str, _=Depends(get_current_user)):
    """Viewer de PDF em canvas (PDF.js) — nunca iframe (D-F)."""
    return templates.TemplateResponse(
        "publicacoes/viewer.html", {"request": request, "doc_id": doc_id}
    )


@router.get("/configuracoes", response_class=HTMLResponse, include_in_schema=False)
async def configuracoes_page(request: Request, _: AdminRequired):
    """Página de Configurações do Sistema - Admin"""
    return templates.TemplateResponse("configuracoes.html", {"request": request})


# --- ROTAS MOBILE (/m/) ---

@router.get("/m/", response_class=HTMLResponse, include_in_schema=False)
@router.get("/m", response_class=HTMLResponse, include_in_schema=False)
async def mobile_frota_page(request: Request, user=Depends(get_current_user)):
    """Dashboard Cockpit Mobile — Lista de Frota para Linha de Voo."""
    return templates.TemplateResponse("mobile/frota.html", {"request": request, "user": user})


@router.get("/m/aeronave/{aeronave_id}", response_class=HTMLResponse, include_in_schema=False)
async def mobile_tarefas_aeronave_page(request: Request, aeronave_id: str, user=Depends(get_current_user)):
    """Lista de Tarefas e Panes da Aeronave para Mantenedor em 1 Toque."""
    return templates.TemplateResponse("mobile/tarefas_aeronave.html", {
        "request": request,
        "aeronave_id": aeronave_id,
        "user": user
    })


