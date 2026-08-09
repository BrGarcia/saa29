"""
tests/unit/test_vencimentos_inspecoes_media_prioridade.py
Testes de regressão para os achados de MÉDIA prioridade de
docs/backlog/Fable5/Etapa3.md:

    #6  N+1 em associar_controle_a_equipamento (vencimentos)
    #7  N+1 em abrir_inspecao (inspecoes)
    #8  TOCTOU/SAVEPOINT em criações protegidas por UNIQUE
    #10 ValueError -> exceções de domínio (contrato HTTP consistente)
    #11 Teto de paginação em listar_inspecoes
"""

import uuid
import pytest
from datetime import date, timedelta

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap.database import get_engine
from app.modules.equipamentos.models import ItemEquipamento, ModeloEquipamento
from app.modules.inspecoes import schemas as insp_schemas
from app.modules.inspecoes import service as insp_service
from app.modules.vencimentos import service as venc_service
from app.modules.vencimentos.models import ControleVencimento, EquipamentoControle, TipoControle
from app.modules.vencimentos.schemas import ProrrogacaoVencimentoCreate, TipoControleCreate
from app.shared.core import exceptions as domain_exc


async def _criar_modelo(db: AsyncSession, pn: str) -> ModeloEquipamento:
    modelo = ModeloEquipamento(id=uuid.uuid4(), part_number=pn, nome_generico="RADIO")
    db.add(modelo)
    await db.flush()
    return modelo


async def _criar_itens(db: AsyncSession, modelo_id: uuid.UUID, qtd: int) -> list[ItemEquipamento]:
    itens = [
        ItemEquipamento(id=uuid.uuid4(), modelo_id=modelo_id, numero_serie=f"SN-{uuid.uuid4().hex[:8]}")
        for _ in range(qtd)
    ]
    db.add_all(itens)
    await db.flush()
    return itens


class _ContadorDeQueries:
    def __init__(self):
        self.statements: list[str] = []

    def __enter__(self):
        event.listen(get_engine().sync_engine, "before_cursor_execute", self._contar)
        return self

    def __exit__(self, *exc):
        event.remove(get_engine().sync_engine, "before_cursor_execute", self._contar)

    def _contar(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def selects_para(self, tabela: str) -> int:
        return sum(1 for s in self.statements if "select" in s.lower() and tabela.lower() in s.lower())


# ------------------------------------------------------------------ #
#  #6 — N+1 em associar_controle_a_equipamento
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_associar_controle_a_equipamento_nao_gera_n_mais_1(db: AsyncSession):
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    tipo = TipoControle(id=uuid.uuid4(), nome=f"TC-{uuid.uuid4().hex[:6]}")
    db.add(tipo)
    await db.flush()
    await _criar_itens(db, modelo.id, qtd=5)

    with _ContadorDeQueries() as contador:
        await venc_service.associar_controle_a_equipamento(db, modelo.id, tipo.id, 12)

    # Antes: 1 SELECT em controle_vencimentos por item (5 itens -> 5 selects).
    # Depois: 1 único SELECT batched via IN.
    selects_controle = contador.selects_para("controle_vencimentos")
    assert selects_controle <= 2, f"N+1 detectado: {selects_controle} selects em controle_vencimentos"

    # Efeito observável preservado: todos os itens ganham o controle.
    res = await db.execute(
        select(ControleVencimento).where(ControleVencimento.tipo_controle_id == tipo.id)
    )
    assert len(res.scalars().all()) == 5


# ------------------------------------------------------------------ #
#  #7 — N+1 em abrir_inspecao (regressão adicional à já existente em
#       test_inspecoes_refatoracao.py, focada na contagem de queries)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_abrir_inspecao_multiplos_tipos_usa_queries_batched(db: AsyncSession):
    from tests.unit.test_inspecoes_refatoracao import criar_usuario_teste, criar_aeronave_teste, criar_tipo_com_tarefas

    usuario = await criar_usuario_teste(db)
    aeronave = await criar_aeronave_teste(db)
    tipos_ids = []
    for _ in range(3):
        tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)
        tipos_ids.append(tipo.id)

    with _ContadorDeQueries() as contador:
        await insp_service.abrir_inspecao(
            db, insp_schemas.InspecaoCreate(aeronave_id=aeronave.id, tipos_inspecao_ids=tipos_ids), usuario.id
        )

    selects_tipos = contador.selects_para("tipos_inspecao")
    selects_templates = contador.selects_para("tarefas_template")
    assert selects_tipos <= 2, f"N+1 detectado em tipos_inspecao: {selects_tipos} selects"
    assert selects_templates <= 2, f"N+1 detectado em tarefas_template: {selects_templates} selects"


