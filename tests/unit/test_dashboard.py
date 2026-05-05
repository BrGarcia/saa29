"""
tests/unit/test_dashboard.py
Suite de testes TDD para o módulo de Dashboard Central.

Metodologia:
    - Escrito ANTES da implementação do service.py (TDD — Red phase)
    - Usa banco SQLite in-memory via fixture `db` do conftest.py
    - Testa cada função de service de forma isolada
    - Testa o endpoint REST via `client_autenticado`
"""

import uuid
import pytest
import pytest_asyncio
from datetime import date, datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

import app.modules.dashboard.service as service
from app.modules.dashboard.schemas import (
    DashboardResumo, PanesSummary, VencimentosSummary,
    InspecaoAtiva, FrotaSummary,
)

# ---------------------------------------------------------------------------
# Helpers para criação de dados de teste
# ---------------------------------------------------------------------------

async def _criar_aeronave(db: AsyncSession, matricula: str, status: str = "DISPONIVEL"):
    from app.modules.aeronaves.models import Aeronave
    from datetime import date as date_type
    aeronave = Aeronave(
        matricula=matricula,
        serial_number=f"SN-{matricula}-{uuid.uuid4().hex[:4]}",
        modelo="A-29",
        status=status,
        data_inicio_operacao=date_type(2020, 1, 1),
    )
    db.add(aeronave)
    await db.flush()
    return aeronave


async def _criar_usuario(db: AsyncSession, username: str = None):
    from app.modules.auth.models import Usuario
    from app.modules.auth.security import hash_senha
    usuario = Usuario(
        nome="Teste Dashboard",
        posto="Sgt",
        funcao="MANTENEDOR",
        username=username or f"test_{uuid.uuid4().hex[:6]}",
        senha_hash=hash_senha("senha123"),
    )
    db.add(usuario)
    await db.flush()
    return usuario


async def _criar_pane(db: AsyncSession, aeronave_id, criado_por_id,
                      status: str = "ABERTA", dias_atras: int = 0):
    from app.modules.panes.models import Pane
    data = datetime.now(timezone.utc) - timedelta(days=dias_atras)
    pane = Pane(
        aeronave_id=aeronave_id,
        status=status,
        sistema_subsistema="AVIÔNICA",
        descricao="Falha de teste",
        criado_por_id=criado_por_id,
        data_abertura=data,
    )
    if status == "RESOLVIDA":
        pane.data_conclusao = data + timedelta(hours=2)
    db.add(pane)
    await db.flush()
    return pane


async def _criar_controle_vencimento(db: AsyncSession, status: str):
    from app.modules.vencimentos.models import ControleVencimento, TipoControle
    from app.modules.equipamentos.models import ModeloEquipamento, ItemEquipamento
    # Modelo de equipamento
    modelo = ModeloEquipamento(
        part_number=f"PN-{uuid.uuid4().hex[:6]}",
        nome_generico=f"Equip-{uuid.uuid4().hex[:4]}",
    )
    db.add(modelo)
    await db.flush()
    # Item de equipamento
    item = ItemEquipamento(
        modelo_id=modelo.id,
        numero_serie=f"SN-{uuid.uuid4().hex[:8]}",
        status="ATIVO",
    )
    db.add(item)
    await db.flush()
    # Tipo de controle
    tipo = TipoControle(
        nome=f"TC-{uuid.uuid4().hex[:4]}",
        descricao="Tipo de teste",
    )
    db.add(tipo)
    await db.flush()
    # Controle de vencimento
    controle = ControleVencimento(
        item_id=item.id,
        tipo_controle_id=tipo.id,
        status=status,
        origem="PADRAO",
    )
    db.add(controle)
    await db.flush()
    return controle


