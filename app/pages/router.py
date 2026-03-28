"""
app/pages/router.py
Rotas do Frontend (Jinja2 Templates). Servindo o MVP de Interface.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["Frontend"])

# Diretório base dos templates (raiz do repositório)
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_page(request: Request):
    """Renderiza a Dashboard Principal."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    """Renderiza a tela de Login."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/panes", response_class=HTMLResponse, include_in_schema=False)
async def list_panes_page(request: Request):
    """Renderiza a listagem de panes."""
    return templates.TemplateResponse("panes/lista.html", {"request": request})


@router.get("/panes/{pane_id}/detalhes", response_class=HTMLResponse, include_in_schema=False)
async def detail_pane_page(request: Request, pane_id: str):
    """Renderiza a visualização detalhada de uma pane."""
    return templates.TemplateResponse("panes/detalhe.html", {"request": request, "pane_id": pane_id})