# ------------------------------------------------------------------ #
#  #8 — TOCTOU/SAVEPOINT
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_criar_tipo_controle_duplicado_retorna_conflito_de_dominio(db: AsyncSession):
    nome = f"TC-{uuid.uuid4().hex[:6]}"
    await venc_service.criar_tipo_controle(db, TipoControleCreate(nome=nome))

    with pytest.raises(domain_exc.ConflitoNegocioError, match="já existe"):
        await venc_service.criar_tipo_controle(db, TipoControleCreate(nome=nome))


@pytest.mark.asyncio
async def test_criar_tipo_controle_savepoint_absorve_integrity_error_sem_derrubar_sessao(db: AsyncSession):
    """Força a colisão de UNIQUE diretamente no caminho do SAVEPOINT (não no
    pre-check), inserindo o registro conflitante já com o mesmo valor
    normalizado (`.upper()`) que `criar_tipo_controle` grava. Confirma que o
    `IntegrityError` é convertido em erro de domínio e que a sessão continua
    utilizável em seguida — sem SAVEPOINT, um IntegrityError não tratado
    invalidaria toda a transação."""
    nome = f"TC-{uuid.uuid4().hex[:6]}".upper()
    tipo_id = uuid.uuid4()
    db.add(TipoControle(id=tipo_id, nome=nome))
    await db.flush()

    with pytest.raises(domain_exc.ConflitoNegocioError, match="já existe"):
        await venc_service.criar_tipo_controle(db, TipoControleCreate(nome=nome))

    # A sessão continua utilizável após o SAVEPOINT reverter só o insert conflitante.
    outro = await venc_service.criar_tipo_controle(db, TipoControleCreate(nome=f"TC-{uuid.uuid4().hex[:6]}"))
    assert outro.id is not None


@pytest.mark.asyncio
async def test_atualizar_tipo_controle_inexistente_levanta_404_nao_409(db: AsyncSession):
    """BUG-02 (achados_vencimentos.md): antes, `atualizar_tipo_controle`
    levantava um `ValueError` genérico que o router mapeava sempre para 409,
    mesmo quando a causa era "não encontrado". Agora o service diferencia:
    404 para ID inexistente, 409 apenas para nome duplicado."""
    from app.modules.vencimentos.schemas import TipoControleUpdate

    with pytest.raises(domain_exc.EntidadeNaoEncontradaError):
        await venc_service.atualizar_tipo_controle(
            db, uuid.uuid4(), TipoControleUpdate(nome="X")
        )


@pytest.mark.asyncio
async def test_atualizar_tipo_controle_nome_duplicado_levanta_409(db: AsyncSession):
    nome_a = f"TC-{uuid.uuid4().hex[:6]}"
    nome_b = f"TC-{uuid.uuid4().hex[:6]}"
    tipo_a = await venc_service.criar_tipo_controle(db, TipoControleCreate(nome=nome_a))
    await venc_service.criar_tipo_controle(db, TipoControleCreate(nome=nome_b))

    from app.modules.vencimentos.schemas import TipoControleUpdate

    with pytest.raises(domain_exc.ConflitoNegocioError):
        await venc_service.atualizar_tipo_controle(
            db, tipo_a.id, TipoControleUpdate(nome=nome_b)
        )


