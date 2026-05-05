"""
app/modules/dashboard/schemas.py
Contratos Pydantic para o módulo de Dashboard Central.
Estes schemas são a fonte de verdade para a API e os testes.
"""

from pydantic import BaseModel


class PaneCritica(BaseModel):
    """Resumo de uma pane aberta para exibição no card de panes."""
    id: str
    matricula: str
    sistema: str | None = None
    data_abertura: str  # ISO 8601 string


class PanesSummary(BaseModel):
    """Resumo agregado do módulo de Panes."""
    total_abertas: int = 0
    total_resolvidas_mes: int = 0
    panes_criticas: list[PaneCritica] = []


class VencimentosSummary(BaseModel):
    """Contagem de vencimentos agrupados por status."""
    ok: int = 0
    vencendo: int = 0
    vencido: int = 0
    prorrogado: int = 0


class InspecaoAtiva(BaseModel):
    """Resumo de uma inspeção em andamento para exibição no card."""
    inspecao_id: str
    matricula: str
    tipos: list[str] = []       # ex: ["50h", "PS"]
    status: str
    data_fim_prevista: str | None = None  # ISO date string


class MovimentacaoRecente(BaseModel):
    """Registro de uma instalação recente de equipamento."""
    descricao: str              # ex: "VUHF-1 (slot VUHF1)"
    aeronave_matricula: str | None = None
    data: str                   # ISO date string


class AeronaveStatus(BaseModel):
    """Estado individual de uma aeronave na frota."""
    matricula: str
    status: str


class FrotaSummary(BaseModel):
    """Resumo da frota com contagens e estado individual de cada aeronave."""
    disponivel: int = 0
    operacional: int = 0
    indisponivel: int = 0
    inspecao: int = 0
    estocada: int = 0
    inativa: int = 0
    aeronaves: list[AeronaveStatus] = []


class DashboardResumo(BaseModel):
    """Schema raiz do endpoint GET /dashboard/resumo."""
    panes: PanesSummary = PanesSummary()
    vencimentos: VencimentosSummary = VencimentosSummary()
    inspecoes_ativas: list[InspecaoAtiva] = []
    movimentacoes_recentes: list[MovimentacaoRecente] = []
    frota: FrotaSummary = FrotaSummary()
