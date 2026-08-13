"""
app/pages/router.py
Rotas do Frontend (Jinja2 Templates). Servindo o MVP de Interface.
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.bootstrap.dependencies import get_current_user, AdminRequired, DBSession
from app.modules.publicacoes import service as publicacoes_service

router = APIRouter(tags=["Frontend"])

# Sentinela de URL para `capitulo == ""` (PDFs soltos na raiz do manual, caso
# medido na edição `piloto-fim`) — um segmento de path vazio não roteia, e
# nenhum capítulo real do acervo usa este nome (Etapa 2 de
# docs/backlog/modulo_publicacoes/09_plano_configuracoes.md).
CAPITULO_RAIZ_SLUG = "_raiz_"

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


@router.get("/pedidos", response_class=HTMLResponse, include_in_schema=False)
async def pedidos_page(request: Request, _=Depends(get_current_user)):
    """Central de Pedidos — ciclo de vida administrativo dos pedidos de reposição."""
    return templates.TemplateResponse("pedidos.html", {"request": request})


@router.get("/encarregado", response_class=HTMLResponse, include_in_schema=False)
async def encarregado_page(request: Request, _=Depends(get_current_user)):
    """Ciência de Alterações — consolida panes/inspeções/inventário/vencimentos
    pendentes de transcrição para o SILOMS (feature_encarregado_ciencia.md)."""
    return templates.TemplateResponse("encarregado.html", {"request": request})


@router.get("/calendario", response_class=HTMLResponse, include_in_schema=False)
async def calendario_page(request: Request, _=Depends(get_current_user)):
    """Calendario operacional do SAA29."""
    return templates.TemplateResponse("calendario.html", {"request": request})


@router.get("/publicacoes", response_class=HTMLResponse, include_in_schema=False)
async def publicacoes_lista_page(request: Request, _=Depends(get_current_user)):
    """
    Explorador do acervo: árvore Categoria → Manual → Capítulo, busca por
    nome/conteúdo, resolução de mensagem do FIM. Client-fetch puro em
    `publicacoes_explorador.js` sobre `GET /api/manuais` e os demais
    endpoints de `app/modules/publicacoes` — esta rota não toca o banco.
    """
    return templates.TemplateResponse("publicacoes/lista.html", {"request": request})


@router.get("/publicacoes/viewer/{doc_id}", response_class=HTMLResponse, include_in_schema=False)
async def publicacoes_viewer_page(request: Request, doc_id: str, _=Depends(get_current_user)):
    """
    Viewer de PDF em canvas (PDF.js) — nunca iframe (D-F). Zoom, ajuste à
    largura/página, rotação, tela cheia, miniaturas sob demanda e busca de
    texto dentro do documento (`publicacoes_viewer.js`).

    `doc_id: str`, não `uuid.UUID`: um id malformado só falha quando o JS
    chama a API (`/api/documentos/{doc_id}`, que aí sim valida), não aqui —
    a página trata o erro no cliente em vez de devolver 422 de path.
    """
    return templates.TemplateResponse(
        "publicacoes/viewer.html", {"request": request, "doc_id": doc_id}
    )


@router.get("/publicacoes/avulsas", response_class=HTMLResponse, include_in_schema=False)
async def publicacoes_avulsas_page(request: Request, _=Depends(get_current_user)):
    """Lista/filtros/cadastro de BO/BS/NPO/BT (acervo B, M2)."""
    return templates.TemplateResponse("publicacoes/avulsas.html", {"request": request})


# Declaradas depois de /publicacoes/avulsas e /publicacoes/viewer/{doc_id}, seguindo
# a convenção de rotas estáticas antes das paramétricas no mesmo nível
# (equipamentos/router.py:194-195) — não há colisão real (segmentos literais
# distintos), mas mantém o padrão do projeto.
@router.get("/publicacoes/manuais/{codigo}", response_class=HTMLResponse, include_in_schema=False)
async def publicacoes_manual_page(
    request: Request, codigo: str, db: DBSession, _=Depends(get_current_user)
):
    """Capítulos de um manual da edição vigente (Etapa 2 — lacuna do M1)."""
    dados = await publicacoes_service.obter_manual_com_capitulos(db, codigo)
    return templates.TemplateResponse(
        "publicacoes/manual.html",
        {
            "request": request,
            "manual": dados["manual"],
            "capitulos": dados["capitulos"],
            "capitulo_raiz_slug": CAPITULO_RAIZ_SLUG,
        },
    )


@router.get(
    "/publicacoes/manuais/{codigo}/{capitulo}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def publicacoes_capitulo_page(
    request: Request,
    codigo: str,
    capitulo: str,
    db: DBSession,
    _=Depends(get_current_user),
    offset: int = 0,
    limit: int = 50,
):
    """
    Documentos de um capítulo, paginados por query string — `?offset=`/`?limit=`
    na própria URL, para não perder a propriedade de URL compartilhável.
    """
    offset = max(0, offset)
    limit = max(1, min(limit, 100))
    capitulo_real = "" if capitulo == CAPITULO_RAIZ_SLUG else capitulo

    manual = await publicacoes_service.obter_cabecalho_manual(db, codigo)
    total, documentos = await publicacoes_service.listar_documentos_do_manual(
        db, codigo, capitulo=capitulo_real, limit=limit, offset=offset
    )
    return templates.TemplateResponse(
        "publicacoes/capitulo.html",
        {
            "request": request,
            "manual": manual,
            "capitulo": capitulo_real,
            "capitulo_slug": capitulo,
            "documentos": [
                {
                    "id": doc.id,
                    "titulo": doc.titulo,
                    "paginas": doc.paginas,
                    "has_text": doc.has_text,
                    "viewer_url": f"/publicacoes/viewer/{doc.id}",
                }
                for doc in documentos
            ],
            "total": total,
            "offset": offset,
            "limit": limit,
        },
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


