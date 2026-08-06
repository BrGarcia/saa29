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
from datetime import datetime, timezone, timedelta
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
                      status: str = "ABERTA", dias_atras: int = 0,
                      sistema_ata_id=None, descricao: str = "Falha de teste"):
    from app.modules.panes.models import Pane
    data = datetime.now(timezone.utc) - timedelta(days=dias_atras)
    pane = Pane(
        aeronave_id=aeronave_id,
        status=status,
        descricao=descricao,
        criado_por_id=criado_por_id,
        data_abertura=data,
        sistema_ata_id=sistema_ata_id,
    )
    if status == "RESOLVIDA":
        pane.data_conclusao = data + timedelta(hours=2)
    db.add(pane)
    await db.flush()
    return pane


async def _criar_sistema_ata(db: AsyncSession, descricao: str = "Ar Condicionado"):
    from app.modules.panes.models import SistemaAta
    sistema = SistemaAta(codigo=f"AT{uuid.uuid4().hex[:6]}", descricao=descricao)
    db.add(sistema)
    await db.flush()
    return sistema


async def _criar_instalacao(db: AsyncSession, aeronave_id,
                            criado_em: datetime | None = None,
                            removido_em: datetime | None = None):
    from app.modules.equipamentos.models import (
        ModeloEquipamento, SlotInventario, ItemEquipamento, Instalacao,
    )
    suffix = uuid.uuid4().hex[:8]
    modelo = ModeloEquipamento(part_number=f"PN-{suffix}", nome_generico=f"Equip-{suffix}")
    db.add(modelo)
    await db.flush()
    slot = SlotInventario(nome_posicao=f"SLOT-{suffix}", modelo_id=modelo.id)
    db.add(slot)
    await db.flush()
    item = ItemEquipamento(modelo_id=modelo.id, numero_serie=f"SN-{suffix}")
    db.add(item)
    await db.flush()

    criado_em = criado_em or datetime.now(timezone.utc)
    instalacao = Instalacao(
        item_id=item.id,
        aeronave_id=aeronave_id,
        slot_id=slot.id,
        data_instalacao=criado_em.date(),
        created_at=criado_em,
    )
    if removido_em is not None:
        instalacao.data_remocao = removido_em.date()
        instalacao.removido_em = removido_em
    db.add(instalacao)
    await db.flush()
    return instalacao


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


@pytest.mark.asyncio
async def test_pane_critica_sistema_usa_sistema_ata_quando_presente(db: AsyncSession):
    """MELHORIA-03: `sistema` deve refletir o sistema ATA real da pane, não
    um trecho arbitrário da descrição, quando `sistema_ata_id` está setado."""
    aeronave = await _criar_aeronave(db, f"TEST{uuid.uuid4().hex[:3]}")
    usuario = await _criar_usuario(db)
    sistema = await _criar_sistema_ata(db, descricao="Trem de Pouso")
    await _criar_pane(
        db, aeronave.id, usuario.id, status="ABERTA",
        sistema_ata_id=sistema.id, descricao="Descrição livre qualquer, não deveria aparecer aqui",
    )

    resultado = await service.get_panes_summary(db)

    assert any(p.sistema == "Trem de Pouso" for p in resultado.panes_criticas)


@pytest.mark.asyncio
async def test_pane_critica_sistema_usa_descricao_truncada_sem_sistema_ata(db: AsyncSession):
    """Sem `sistema_ata_id`, mantém o fallback de descrição truncada (comportamento pré-existente)."""
    aeronave = await _criar_aeronave(db, f"TEST{uuid.uuid4().hex[:3]}")
    usuario = await _criar_usuario(db)
    descricao_longa = "D" * 60
    await _criar_pane(db, aeronave.id, usuario.id, status="ABERTA", descricao=descricao_longa)

    resultado = await service.get_panes_summary(db)

    pane_res = next(p for p in resultado.panes_criticas if p.matricula == aeronave.matricula)
    assert pane_res.sistema == descricao_longa[:40] + "..."


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


@pytest.mark.asyncio
async def test_inspecoes_ativas_limitadas_a_5_itens(db: AsyncSession):
    """MELHORIA-07: diferente de panes/movimentações, get_inspecoes_ativas
    não tinha .limit(...) — o card podia crescer sem teto."""
    aeronave = await _criar_aeronave(db, f"TEST{uuid.uuid4().hex[:3]}")
    usuario = await _criar_usuario(db)
    for _ in range(8):
        await _criar_inspecao(db, aeronave.id, usuario.id, status="ABERTA")

    resultado = await service.get_inspecoes_ativas(db)

    assert len(resultado) <= 5


# ===========================================================================
# BLOCO 4: Frota Summary
# ===========================================================================

@pytest.mark.asyncio
async def test_frota_summary_banco_vazio_retorna_zeros(db: AsyncSession):
    """Com banco sem aeronaves (ou apenas frota padrão), todos os contadores devem ser consistentes."""
    resultado = await service.get_frota_summary(db)
    assert isinstance(resultado, FrotaSummary)
    assert resultado.disponivel >= 0
    assert resultado.indisponivel >= 0
    assert resultado.inspecao >= 0


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