@pytest.mark.asyncio
async def test_associar_controle_modelo_inexistente_levanta_404_nao_409(db: AsyncSession):
    """MELHORIA-04 (achados_vencimentos.md): antes, um `modelo_id` inexistente
    caía no `except IntegrityError` (violação de FK) e sempre retornava a
    mensagem enganosa "já está associado". Agora é validado explicitamente."""
    tipo = TipoControle(id=uuid.uuid4(), nome=f"TC-{uuid.uuid4().hex[:6]}")
    db.add(tipo)
    await db.flush()

    with pytest.raises(domain_exc.EntidadeNaoEncontradaError):
        await venc_service.associar_controle_a_equipamento(db, uuid.uuid4(), tipo.id, 12)


@pytest.mark.asyncio
async def test_associar_controle_tipo_controle_inexistente_levanta_404_nao_409(db: AsyncSession):
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")

    with pytest.raises(domain_exc.EntidadeNaoEncontradaError):
        await venc_service.associar_controle_a_equipamento(db, modelo.id, uuid.uuid4(), 12)


@pytest.mark.asyncio
async def test_remover_controle_de_equipamento_inexistente_levanta_404(db: AsyncSession):
    """MELHORIA-05 (achados_vencimentos.md): antes, remover uma associação
    inexistente retornava sucesso silencioso (`if assoc: ...` sem `else`)."""
    with pytest.raises(domain_exc.EntidadeNaoEncontradaError):
        await venc_service.remover_controle_de_equipamento(db, uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_remover_controle_de_equipamento_com_vencimentos_dependentes_levanta_409(db: AsyncSession):
    """Achado adicional ALTA (achados_vencimentos.md): sem essa checagem,
    remover a regra deixava os `ControleVencimento` já criados para os itens
    do PN "zumbis" — visíveis na matriz, marchando para VENCIDO, e
    impossíveis de dar baixa (`registrar_execucao` passaria a falhar sempre,
    pois a regra de periodicidade não existiria mais)."""
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    tipo = TipoControle(id=uuid.uuid4(), nome=f"TC-{uuid.uuid4().hex[:6]}")
    db.add(tipo)
    await db.flush()
    # associar_controle_a_equipamento cria o ControleVencimento retroativo
    # para os itens já existentes do PN.
    await _criar_itens(db, modelo.id, qtd=1)
    await venc_service.associar_controle_a_equipamento(db, modelo.id, tipo.id, 12)

    with pytest.raises(domain_exc.ConflitoNegocioError):
        await venc_service.remover_controle_de_equipamento(db, modelo.id, tipo.id)


@pytest.mark.asyncio
async def test_remover_controle_de_equipamento_sem_vencimentos_dependentes_sucede(db: AsyncSession):
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    tipo = TipoControle(id=uuid.uuid4(), nome=f"TC-{uuid.uuid4().hex[:6]}")
    db.add(tipo)
    await db.flush()
    # Nenhum item existente para o PN -> nenhum ControleVencimento criado.
    await venc_service.associar_controle_a_equipamento(db, modelo.id, tipo.id, 12)

    await venc_service.remover_controle_de_equipamento(db, modelo.id, tipo.id)

    res = await db.execute(
        select(EquipamentoControle).where(
            EquipamentoControle.modelo_id == modelo.id, EquipamentoControle.tipo_controle_id == tipo.id
        )
    )
    assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_cancelar_prorrogacao_vencimento_inexistente_levanta_404(db: AsyncSession):
    with pytest.raises(domain_exc.EntidadeNaoEncontradaError):
        await venc_service.cancelar_prorrogacao(db, uuid.uuid4())


@pytest.mark.asyncio
async def test_cancelar_prorrogacao_sem_prorrogacao_ativa_levanta_409(db: AsyncSession):
    """MELHORIA-05: antes, cancelar quando não há prorrogação ativa retornava
    `{"success": False}` (200) em vez de sinalizar o conflito. Decisão do
    desenvolvedor (achados_vencimentos.md): 404 é reservado para
    `vencimento_id` inexistente; "existe mas sem prorrogação ativa" é um
    conflito de estado (409), não "recurso não encontrado"."""
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    item = (await _criar_itens(db, modelo.id, qtd=1))[0]
    tipo = TipoControle(id=uuid.uuid4(), nome=f"TC-{uuid.uuid4().hex[:6]}")
    db.add(tipo)
    await db.flush()
    venc = ControleVencimento(id=uuid.uuid4(), item_id=item.id, tipo_controle_id=tipo.id)
    db.add(venc)
    await db.flush()

    with pytest.raises(domain_exc.ConflitoNegocioError):
        await venc_service.cancelar_prorrogacao(db, venc.id)


@pytest.mark.asyncio
async def test_criar_tipo_inspecao_duplicado_retorna_conflito_de_dominio(db: AsyncSession):
    codigo = f"IF-{uuid.uuid4().hex[:6].upper()}"
    await insp_service.criar_tipo_inspecao(db, insp_schemas.TipoInspecaoCreate(codigo=codigo, nome="Original"))

    with pytest.raises(domain_exc.ConflitoNegocioError):
        await insp_service.criar_tipo_inspecao(db, insp_schemas.TipoInspecaoCreate(codigo=codigo, nome="Duplicada"))


# ------------------------------------------------------------------ #
#  #10 — contrato HTTP consistente (via router)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_atualizar_tipo_inspecao_inexistente_retorna_404_via_router(db: AsyncSession):
    """Antes: qualquer ValueError virava 409 no router, mesmo para 'não
    encontrado'. Depois: EntidadeNaoEncontradaError propaga como 404
    automaticamente (é uma HTTPException tipada), sem try/except no router."""
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from app.bootstrap.dependencies import get_current_user, get_db
    from app.modules.inspecoes.router import router as inspecoes_router
    from tests.unit.test_inspecoes_refatoracao import criar_usuario_teste

    usuario = await criar_usuario_teste(db, funcao="ENCARREGADO")
    app = FastAPI()
    app.include_router(inspecoes_router, prefix="/inspecoes")

    async def override_get_db():
        yield db

    async def override_user():
        return usuario

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.put(f"/inspecoes/tipos/{uuid.uuid4()}", json={"nome": "Novo nome"})

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_abrir_inspecao_duplicada_retorna_409_via_router(db: AsyncSession):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from app.bootstrap.dependencies import get_current_user, get_db
    from app.modules.inspecoes.router import router as inspecoes_router
    from tests.unit.test_inspecoes_refatoracao import criar_usuario_teste, criar_aeronave_teste, criar_tipo_com_tarefas

    usuario = await criar_usuario_teste(db, funcao="ENCARREGADO")
    aeronave = await criar_aeronave_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)
    await insp_service.abrir_inspecao(
        db, insp_schemas.InspecaoCreate(aeronave_id=aeronave.id, tipos_inspecao_ids=[tipo.id]), usuario.id
    )

    app = FastAPI()
    app.include_router(inspecoes_router, prefix="/inspecoes")

    async def override_get_db():
        yield db

    async def override_user():
        return usuario

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/inspecoes/",
            json={"aeronave_id": str(aeronave.id), "tipos_inspecao_ids": [str(tipo.id)]},
        )

    assert resp.status_code == 409


