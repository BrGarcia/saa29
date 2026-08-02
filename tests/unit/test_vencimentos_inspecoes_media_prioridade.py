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

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap.database import get_engine
from app.modules.equipamentos.models import ItemEquipamento, ModeloEquipamento
from app.modules.inspecoes import schemas as insp_schemas
from app.modules.inspecoes import service as insp_service
from app.modules.vencimentos import service as venc_service
from app.modules.vencimentos.models import ControleVencimento, TipoControle
from app.modules.vencimentos.schemas import TipoControleCreate
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

    with pytest.raises(ValueError, match="já existe"):
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

    with pytest.raises(ValueError, match="já existe"):
        await venc_service.criar_tipo_controle(db, TipoControleCreate(nome=nome))

    # A sessão continua utilizável após o SAVEPOINT reverter só o insert conflitante.
    outro = await venc_service.criar_tipo_controle(db, TipoControleCreate(nome=f"TC-{uuid.uuid4().hex[:6]}"))
    assert outro.id is not None


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
