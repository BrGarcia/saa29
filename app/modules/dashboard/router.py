"""
app/modules/dashboard/router.py
Endpoints REST do módulo Dashboard Central.
"""

from fastapi import APIRouter, status
from app.bootstrap.dependencies import DBSession, CurrentUser
from app.modules.dashboard import service
from app.modules.dashboard.schemas import DashboardResumo

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
