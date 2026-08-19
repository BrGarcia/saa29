"""
app/modules/dashboard/router.py
Endpoints REST do módulo Dashboard Central.
"""

from fastapi import APIRouter, status
from app.bootstrap.dependencies import DBSession, CurrentUser
from app.modules.dashboard import service
from app.modules.dashboard.schemas import DashboardResumo, FrotaAgregadaItem

router = APIRouter()


@router.get(
    "/resumo",
    response_model=DashboardResumo,
    status_code=status.HTTP_200_OK,
    summary="Resumo do Dashboard Central",
    description=(
        "Retorna um consolidado de todas as informações operacionais críticas: "
        "panes abertas, vencimentos, inspeções em andamento, "
        "movimentações de inventário e status da frota. "
        "Acessível a todos os perfis autenticados."
    ),
)
async def get_dashboard_resumo(
    db: DBSession,
    _: CurrentUser,
) -> DashboardResumo:
    """Endpoint do Dashboard — acessível a qualquer usuário autenticado."""
    return await service.get_dashboard_resumo(db)


@router.get(
    "/frota",
    response_model=list[FrotaAgregadaItem],
    status_code=status.HTTP_200_OK,
    summary="Frota agregada para o mobile",
    description=(
        "Uma única resposta por aeronave com contadores de panes abertas, "
        "inspeções ativas, tarefas pendentes, vencimentos vencidos/vencendo "
        "e slots vazios — evita o N+1 que a tela inicial do mobile fazia "
        "antes (1 requisição de panes por aeronave)."
    ),
)
async def get_frota_agregada_endpoint(
    db: DBSession,
    _: CurrentUser,
) -> list[FrotaAgregadaItem]:
    """Endpoint consumido por GET /m/ (frota_mobile.js) — sem paginação, a
    frota é pequena (um esquadrão local, RN-14)."""
    return await service.get_frota_agregada(db)