@pytest.mark.asyncio
async def test_frota_summary_override_status_inspecao_ativa(db: AsyncSession):
    """O Dashboard deve mostrar INSPEÇÃO se houver inspeção ativa, mesmo que o status da aeronave seja DISPONIVEL."""
    aeronave = await _criar_aeronave(db, "T-INS", "DISPONIVEL")
    usuario = await _criar_usuario(db)
    await _criar_inspecao(db, aeronave.id, usuario.id, status="EM_ANDAMENTO")

    resultado = await service.get_frota_summary(db)

    a_res = next(a for a in resultado.aeronaves if a.matricula == "T-INS")
    assert a_res.status == "INSPEÇÃO"


@pytest.mark.asyncio
async def test_frota_summary_override_status_pane_aberta(db: AsyncSession):
    """BUG-01: antes, panes_ativas era um set[UUID] comparado contra uma str
    (ac_id_str) — nunca batia, e uma aeronave com pane ABERTA continuava
    aparecendo com o status base do banco em vez de INDISPONIVEL."""
    aeronave = await _criar_aeronave(db, "T-PANE", "DISPONIVEL")
    usuario = await _criar_usuario(db)
    await _criar_pane(db, aeronave.id, usuario.id, status="ABERTA")

    resultado = await service.get_frota_summary(db)

    a_res = next(a for a in resultado.aeronaves if a.matricula == "T-PANE")
    assert a_res.status == "INDISPONIVEL"


# ===========================================================================
# BLOCO 5: Movimentações Recentes
# ===========================================================================

# Nota de isolamento (mesma observação de test_panes_alta_prioridade.py): o
# banco de testes é SQLite in-memory compartilhado pela sessão inteira do
# pytest, e tests/architecture/test_performance_audit.py usa `db.commit()`
# explícito (fora do padrão flush+rollback), deixando linhas de Instalacao
# "TEST-PERF"/"TEST-HIST" persistidas para o resto da suíte. Por isso, os
# testes abaixo nunca assumem banco vazio nem contam o total de eventos —
# sempre filtram pela matrícula (única via uuid) da própria aeronave do teste.

@pytest.mark.asyncio
async def test_movimentacoes_recentes_instalacao_ativa_aparece_como_instalacao(db: AsyncSession):
    aeronave = await _criar_aeronave(db, f"TEST{uuid.uuid4().hex[:6]}")
    await _criar_instalacao(db, aeronave.id)

    resultado = await service.get_movimentacoes_recentes(db)

    evento = next((r for r in resultado if r.aeronave_matricula == aeronave.matricula), None)
    assert evento is not None
    assert evento.tipo == "INSTALACAO"
    assert "instalado" in evento.descricao


@pytest.mark.asyncio
async def test_movimentacoes_recentes_remocao_aparece_como_evento_distinto(db: AsyncSession):
    """MELHORIA-04: a instalação removida deve gerar DOIS eventos no feed
    (instalação + remoção), não um só como se ainda estivesse ativa — decisão
    do desenvolvedor (achados_dashboard.md, MELHORIA-04, opção b)."""
    aeronave = await _criar_aeronave(db, f"TEST{uuid.uuid4().hex[:6]}")
    # Timestamps o mais "agora" possível: precisam vencer a recência de
    # qualquer linha já commitada por outros testes na mesma sessão de banco
    # compartilhada (ver nota de isolamento acima).
    await _criar_instalacao(db, aeronave.id, removido_em=datetime.now(timezone.utc))

    resultado = await service.get_movimentacoes_recentes(db)

    eventos_desta_aeronave = [r for r in resultado if r.aeronave_matricula == aeronave.matricula]
    tipos = {r.tipo for r in eventos_desta_aeronave}
    assert tipos == {"INSTALACAO", "REMOCAO"}
    evento_remocao = next(r for r in eventos_desta_aeronave if r.tipo == "REMOCAO")
    assert "removido" in evento_remocao.descricao


@pytest.mark.asyncio
async def test_movimentacoes_recentes_remocao_de_instalacao_antiga_ainda_aparece_no_feed(db: AsyncSession):
    """Antes, a ordenação era só por created_at (data da instalação original)
    — uma instalação de 1 ano atrás nunca entraria no top-5 mais recente, e
    sua remoção de agora ficaria invisível no feed. Com o evento de remoção
    ordenado pelo próprio `removido_em`, ele aparece mesmo que a instalação
    original seja antiga."""
    aeronave = await _criar_aeronave(db, f"TEST{uuid.uuid4().hex[:6]}")
    await _criar_instalacao(
        db, aeronave.id,
        criado_em=datetime.now(timezone.utc) - timedelta(days=365),
        removido_em=datetime.now(timezone.utc),
    )

    resultado = await service.get_movimentacoes_recentes(db)

    evento = next((r for r in resultado if r.aeronave_matricula == aeronave.matricula), None)
    assert evento is not None
    assert evento.tipo == "REMOCAO"


@pytest.mark.asyncio
async def test_movimentacoes_recentes_limitadas_a_5_itens(db: AsyncSession):
    aeronave = await _criar_aeronave(db, f"TEST{uuid.uuid4().hex[:6]}")
    for i in range(8):
        await _criar_instalacao(
            db, aeronave.id, criado_em=datetime.now(timezone.utc) - timedelta(days=i)
        )

    resultado = await service.get_movimentacoes_recentes(db)

    assert len(resultado) <= 5


# ===========================================================================
# BLOCO 6: Orquestrador e Endpoint REST
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