# ------------------------------------------------------------------ #
#  #11 — teto de paginação
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_listar_inspecoes_respeita_teto_de_seguranca(db: AsyncSession, monkeypatch):
    """Reduz o teto para tornar o teste rápido (sem criar 200+ inspeções) e
    confirma que o service nunca retorna mais que o teto configurado,
    mesmo quando o filtro pede um limit maior."""
    from tests.unit.test_inspecoes_refatoracao import criar_usuario_teste, criar_aeronave_teste, criar_tipo_com_tarefas

    monkeypatch.setattr(insp_service, "LIMITE_MAXIMO_LISTAGEM", 3)

    usuario = await criar_usuario_teste(db)
    tipo, _ = await criar_tipo_com_tarefas(db, obrigatorias=1)
    for _ in range(5):
        aeronave = await criar_aeronave_teste(db)
        await insp_service.abrir_inspecao(
            db, insp_schemas.InspecaoCreate(aeronave_id=aeronave.id, tipos_inspecao_ids=[tipo.id]), usuario.id
        )

    resultado = await insp_service.listar_inspecoes(
        db, insp_schemas.FiltroInspecao(skip=0, limit=1000)
    )
    assert len(resultado) <= 3


# ------------------------------------------------------------------ #
#  RISCO-03 — no máximo uma prorrogação ativa por controle
# ------------------------------------------------------------------ #