async def _criar_inspecao(db: AsyncSession, aeronave_id, aberto_por_id,
                          status: str = "ABERTA"):
    from app.modules.inspecoes.models import Inspecao
    inspecao = Inspecao(
        aeronave_id=aeronave_id,
        status=status,
        aberto_por_id=aberto_por_id,
    )
    db.add(inspecao)
    await db.flush()
    return inspecao


# ===========================================================================
# BLOCO 1: Panes Summary
# ===========================================================================

@pytest.mark.asyncio
async def test_panes_summary_banco_vazio_retorna_zeros(db: AsyncSession):
    """Com banco vazio, todos os contadores devem ser zero e a lista vazia."""
    resultado = await service.get_panes_summary(db)
    assert isinstance(resultado, PanesSummary)
    assert resultado.total_abertas == 0
    assert resultado.total_resolvidas_mes == 0
    assert resultado.panes_criticas == []


@pytest.mark.asyncio
async def test_panes_summary_conta_abertas_corretamente(db: AsyncSession):
    """Deve contar apenas panes com status ABERTA e ativas."""
    aeronave = await _criar_aeronave(db, f"TEST{uuid.uuid4().hex[:3]}")
    usuario = await _criar_usuario(db)
    await _criar_pane(db, aeronave.id, usuario.id, status="ABERTA")
    await _criar_pane(db, aeronave.id, usuario.id, status="ABERTA")
    await _criar_pane(db, aeronave.id, usuario.id, status="RESOLVIDA")

    resultado = await service.get_panes_summary(db)

    assert resultado.total_abertas == 2


@pytest.mark.asyncio
async def test_panes_summary_resolvidas_mes_nao_inclui_mes_anterior(db: AsyncSession):
    """Panes resolvidas no mês anterior NÃO devem ser contadas no resumo do mês atual."""
    aeronave = await _criar_aeronave(db, f"TEST{uuid.uuid4().hex[:3]}")
    usuario = await _criar_usuario(db)
    # Pane resolvida no mês atual (dias_atras=0 → data_conclusao no mês atual)
    await _criar_pane(db, aeronave.id, usuario.id, status="RESOLVIDA", dias_atras=0)
    # Pane resolvida 40 dias atrás (mês anterior)
    await _criar_pane(db, aeronave.id, usuario.id, status="RESOLVIDA", dias_atras=40)

    resultado = await service.get_panes_summary(db)

    assert resultado.total_resolvidas_mes == 1


@pytest.mark.asyncio
async def test_panes_criticas_ordenadas_por_data_abertura_mais_antiga(db: AsyncSession):
    """As panes críticas devem ser as mais antigas (data_abertura ASC)."""
    aeronave = await _criar_aeronave(db, f"TEST{uuid.uuid4().hex[:3]}")
    usuario = await _criar_usuario(db)
    await _criar_pane(db, aeronave.id, usuario.id, status="ABERTA", dias_atras=1)
    await _criar_pane(db, aeronave.id, usuario.id, status="ABERTA", dias_atras=10)
    await _criar_pane(db, aeronave.id, usuario.id, status="ABERTA", dias_atras=5)

    resultado = await service.get_panes_summary(db)

    datas = [p.data_abertura for p in resultado.panes_criticas]
    assert datas == sorted(datas), "Panes críticas devem estar ordenadas da mais antiga para a mais nova"


@pytest.mark.asyncio
async def test_panes_criticas_limitadas_a_5_itens(db: AsyncSession):
    """Mesmo com 10 panes abertas, panes_criticas retorna no máximo 5."""
    aeronave = await _criar_aeronave(db, f"TEST{uuid.uuid4().hex[:3]}")
    usuario = await _criar_usuario(db)
    for i in range(10):
        await _criar_pane(db, aeronave.id, usuario.id, status="ABERTA", dias_atras=i)

    resultado = await service.get_panes_summary(db)

    assert len(resultado.panes_criticas) <= 5