async def _criar_venc_para_prorrogacao(db: AsyncSession) -> ControleVencimento:
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    item = (await _criar_itens(db, modelo.id, qtd=1))[0]
    tipo = TipoControle(id=uuid.uuid4(), nome=f"TC-{uuid.uuid4().hex[:6]}")
    db.add(tipo)
    await db.flush()
    venc = ControleVencimento(id=uuid.uuid4(), item_id=item.id, tipo_controle_id=tipo.id)
    db.add(venc)
    await db.flush()
    return venc


@pytest.mark.asyncio
async def test_indice_unico_barra_duas_prorrogacoes_ativas_para_mesmo_controle(db: AsyncSession):
    """Confirma que a constraint do banco (não apenas a lógica de aplicação)
    impede duas prorrogações `ativo=True` simultâneas para o mesmo controle —
    a rede de segurança real contra a corrida descrita no RISCO-03."""
    from app.modules.vencimentos.models import ProrrogacaoVencimento
    from sqlalchemy.exc import IntegrityError

    venc = await _criar_venc_para_prorrogacao(db)

    db.add(ProrrogacaoVencimento(
        controle_id=venc.id, numero_documento="DOC-1",
        data_concessao=date.today(), data_nova_vencimento=date.today() + timedelta(days=30),
        dias_adicionais=30, ativo=True,
    ))
    await db.flush()

    db.add(ProrrogacaoVencimento(
        controle_id=venc.id, numero_documento="DOC-2",
        data_concessao=date.today(), data_nova_vencimento=date.today() + timedelta(days=60),
        dias_adicionais=60, ativo=True,
    ))
    with pytest.raises(IntegrityError):
        await db.flush()


@pytest.mark.asyncio
async def test_prorrogar_vencimento_concorrente_levanta_conflito_de_dominio(db: AsyncSession, monkeypatch):
    """Simula a corrida de duas requisições concorrentes de prorrogação:
    neutraliza a desativação prévia (equivalente a duas transações lendo
    "nenhuma prorrogação ativa" antes de qualquer commit) e confirma que o
    SAVEPOINT converte o IntegrityError do índice único em um erro de
    domínio, sem derrubar a sessão."""
    async def _no_op(db, vencimento):
        return None

    monkeypatch.setattr(venc_service, "_desativar_prorrogacoes_ativas", _no_op)

    venc = await _criar_venc_para_prorrogacao(db)
    dados = ProrrogacaoVencimentoCreate(
        numero_documento="DOC-1", data_concessao=date.today(), dias_adicionais=10
    )

    await venc_service.prorrogar_vencimento(db, venc.id, dados)

    with pytest.raises(domain_exc.ConflitoNegocioError):
        await venc_service.prorrogar_vencimento(db, venc.id, dados)

    # A sessão continua utilizável após o SAVEPOINT reverter só o insert conflitante.
    monkeypatch.undo()
    await venc_service.cancelar_prorrogacao(db, venc.id)


# ------------------------------------------------------------------ #
#  MELHORIA-06 — data de execução não pode estar no futuro
# ------------------------------------------------------------------ #

def test_controle_vencimento_update_rejeita_data_futura():
    from pydantic import ValidationError
    from app.modules.vencimentos.schemas import ControleVencimentoUpdate

    with pytest.raises(ValidationError):
        ControleVencimentoUpdate(data_ultima_exec=date.today() + timedelta(days=1))

    # Data de hoje é permitida (limite exato, não é "futuro").
    valido = ControleVencimentoUpdate(data_ultima_exec=date.today())
    assert valido.data_ultima_exec == date.today()


# ------------------------------------------------------------------ #
#  Achados adicionais (fora do escopo das 7 perguntas originais)
# ------------------------------------------------------------------ #

async def _criar_venc_executavel(db: AsyncSession, periodicidade: int = 12) -> ControleVencimento:
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    item = (await _criar_itens(db, modelo.id, qtd=1))[0]
    tipo = TipoControle(id=uuid.uuid4(), nome=f"TC-{uuid.uuid4().hex[:6]}")
    db.add(tipo)
    await db.flush()
    db.add(EquipamentoControle(id=uuid.uuid4(), modelo_id=modelo.id, tipo_controle_id=tipo.id, periodicidade_meses=periodicidade))
    await db.flush()
    venc = ControleVencimento(id=uuid.uuid4(), item_id=item.id, tipo_controle_id=tipo.id)
    db.add(venc)
    await db.flush()
    return venc


@pytest.mark.asyncio
async def test_registrar_execucao_rejeita_data_anterior_a_ultima_execucao(db: AsyncSession):
    """Achado adicional (achados_vencimentos.md, seção 'Em registrar_execucao'):
    sem essa checagem, uma data anterior à última execução registrada causava
    um retrocesso silencioso do último serviço realizado."""
    venc = await _criar_venc_executavel(db)
    usuario_id = uuid.uuid4()

    await venc_service.registrar_execucao(db, venc.id, date(2026, 6, 1), usuario_id)

    with pytest.raises(domain_exc.ConflitoNegocioError):
        await venc_service.registrar_execucao(db, venc.id, date(2026, 5, 1), usuario_id)


@pytest.mark.asyncio
async def test_registrar_execucao_grava_historico_imutavel_com_observacao(db: AsyncSession):
    """Achado adicional: antes, `registrar_execucao` sobrescrevia
    `data_ultima_exec` sem deixar rastro da execução anterior, e o campo
    `observacao` do schema era aceito pela API mas nunca persistido em
    lugar nenhum."""
    venc = await _criar_venc_executavel(db, periodicidade=6)
    usuario_id = uuid.uuid4()

    await venc_service.registrar_execucao(db, venc.id, date(2026, 1, 1), usuario_id, observacao="Primeira execução")
    await venc_service.registrar_execucao(db, venc.id, date(2026, 3, 1), usuario_id, observacao="Segunda execução")

    historico = await venc_service.listar_historico_execucao(db, venc.id)
    assert len(historico) == 2
    por_data = {h.data_execucao: h for h in historico}
    assert por_data[date(2026, 1, 1)].observacao == "Primeira execução"
    assert por_data[date(2026, 3, 1)].observacao == "Segunda execução"
    assert por_data[date(2026, 3, 1)].data_vencimento_calculada == date(2026, 9, 1)


@pytest.mark.asyncio
async def test_check_constraint_bloqueia_periodicidade_nao_positiva(db: AsyncSession):
    """Achado adicional: `periodicidade_meses` só era validado no schema
    Pydantic (`Field(gt=0)`), sem nenhuma rede de segurança no banco."""
    from sqlalchemy.exc import IntegrityError

    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    tipo = TipoControle(id=uuid.uuid4(), nome=f"TC-{uuid.uuid4().hex[:6]}")
    db.add(tipo)
    await db.flush()

    db.add(EquipamentoControle(id=uuid.uuid4(), modelo_id=modelo.id, tipo_controle_id=tipo.id, periodicidade_meses=0))
    with pytest.raises(IntegrityError):
        await db.flush()


@pytest.mark.asyncio
async def test_associar_controle_registra_alterado_por_id(db: AsyncSession):
    """Achado adicional: `EquipamentoControle` não tinha trilha de quem
    alterou a periodicidade — relevante para auditoria regulatória."""
    modelo = await _criar_modelo(db, f"PN-{uuid.uuid4().hex[:8]}")
    tipo = TipoControle(id=uuid.uuid4(), nome=f"TC-{uuid.uuid4().hex[:6]}")
    db.add(tipo)
    await db.flush()
    usuario_id = uuid.uuid4()

    assoc = await venc_service.associar_controle_a_equipamento(db, modelo.id, tipo.id, 12, usuario_id)
    assert assoc.alterado_por_id == usuario_id
    assert assoc.created_at is not None

    outro_usuario_id = uuid.uuid4()
    assoc2 = await venc_service.associar_controle_a_equipamento(db, modelo.id, tipo.id, 24, outro_usuario_id)
    assert assoc2.alterado_por_id == outro_usuario_id