@pytest.mark.asyncio
async def test_panes_criticas_contem_matricula_da_aeronave(db: AsyncSession):
    """Cada pane crítica deve incluir a matrícula da aeronave."""
    matricula = f"T{uuid.uuid4().hex[:3].upper()}"
    aeronave = await _criar_aeronave(db, matricula)
    usuario = await _criar_usuario(db)
    await _criar_pane(db, aeronave.id, usuario.id, status="ABERTA")

    resultado = await service.get_panes_summary(db)

    assert any(p.matricula == matricula for p in resultado.panes_criticas)


# ===========================================================================
# BLOCO 2: Vencimentos Summary
# ===========================================================================

@pytest.mark.asyncio
async def test_vencimentos_summary_banco_vazio_retorna_zeros(db: AsyncSession):
    """Com banco vazio, todos os contadores de vencimento devem ser zero."""
    resultado = await service.get_vencimentos_summary(db)
    assert isinstance(resultado, VencimentosSummary)
    assert resultado.ok == 0
    assert resultado.vencendo == 0
    assert resultado.vencido == 0
    assert resultado.prorrogado == 0


@pytest.mark.asyncio
async def test_vencimentos_summary_agrupa_por_status(db: AsyncSession):
    """Deve agrupar corretamente os controles por status."""
    await _criar_controle_vencimento(db, "OK")
    await _criar_controle_vencimento(db, "OK")
    await _criar_controle_vencimento(db, "VENCENDO")
    await _criar_controle_vencimento(db, "VENCIDO")
    await _criar_controle_vencimento(db, "PRORROGADO")

    resultado = await service.get_vencimentos_summary(db)

    assert resultado.ok >= 2
    assert resultado.vencendo >= 1
    assert resultado.vencido >= 1
    assert resultado.prorrogado >= 1


# ===========================================================================
# BLOCO 3: Inspeções Ativas
# ===========================================================================

@pytest.mark.asyncio
async def test_inspecoes_ativas_banco_vazio_retorna_lista_vazia(db: AsyncSession):
    """Com banco vazio, deve retornar lista vazia."""
    resultado = await service.get_inspecoes_ativas(db)
    assert isinstance(resultado, list)
    assert resultado == []


@pytest.mark.asyncio
async def test_inspecoes_ativas_retorna_apenas_abertas_e_em_andamento(db: AsyncSession):
    """Deve incluir apenas inspeções com status ABERTA ou EM_ANDAMENTO."""
    aeronave = await _criar_aeronave(db, f"TEST{uuid.uuid4().hex[:3]}")
    usuario = await _criar_usuario(db)
    await _criar_inspecao(db, aeronave.id, usuario.id, status="ABERTA")
    await _criar_inspecao(db, aeronave.id, usuario.id, status="EM_ANDAMENTO")
    await _criar_inspecao(db, aeronave.id, usuario.id, status="CONCLUIDA")
    await _criar_inspecao(db, aeronave.id, usuario.id, status="CANCELADA")

    resultado = await service.get_inspecoes_ativas(db)

    assert len(resultado) == 2
    statuses = {r.status for r in resultado}
    assert statuses == {"ABERTA", "EM_ANDAMENTO"}


@pytest.mark.asyncio
async def test_inspecoes_ativas_inclui_matricula(db: AsyncSession):
    """Cada inspeção ativa deve conter a matrícula da aeronave."""
    matricula = f"T{uuid.uuid4().hex[:3].upper()}"
    aeronave = await _criar_aeronave(db, matricula)
    usuario = await _criar_usuario(db)
    await _criar_inspecao(db, aeronave.id, usuario.id, status="ABERTA")

    resultado = await service.get_inspecoes_ativas(db)

    assert any(r.matricula == matricula for r in resultado)


@pytest.mark.asyncio
async def test_inspecoes_ativas_retorna_instancias_corretas(db: AsyncSession):
    """Cada item da lista deve ser uma instância de InspecaoAtiva."""
    aeronave = await _criar_aeronave(db, f"TEST{uuid.uuid4().hex[:3]}")
    usuario = await _criar_usuario(db)
    await _criar_inspecao(db, aeronave.id, usuario.id, status="ABERTA")

    resultado = await service.get_inspecoes_ativas(db)

    for item in resultado:
        assert isinstance(item, InspecaoAtiva)


# ===========================================================================
# BLOCO 4: Frota Summary
# ===========================================================================

@pytest.mark.asyncio
async def test_frota_summary_banco_vazio_retorna_zeros(db: AsyncSession):
    """Com banco sem aeronaves, todos os contadores devem ser zero."""
    resultado = await service.get_frota_summary(db)
    assert isinstance(resultado, FrotaSummary)
    assert resultado.disponivel == 0
    assert resultado.indisponivel == 0
    assert resultado.inspecao == 0


@pytest.mark.asyncio
async def test_frota_summary_conta_por_status(db: AsyncSession):
    """Deve contar aeronaves agrupadas corretamente por status."""
    await _criar_aeronave(db, f"A{uuid.uuid4().hex[:3]}", "DISPONIVEL")
    await _criar_aeronave(db, f"B{uuid.uuid4().hex[:3]}", "DISPONIVEL")
    await _criar_aeronave(db, f"C{uuid.uuid4().hex[:3]}", "INDISPONIVEL")
    await _criar_aeronave(db, f"D{uuid.uuid4().hex[:3]}", "ESTOCADA")

    resultado = await service.get_frota_summary(db)

    assert resultado.disponivel >= 2
    assert resultado.indisponivel >= 1
    assert resultado.estocada >= 1


@pytest.mark.asyncio
async def test_frota_summary_inclui_lista_individual(db: AsyncSession):
    """Deve retornar a lista individual de aeronaves com matrícula e status."""
    matricula = f"A{uuid.uuid4().hex[:3].upper()}"
    await _criar_aeronave(db, matricula, "DISPONIVEL")

    resultado = await service.get_frota_summary(db)

    assert len(resultado.aeronaves) >= 1
    aeronave_res = next((a for a in resultado.aeronaves if a.matricula == matricula), None)
    assert aeronave_res is not None
    assert aeronave_res.status == "DISPONIVEL"


# ===========================================================================
# BLOCO 5: Orquestrador e Endpoint REST
# ===========================================================================

@pytest.mark.asyncio
async def test_get_dashboard_resumo_retorna_schema_completo(db: AsyncSession):
    """O orquestrador deve retornar um DashboardResumo com todos os campos."""
    resultado = await service.get_dashboard_resumo(db)
    assert isinstance(resultado, DashboardResumo)
    assert hasattr(resultado, "panes")
    assert hasattr(resultado, "vencimentos")
    assert hasattr(resultado, "inspecoes_ativas")
    assert hasattr(resultado, "movimentacoes_recentes")
    assert hasattr(resultado, "frota")


@pytest.mark.asyncio
async def test_endpoint_dashboard_retorna_200_para_usuario_autenticado(
    client_autenticado: AsyncClient,
):
    """O endpoint GET /dashboard/resumo deve retornar 200 para qualquer usuário autenticado."""
    response = await client_autenticado.get("/dashboard/resumo")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_endpoint_dashboard_retorna_401_sem_autenticacao(client: AsyncClient):
    """O endpoint GET /dashboard/resumo deve retornar 401 sem token."""
    response = await client.get("/dashboard/resumo")
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_endpoint_dashboard_estrutura_json(client_autenticado: AsyncClient):
    """O JSON retornado deve conter as 5 chaves esperadas."""
    response = await client_autenticado.get("/dashboard/resumo")
    assert response.status_code == 200
    data = response.json()
    assert "panes" in data
    assert "vencimentos" in data
    assert "inspecoes_ativas" in data
    assert "movimentacoes_recentes" in data
    assert "frota" in data
